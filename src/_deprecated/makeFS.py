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

CHARSET_EASY = string.ascii_letters + string.digits  # excluding special characters due to parsing difficulties

SUPPORTED_FILE_SYSTEMS = {
    "freebsd": ["ufs1", "ufs2", "zfs", "ext2", "ext3", "ext4"],
    "netbsd": ["4.3bsd", "ufs1", "ufs2", "ext2"],
    "openbsd": ["4.3bsd", "ufs1", "ufs2", "ext2"],
    "darwin": [],
    "linux": ["ext2", "ext3", "ext4", "zfs"],
}


def get_os_platform():
    return platform.system().lower()


def create_directory(_path):
    try:
        pathlib.Path(_path).mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logging.error(e)


def get_all_directories_in_path(dir_path):
    return [x[0] for x in os.walk(dir_path)]


def get_all_files_in_path(dir_path):
    list_of_file_paths = []
    for (_dir, _, file_names) in os.walk(dir_path):
        list_of_file_paths += [os.path.join(_dir, file) for file in file_names]
    for (_dir, dir_names, _) in os.walk(dir_path):
        list_of_file_paths += [os.path.join(_dir, d) for d in dir_names]
    return list_of_file_paths


def get_only_files_in_path(dir_path):
    list_of_file_paths = []
    for (_dir, _, file_names) in os.walk(dir_path):
        list_of_file_paths += [os.path.join(_dir, file) for file in file_names]
    return list_of_file_paths


class FileSystemCreator:
    def setup(self, **kwargs):
        if "file_system_name" in kwargs:
            self.file_system_name = kwargs["file_system_name"]
        if "file_system_type" in kwargs:
            self.file_system_type = kwargs["file_system_type"]
        if "file_system_size" in kwargs:
            self.file_system_size = kwargs["file_system_size"]
        if "generate_amount_of_files" in kwargs:
            self.generate_amount_of_files = kwargs["generate_amount_of_files"]
        if "max_file_size" in kwargs:
            self.max_file_size = kwargs["max_file_size"]
        if "mount_at" in kwargs:
            self.mount_at = kwargs["mount_at"]
        if "save_file_system_at" in kwargs:
            self.save_file_system_at = kwargs["save_file_system_at"]
        if "mode" in kwargs:
            self.mode = kwargs["mode"]
        else:
            pass

    def __init__(self):
        logging.basicConfig(level=logging.DEBUG)
        self.file_system_name = None
        self.file_system_type = None
        self.file_system_size = None
        self.generate_amount_of_files = None
        self.max_file_size = None
        self.mount_at = "/mnt"
        self.save_file_system_at = "/tmp/"
        self.block_device = None
        self.path_to_file_system = None
        self.seed = None
        self.file_system_logger = {}
        self.mode = None
        self.class_random_generator = random.Random()  # Class bound number generator
        self.target_maker = None

    def get_random_string_of_size(self, size, chars=CHARSET_EASY):
        self.class_random_generator.seed(self.seed)
        generated_string = "".join(self.class_random_generator.choice(chars) for x in range(size))
        return generated_string

    def create_new_path_at_random_location(self, list_of_dirs, ignore_sys_folders=False):
        self.class_random_generator.seed(self.seed)
        random_index_in_dir_list = self.class_random_generator.randint(0, len(list_of_dirs) - 1)
        name_length = self.class_random_generator.randint(1, 255)
        if ignore_sys_folders:
            if list_of_dirs[random_index_in_dir_list] not in [
                os.path.join(self.mount_at, "lost+found"),
                os.path.join(self.mount_at, ".snap"),
            ]:
                return os.path.join(list_of_dirs[random_index_in_dir_list], self.get_random_string_of_size(size=name_length),)
            else:
                logging.debug("lost+found or .snap reached, recalling method...")
                return self.create_new_path_at_random_location(list_of_dirs)
        else:
            return os.path.join(list_of_dirs[random_index_in_dir_list], self.get_random_string_of_size(size=name_length),)

    def init_file_system_creation(self):
        host_os = get_os_platform()
        if not any(x == self.file_system_type for x in SUPPORTED_FILE_SYSTEMS[host_os]):
            print("Requested file system not supported on current host os: {}".format(host_os))
            sys.exit(1)
        self.create_raw_disk_image()
        if host_os == "freebsd":
            self.target_maker = FreeBSD(
                self.file_system_type,
                self.file_system_size,
                self.file_system_name,
                self.path_to_file_system,
                self.mount_at,
                self.generate_amount_of_files,
                self.max_file_size,
                self.mode,
                self.save_file_system_at,
            )
        elif host_os == "netbsd":
            self.target_maker = NetBSD(
                self.file_system_type,
                self.file_system_size,
                self.file_system_name,
                self.path_to_file_system,
                self.mount_at,
                self.generate_amount_of_files,
                self.max_file_size,
                self.mode,
                self.save_file_system_at,
            )
        elif host_os == "openbsd":
            self.target_maker = OpenBSD(
                self.file_system_type,
                self.file_system_size,
                self.file_system_name,
                self.path_to_file_system,
                self.mount_at,
                self.generate_amount_of_files,
                self.max_file_size,
                self.mode,
                self.save_file_system_at,
            )
        elif host_os == "linux":
            self.target_maker = Ubuntu(
                self.file_system_type,
                self.file_system_size,
                self.file_system_name,
                self.path_to_file_system,
                self.mount_at,
                self.generate_amount_of_files,
                self.max_file_size,
                self.mode,
                self.save_file_system_at,
            )
        self.target_maker.create_file_system()

    def create_raw_disk_image(self):
        if not self.file_system_name:
            self.file_system_name = "fs_" + str(uuid.uuid4())
        logging.debug(self.file_system_name)
        self.path_to_file_system = os.path.join(self.save_file_system_at, self.file_system_name)
        logging.debug(self.path_to_file_system)
        with open(self.path_to_file_system, "wb") as file:
            file.write(b"0" * self.file_system_size)

    def _set_serialize_file_data(self, ctr, full_path):
        self.file_system_logger["files"]["seed_{}".format(ctr)]["file_name"] = str(pathlib.Path(full_path).name)
        self.file_system_logger["files"]["seed_{}".format(ctr)]["file_path"] = str(pathlib.Path(full_path).parent)
        self.file_system_logger["files"]["seed_{}".format(ctr)]["full_path"] = str(full_path)

    def create_new_hardlink_in_current_file_system_structure(self, list_of_files, list_of_only_directories, ctr):
        try:
            src = self.class_random_generator.choice(list_of_files)
            dst = self.create_new_path_at_random_location(list_of_only_directories)
            os.link(src, dst)
            self.file_system_logger["files"]["seed_{}".format(ctr)]["file_type"] = "HARD_LINK"
            self.file_system_logger["files"]["seed_{}".format(ctr)]["source"] = str(src)
            self._set_serialize_file_data(ctr, dst)
        except OSError:
            pass

    def create_new_symlink_in_current_file_system_structure(self, list_of_files, list_of_only_directories, ctr):
        try:
            src = self.class_random_generator.choice(list_of_files)
            dst = self.create_new_path_at_random_location(list_of_only_directories)
            os.symlink(src, dst)
            self.file_system_logger["files"]["seed_{}".format(ctr)]["file_type"] = "SYM_LINK"
            self.file_system_logger["files"]["seed_{}".format(ctr)]["source"] = str(src)
            self._set_serialize_file_data(ctr, dst)
        except OSError:
            pass

    def create_new_file_in_current_file_system_structure(self, location, ctr):
        try:
            file_size = self.class_random_generator.randrange(0.25 * self.max_file_size, self.max_file_size, 50)
            self.file_system_logger["files"]["seed_{}".format(ctr)]["file_type"] = "FILE"
            self.file_system_logger["files"]["seed_{}".format(ctr)]["file_size"] = file_size
            self._set_serialize_file_data(ctr, location)
            with open(location, "wb") as file:
                file.write(os.urandom(file_size))
        except OSError:
            pass

    def create_new_directory_in_current_file_system_structure(self, dir_path, ctr):
        if not os.path.exists(dir_path):
            try:
                pathlib.Path(dir_path).mkdir(parents=True, exist_ok=True)
                self.file_system_logger["files"]["seed_{}".format(ctr)]["file_type"] = "DIR"
                self._set_serialize_file_data(ctr, dir_path)
            except (OSError, BlockingIOError):
                self.create_new_directory_in_current_file_system_structure(dir_path[-3], ctr)

    def _setup_serialize(self):
        self.file_system_logger["fs_name"] = self.file_system_name
        self.file_system_logger["fs_type"] = self.file_system_type
        self.file_system_logger["fs_size (MB)"] = str(int(self.file_system_size) >> 20)
        self.file_system_logger["amount_files"] = self.generate_amount_of_files
        self.file_system_logger["max_file_size (MB)"] = str(int(self.max_file_size) >> 20)
        self.file_system_logger["files"] = {}
        self.file_system_logger["files"]["init_files"] = {}

    def _set_seed(self):
        if self.mode:
            self.seed = self.class_random_generator.getrandbits(random.randint(1, 1024))
        else:
            self.seed = None
        self.class_random_generator.seed(self.seed)

    def populate_file_system(self):
        self._setup_serialize()
        try:
            self._prepare_file_system_with_dummy_files()
        except OSError:
            pass
        for file_ctr in range(self.generate_amount_of_files):
            self._set_seed()
            self.file_system_logger["files"]["seed_{}".format(file_ctr)] = {}
            self.file_system_logger["files"]["seed_{}".format(file_ctr)]["seed_value"] = self.seed
            coin_toss = self.class_random_generator.randint(0, 7)
            all_dirs = get_all_directories_in_path(self.mount_at)
            if coin_toss in range(0, 4):
                self.file_system_logger["files"]["seed_{}".format(file_ctr)]["file_type"] = "FILE"
                self.create_new_file_in_current_file_system_structure(self.create_new_path_at_random_location(all_dirs), file_ctr)
            if coin_toss in range(4, 6):
                self.file_system_logger["files"]["seed_{}".format(file_ctr)]["file_type"] = "DIR"
                self.create_new_directory_in_current_file_system_structure(
                    self.create_new_path_at_random_location(all_dirs), file_ctr
                )
            if coin_toss == 6:
                self.file_system_logger["files"]["seed_{}".format(file_ctr)]["file_type"] = "SYM_LINK"
                all_files = get_all_files_in_path(self.mount_at)
                self.create_new_symlink_in_current_file_system_structure(all_files, all_dirs, file_ctr)
            if coin_toss == 7:
                self.file_system_logger["files"]["seed_{}".format(file_ctr)]["file_type"] = "HARD_LINK"
                only_files_no_dirs = get_only_files_in_path(self.mount_at)
                self.create_new_hardlink_in_current_file_system_structure(only_files_no_dirs, all_dirs, file_ctr)
        print(json.dumps(self.file_system_logger, separators=(",", ":")))

    def _get_random_name_for_dummy_file(self):
        self._set_seed()
        name_length = self.class_random_generator.randint(1, 255)
        _name = self.get_random_string_of_size(size=name_length)
        return _name

    def _prepare_file_system_with_dummy_files(self):
        for i, v in list(enumerate(["FILE", "SYM_LINK", "DIR"])):
            _name = self._get_random_name_for_dummy_file()
            _path = os.path.join(self.mount_at, _name)
            if "FILE" in v:
                _touch_fn = _name
                pathlib.Path(_path).touch()
            elif "SYM_LINK" in v:
                lnk_path = os.path.join(self.mount_at, _name)
                os.symlink(os.path.join(self.mount_at, _touch_fn), lnk_path)
            else:
                pathlib.Path(_path).mkdir(parents=True, exist_ok=True)
            self._set_serialize_init_files_data(_name, _path, i, v)

    def _set_serialize_init_files_data(self, _name, _path, i, v):
        self.file_system_logger["files"]["init_files"]["init_{}".format(i)] = {}
        self.file_system_logger["files"]["init_files"]["init_{}".format(i)]["seed"] = self.seed
        self.file_system_logger["files"]["init_files"]["init_{}".format(i)]["file_type"] = v
        self.file_system_logger["files"]["init_files"]["init_{}".format(i)]["name"] = _name
        self.file_system_logger["files"]["init_files"]["init_{}".format(i)]["path"] = self.mount_at
        self.file_system_logger["files"]["init_files"]["init_{}".format(i)]["full_path"] = _path
        if v == "SYM_LINK":
            self.file_system_logger["files"]["init_files"]["init_{}".format(i)]["source"] = self.file_system_logger["files"][
                "init_files"
            ]["init_0"]["full_path"]

    def parse_arguments(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("-fs", "--filesystem", type=str, help="ext2, ext3, ext4, ufs, zfs")
        parser.add_argument(
            "-s", "--size", type=int, default=1024, help="Specify the size in MB of the newly created file system, default: 1MB",
        )
        parser.add_argument(
            "-n", "--name", type=str, help="custom name you want to give the file system, default: fs_rndstr",
        )
        parser.add_argument(
            "-o", "--output_dir", type=str, help="Path to store the newly created file system, default: /tmp/",
        )
        parser.add_argument(
            "-p", "--populate", type=int, help="Number of files/directories that should be created",
        )
        parser.add_argument(
            "-ps", "--populate_size", type=int, help="Upper file size limit in KB for -p option",
        )
        parser.add_argument(
            "-mnt", "--mount", type=str, help="path to mount the filesystem for populating it",
        )
        parser.add_argument(
            "-m",
            "--mode",
            type=int,
            default=1,
            help="1 for determinism, or 0 for random (random does not use seeds and does no logging)",
        )
        parser.add_argument("-fsls", "--fileSystemLogFile_and_size", action="append", nargs=2)
        args = parser.parse_args()
        if args.fileSystemLogFile_and_size:
            with open(args.fileSystemLogFile_and_size[0][0]) as f:
                log_data = json.loads(f.read())

            shaper = FreeBSDShaper(
                log_data=log_data,
                fs_name=log_data["fs_name"],
                fs_type=log_data["fs_type"],
                fs_size=int(args.fileSystemLogFile_and_size[0][1]),
                amount_files=int(log_data["amount_files"]),
                max_file_size=int(log_data["max_file_size (MB)"]),
                path_to_file_system=None,
                mode=1,
            )
            shaper.init_file_system_creation()
            sys.exit(1)
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
            create_directory(args.output_dir)
        else:
            create_directory(self.save_file_system_at)
        if args.mount:
            create_directory(args.mount)
        else:
            create_directory(self.mount_at)
        if args.mode:
            self.mode = 1
        else:
            self.mode = 0
        return args


#######################################################################################################################
#######################################################################################################################
#######################################################################################################################


class Ubuntu(FileSystemCreator):
    def __init__(
        self, fs_type, fs_size, fs_name, path_to_file_system, mount_at, amount_files, max_file_size, mode, save_file_system_at,
    ):
        super(Ubuntu, self).__init__()
        self.file_system_type = fs_type
        self.file_system_size = fs_size
        self.file_system_name = fs_name
        self.path_to_file_system = path_to_file_system
        self.block_device = None
        self.mount_at = mount_at
        self.generate_amount_of_files = amount_files
        self.max_file_size = max_file_size
        self.mode = mode
        self.save_file_system_at = save_file_system_at

    def create_file_system(self):
        self.make_block_device()
        self.format_file_system()
        if self.generate_amount_of_files and self.max_file_size:
            if self.file_system_type != "zfs":
                self.mount_at = os.path.join(self.mount_at, self.file_system_name)
                FileSystemCreator.mount_at = self.mount_at
                logging.info("Mounting...")
                self.mount_file_system()
            self.populate_file_system()
            self.unmount_file_system()
        if self.file_system_type == "zfs" and not self.generate_amount_of_files:
            self.unmount_zfs()

    def format_file_system(self):
        if self.file_system_type in ["ext2", "ext3", "ext4"]:
            self.make_ext()
        elif self.file_system_type == "zfs":
            self.make_zfs()
        logging.debug("{} was created successfully".format(self.file_system_name))

    def make_block_device(self):
        cmd_find_loopdev = "losetup -f"
        self.block_device = subprocess.check_output(cmd_find_loopdev.split(), encoding="UTF-8").strip()
        cmd = "losetup {} {}".format(self.block_device, self.path_to_file_system)
        subprocess.check_output(cmd.split(), encoding="UTF-8").strip()
        logging.debug("block device {} created".format(self.block_device))

    def destroy_block_device(self):
        cmd_destroy_loopdev = "losetup -d {}".format(self.block_device)
        subprocess.call(cmd_destroy_loopdev.split(), stdout=subprocess.DEVNULL)

    def make_ext(self):
        cmd = "/sbin/mkfs.{} -v {}".format(self.file_system_type, self.path_to_file_system)
        subprocess.call(cmd.split(), stdout=subprocess.DEVNULL)

    def make_zfs(self):
        self.file_system_name = "pool_" + self.file_system_name
        subprocess.call("zpool create {} {}".format(self.file_system_name, self.block_device).split())
        subprocess.call("zfs set mountpoint=/mnt/{} {}".format(self.file_system_name, self.file_system_name).split())
        subprocess.call("zfs set atime=off {}".format(self.file_system_name).split())
        self.mount_at = os.path.join("/mnt", self.file_system_name)
        FileSystemCreator.mount_at = self.mount_at

    def mount_file_system(self):
        pathlib.Path(self.mount_at).mkdir(parents=True, exist_ok=True)
        cmd_mount = "/bin/mount -t {} {} {}".format(self.file_system_type, self.block_device, self.mount_at)
        logging.debug(cmd_mount)
        try:
            subprocess.call(cmd_mount.split(), stdout=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            logging.error("Failed to mount {} during populating phase".format(self.file_system_name))
            self.destroy_block_device()
            sys.exit(1)
        except RuntimeError as e:
            logging.error(e)
            self.destroy_block_device()
            sys.exit(1)

    def unmount_file_system(self):
        if self.file_system_type in ["ext2", "ext3", "ext4"]:
            self.unmount_ext_or_ufs()
        if self.file_system_type == "zfs":
            self.unmount_zfs()

    def unmount_ext_or_ufs(self):
        cmd_umnt = "/bin/umount {}".format(self.block_device)
        try:
            subprocess.call(cmd_umnt.split(), stdout=subprocess.DEVNULL)
        except RuntimeError as e:
            logging.error(e)
        finally:
            self.destroy_block_device()

    def unmount_zfs(self):
        cmd_export_pool = "zpool export {}".format(self.file_system_name)
        try:
            subprocess.call(cmd_export_pool.split(), stdout=subprocess.DEVNULL)
            self.destroy_block_device()
        except RuntimeError as e:
            logging.warning(e)
            sys.exit(1)


#######################################################################################################################
#######################################################################################################################
#######################################################################################################################


class FreeBSD(FileSystemCreator):
    def __init__(
        self, fs_type, fs_size, fs_name, path_to_file_system, mount_at, amount_files, max_file_size, mode, save_file_system_at,
    ):
        super(FreeBSD, self).__init__()
        self.file_system_type = fs_type
        self.file_system_size = fs_size
        self.file_system_name = fs_name
        self.path_to_file_system = path_to_file_system
        self.block_device = None
        self.mount_at = mount_at
        self.generate_amount_of_files = amount_files
        self.max_file_size = max_file_size
        self.mode = mode
        self.save_file_system_at = save_file_system_at

    def create_file_system(self):
        self.make_block_device()
        self.format_file_system()
        if self.generate_amount_of_files and self.max_file_size:
            if self.file_system_type != "zfs":
                self.mount_at = os.path.join(self.mount_at, self.file_system_name)
                FileSystemCreator.mount_at = self.mount_at
                logging.info("Mounting...")
                self.mount_file_system()
            self.populate_file_system()
            self.unmount_file_system()
        if self.file_system_type == "zfs" and not self.generate_amount_of_files:
            self.unmount_zfs()

    def format_file_system(self):
        if self.file_system_type in ["ext2", "ext3", "ext4"]:
            self.make_ext()
        elif "ufs" in self.file_system_type:
            self.make_ufs()
        elif self.file_system_type == "zfs":
            self.make_zfs()
        logging.debug("{} was created successfully".format(self.file_system_name))

    def make_block_device(self):
        cmd = "/sbin/mdconfig -a -t vnode -f {}".format(self.path_to_file_system)
        _blk_dev = subprocess.check_output(cmd.split(), encoding="UTF-8").strip()
        self.block_device = os.path.join("/dev", _blk_dev)
        logging.debug("block device {} created".format(self.block_device))
        return self.block_device

    def destroy_block_device(self):
        cmd_del_blk_dev = "/sbin/mdconfig -d -u {}".format(self.block_device)
        subprocess.call(cmd_del_blk_dev.split(), stdout=subprocess.DEVNULL)

    def make_ufs(self):
        if self.file_system_type == "ufs1":
            cmd = "/sbin/newfs -O 1 {}".format(self.block_device)
        else:
            cmd = "/sbin/newfs {}".format(self.block_device)
        subprocess.call(cmd.split(), close_fds=True, stdout=subprocess.DEVNULL)

    def make_ext(self):
        cmd = "/usr/local/sbin/mkfs.{} -v {}".format(self.file_system_type, self.path_to_file_system)
        subprocess.call(cmd.split(), stdout=subprocess.DEVNULL)

    def make_zfs(self):
        self.file_system_name = "pool_" + self.file_system_name
        subprocess.call("zpool create {} {}".format(self.file_system_name, self.block_device).split())
        subprocess.call("zfs set mountpoint=/mnt/{} {}".format(self.file_system_name, self.file_system_name).split())
        subprocess.call("zfs set atime=off {}".format(self.file_system_name).split())
        self.mount_at = os.path.join("/mnt", self.file_system_name)
        FileSystemCreator.mount_at = self.mount_at

    def mount_file_system(self):
        mnt_param = ""
        if self.file_system_type in ["ext2", "ext3", "ext4"]:
            mnt_param = "ext2fs"
        elif "ufs" in self.file_system_type:
            mnt_param = "ufs"
        pathlib.Path(self.mount_at).mkdir(parents=True, exist_ok=True)
        cmd_mount = "/sbin/mount -t {} {} {}".format(mnt_param, self.block_device, self.mount_at)
        logging.debug(cmd_mount)
        try:
            subprocess.call(cmd_mount.split(), stdout=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            logging.error("Failed to mount {} during populating phase".format(self.file_system_name))
            self.destroy_block_device()
            sys.exit(1)
        except RuntimeError as e:
            logging.error(e)
            self.destroy_block_device()
            sys.exit(1)

    def unmount_file_system(self):
        if self.file_system_type in ["ext2", "ext3", "ext4", "ufs1", "ufs2"]:
            self.unmount_ext_or_ufs()
        if self.file_system_type == "zfs":
            self.unmount_zfs()

    def unmount_ext_or_ufs(self):
        cmd_umnt = "/sbin/umount {}".format(self.block_device)
        try:
            subprocess.call(cmd_umnt.split(), stdout=subprocess.DEVNULL)
        except RuntimeError as e:
            logging.error(e)
        finally:
            self.destroy_block_device()

    def unmount_zfs(self):
        cmd_export_pool = "zpool export {}".format(self.file_system_name)
        try:
            subprocess.call(cmd_export_pool.split(), stdout=subprocess.DEVNULL)
            self.destroy_block_device()
        except RuntimeError as e:
            logging.warning(e)
            sys.exit(1)


#######################################################################################################################
#######################################################################################################################
#######################################################################################################################


class NetBSD(FileSystemCreator):
    def __init__(
        self, fs_type, fs_size, fs_name, path_to_file_system, mount_at, amount_files, max_file_size, mode, save_file_system_at,
    ):
        super(NetBSD, self).__init__()
        self.file_system_type = fs_type
        self.file_system_size = fs_size
        self.file_system_name = fs_name
        self.path_to_file_system = path_to_file_system
        self.block_device = None
        self.mount_at = mount_at
        self.generate_amount_of_files = amount_files
        self.max_file_size = max_file_size
        self.mode = mode
        self.save_file_system_at = save_file_system_at

    def create_file_system(self):
        self.make_block_device()
        self.format_file_system()
        if self.generate_amount_of_files and self.max_file_size:
            self.mount_at = os.path.join(self.mount_at, self.file_system_name)
            FileSystemCreator.mount_at = self.mount_at
            logging.info("Mounting...")
            self.mount_file_system()
            self.populate_file_system()
            self.unmount_file_system()

    def format_file_system(self):
        if self.file_system_type == "ext2":
            self.make_ext()
        elif "ufs" in self.file_system_type or "4.3bsd" in self.file_system_type:
            self.make_ufs()
        logging.debug("{} was created successfully".format(self.file_system_name))

    def make_block_device(self):
        cmd = "/usr/sbin/vndconfig vnd0 {}".format(self.path_to_file_system)
        _ = subprocess.check_output(cmd.split(), encoding="utf-8").strip()
        self.block_device = "/dev/vnd0"
        cmd_disklabel = "/sbin/disklabel {}".format(self.block_device)
        subprocess.call(cmd_disklabel.split(), stdout=subprocess.DEVNULL)
        self.block_device = "/dev/rvnd0"
        logging.debug("block device {} created".format(self.block_device))

    def destroy_block_device(self):
        cmd_del_blk_dev = "/usr/sbin/vndconfig -u {}".format(self.block_device.split("/")[-1])
        subprocess.call(cmd_del_blk_dev.split(), stdout=subprocess.DEVNULL)

    def make_ufs(self):
        if self.file_system_type == "4.3bsd":
            cmd = "/sbin/newfs -O 0 {}".format(self.block_device)
        elif self.file_system_type == "ufs1":
            cmd = "/sbin/newfs -O 1 {}".format(self.block_device)
        else:
            cmd = "/sbin/newfs -O 2 {}".format(self.block_device)
        subprocess.call(cmd.split(), close_fds=True, stdout=subprocess.DEVNULL)

    def make_ext(self):
        cmd = "/sbin/newfs_ext2fs {}".format(self.block_device)
        subprocess.call(cmd.split(), stdout=subprocess.DEVNULL)

    def mount_file_system(self):
        mnt_param = ""
        self.block_device = self.block_device.translate({ord(c): None for c in "r"})
        if self.file_system_type == "ext2":
            mnt_param = "ext2fs"
        elif "ufs" in self.file_system_type or "4.3bsd" in self.file_system_type:
            mnt_param = "ufs"
        pathlib.Path(self.mount_at).mkdir(parents=True, exist_ok=True)
        cmd_mount = "/sbin/mount -t {} {} {}".format(mnt_param, self.block_device, self.mount_at)
        logging.debug(cmd_mount)
        try:
            subprocess.call(cmd_mount.split(), stdout=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            logging.error("Failed to mount {} during populating phase".format(self.file_system_name))
            self.destroy_block_device()
            sys.exit(1)
        except RuntimeError as e:
            logging.error(e)
            self.destroy_block_device()
            sys.exit(1)

    def unmount_file_system(self):
        self.unmount_ext_or_ufs()

    def unmount_ext_or_ufs(self):
        cmd_umnt = "/sbin/umount {}".format(self.block_device)
        try:
            subprocess.call(cmd_umnt.split(), stdout=subprocess.DEVNULL)
        except RuntimeError as e:
            logging.error(e)
        finally:
            self.destroy_block_device()


#######################################################################################################################
#######################################################################################################################
#######################################################################################################################


class OpenBSD(FileSystemCreator):
    def __init__(
        self, fs_type, fs_size, fs_name, path_to_file_system, mount_at, amount_files, max_file_size, mode, save_file_system_at,
    ):
        super(OpenBSD, self).__init__()
        self.file_system_type = fs_type
        self.file_system_size = fs_size
        self.file_system_name = fs_name
        self.path_to_file_system = path_to_file_system
        self.block_device = None
        self.mount_at = mount_at
        self.generate_amount_of_files = amount_files
        self.max_file_size = max_file_size
        self.mode = mode
        self.save_file_system_at = save_file_system_at

    def create_file_system(self):
        self.make_block_device()
        self.format_file_system()
        if self.generate_amount_of_files and self.max_file_size:
            self.mount_at = os.path.join(self.mount_at, self.file_system_name)
            FileSystemCreator.mount_at = self.mount_at
            logging.info("Mounting...")
            self.mount_file_system()
            self.populate_file_system()
            self.unmount_file_system()

    def format_file_system(self):
        if self.file_system_type == "ext2":
            self.make_ext()
        elif "ufs" in self.file_system_type or "4.3bsd" in self.file_system_type:
            self.make_ufs()
        logging.debug("{} was created successfully".format(self.file_system_name))

    def make_block_device(self):
        cmd = "/sbin/vnconfig vnd0 {}".format(self.path_to_file_system)
        _ = subprocess.check_output(cmd.split(), encoding="utf-8").strip()
        self.block_device = "/dev/vnd0"
        cmd_disklabel = "/sbin/disklabel -A {}".format(self.block_device.split("/")[-1])
        subprocess.call(cmd_disklabel.split(), stdout=subprocess.DEVNULL)
        self.block_device = (
            subprocess.check_output(cmd_disklabel.split(), stderr=subprocess.STDOUT, encoding="utf-8").split()[1][:-1].strip()
        )
        logging.debug("block device {} created".format(self.block_device))

    def destroy_block_device(self):
        cmd_del_blk_dev = "/sbin/vnconfig -u {}".format(self.block_device.split("/")[-1])
        subprocess.call(cmd_del_blk_dev.split(), stdout=subprocess.DEVNULL)

    def make_ufs(self):
        if self.file_system_type == "4.3bsd":
            cmd = "/sbin/newfs -O 0 {}".format(self.block_device)
        elif self.file_system_type == "ufs1":
            cmd = "/sbin/newfs -O 1 {}".format(self.block_device)
        else:
            cmd = "/sbin/newfs -O 2 {}".format(self.block_device)
        subprocess.call(cmd.split(), close_fds=True, stdout=subprocess.DEVNULL)

    def make_ext(self):
        cmd = "/sbin/newfs_ext2fs -I {}".format(self.block_device)
        subprocess.call(cmd.split(), stdout=subprocess.DEVNULL)

    def mount_file_system(self):
        mnt_param = ""
        self.block_device = self.block_device.translate({ord(c): None for c in "r"})
        if self.file_system_type == "ext2":
            mnt_param = "ext2fs"
        elif "ufs" in self.file_system_type or "4.3bsd" in self.file_system_type:
            mnt_param = "ffs"
        pathlib.Path(self.mount_at).mkdir(parents=True, exist_ok=True)
        cmd_mount = "/sbin/mount -t {} {} {}".format(mnt_param, self.block_device, self.mount_at)
        logging.debug(cmd_mount)
        try:
            subprocess.call(cmd_mount.split(), stdout=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            logging.error("Failed to mount {} during populating phase".format(self.file_system_name))
            self.destroy_block_device()
            sys.exit(1)
        except RuntimeError as e:
            logging.error(e)
            self.destroy_block_device()
            sys.exit(1)

    def unmount_file_system(self):
        self.unmount_ext_or_ufs()

    def unmount_ext_or_ufs(self):
        cmd_umnt = "/sbin/umount {}".format(self.block_device)
        try:
            subprocess.call(cmd_umnt.split(), stdout=subprocess.DEVNULL)
        except RuntimeError as e:
            logging.error(e)
        finally:
            self.destroy_block_device()


#######################################################################################################################
#######################################################################################################################
#######################################################################################################################


class FreeBSDShaper(FreeBSD):
    def __init__(
        self, log_data, amount_files, fs_name, fs_size, fs_type, max_file_size, path_to_file_system, mode,
    ):
        self.data = log_data
        self.shaper_random_generator = random.Random()
        self.generate_amount_of_files = amount_files
        self.file_system_type = fs_type
        self.file_system_size = fs_size << 20
        self.path_to_file_system = path_to_file_system
        self.max_file_size = max_file_size << 10
        self.file_system_name = "REPLICA_{}MB_OF_".format(int(self.file_system_size) >> 20) + fs_name
        self.mount_at = os.path.join("/mnt/", self.file_system_name)
        self.mode = mode
        super(FreeBSDShaper, self).__init__(
            amount_files=self.generate_amount_of_files,
            fs_name=self.file_system_name,
            fs_size=self.file_system_size,
            fs_type=self.file_system_type,
            max_file_size=self.max_file_size,
            mode=1,
            mount_at=self.mount_at,
            path_to_file_system=self.path_to_file_system,
        )

    def init_file_system_creation(self):
        self.create_raw_disk_image()
        if get_os_platform() == "freebsd":
            self.create_file_system()

    def create_file_system(self):
        self.create_raw_disk_image()
        self.make_block_device()
        self.format_file_system()
        self.populate_file_system()
        self.unmount_file_system()

    def populate_file_system(self):
        if self.file_system_type != "zfs":
            self.mount_file_system()
        self._setup_serialize()
        self._init_files()
        for file_ctr in range(self.generate_amount_of_files):
            self.seed = self.data["files"]["seed_{}".format(file_ctr)]["seed_value"]
            self.file_system_logger["files"]["seed_{}".format(file_ctr)] = {}
            self.file_system_logger["files"]["seed_{}".format(file_ctr)]["seed_value"] = self.seed
            self.shaper_random_generator.seed(self.seed)
            coin_toss = self.shaper_random_generator.randint(1, 7)
            all_dirs = get_all_directories_in_path(self.mount_at)
            self._populate_on_coin_toss(all_dirs, coin_toss, file_ctr)
            if (
                self.file_system_logger["files"]["seed_{}".format(file_ctr)]["file_name"]
                != self.data["files"]["seed_{}".format(file_ctr)]["file_name"]
            ):
                self._populate_fs_error_logging(file_ctr)
        print("[+] Finished populating the replica fs successfully!")
        json.dumps(self.file_system_logger)

    def _populate_fs_error_logging(self, f):
        logging.error("Name mismatching for {}".format(self.data["files"]["seed_{}".format(f)]))
        logging.error("Expected: {}".format(self.data["files"]["seed_{}".format(f)]["file_name"]))
        logging.error("Got: {}".format(self.file_system_logger["files"]["seed_{}".format(f)]["file_name"]))
        sys.exit(1)

    def _populate_on_coin_toss(self, all_dirs, coin_toss, file_ctr):
        if coin_toss in range(1, 4):
            self.file_system_logger["files"]["seed_{}".format(file_ctr)]["file_type"] = "FILE"
            self.create_new_file_in_current_file_system_structure(self.create_new_path_at_random_location(all_dirs), file_ctr)
        if coin_toss in range(4, 6):
            self.file_system_logger["files"]["seed_{}".format(file_ctr)]["file_type"] = "DIR"
            self.create_new_directory_in_current_file_system_structure(
                self.create_new_path_at_random_location(all_dirs), file_ctr
            )
        if coin_toss == 6:
            self.file_system_logger["files"]["seed_{}".format(file_ctr)]["file_type"] = "SYM_LINK"
            all_files = get_all_files_in_path(self.mount_at)
            self.create_new_symlink_in_current_file_system_structure(all_files, all_dirs, file_ctr)
        if coin_toss == 7:
            self.file_system_logger["files"]["seed_{}".format(file_ctr)]["file_type"] = "HARD_LINK"
            only_files_no_dirs = get_only_files_in_path(self.mount_at)
            self.create_new_hardlink_in_current_file_system_structure(only_files_no_dirs, all_dirs, file_ctr)

    def _init_files(self):
        for i, v in list(enumerate(["FILE", "SYM_LINK", "DIR"])):
            self.seed = self.data["files"]["init_files"]["init_{}".format(i)]["seed"]
            self.shaper_random_generator.seed(self.seed)
            name_length = self.shaper_random_generator.randint(1, 255)
            _name = self.get_random_string_of_size(size=name_length)
            _path = os.path.join(self.mount_at, _name)
            if "FILE" in v:
                _touch_fn = _name
                pathlib.Path(_path).touch()
            elif "SYM_LINK" in v:
                lnk_path = os.path.join(self.mount_at, _name)
                os.symlink(os.path.join(self.mount_at, _touch_fn), lnk_path)
            else:
                pathlib.Path(_path).mkdir(parents=True, exist_ok=True)
            self._set_serialize_init_files_data(_name, _path, i, v)
            if _name != self.data["files"]["init_files"]["init_{}".format(i)]["name"]:
                self._init_fs_error_logging(i)

    def _init_fs_error_logging(self, i):
        logging.error("[!] Name mismatching for {}".format(self.data["files"]["init_files"]["init_{}".format(i)]["file_type"]))
        logging.error("Expected: {}".format(self.data["files"]["init_files"]["init_{}".format(i)]["name"]))
        logging.error("Got: {}".format(self.file_system_logger["files"]["init_files"]["init_{}".format(i)]["name"]))
        sys.exit(1)


def main():
    if os.geteuid() != 0:
        print("[!] Script needs to be run as root!")
        sys.exit(1)
    logging.basicConfig(level="ERROR")
    file_system_maker = FileSystemCreator()
    arguments = file_system_maker.parse_arguments()
    file_system_maker.setup(
        file_system_name=arguments.name,
        file_system_type=str(arguments.filesystem).lower(),
        file_system_size=arguments.size,
        generate_amount_of_files=arguments.populate,
        max_file_size=arguments.populate_size,
        mode=arguments.mode,
        save_file_system_at=arguments.output_dir,
    )
    file_system_maker.init_file_system_creation()


if __name__ == "__main__":
    sys.exit(main())
