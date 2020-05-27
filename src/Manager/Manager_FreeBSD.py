import logging
import os
import re

import paramiko


class FreeBSD:
    def __init__(self, rfile, mount_at, vm_object):
        logging.basicConfig(level=logging.DEBUG)
        self.bdev = None
        self.fs_type = None
        self.rfile = rfile
        self.mount_at = mount_at
        self.vm_object = vm_object
        self.pool = None

    def make_block_device(self):
        logging.debug("CREATING BLKDEV FOR: {}".format(self.rfile))
        cmd = "/sbin/mdconfig -a -t vnode -f {}".format(self.rfile)
        logging.debug(cmd)
        self.bdev = os.path.join("/dev", self.vm_object.exec_cmd_quiet(cmd))

    def destroy_bdev(self):
        cmd = "/sbin/mdconfig -d -u {}".format(self.bdev)
        logging.debug(cmd)
        return self.vm_object.exec_cmd_quiet(cmd)

    def _determine_fs_type(self):
        if self.vm_object.silent_vm_state():
            out = self.vm_object.exec_cmd_quiet("/usr/bin/file {}".format(self.rfile))
            match = re.search(r"ext[1-4] filesystem data", out)
            if match:
                self.fs_type = match.group(0).split()[0]
            elif "Unix Fast File system" in out:
                self.fs_type = "ufs"
            elif "data" in out:
                self.fs_type = "zfs"

    def _clean_mount_dir(self):
        self.vm_object.rm_files(self.mount_at)
        self.vm_object.mkdir(self.mount_at)

    def _get_mount_switch(self):
        if any(x == self.fs_type for x in ["ext2", "ext3", "ext4"]):
            flag = "ext2fs"
        elif self.fs_type == "ufs":
            flag = "ufs"
        else:
            logging.debug("Malformed file system")
            logging.debug('Trying mount -t "auto" ...')
            flag = "auto"
        return flag

    def _mount_ext_ufs(self):
        cmd = '/sbin/mount -t "{}" {} {}'.format(self._get_mount_switch(), self.bdev, self.mount_at)
        logging.debug(cmd)
        if not self.vm_object.exec_cmd_quiet(cmd):
            return 1  # Success
        else:
            logging.debug("Mounting of {} failed".format(self.bdev))  # Failed
            return 0

    def _mount_zfs(self):
        res = self.vm_object.exec_cmd_quiet("zpool import")
        logging.debug("ZPOOL IMPORT STDOUT: <<{}>>".format(res))
        if res and len(str(res)) > 2:
            self.pool = res.split()[1]
            if not self.vm_object.exec_cmd_quiet("zpool import {} -f".format(self.pool)):
                return 1  # Success
            else:
                return 0
        else:
            logging.debug("No zpool to import found")
            return 0

    def mount_file_system(self):
        try:
            self._clean_mount_dir()
            self._determine_fs_type()
            self.make_block_device()
            if any(mime in self.fs_type for mime in ["ext2", "ext3", "ext4", "ufs"]) and self._mount_ext_ufs():
                return 1
            # ugly hack for zfs
            elif "data" in self.fs_type and self._mount_zfs():
                return 1
            else:
                if self.vm_object.silent_vm_state():
                    return 0
                else:
                    return 2
        except TypeError:
            return None

    def _unmount_ext_ufs(self):
        cmd_mount = "/sbin/umount -f {}".format(self.mount_at)
        logging.debug(cmd_mount)
        if not self.vm_object.exec_cmd_quiet(cmd_mount) and not self.destroy_bdev():
            return 1  # Success
        else:
            logging.debug("Failed to properly umount {}".format(self.mount_at))
            return 0

    def _unmount_zfs(self):
        cmd_zpool_export = "zpool export {}".format(self.pool)
        logging.debug(cmd_zpool_export)
        if not self.vm_object.exec_cmd_quiet(cmd_zpool_export) and not self.destroy_bdev():
            return 1  # Success
        else:
            logging.debug("Failed to export pool".format(self.pool))
            return 0

    def unmount_file_system(self):
        try:
            if any(ext in self.fs_type for ext in ["ext2", "ext3", "ext4", "ufs"]):
                return self._unmount_ext_ufs()
            elif "data" in self.fs_type:
                return self._unmount_zfs()
        except (paramiko.ssh_exception.SSHException, paramiko.ssh_exception.NoValidConnectionsError,) as e:
            logging.debug(e)
