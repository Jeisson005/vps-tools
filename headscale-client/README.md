# 🚀 Headscale Linux Client & Network Diagnostic Suite

Herramienta integral para gestionar el cliente Tailscale/Headscale en Linux, alternar en 1 clic entre **Modo Directo (Mesh)** y **Modo Full (Exit Node por VPS)**, y diagnosticar bloqueos de red, DNS o inspección profunda de paquetes (DPI/SNI).

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
│   ├── vpn.sh                  # Gestor CLI de la VPN (up, down, status, mode full/direct)
│   └── diagnose.sh             # Motor CLI de diagnóstico en 4 capas (DNS, TCP, TLS, HTTP)
└── web/
    ├── app.py                  # API FastAPI para control y diagnósticos asíncronos
    └── static/
        └── index.html          # Dashboard visual sobrio (Zinc Theme)
```

---

## ⚙️ 1. Configuración Inicial

1. Copia el archivo de entorno:
   ```bash
   cp .env.example .env
   ```
2. *(Opcional)* Si deseas agregar dominios privados o empresariales para monitorear sin subirlos a Git:
   ```bash
   cp domains.custom.txt.example domains.custom.txt
   echo "mi-empresa.internal.com|Portal Corporativo|Trabajo" >> domains.custom.txt
   ```

---

## 💻 2. Uso mediante CLI (Terminal)

El script `scripts/vpn.sh` te permite controlar tu VPN rápidamente:

| Comando | Descripción |
|---|---|
| `./scripts/vpn.sh status` | Ver estado actual, IP VPN, Exit Node activo y lista de peers. |
| `./scripts/vpn.sh up` | Conectar Tailscale al servidor Headscale con tu llave. |
| `./scripts/vpn.sh down` | Desconectar Tailscale de forma segura. |
| `./scripts/vpn.sh mode full` | **Modo Full:** Todo tu tráfico de internet sale cifrado por el VPS (`100.64.0.4`). |
| `./scripts/vpn.sh mode direct` | **Modo Directo:** Tu tráfico sale directo por tu ISP; solo la VPN va al VPS. |
| `./scripts/vpn.sh switch` | Alternar entre Modo Full y Modo Directo en 1 comando. |
| `./scripts/vpn.sh ping` | Probar latencia contra el servidor VPS (`100.64.0.4`). |

### 🔍 Diagnóstico Rápido por Terminal:
```bash
# Diagnosticar todos los dominios por categorías
./scripts/diagnose.sh

# Filtrar por categoría (ej: Streaming, Mensajería, Redes Sociales)
./scripts/diagnose.sh --category Streaming

# Probar un dominio individual específico
./scripts/diagnose.sh xvideos.com
```

---

## 🌐 3. Panel de Administración Web Local (Docker Compose)

Puedes levantar el dashboard web en tu laptop para tener interfaz gráfica y botones de 1 clic:

1. **Iniciar el panel local:**
   ```bash
   docker compose up -d --build
   ```
2. **Abrir en tu navegador:**
   👉 **`http://localhost:29485`**

### ✨ Funciones del Panel:
* **Estado en Vivo:** Indicador en tiempo real de conexión, IP asignada y nodo de salida.
* **1-Click Mode Switch:** Botones para cambiar entre *Modo Directo* y *Modo Full (VPS)* al instante.
* **Diagnóstico Visual:** Barras de progreso, filtros interactivos por categorías y pruebas instantáneas de dominios personalizados.
