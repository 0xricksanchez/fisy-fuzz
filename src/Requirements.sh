#!/bin/bash
set -e

echo "[*] Installing system dependencies..."
sudo apt-get install -y python3-dev python3-pip qemu-kvm libvirt-clients libvirt-dev libvirt-daemon-system gcc \
                        libsdl1.2-dev zlib1g-dev libasound2-dev linux-kernel-headers pkg-config libgnutls28-dev \
                        libpci-dev libglib2.0-dev libfdt-dev libpixman-1-dev net-tools virtinst git libnl-3-dev \
                        libnl-route-3-dev libxml2-dev libpciaccess-dev libyajl-dev xsltproc libdevmapper-dev \
                        uuid-dev qemu qemu-block-extra qemu-guest-agent qemu-system qemu-system-common libvirt-bin \
                        qemu-utils qemu-user qemu-efi openbios-ppc sgabios systemtap pm-utils open-iscsi debootstrap \
                        zfsutils-linux file tmux


mkdir -p ~/git

echo "[*] Installing radamsa"
git clone https://gitlab.com/akihe/radamsa.git ~/git/radamsa/
cd ~/git/radamsa
make
sudo make install

echo "[*] Installing needed python packages..."
sudo -EH python3 -m pip install libvirt-python wget paramiko pprint scp python-magic Pillow colorama seaborn

echo "[*] Setting up users..."
sudo usermod -aG libvirt $USER
sudo usermod -aG libvirt-qemu $USER
sudo usermod -aG kvm $USER

echo "[*] Testing install..."
sudo systemctl enable libvirtd
sudo systemctl start libvirtd
virsh list --all >> /dev/null
if [[ $? == 0 ]]; then
  echo "[+] libvirt successfully set up!"
else
  echo "[-] libvirt failed to install!"
fi

kvm-ok >>  /dev/null
if [[ $? == 0 ]]; then
  echo "[+] kvm support successfully set up!"
  cpu_check=$(cat /proc/cpuinfo | grep "model name" | uniq | grep -oh ": [a-zA-Z]*" | cut -c 3-)
  if [[ ${cpu_check} == "Intel" ]]; then
    modprobe kvm_intel
  elif [[ ${cpu_check} == "AMD" ]]; then
    modprobe kvm_amd
  else
    echo "[*] Unknown CPU, skipping modprobe"
  fi
else
  echo "[-] kvm support failed to install!"
fi

installed_qemu_packages=$(dpkg -l | grep '^ii' | grep -o '  qemu-[a-zA-Z0-9-]*')
echo "[*] Installed QEMU modules:"${installed_qemu_packages}
