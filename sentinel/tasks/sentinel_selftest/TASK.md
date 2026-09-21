# Autoprueba Diaria Sentinel (`sentinel_selftest`)

## Objetivo
Verificar cada madrugada (00:00) que el motor Sentinel está operativo de punta
a punta, con énfasis en el uso de IA con la configuración **viva de Hermes**
(credencial, modelo y endpoint leídos en cada ejecución, sin copias).

## Qué comprueba (en orden)
1. `hermes_config` — `.env` + `config.yaml` de Hermes legibles y completos.
2. `models_endpoint` — `GET {base_url}/models` responde con catálogo no vacío.
3. `chat_e2e` — `POST {base_url}/chat/completions` responde `OK`.
4. `classifier_referee` — el referee IA del clasificador devuelve categoría válida.
5. `healer_e2e` — `opencode run` headless con provider dedicado `sentinel-hermes`
   (credencial viva de Hermes, servidor privado) responde `OK`.
6. `telegram_urgent` — el bot rojo responde `getMe` (sin enviar mensajes).
7. `cron_wiring` — la tarea está registrada en `sentinel.tab` y sincronizada.
8. `sentinel_api` — `GET /health` del API local responde 200.
9. `disk` — uso de disco raíz por debajo del 95%.

## Criterio de éxito
Exit 0 y todas las comprobaciones en `OK`. No envía Telegram en éxito
(para no hacer ruido).

## Si falla
Envía un mensaje por el bot urgente (rojo) con la lista de fallos y sale 1;
el runner de Sentinel lo clasifica y, si es reparable, intenta auto-reparar.
