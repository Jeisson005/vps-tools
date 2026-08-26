#!/usr/bin/env bash
set -euo pipefail

echo "==> [01/11] Updating system and installing essential packages..."

if [[ $EUID -ne 0 ]]; then
  echo "Error: This script must be run as root or with sudo." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

echo "--> Updating apt repositories..."
apt-get update -y

echo "--> Upgrading system packages..."
apt-get upgrade -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold"

echo "--> Installing essential diagnostic, performance and utility tools..."
apt-get install -y \
  apt-transport-https \
  ca-certificates \
  curl \
  wget \
  git \
  gnupg \
  lsb-release \
  ufw \
  fail2ban \
  unattended-upgrades \
  htop \
  btop \
  ncdu \
  zstd \
  tree \
  iotop \
  sysstat \
  mtr-tiny \
  iperf3 \
  net-tools \
  dnsutils \
  rsync \
  zip \
  unzip \
  tar \
  jq \
  nano \
  software-properties-common

echo "--> Essential system packages installed successfully."
