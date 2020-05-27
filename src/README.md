# makeFS

This script produces a valid ext2/ext3/ext4/ufs/zfs filesystem of size 'X'.  
Naming can be specified, otherwise a random UID is created.  
It also can be populated with with 'N' files of max size 'M' if specified.  
This includes, files made from `/dev/urandom`, directories, sym- and hardlinks.  
The file and directory structure is created at random.  

e.g.: `python3 makeFS2.py -fs "ext2" -n "ext20MB" -s 20 -p 15 -ps 1000`

# VmManager
This script is able to install and manage multiple VMs via libvirt and its python bindings

## VM Setup and Install:
It's expected to create an instance of VMManager first:
```
vmm = VMMANAGER()
```

You can tweak hardware details of your VM by calling `setup()`:
```
@param name= Name for the VM
@param vm_memory= RAM in MB. Default=4096
@param vm_cpus= #CPU_CORES. Default=2
@param vm_hdd= HDD size in GB. Default=10
vmm.setup(name='', vm_memory=, vm_cpus=, vm_hdd=)

```

#### Install VM from local .ISO
```
@param iso= Path to the .iso image file
vmm.install_vm(iso='')
```

#### Install VM from web .ISO:
```
@param url_iso= URL from where to wget the .iso image
@param save_dl_to= Path on the local disk. Default='/tmp'
vmm.install_vm(url_iso='', save_dl_to='')
```

#### Install VM from zipped web .ISO:
```
@param url_zip= URL from where to wget the .iso.xz image
@param save_dl_to= Path on the local disk. Default='/tmp'
@param save_unpckd_to= Path on the local disk. Default='/tmp'
@param save_unpckd_as= Filename for the unpacked .iso. Default=Tries to use Archive name without extension
vmm.install_vm(url_zip='',
               save_dl_to='',
               save_unpckd_to='',
               save_unpckd_as='')
```



#### Boot directly from a QCOW2 VM hdd
##### 1. If fetching QCOW from web:
```
@param name= Name for the VM
@param vm_type= A fitting representation of the image from 'qemu-system-XXX'
@param url= URL from where to wget the .qcow2 image
@param save_dl_to= Path on the local disk to save download to. Default='/tmp'
@param save_dl_as= Filename for download. Default=Tries to use Archive name without extension
@param port= Port for port forwarding between Host<->Guest. Default=22
vmm.setup(name='', vm_type='', url='', save_url_cntnt_to='', save_url_cntnt_as='', fwdPort=)
vmm.get_img()
machine = vmm.qemu_boot_qcow()
```

If the QCOW is zipped as .xz you can call `vmm.unpack()` prior to `vmm.run_qemu()`.
`vmm.unpack()`


##### 2. If QCOW already on disk:
```
@param name= Name for the VM
@param vm_type= A fitting representation of the image from 'qemu-system-XXX'
@param unpckd_url_cntnt= Path to and including the local .qcow2 image
@param port= Port for port forwarding between Host<->Guest. Default=22
vmm.setup(name='', vm_type='', unpckd_url_cntnt='', port=)
machine = vmm.qemu_boot_qcow()
```



## VM user interaction:
Note: relative paths should always be resolved automatically

#### Copy files to guest:
```
@param lfile= Path to a file on the host system
@param path_on_guest= Path (dir!) on the guest to save the lfile to
vmm.cp_files_to_guest(lfile='', path_on_guest='')
```
If path does not exist the path gets created

#### Copy files to host:
```
@param rfile= Path to a file on the guest system
@param path_on_host= Path (dir!) on the guest to save the lfile to
@param filename=  Name for the file on the host system
vmm.cp_files_to_host(rfile='', path_on_host='', filename='')
```

#### Tar n files on guest:
Tars the files given in `lst_of_files` in `PATH_REMOTE_DIR` on guest
```
@param rpath= The parent directory on where the files are located
@param archive_name= Name for the archive
@param lst_of_files= List of files @ location rpath
rpath = vmm.qemu_exec_tar_files(rpath='', archive_name='', lst_of_files=['', '', ..., '']) 
``` 

#### Tar a dir on guest:
Tars the whole dir specified
```
@param rpath= The parent directory on where the files are located
@param archive_name= Name for the archive
rpath = vm_exec_tar_dir(rpath='', archive_name='')
```

#### Exec any cmd on guest from cmdline:
```
Executes the CMD given on the commandline on the guest system
vmm.vm_exec_cmd(CMD)
```

#### Exec makedir on guest:
```
Creates a directory including all necessary parents supplied
vmm.vm_exec_mkdir(PATH)
```

#### Exec remove on guest:
```
Does a recursive remove to be able to handle directory and single files
vmm.vm_exec_rm(PATH)
```

#### Get latest crash from guests `/var/crash/:`
```
@param lpath= Path on the host system to save the `latest_crash.tar` archive to
vmm.fetch_latest_crash(lpath=)
```

#### Get latest unknown crash from guests `/var/crash/`:
```
@param lpath= Path on the host system to save the `latest_unknown_crash.tar` archive to
vmm.fetch_latest_unknown_crash(lpath=)
```

#### Get all crashes from guests `/var/crash/`:
```
@param lpath= Path on the host system to save the `allcrashes.tar` archive to
vmm.fetch_all_crashes(lpath=LOCAL_PATH_WHERE_TO_SAVE)
```

## VM Management

On top of providing the above user interface to the VM for interaction several management convenience functions were added too.

#### Boot VMs
This will list the the installed/found VMs managed by libvirt and prompts the user for a box to start

* `vmm.boot_vm()`

#### Manage VMs
All the functions below take an optional `vm_name=` argument for convenient management of other existing VMs.
* `vmm.shutdown_vm()`
* `vmm.suspend_vm()`
* `vmm.resume_vm()`
* `vmm.reset_vm()`
* `vmm.force_stop_vm()`
* `vmm.delete_vm()`
* `vmm.check_vm_state()`
* `vmm.quick_boot()`
* `vmm.reboot_vm_if_crashed()`
* `vmm.reset_vm_if_crashed()`
* `vmm.restore_latest_snap_if_crashed()`

#### Snapshots

Furthermore a snapshot interface was added. These can take the same `vm_name` optional argument as well.

* `vmm.create_snapshot()`
* `vmm.create_snapshot_as(snapshot_name)`
* `vmm.delete_snapshot(snapshot_name)`
* `vmm.restore_snapshot(snapshot_name)`
* `vmm.get_current_snapshot()`

#### Others

* `vmm.create_core_dump()`
* `vmm.take_screenshot()`
* `vmm.check_vm_state()`
