import datetime
import json
import logging
import os
import pathlib
import random
import re
import signal
import socket
import subprocess
import sys
import time
import zipfile
from distutils.util import strtobool
import colorama as clr
import paramiko


from byte_flipper import ByteFlipper
from radamsa import Radamsa
from metadata import MetaMutation


THIS_FILE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(str(pathlib.Path(THIS_FILE).parent))
sys.path.append(str(pathlib.Path(THIS_FILE)))
from Manager.Manager_FreeBSD import FreeBSD
from Manager.Manager_NetBSD import NetBSD
from Manager.Manager_OpenBSD import OpenBSD
from Manager.Manager_Ubuntu import Ubuntu
from Manager.Manager import VmManager, get_basename, get_parent_path, create_directory

from config import fuzzing_config

from UserEmulation.UE_Generic import GenericUserEmulation
from UserEmulation.UE_FreeBSD import FreebsdUserEmulation
from UserEmulation.UE_NetBSD import NetbsdUserEmulation
from UserEmulation.UE_OpenBSD import OpenbsdUserEmulation
from UserEmulation.UE_Ubuntu import UbuntuUserEmulation

from utility import extract_core_features


def get_random_list_entry(file_list):
    return random.choice(list(filter(None, file_list))).rstrip(",").strip()


class Fuzzer:
    def __init__(self):
        self.name = None  # internal name for this Fuzzer object
        self.vm_name = None  # Name of the libvirt VM
        self.rmount = None  # full remote path where file system is mounted
        self.new_crash_dir = None  # local directory where crash is saved
        self.vm_object = None  # Manager object instance
        self.lpath_mfs = None  # full path to the current mutated fs
        self.syscall_log = None  # full path to the log for the executed syscalls
        self.mutation_engine = None
        self.mutation_size = None
        self.mfs_type = "ufs"  # file system type that is currently used
        self.mfs_size = 20  # size of said file system
        self.mfs_files = 20  # amount of files on the filesystem
        self.mfs_max_file_size = 1000  # max size of each file on the filesystem
        self.iter = 0  # current iteration
        self.crashes = 0  # amount of crashes in current cycle
        self.ucrashes = 0  # amount unique crashes in current cycle
        self.last_panic = ""  # displays the type of the last panic
        self.start = datetime.datetime.now()  # datetime object when fuzzing started
        self.end = None  # datetime object when fuzzing ended
        self.runtime = 0  # essentially datetime.now() - self.start
        self.success_mounts = 0  # number of times mounting succeeded
        self.last_crash_iter = 0  # used to deduct whether a system reset is reasonable
        self.last_unique = 0
        self.start_iter = 0  # used for timing iterations
        self.end_iter = 0  # used to time iterations
        self.all_iter_time = 0  # used for timing iterations
        self.avg_iter_time = 0  # used for timing iterations
        self.max_exec = 0  # used for producing stats about possible executed syscalls
        self.actual_exec = 0  # used for producing stats about possible executed syscalls
        self.radamsa_seed = None  # generated seed by radamsa
        self.fs_log = None  # logs the created filesystem in a json serializable format
        self.dyn_scaling = True  # if enabled increases the fs size after 15k iterations of not finding a unique crash
        self.target_os = None
        self.host_os = None
        signal.signal(signal.SIGINT, self.signal_handler)

    def __setup__(self, **kwargs):
        if "name" in kwargs:
            self.name = kwargs["name"]
        if "vm_name" in kwargs:
            self.vm_name = kwargs["vm_name"]
        if "mfs_type" in kwargs:
            self.mfs_type = kwargs["mfs_type"]
        if "mfs_size" in kwargs:
            self.mfs_size = kwargs["mfs_size"]
        if "mfs_files" in kwargs:
            self.mfs_files = kwargs["mfs_files"]
        if "mfs_max_file_size" in kwargs:
            self.mfs_max_file_size = kwargs["mfs_max_file_size"]
        if "mutation_engine" in kwargs:
            self.mutation_engine = kwargs["mutation_engine"][0]
            self.mutation_size = int(kwargs["mutation_engine"][1])
        if "vm_object" in kwargs:
            self.vm_object = kwargs["vm_object"]
        if "dyn_scaling" in kwargs:
            try:
                self.dyn_scaling = bool(strtobool(kwargs["dyn_scaling"]))
            except ValueError:
                self.dyn_scaling = False

    def signal_handler(self, sig, frame):
        print("Observed Ctrl+C! Exiting...")
        self._save_stats()
        sys.exit(1)

    def get_guest_os_kernel(self):
        self.host_os = self.vm_object.exec_cmd_quiet("uname").lower()

    def set_target(self, rpath):
        self.get_guest_os_kernel()
        if self.host_os == "freebsd":
            self.target_os = FreeBSD(mount_at=self.rmount, rfile=rpath, vm_object=self.vm_object)
        elif self.host_os == "openbsd":
            self.target_os = OpenBSD(mount_at=self.rmount, rfile=rpath, vm_object=self.vm_object)
        elif self.host_os == "netbsd":
            self.target_os = NetBSD(mount_at=self.rmount, rfile=rpath, vm_object=self.vm_object)
        elif self.host_os == "linux":
            self.target_os = Ubuntu(mount_at=self.rmount, rfile=rpath, vm_object=self.vm_object)
        else:
            logging.error("Unknown or not implemented target kernel: {}".format(self.host_os))
            sys.exit(1)

    def mutation_radamsa(
        self, file_system, preserve_magic=True, preserve_uberblock=False, determinism=True,
    ):
        self.radamsa_seed, self.lpath_mfs = Radamsa(file_system).mutation(preserve_magic, preserve_uberblock, determinism)

    def mutation_byte_flip_seq(self, fs_path, n_bytes=1):
        self.lpath_mfs = ByteFlipper(fs_path, n_bytes, mode="seq").mutation_seq()

    def mutation_byte_flip_rnd(self, fs_path, n_bytes=1):
        self.lpath_mfs = ByteFlipper(fs_path, n_bytes, mode="rnd").mutation_rnd()

    def mutation_metadata(self, fs_path, n_bytes=3):
        self.lpath_mfs = MetaMutation(fs_path, n_bytes, mode="sb_meta").mutation()

    def mutation_metablock(self, fs_path):
        pass

    def _get_two_distinct_list_elements(self, list_one, list_two):
        _file1 = get_random_list_entry(list_one)
        _file2 = get_random_list_entry(list_two)
        try:
            if _file1 != _file2:
                return _file1, _file2
            else:
                self._get_two_distinct_list_elements(list_one, list_two)
        except RecursionError:
            return None, None

    @staticmethod
    def _flush_write(open_file_handle):
        open_file_handle.flush()
        os.fsync(open_file_handle.fileno())

    def user_interaction_emulation(self, syscall_log):
        print(clr.Fore.LIGHTYELLOW_EX + "\t[*] Accessing & modifying mounted filesystem: {}".format(self.rmount) + clr.Fore.RESET)
        copy_scripts_to_fuzzer(self.vm_object)
        exec_cmds = 0
        try:
            total_cmds = self._set_user_emulation()
        except IndexError:
            return 1
        self.max_exec += len(total_cmds)
        for cmd in total_cmds:
            if any(x in cmd for x in ["cp", "mv"]):
                cmd = self.dynamic_resolving_of_cp_and_mv_command(cmd, syscall_log)
            ret_cmd = self.vm_object.exec_cmd_quiet(cmd)
            logging.debug("RET VAL FOR {} IS: {}".format(cmd, ret_cmd))
            if ret_cmd == 2 and not self.vm_object.check_vm_state():
                self.print_successful_executed_commands(exec_cmds, total_cmds)
                return self._flush_write_crash_syscall_log(cmd, syscall_log, exec_cmds)
            if (
                any(x in cmd for x in ["dd", "find", "readlink", "getfacl", "ls", "stat", "tar", "du", "wc"])
                and type(ret_cmd) == str
            ):
                if "tar" in cmd and "Error" in ret_cmd:
                    syscall_log.write("[-] {}\n".format(cmd))
                elif "getfacl" in cmd and "stat() failed" in ret_cmd:
                    syscall_log.write("[-] {}\n".format(cmd))
                elif "No such" in ret_cmd:
                    syscall_log.write("[-] {}\n".format(cmd))
                else:
                    exec_cmds = self._write_success_log(cmd, syscall_log, exec_cmds)
            elif (
                not any(x in cmd for x in ["dd", "find", "readlink", "getfacl", "ls", "stat", "tar", "du", "wc"]) and not ret_cmd
            ):
                exec_cmds = self._write_success_log(cmd, syscall_log, exec_cmds)
            else:
                syscall_log.write("[-] {}\n>>{}\n".format(cmd, ret_cmd))
                self._flush_write(syscall_log)
        self.print_successful_executed_commands(exec_cmds, total_cmds)
        self.actual_exec += exec_cmds
        return 1

    def _set_user_emulation(self):
        # return UserEmulation(vm_object=self.vm_object, rpath=self.rmount).set_user_emulation()
        if self.host_os == "freebsd":
            user_emulation_command_list = FreebsdUserEmulation(
                vm_object=self.vm_object, rpath=self.rmount
            ).set_freebsd_user_emulation()
        elif self.host_os == "openbsd":
            user_emulation_command_list = OpenbsdUserEmulation(
                vm_object=self.vm_object, rpath=self.rmount
            ).set_openbsd_user_emulation()
        elif self.host_os == "netbsd":
            user_emulation_command_list = NetbsdUserEmulation(
                vm_object=self.vm_object, rpath=self.rmount
            ).set_netbsd_user_emulation()
        elif self.host_os == "linux":
            user_emulation_command_list = UbuntuUserEmulation(
                vm_object=self.vm_object, rpath=self.rmount
            ).set_ubuntu_user_emulation()
        else:
            logging.error("unknown target kernel/os!")
            sys.exit(1)
        return user_emulation_command_list

    @staticmethod
    def print_successful_executed_commands(exec_cmds, total_cmds):
        print(clr.Fore.LIGHTYELLOW_EX + "[*] Completed {}/{} program calls".format(exec_cmds, len(total_cmds)) + clr.Fore.RESET)

    def dynamic_resolving_of_cp_and_mv_command(self, cmd, syscall_log):
        try:
            gen_user = GenericUserEmulation(vm_object=self.vm_object, remote_mount_path=self.rmount)
            _file, _dir = self._get_two_distinct_list_elements(
                gen_user.get_files_of_mounted_file_system(param="files"), gen_user.get_files_of_mounted_file_system(param="dir"),
            )
            cmd = cmd.format(_file, _dir)
        except (AttributeError, TypeError):
            syscall_log.write("[-] {}\n".format(cmd))
        return cmd

    def _write_success_log(self, cmd, log_handler, ctr_exec_cmd):
        log_handler.write("[+] {}\n".format(cmd))
        self._flush_write(log_handler)
        ctr_exec_cmd += 1
        return ctr_exec_cmd

    def _flush_write_crash_syscall_log(self, cmd, fd, success):
        fd.write("[!] {}\n".format(cmd))
        self._flush_write(fd)
        self.actual_exec += success
        self.check_if_crash_sample()
        return None

    def _compress_vmcore(self):
        vmcore = [os.path.join(self.new_crash_dir, f) for f in os.listdir(self.new_crash_dir) if f.startswith("vmcore")][0]
        zip_path = os.path.join(self.new_crash_dir, get_basename(vmcore))
        with zipfile.ZipFile(zip_path + ".zip", "w", compression=zipfile.ZIP_DEFLATED) as myzip:
            myzip.write(vmcore, arcname=get_basename(vmcore))
        os.remove(vmcore)

    def save_fs_dict_to_disk(self):
        try:
            _path = os.path.join(self.new_crash_dir, "fs.json")
            self.fs_log = re.sub(r"[\a-zA-Z0-9]*?{\"fs", '{"fs', self.fs_log)
            if self.fs_log.endswith("%"):
                self.fs_log = self.fs_log[-1]
            self.fs_log = json.loads(self.fs_log)
            self.fs_log["crash_meta_data"] = {}
            self.fs_log["crash_meta_data"]["seed"] = self.radamsa_seed
            self.fs_log["crash_meta_data"]["panic"] = self.last_panic
            with open(_path, "w") as f:
                f.write(json.dumps(self.fs_log, indent=4))
        except TypeError:
            pass

    def check_if_crash_sample(self):
        self.last_crash_iter = self.iter
        try:
            self.new_crash_dir = self.vm_object.crash_handler()
            if self.new_crash_dir:
                self._backup_samples()
                self._check_if_crash_is_yet_unknown()
                self.save_fs_dict_to_disk()
                self.vm_object.exec_cmd_quiet("/bin/rm -rf /var/crash/*")
                self._compress_vmcore()
            self._save_stats()
        except socket.timeout as e:
            logging.error("SOCKET TIMEOUT: {}".format(e))
            self.vm_object.reset_vm()
            if self.vm_object.silent_vm_state():
                self.check_if_crash_sample()
            else:
                self.vm_object.restore_snapshot(self.vm_object.get_current_snapshot())
                self.vm_object.quick_boot(vm_name=self.vm_object.name)

    def _save_stats(self):
        statsp = os.path.join(os.getcwd(), "stats")
        create_directory(statsp)
        with open(os.path.join(statsp, str(self.start)[:-4] + "_" + get_basename(self.lpath_mfs)) + ".txt", "w",) as s:
            s.write("> Start date: {}\n".format(str(self.start)))
            s.write("> End date: {}\n".format(str(datetime.datetime.now())))
            s.write("> Engine: {}\n".format(str(get_basename(self.lpath_mfs)).split("_"))[-5].strip())
            s.write("> Runtime: {}\n".format(str(self.runtime)))
            s.write("> File system name: {}\n".format(str(self.lpath_mfs)))
            s.write("> File system type: {}\n".format(str(self.mfs_type)))
            s.write("> File system size: {}MB\n".format(str(self.mfs_size)))
            s.write("> #Files in initial file system: {}\n".format(str(self.mfs_files)))
            s.write("> #Max_size of files: {}KB\n".format(str(self.mfs_max_file_size)))
            s.write("> Iterations: {}\n".format(str(self.iter)))
            s.write("> Avg Iteration time: {}s\n".format(str(self.avg_iter_time)))
            s.write("> #Crashes: {}\n".format(str(self.crashes)))
            s.write("> #Unique_Crashes: {}\n".format(str(self.ucrashes)))
            s.write(
                "> #Successful_Mounts: {}({}%)\n".format(
                    str(self.success_mounts), str(self._get_percentage(self.success_mounts, self.iter)),
                )
            )
            s.write("> #Unsuccessful_Mounts {}\n".format(str(int(self.iter) - int(self.success_mounts))))
            s.write(
                "> {}/{} ({}%) Commands executed\n".format(
                    str(self.actual_exec), str(self.max_exec), str(self._get_percentage(self.actual_exec, self.max_exec)),
                )
            )

    def automate(self, rpath_mfs, mount_at):
        self.rmount = mount_at
        self._print_statistics_output_to_tty()
        self.syscall_log = os.path.join(os.getcwd(), "file_system_storage/{}_syscall.log".format(self.name))
        with open(self.syscall_log, "w") as syscall_log:
            self.set_target(rpath_mfs)
            mount_ret = self.target_os.mount_file_system()
            if mount_ret == 1 and self.vm_object.check_vm_state():
                print(clr.Fore.GREEN + "[+] Mounting successful!" + clr.Fore.RESET)
                self.success_mounts += 1
                if self.user_interaction_emulation(syscall_log):
                    self.unmount_file_system_on_remote()
            else:
                print(clr.Fore.RED + "[!] Mounting failed!" + clr.Fore.RESET)
                if mount_ret == 0 and not self.target_os.destroy_bdev() and self.vm_object.silent_vm_state():
                    pass
                else:
                    syscall_log.write("[!] mount\n")
                    self.check_if_crash_sample()
            self.iter += 1
            self._print_separator()
            self.end_iter = round(time.time() - self.start_iter, 2)
            self.all_iter_time += self.end_iter
            self.avg_iter_time = round(self.all_iter_time / self.iter, 2)

    def unmount_file_system_on_remote(self):
        if self.target_os.unmount_file_system() and self.vm_object.silent_vm_state():
            print(clr.Fore.GREEN + "[+] Unmounted {} successfully".format(self.rmount) + clr.Fore.RESET)
        else:
            self.check_if_crash_sample()

    def _print_statistics_output_to_tty(self):
        os.system("clear")
        self._print_separator()
        print(
            "Start date: {} | Runtime: {} | OS: {} | Mutation engine: {}\n"
            "Filesystem type: {} | Filesystem size: {}MB \n"
            "Iteration: {} | Last iteration time: {}s | Avg. iteration time: {}s\n"
            "# Crashes: {} | # New crashes: {} | Last panic: {} | Last new crash (iter): {}\n"
            "Successful mounts: {} ({}%) | {}/{} ({}%) Commands executed".format(
                str(self.start)[:-4],
                self.runtime,
                self.host_os,
                self.mutation_engine,
                self.mfs_type,
                self.mfs_size,
                self.iter,
                self.end_iter,
                self.avg_iter_time,
                self.crashes,
                self.ucrashes,
                self.last_panic,
                self.last_unique,
                self.success_mounts,
                self._get_percentage(self.success_mounts, self.iter),
                self.actual_exec,
                self.max_exec,
                self._get_percentage(self.actual_exec, self.max_exec),
            )
        )
        self._print_separator()

    @staticmethod
    def _print_separator():
        line_separator = "─"
        print(line_separator * int(subprocess.check_output(["stty", "size"], encoding="utf-8").split()[1]))

    def _get_core_details(self, file):
        with open(file, "rb") as f:
            data = f.read()
        self.last_panic = extract_core_features.get_panic_name(data)
        return extract_core_features.get_core_details(data)

    @staticmethod
    def _write_sha256sum_txt(core_txt, sha256_trace):
        sum_txt = str(pathlib.Path(core_txt).parent) + "/shasum256.txt"
        with open(sum_txt, "w") as g:
            g.write(sha256_trace)
        g.close()

    def _check_if_crash_is_yet_unknown(self):
        core_txt = [os.path.join(self.new_crash_dir, f) for f in os.listdir(self.new_crash_dir) if f.startswith("core.txt")][0]
        sanitized_bt = self._get_core_details(core_txt)
        if len(self.last_panic) <= 2:
            return 0
        self.crashes += 1
        sha256_trace = extract_core_features.get_sha256_sum(sanitized_bt)
        self._write_sha256sum_txt(core_txt, sha256_trace)
        crashdb = os.path.join(os.getcwd(), "crash_dumps/crash.db")
        pathlib.Path(self.new_crash_dir).rename(self.new_crash_dir + "_" + str(self.last_panic))
        self.new_crash_dir = self.new_crash_dir + "_" + self.last_panic
        with open(crashdb, "a+") as f:
            f.seek(0)
            db_contents = f.read()
            if sha256_trace not in db_contents:
                self.ucrashes += 1
                self.last_unique = self.iter
                print(clr.Fore.CYAN + "[+] New unseen crash found: {}!".format(sha256_trace) + clr.Fore.RESET)
                mfs_meta = str(get_basename(self.lpath_mfs)).split("_")
                engine = mfs_meta[0].strip()
                if "radamsa" in engine and self.radamsa_seed:
                    engine = engine + " (seed: {})".format(self.radamsa_seed)
                else:
                    engine = "None"
                fs = mfs_meta[-2].strip()
                size = mfs_meta[-1].strip()
                entry = (
                    str(self.name)
                    + "; "
                    + str(self.vm_name)
                    + "; "
                    + fs
                    + "; "
                    + size
                    + "; "
                    + engine
                    + "; "
                    + str(self.last_panic)
                    + "; "
                    + sha256_trace
                    + "; "
                    + str(self.new_crash_dir)
                    + "; "
                    + str(self.runtime)
                    + "; "
                    + str(self.iter)
                    + "\n"
                )
                f.write(entry)
            f.close()

    def _backup_samples(self):
        files = [
            self.lpath_mfs,
            self.syscall_log,
            os.path.join(
                str(get_parent_path(self.lpath_mfs)), "_".join(x for x in str(get_basename(self.lpath_mfs)).split("_")[1:]),
            ),
        ]
        logging.debug("BACKUP FILES: {}".format(files))
        archive = os.path.join(self.new_crash_dir, "sample.zip")
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as myzip:
            for f in list(filter(None, files)):
                myzip.write(f, pathlib.Path(f).name)
        myzip.close()

    def _iter_reset(self):
        if self.iter % 150 == 0 and self.iter - self.last_crash_iter > 50:
            logging.warning("Automatic VM reset in progress...")
            cur_snap = self.vm_object.get_current_snapshot()
            try:
                self.vm_object.restore_snapshot(cur_snap)
                self.vm_object.new_rshell()
            except socket.timeout as e:
                logging.debug("Socket timed out during snapshot restoring: {}".format(e))
                time.sleep(2)
                if self.vm_object.check_vm_state():
                    self.vm_object.new_rshell()
                else:
                    self.vm_object.crash_handler()

    @staticmethod
    def _get_percentage(part, whole):
        try:
            return round(100 * float(part) / float(whole), 2)
        except ZeroDivisionError:
            return 0

    @staticmethod
    def _remove_iteration_leftovers_on_target(fs_maker_vm, fs_name):
        fs_maker_vm.exec_cmd_quiet("/bin/rm -rf {}".format(os.path.join("/tmp/", fs_name)))
        fs_maker_vm.exec_cmd_quiet("/bin/rm -rf {}".format(os.path.join("/mnt", fs_name)))

    def copy_generated_file_system_to_host(self, fs_maker_vm, fs_name):
        fs_maker_vm.cp_to_host(
            save_files_at=os.path.join(os.getcwd() + "/file_system_storage"),
            get_files_from="/tmp/",
            list_of_files_to_copy=fs_name,
        )
        self._remove_iteration_leftovers_on_target(fs_maker_vm, "fs_" + fs_name)

    def fuzz(self, fuzzy_vm, fs_maker_vm):
        create_directory(os.getcwd() + "/file_system_storage")
        while True:
            if self.dyn_scaling:
                self._change_fs_parameters()
            try:
                self.start_iter = time.time()
                self.runtime = str(datetime.datetime.now() - self.start)[:-4]
                self._iter_reset()
                fs_name = "{}_{}_{}MB".format(self.name, self.mfs_type, self.mfs_size)
                cmd = (
                    "python3 /tmp/makeFS2.py -fs {} -m 1"
                    ' -n "{}"'
                    " -s {}"
                    " -p {}"
                    " -ps {}"
                    " -o {}".format(self.mfs_type, fs_name, self.mfs_size, self.mfs_files, self.mfs_max_file_size, "/tmp/",)
                )
                if fs_maker_vm.silent_vm_state():
                    self.fs_log = fs_maker_vm.exec_cmd_quiet(cmd)
                    if "ERROR" in self.fs_log:
                        print("Failed FS creation: {}".format(self.fs_log))
                        sys.exit(1)
                else:
                    fs_maker_vm.restore_snapshot(fs_maker_vm.get_current_snapshot())
                    fs_maker_vm.quick_boot(vm_name=fs_maker_vm.name)
                    self.fs_log = fs_maker_vm.exec_cmd_quiet(cmd)
                if not self.fs_log:
                    logging.error("Failed to fetch fs sample log.. Exiting..!\n")
                    sys.exit(1)
                self.copy_generated_file_system_to_host(fs_maker_vm, fs_name)
                self._make_mutation(fs_name)
                if not self.lpath_mfs:
                    continue
                fuzzy_vm.cp_to_guest(
                    get_files_from="file_system_storage/",
                    list_of_files_to_copy=get_basename(self.lpath_mfs),
                    save_files_at="/tmp",
                )
                if "zfs" in self.mfs_type:
                    mnt_path = "pool_" + "_".join(x for x in get_basename(self.lpath_mfs).split("_")[1:])
                else:
                    mnt_path = get_basename(self.lpath_mfs)
                self.automate(
                    rpath_mfs="/tmp/{}".format(get_basename(self.lpath_mfs)), mount_at="/mnt/{}".format(mnt_path),
                )
                self.vm_object.exec_cmd_quiet("rm -rf {}".format(os.path.join("/tmp", self.lpath_mfs)))
            except (paramiko.ssh_exception.SSHException, paramiko.ssh_exception.NoValidConnectionsError, socket.timeout,) as e:
                logging.error("SSH/socket exception: {}. Resetting VM".format(e))
                self.check_if_crash_sample()
            except (ValueError, OSError) as e:
                logging.error("Ran into a problem during fuzzing: {}".format(e))
            except (EOFError, AttributeError) as e:
                logging.error(e)
                logging.error("VM may be down..? Resetting")
                self.vm_object.restore_snapshot(snap_name=self.vm_object.get_current_snapshot())
                self.vm_object.reset_vm()

    def _make_mutation(self, fs_name):
        try:
            fs = os.path.join(os.getcwd() + "/file_system_storage/", fs_name)
            if self.mutation_engine == "radamsa":
                self.mutation_radamsa(fs)
            elif self.mutation_engine == "byte_flip_seq":
                self.mutation_byte_flip_seq(fs, self.mutation_size)
            elif self.mutation_engine == "byte_flip_rnd":
                self.mutation_byte_flip_rnd(fs, self.mutation_size)
            elif self.mutation_engine == "metadata":
                self.mutation_metadata(fs, self.mutation_size)
            else:
                logging.error("Unknown mutation engine specified! Exiting...")
                sys.exit(1)
        except (AttributeError, IndexError):
            logging.error("Ran into a problem during mutation. Exiting..!")
            sys.exit(1)

    def _change_fs_parameters(self):
        if self.mfs_size >= 750:
            if self.mfs_type == "zfs":
                self.mfs_size = 65
                self.mfs_files = 20
                self.mfs_max_file_size = 2048
            else:
                self.mfs_size = 15
                self.mfs_files = 10
                self.mfs_max_file_size = 1024
            return 0
        if (int(self.iter) - int(self.last_unique)) >= 15000:
            self.last_unique += 15000  # workaround so the new fs size is fuzzing for another 15k iters
            self.mfs_size += 50
            if random.randint(0, 1) == 0:
                self.mfs_files = int(((self.mfs_size << 10) - 3000) / self.mfs_max_file_size)
            else:
                self.mfs_max_file_size = int(((self.mfs_size << 10) - 3000) / self.mfs_files)


def to_dict(input_ordered_dict):
    return json.loads(json.dumps(input_ordered_dict))


def copy_scripts_to_fuzzer(fuzzy_vm):
    if not int(fuzzy_vm.exec_cmd_quiet("[ -f /tmp/get_users_and_groups.py ] && echo 1 || echo 0 | /usr/bin/head -n1")):
        fuzzy_vm.cp_to_guest(
            get_files_from="utility/", list_of_files_to_copy="get_users_and_groups.py", save_files_at="/tmp",
        )
    if not int(fuzzy_vm.exec_cmd_quiet("[ -f /tmp/file_traversal.py ] && echo 1 || echo 0 | /usr/bin/head -n1")):
        fuzzy_vm.cp_to_guest(
            get_files_from="utility/", list_of_files_to_copy="file_traversal.py", save_files_at="/tmp",
        )


def main():
    fs_generator = VmManager()
    fs_generator.setup(vm_user=fuzzing_config.user, vm_password=fuzzing_config.pw, name=sys.argv[2])
    fs_generator.quick_boot(vm_name=sys.argv[2])
    if not int(fs_generator.exec_cmd_quiet("[ -f /tmp/makeFS2.py ] && echo 1 || echo 0 | head -n1")):
        fs_generator.cp_to_guest(get_files_from=".", list_of_files_to_copy="makeFS2.py", save_files_at="/tmp/")
    fuzzer = Fuzzer()
    fuzzer.__setup__(
        name=sys.argv[1],
        vm_name=sys.argv[3],
        mutation_engine=tuple(x for x in sys.argv[4].split(", ")),
        mfs_type=sys.argv[5],
        mfs_size=int(sys.argv[6]),
        mfs_files=int(sys.argv[7]),
        mfs_max_file_size=int(sys.argv[8]),
        dyn_scaling=sys.argv[9],
    )
    fuzz_vm = VmManager()
    fuzz_vm.setup(vm_user=fuzzing_config.user, vm_password=fuzzing_config.pw, name=fuzzer.name)
    fuzz_vm.quick_boot(vm_name=fuzzer.vm_name)
    fuzzer.vm_object = fuzz_vm
    fuzzer.fuzz(fuzz_vm, fs_generator)


if __name__ == "__main__":
    sys.exit(main())
