import datetime
import getpass
import ipaddress
import logging
import lzma
import os
import pathlib
import socket
import subprocess
import sys
import time
import zipfile
from io import BytesIO

import colorama as clr
import libvirt
import magic
import paramiko
import wget
from PIL import Image, ImageFile

from SnapshotTemplate import snapshot


def get_absolute_path(_path):
    if _path[0] == "~" and not os.path.exists(_path):
        _path = os.path.expanduser(_path)
    abs_path = os.path.abspath(_path)
    return abs_path


def check_if_file_exists(_path):
    if pathlib.Path(_path).exists():
        return True
    else:
        return False


def create_directory(_path):
    pathlib.Path(_path).mkdir(parents=True, exist_ok=True)
    return _path


def create_empty_file(_path, fn):
    pathlib.Path(os.path.join(_path, fn)).touch()


def get_basename(_path):
    return str(pathlib.Path(str(_path)).name)


def get_parent_path(_path):
    return str(pathlib.Path(str(_path)).parent)


def kill_process_by_pid(process):
    # don't send the signal unless it seems it is necessary
    if process.poll() is None:
        try:
            process.kill()
        except OSError:
            pass


class VmManager:
    def setup(self, **kwargs):
        if "name" in kwargs:
            self.name = kwargs["name"]
        if "vm_arch" in kwargs:
            self.vm_arch = kwargs["vm_arch"]
        if "port" in kwargs:
            self.port = kwargs["port"]
        if "enable_kvm" in kwargs:
            if True or False in kwargs["enable_kvm"]:
                self.enable_kvm = kwargs["enable_kvm"]
            else:
                pass
        if "url" in kwargs:
            self.url = kwargs["url"]
        if "save_dl_to" in kwargs:
            self.save_dl_to = get_absolute_path(kwargs["save_dl_to"])
        if "save_unpck_to" in kwargs:
            self.save_unpck_to = get_absolute_path(kwargs["save_unpck_to"])
        if "save_unpck_as" in kwargs:
            self.save_unpck_as = kwargs["save_unpck_as"]
        if "unpckd_url_cntnt" in kwargs:
            if check_if_file_exists(get_absolute_path(kwargs["unpckd_url_cntnt"])) != 0:
                self.path_to_iso_or_qcow = kwargs["unpckd_url_cntnt"]
            else:
                print("{} does not exist!".format(kwargs["unpckd_url_cntnt"]))
                sys.exit(1)
        if "path_to_archive" in kwargs:
            self.p_archive = get_absolute_path(kwargs["path_to_archive"])
        if "copy_files_to" in kwargs:
            self.copy_files_to = get_absolute_path(kwargs["copy_files_to"])
        if "vm_memory" in kwargs:
            self.vm_memory = kwargs["vm_memory"]
        if "vm_cpus" in kwargs:
            self.vm_cpus = kwargs["vm_cpus"]
        if "vm_hdd" in kwargs:
            self.vm_hdd = kwargs["vm_hdd"]
        if "vm_user" in kwargs:
            self.vm_user = kwargs["vm_user"]
        if "vm_password" in kwargs:
            self.vm_password = kwargs["vm_password"]

    def __init__(self):
        logging.basicConfig(level=logging.INFO)
        logging.getLogger("paramiko").setLevel(logging.CRITICAL)
        self.name = ""
        self.vm_arch = "x86"  # The vm_type,enable_kvm flags are only relevant
        self.port = 22  # without having it installed
        self.enable_kvm = True  # enables hardware virtualization features
        self.url = None  # iso/qcow download URL
        self.save_dl_to = "/tmp"  # save download to
        self.save_dl_as = None  # save download file as
        self.save_unpck_to = "/tmp"  # save unpacked file to
        self.save_unpck_as = None  # save unpacked file as
        self.path_to_iso_or_qcow = None  # unzipped .xz image
        self.p_archive = None  # path specified by self.save_url_cntnt_to + self.save_url_cntnt_as
        self.copy_files_to = None  # path can set for copies between host<->guest if path shall stay static
        self.vm_user = None  # saved username for booted VM
        self.vm_password = None  # saved passwd for booted VM
        self.vm_ip = "127.0.0.1"  # saved IPv4 for booted VM
        self.vm_memory = 4096  # RAM of booted VM
        self.vm_cpus = 2  # Number of cores of VM
        self.vm_hdd = 10  # VM HDD size in GB
        self.rshell = None  # remote shell object for host<-> operations
        self.curr_crash_dir = None  # is set to path new directory path for current crash
        self.conn_err_ctr = 0  # counter for connerr that might be a hint towards a broken VM

    def __exit__(self):
        return 1

    ######################################################################################################
    #   BASIC VM OPERATIONS VIA PARAMIKO SSH                                                             #
    ######################################################################################################

    def _get_basic_ssh_conn(self):
        self.get_vm_credentials()
        ssh_conn = paramiko.SSHClient()
        ssh_conn.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_conn.connect(
            hostname=self.vm_ip,
            port=self.port,
            username=self.vm_user,
            password=self.vm_password,
            look_for_keys=False,
            allow_agent=False,
            timeout=15,
        )
        return ssh_conn

    def get_vm_credentials(self):
        if self.vm_user is None or self.vm_password is None:
            self.vm_user = str(input('Username for "{}": '.format(self.name)))
            self.vm_password = getpass.getpass("Password: ")
        else:
            logging.debug("Reusing stored vm credentials.")

    def invoke_remote_ssh_shell(self):
        if not self.silent_vm_state():
            self.reset_vm()
        ssh_conn = self._get_basic_ssh_conn()
        ssh_conn.get_transport().set_keepalive(200)
        ssh_conn.get_transport().open_session()
        ssh_conn.invoke_shell()
        self.rshell = ssh_conn
        return ssh_conn

    def _exec(self, cmd, timeout=10):
        if not self.rshell:
            self.invoke_remote_ssh_shell()
        try:
            # get_pty=True combines stdout/stderr
            _, stdout, _ = self.rshell.exec_command(cmd, get_pty=True, timeout=timeout)
            stdout_decoded = stdout.read().decode().strip()
            if stdout_decoded != "":
                return stdout_decoded
            else:
                return None
        except (paramiko.ssh_exception.SSHException, socket.timeout, paramiko.ssh_exception.NoValidConnectionsError,) as e:
            logging.debug("_EXEC ERROR: {}".format(e))
            return 2
        except UnicodeDecodeError:
            return 1

    def exec_cmd_quiet(self, cmd):
        stdout = self._exec(cmd)
        return stdout

    def exec_cmd(self, cmd):
        stdout = self._exec(cmd)
        print(">> {}".format(stdout))
        return stdout

    def exec_get_return_code(self, cmd):
        res = str(self.exec_cmd_quiet(cmd))
        if int(res[-1]) != 0:
            return False
        else:
            return True

    def interactive_shell(self):
        print(clr.Fore.RED + 'Exit remote shell via "exit"' + clr.Fore.RESET)
        while True:
            command = input("$> ")
            if str.lower(command.strip()) == "exit":
                self.__exit__()
            self._exec(command)

    def zip_files(self, path_to_save_archive_in, files, archive_path):
        file_list = " ".join(os.path.join(path_to_save_archive_in, f) for f in files)
        logging.debug("Packing {} in {}".format(file_list, archive_path))
        return self.exec_get_return_code("tar -jcvf {} {}; echo $?".format(archive_path, file_list))

    def mkdir(self, rpath):
        return self.exec_get_return_code("/bin/mkdir -p {}; echo $?".format(rpath))

    def rm_files(self, rpath):
        return self.exec_get_return_code("/bin/rm -rf {}; echo $?".format(rpath))

    def vm_ls(self, rpath):
        return self._exec("/bin/ls -lah {}".format(rpath))

    @staticmethod
    def _prep_file_list(list_of_files_to_copy, files_to_copy, save_files_at):
        if isinstance(files_to_copy, str):
            list_of_files_to_copy.append(os.path.join(save_files_at, files_to_copy))
        else:
            list_of_files_to_copy.extend(files_to_copy)
            list_of_files_to_copy[:] = [os.path.join(save_files_at, x) for x in list_of_files_to_copy]
        return list_of_files_to_copy

    def _get_files(self, list_of_files_to_copy, save_files_at):
        try:
            if not self.rshell:
                self.invoke_remote_ssh_shell()
            ftp_client = self.rshell.open_sftp()
            for f in list_of_files_to_copy:
                ftp_client.get(f, os.path.join(save_files_at, get_basename(f)))
            ftp_client.close()
        except paramiko.ssh_exception.SSHException as e:
            logging.error("SSHException during get files: {}\nResetting and trying to invoke new rshell".format(e))
            self.reset_vm()
            self.new_rshell()
            self._get_files(list_of_files_to_copy, save_files_at)

    def cp_to_host(self, save_files_at, get_files_from, list_of_files_to_copy, zipped=False):
        sanitized_list_of_files_to_copy = []
        try:
            save_files_at, get_files_from = (
                get_absolute_path(save_files_at),
                get_absolute_path(get_files_from),
            )
            self.mkdir(save_files_at)
            if zipped:
                archive_name = str(datetime.datetime.today().strftime("%d_%m_%Y")) + ".bzip2"
                archive_path = os.path.join("/tmp", archive_name)
                if self.zip_files(get_files_from, list_of_files_to_copy, archive_path=archive_path):
                    sanitized_list_of_files_to_copy.append(archive_path)
                else:
                    logging.error("Failed to compress: {}/{}".format(get_files_from, list_of_files_to_copy))
                    sanitized_list_of_files_to_copy = self._prep_file_list(
                        sanitized_list_of_files_to_copy, list_of_files_to_copy, get_files_from,
                    )
            else:
                sanitized_list_of_files_to_copy = self._prep_file_list(
                    sanitized_list_of_files_to_copy, list_of_files_to_copy, get_files_from,
                )
            self._get_files(sanitized_list_of_files_to_copy, save_files_at)
            return 1
        # except (TypeError, OSError) as e:
        #    logging.error('Encountered an error while fetching files: {}'.format(e))
        #    return 0
        except FileNotFoundError:
            logging.error("To host: One or more files of {} not found".format(list_of_files_to_copy))
            return None

    def _send_files(self, list_of_files_to_copy, save_files_at):
        try:
            if not self.rshell:
                self.invoke_remote_ssh_shell()
            ftp_client = self.rshell.open_sftp()
            for f in list_of_files_to_copy:
                ftp_client.put(f, os.path.join(save_files_at, get_basename(f)))
            ftp_client.close()
        except paramiko.ssh_exception.SSHException as e:
            logging.error("SSHException during send files: {}\n Trying to invoke new rshell".format(e))
            self.new_rshell()
            self._send_files(list_of_files_to_copy, save_files_at)

    def cp_to_guest(self, get_files_from, list_of_files_to_copy, save_files_at, zipped=False):
        try:
            get_files_from, save_files_at = (
                get_absolute_path(get_files_from),
                get_absolute_path(save_files_at),
            )
            self.mkdir(save_files_at)
            sanitized_list_of_files_to_copy = []
            if zipped:
                file_list = " ".join(os.path.join(get_files_from, f) for f in list_of_files_to_copy)
                with zipfile.ZipFile("/tmp/files.zip", "w", compression=zipfile.ZIP_DEFLATED) as myzip:
                    for f in file_list:
                        # arcname removes dirpath to actual file and just takes the file itself
                        myzip.write(f, arcname=pathlib.Path(f).name)
                sanitized_list_of_files_to_copy.append("/tmp/files.zip")
            else:
                sanitized_list_of_files_to_copy = self._prep_file_list(
                    sanitized_list_of_files_to_copy, list_of_files_to_copy, get_files_from,
                )
            self._send_files(sanitized_list_of_files_to_copy, save_files_at)
        # except (TypeError, OSError) as e:
        #    logging.error('Encountered an error while fetching files: {}'.format(e))
        #    return 0
        except FileNotFoundError:
            logging.error("To guest: One or more files of {} not found".format(list_of_files_to_copy))
            return None

    def get_last_changed_file_in_dir(self, search_path):
        cmd = "/bin/ls -t {} | head -n1".format(search_path)
        try:
            latest_file = self._exec(cmd)
            logging.debug(latest_file)
            return search_path, latest_file
        except AttributeError as e:
            logging.debug(e)

    def _get_latest_core(self):
        try:
            core_files = []
            find_latest_core_file_cmd = '/usr/bin/find /var/crash -name "core*" -print0'
            latest_core_file = self._exec(find_latest_core_file_cmd)
            if not latest_core_file:
                return None
            else:
                find_latest_core_file_cmd = (
                    '/usr/bin/find /var/crash -name "core*" -print0 | /usr/bin/xargs -0 ls -t | /usr/bin/head -n1'
                )
                latest_core_file = self._exec(find_latest_core_file_cmd)
            find_latest_vmcore_cmd = (
                '/usr/bin/find /var/crash -name "vmcore*" -print0 | /usr/bin/xargs -0 ls -t | /usr/bin/head -n1'
            )
            latest_vmcore_file = self._exec(find_latest_vmcore_cmd)
            get_core_file_size_cmd = '/usr/bin/stat {} | /usr/bin/cut -d" " -f8'.format(latest_core_file)
            if latest_core_file and latest_vmcore_file and int(self._exec(get_core_file_size_cmd).strip()) > 1:
                core_files.append(os.path.join("/var/crash", latest_core_file.strip()))
                core_files.append(os.path.join("/var/crash", latest_vmcore_file.strip()))
                return core_files
            else:
                return None
        except ValueError:
            return None

    def fetch_latest_core_file(self):
        self.curr_crash_dir = None
        try:
            latest_core_files = self._get_latest_core()
            logging.debug("LATEST CORES: {}".format(latest_core_files))
            if len(latest_core_files) == 2:
                _timestamp_dir = os.path.join("crash_dumps", self._get_timestamp())
                self.curr_crash_dir = os.path.join(os.getcwd(), _timestamp_dir)
                create_directory(self.curr_crash_dir)
                for list_entry in latest_core_files:
                    if "core.txt" in list_entry:
                        zipped_enable = False
                    else:
                        zipped_enable = False
                    self.cp_to_host(
                        save_files_at=self.curr_crash_dir,
                        get_files_from=get_parent_path(list_entry),
                        list_of_files_to_copy=get_basename(list_entry),
                        zipped=zipped_enable,
                    )
                return 1
            else:
                logging.error("No new core files found!")
                return 0
        except TypeError:
            logging.error("No core file(s) found. Continuing!")
            return 0

    def fetch_all_core_files(self):
        get_all_core_files_cmd = '/bin/ls /var/crash/ | grep "core.txt"'
        # gets a list of files without any empty string entries
        core_files = list(filter(None, self._exec(get_all_core_files_cmd).split("\n")))
        if core_files:
            all_cores = " ".join(f for f in core_files)
            self.cp_to_host(
                save_files_at="crash_dumps/", get_files_from="/var/crash/", list_of_files_to_copy=all_cores,
            )
        else:
            logging.info("No core files found!")

    def check_vm_state(self):
        try:
            if not int(
                subprocess.check_output(
                    "timeout 3 nc -z {} 22; echo $?".format(self.vm_ip), shell=True, encoding="utf-8",
                ).strip()
            ):
                print(clr.Fore.GREEN + "[+] VM status: {}".format("OK" + clr.Fore.RESET))
                return 1
            else:
                print(clr.Fore.RED + "[!] VM status: {}".format("Not Responding" + clr.Fore.RESET))
                return 0
        except subprocess.TimeoutExpired:
            print(clr.Fore.RED + "[!] VM status: {}".format("Not Responding" + clr.Fore.RESET))
            return 0

    def silent_vm_state(self):
        if not int(
            subprocess.check_output("timeout 3 nc -z {} 22; echo $?".format(self.vm_ip), shell=True, encoding="utf-8",).strip()
        ):
            # ret code was 0, VM reachable
            return 1
        else:
            return 0

    def crash_handler(self):
        print(clr.Fore.LIGHTYELLOW_EX + "[*] Checking for crash dump..!" + clr.Fore.RESET)
        try:
            self.reset_vm()
            return self._return_core_path_if_present()
        except paramiko.ssh_exception.NoValidConnectionsError as e:
            logging.error("NoValidConnErr in Manager crash handler: {}\n self.cerr is {}".format(e, self.conn_err_ctr))
            self.conn_err_ctr += 1
            if self.conn_err_ctr == 2:
                self.conn_err_ctr = 0
                # Probably stuck in a boot loop at this point because of a broken system
                # ext2: fsck /dev/ad0p2: Segmentation fault
                # Unknown error1: help!
                self.restore_snapshot(self.get_current_snapshot())
                self.new_rshell()
            else:
                self.crash_handler()

    def _return_core_path_if_present(self):
        self.new_rshell()
        if self.fetch_latest_core_file():
            print(clr.Fore.LIGHTYELLOW_EX + "\t[*] Found core file" + clr.Fore.RESET)
            self.conn_err_ctr = 0
            return self.curr_crash_dir
        else:
            self.conn_err_ctr = 0
            return None

    def new_rshell(self):
        self.rshell = None
        self.invoke_remote_ssh_shell()

    ######################################################################################################
    #   LIBVIRT VM OPERATIONS                                                                            #
    ######################################################################################################

    def test_install(self):
        if subprocess.run("virsh list --all".split(), stdout=subprocess.DEVNULL) and subprocess.run(
            "qemu-system-{} --help".format(self.vm_arch).split(), stdout=subprocess.DEVNULL,
        ):
            logging.info("Tests passed!")
        else:
            logging.error("QEMU and/or libvirt not properly installed!")
            sys.exit(1)

    def _boot_sleep(self, sleep_timer_in_seconds):
        sys.stdout.write(clr.Fore.LIGHTYELLOW_EX + "\t[*] Please stand by." + clr.Fore.RESET)
        for i in range(sleep_timer_in_seconds):
            sys.stdout.write(clr.Fore.LIGHTYELLOW_EX + "." + clr.Fore.RESET)
            sys.stdout.flush()
            time.sleep(1)
        sys.stdout.write("\033[F")  # back to previous line

    @staticmethod
    def get_open_libvirt_connection():
        conn = libvirt.open()
        if conn is None:
            logging.error("Failed to open connection to hypervisor")
            sys.exit(1)
        else:
            return conn

    def get_domain_object(self):
        conn = self.get_open_libvirt_connection()
        dom = conn.lookupByName(self.name)
        return conn, dom

    def set_vcpus(self, vcpus):
        conn, dom = self.get_domain_object()
        try:
            dom.setVcpus(vcpus)
        except libvirt.libvirtError:
            logging.error("Failed to set new max amount of vcpus for {}!".format(dom.name()))
        finally:
            conn.close()

    def set_memory(self, memory):
        conn, dom = self.get_domain_object()
        try:
            dom.setMemory(memory)
        except libvirt.libvirtError:
            logging.error("Failed to set new max amount of RAM for {}!".format(dom.name()))
        finally:
            conn.close()

    def list_installed_vms(self):
        conn = self.get_open_libvirt_connection()
        hosts = conn.listAllDomains(0)
        print("[*] Found vms: [" + ", ".join(h.name() for h in hosts) + "]")
        conn.close()

    def get_ip_of_vm(self):
        # TODO: Fix by utilizing libvirts python API
        iface = subprocess.check_output("virsh domifaddr {}".format(self.name).split(), encoding="utf-8")
        ipv4 = iface.split()[-1].split("/")[0].strip()
        try:
            if ipaddress.ip_address(ipv4):
                self.vm_ip = ipv4
        except ValueError as e:
            logging.error("[!] Failed to fetch an IPv4 address of {}".format(self.name))
            logging.error("Expected: xxy.xxy.xxy.xyz")
            logging.error("Got : {}".format(e))
            logging.error("[*] Trying to restore from snapshot")
            cur_snap = self.get_current_snapshot()
            if cur_snap:
                self.restore_snapshot(cur_snap)
                self.reset_vm()
                self.quick_boot(self.name)
            else:
                logging.error("[!] No snapshot found. Trying to reset VM instead")
                self.reset_vm()
            self.get_ip_of_vm()

    def quick_boot(self, vm_name):
        try:
            self.name = vm_name
            conn, dom = self.get_domain_object()
            self.get_vm_credentials()
            if not dom.isActive():
                dom.create()
                # needs around 60 seconds until booting seq started network ifaces
                self._boot_sleep(60)
                self.get_ip_of_vm()
                print("\n[+] VM started @ {}!".format(self.vm_ip))
            else:
                self.get_ip_of_vm()
            conn.close()
        except libvirt.libvirtError:
            pass

    def boot_vm(self):
        if self.list_installed_vms() != "":
            print("[*] Which VM do you want to start?")
            self.name = input(">> ")
            conn = self.get_open_libvirt_connection()
            dom = conn.lookupByName(self.name)
            active = dom.isActive()
            if active == 1:
                self.get_ip_of_vm()
            else:
                dom.create()
                self._boot_sleep(60)
                self.get_ip_of_vm()
                print("[+] VM started @ {}!".format(self.vm_ip))
            conn.close()
        else:
            print("[!] No VMs found!")
            sys.exit(1)

    def shutdown_vm(self):
        conn, dom = self.get_domain_object()
        dom.shutdown()
        conn.close()

    def suspend_vm(self):
        conn, dom = self.get_domain_object()
        dom.suspend()
        conn.close()

    def resume_vm(self):
        conn, dom = self.get_domain_object()
        self._boot_sleep(20)
        dom.resume()
        conn.close()

    def reset_vm(self):
        # Reset emulates the power reset button on a machine, where all
        # hardware sees the RST line set and re-initializes internal state
        conn, dom = self.get_domain_object()
        dom.reset()
        self._boot_sleep(40)
        timer = 40
        while True:
            if timer > 120:
                logging.error("\nCould not fully boot in {} seconds. Resetting VM again!".format(timer))
                self.restore_snapshot(self.get_current_snapshot())
                break
            elif not self.silent_vm_state():
                sys.stdout.write(".....")
                sys.stdout.flush()
                time.sleep(5)
                timer += 5
            else:
                break
        print("\n")
        conn.close()

    def reboot_vm(self):
        # The hypervisor will choose the method of shutdown it considers best
        conn, dom = self.get_domain_object()
        dom.reboot()
        self._boot_sleep(60)
        conn.close()

    def force_stop_vm(self):
        conn, dom = self.get_domain_object()
        dom.destroy()
        conn.close()

    def delete_vm(self, vm_name):
        conn = self.get_open_libvirt_connection()
        try:
            pool = conn.storagePoolLookupByName("default")
            dom = conn.lookupByName(vm_name)
            dom.undefineFlags(libvirt.VIR_DOMAIN_UNDEFINE_NVRAM)
            stgvol = pool.storageVolLookupByName("{}.qcow2".format(self.name)).path()
            if stgvol:
                stgvol.wipe(0)
                stgvol.delete(0)
        except libvirt.libvirtError as e:
            logging.error("Failed to properly delete: {}".format(e))
        finally:
            conn.close()

    def rename_vm(self, new_name):
        conn, dom = self.get_domain_object()
        dom.rename(new_name)
        conn.close()

    def clone_vm(self, clone_name):
        # TODO: Fix by utilizing libvirts python API
        conn, dom = self.get_domain_object()
        domname = dom.name()
        cmd = "virt-clone --original {} --name {} --auto-clone".format(domname, clone_name)
        subprocess.call(cmd.split())

    def _png_writer(self, stream, data, buffer):
        # Writes screenshot to disk
        ImageFile.LOAD_TRUNCATED_IMAGES = True
        buffer.write(data)
        buffer.seek(0)
        image = Image.open(buffer)
        image.save(os.path.join("vm_screenshots", "{}_{}.png".format(self.name, self._get_timestamp())))

    @staticmethod
    def _get_timestamp():
        time_stamp = datetime.datetime.now().isoformat(timespec="seconds")
        time_stamp = str(time_stamp).replace(":", "_").replace(" ", "_").rsplit(".")[0]
        return time_stamp

    def take_screenshot(self):
        conn = self.get_open_libvirt_connection()
        create_directory(os.path.join(os.getcwd(), "vm_screenshots"))
        dom = conn.lookupByName(self.name)
        if dom.isActive():
            stream = conn.newStream()
            dom.screenshot(stream=stream, screen=0)
            buffer = BytesIO()
            stream.recvAll(self._png_writer, buffer)
            stream.finish()
        conn.close()

    @staticmethod
    def get_snapshot_xml_representation(dom, snap_name=None):
        raw_xml = dom.XMLDesc(0)
        if snap_name:
            return snapshot.xml_head_name.format(snap_name) + raw_xml + snapshot.xml_tail
        else:
            return snapshot.xml_head.format(snap_name) + raw_xml + snapshot.xml_tail

    def create_snapshot(self):
        conn, dom = self.get_domain_object()
        try:
            xml_descr = self.get_snapshot_xml_representation(dom)
            dom.snapshotCreateXML(xml_descr)
        except libvirt.libvirtError:
            logging.error("Failed to create snapshot for {}".format(self.name))
        finally:
            conn.close()

    def create_snapshot_with_name(self, snap_name):
        conn, dom = self.get_domain_object()
        try:
            xml_descr = self.get_snapshot_xml_representation(dom, snap_name)
            dom.snapshotCreateXML(xml_descr)
        except libvirt.libvirtError as e:
            logging.error("{} - Failed to create snapshot: {}".format(dom, e))
        finally:
            conn.close()

    def delete_snapshot(self, snap_name):
        conn, dom = self.get_domain_object()
        snap_list = dom.snapshotListNames()
        if snap_name in snap_list:
            try:
                _snapshot = dom.snapshotLookupByName(snap_name)
                _snapshot.delete()
            except libvirt.libvirtError as e:
                logging.error("{} - Failed to delete snapshot: {}".format(snap_name, e))
        conn.close()

    def list_snapshots(self):
        conn, dom = self.get_domain_object()
        snapshots = dom.listAllSnapshots()
        if snapshots:
            print("[*] Found snapshots: " + ", ".join(x.getName() for x in snapshots))
            return snapshots
        else:
            logging.error("Failed to find any snapshots for {}!".format(self.name))
        conn.close()

    def restore_snapshot(self, snap_name):
        conn, dom = self.get_domain_object()
        try:
            snap = dom.snapshotLookupByName(snap_name)
            dom.revertToSnapshot(snap)
            self.get_vm_credentials()
            if not dom.isActive():
                dom.create()
                # needs around 60 seconds until booting seq started network ifaces
                self._boot_sleep(60)
            conn.close()
            logging.warning("Successfully reset {} to snapshot: {}, VM status: {}".format(dom.name(), snap_name, dom.state()))
        except libvirt.libvirtError:
            logging.error("Failed to reset {} to snapshot: {}".format(dom.name(), snap_name))

    def get_current_snapshot(self):
        conn, dom = self.get_domain_object()
        try:
            cur = dom.snapshotCurrent().getName()
            return cur
        except libvirt.libvirtError:
            logging.error("Failed to find current snapshots for {}!".format(dom.name()))
            return None
        finally:
            conn.close()

    ######################################################################################################
    #   VM IMAGE FETCHING AND INSTALLATION                                                               #
    ######################################################################################################

    def get_img(self, url, save_to):
        """
        Attempts to download a(n) (packen) iso
        :param url: Full URL to image
        :param save_to: lpath to save to
        :return: path to downloaded file
        """
        if self.p_archive:
            print("[!] Archive specified!\nAborting image fetch")
        if not url:
            print("[!] Requires url!\nAborting...")
            sys.exit(1)
        else:
            create_directory(save_to)
            url_split_archive_name_only = url.split("/")[-1]
            save_img = get_absolute_path(os.path.join(save_to, url_split_archive_name_only))
            if check_if_file_exists(save_img):
                print("[!] File {} already exists.".format(save_img))
                self.p_archive = save_img
            else:
                print("[*] Fetching {}".format(url))
                if wget.download(url, save_img):
                    self.p_archive = save_img
                if "QEMU QCOW Image" in magic.from_file(self.p_archive):
                    self.path_to_iso_or_qcow = self.p_archive
            return self.p_archive

    def _unpack_lzma(self, save_as):
        """
        Unpacks a lzma compatible archive (e.g ISO.xz)
        :param save_as: save ISO as
        :return: path to unpacked content
        """
        with lzma.open(self.p_archive) as f, open(save_as, "wb") as fout:
            logging.info("Decompressing....")
            file_cntnt = f.read()
            fout.write(file_cntnt)
            fout.close()
        self.path_to_iso_or_qcow = save_as

    def _set_unpckd_path(self, save_as, save_to):
        """
        Some path demangling
        :param save_as: Name of unpacked iso.xz
        :param save_to: Path to save unpacked iso.xz to
        :return:
        """
        img_n = ""
        archive_no_ext, _ = os.path.splitext(self.p_archive)
        save_to = get_absolute_path(save_to)
        if save_as and save_to:
            img_n = os.path.join(save_to, save_as)
        elif save_as and save_to is None:
            abs_path_without_archive = pathlib.Path(self.p_archive).parent
            img_n = os.path.join(abs_path_without_archive, save_as)
        elif save_as is None and save_to:
            base_name = pathlib.Path(archive_no_ext).name
            img_n = os.path.join(save_to, base_name)
        elif save_as is None and save_to is None:
            img_n = archive_no_ext
        return get_absolute_path(img_n)

    def unpack(self, save_as, save_to):
        """
        Unpack downloaded ISO.xz as save_as to save_to
        :param save_as: Name of unpacked iso.xz
        :param save_to: Path to save unpacked iso.xz to
        """
        create_directory(save_to)
        if check_if_file_exists(self.p_archive):
            unpkd_img_name = self._set_unpckd_path(save_as, save_to)
            logging.debug("[*] Trying to decompress {} as {}".format(self.p_archive, unpkd_img_name))
            if not pathlib.Path(unpkd_img_name).exists():
                self._unpack_lzma(unpkd_img_name)
        else:
            logging.debug("[!] Error unpacking {}".format(self.p_archive))

    def _install(self, iso):
        abs_iso = get_absolute_path(iso)
        cmd = "virt-install --name {}\
          --memory {}\
          --vcpus {}\
          --disk size={}\
          --cdrom {}\
          --os-variant freebsd8".format(
            self.name, self.vm_memory, self.vm_cpus, self.vm_hdd, abs_iso
        )
        subprocess.run(cmd.split())

    def install_vm(
        self, iso=None, url_iso=None, url_zip=None, save_dl_to="~/Downloads", save_unpckd_to=None, save_unpckd_as=None,
    ):
        """
        Setups a VM install that varies on the supplied parameters
        :param iso: ISO.iso VM image
        :param url_iso: Full URL to a ISO.iso image
        :param url_zip:  Full URL to a iso.iso.xz image
        :param save_dl_to: Path to save the downloaded content to
        :param save_unpckd_to: Path to save the unpacked downloaded content to
        :param save_unpckd_as: Full Path that specifies the name of the unpacked content
        """
        if iso:
            self._install(iso)
        if url_iso:
            self.get_img(url_iso, save_to=save_dl_to)
            self._install(self.p_archive)
        if url_zip:
            self.get_img(url=url_zip, save_to=save_dl_to)
            self.unpack(save_to=save_unpckd_to, save_as=save_unpckd_as)
            self._install(self.path_to_iso_or_qcow)


######################################################################################################
#   QUICK QEMU BOOT WITHOUT INSTALLATION                                                             #
######################################################################################################


class QEMU(VmManager):
    def __init__(
        self, name, architecture, path_to_hdd, enable_kvm=True, port=22, ip="127.0.0.1", memory=2048,
    ):
        super(QEMU, self).__init__()
        logging.basicConfig(level=logging.INFO)
        logging.getLogger("paramiko").setLevel(logging.CRITICAL)
        self.name = name
        self.vm_arch = architecture
        self.port = port
        self.enable_kvm = enable_kvm
        self.qemu_process = None
        self.vm_memory = memory
        self.ip = ip
        self.path_to_iso_or_qcow = path_to_hdd

    def qemu_boot_qcow(self):
        """
        Requires a proper prior VmManager.setup(...) call to set all the necessary parameters
        """
        if self.enable_kvm:
            qemu_cmd = (
                "qemu-system-{} -m {} --enable-kvm"
                " -netdev user,id=mynet0,hostfwd=tcp:{}:{}-:22"
                " -device e1000,netdev=mynet0 {}".format(
                    self.vm_arch, self.vm_memory, self.vm_ip, self.port, self.path_to_iso_or_qcow,
                )
            )
        else:
            qemu_cmd = (
                "qemu-system-{} -m {}"
                " -netdev user,id=mynet0,hostfwd=tcp:{}:{}-:22"
                " -device e1000,netdev=mynet0 {}".format(
                    self.vm_arch, self.vm_memory, self.vm_ip, self.port, self.path_to_iso_or_qcow,
                )
            )
        logging.debug(qemu_cmd)
        try:
            active_machine = subprocess.Popen(qemu_cmd.split(), stdout=subprocess.PIPE, preexec_fn=os.setsid)
            self.qemu_process = active_machine
            if self.qemu_process.poll() is None:
                print("[*] Sleeping for 60s to wait for boot...")
                self._boot_sleep(60)
            else:
                sys.exit(1)
            return active_machine
        except RuntimeError as e:
            logging.debug(e)


def main():
    vm = VmManager()
    vm.setup(name="fuzzbox")
    vm.install_vm(iso="~/Downloads/FreeBSD-11.2-RELEASE-amd64-dvd1.iso")


if __name__ == "__main__":
    sys.exit(main())
