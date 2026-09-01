# 🚀 Headscale Linux Client & Network Diagnostic Suite

Herramienta integral para gestionar el cliente Tailscale/Headscale en Linux, alternar en 1 clic entre **Modo Malla (Mesh)** y **Túnel Completo (Exit Node por VPS)**, gestionar el **Proxy SOCKS5/HTTP nativo** para split tunneling por extensión de navegador, y diagnosticar bloqueos de red o DPI.

---

## 📁 Estructura del Módulo

```text
headscale-client/
├── .env.example                # Variables de configuración (servidor, llaves, exit node)
├── domains.default.txt         # Dataset base de dominios por categoría
├── domains.custom.txt.example  # Plantilla para tus dominios privados (no trackeado en git)
├── docker-compose.yml          # Despliegue del panel web local
├── Dockerfile                  # Contenedor con herramientas de red y diagnóstico
├── scripts/
│   ├── vpn.sh                  # Gestor CLI de VPN, modos, proxy y arranque
│   └── diagnose.sh             # Motor CLI de diagnóstico en 4 capas (DNS, TCP, TLS, HTTP)
└── web/
    ├── app.py                  # API FastAPI para control, proxy y diagnósticos
    └── static/
        └── index.html          # Dashboard visual con 3 pestañas (Zinc Theme)
```

---

## ⚙️ 1. Configuración Inicial

1. Copia el archivo de entorno:
   ```bash
   cp .env.example .env
   ```
2. *(Opcional)* Si deseas agregar dominios privados o empresariales para diagnosticar sin subirlos a Git:
   ```bash
   cp domains.custom.txt.example domains.custom.txt
   echo "mi-empresa.internal.com|Portal Corporativo|Trabajo" >> domains.custom.txt
   ```

---

## 💻 2. Uso mediante CLI (Terminal)

El script `scripts/vpn.sh` te permite controlar todas las facetas de tu VPN:

### 🌐 Conexión y Enrutamiento:
| Comando | Descripción |
|---|---|
| `./scripts/vpn.sh status` | Ver estado actual, IP VPN, Exit Node activo, Proxy, Inicio automático y Peers. |
| `./scripts/vpn.sh up` | Conectar Tailscale al servidor Headscale con tu llave. |
| `./scripts/vpn.sh down` | Desconectar Tailscale. |
| `./scripts/vpn.sh mode mesh` | **Modo Malla (Mesh):** Red privada entre tus equipos; internet general sale directo por tu ISP. |
| `./scripts/vpn.sh mode full [IP]` | **Túnel Completo:** Todo tu tráfico de internet sale cifrado por el Exit Node (`100.64.0.4`). |
| `./scripts/vpn.sh switch` | Alternar entre Modo Malla y Túnel Completo en 1 comando. |

### ⚡ Proxy y Sistema:
| Comando | Descripción |
|---|---|
| `./scripts/vpn.sh proxy enable` | Activar el Proxy nativo de Tailscale (`SOCKS5: 127.0.0.1:1080` / `HTTP: 127.0.0.1:8080`). |
| `./scripts/vpn.sh proxy disable` | Desactivar el Proxy nativo. |
| `./scripts/vpn.sh proxy status` | Ver si el proxy local está escuchando. |
| `./scripts/vpn.sh autostart enable` | Habilitar que Tailscale inicie automáticamente al arrancar la laptop. |
| `./scripts/vpn.sh autostart disable` | Deshabilitar inicio automático. |

### 🔍 Diagnóstico de Red & Bloqueos:
```bash
# Diagnosticar todos los dominios
./scripts/diagnose.sh

# Filtrar por categoría (ej: Streaming, Mensajería, IA & Dev, Adulto)
./scripts/diagnose.sh --category "IA & Dev"

# Probar un dominio individual específico
./scripts/diagnose.sh netflix.com
```

---

## 🌐 3. Panel Web Local en tu Laptop (3 Pestañas)

Abre en tu navegador:
👉 **[http://localhost:29485](http://localhost:29485)**

### 📑 Pestañas del Panel:
1. 🌐 **Control & Malla VPN:**
   * Estado de conexión en tiempo real, IP VPN y lista de dispositivos en la malla (Peers).
   * Selector dinámico de Exit Node y cambio en 1 clic entre **Modo Malla** y **Túnel Completo**.
   * Botones de Conectar / Desconectar.
2. ⚡ **Proxy Integrado (SOCKS5/HTTP):**
   * Control de encendido/apagado del Proxy nativo de Tailscale en `127.0.0.1:1080`.
   * Guía visual para configurar extensiones de navegador (*ZeroOmega / Proxy SwitchyOmega / FoxyProxy*).
3. 🔍 **Diagnóstico de Red & Bloqueos:**
   * Motor de inspección profunda en 4 capas (**DNS $\rightarrow$ TCP $\rightarrow$ TLS/SNI $\rightarrow$ HTTP**).
   * Filtros por categoría, barra de progreso y evaluación de dominios personalizados.
