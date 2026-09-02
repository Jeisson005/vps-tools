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
      if (sId === "passbolt") openPassboltAccounts();
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

// --- Passbolt Accounts Manager ---
function escapeHtml(s) {
  return String(s || "").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function resetPassboltForm() {
  document.getElementById("pb-instance-id").value = "";
  document.getElementById("pb-account-name").value = "";
  document.getElementById("pb-base-url").value = "";
  document.getElementById("pb-user-email").value = "";
  document.getElementById("pb-private-key-paste").value = "";
  document.getElementById("pb-passphrase").value = "";
  document.getElementById("pb-is-default").checked = false;
  document.getElementById("pb-passphrase").placeholder = "Frase de paso si tu clave está cifrada";
  passboltArmoredKey = "";
  const label = document.getElementById("pb-key-status");
  label.innerText = "Ninguna clave cargada";
  label.className = "file-status-label";
  const feedback = document.getElementById("pb-test-feedback");
  feedback.className = "test-feedback-box hidden";
  feedback.innerText = "";
  document.getElementById("btn-delete-passbolt-account").classList.add("hidden");
  document.getElementById("pb-modal-title").innerText = "Configurar cuenta Passbolt";
}

async function openPassboltAccounts() {
  document.getElementById("passbolt-accounts-modal").classList.add("active");
  await renderPassboltAccounts();
}

function closePassboltAccounts() {
  document.getElementById("passbolt-accounts-modal").classList.remove("active");
}

async function renderPassboltAccounts() {
  const list = document.getElementById("pb-accounts-list");
  if (!list) return;
  list.innerHTML = '<div class="empty-state">Cargando cuentas...</div>';
  let accounts = [];
  try {
    const res = await apiFetch("/api/admin/passbolt/accounts");
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
    else badges.push('<span class="badge">Sin clave</span>');

    const row = document.createElement("div");
    row.className = "account-row";
    row.innerHTML = `
      <div class="account-info">
        <div class="account-title"><b>${escapeHtml(acc.instance_id)}</b> ${badges.join(" ")}</div>
        <div class="account-sub">${escapeHtml(acc.user_email || "sin correo")}</div>
        <div class="account-sub muted">${escapeHtml(acc.base_url || "sin URL")}${acc.fingerprint ? " · " + escapeHtml(acc.fingerprint) : ""}</div>
      </div>
      <div class="account-actions">
        <button class="btn btn-secondary btn-sm pb-test-account" data-id="${escapeHtml(acc.instance_id)}">Probar</button>
        <button class="btn btn-primary btn-sm pb-edit-account" data-id="${escapeHtml(acc.instance_id)}">Editar</button>
        <button class="btn btn-ghost btn-sm btn-danger pb-delete-account" data-id="${escapeHtml(acc.instance_id)}">Eliminar</button>
      </div>
    `;
    list.appendChild(row);
  });
  list.querySelectorAll(".pb-test-account").forEach(b => b.addEventListener("click", () => testPassboltAccount(b.getAttribute("data-id"), b)));
  list.querySelectorAll(".pb-edit-account").forEach(b => b.addEventListener("click", () => openPassboltEditor(b.getAttribute("data-id"))));
  list.querySelectorAll(".pb-delete-account").forEach(b => b.addEventListener("click", () => deletePassboltAccount(b.getAttribute("data-id"))));
}

async function testPassboltAccount(instanceId, btn) {
  const oldText = btn ? btn.innerText : "";
  if (btn) { btn.disabled = true; btn.innerText = "Probando..."; }
  try {
    const res = await apiFetch(`/api/admin/passbolt/accounts/${encodeURIComponent(instanceId)}/test`, { method: "POST" });
    const data = await res.json();
    if (data.ok) showToast((data.message || "Conexión exitosa") + ` [${instanceId}]`, "success");
    else showToast((data.message || "Fallo de conexión") + ` [${instanceId}]`, "error");
  } catch (e) {
    showToast("Error probando cuenta: " + e.message, "error");
  } finally {
    if (btn) { btn.disabled = false; btn.innerText = oldText; }
  }
}

async function deletePassboltAccount(instanceId) {
  if (!confirm(`¿Eliminar la cuenta Passbolt '${instanceId}'? Esta acción no se puede deshacer.`)) return;
  try {
    const res = await apiFetch(`/api/admin/passbolt/accounts/${encodeURIComponent(instanceId)}`, { method: "DELETE" });
    if (res.ok) {
      showToast("Cuenta eliminada", "success");
      loadServices();
      await renderPassboltAccounts();
    } else {
      const err = await res.json();
      showToast(err.detail || "Error eliminando cuenta", "error");
    }
  } catch (e) {
    showToast(e.message, "error");
  }
}

async function openPassboltEditor(instanceId) {
  closePassboltAccounts();
  resetPassboltForm();
  if (instanceId) {
    document.getElementById("pb-modal-title").innerText = "Editar cuenta Passbolt";
    try {
      const res = await apiFetch("/api/admin/passbolt/accounts");
      const accounts = await res.json();
      const acc = accounts.find(a => a.instance_id === instanceId);
      if (acc) {
        document.getElementById("pb-instance-id").value = acc.instance_id;
        document.getElementById("pb-account-name").value = acc.instance_id;
        document.getElementById("pb-base-url").value = acc.base_url || "";
        document.getElementById("pb-user-email").value = acc.user_email || "";
        document.getElementById("pb-is-default").checked = !!acc.is_default;
        if (acc.has_private_key) {
          const label = document.getElementById("pb-key-status");
          label.innerText = "✓ Clave privada guardada en base de datos";
          label.className = "file-status-label loaded";
        }
        if (acc.has_passphrase) {
          document.getElementById("pb-passphrase").placeholder = "•••••••••••• (Guardada en BD)";
        }
        document.getElementById("btn-delete-passbolt-account").classList.remove("hidden");
      }
    } catch (e) {
      showToast("Error cargando cuenta", "error");
    }
  }
  document.getElementById("passbolt-modal").classList.add("active");
}

function closePassboltModal() {
  document.getElementById("passbolt-modal").classList.remove("active");
}

document.getElementById("btn-close-passbolt-modal").addEventListener("click", closePassboltModal);
document.getElementById("btn-cancel-passbolt").addEventListener("click", closePassboltModal);
document.getElementById("btn-close-pb-accounts-modal").addEventListener("click", closePassboltAccounts);
document.getElementById("btn-close-pb-accounts-modal-2").addEventListener("click", closePassboltAccounts);
document.getElementById("btn-add-passbolt-account").addEventListener("click", () => openPassboltEditor(null));

document.getElementById("btn-delete-passbolt-account").addEventListener("click", async () => {
  const instanceId = document.getElementById("pb-instance-id").value;
  if (!instanceId) return;
  await deletePassboltAccount(instanceId);
  closePassboltModal();
  openPassboltAccounts();
});

// Toggle Passphrase Visibility
document.getElementById("btn-toggle-pb-passphrase").addEventListener("click", () => {
  const input = document.getElementById("pb-passphrase");
  input.type = input.type === "password" ? "text" : "password";
});

// File Drag & Drop for GPG Key
const dropArea = document.getElementById("pb-file-drop");
const fileInput = document.getElementById("pb-key-file");

['dragenter', 'dragover'].forEach(name => {
  dropArea.addEventListener(name, (e) => {
    e.preventDefault();
    dropArea.classList.add("dragover");
  });
});
['dragleave', 'drop'].forEach(name => {
  dropArea.addEventListener(name, (e) => {
    e.preventDefault();
    dropArea.classList.remove("dragover");
  });
});

dropArea.addEventListener("drop", (e) => {
  const files = e.dataTransfer.files;
  if (files.length > 0) handleKeyFile(files[0]);
});

fileInput.addEventListener("change", (e) => {
  if (e.target.files.length > 0) handleKeyFile(e.target.files[0]);
});

function handleKeyFile(file) {
  const reader = new FileReader();
  reader.onload = (e) => {
    passboltArmoredKey = e.target.result;
    document.getElementById("pb-private-key-paste").value = passboltArmoredKey;
    const label = document.getElementById("pb-key-status");
    label.innerText = `✓ Archivo cargado: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
    label.className = "file-status-label loaded";
  };
  reader.readAsText(file);
}

// Live Test Connection Button inside the editor
document.getElementById("btn-test-passbolt-live").addEventListener("click", async () => {
  const btn = document.getElementById("btn-test-passbolt-live");
  const feedback = document.getElementById("pb-test-feedback");
  const instanceId = document.getElementById("pb-instance-id").value;
  const baseUrl = document.getElementById("pb-base-url").value.trim();

  if (!baseUrl) {
    showToast("Ingresa la URL del servidor Passbolt", "error");
    return;
  }

  btn.disabled = true;
  btn.innerText = "Probando conexión...";
  feedback.className = "test-feedback-box hidden";

  const showFeedback = (ok, message, details) => {
    feedback.classList.remove("hidden");
    feedback.className = `test-feedback-box ${ok ? "success" : "error"}`;
    feedback.innerHTML = ok
      ? `<strong>✓ Conexión Exitosa:</strong> ${message}<br><small>Usuario: ${details?.user || 'N/A'} | Recursos: ${details?.vault_resources_count ?? 'N/A'}</small>`
      : `<strong>✗ Fallo:</strong> ${message}`;
  };

  try {
    // Existing account -> test from stored config; new account -> test the draft.
    let result;
    if (instanceId) {
      const res = await apiFetch(`/api/admin/passbolt/accounts/${encodeURIComponent(instanceId)}/test`, { method: "POST" });
      result = await res.json();
    } else {
      const userEmail = document.getElementById("pb-user-email").value.trim();
      const keyPaste = document.getElementById("pb-private-key-paste").value.trim();
      const passphrase = document.getElementById("pb-passphrase").value;
      const res = await apiFetch("/api/admin/services/passbolt/test-config", {
        method: "POST",
        body: JSON.stringify({
          config: { base_url: baseUrl, user_email: userEmail },
          secrets: {
            private_key: keyPaste || passboltArmoredKey || undefined,
            passphrase: passphrase || undefined
          }
        })
      });
      result = await res.json();
    }
    showFeedback(result.ok, result.message || "Sin mensaje", result.details);
  } catch (err) {
    showFeedback(false, err.message);
  } finally {
    btn.disabled = false;
    btn.innerText = "Probar Conexión Live";
  }
});

// Save Passbolt Account Form
document.getElementById("passbolt-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const instanceId = document.getElementById("pb-instance-id").value;
  const name = document.getElementById("pb-account-name").value.trim();
  const baseUrl = document.getElementById("pb-base-url").value.trim();
  const userEmail = document.getElementById("pb-user-email").value.trim();
  const keyPaste = document.getElementById("pb-private-key-paste").value.trim();
  const passphrase = document.getElementById("pb-passphrase").value;
  const isDefault = document.getElementById("pb-is-default").checked;

  const resolvedId = instanceId || name;
  if (!resolvedId) { showToast("Ingresa un nombre para la cuenta", "error"); return; }
  if (!baseUrl) { showToast("Ingresa la URL del servidor Passbolt", "error"); return; }

  const payload = {
    instance_id: resolvedId,
    enabled: true,
    is_default: isDefault,
    config: { base_url: baseUrl, user_email: userEmail },
    secrets: {}
  };
  if (keyPaste || passboltArmoredKey) payload.secrets.private_key = keyPaste || passboltArmoredKey;
  if (passphrase) payload.secrets.passphrase = passphrase;

  try {
    const res = await apiFetch("/api/admin/passbolt/accounts", {
      method: "POST",
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      showToast("Cuenta Passbolt guardada", "success");
      closePassboltModal();
      loadServices();
      await openPassboltAccounts();
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
