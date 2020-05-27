import os
import random

from UserEmulation.UE_Generic import GenericUserEmulation


def get_random_list_entry(file_list):
    return random.choice(list(filter(None, file_list))).rstrip(",").strip()


class NetbsdUserEmulation:
    def __init__(self, vm_object, rpath):
        self.vm_object = vm_object
        self.rpath = rpath

    def prepare_netbsd_user_emulation(self):
        gen_user = GenericUserEmulation(vm_object=self.vm_object, remote_mount_path=self.rpath)
        users, groups = gen_user.get_users_and_groups_of_target_os()
        chflags_modes = [
            "arch",
            "nodump",
            "opaque",
            "sappnd",
            "schg",
            "snapshot",
            "sunlnk",
            "uappnd",
            "uarch",
            "uchg",
            "hidden",
        ]

        netbsd_user_emulation = [
            "/usr/bin/find {}/*".format(self.rpath),
            "/bin/ls -lah {}/*".format(get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="dir"))),
            "/usr/bin/touch {}".format(
                os.path.join(get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="dir")), "TOUCHED",)
            ),
            "/bin/mkdir -p {}/a/b/c".format(get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="dir"))),
            "/bin/dd if=/dev/urandom of={} bs={} count={}".format(
                os.path.join(get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="dir")), "DATA",),
                1 << 20,
                random.randint(1, 5),
            ),
            "/bin/ln {} {}".format(
                get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="file")),
                os.path.join(self.rpath, "HARDLINK"),
            ),
            "/bin/ln -s {} {}".format(
                get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="file")),
                os.path.join(self.rpath, "SOFTLINK"),
            ),
            "/usr/bin/file {}".format(get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="files"))),
            "/usr/bin/readlink {}".format(get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="link"))),
            "/usr/bin/stat {}".format(get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="dir"))),
            "/bin/cp -R {} {}/COPIED",  # no
            "/sbin/mknod {}".format(
                os.path.join(get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="dir")), "NODDED",)
            ),  # no
            '/bin/tar -jcvf {} "{} {}"'.format(
                os.path.join(self.rpath, "archive.bzip2"),
                get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="file")),
                get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="file")),
            ),
            "/bin/chmod {} {}".format(
                gen_user.get_random_chmod_mode(), get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="files")),
            ),
            "/sbin/chown {}:{} {}".format(
                get_random_list_entry(users),
                get_random_list_entry(groups),
                get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="files")),
            ),
            "/bin/chgrp {} {}".format(
                get_random_list_entry(groups), get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="files")),
            ),
            "/bin/mv {} {}",
            "/bin/echo APPENDED >> {}".format(get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="file"))),
            "/bin/rm -rf {}".format(get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="dir")[:-1])),
            "/usr/bin/chflags {} {}".format(
                get_random_list_entry(chflags_modes),
                get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="files")),
            ),
            "/usr/bin/split {} {}".format(
                get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="files")),
                get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="dir")),
            ),
            "/usr/bin/du {}".format(get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="files"))),
            "/usr/bin/wc {}".format(get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="files"))),
            "/usr/bin/dirname {}".format(get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="files"))),
            "/usr/bin/basename {}".format(get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="files"))),
        ]
        random.shuffle(netbsd_user_emulation)
        return netbsd_user_emulation

    def get_netbsd_backup_user_emulation(self):
        gen_user = GenericUserEmulation(vm_object=self.vm_object, remote_mount_path=self.rpath)

        netbsd_user_emulation = [
            "/usr/bin/find {}/*".format(self.rpath),
            "/bin/ls -lah {}/*".format(self.rpath),
            "/usr/bin/touch {}".format(os.path.join(self.rpath, "TOUCHED")),
            "/bin/mkdir -p {}/a/b/c".format(self.rpath),
            "/bin/dd if=/dev/urandom of={} bs={} count={}".format(
                os.path.join(self.rpath, "DATA"), 1 << 20, random.randint(1, 5)
            ),
            "/sbin/mknod {}".format(os.path.join(self.rpath, "NODDED")),
            "/bin/echo APPENDED >> {}".format(os.path.join(self.rpath, "ECHOED")),
        ]
        random.shuffle(netbsd_user_emulation)
        for entry in [
            "/bin/ln {} {}".format(os.path.join(self.rpath, "DATA"), "HARDLINK"),
            "/bin/ln -s {} {}".format(os.path.join(self.rpath, "DATA"), "SOFTLINK"),
            "/usr/bin/readlink {}".format(os.path.join(self.rpath, get_random_list_entry(["SOFTLINK", "HARDLINK"]))),
            "/bin/chmod {} {}".format(gen_user.get_random_chmod_mode(), os.path.join(self.rpath, "DATA")),
            "/bin/rm -rf {}/*".format(self.rpath),
        ]:
            netbsd_user_emulation.append(entry)
        return netbsd_user_emulation

    def set_netbsd_user_emulation(self):
        try:
            gen_user = GenericUserEmulation(vm_object=self.vm_object, remote_mount_path=self.rpath)
            res = gen_user.get_files_of_mounted_file_system("files")
            if any("Traceback" in pos for pos in res):
                user_emulation_command_list = self._failed_trav_user_emul()
            else:
                user_emulation_command_list = self.prepare_netbsd_user_emulation()
        except AttributeError:
            user_emulation_command_list = self._failed_trav_user_emul()
        return user_emulation_command_list

    def _failed_trav_user_emul(self):
        print("\t  > Failed to perform a file traversal on mounted file system")
        print("\t  > Starting backup user emulation that only attempts to write to disk...")
        user_emulation_command_list = self.get_netbsd_backup_user_emulation()
        return user_emulation_command_list

    @staticmethod
    def randomize_emulation_list_length(emu_list, multiplier):
        new_emu_list = []
        for i in range(multiplier):
            new_emu_list += random.sample(emu_list, random.randint(0, len(emu_list)))
        return new_emu_list
