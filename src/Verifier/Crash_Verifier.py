import logging
import os
import pathlib
import re
import sys
import threading
import time
import zipfile
from collections import deque

THIS_FILE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(str(pathlib.Path(THIS_FILE).parent))
sys.path.append(str(pathlib.Path(THIS_FILE)))
from Manager.Manager_FreeBSD import FreeBSD
from Manager.Manager import VmManager
from utility import extract_core_features
from config import fuzzing_config


class CrashVerifier(object):
    def __init__(self, crash_db, target_os, interval=60):
        self.interval = interval
        self.crash_fifo = None
        self.last_crash_line = 0
        self.path_crash_db = crash_db
        self.checked_crashes = []
        self.target = target_os
        self.vm_object = None
        self.reprod_crash_file = None
        self.orig_sha_sum = None
        time.sleep(self.interval * 15)
        self.init_crash_fifo()

        thread = threading.Thread(target=self.run, name="crash_verifier", args=())
        thread.daemon = True
        thread.start()
        thread.join()

    @staticmethod
    def get_vm_object():
        verifier_vm = VmManager()
        verifier_vm.setup(vm_user=fuzzing_config.user, vm_password=fuzzing_config.pw, name="verifier")
        verifier_vm.quick_boot(vm_name="verifier")
        return verifier_vm

    def run(self):
        if len(list(self.crash_fifo)) >= 1:
            self.verify()
            self.run()
        else:
            time.sleep(self.interval * 15)
            self.init_crash_fifo()
            self.run()

    def init_crash_fifo(self):
        self.crash_fifo = deque()
        crash_db_contents = self.read_crash_db()
        self._fill_crash_fifo(crash_db_contents)

    def _fill_crash_fifo(self, crash_db_contents):
        for line in crash_db_contents:
            if line.split(";")[-3].strip() not in self.checked_crashes:
                crash_path = str(line.split("; ")[-3].strip())
                origin_sha_sum = line.split("; ")[-4].strip()
                self.crash_fifo.append((crash_path, origin_sha_sum))

    def verify(self):
        next_unverified_crash_tuple = self.crash_fifo.popleft()
        next_unverified_crash = next_unverified_crash_tuple[0]
        self.orig_sha_sum = next_unverified_crash_tuple[1]
        sample = os.path.join(next_unverified_crash, "sample.zip")
        syscall_log, sample_file_system = self.get_file_system_and_log_if_present(next_unverified_crash, sample)
        command_chain = self.get_command_chain(syscall_log)
        if self.target == "freebsd":
            self._freebsd_verifier(command_chain, next_unverified_crash, sample_file_system)
        self.checked_crashes.append(next_unverified_crash)
        self._remove_archive_contents(next_unverified_crash, sample_file_system, syscall_log)
        self.vm_object.restore_snapshot(self.vm_object.get_current_snapshot())

    def _freebsd_verifier(self, command_chain, next_unverified_crash, sample_file_system):
        self.vm_object = self.get_vm_object()
        self.vm_object.cp_to_guest(
            get_files_from=next_unverified_crash, list_of_files_to_copy=sample_file_system, save_files_at="/tmp/",
        )
        freebsd_target = FreeBSD(
            mount_at=os.path.join("/mnt/", sample_file_system),
            rfile=os.path.join("/tmp", sample_file_system),
            vm_object=self.vm_object,
        )
        if command_chain and freebsd_target.mount_file_system() and self.vm_object.silent_vm_state():
            self._execute_command_chain(command_chain, next_unverified_crash)
        elif not command_chain and freebsd_target.mount_file_system() == 2:
            with open(os.path.join(next_unverified_crash, "reprod.1"), "w") as f:
                f.write("System crashed as expected during mount!\n")
        else:
            with open(os.path.join(next_unverified_crash, "reprod.0"), "w") as f:
                f.write("Command chain was empty. Expected the system to crash during mount!\n")

    def _reset_verifier_vm(self):
        self.vm_object.reset_vm()
        self.vm_object.new_rshell()

    @staticmethod
    def _remove_archive_contents(next_unverified_crash, sample_file_system, syscall_log):
        pathlib.Path(syscall_log).unlink()
        pathlib.Path(os.path.join(next_unverified_crash, sample_file_system)).unlink()
        pathlib.Path(os.path.join(next_unverified_crash, "_".join(x for x in sample_file_system.split("_")[1:]),)).unlink()

    def _execute_command_chain(self, command_chain, next_unverified_crash):
        for command in command_chain:
            self.vm_object.exec_cmd_quiet(command)
            if command != command_chain[-1] and self.vm_object.silent_vm_state():
                continue
            elif command != command_chain[-1] and not self.vm_object.silent_vm_state():
                with open(os.path.join(next_unverified_crash, "reprod.2"), "w") as f:
                    f.write("Command chain mismatch. Manual review necessary!\n")
                    f.write("Originally crashed at: {}\n".format(command_chain[-1]))
                    f.write("Now crashed at: {}".format(command))
                    self._reset_verifier_vm()
                    self._fetch_latest_core_file(next_unverified_crash)
            elif command == command_chain[-1] and self.vm_object.silent_vm_state():
                with open(os.path.join(next_unverified_crash, "reprod.0"), "w") as f:
                    f.write("Could not verify crash with loaded command chain: \n{}".format(command_chain))
            elif command == command_chain[-1] and not self.vm_object.silent_vm_state():
                self._reset_verifier_vm()
                new_sha_sum = self.get_shasum_of_repro_crash(next_unverified_crash)
                if self.orig_sha_sum == new_sha_sum:
                    with open(os.path.join(next_unverified_crash, "reprod.1"), "w") as f:
                        f.write("System crashed after executing the same command chain!\n")
                        f.write("sha256 sums are a match!")
                else:
                    with open(os.path.join(next_unverified_crash, "reprod.2"), "w") as f:
                        f.write("System crashed after executing the same command chain!\n")
                        f.write("sha256 sums are a mismatch:\n")
                        f.write("> Original crash: {}\n".format(self.orig_sha_sum))
                        f.write("> Reproduced crash: {}\n".format(new_sha_sum))
                        f.write("Manual review necessary!")

    @staticmethod
    def get_command_chain(syscall_log):
        command_chain = []
        with open(syscall_log, "r") as f:
            data = f.readlines()
            for line in data:
                if line.startswith("[+]") or line.startswith("[!]") and not line.startswith("[!] mount"):
                    command_chain.append(line.split("] ")[1].strip())
        return command_chain

    def get_file_system_and_log_if_present(self, next_unverified_crash, sample):
        if pathlib.Path(sample).is_file():
            with zipfile.ZipFile(sample, "r") as zip_ref:
                zip_ref.extractall(next_unverified_crash)
            syscall_log, sample_fs = None, None
            for file in pathlib.Path(next_unverified_crash).iterdir():
                log_match = re.search(r".*fuzz[0-9]{1,2}_syscall.log", str(file))
                fs_match = re.search(r".*_fuzz[0-9]_[a-zA-Z0-9]+_[0-9]+MB", str(file))
                if log_match:
                    syscall_log = log_match.group(0)
                if fs_match:
                    sample_fs = fs_match.group(0)
                if syscall_log and sample_fs:
                    return syscall_log, str(pathlib.Path(sample_fs).name)
        else:
            logging.error("No sample.zip found. Continuing!")
            self.verify()

    def read_crash_db(self):
        with open(self.path_crash_db, "r") as f:
            contents = f.readlines()
        return contents

    def _get_latest_core(self):
        try:
            find_latest_core_file_cmd = (
                '/usr/bin/find /var/crash -name "core*" -print0 | /usr/bin/xargs -0 ls -t | /usr/bin/head -n1'
            )
            latest_core_file = self.vm_object.exec_cmd_quiet(find_latest_core_file_cmd)
            get_core_file_size_cmd = '/usr/bin/stat {} | /usr/bin/cut -d" " -f8'.format(latest_core_file)
            if latest_core_file and int(str(self.vm_object.exec_cmd_quiet(get_core_file_size_cmd)).strip()) > 1:
                self.vm_object.exec_cmd_quiet("mv {} /var/crash/core.txt.reprod".format(latest_core_file))
                self.reprod_crash_file = "/var/crash/core.txt.reprod"
            else:
                return None
        except ValueError:
            return None

    def _fetch_latest_core_file(self, save_to):
        try:
            self._get_latest_core()
            logging.error("LATEST CORES: {}".format(self.reprod_crash_file))
            if self.reprod_crash_file:
                self.vm_object.cp_to_host(
                    save_files_at=save_to,
                    get_files_from=str(pathlib.Path(self.reprod_crash_file).parent),
                    list_of_files_to_copy=str(pathlib.Path(self.reprod_crash_file).name),
                )
                self.reprod_crash_file = os.path.join(save_to, str(pathlib.Path(self.reprod_crash_file).name))
                return 1
            else:
                logging.error("No new core files found!")
                return 0
        except TypeError:
            logging.error("No core file(s) found. Continuing!")
            return 0

    def get_shasum_of_repro_crash(self, save_to):
        if self._fetch_latest_core_file(save_to):
            with open(self.reprod_crash_file, "rb") as f:
                data = f.read()
            return extract_core_features.get_sha256_sum(extract_core_features.get_core_details(data))
        else:
            return "NONE"


def main():
    CrashVerifier(
        crash_db="/home/dev/git/bsdfuzz/fsfuzz/src/crash_dumps/crash.db", target_os="freebsd",
    )


if __name__ == "__main__":
    sys.exit(main())
