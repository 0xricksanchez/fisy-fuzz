import logging
import re

import paramiko


class Ubuntu:
    def __init__(self, rfile, mount_at, vm_object):
        logging.basicConfig(level=logging.DEBUG)
        self.bdev = None
        self.fs_type = None
        self.rfile = rfile
        self.mount_at = mount_at
        self.vm_object = vm_object

    def make_block_device(self):
        cmd_find_loopdev = "losetup -f"
        self.bdev = self.vm_object.exec_cmd_quiet(cmd_find_loopdev)
        cmd = "losetup {} {}".format(self.bdev, self.rfile)
        self.vm_object.exec_cmd_quiet(cmd)
        logging.debug("block device {} created".format(self.bdev))

    def destroy_block_device(self):
        cmd = "losetup -d {}".format(self.bdev)
        logging.debug(cmd)
        return self.vm_object.exec_cmd_quiet(cmd)

    def _determine_fs_type(self):
        if self.vm_object.silent_vm_state():
            file_output = self.vm_object.exec_cmd_quiet("/usr/bin/file {}".format(self.rfile))
            match = re.search(r"ext[1-4] filesystem data", file_output)
            if match:
                self.fs_type = match.group(0).split()[0]

    def _clean_mount_dir(self):
        self.vm_object.rm_files(self.mount_at)
        self.vm_object.mkdir(self.mount_at)

    def _get_mount_switch(self):
        if any(x == self.fs_type for x in ["ext2", "ext3", "ext4"]):
            flag = self.fs_type
        else:
            logging.debug("Malformed file system")
            logging.debug('Trying mount -t "auto" ...')
            flag = "auto"
        return flag

    def _mount_ext(self):
        cmd = '/bin/mount -t "{}" {} {}'.format(self._get_mount_switch(), self.bdev, self.mount_at)
        logging.debug(cmd)
        if not self.vm_object.exec_cmd_quiet(cmd):
            return 1  # Success
        else:
            logging.debug("Mounting of {} failed".format(self.bdev))  # Failed
            return 0

    def mount_file_system(self):
        try:
            self._clean_mount_dir()
            self._determine_fs_type()
            self.make_block_device()
            if any(mime in self.fs_type for mime in ["ext2", "ext3", "ext4", "ufs"]) and self._mount_ext():
                return 1
            else:
                if self.vm_object.silent_vm_state():
                    return 0
                else:
                    return 2
        except TypeError:
            return None

    def _unmount_ext_ufs(self):
        cmd_mount = "/bin/umount -f {}".format(self.mount_at)
        logging.debug(cmd_mount)
        if not self.vm_object.exec_cmd_quiet(cmd_mount) and not self.destroy_block_device():
            return 1  # Success
        else:
            logging.debug("Failed to properly umount {}".format(self.mount_at))
            return 0

    def unmount_file_system(self):
        try:
            if any(ext in self.fs_type for ext in ["ext2", "ext3", "ext4"]):
                return self._unmount_ext_ufs()
        except (paramiko.ssh_exception.SSHException, paramiko.ssh_exception.NoValidConnectionsError,) as e:
            logging.debug(e)
