#!/usr/bin/env sh
# Some stuff to setup for the FreeBSD fuzzer instances..

pkg install -y vim python3 e2fsprogs p7zip gdb wget curl
kldload ext2fs
sed -i -e 's/#PermitRootLogin no/PermitRootLogin yes/g' /etc/ssh/sshd_config
sed -i -e 's/#PasswordAuthentication no/PasswordAuthentication yes/g' /etc/ssh/sshd_config

/etc/rc.d/sshd restart

echo "kern.panic_reboot_wait_time=-1" >> /etc/sysctl.conf # Doesnt reboot on crash
# echo "kern.panic_reboot_wait_time=0" >> /etc/sysctl.conf # immediate reboot on crash
echo "vm.redzone.panic=1" >> /etc/sysctl.conf