#!/bin/bash
set -e

sudo apt update
sudo apt upgrade -y
sudo apt-get install -yqq linux-crashdump python3-dev python3-pip zfsutils-linux file p7zip-full openssh-server vim
# systemd specific solution for tmpfs mounting!
sudo ln -s /usr/share/systemd/tmp.mount /etc/systemd/system/tmp.mount
sudo systemctl enable tmp.mount
sudo systemctl start tmp.mount
sed -i -e 's/#Port 22/Port 22/g' /etc/ssh/sshd_config
sudo ufw allow 22
sudo systemctl restart ssh

echo "panic=0" >> /etc/sysctl.conf
echo "kernel.core_pattern=/var/crash/core.%t.%p" >> /etc/sysctl.conf
echo "kernel.panic=10" >> /etc/sysctl.conf
echo "kernel.unknown_nmi_panic=1" >> /etc/sysctl.conf