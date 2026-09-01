# 🌉 Headscale Node (Puente / Subnet Router / Exit Node)

Módulo portable y autónomo para convertir cualquier máquina en un **nodo puente** de la malla de Headscale.

---

## 🎯 Casos de Uso

### 🏠 Caso 1: Puente en tu Casa (Acceder a tu LAN doméstica o Navegar con tu IP de casa)
1. Coloca esta carpeta en tu PC de casa, Mini PC o Raspberry Pi.
2. Configura en `.env`:
   ```bash
   NODE_HOSTNAME=home-bridge
   ADVERTISE_ROUTES=192.168.1.0/24
   TS_EXTRA_ARGS=--advertise-exit-node --accept-routes
   ```
3. Ejecuta `./scripts/start.sh`.
4. **Resultado:**
   - Desde tu celular o laptop en cualquier lugar del mundo podrás acceder a tus dispositivos de casa (`192.168.1.x`).
   - O si activas "Use Exit Node" en la app de Tailscale, navegarás como si estuvieras sentado en tu casa.

---

### 🏢 Caso 2: Puente en tu Trabajo (Acceso a la red corporativa u oficinas)
1. Coloca esta carpeta en tu PC de la oficina o en un servidor local del trabajo.
2. Configura en `.env`:
   ```bash
   NODE_HOSTNAME=work-bridge
   ADVERTISE_ROUTES=10.0.0.0/16,172.16.0.0/16
   TS_EXTRA_ARGS=--accept-routes
   ```
3. Ejecuta `./scripts/start.sh`.
4. **Resultado:**
   - Podrás acceder a las bases de datos, servidores SSH y paneles internos del trabajo (`10.x.x.x`) desde tu casa o celular sin tener que activar software VPN corporativo intrusivo en tus dispositivos personales.

---

### 🔀 Caso 3: Puente a través de una VPN Corporativa (Sidecar)
Si tienes un contenedor que ya está conectado a una VPN de terceros (OpenVPN, Cisco AnyConnect, FortiClient):
1. Enlaza este contenedor a la red de ese contenedor (`network_mode: service:mi-vpn-corporativa`).
2. Publica la subred corporativa hacia tu red Headscale.

---

## 🚀 Despliegue

```bash
# 1. Copiar configuración
cp .env.example .env

# 2. Configurar TS_AUTHKEY generada en tu servidor Headscale:
#    (En el servidor VPS: ./scripts/preauthkey.sh)

# 3. Iniciar
./scripts/start.sh
```
