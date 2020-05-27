#!/usr/bin/env sh

pkg install -y vim python3 e2fsprogs p7zip
kldload ext2fs
# Needs to be run as root on the FreeBSD VMs since we require root privs via ssh
sed -i -e 's/#PermitRootLogin no/PermitRootLogin yes/g' /etc/ssh/sshd_config
sed -i -e 's/#PasswordAuthentication no/PasswordAuthentication yes/g' /etc/ssh/sshd_config
sed -i -e 's/#PermitEmptyPasswords no/PermitEmptyPasswords yes/g' /etc/ssh/sshd_config
/etc/rc.d/sshd restart

echo "tmpfs_load='YES'" >> /boot/loader.conf
echo "tmpfs          /tmp        tmpfs   rw,mode=1777    0       0" >> /etc/fstab
# NOTE: To use /tmp as a tmpfs in memory partition for performance speed ups we have to either:
# 1. echo "tmpfs_load='YES'" >> /boot/loader.conf, or
# 2. add options TMPFS to the Kernel file and recompile it
# Afterwards we can add tmpfs          /tmp        tmpfs   rw,mode=1777    0       0 in /etc/fstab
# Source: https://www.chruetertee.ch/blog/archive/2007/08/28/ram-disk-mit-tmpfs-auf-freebsd-erstellen.html
# Source2: Alternatively mdmfs: https://www.freebsd.org/doc/handbook/disks-virtual.html
