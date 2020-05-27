#!/usr/bin/env sh

pkg install -y vim python3 e2fsprogs p7zip gdb
kldload ext2fs
# Needs to be run as root on the FreeBSD VMs since we require root privs via ssh
sed -i -e 's/#PermitRootLogin no/PermitRootLogin yes/g' /etc/ssh/sshd_config
sed -i -e 's/#PasswordAuthentication no/PasswordAuthentication yes/g' /etc/ssh/sshd_config
sed -i -e 's/#PermitEmptyPasswords no/PermitEmptyPasswords yes/g' /etc/ssh/sshd_config

/etc/rc.d/sshd restart

echo "kern.panic_reboot_wait_time=-1" >> /etc/sysctl.conf
echo "vm.redzone.panic=1" >> /etc/sysctl.conf

# https://gist.github.com/bijanebrahimi/f2eb0c620d81aa6234e121a0ddd88cc2
echo "options DDB" >>  /usr/src/sys/amd64/conf/GENERIC
echo "options KDB" >>  /usr/src/sys/amd64/conf/GENERIC
echo "options KDB_TRACE" >>  /usr/src/sys/amd64/conf/GENERIC
# echo "options KDB_UNATTENDED" >>  /usr/src/sys/amd64/conf/GENERIC
echo "options INVARIANTS" >>  /usr/src/sys/amd64/conf/GENERIC
echo "options INVARIANT_SUPPORT" >>  /usr/src/sys/amd64/conf/GENERIC
echo "options DIAGNOSTIC" >>  /usr/src/sys/amd64/conf/GENERIC
echo "options DEBUG_REDZONE" >>  /usr/src/sys/amd64/conf/GENERIC
echo "options PANIC_REBOOT_WAIT_TIME=0" >>  /usr/src/sys/amd64/conf/GENERIC
cd /usr/src/ || exit
# -DKERNFAST
make -j4 buildkernel KERNCONF=GENERIC
make installkernel KERNCONF=GENERIC
# kgdb /boot/kernel/kernel /var/crash/vmcore.
