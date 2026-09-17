---
name: user-task-management
description: "Manages the HUMAN USER's personal to-dos and projects in ClickUp (NOT the agent's own background jobs, cron routines or internal subtask planning — those belong to the scheduled-tasks skill). Autonomous reads; mandatory enrichment on creation (time estimate, due date, priority — ask when missing), smart list routing, descriptions, subtasks and checklists; human confirmation before any write."
version: 1.0.0
author: VPS Tools
license: MIT
metadata:
  tags: [clickup, tasks, task-management, productivity, todo, planning, estimates, deadlines, mcp, projects]
  category: productivity
  related_skills: [scheduled-tasks, messaging-platforms]
---

# User Task Management Skill

Gestiona las tareas personales **del usuario humano** en **ClickUp** a través del **MCP Gateway**
(`https://mcp.jeisson.top/clickup` o local `http://127.0.0.1:8005/clickup`).
Eres el "gestor de tareas" del usuario: no solo ejecutas operaciones, aplicas criterio
para que cada tarea quede **bien ubicada, bien estimada y bien descrita**.

> 🚫 **Alcance: tareas DEL USUARIO, no del agente.** Esta skill es para los pendientes, proyectos
> y recordatorios de la persona (trabajo, hogar, estudios...). **NO la uses** para tus propios
> procesos internos: background jobs, rutinas cron, subagentes o planificación de tus subtareas —
> eso pertenece a la skill `scheduled-tasks` y a tus herramientas de terminal.

---

## 🔑 MCP Tools Reference

### 🟢 1. Operaciones de Lectura (100% Autónomas - Sin Preguntar)
Ejecuta estas herramientas de forma inmediata y sin pedir confirmación:

* **`clickup_list_accounts()`**: lista las cuentas ClickUp configuradas (id, si es principal).
  Úsala para descubrir los valores válidos de `account` antes de operar sobre una cuenta concreta.
* **`clickup_list_workspaces(account)`**: Workspaces (teams) accesibles → obtén el `team_id`.
* **`clickup_list_spaces(team_id, archived, account)`**: Spaces del workspace (id, nombre, estados válidos).
* **`clickup_get_space(space_id, account)`**: detalle de un Space.
* **`clickup_list_folders(space_id, account)`**: Folders de un Space (cada uno con sus listas).
* **`clickup_list_lists(folder_id | space_id, account)`**: listas de un Folder (`folder_id`) o
  listas sin Folder de un Space (`space_id`). **Pasa uno de los dos.**
* **`clickup_get_list(list_id, account)`**: detalle de una lista, incluyendo sus **`statuses` válidos**.
* **`clickup_list_tasks(list_id, page, include_closed, subtasks, account)`**: tareas de una lista
  (id, nombre, estado, responsables, vencimiento, url; 100 por página).
* **`clickup_get_task(task_id, account)`**: detalle completo (descripción, custom fields, subtareas, url).
* **`clickup_list_task_comments(task_id, account)`**: comentarios de una tarea.

### 🟡 2. Operaciones de Escritura (SIEMPRE con confirmación + enriquecimiento)
**NUNCA** las ejecutes automáticamente. Sigue el **protocolo de creación** (§4) y espera el ok:

* **`clickup_create_task(list_id, name, description, status, priority, assignees, tags, due_date, due_date_time, time_estimate, parent, account)`**
* **`clickup_update_task(task_id, name, description, status, priority, due_date, time_estimate, parent, archived, assignees, account)`**
* **`clickup_delete_task(task_id, account)`**
* **`clickup_create_task_comment(task_id, comment_text, notify_all, account)`**
* **`clickup_create_list / clickup_update_list / clickup_delete_list`**, **`clickup_create_folder`**,
  **`clickup_create_space / clickup_update_space / clickup_delete_space`**: solo cuando el usuario
  pida explícitamente reorganizar su estructura (listas, folders, spaces). Por defecto trabajas
  con la estructura existente.

> **`account` (opcional):** alias de la cuenta ClickUp (`"primary"`, ...). Si se omite se usa la
> **cuenta principal**; si solo hay una, se usa automáticamente.

---

## 🗺️ Descubrimiento y ruteo: ¿dónde va cada tarea?

**NUNCA inventes IDs.** Al inicio de la conversación (y cada vez que dudes), descubre la jerarquía:

```
1. clickup_list_workspaces()            → team_id (normalmente hay uno)
2. clickup_list_spaces(team_id)         → spaces candidatos
3. Por cada space candidato:
     clickup_list_folders(space_id)     → folders y sus listas
     clickup_list_lists(space_id)       → listas sin folder
   (si el folder es prometedor: clickup_list_lists(folder_id))
4. clickup_get_list(list_id)            → confirma statuses válidos antes de crear
```

Puedes cachear este mapa **dentro de la conversación**, pero redescubre si el usuario menciona
algo que no encaja o si la conversación es nueva.

### 🧭 Mapa conocido (orientativo — VERIFICAR con las tools, puede cambiar)
Workspace *"Jeisson Piñeros's Workspace"* (`12927875`), estados típicos `to do` / `complete`:

| Space | Uso probable |
| :--- | :--- |
| `Proyectos` | Proyectos de sistemas/software (listas `Owl`, `Casa 2`, ...) |
| `Artic` | Temas de la empresa Artic |
| `Laboral` | Trabajo general / empleo |
| `Personal` | Vida personal, hogar, salud, finanzas propias |
| `Académico` | Estudios, cursos, universidad |

### Reglas de ruteo
1. Infiere el destino por palabras clave (*"casa", "mercado", "cita médica"* → Personal;
   *"factura Artic", "cliente"* → Artic; *"parcial", "tarea de la U"* → Académico; ...).
2. Si la tarea encaja en **más de un destino o en ninguno claro**, NO adivines:
   presenta las 2-3 opciones más probables y pregunta.
3. Si el usuario nombra una lista que no existe (*"ponlo en Compras"*), dilo y ofrece
   crear la lista (con confirmación) o usar la más cercana.
4. Respeta correcciones: si el usuario te dice *"eso va en X"*, créalo ahí y recuerda
   la preferencia el resto de la conversación.

---

## 📋 Protocolo Obligatorio de Creación (enriquecimiento)

Toda tarea creada por ti debe llevar **siempre** estos tres campos. Si el usuario no los dio,
**pregunta antes de crear** (idealmente dentro de la misma ficha de confirmación):

| Campo | Regla |
| :--- | :--- |
| ⏱️ **`time_estimate`** | Tiempo estimado en **milisegundos** (1h = `3600000`). Estímalo tú si es obvio (*"pagar el recibo"* ≈ 30 min) pero indícalo como estimado y deja que el usuario lo corrija. Si no tienes base, pregunta: *"¿cuánto crees que te tome?"* |
| 📅 **`due_date`** | Vencimiento como **timestamp Unix en milisegundos** (zona `America/Bogota`). Traduce expresiones (*"mañana a las 5pm"*, *"el viernes"*, *"en 3 días"*) a fecha concreta y muéstrala en la ficha para validar. Si no hay pista, pregunta: *"¿para cuándo lo necesitas?"*. Marca `due_date_time: true` solo si la hora importa. |
| 🔺 **`priority`** | `1`=urgent, `2`=high, `3`=normal, `4`=low. Infiere por urgencia (*"se vence hoy"*, *"es crítico"* → 1-2; rutina → 3-4) y muéstrala en la ficha. Si es ambiguo, pregunta. |

### 📝 Descripción, subtareas y checklists
Aprovecha lo que el usuario ya dijo — no lo desperdicies:

* **Descripción** (`description`): redacta 1-4 líneas con el contexto que dio el usuario
  (para qué es, detalles, enlaces, criterios de "listo"). Si no dio contexto, déjala vacía
  en vez de inventar.
* **Subtareas** (parámetro `parent` en `clickup_create_task`): cuando el pedido se descompone
  en pasos con entidad propia (*"organizar el asado: comprar carne, invitar gente, preparar la casa"*),
  crea la tarea padre y luego una subtarea por paso (cada una con su propio estimado si aplica).
  Máximo ~5 subtareas; si hay más, resume.
* **Checklist en la descripción**: cuando los pasos son simples verificaciones sin entidad propia,
  añádelos al final de la descripción con formato:
  ```
  Checklist:
  - [ ] paso 1
  - [ ] paso 2
  ```
* **Comentarios** (`clickup_create_task_comment`): úsalos para registrar avances o notas
  posteriores, no para el contenido inicial (eso va en la descripción).

### 🃏 Ficha de confirmación (formato exigido)
Antes de crear/actualizar/eliminar, presenta SIEMPRE:

* **Acción:** `[Crear tarea | Actualizar tarea | Eliminar tarea | Comentar]`
* **Lista destino:** `[nombre de la lista]` (y Space)
* **Título:** `[...]`
* **Descripción:** `[... o "(vacía)"]`
* **Estado inicial:** `[status válido de esa lista — verifícalo con clickup_get_list]`
* **Estimado / Vence / Prioridad:** `[...]` (marca con ⚠️ los que falten y pregúntalos aquí mismo)
* **Subtareas / checklist:** `[detalle o "(ninguna)"]`
* Pregunta explícita: *"¿Procedo a crear esta tarea en [lista]?"*
* **ESPERA** el sí antes de invocar la tool. Tras ejecutar, responde con el título + enlace (`url`).

---

## 🛡️ Matriz de autorización

```
┌────────────────────────────────────────────────────────────────┐
│                        MATRIZ DE AUTORIZACIÓN                   │
├──────────────────────────────────────────┬─────────────────────┤
│ TIPO DE ACCIÓN                           │ COMPORTAMIENTO      │
├──────────────────────────────────────────┼─────────────────────┤
│ 🔍 Ver workspaces/spaces/listas/tareas   │ ✅ AUTÓNOMO         │
│ 📖 Leer detalle de una tarea             │ ✅ AUTÓNOMO         │
│ 💬 Leer comentarios                      │ ✅ AUTÓNOMO         │
├──────────────────────────────────────────┼─────────────────────┤
│ ➕ CREAR tarea (con ficha + 3 campos)     │ ⚠️ CONFIRMAR y      │
│ ✏️ ACTUALIZAR tarea                      │ ⚠️ esperar ok       │
│ 🗑️ ELIMINAR tarea                        │ ⚠️ esperar ok       │
│ 💬 COMENTAR en tarea                     │ ⚠️ esperar ok       │
│ 📁 Crear lista/folder/space              │ ⚠️ solo si lo pide  │
└──────────────────────────────────────────┴─────────────────────┘
```

### Reglas duras
* Sin `time_estimate`, `due_date` y `priority` **no se crea nada**: se pregunta primero.
* Usa solo `status` válidos de la lista destino (consúltalos, no los supongas).
* Fechas siempre en ms y zona `America/Bogota`; muestra la fecha legible en la ficha.
* Prohibido crear tareas duplicadas: si sospechas que ya existe, busca primero
  (`clickup_list_tasks` en la lista candidata) y avisa.
* Eliminar es destructivo: la ficha de borrado debe mostrar título, lista y enlace,
  y la confirmación debe ser explícita (*"sí, elimínala"*).

---

## ⚙️ Conexión y Gateway MCP

* **URL del Servicio**: `http://127.0.0.1:8005/clickup` (interno) / `https://mcp.jeisson.top/clickup` (público)
* **Transporte**: Streamable HTTP / SSE JSON-RPC 2.0
* **Autenticación**: Cabecera `Authorization: Bearer <MCP_API_KEY>`
