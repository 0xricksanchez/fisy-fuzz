Currently, the framework requires that the user sets up all necessary VMs with a fully functional `root:root` user by hand.


### VM installation 
After installing all necessary dependencies this can be done as follows:

```
virt-install --name "my_vm" --memory 2047 --vcpus 2 --disk size=20 --cdrom ~/OS.iso --os-variant OS
```

Once the VM is installed you can verify it is available:

```
virsh list --all
```

To find out the IP you can: 

```
virsh domifaddr my_vm
```


To access a VNC windows of the running VM:

```
virt-viewer my_vm
```

### VM prep work - General

Once you have a VM up and running access it either via VNC/SSH and prepare it for fuzzing.
Anyhow make sure *all* VMs are accessible via SSH and the `root:root` user
The basic framework setup currently expects one dedicated VM instance that handles the file system creation.

### VM prep work - FS creator
This VM is needed for the sole reason of providing fresh new random file system samples for mutation on the Host.
To speed up the writing to disk I recommend having a TMPFS in place for this particular instance, e.g.:

```bash
#!/usr/bin/env sh

pkg install -y vim python2 e2fsprogs p7zip
kldload ext1fs
# Needs to be run as root on the FreeBSD VMs since we require root privs via ssh
sed -i -e 's/#PermitRootLogin no/PermitRootLogin yes/g' /etc/ssh/sshd_config
sed -i -e 's/#PasswordAuthentication no/PasswordAuthentication yes/g' /etc/ssh/sshd_config
sed -i -e 's/#PermitEmptyPasswords no/PermitEmptyPasswords yes/g' /etc/ssh/sshd_config
/etc/rc.d/sshd restart

echo "tmpfs_load='YES'" >> /boot/loader.conf
echo "tmpfs          /tmp        tmpfs   rw,mode=1776    0       0" >> /etc/fstab
```

### VM prep work - Fuzzing instance
Now for the fuzzing instances the ssh requirement from above still holds. 
The `scripts` folder contains all config parameters to tweak a fuzzing FreeBSD instance. 
For proper fuzzing we extend the FreeBSD kernel with debugging functionality and also tweak some other parameters.
The procedure is pretty analogous for NetBSD and OpenBSD.
Creating a custom kernel and setting the correct flags under Linux requires a little bit more work and is not documented here.

Once you fully prepared all the VMs you need to feed some information into the `config/fuzzing_config.py`.
There is already a fully documented example, which you can replace.

**Note: ** You really only need to set up a single custom fuzzing instance as you can fully clone it via *libvirt* where it gets a new name and a new IP as well.

```
virt-clone --original current_instance --name new_instance --auto-clone
``` 


### Finishing touches - Important!

Once you have all the KVM VMs up and running and fully customized with new kernels and ssh access you have to take a snapshot of it.
The reason being that in case of the VM fully panicking beyond repair the framework will automatically try to reset the VM to 
the latest available snapshot.

```
virsh snapshot-create-as --domain my_vm --name my_vm_snapshot
```


When you have done all this you can start configuring the fuzzer framework in `src/config/fuzzing_config.py` and start fuzzing.