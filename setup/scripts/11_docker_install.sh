#!/usr/bin/env bash
set -euo pipefail

echo "==> [11/11] Checking / Installing Docker CE & Docker Compose..."

if [[ $EUID -ne 0 ]]; then
  echo "Error: This script must be run as root or with sudo." >&2
  exit 1
fi

INSTALL_DOCKER="${INSTALL_DOCKER:-yes}"
NEW_USER="${NEW_USER:-deploy}"
DOCKER_DEFAULT_LOG_ROTATION="${DOCKER_DEFAULT_LOG_ROTATION:-yes}"

if [[ "$INSTALL_DOCKER" != "yes" ]]; then
  echo "--> Docker installation skipped by configuration."
  exit 0
fi

if command -v docker &>/dev/null && docker compose version &>/dev/null; then
  echo "--> Docker is already installed:"
  docker --version
  docker compose version
else
  echo "--> Setting up Docker official repository..."
  
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y
  apt-get install -y ca-certificates curl gnupg

  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor --yes -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg

  # Determine distro (Ubuntu or Debian)
  distro_id="$(grep -oP '(?<=^ID=).+' /etc/os-release | tr -d '\"' || echo 'ubuntu')"
  distro_codename="$(grep -oP '(?<=^VERSION_CODENAME=).+' /etc/os-release | tr -d '\"' || lsb_release -cs 2>/dev/null || echo 'noble')"

  if [[ "$distro_id" != "ubuntu" ]] && [[ "$distro_id" != "debian" ]]; then
    distro_id="ubuntu"
  fi

  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/$distro_id \
    $distro_codename stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

  apt-get update -y
  echo "--> Installing Docker packages..."
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

  systemctl enable docker
  systemctl start docker
fi

# Configure production daemon.json if enabled
if [[ "$DOCKER_DEFAULT_LOG_ROTATION" == "yes" ]]; then
  echo "--> Configuring production /etc/docker/daemon.json..."
  mkdir -p /etc/docker
  if [[ ! -f /etc/docker/daemon.json ]]; then
    cat <<EOF > /etc/docker/daemon.json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "live-restore": true
}
EOF
    systemctl reload docker 2>/dev/null || systemctl restart docker 2>/dev/null || true
  fi
fi

# Add user to docker group
if id "$NEW_USER" &>/dev/null; then
  echo "--> Adding user '$NEW_USER' to 'docker' group..."
  usermod -aG docker "$NEW_USER"
fi

echo "--> Docker setup verified successfully."
