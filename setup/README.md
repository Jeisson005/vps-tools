# VPS Initial Setup & Hardening

Modular suite to provision, secure, and optimize a brand new Linux VPS (Ubuntu/Debian/Contabo/Hetzner/DigitalOcean/AWS) and prepare it for production with Docker.

---

## Features & Modules

| Script | Purpose |
| :--- | :--- |
| **`01_system_packages.sh`** | Updates package indices and installs essential diagnostic/system utilities (`curl`, `git`, `htop`, `jq`, `ufw`, `fail2ban`, etc.). |
| **`02_create_user.sh`** | Creates a dedicated non-root administrative user (`deploy`), configures `sudo` privileges, and sets up SSH keys. |
| **`03_ssh_hardening.sh`** | Hardens SSH configuration (disables password login once keys exist, limits auth tries, prevents root login) with anti-lockout safety checks. |
| **`04_ufw_firewall.sh`** | Applies a strict firewall policy (`deny incoming`, `allow outgoing`) allowing SSH, HTTP (80), HTTPS (443), and custom ports. |
| **`05_fail2ban.sh`** | Configures Fail2ban with an active SSH jail to block brute-force attacks. |
| **`06_timezone_swap.sh`** | Sets system timezone (default: `America/Bogota`) and creates an optimized Swapfile (`4G`, `swappiness=10`) to prevent OOM errors. |
| **`07_security_upgrades.sh`**| Configures `unattended-upgrades` to automatically install critical security patches. |
| **`08_journald_tuning.sh`** | Limits `systemd-journald` size to `500M` and 30 days retention to avoid disk saturation. |
| **`09_clean_motd.sh`** | Suppresses Contabo/Ubuntu ESM promotional text and sets up a clean, dynamic status dashboard with system metrics. |
| **`10_sysctl_bbr.sh`** | Enables Google BBR TCP congestion control and optimizes kernel file descriptor / connection limits. |
| **`11_docker_install.sh`** | Installs official Docker Engine and Docker Compose v2 plugin and adds user to the `docker` group. |
| **`12_passwordless_sudo.sh`** | Configures passwordless sudo for a specified administrative user with syntax validation via `visudo`. |

---

## Getting Started

### 1. Quick Setup on a Fresh VPS

Clone this repository or transfer the `setup` folder to your new server:

```bash
git clone https://github.com/Jeisson005/vps-tools.git
cd vps-tools/setup
```

### 2. Configure Environment (Optional)

Copy the configuration template and tweak variables if desired:

```bash
cp .env.example .env
nano .env
```

Available options in `.env`:
- `NEW_USER`: Administrative username (default: `deploy`).
- `NEW_USER_SSH_KEY`: Public key string to inject into `authorized_keys`.
- `SSH_PORT`: Custom SSH port (default: `22`).
- `UFW_EXTRA_PORTS`: Additional ports to allow through firewall (e.g., `"80 443"`).
- `TIMEZONE`: System timezone (e.g., `UTC` or `America/Bogota`).
- `SWAP_SIZE`: Size of swap file (default: `4G`).
- `INSTALL_DOCKER`: Set to `yes` (default) to install Docker Engine.

### 3. Run the Provisioning Suite

#### Option A: Full Automated Run (Non-interactive)
```bash
sudo ./setup.sh --all
```

#### Option B: Interactive Menu
```bash
sudo ./setup.sh
```
Allows executing all steps in sequence or running individual steps one by one.

---

## Important Safety Note

> [!CAUTION]
> **Always verify your SSH connection in a new terminal window BEFORE closing your current root session:**
> ```bash
> ssh deploy@<YOUR_SERVER_IP> -p 22
> ```
> Ensure you can log in with your SSH key and execute `sudo -i` without issues.
