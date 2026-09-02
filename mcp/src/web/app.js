// MCP Gateway Admin Panel Frontend (Pure Vanilla JS, 0 dependencies)

let currentToken = localStorage.getItem("mcp_admin_token") || "";
let loadedServices = [];
let passboltArmoredKey = "";

// --- Toast Notifications ---
function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.innerText = message;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 250);
  }, 3500);
}

// --- Direct Fetch Helper ---
async function apiFetch(endpoint, options = {}) {
  options.headers = options.headers || {};
  options.headers["Content-Type"] = options.headers["Content-Type"] || "application/json";

  const res = await fetch(endpoint, options);
  if (!res.ok && res.status !== 404) {
    console.warn(`Request to ${endpoint} returned status ${res.status}`);
  }
  return res;
}

// --- Tab Navigation ---
function initTabs() {
  const tabs = document.querySelectorAll(".nav-tab");
  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      tabs.forEach(t => t.classList.remove("active"));
      document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));

      tab.classList.add("active");
      const target = tab.getAttribute("data-tab");
      const pane = document.getElementById(`tab-${target}`);
      if (pane) {
        pane.classList.add("active");
      }

      if (target === "tester") loadTesterTools();
      if (target === "clients") updateClientSnippets();
      if (target === "logs") loadLogs();
    });
  });
}

// --- Load Services List ---
async function loadServices() {
  try {
    const res = await apiFetch("/api/admin/services");
    if (!res.ok) throw new Error("Error cargando servicios");
    const services = await res.json();
    loadedServices = services;
    renderServicesGrid(services);
  } catch (err) {
    showToast(err.message, "error");
  }
}

function renderServicesGrid(services) {
  const grid = document.getElementById("services-grid");
  if (!grid) return;
  grid.innerHTML = "";

  services.forEach(s => {
    const isConfigured = s.configured;
    const isEnabled = s.enabled;

    let badgeClass = "badge";
    let badgeText = "Sin Configurar";
    if (isConfigured && isEnabled) {
      badgeClass = "badge badge-success";
      badgeText = "Activo";
    } else if (!isEnabled) {
      badgeClass = "badge badge-error";
      badgeText = "Inactivo";
    }

    const card = document.createElement("div");
    card.className = "service-card";
    card.innerHTML = `
      <div class="service-top">
        <div class="service-header">
          <div class="service-title-wrap">
            <div class="service-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
            </div>
            <div>
              <div class="service-name">${s.name}</div>
            </div>
          </div>
          <span class="${badgeClass}">${badgeText}</span>
        </div>
        <p class="service-desc">${s.description}</p>
        <div class="service-tags">
          <span class="tag-subroute">/${s.id}</span>
          <span class="tag-tools">${s.tools_count} Tools activas</span>
        </div>
      </div>
      <div class="service-bottom">
        <label class="switch" title="${isEnabled ? 'Desactivar' : 'Activar'}">
          <input type="checkbox" ${isEnabled ? "checked" : ""} class="service-toggle" data-id="${s.id}">
          <span class="slider"></span>
        </label>
        <div class="service-actions">
          <button class="btn btn-secondary btn-sm btn-test-service" data-id="${s.id}">
            Probar
          </button>
          <button class="btn btn-primary btn-sm btn-config-service" data-id="${s.id}">
            Configurar
          </button>
        </div>
      </div>
    `;
    grid.appendChild(card);
  });

  // Attach event listeners
  document.querySelectorAll(".service-toggle").forEach(toggle => {
    toggle.addEventListener("change", async (e) => {
      const sId = e.target.getAttribute("data-id");
      const enabled = e.target.checked;
      await toggleServiceState(sId, enabled);
    });
  });

  document.querySelectorAll(".btn-config-service").forEach(btn => {
    btn.addEventListener("click", (e) => {
      const sId = e.target.closest("button").getAttribute("data-id");
      openServiceAccounts(sId);
    });
  });

  document.querySelectorAll(".btn-test-service").forEach(btn => {
    btn.addEventListener("click", async (e) => {
      const sId = e.target.closest("button").getAttribute("data-id");
      await testServiceDirectly(sId);
    });
  });
}

async function testServiceDirectly(serviceId) {
  showToast(`Probando conexión con ${serviceId}...`, "info");
  try {
    const res = await apiFetch(`/api/admin/services/${serviceId}/test`, { method: "POST" });
    const data = await res.json();
    if (data.ok) {
      showToast(data.message || "¡Conexión exitosa!", "success");
    } else {
      showToast(data.message || "Fallo en la prueba de conexión", "error");
    }
  } catch (err) {
    showToast("Error ejecutando prueba: " + err.message, "error");
  }
}

async function toggleServiceState(serviceId, enabled) {
  try {
    const res = await apiFetch(`/api/admin/services/${serviceId}/toggle`, {
      method: "POST",
      body: JSON.stringify({ enabled })
    });
    if (res.ok) {
      showToast(`Servicio ${serviceId} ${enabled ? 'habilitado' : 'deshabilitado'}`, "success");
      loadServices();
    } else {
      throw new Error("No se pudo cambiar el estado del servicio");
    }
  } catch (err) {
    showToast(err.message, "error");
    loadServices();
  }
}

// --- Generic Service Accounts Manager (schema-driven) ---
let currentAccountService = "";

function escapeHtml(s) {
  return String(s || "").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

async function getServiceSchema(serviceId) {
  const res = await apiFetch(`/api/admin/services/${encodeURIComponent(serviceId)}/account-schema`);
  if (!res.ok) return { config: [], secrets: [] };
  try { return await res.json(); } catch (e) { return { config: [], secrets: [] }; }
}

async function openServiceAccounts(serviceId) {
  currentAccountService = serviceId;
  const title = document.getElementById("pb-accounts-title");
  if (title) {
    const svc = loadedServices.find(s => s.id === serviceId);
    title.innerText = "Cuentas · " + (svc ? svc.name : serviceId);
  }
  document.getElementById("passbolt-accounts-modal").classList.add("active");
  await renderServiceAccounts();
}

function closeServiceAccounts() {
  document.getElementById("passbolt-accounts-modal").classList.remove("active");
}

function closeAccountEditor() {
  document.getElementById("passbolt-modal").classList.remove("active");
}

function resetAccountForm() {
  document.getElementById("pb-instance-id").value = "";
  document.getElementById("pb-account-name").value = "";
  document.getElementById("pb-is-default").checked = false;
  const container = document.getElementById("account-form-fields");
  if (container) container.innerHTML = "";
  const feedback = document.getElementById("pb-test-feedback");
  feedback.className = "test-feedback-box hidden";
  feedback.innerText = "";
  const del = document.getElementById("btn-delete-passbolt-account");
  if (del) del.classList.add("hidden");
  const t = document.getElementById("pb-modal-title");
  if (t) t.innerText = "Configurar cuenta";
}

async function renderServiceAccounts() {
  const list = document.getElementById("pb-accounts-list");
  if (!list) return;
  list.innerHTML = '<div class="empty-state">Cargando cuentas...</div>';
  let accounts = [];
  try {
    const res = await apiFetch(`/api/admin/services/${encodeURIComponent(currentAccountService)}/accounts`);
    accounts = await res.json();
  } catch (e) {
    list.innerHTML = '<div class="empty-state">Error cargando cuentas</div>';
    return;
  }
  if (!accounts || accounts.length === 0) {
    list.innerHTML = '<div class="empty-state">No hay cuentas configuradas. Añade la primera.</div>';
    return;
  }
  list.innerHTML = "";
  accounts.forEach(acc => {
    const badges = [];
    if (acc.is_default) badges.push('<span class="badge badge-primary">Principal</span>');
    if (acc.configured) badges.push('<span class="badge badge-success">Conectada</span>');
    else badges.push('<span class="badge">Sin credenciales</span>');
    const label = acc.name || acc.instance_id;
    const detail = acc.user_email || acc.instance_id;
    const row = document.createElement("div");
    row.className = "account-row";
    row.innerHTML = `
      <div class="account-info">
        <div class="account-title"><b>${escapeHtml(label)}</b> ${badges.join(" ")}</div>
        <div class="account-sub">${escapeHtml(detail)}</div>
        ${acc.base_url ? `<div class="account-sub muted">${escapeHtml(acc.base_url)}</div>` : ""}
      </div>
      <div class="account-actions">
        ${currentAccountService === "whatsapp" ? `<button class="btn btn-secondary btn-sm acc-qr" data-id="${escapeHtml(acc.instance_id)}">Ver QR</button>` : ""}
        <button class="btn btn-secondary btn-sm acc-test" data-id="${escapeHtml(acc.instance_id)}">Probar</button>
        <button class="btn btn-primary btn-sm acc-edit" data-id="${escapeHtml(acc.instance_id)}">Editar</button>
        <button class="btn btn-ghost btn-sm btn-danger acc-delete" data-id="${escapeHtml(acc.instance_id)}">Eliminar</button>
      </div>
    `;
    list.appendChild(row);
  });
  list.querySelectorAll(".acc-qr").forEach(b => b.addEventListener("click", () => showQr(b.getAttribute("data-id"))));
  list.querySelectorAll(".acc-test").forEach(b => b.addEventListener("click", () => testServiceAccount(b.getAttribute("data-id"), b)));
  list.querySelectorAll(".acc-edit").forEach(b => b.addEventListener("click", () => openAccountEditor(b.getAttribute("data-id"))));
  list.querySelectorAll(".acc-delete").forEach(b => b.addEventListener("click", () => deleteServiceAccount(b.getAttribute("data-id"))));
}

// WhatsApp QR modal -----------------------------------------------------------
let currentQrAccount = "";

async function showQr(instanceId) {
  currentQrAccount = instanceId;
  const modal = document.getElementById("qr-modal");
  const img = document.getElementById("qr-img");
  const urlEl = document.getElementById("qr-url");
  img.style.display = "none";
  img.src = "";
  urlEl.innerText = "";
  modal.classList.add("active");
  await loadQrImage(instanceId);
}

async function loadQrImage(instanceId) {
  const img = document.getElementById("qr-img");
  const urlEl = document.getElementById("qr-url");
  try {
    const res = await apiFetch(`/api/admin/services/${encodeURIComponent(currentAccountService)}/accounts/${encodeURIComponent(instanceId)}/qr`);
    const data = await res.json();
    if (data.image) { img.src = data.image; img.style.display = "block"; }
    if (data.qr) urlEl.innerText = data.qr;
    if (!data.image && !data.qr) showToast("El bridge aún no genera QR (sin vincular o reiniciando). Prueba en unos segundos.", "error");
  } catch (e) {
    showToast("Error obteniendo QR: " + e.message, "error");
  }
}

document.getElementById("btn-close-qr-modal").addEventListener("click", () => document.getElementById("qr-modal").classList.remove("active"));
document.getElementById("btn-close-qr-modal-2").addEventListener("click", () => document.getElementById("qr-modal").classList.remove("active"));
document.getElementById("btn-refresh-qr").addEventListener("click", () => {
  if (currentQrAccount) loadQrImage(currentQrAccount);
});

async function testServiceAccount(instanceId, btn) {
  const oldText = btn ? btn.innerText : "";
  if (btn) { btn.disabled = true; btn.innerText = "Probando..."; }
  try {
    const res = await apiFetch(`/api/admin/services/${encodeURIComponent(currentAccountService)}/accounts/${encodeURIComponent(instanceId)}/test`, { method: "POST" });
    const data = await res.json();
    if (data.ok) showToast((data.message || "Conexión exitosa") + ` [${instanceId}]`, "success");
    else showToast((data.message || "Fallo de conexión") + ` [${instanceId}]`, "error");
  } catch (e) {
    showToast("Error probando cuenta: " + e.message, "error");
  } finally {
    if (btn) { btn.disabled = false; btn.innerText = oldText; }
  }
}

async function deleteServiceAccount(instanceId) {
  if (!confirm(`¿Eliminar la cuenta '${instanceId}'? Esta acción no se puede deshacer.`)) return;
  try {
    const res = await apiFetch(`/api/admin/services/${encodeURIComponent(currentAccountService)}/accounts/${encodeURIComponent(instanceId)}`, { method: "DELETE" });
    if (res.ok) {
      showToast("Cuenta eliminada", "success");
      loadServices();
      await renderServiceAccounts();
    } else {
      const err = await res.json();
      showToast(err.detail || "Error eliminando cuenta", "error");
    }
  } catch (e) {
    showToast(e.message, "error");
  }
}

function buildSectionTitle(text) {
  const div = document.createElement("div");
  div.className = "form-section-title";
  div.innerText = text;
  return div;
}

function buildAccountField(field, value) {
  const wrap = document.createElement("div");
  wrap.className = "input-group";
  const label = document.createElement("label");
  label.innerText = field.label + (field.required ? " *" : "");
  wrap.appendChild(label);

  const id = "af-" + field.key;
  if (field.type === "textarea" || field.type === "password") {
    const el = document.createElement(field.type === "textarea" ? "textarea" : "input");
    if (field.type === "textarea") { el.rows = 3; if (field.placeholder) el.placeholder = field.placeholder; }
    else { el.type = "password"; if (field.placeholder) el.placeholder = field.placeholder; }
    el.id = id;
    el.dataset.fieldKey = field.key;
    if (value !== undefined && value !== null) el.value = value;
    if (field.type === "password" && value) el.placeholder = "•••••••••••• (guardado en BD)";
    wrap.appendChild(el);
  } else {
    const el = document.createElement("input");
    el.type = field.type || "text";
    el.id = id;
    el.dataset.fieldKey = field.key;
    if (field.placeholder) el.placeholder = field.placeholder;
    if (value !== undefined && value !== null) el.value = value;
    wrap.appendChild(el);
  }
  return wrap;
}

function collectAccountFields() {
  const config = {};
  const secrets = {};
  document.querySelectorAll("#account-form-fields [data-field-key]").forEach(el => {
    const key = el.dataset.fieldKey;
    const val = el.value.trim();
    if (val) (el.dataset.kind === "secret" ? secrets : config)[key] = val;
  });
  return { config, secrets };
}

async function openAccountEditor(instanceId) {
  closeServiceAccounts();
  resetAccountForm();
  const schema = await getServiceSchema(currentAccountService);
  const container = document.getElementById("account-form-fields");
  container.innerHTML = "";
  container.appendChild(buildSectionTitle("Datos de la cuenta"));
  (schema.config || []).forEach(f => container.appendChild(buildAccountField(f)));
  container.appendChild(buildSectionTitle("Credenciales / secretos"));
  (schema.secrets || []).forEach(f => container.appendChild(buildAccountField(f)));

  if (instanceId) {
    const t = document.getElementById("pb-modal-title");
    if (t) t.innerText = "Editar cuenta";
    try {
      const res = await apiFetch(`/api/admin/services/${encodeURIComponent(currentAccountService)}/accounts`);
      const accounts = await res.json();
      const acc = accounts.find(a => a.instance_id === instanceId);
      if (acc) {
        document.getElementById("pb-instance-id").value = acc.instance_id;
        document.getElementById("pb-account-name").value = acc.name || acc.instance_id;
        document.getElementById("pb-is-default").checked = !!acc.is_default;
        (schema.config || []).forEach(f => {
          const el = document.getElementById("af-" + f.key);
          if (!el) return;
          if (f.key === "email" && acc.user_email) el.value = acc.user_email;
          if (f.key === "base_url" && acc.base_url) el.value = acc.base_url;
          if (f.key === "user_email" && acc.user_email) el.value = acc.user_email;
        });
        document.getElementById("btn-delete-passbolt-account").classList.remove("hidden");
      }
    } catch (e) { showToast("Error cargando cuenta", "error"); }
  }
  document.getElementById("passbolt-modal").classList.add("active");
}

document.getElementById("btn-close-passbolt-modal").addEventListener("click", closeAccountEditor);
document.getElementById("btn-cancel-passbolt").addEventListener("click", closeAccountEditor);
document.getElementById("btn-close-pb-accounts-modal").addEventListener("click", closeServiceAccounts);
document.getElementById("btn-close-pb-accounts-modal-2").addEventListener("click", closeServiceAccounts);
document.getElementById("btn-add-passbolt-account").addEventListener("click", () => openAccountEditor(null));

document.getElementById("btn-delete-passbolt-account").addEventListener("click", async () => {
  const instanceId = document.getElementById("pb-instance-id").value;
  if (!instanceId) return;
  await deleteServiceAccount(instanceId);
  closeAccountEditor();
  openServiceAccounts(currentAccountService);
});

// Live Test (existing account or draft)
document.getElementById("btn-test-passbolt-live").addEventListener("click", async () => {
  const btn = document.getElementById("btn-test-passbolt-live");
  const feedback = document.getElementById("pb-test-feedback");
  const instanceId = document.getElementById("pb-instance-id").value;
  const { config, secrets } = collectAccountFields();

  btn.disabled = true;
  btn.innerText = "Probando conexión...";
  feedback.className = "test-feedback-box hidden";

  const showFeedback = (ok, message, details) => {
    feedback.classList.remove("hidden");
    feedback.className = `test-feedback-box ${ok ? "success" : "error"}`;
    feedback.innerHTML = ok
      ? `<strong>✓ Conexión Exitosa:</strong> ${message}`
      : `<strong>✗ Fallo:</strong> ${message}`;
  };

  try {
    let result;
    if (instanceId) {
      const res = await apiFetch(`/api/admin/services/${encodeURIComponent(currentAccountService)}/accounts/${encodeURIComponent(instanceId)}/test`, { method: "POST" });
      result = await res.json();
    } else {
      const res = await apiFetch(`/api/admin/services/${encodeURIComponent(currentAccountService)}/test-config`, {
        method: "POST",
        body: JSON.stringify({ config, secrets })
      });
      result = (res.ok) ? await res.json() : { ok: false, message: "test-config no disponible para este servicio" };
    }
    showFeedback(result.ok, result.message || "Sin mensaje", result.details);
  } catch (err) {
    showFeedback(false, err.message);
  } finally {
    btn.disabled = false;
    btn.innerText = "Probar Conexión Live";
  }
});

// Save account
document.getElementById("passbolt-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const instanceId = document.getElementById("pb-instance-id").value;
  const name = document.getElementById("pb-account-name").value.trim();
  const isDefault = document.getElementById("pb-is-default").checked;
  const { config, secrets } = collectAccountFields();

  const resolvedId = instanceId || name;
  if (!resolvedId) { showToast("Ingresa un nombre para la cuenta", "error"); return; }
  // Require at least one value (config OR secrets) when creating a new account.
  // Some services (e.g. WhatsApp) only need configuration, no secrets.
  const hasAny = Object.keys(config).length || Object.keys(secrets).length;
  if (!instanceId && !hasAny) { showToast("Completa al menos un dato (configuración o credencial)", "error"); return; }

  const payload = { instance_id: resolvedId, name, enabled: true, is_default: isDefault, config, secrets };
  try {
    const res = await apiFetch(`/api/admin/services/${encodeURIComponent(currentAccountService)}/accounts`, {
      method: "POST",
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      showToast("Cuenta guardada", "success");
      closeAccountEditor();
      loadServices();
      await openServiceAccounts(currentAccountService);
    } else {
      const err = await res.json();
      showToast(err.detail || "Error guardando cuenta", "error");
    }
  } catch (err) {
    showToast(err.message, "error");
  }
});
// --- Tab 2: Tester & Tool Inspector ---
async function loadTesterTools() {
  const select = document.getElementById("tester-tool-select");
  const scope = document.getElementById("tester-scope").value;
  select.innerHTML = "<option value=''>Cargando herramientas...</option>";

  try {
    const res = await apiFetch("/api/admin/tools");
    const tools = await res.json();
    select.innerHTML = "";

    const filtered = scope === "unified" ? tools : tools.filter(t => t.service === scope);
    if (filtered.length === 0) {
      select.innerHTML = "<option value=''>No hay herramientas disponibles en este scope</option>";
      return;
    }

    filtered.forEach(t => {
      const opt = document.createElement("option");
      opt.value = t.name;
      opt.innerText = `${t.name} — ${t.description.substring(0, 60)}...`;
      opt.setAttribute("data-schema", JSON.stringify(t.inputSchema || {}));
      select.appendChild(opt);
    });

    fillDefaultTemplate();
  } catch (err) {
    select.innerHTML = "<option value=''>Error cargando herramientas</option>";
  }
}

document.getElementById("tester-scope").addEventListener("change", loadTesterTools);
document.getElementById("tester-tool-select").addEventListener("change", fillDefaultTemplate);

function fillDefaultTemplate() {
  const select = document.getElementById("tester-tool-select");
  const selectedOpt = select.options[select.selectedIndex];
  if (!selectedOpt) return;

  const toolName = selectedOpt.value;
  let sample = {};
  if (toolName === "passbolt_search_resources") {
    sample = { query: "postgres", limit: 10 };
  } else if (toolName === "passbolt_get_secret") {
    sample = { resource_id: "00000000-0000-0000-0000-000000000000" };
  } else if (toolName === "passbolt_list_folders") {
    sample = {};
  }
  document.getElementById("tester-args").value = JSON.stringify(sample, null, 2);
}

document.getElementById("btn-fill-template").addEventListener("click", fillDefaultTemplate);

document.getElementById("btn-run-tool").addEventListener("click", async () => {
  const toolName = document.getElementById("tester-tool-select").value;
  const scope = document.getElementById("tester-scope").value;
  const rawArgs = document.getElementById("tester-args").value.trim();
  const output = document.getElementById("tester-output");
  const badge = document.getElementById("tester-status-badge");
  const btn = document.getElementById("btn-run-tool");

  if (!toolName) {
    showToast("Selecciona una herramienta primero", "error");
    return;
  }

  let parsedArgs = {};
  if (rawArgs) {
    try {
      parsedArgs = JSON.parse(rawArgs);
    } catch (e) {
      showToast("Los argumentos deben ser un JSON válido", "error");
      return;
    }
  }

  btn.disabled = true;
  btn.innerText = "Ejecutando...";
  badge.className = "badge";
  badge.innerText = "Procesando...";
  output.innerText = "Enviando llamada JSON-RPC 2.0 al Gateway...";

  const startTime = performance.now();
  try {
    const res = await apiFetch("/api/admin/tools/execute", {
      method: "POST",
      body: JSON.stringify({
        scope: scope,
        tool: toolName,
        arguments: parsedArgs
      })
    });
    const elapsed = Math.round(performance.now() - startTime);
    const data = await res.json();

    if (res.ok && !data.error) {
      badge.className = "badge badge-success";
      badge.innerText = `Éxito (${elapsed}ms)`;
      output.innerText = JSON.stringify(data, null, 2);
    } else {
      badge.className = "badge badge-error";
      badge.innerText = `Error (${elapsed}ms)`;
      output.innerText = JSON.stringify(data, null, 2);
    }
  } catch (err) {
    badge.className = "badge badge-error";
    badge.innerText = "Error de Red";
    output.innerText = `Error: ${err.message}`;
  } finally {
    btn.disabled = false;
    btn.innerText = "Ejecutar Herramienta";
  }
});

// --- Tab 3: Client Snippets ---
async function updateClientSnippets() {
  try {
    const res = await apiFetch("/api/admin/gateway-info");
    const info = await res.json();
    const domain = window.location.origin;
    const apiKey = info.api_key || "mcp_sec_...";

    // 1. Hermes Config Snippet
    document.getElementById("code-hermes").innerText = 
`mcp_servers:
  passbolt:
    url: "${domain}/passbolt"
    headers:
      Authorization: "Bearer ${apiKey}"
    timeout: 180

  unified:
    url: "${domain}/unified"
    headers:
      Authorization: "Bearer ${apiKey}"
    timeout: 180`;

    // 2. Claude Desktop Config Snippet
    document.getElementById("code-claude").innerText = 
`{
  "mcpServers": {
    "passbolt": {
      "url": "${domain}/passbolt",
      "headers": {
        "Authorization": "Bearer ${apiKey}"
      }
    }
  }
}`;

    // 3. Cursor Config Snippet
    document.getElementById("code-cursor").innerText = 
`{
  "mcpServers": {
    "passbolt": {
      "url": "${domain}/passbolt",
      "headers": {
        "Authorization": "Bearer ${apiKey}"
      }
    }
  }
}`;
  } catch (err) {
    console.error("Error updating snippets:", err);
  }
}

// Copy Code Button Handlers
document.querySelectorAll(".btn-copy").forEach(btn => {
  btn.addEventListener("click", () => {
    const targetId = btn.getAttribute("data-target");
    const code = document.getElementById(targetId).innerText;
    navigator.clipboard.writeText(code).then(() => {
      const originalText = btn.innerText;
      btn.innerText = "¡Copiado!";
      setTimeout(() => btn.innerText = originalText, 1500);
    });
  });
});

// --- Tab 4: Logs ---
async function loadLogs() {
  const tbody = document.getElementById("logs-tbody");
  tbody.innerHTML = "<tr><td colspan='5' class='text-center'>Cargando registros...</td></tr>";

  try {
    const res = await apiFetch("/api/admin/logs");
    const logs = await res.json();
    tbody.innerHTML = "";

    if (logs.length === 0) {
      tbody.innerHTML = "<tr><td colspan='5' class='text-center'>No hay actividad registrada aún.</td></tr>";
      return;
    }

    logs.forEach(log => {
      const tr = document.createElement("tr");
      const statusBadge = log.status === "success" 
        ? "<span class='badge badge-success'>Éxito</span>" 
        : "<span class='badge badge-error'>Error</span>";

      tr.innerHTML = `
        <td><small>${log.timestamp || 'N/A'}</small></td>
        <td><b>${log.service}</b></td>
        <td><code>${log.action}</code></td>
        <td>${statusBadge}</td>
        <td><small>${log.details || ''}</small></td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan='5' class='text-center text-error'>Error cargando logs: ${err.message}</td></tr>`;
  }
}

document.getElementById("btn-refresh-services").addEventListener("click", loadServices);
document.getElementById("btn-refresh-logs").addEventListener("click", loadLogs);

// --- Initialization ---
function loadInitialData() {
  loadServices();
}

// Bootstrap
document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  loadInitialData();
});
