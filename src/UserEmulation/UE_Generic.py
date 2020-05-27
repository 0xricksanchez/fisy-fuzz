import random


class GenericUserEmulation:
    def __init__(self, vm_object, remote_mount_path):
        self.vm_object = vm_object
        self.rpath = remote_mount_path

    def get_users_and_groups_of_target_os(self):
        res = self.vm_object.exec_cmd_quiet("python3 /tmp/get_users_and_groups.py").split("<delim>")
        users = res[0].split()
        groups = res[1].split()
        return users, groups

    def get_files_of_mounted_file_system(self, param="all"):
        res = self.vm_object.exec_cmd_quiet("python3 /tmp/file_traversal.py {} {}".format(self.rpath, param)).split("<delim>")
        if param == "all":
            list_of_all_directories = res[0].split()
            list_of_all_files = res[1].split()
            list_of_files_and_links = res[2].split()
            list_of_all_links = res[3].split()
            return (
                list_of_all_directories,
                list_of_all_files,
                list_of_files_and_links,
                list_of_all_links,
            )
        else:
            return res[0].split(",")

    @staticmethod
    def get_random_chmod_mode():
        mod = ""
        for i in range(3):
            mod += str(random.randint(0, 7))
        return int(mod)
