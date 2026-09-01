# 🛡️ Headscale (Self-Hosted Tailscale Control Server)

Servidor de control autoalojado de código abierto para **Tailscale**, compatible con todos los clientes oficiales (Android, iOS, Windows, macOS, Linux).

---

## 🌟 Características

* **Multi-Origen:** Conexión desde cualquier dispositivo usando la app oficial de Tailscale.
* **Multi-Destino:** Puente hacia tu red doméstica, red del trabajo, túneles a contenedores con VPN o salida a internet por el VPS.
* **Multi-Modo:**
  * **Modo 1 (Split-Tunnel):** Acceso transparente a servicios privados (VNC `8444`, SSH, DBs) sin alterar tu tráfico de internet.
  * **Modo 2 (Subnet Routing):** Acceso a subredes LAN completas (ej: `192.168.1.0/24` o `10.0.0.0/8`).
  * **Modo 3 (Full-Tunnel / Exit Node):** Desvío total del tráfico para navegar de forma segura por el nodo que elijas.
* **MagicDNS:** Nombres de dominio amigables para cada dispositivo (ej: `jeisson-laptop.vpn.jeisson.top`).
* **DERP Server Embebido:** Conexión garantizada incluso detrás de firewalls restrictivos o CGNAT.
* **Headscale-UI:** Panel web para visualizar nodos, generar claves y verificar rutas.

---

## 🚀 Despliegue del Servidor

```bash
cd headscale
./scripts/start.sh
```

---

## 📲 Conectar Dispositivos (Clientes)

### 1. En Linux / Servidores
```bash
# Registrarse con el servidor privado
sudo tailscale up --login-server https://headscale.jeisson.top --accept-routes
```

### 2. En Windows / macOS
1. Abre la terminal / PowerShell.
2. Ejecuta:
   ```powershell
   tailscale login --login-server https://headscale.jeisson.top
   ```
3. O en la aplicación gráfica, presiona `Ctrl + Shift` mientras haces clic en el icono de Tailscale -> **Change Server** -> escribe `https://headscale.jeisson.top`.

### 3. En Android / iOS
1. Abre la app oficial de Tailscale.
2. Toca el menú de 3 puntos en la esquina superior derecha.
3. Toca **Use Custom Server** (o Cambiar Servidor).
4. Escribe: `https://headscale.jeisson.top`.
5. Pulsa **Log in** y autoriza el dispositivo con la URL que te muestre la pantalla.

---

## 🔑 Gestión Rápida de Claves y Nodos

```bash
# Ver estado, usuarios y nodos conectados
./scripts/status.sh

# Crear una llave de pre-autenticación para registrar equipos sin aprobación manual
./scripts/preauthkey.sh jeisson 30d reusable

# Registrar nodo con pre-auth key en 1 solo comando:
tailscale up --login-server https://headscale.jeisson.top --auth-key <tskey-auth-...> --accept-routes
```
