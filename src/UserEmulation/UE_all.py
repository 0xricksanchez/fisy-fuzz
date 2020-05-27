import os
import random

from UserEmulation.UE_Generic import GenericUserEmulation


def get_random_list_entry(file_list):
    return random.choice(list(filter(None, file_list))).rstrip(",").strip()


class UserEmulation:
    def __init__(self, vm_object, rpath):
        self.vm_object = vm_object
        self.rpath = rpath

    def prepare_user_emulation(self):
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

        user_emulation = [
            "$(which find) {}/*".format(self.rpath),
            "$(which ls) -lah {}/*".format(get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="dir"))),
            "$(which touch) {}".format(
                os.path.join(get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="dir")), "TOUCHED",)
            ),
            "$(which mkdir) -p {}/a/b/c".format(get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="dir"))),
            "$(which dd) if=/dev/urandom of={} bs={} count={}".format(
                os.path.join(get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="dir")), "DATA",),
                1 << 20,
                random.randint(1, 5),
            ),
            "$(which ln) {} {}".format(
                get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="file")),
                os.path.join(self.rpath, "HARDLINK"),
            ),
            "$(which ln) -s {} {}".format(
                get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="file")),
                os.path.join(self.rpath, "SOFTLINK"),
            ),
            "$(which file) {}".format(get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="files"))),
            "$(which readlink) {}".format(get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="link"))),
            "$(which stat) {}".format(get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="dir"))),
            "$(which cp) -R {} {}/COPIED",
            "$(which mknod) {}".format(
                os.path.join(get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="dir")), "NODDED",)
            ),
            '$(which tar) -jcvf {} "{} {}"'.format(
                os.path.join(self.rpath, "archive.bzip2"),
                get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="file")),
                get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="file")),
            ),
            "$(which chmod) {} {}".format(
                gen_user.get_random_chmod_mode(), get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="files")),
            ),
            "$(which chown) {}:{} {}".format(
                get_random_list_entry(users),
                get_random_list_entry(groups),
                get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="files")),
            ),
            "$(which chgrp) {} {}".format(
                get_random_list_entry(groups), get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="files")),
            ),
            "$(which mv) {} {}",
            "$(which echo) APPENDED >> {}".format(get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="file"))),
            "$(which chdir) {}".format(get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="dir"))),
            "$(which rm) -rf {}".format(get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="dir")[:-1])),
            "$(which chflags) {} {}".format(
                get_random_list_entry(chflags_modes),
                get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="files")),
            ),
            "$(which getfacl) {}".format(get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="files"))),
            "$(which split) {} {}".format(
                get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="files")),
                get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="dir")),
            ),
            "$(which du) {}".format(get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="files"))),
            "$(which wc) {}".format(get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="files"))),
            "$(which truncate) -s {} {}".format(
                random.randint(1, 5), get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="file")),
            ),
            "$(which dirname) {}".format(get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="files"))),
            "$(which basename) {}".format(get_random_list_entry(gen_user.get_files_of_mounted_file_system(param="files"))),
        ]
        # '$(which setfacl) -m {}:{} {}'.format(get_random_list_entry(users),
        #                                  gen_user.get_random_chmod_mode(),
        #                                  get_random_list_entry(
        #                                      gen_user.get_files_of_mounted_file_system(
        #                                          param='files')))
        # ] needs to be explicitly enabled during mount -o acls
        random.shuffle(user_emulation)
        return user_emulation

    def get_backup_user_emulation(self):
        gen_user = GenericUserEmulation(vm_object=self.vm_object, remote_mount_path=self.rpath)

        user_emulation = [
            "$(which find) {}/*".format(self.rpath),
            "$(which ls) -lah {}/*".format(self.rpath),
            "$(touch) {}".format(os.path.join(self.rpath, "TOUCHED")),
            "$(mkdir) -p {}/a/b/c".format(self.rpath),
            "$(which dd) if=/dev/urandom of={} bs={} count={}".format(
                os.path.join(self.rpath, "DATA"), 1 << 20, random.randint(1, 5)
            ),
            "$(which mknod) {}".format(os.path.join(self.rpath, "NODDED")),
            "$(which echo) APPENDED >> {}".format(os.path.join(self.rpath, "ECHOED")),
        ]
        random.shuffle(user_emulation)
        for entry in [
            "$(which ln) {} {}".format(os.path.join(self.rpath, "DATA"), "HARDLINK"),
            "$(which ln) -s {} {}".format(os.path.join(self.rpath, "DATA"), "SOFTLINK"),
            "$(which readlink) {}".format(os.path.join(self.rpath, get_random_list_entry(["SOFTLINK", "HARDLINK"]))),
            "$(which chmod) {} {}".format(gen_user.get_random_chmod_mode(), os.path.join(self.rpath, "DATA")),
            "$(which rm) -rf {}/*".format(self.rpath),
        ]:
            user_emulation.append(entry)
        return user_emulation

    def set_user_emulation(self):
        try:
            gen_user = GenericUserEmulation(vm_object=self.vm_object, remote_mount_path=self.rpath)
            res = gen_user.get_files_of_mounted_file_system("files")
            if any("Traceback" in pos for pos in res):
                ue_cmd_lst = self._failed_trav_user_emul()
            else:
                ue_cmd_lst = self.prepare_user_emulation()
        except AttributeError:
            ue_cmd_lst = self._failed_trav_user_emul()
        return ue_cmd_lst

    def _failed_trav_user_emul(self):
        print("\t > Failed to perform a file traversal on mounted file system")
        print("\t > Starting backup user emulation that only attempts to write to disk...\n")
        ue_cmd_lst = self.get_backup_user_emulation()
        return ue_cmd_lst

    @staticmethod
    def rnd_e_lst_len(emu_list, multiplier):
        new_emu_list = []
        for i in range(multiplier):
            new_emu_list += random.sample(emu_list, random.randint(0, len(emu_list)))
        return new_emu_list
