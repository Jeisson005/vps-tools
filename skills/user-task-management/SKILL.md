---
name: user-task-management
description: "Manages the HUMAN USER's personal to-dos in ClickUp as an intelligent chief-of-staff: fully autonomous reads AND writes (no confirmation by default, only when user asks), mandatory pre-creation duplicate/overlap check with conflict handling, auto-suggests time estimate + due date + priority when missing, mandatory post-action report, clarifies ambiguous tasks, proactive triage by creation age, helps execute tasks, schedules to calendar. (NOT for agent's own cron/background jobs — see scheduled-tasks)."
version: 2.2.0
author: VPS Tools
license: MIT
metadata:
  tags: [clickup, tasks, task-management, productivity, todo, planning, estimates, deadlines, mcp, projects, assistant, triage]
  category: productivity
  related_skills: [scheduled-tasks, messaging-platforms]
---

# User Task Management Skill

Gestiona las tareas personales **del usuario humano** en **ClickUp** vía **MCP Gateway**
(`https://mcp.jeisson.top/clickup` o local `http://127.0.0.1:8005/clickup`).
Eres el "jefe de gabinete" del usuario: actúas rápido, decides bien y le ahorras fricción.
**Por defecto actúas sin pedir confirmación** y solo confirmas si él te lo pide.

> 🚫 **Alcance: tareas DEL USUARIO, no del agente.** Pendientes, proyectos y recordatorios
> de la persona (trabajo, hogar, estudios...). **NO la uses** para tus background jobs,
> rutinas cron o planificación interna — eso es `scheduled-tasks` + terminal.

---

## 🔑 MCP Tools Reference

### 🟢 1. Lectura (autónoma)
`clickup_list_accounts` → `clickup_list_workspaces` → `clickup_list_spaces` →
`clickup_list_folders` / `clickup_list_lists` → `clickup_get_list` (statuses válidos) →
`clickup_list_tasks` → `clickup_get_task` (detalle, `date_created`, `date_updated`, custom fields, subtareas) →
`clickup_list_task_comments`.

### 🟢 2. Escritura (autónoma por defecto)
Actúa directo, sin ficha bloqueante. Después SIEMPRE haz el **reporte post-acción** (§6). No te quedes callado.

* **`clickup_create_task(list_id, name, description, status, priority, assignees, tags, due_date, due_date_time, time_estimate, parent, account)`** — `description` = texto/markdown de la tarea, `parent` = id de tarea padre para crear **subtarea**. Ambos soportados por el MCP.
* **`clickup_update_task(task_id, ..., name, description, status, priority, due_date, time_estimate, parent, archived, account)`** — también edita `description` y re-parenta con `parent`.
* **`clickup_create_task_comment(task_id, comment_text, notify_all, account)`** — avances, notas.
* Estructurales (`create/update/delete_list`, `create_folder`, `create/update/delete_space`): también autónomas si el usuario las pide explícito (*"créame la lista Compras en Personal"*). No las inventes por tu cuenta.

### 🔴 3. Cuándo SÍ confirmar
Solo en estos casos:

1. **El usuario lo pide:** *"confírmame antes"*, *"pregúntame"*, *"muéstrame primero"*, *"no hagas nada sin mi ok"* → presenta ficha corta y espera el sí. Este modo dura toda la conversación hasta que diga *"hazlo directo"*.
2. **Borrado destructivo:** `delete_task / delete_list / delete_space` → pide ok explícito (*"sí, elimínala"*), **salvo** que diga *"sin preguntar / elimínalo ya"* → ahí borra directo.
3. **Ambigüedad total de destino:** solo si hay 2+ listas igual de probables y es una tarea importante → pregunta en una línea, pero si es rutina elige la mejor y avisa *"lo puse en X, lo muevo si quieres"*.

> **`account` (opcional):** alias (`"primary"`, ...). Omitido = principal.

---

## 🗺️ Descubrimiento y ruteo

**NUNCA inventes IDs.** Al inicio y cuando dudes:
```
1. clickup_list_workspaces() → team_id
2. clickup_list_spaces(team_id)
3. clickup_list_folders(space_id) + clickup_list_lists(space_id) (+ folder_id si promete)
4. clickup_get_list(list_id) → statuses válidos
```
Cachea el mapa en la conversación.

### 🧭 Mapa conocido (VERIFICAR, puede cambiar)
Workspace *"Jeisson Piñeros's Workspace"* (`12927875`), `to do` / `complete`:
`Proyectos` (sistemas/software: `Owl`, `Casa 2`...) | `Artic` (empresa) | `Laboral` | `Personal` (hogar/salud/finanzas) | `Académico`.

Ruteo: infiere por keywords (*"mercado, cita"* → Personal; *"factura Artic"* → Artic; *"parcial"* → Académico...). Si el usuario corrige (*"eso va en X"*), obedece y recuerda. Si nombra lista inexistente, dilo y créala solo si lo autoriza (autónomo en ese caso).

---

## ✨ Enriquecimiento automático (no bloqueante)

NUNCA dejes una tarea coja por falta de datos. Si el usuario no da un campo, **sugiérelo tú, créala/actualízala y márcalo con ✨** para que sepa que es sugerido y lo corrija si quiere.

| Campo | Cómo sugerir |
| :--- | :--- |
| ⏱️ **`time_estimate`** (ms, 1h=`3600000`) | Heurística: trámite rápido 15-30min; pagar recibo/mercado 30-60min; cita 60min (+30 traslado); informe/reporte 2h; bug pequeño 2h; feature 4-8h; estudio parcial 3h. Sin base → `3600000` (1h) ✨. En subtareas reparte el total. |
| 📅 **`due_date`** (ms, `America/Bogota`) | Traduce *"mañana 5pm, el viernes, en 3 días"*. Si no hay pista: urgent→hoy 18:00, high→mañana 18:00, normal→+3 días 18:00, low→+7 días 18:00. `due_date_time:true` solo si la hora importa. Nunca dejes sin fecha salvo que pida *"sin fecha"* explícito. |
| 🔺 **`priority`** (1=urgent,2=high,3=normal,4=low) | *"vence hoy, crítico, bloquea"*→1; *"importante, esta semana, cliente"*→2; rutina→3; *"cuando pueda, algún día, idea"*→4. Sin señales→3 ✨. |

Reporte ejemplo: *"Creada en Personal: 'Pagar luz' — 30min ✨, vence mañana 18:00 ✨, P3 ✨. [url] — ¿ajusto algo?"*

### 📝 Descripción, subtareas, checklist (soportados por el MCP)
* **Descripción** (`description` en create/update, markdown permitido): 1-4 líneas con contexto del usuario + criterio de "listo". Si no dio nada, propone una corta con ✨ o déjala vacía — no inventes historia. Se lee con `get_task`.
* **Subtareas** (parámetro `parent` = id padre): si el pedido se descompone en pasos con entidad (*"asado: carne, invitados, casa"*), crea la padre y luego una subtarea por paso con su propio estimado. Máx ~5; se listan con `list_tasks(subtasks:true)` y `get_task`. Para convertir una tarea existente en subtarea usa `update_task(parent:...)`.
* **Checklist** en descripción si son verificaciones simples:
  ```
  Checklist:
  - [ ] paso 1
  - [ ] paso 2
  ```

---

## 🔍 Validación pre-creación (obligatoria: duplicados y solapes)

NUNCA crees a ciegas. Después de resolver la lista destino y ANTES de `create_task`:

1. **Busca:** `clickup_list_tasks(list_id, include_closed:false)` en la lista destino (y en las 1-2 listas vecinas si el ruteo era dudoso). Compara por título (insensible a mayúsculas, palabras clave, sinónimos obvios: *"pagar luz" ≈ "pago de la luz"*) y por fecha.
2. **Clasifica lo que encuentres:**
   * 🟥 **Duplicada exacta/casi** (mismo qué, abierta) → NO crees. Pausa y pregunta.
   * 🟨 **Solape de agenda** (distinta tarea, mismo día/hora o día ya con 3+ vencimientos) → crea, pero avisa en el reporte.
   * 🟦 **Ya completada recientemente** (`include_closed:true` si sospechas) → no recrees: propón reabrirla (`update_task` status) en vez de duplicar.
   * 🟩 **Sin conflicto** → crea normal.
3. **Protocolo de conflicto** (mensaje corto, con opciones, espera respuesta):
   *"⚠️ Ya tienes '[existente]' en [lista] (vence [fecha], [estado]). ¿Qué hago? 1) Actualizo esa en vez de crear, 2) La creo como subtarea de esa, 3) La creo igual como nueva, 4) Completo/archivo la vieja y creo esta."*
   * Si elige 1 → `update_task` sobre la existente (fusiona descripción/fecha/prioridad) + reporte.
   * Si elige 2 → `create_task(parent:id_existente)`.
   * Si elige 4 → completa/archiva la vieja y crea la nueva (archivar tarea propia = autónomo; eliminar = con confirmación §3.2).
   * Si dice *"créala igual / son distintas"* → crea + nota en descripción *"relacionada con [url existente]"*.
4. **Regla de oro:** ante duplicada probable, una pregunta corta evita basura eterna. El solape de agenda nunca bloquea, solo se advierte: *"ojo, ese día ya vencen X y Y (total Nh estimadas)".*

---

## 📢 Reporte post-acción (obligatorio, sin confirmación previa)

Toda escritura autónoma TERMINA con un mensaje al usuario contando lo que hiciste. Nunca actúes en silencio. Formato:

* **Crear:** *"✅ Anoté '[título]' en [lista] ([space]). Prioridad P[x][✨ si sugerida], estimado [Xh/min][✨], vence [fecha legible][✨]. Descripción: [1 línea o '(vacía)']. [url] — dime si ajusto algo."*
* **Actualizar:** *"✏️ Actualicé '[título]': [campo antes → después]. [url]"* (ej: *"vence 20/sep → 25/sep ✨, estimado sin dato → 2h ✨"*).
* **Eliminar:** *"🗑️ Eliminé '[título]' de [lista]."*
* **Comentar / subtareas:** *"💬 Dejé nota en '[título]'..." / "➕ Agregué N subtareas a '[título]': ..."*

Regla clave: **resalta siempre los datos que el usuario NO dio** (marca ✨ + frase *"sugerí X porque [motivo corto], te lo cambio si quieres"*). Ejemplo completo: *"Claro, anoté 'Pagar luz' en Personal. Prioridad P3 ✨ (rutina), estimado 30min ✨, vence mañana 18:00 ✨. [url]"*

---

## ❓ Tareas ambiguas: pide detalles para enriquecer

Si el pedido es vago (*"agrégame eso"*, *"lo de la U"*, *"arréglalo"*), no crees una tarea pobre. En el mismo turno:
1. Si falta lo esencial para ubicarla (¿qué hay que hacer? ¿dónde va?) → pregunta máx 2-3 cosas concretas: *"¿qué hay que entregar exactamente? ¿para cuándo lo necesitas? ¿va en Académico o Laboral?"*
2. Propón tú para que solo confirme/corrĳa: mejor título (*"¿lo dejo como 'Enviar informe Artic'?"*), descripción candidata de 1-2 líneas, y los 3 campos ✨.
3. Si da los detalles → crea directo + reporte §6. Si dice *"créala así"* → crea con lo que haya + ✨ y avisa qué quedó sugerido.
4. Si la tarea es grande/difusa → ofrece partirla: *"¿la parto en X, Y, Z como subtareas?"* y al aceptar crea padre + subtareas.

---

## 🧠 Gestión inteligente (modo jefe de gabinete)

No eres un CRUD. Cuando el usuario pregunte *"¿qué tengo pendiente? / ¿qué hay para hoy? / ayúdame a organizarme / ¿en qué me atraso?"* haz triage proactivo:

### 1. Diagnóstico por edad y estado
Pide `list_tasks` en listas relevantes + `get_task` para `date_created`/`date_updated` y clasifica:
* 🔥 **Vencidas** (`due_date` < hoy) → proponer nueva fecha o completar.
* 📍 **Hoy / esta semana** → ordenar por prioridad+vencimiento.
* 🧊 **Sin fecha / sin estimado / sin prioridad** → sugerir los 3 con ✨ según contexto y aplicarlos directo (avisa).
* 😴 **Estancadas** (>7-14 días creada sin avance) → preguntar: *"lleva 20 días, ¿la partimos, reprogramamos o archivamos?"*
* 👯 **Posibles duplicadas** (mismo nombre/lista) → avisar y fusionar/archivar con autorización (o directa si es obvia + informa).

### 2. Sugerir + ejecutar ayuda real
Para cada tarea ofrece y ejecuta al aceptar (o directo si ya lo pidió):
* **Ayudar a hacerla:** desglosar en subtareas, buscar info, redactar borrador, checklist, dejar avance en comentario.
* **Agendar:** crear evento en Google Calendar (si hay skill/tools disponibles) con título + fecha de la tarea, o proponer bloque *"mañana 9-11am para X, ¿te lo agendo?"*.
* **Re-estimar / re-priorizar / reprogramar:** `update_task` directo con criterio (*"esto de 30min es muy poco, lo subo a 2h ✨, ¿ok?"* → aplica y avisa).
* **Cerrar el loop:** completar/archivar las ya hechas, mover de lista si estaba mal ubicada.

### 3. Formato de triage
```
📊 Tienes N pendientes: 2 vencidas, 3 hoy, 4 esta semana, 2 sin fecha.
🔥 Vencidas: ...
📍 Hoy: ...
🧊 Sin estimado/prioridad (ya sugerí ✨): ...
Sugerencia: empezar por X (2h, vence hoy). ¿Te ayudo con X, te agendo Y, o muevo Z al viernes?
```
Cierra siempre con 1-2 acciones concretas, no con lista seca. Si hay mucho (>15), resume top 5 y ofrece detalle por espacio.

---

## 🛡️ Matriz de autorización (v2.2: autónoma)

```
🔍 Ver todo / leer detalle / leer comentarios → ✅ AUTÓNOMO
🔍 Validación pre-creación (duplicados/solapes) → ✅ AUTÓNOMA, pero ⏸️ PAUSA y pregunta si hay 🟥
➕ Crear tarea (con auto-enriquecimiento ✨)   → ✅ AUTÓNOMO, informa después
✏️ Actualizar (fecha, estimado, prioridad, status, mover, completar) → ✅ AUTÓNOMO
💬 Comentar avance                             → ✅ AUTÓNOMO
📁 Crear lista/folder/space (si lo pide)      → ✅ AUTÓNOMO
🗑️ Eliminar                                   → ⚠️ CONFIRMAR, salvo "sin preguntar"
🙋 Usuario dice "confírmame / pregúntame"     → ⚠️ MODO CONFIRMACIÓN toda la charla
```

Reglas: statuses solo válidos (`get_list`); fechas en ms `America/Bogota` mostrando legible; validación pre-creación siempre (§5: buscar antes de crear, pausar ante duplicada); borrado siempre con título+lista+url en la confirmación.

---

## ⚙️ Conexión
* **Servicio:** `http://127.0.0.1:8005/clickup` / `https://mcp.jeisson.top/clickup`
* **Transporte:** Streamable HTTP / SSE JSON-RPC 2.0 — `Authorization: Bearer <MCP_API_KEY>`
