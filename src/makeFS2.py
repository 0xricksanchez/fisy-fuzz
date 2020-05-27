import argparse
import json
import logging
import os
import pathlib
import platform
import random
import string
import subprocess
import sys
import uuid
from shutil import rmtree
from typing import List

CHARSET_EASY = string.ascii_letters + string.digits  # excluding special characters due to parsing difficulties

SUPPORTED_FILE_SYSTEMS = {
    "freebsd": ["ufs1", "ufs2", "zfs", "ext2", "ext3", "ext4"],
    "netbsd": ["4.3bsd", "ufs1", "ufs2", "ext2"],
    "openbsd": ["4.3bsd", "ufs1", "ufs2", "ext2"],
    "linux": ["uf1", "ufs2", "ext2", "ext3", "ext4", "zfs"],
    "darwin": ["apfs"],
}


def _mk_dir(_path: str):
    pathlib.Path(_path).mkdir(parents=True, exist_ok=True)


def _get_all_dirs(_path: str):
    return [x[0] for x in os.walk(_path)]


def _get_all_files(_path: str):
    files = []
    for (_dir, _, file_names) in os.walk(_path):
        files += [os.path.join(_dir, file) for file in file_names]
    for (_dir, dir_names, _) in os.walk(_path):
        files += [os.path.join(_dir, d) for d in dir_names]
    return files


def _get_all_data_files(_path: str):
    files = []
    for (_dir, _, file_names) in os.walk(_path):
        files += [os.path.join(_dir, file) for file in file_names]
    return files


def _chk_availability(cmd: str):
    return not subprocess.call(["which", f"{cmd}"], stdout=subprocess.DEVNULL)


class GenericFilesystemCreator:
    def __init__(self):
        self.fs_name = None
        self.fs_type = None
        self.fs_size = None
        self.n_files = None
        self.max_fsize = None
        self.mount_pt = "/mnt"
        self.save_pt = "/tmp/"
        self.path = None
        self.seed = None
        self.logger = {}
        self.mode = None
        self.rng = random.Random()  # Class bound number generator
        self.host = platform.system().lower()
        self.data = None

    def __setup__(self, **kwargs):
        if "fs_name" in kwargs:
            self.fs_name = kwargs["fs_name"]
        if "fs_type" in kwargs:
            self.fs_type = kwargs["fs_type"]
        if "fs_size" in kwargs:
            self.fs_size = kwargs["fs_size"]
        if "n_files" in kwargs:
            self.n_files = kwargs["n_files"]
        if "max_fsize" in kwargs:
            self.max_fsize = kwargs["max_fsize"]
        if "mount_pt" in kwargs:
            self.mount_pt = kwargs["mount_pt"]
        if "save_pt" in kwargs:
            self.save_pt = kwargs["save_pt"]
        if "mode" in kwargs:
            self.mode = kwargs["mode"]
        if "data" in kwargs:
            self.data = kwargs["data"]

    def mk_file_system(self):
        self._parse_opts()
        if not any(x == self.fs_type for x in SUPPORTED_FILE_SYSTEMS[self.host]):
            logging.error(f"Requested file system not supported on current host os: {self.host}")
            sys.exit(1)
        self._init_mk_fs()
        host = self._set_target()
        self._create_fs(host)

    def _set_target(self):
        target = None
        if self.host == "freebsd":
            target = FreeBSD
        elif self.host == "netbsd":
            target = NetBSD
        elif self.host == "openbsd":
            target = OpenBSD
        elif self.host == "linux":
            target = Ubuntu
        elif self.host == "darwin":
            target = Darwin
        return target(
            fs=self.fs_type,
            size=self.fs_size,
            name=self.fs_name,
            location=self.path,
            mount_pt=self.mount_pt,
            n_files=self.n_files,
            max_fsize=self.max_fsize,
            mode=self.mode,
            save_pt=self.save_pt,
        )

    def _create_fs(self, target):
        target.mk_fs()
        if self.n_files and self.max_fsize:
            self._logger_setup()
            self._mount(target)
            self._init_fs_dummy_data()
            self._populate_fs()
            target.unmount_fs()
            rmtree(self.mount_pt)
        else:
            print(f"Created empty {self.fs_type} disk: {self.path} {self.fs_name}")
            if target.fs_type == "zfs":
                target.unmount_fs()

    def _mount(self, target):
        if self.fs_type != "zfs":
            target.mount_pt = os.path.join(self.mount_pt, self.fs_name)
            self.mount_pt = target.mount_pt
            logging.info("Mounting...")
            target.mount_fs()

    @staticmethod
    def generic_mount(flag, dev, location):
        try:
            subprocess.call(
                f"/sbin/mount -t {flag} {dev} {location}".split(), stdout=subprocess.DEVNULL,
            )
            return 1
        except subprocess.CalledProcessError:
            return 0

    @staticmethod
    def _generic_mk_zfs(name, dev):
        if not _chk_availability("zpool"):
            logging.error("Could not find zfs utils.")
            logging.error("Please install the appropriate tooling: e.g.: zfsutils-linux on Debian.")
            sys.exit(1)
        try:
            subprocess.call(f"zpool create {name} {dev}".split())
            subprocess.call(f"zfs set mountpoint=/mnt/{name} {name}".split())
            subprocess.call(f"zfs set atime=off {name}".split())
            return os.path.join("/mnt", name)
        except subprocess.CalledProcessError:
            logging.error("Failed in genericMakeZFS routine!")
            sys.exit(1)

    def _init_mk_fs(self):
        if not self.fs_name:
            self._set_fs_name()
        self._mk_raw_disk()

    def _mk_raw_disk(self):
        self.path = os.path.join(self.save_pt, self.fs_name)
        pathlib.Path(self.path).write_bytes(b"0" * self.fs_size)

    def _set_fs_name(self):
        self.fs_name = "fs_" + str(uuid.uuid4())

    def _populate_fs(self):
        for f_ctr in range(self.n_files):
            if self.data:
                self.seed = self.data["files"][f"seed_{f_ctr}"]["seed_value"]
                self.rng.seed(self.seed)
            else:
                self._set_seed()
            self._set_logger_seed(f_ctr)
            coin_toss = self.rng.randint(0, 7)
            all_dirs = _get_all_dirs(self.mount_pt)
            self._create_files(all_dirs, coin_toss, f_ctr)
            self._hierarchy_sanity_check(f_ctr)
        print(json.dumps(self.logger, separators=(",", ":"), indent=4))

    def _hierarchy_sanity_check(self, f_ctr):
        if self.data and self.logger["files"][f"seed_{f_ctr}"]["file_name"] != self.data["files"][f"seed_{f_ctr}"]["file_name"]:
            self._shpr_hierarchy_verification(f_ctr)

    def _shpr_hierarchy_verification(self, fctr):
        print("[!] Error reproducing same data hierarchy!!\n\n")
        print(f"During seed {fctr}")
        _expected = self.data["files"][f"seed_{fctr}"]["file_name"]
        _actual = self.logger["files"][f"seed_{fctr}"]["file_name"]
        print(f"Expected: {_expected}")
        print(f"Got: {_actual}")

    def _create_files(self, all_dirs, coin_toss, fctr):
        if coin_toss in range(0, 4):
            self._create_data_file(self._get_new_rndm_file_path(all_dirs), fctr)
        if coin_toss in range(4, 6):
            self._create_dir(self._get_new_rndm_file_path(all_dirs), fctr)
        if coin_toss == 6:
            all_files = _get_all_files(self.mount_pt)
            self._create_new_link(all_files, all_dirs, fctr, "SYM_LINK")
        if coin_toss == 7:
            all_data_files = _get_all_data_files(self.mount_pt)
            self._create_new_link(all_data_files, all_dirs, fctr, "HARD_LINK")

    def _logger_setup(self):
        self.logger["fs_name"] = self.fs_name
        self.logger["fs_type"] = self.fs_type
        self.logger["save_at"] = self.save_pt
        self.logger["fs_size (MB)"] = str(int(self.fs_size) >> 20)
        self.logger["amount_files"] = self.n_files
        self.logger["max_file_size (MB)"] = str(int(self.max_fsize) >> 20)
        self.logger["files"] = {}
        self.logger["files"]["init_files"] = {}

    def _get_rndm_str(self, size: int, chars=CHARSET_EASY):
        self.rng.seed(self.seed)
        generated_string = "".join(self.rng.choice(chars) for x in range(size))
        return generated_string

    def _get_rndm_path_from_lst(self, dirs: List, ignore_system_dirs=False):
        self.rng.seed(self.seed)
        rndm_idx = self.rng.randint(0, len(dirs) - 1)
        if ignore_system_dirs:
            if dirs[rndm_idx] not in [
                os.path.join(self.mount_pt, "lost+found"),
                os.path.join(self.mount_pt, ".snap"),
            ]:
                return dirs[rndm_idx]
            else:
                logging.debug("lost+found or .snap reached, recalling method...")
                return self._get_rndm_path_from_lst(dirs)
        else:
            return dirs[rndm_idx]

    def _get_new_rndm_file_path(self, dirs: List):
        self.rng.seed(self.seed)
        return os.path.join(self._get_rndm_path_from_lst(dirs), self._get_rndm_fname())

    def _get_rndm_fname(self):
        n_len = self.rng.randint(1, 255)
        return self._get_rndm_str(size=n_len)

    def _create_new_link(self, files: List, dirs: List, ctr: int, ftype: str):
        try:
            src = self.rng.choice(files)
            dst = self._get_new_rndm_file_path(dirs)
            if ftype == "SYM_LINK":
                self._create_symlink(src, dst)
            if ftype == "HARD_LINK":
                self._create_hardlink(src, dst)
            self._set_logger_generic(ctr, dst)
            self._set_logger_specific(ctr, ftype=ftype, src=str(src))
        except OSError:
            pass

    @staticmethod
    def _create_hardlink(src: str, dst: str):
        os.link(src, dst)

    @staticmethod
    def _create_symlink(src: str, dst: str):
        os.symlink(src, dst)

    def _create_data_file(self, location: str, ctr: int):
        try:
            fsize = self.rng.randrange(0.25 * self.max_fsize, self.max_fsize, 50)
            self._set_logger_generic(ctr, location)
            self._set_logger_specific(ctr, ftype="FILE", fsize=fsize)
            pathlib.Path(location).write_bytes(os.urandom(fsize))
        except OSError:
            pass

    def _create_dir(self, dpath: str, ctr: int):
        if not os.path.exists(dpath):
            try:
                _mk_dir(dpath)
                self._set_logger_specific(ctr, ftype="DIR")
                self._set_logger_generic(ctr, dpath)
            except (OSError, BlockingIOError):
                self._create_dir(dpath[-3], ctr)

    def _set_logger_generic(self, ctr: int, _path: str):
        self.logger["files"][f"seed_{ctr}"]["file_name"] = str(pathlib.Path(_path).name)
        self.logger["files"][f"seed_{ctr}"]["file_path"] = str(pathlib.Path(_path).parent)
        self.logger["files"][f"seed_{ctr}"]["full_path"] = str(_path)

    def _set_logger_specific(self, ctr: int, ftype=None, src=None, fsize=None):
        if ftype:
            self.logger["files"][f"seed_{ctr}"]["file_type"] = ftype
        if src:
            self.logger["files"][f"seed_{ctr}"]["source"] = src
        if fsize:
            self.logger["files"][f"seed_{ctr}"]["file_size"] = fsize

    def _set_seed(self):
        if self.mode:
            self.seed = self.rng.getrandbits(random.randint(1, 1024))
        else:
            self.seed = None
        self.rng.seed(self.seed)

    def _set_logger_seed(self, f_ctr: int):
        self.logger["files"][f"seed_{f_ctr}"] = {}
        self.logger["files"][f"seed_{f_ctr}"]["seed_value"] = self.seed

    def _init_fs_dummy_data(self):
        for i, v in list(enumerate(["FILE", "SYM_LINK", "DIR"])):
            if self.data:
                self.seed = self.data["files"]["init_files"][f"init_{i}"]["seed"]
                self.rng.seed(self.seed)
            else:
                self._set_seed()
            _name = self._get_rndm_fname()
            _path = os.path.join(self.mount_pt, _name)
            if "FILE" in v:
                _touch_fn = _name
                pathlib.Path(_path).touch()
            elif "SYM_LINK" in v:
                lnk_path = os.path.join(self.mount_pt, _name)
                os.symlink(os.path.join(self.mount_pt, _touch_fn), lnk_path)
            else:
                pathlib.Path(_path).mkdir(parents=True, exist_ok=True)
            self._set_logger_dummy_data(_name, _path, i, v)
            if self.data:
                if _name != self.data["files"]["init_files"][f"init_{i}"]["name"]:
                    self._shpr_dummy_sanity_check(i)

    def _shpr_dummy_sanity_check(self, ctr: int):
        _data = self.data["files"]["init_files"][f"init_{ctr}"]["file_type"]
        print(f"[!] Name mismatching for {_data}")
        _expected = self.data["files"]["init_files"][f"init_{ctr}"]["name"]
        _actual = self.logger["files"]["init_files"][f"init_{ctr}"]["name"]
        print(f" Expected: {_expected}")
        print(f" Got: {_actual}")
        sys.exit(1)

    def _set_logger_dummy_data(self, name: str, _path: str, i: int, ftype: str):
        self.logger["files"]["init_files"][f"init_{i}"] = {}
        self.logger["files"]["init_files"][f"init_{i}"]["seed"] = self.seed
        self.logger["files"]["init_files"][f"init_{i}"]["file_type"] = ftype
        self.logger["files"]["init_files"][f"init_{i}"]["name"] = name
        self.logger["files"]["init_files"][f"init_{i}"]["path"] = self.mount_pt
        self.logger["files"]["init_files"][f"init_{i}"]["full_path"] = _path
        if ftype == "SYM_LINK":
            self.logger["files"]["init_files"][f"init_{i}"]["source"] = self.logger["files"]["init_files"]["init_0"]["full_path"]

    def _parse_opts(self):
        log_data = None
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "-fs", "--filesystem", type=str, help="ext2, ext3, ext4, ufs1, ufs2, zfs, apfs",
        )
        parser.add_argument(
            "-s",
            "--size",
            type=int,
            default=10,
            help="Specify the size in MB of the newly created file system, (default: %(default)s)",
        )
        parser.add_argument(
            "-n", "--name", type=str, help="custom name you want to give the file system",
        )
        parser.add_argument(
            "-o",
            "--output_dir",
            type=str,
            default="/tmp/",
            help="Path to store the newly created file system, (default: %(default)s)",
        )
        parser.add_argument(
            "-p", "--populate", type=int, help="Number of files/directories that will be created on the fresh file system",
        )
        parser.add_argument(
            "-ps", "--populate_size", type=int, help="Max file size limit in KB for -p option",
        )
        parser.add_argument(
            "-mnt",
            "--mount",
            type=str,
            default="/mnt/",
            help="path to mount the filesystem for populating it, (default %(default)s)",
        )
        parser.add_argument(
            "-m",
            "--mode",
            type=int,
            default=1,
            help="1 for determinism, or 0 for random (does not use seeds and does no logging), " "(default: %(default)s)",
        )
        parser.add_argument(
            "-shp",
            "--shaper",
            action="append",
            nargs=2,
            help="Requires a valid json log file from the file system creation process and "
            "the desired new file system size to reshape the create a new file system "
            "with the same layout but of the new size!",
        )
        args = parser.parse_args()
        if args.shaper:
            log_data = json.loads(pathlib.Path(args.shaper[0][0]).read_text())
            args.name = f"SHP_{args.shaper[0][1]}__" + log_data["fs_name"]
            args.filesystem = str(log_data["fs_type"])
            args.size = int(args.shaper[0][1])
            args.populate = int(log_data["amount_files"])
            args.populate_size = int(log_data["max_file_size (MB)"]) << 10
            args.mode = 1
            args.output_dir = str(log_data["save_at"])
        if not args.size or not args.filesystem:
            parser.print_help()
            sys.exit(1)
        if args.size < 64 and args.filesystem == "zfs":
            parser.error("ZFS needs at least 64MB of disk size")
            sys.exit(1)
        elif args.size < 2 and args.filesystem == "ext3":
            parser.error("EXT3 needs at least 2MB of disk size")
            sys.exit(1)
        if (args.populate and not args.populate_size) or (args.populate_size and not args.populate):
            parser.error("-p and -ps depend on each other. Set both or neither of them!")
            sys.exit(1)
        elif args.populate_size and args.populate:
            args.populate_size = args.populate_size << 10  # shift bytes into Megabytes
        args.size = args.size << 20
        if args.populate and args.populate_size and (args.populate * args.populate_size > args.size):
            parser.error("New file system does not hold enough free space to write all requested files!")
            sys.exit(1)
        if args.output_dir:
            _mk_dir(args.output_dir)
        else:
            _mk_dir(self.save_pt)
        if args.mount:
            _mk_dir(args.mount)
        else:
            _mk_dir(self.mount_pt)
        if args.mode:
            self.mode = 1
        else:
            self.mode = 0

        self.__setup__(
            fs_name=args.name,
            fs_type=str(args.filesystem).lower(),
            fs_size=args.size,
            n_files=args.populate,
            max_fsize=args.populate_size,
            mode=args.mode,
            save_pt=args.output_dir,
            data=log_data,
        )


#######################################################################################################################
# DARTWIN SPECIFIC FILE SYSTEM CREATION STEPS                                                                          #
#######################################################################################################################


class Darwin(GenericFilesystemCreator):
    def __init__(self, fs, size, name, location, mount_pt, n_files, max_fsize, mode, save_pt):
        super(Darwin, self).__init__()
        self.fs_type = fs
        self.fs_size = size
        self.fs_name = name
        self.path = location
        self.dev = None
        self.mount_pt = mount_pt
        self.n_files = n_files
        self.max_fsize = max_fsize
        self.mode = mode
        self.save_pt = save_pt

    def _attach_disk(self):
        hdiutil_out = subprocess.check_output(
            f"/usr/bin/hdiutil attach -imagekey diskimage-class=CRawDiskImage -nomount {self.path}".split(), encoding="utf-8",
        ).strip()
        self.dev = hdiutil_out.split()[-2].strip()  # needs better sanity checks
        logging.debug(f"block device {self.dev} created")
        return self.dev

    def _detach_disk(self):
        subprocess.call(f"/usr/bin/hdiutil detach {self.dev}".split(), stdout=subprocess.DEVNULL)

    def mk_fs(self):
        if self.fs_type == "apfs":
            self._mk_apfs()
            self._attach_disk()
        logging.debug(f"{self.fs_name} was created successfully")

    def _mk_apfs(self):
        subprocess.call(f"/sbin/newfs_{self.fs_type} -v {self.fs_name} {self.path}".split())

    def mount_fs(self):
        _mk_dir(self.mount_pt)
        try:
            subprocess.call(
                f"/sbin/mount_{self.fs_type} {self.dev} {self.mount_pt}".split(), stdout=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            logging.error(f"Failed to mount {self.fs_name} during populating phase")
            sys.exit(1)
        except RuntimeError as e:
            logging.error(e)
            sys.exit(1)
        finally:
            self._detach_disk()

    def unmount_fs(self):
        if self.fs_type == "apfs":
            self._unmount_apfs()

    def _unmount_apfs(self):
        try:
            subprocess.call(f"/sbin/umount {self.dev}".split(), stdout=subprocess.DEVNULL)
        except RuntimeError as e:
            logging.error(e)
        finally:
            self._detach_disk()


#######################################################################################################################
# UBUNTU SPECIFIC FILE SYSTEM CREATION STEPS                                                                          #
#######################################################################################################################


class Ubuntu(GenericFilesystemCreator):
    def __init__(self, fs, size, name, location, mount_pt, n_files, max_fsize, mode, save_pt):
        super(Ubuntu, self).__init__()
        self.fs_type = fs
        self.fs_size = size
        self.fs_name = name
        self.path = location
        self.dev = None
        self.mount_pt = mount_pt
        self.n_files = n_files
        self.max_fsize = max_fsize
        self.mode = mode
        self.save_pt = save_pt

    def _mk_blk_dev(self):
        self.dev = subprocess.check_output("losetup -f".split(), encoding="utf-8").strip()
        subprocess.check_output(f"losetup {self.dev} {self.path}".split(), encoding="utf-8").strip()
        logging.debug(f"block device {self.dev} created")
        return self.dev

    def _unmk_blk_dev(self):
        subprocess.call(f"losetup -d {self.dev}".split(), stdout=subprocess.DEVNULL)

    def mk_fs(self):
        self._mk_blk_dev()
        if self.fs_type in ["ufs1", "ufs2"]:
            self._mk_ufs()
        if self.fs_type in ["ext2", "ext3", "ext4"]:
            self._mk_ext()
        if self.fs_type == "zfs":
            self._mk_zfs()
        logging.debug(f"{self.fs_name} was created successfully")

    def _mk_ufs(self):
        if not _chk_availability("mkfs.ufs"):
            logging.error("Could not find mkfs.ufs")
            logging.error(
                "Please install legacy package from:"
                "\thttps://mirrors.mediatemple.net/debian-archive/debian/pool/main/u/ufsutils/ufsutils_8.2-3_amd64.deb"
            )
            sys.exit(1)
        if self.fs_type == "ufs1":
            flag = 1
        else:
            flag = 2
        # -b and -f flags ensure the same default result compared to FreeBSD
        cmd = f"/sbin/mkfs.ufs -O {flag} -b 32768 -f 4096 {self.dev}"
        subprocess.call(cmd.split(), close_fds=True, stdout=subprocess.DEVNULL)
        print(
            f"[*] The Ubuntu kernel has by default no write permissions for UFS.\n\tEmpty file system '{self.fs_name}' created."
        )
        sys.exit(0)

    def _mk_ext(self):
        subprocess.call(
            f"/sbin/mkfs.{self.fs_type} -v {self.path}".split(), stdout=subprocess.DEVNULL,
        )

    def _mk_zfs(self):
        self.fs_name = "pool_" + self.fs_name
        GenericFilesystemCreator.mountAt = GenericFilesystemCreator._generic_mk_zfs(self.fs_name, self.dev)

    def mount_fs(self):
        _mk_dir(self.mount_pt)
        try:
            subprocess.call(
                f"/bin/mount -t {self.fs_type} {self.dev} {self.mount_pt}".split(), stdout=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            logging.error(f"Failed to mount {self.fs_name} during populating phase")
            self._unmk_blk_dev()
            sys.exit(1)
        except RuntimeError as e:
            logging.error(e)
            self._unmk_blk_dev()
            sys.exit(1)

    def unmount_fs(self):
        if self.fs_type in ["ext2", "ext3", "ext4"]:
            self._unmount_ext()
        if self.fs_type == "zfs":
            self._unmount_zfs()

    def _unmount_ext(self):
        try:
            subprocess.call(f"/bin/umount {self.dev}".split(), stdout=subprocess.DEVNULL)
        except RuntimeError as e:
            logging.error(e)
        finally:
            self._unmk_blk_dev()

    def _unmount_zfs(self):
        cmd_export_pool = "zpool export {}".format(self.fs_name)
        try:
            subprocess.call(cmd_export_pool.split(), stdout=subprocess.DEVNULL)
            self._unmk_blk_dev()
        except RuntimeError as e:
            logging.warning(e)
            sys.exit(1)


#######################################################################################################################
# FreeBSD SPECIFIC FILE SYSTEM CREATION STEPS                                                                         #
#######################################################################################################################


class FreeBSD(GenericFilesystemCreator):
    def __init__(
        self, fs, size, name, location, mount_pt, n_files, max_fsize, mode, save_pt, log_data=None,
    ):
        super(FreeBSD, self).__init__()
        self.fs_type = fs
        self.fs_size = size
        self.fs_name = name
        self.path = location
        self.dev = None
        self.mount_pt = mount_pt
        self.n_files = n_files
        self.max_fsize = max_fsize
        self.mode = mode
        self.save_pt = save_pt
        self.data = log_data

    def _mk_blk_dev(self):
        dev = subprocess.check_output(f"/sbin/mdconfig -a -t vnode -f {self.path}".split(), encoding="utf-8").strip()
        self.dev = os.path.join("/dev", dev)
        logging.debug(f"block device {self.dev} created")
        return self.dev

    def _unmk_blk_dev(self):
        subprocess.call(f"/sbin/mdconfig -d -u {self.dev}".split(), stdout=subprocess.DEVNULL)

    def mk_fs(self):
        self._mk_blk_dev()
        if self.fs_type in ["ext2", "ext3", "ext4"]:
            self._mk_ext()
        if self.fs_type == "zfs":
            self._mk_zfs()
        if self.fs_type in ["4.3bsd", "ufs1", "ufs2"]:
            self._mk_ufs()
        logging.debug(f"{self.fs_name} was created successfully")

    def _mk_ufs(self):
        if self.fs_type == "ufs1":
            cmd = f"/sbin/newfs -O 1 {self.dev}"
        else:
            cmd = f"/sbin/newfs {self.dev}"
        subprocess.call(cmd.split(), close_fds=True, stdout=subprocess.DEVNULL)

    def _mk_ext(self):
        subprocess.call(
            f"/usr/local/sbin/mkfs.{self.fs_type} -v {self.path}".split(), stdout=subprocess.DEVNULL,
        )

    def _mk_zfs(self):
        self.fs_name = "pool_" + self.fs_name
        GenericFilesystemCreator.mountAt = GenericFilesystemCreator._generic_mk_zfs(self.fs_name, self.dev)

    def mount_fs(self):
        _mk_dir(self.mount_pt)
        flag = ""
        if self.fs_type in ["ext2", "ext3", "ext4"]:
            flag = "ext2fs"
        elif "ufs" in self.fs_type:
            flag = "ufs"
        if not GenericFilesystemCreator.generic_mount(flag, self.dev, self.mount_pt):
            self._unmk_blk_dev()
            logging.error(f"Failed to mount {self.fs_name} during populating phase")
            sys.exit(1)

    def unmount_fs(self):
        if self.fs_type in ["ext2", "ext3", "ext4", "ufs1", "ufs2"]:
            self._unmount_ext_ufs()
        if self.fs_type == "zfs":
            self._unmount_zfs()

    def _unmount_ext_ufs(self):
        try:
            subprocess.call(f"/sbin/umount {self.dev}".split(), stdout=subprocess.DEVNULL)
        except RuntimeError as e:
            logging.error(e)
        finally:
            self._unmk_blk_dev()

    def _unmount_zfs(self):
        cmd_export_pool = "zpool export {}".format(self.fs_name)
        try:
            subprocess.call(cmd_export_pool.split(), stdout=subprocess.DEVNULL)
            self._unmk_blk_dev()
        except RuntimeError as e:
            logging.warning(e)
            sys.exit(1)


#######################################################################################################################
# OpenBSD SPECIFIC FILE SYSTEM CREATION STEPS                                                                         #
#######################################################################################################################


class OpenBSD:
    def __init__(self, fs, size, name, location, mount_pt, n_files, max_fsize, mode, save_pt):
        super(OpenBSD, self).__init__()
        self.fs_type = fs
        self.fs_size = size
        self.fs_name = name
        self.path = location
        self.dev = None
        self.mount_pt = mount_pt
        self.n_files = n_files
        self.max_fsize = max_fsize
        self.mode = mode
        self.save_pt = save_pt

    def _mk_blk_dev(self):
        subprocess.check_output(f"/sbin/vnconfig vnd0 {self.path}".split(), stderr=subprocess.STDOUT, encoding="utf-8",).strip()
        self.dev = (
            subprocess.check_output("/sbin/disklabel -A vnd0", stderr=subprocess.STDOUT, encoding="utf-8").split()[1][:-1].strip()
        )
        logging.debug(f"block device {self.dev} created")
        return self.dev

    def _unmk_blk_dev(self):
        subprocess.call(
            f'/sbin/vnconfig -u {self.dev.split("/")[-1]}'.split(), stdout=subprocess.DEVNULL,
        )

    def mk_fs(self):
        self._mk_blk_dev()
        if self.fs_type == "ext2":
            self._mk_ext()
        if self.fs_type in ["4.3bsd", "ufs1", "ufs2"]:
            self._mk_ufs()
        logging.debug(f"{self.fs_name} was created successfully")

    def _mk_ufs(self):
        if self.fs_type == "4.3bsd":
            cmd = f"/sbin/newfs -O 0 {self.dev}"
        elif self.fs_type == "ufs1":
            cmd = f"/sbin/newfs -O 1 {self.dev}"
        else:
            cmd = f"/sbin/newfs -O 2 {self.dev}"
        subprocess.call(cmd.split(), stdout=subprocess.DEVNULL)

    def _mk_ext(self):
        subprocess.call(f"/sbin/newfs_ext2fs -I {self.dev}".split(), stdout=subprocess.DEVNULL)

    def mount_fs(self):
        _mk_dir(self.mount_pt)
        flag = ""
        if self.fs_type == "ext2":
            flag = "ext2fs"
        if self.fs_type in ["ufs", "4.3bsd"]:
            flag = "ffs"
        if not GenericFilesystemCreator.generic_mount(flag, self.dev, self.mount_pt):
            self._unmk_blk_dev()
            logging.error(f"Failed to mount {self.fs_name} during populating phase")
            sys.exit(1)

    def unmount_fs(self):
        self._unmount_ext_ufs()

    def _unmount_ext_ufs(self):
        try:
            subprocess.call(f"/bin/umount {self.dev}".split(), stdout=subprocess.DEVNULL)
        except RuntimeError as e:
            logging.error(e)
        finally:
            self._unmk_blk_dev()


#######################################################################################################################
# NetBSD SPECIFIC FILE SYSTEM CREATION STEPS                                                                          #
#######################################################################################################################


class NetBSD:
    def __init__(self, fs, size, name, location, mount_pt, n_files, max_fsize, mode, save_pt):
        super(NetBSD, self).__init__()
        self.fs_type = fs
        self.fs_size = size
        self.fs_name = name
        self.path = location
        self.dev = None
        self.mount_pt = mount_pt
        self.n_files = n_files
        self.max_fsize = max_fsize
        self.mode = mode
        self.save_pt = save_pt

    def _mk_blk_dev(self):
        _ = subprocess.check_output(f"/usr/sbin/vndconfig vnd0 {self.path}".split(), encoding="utf-8").strip()
        self.dev = "/dev/vnd0"
        subprocess.call(f"/sbin/disklabel {self.dev}".split(), stdout=subprocess.DEVNULL)
        self.dev = "/dev/rvnd0"
        logging.debug(f"block device {self.dev} created")
        return self.dev

    def _unmk_blk_dev(self):
        subprocess.call(
            f'/usr/sbin/vndconfig -u {self.dev.split("/")[-1]}'.split(), stdout=subprocess.DEVNULL,
        )

    def mk_fs(self):
        self._mk_blk_dev()
        if self.fs_type in ["ext2", "ext3", "ext4"]:
            self._mk_ext()
        if self.fs_type in ["4.3bsd", "ufs1", "ufs2"]:
            self._mk_ufs()
        logging.debug(f"{self.fs_name} was created successfully")

    def _mk_ufs(self):
        if self.fs_type == "4.3bsd":
            cmd = f"/sbin/newfs -O 0 {self.dev}"
        elif self.fs_type == "ufs1":
            cmd = f"/sbin/newfs -O 1 {self.dev}"
        else:
            cmd = f"/sbin/newfs -O 2 {self.dev}"
        subprocess.call(cmd.split(), stdout=subprocess.DEVNULL)

    def _mk_ext(self):
        subprocess.call(f"/sbin/newfs_ext2fs {self.dev}".split(), stdout=subprocess.DEVNULL)

    def mount_fs(self):
        _mk_dir(self.mount_pt)
        flag = ""
        self.dev = self.dev.translate({ord(c): None for c in "r"})
        if self.fs_type == "ext2":
            flag = "ext2fs"
        if self.fs_type in ["ufs", "4.3bsd"]:
            flag = "ufs"
        if not GenericFilesystemCreator.generic_mount(flag, self.dev, self.mount_pt):
            self._unmk_blk_dev()
            logging.error(f"Failed to mount {self.fs_name} during populating phase")
            sys.exit(1)

    def unmount_fs(self):
        self._unmount_ext_ufs()

    def _unmount_ext_ufs(self):
        try:
            subprocess.call(f"/bin/umount {self.dev}".split(), stdout=subprocess.DEVNULL)
        except RuntimeError as e:
            logging.error(e)
        finally:
            self._unmk_blk_dev()


def main():
    if os.geteuid() != 0:
        print("[!] Script needs to be run as root!")
        sys.exit(1)
    logging.basicConfig(level="ERROR")
    return GenericFilesystemCreator().mk_file_system()


if __name__ == "__main__":
    main()
