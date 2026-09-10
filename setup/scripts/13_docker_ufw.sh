#!/usr/bin/env bash
# ==============================================================================
# [13/13] Docker <-> UFW hardening (DOCKER-USER allowlist)
#
# PROBLEM: Docker publishes ports with its own iptables rules (chain DOCKER-USER
# -> DOCKER-FORWARD -> DOCKER) that are evaluated BEFORE UFW's chains. So a
# container published as "0.0.0.0:PORT" is reachable from the Internet even with
# UFW default-deny. (This is how an exposed MariaDB on :3306 got dropped in the
# 2026-09 incident.)
#
# FIX: put an allowlist in the DOCKER-USER chain (which Docker evaluates first
# and preserves across restarts), so published ports are DENIED by default and
# only the intended public ones pass. The rules are (re)applied by a systemd
# unit after docker.service on every boot.
#
# Usage:
#   sudo bash scripts/13_docker_ufw.sh            # install + apply (idempotent)
#   sudo bash scripts/13_docker_ufw.sh status     # show current DOCKER-USER
#   sudo bash scripts/13_docker_ufw.sh uninstall  # remove rules + unit
#
# Config (env or setup/.env):
#   DOCKER_UFW_HARDEN=yes|no          (default yes)
#   DOCKER_PUBLIC_TCP_PORTS="80 443 21115:21119"
#   DOCKER_PUBLIC_UDP_PORTS="21116"
#   These are PUBLISHED host ports (the left side of "HOST:CONTAINER"), matching
#   UFW's semantics. "a:b" ranges are supported.
# ==============================================================================

set -euo pipefail

CHAIN="DOCKER-USER"
APPLIER="/usr/local/sbin/docker-ufw-apply"
UNIT="/etc/systemd/system/docker-ufw.service"
DEFAULTS="/etc/default/docker-ufw"

DOCKER_UFW_HARDEN="${DOCKER_UFW_HARDEN:-yes}"
DOCKER_PUBLIC_TCP_PORTS="${DOCKER_PUBLIC_TCP_PORTS:-80 443 21115:21119}"
DOCKER_PUBLIC_UDP_PORTS="${DOCKER_PUBLIC_UDP_PORTS:-21116}"

if [[ $EUID -ne 0 ]]; then
  echo "Error: This script must be run as root or with sudo." >&2
  exit 1
fi

require_root() {
  if [[ $EUID -ne 0 ]]; then
    echo "Error: This script must be run as root or with sudo." >&2
    exit 1
  fi
}

show_status() {
  echo "==> DOCKER-USER chain:"
  iptables -L "${CHAIN}" -n --line-numbers 2>/dev/null || echo "(chain not found)"
  echo ""
  echo "==> docker-ufw.service:"
  systemctl status docker-ufw.service --no-pager 2>/dev/null | head -12 || true
}

uninstall() {
  echo "--> Disabling docker-ufw.service..."
  systemctl disable --now docker-ufw.service >/dev/null 2>&1 || true
  rm -f "${UNIT}" "${APPLIER}" "${DEFAULTS}"
  systemctl daemon-reload
  if iptables -L "${CHAIN}" -n >/dev/null 2>&1; then
    echo "--> Flushing ${CHAIN}..."
    iptables -F "${CHAIN}"
  fi
  echo "--> Uninstalled. NOTE: Docker ports are now UNFILTERED (UFW bypassed) again."
}

case "${1:-install}" in
  status)
    require_root
    show_status
    exit 0
    ;;
  uninstall)
    require_root
    uninstall
    exit 0
    ;;
esac

if [[ "${DOCKER_UFW_HARDEN}" != "yes" ]]; then
  echo "--> Docker/UFW hardening skipped by configuration (DOCKER_UFW_HARDEN=${DOCKER_UFW_HARDEN})."
  exit 0
fi

echo "==> [13/13] Hardening Docker <-> UFW (DOCKER-USER allowlist)..."
echo "    Public container ports -> tcp: ${DOCKER_PUBLIC_TCP_PORTS:-none} | udp: ${DOCKER_PUBLIC_UDP_PORTS:-none}"

# ---------------------------------------------------------------------------
# 1) The applier (sourced env from /etc/default/docker-ufw, with defaults)
# ---------------------------------------------------------------------------
cat > "${APPLIER}" <<'APPLIER_EOF'
#!/usr/bin/env bash
# Managed by vps-tools setup/scripts/13_docker_ufw.sh — do not edit by hand.
set -euo pipefail
CHAIN="DOCKER-USER"
TCP_PORTS="${DOCKER_PUBLIC_TCP_PORTS:-80 443 21115:21119}"
UDP_PORTS="${DOCKER_PUBLIC_UDP_PORTS:-21116}"

# Wait for Docker to create the chain (it is created at daemon start).
for _ in $(seq 1 30); do
  iptables -L "${CHAIN}" -n >/dev/null 2>&1 && break
  sleep 1
done
# Ensure the chain exists and is hooked from FORWARD.
iptables -N "${CHAIN}" 2>/dev/null || true
iptables -C FORWARD -j "${CHAIN}" 2>/dev/null || iptables -I FORWARD 1 -j "${CHAIN}"

# Rebuild the policy from scratch (idempotent).
iptables -F "${CHAIN}"

# (1) Allow replies of already-established connections.
iptables -A "${CHAIN}" -m conntrack --ctstate RELATED,ESTABLISHED -j RETURN

# (2) Allow internal sources: Docker networks, LAN and Tailscale CGNAT.
for net in 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 100.64.0.0/10; do
  iptables -A "${CHAIN}" -s "${net}" -j RETURN
done

# (3) Allow the intended public PUBLISHED ports. We match the ORIGINAL
#     (pre-DNAT) destination port via conntrack, so a random host port mapped to
#     a common container port (e.g. 39999:80) is NOT implicitly allowed.
for p in ${TCP_PORTS}; do
  iptables -A "${CHAIN}" -p tcp -m conntrack --ctorigdstport "${p}" -j RETURN
done
for p in ${UDP_PORTS}; do
  iptables -A "${CHAIN}" -p udp -m conntrack --ctorigdstport "${p}" -j RETURN
done

# (4) Deny everything else published by Docker (closes the UFW bypass).
iptables -A "${CHAIN}" -j DROP

echo "[docker-ufw] DOCKER-USER applied: public tcp='${TCP_PORTS}' udp='${UDP_PORTS}'; rest DROP"
APPLIER_EOF
chmod 0755 "${APPLIER}"

# ---------------------------------------------------------------------------
# 2) Persist config overrides
# ---------------------------------------------------------------------------
cat > "${DEFAULTS}" <<EOF
# Managed by vps-tools 13_docker_ufw.sh
DOCKER_PUBLIC_TCP_PORTS="${DOCKER_PUBLIC_TCP_PORTS}"
DOCKER_PUBLIC_UDP_PORTS="${DOCKER_PUBLIC_UDP_PORTS}"
EOF
chmod 0644 "${DEFAULTS}"

# ---------------------------------------------------------------------------
# 3) systemd unit (re-apply after Docker on every boot / docker restart)
# ---------------------------------------------------------------------------
cat > "${UNIT}" <<'UNIT_EOF'
[Unit]
Description=Apply UFW-style allowlist to Docker's DOCKER-USER chain
Documentation=file:/usr/local/sbin/docker-ufw-apply
After=docker.service network-online.target
Wants=network-online.target
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
EnvironmentFile=-/etc/default/docker-ufw
ExecStart=/usr/local/sbin/docker-ufw-apply
ExecReload=/usr/local/sbin/docker-ufw-apply

[Install]
WantedBy=multi-user.target
UNIT_EOF

systemctl daemon-reload
systemctl enable docker-ufw.service >/dev/null 2>&1 || true
systemctl restart docker-ufw.service

echo "--> Applied. Current ${CHAIN} policy:"
iptables -L "${CHAIN}" -n --line-numbers

echo ""
echo "--> Summary: published Docker ports are now DENIED by default;"
echo "    only tcp '${DOCKER_PUBLIC_TCP_PORTS}' and udp '${DOCKER_PUBLIC_UDP_PORTS}' are reachable."
echo "    Change ports in ${DEFAULTS} and run: sudo systemctl reload docker-ufw.service"
