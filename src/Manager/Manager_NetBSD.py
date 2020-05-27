import logging
import re

import paramiko


class NetBSD:
    def __init__(self, rfile, mount_at, vm_object):
        logging.basicConfig(level=logging.DEBUG)
        self.bdev = None
        self.fs_type = None
        self.rfile = rfile
        self.mount_at = mount_at
        self.vm_object = vm_object
        self.pool = None

    def make_block_device(self):
        cmd = "/usr/sbin/vndconfig vnd0 {}".format(self.rfile)
        self.vm_object.exec_cmd_quiet(cmd)
        self.bdev = "/dev/vnd0"
        cmd_disklabel = "/sbin/disklabel {}".format(self.bdev)
        self.vm_object.exec_cmd_quiet(cmd_disklabel)
        self.bdev = "/dev/rvnd0"
        logging.debug("block device {} created".format(self.bdev))

    def destroy_block_device(self):
        cmd = "/usr/sbin/vndconfig -u {}".format(self.bdev.split("/")[-1])
        logging.debug(cmd)
        return self.vm_object.exec_cmd_quiet(cmd)

    def _determine_fs_type(self):
        if self.vm_object.silent_vm_state():
            file_output = self.vm_object.exec_cmd_quiet("/usr/bin/file {}".format(self.rfile))
            match = re.search(r"ext[1-4] filesystem data", file_output)
            if match:
                self.fs_type = match.group(0).split()[0]
            elif "Unix Fast File system" in file_output or "4.3bsd" in file_output:
                self.fs_type = "ufs"

    def _clean_mount_dir(self):
        self.vm_object.rm_files(self.mount_at)
        self.vm_object.mkdir(self.mount_at)

    def _get_mount_switch(self):
        flag = ""
        self.bdev = self.bdev.translate({ord(c): None for c in "r"})
        if self.fs_type == "ext2":
            flag = "ext2fs"
        elif "ufs" in self.fs_type:
            flag = "ufs"
        return flag

    def _mount_ext_ufs(self):
        cmd = "/sbin/mount -t {} {} {}".format(self._get_mount_switch(), self.bdev, self.mount_at)
        logging.debug(cmd)
        if not self.vm_object.exec_cmd_quiet(cmd):
            return 1  # Success
        else:
            logging.debug("Mounting of {} failed".format(self.bdev))  # Failed
            return 0

    def mount_file_system(self):
        self._clean_mount_dir()
        self._determine_fs_type()
        self.make_block_device()
        cmd_mount = "/sbin/mount -t {} {} {}".format(self._get_mount_switch(), self.bdev, self.mount_at)
        logging.debug(cmd_mount)
        if not self.vm_object.exec_cmd_quiet(cmd_mount):
            return 1
        else:
            logging.debug("Mounting of {} failed".format(self.bdev))  # Failed
            return 0

    def _unmount_ext_ufs(self):
        cmd_mount = "/sbin/umount -f {}".format(self.mount_at)
        logging.debug(cmd_mount)
        if not self.vm_object.exec_cmd_quiet(cmd_mount) and not self.destroy_block_device():
            return 1  # Success
        else:
            logging.debug("Failed to properly umount {}".format(self.mount_at))
            return 0

    def unmount_file_system(self):
        try:
            self._unmount_ext_ufs()
        except (paramiko.ssh_exception.SSHException, paramiko.ssh_exception.NoValidConnectionsError,) as e:
            logging.debug(e)
