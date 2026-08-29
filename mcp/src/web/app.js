// MCP Gateway Admin Panel Frontend Logic (Pure Vanilla JS, 0 dependencies)

let currentToken = localStorage.getItem("mcp_admin_token") || "";
let loadedServices = [];
let passboltArmoredKey = "";

// --- Toast Notifications ---
function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.innerText = message;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// --- Authenticated Fetch Helper ---
async function apiFetch(endpoint, options = {}) {
  options.headers = options.headers || {};
  if (currentToken) {
    options.headers["Authorization"] = `Bearer ${currentToken}`;
  }
  options.headers["Content-Type"] = options.headers["Content-Type"] || "application/json";

  const res = await fetch(endpoint, options);
  if (res.status === 401) {
    localStorage.removeItem("mcp_admin_token");
    currentToken = "";
    document.getElementById("app-layout").classList.add("hidden");
    document.getElementById("login-modal").classList.add("active");
    throw new Error("Sesión expirada o no autorizada.");
  }
  return res;
}

// --- Auth Flow ---
document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const password = document.getElementById("admin-password").value;
  try {
    const res = await fetch("/api/admin/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password })
    });
    const data = await res.json();
    if (res.ok && data.token) {
      currentToken = data.token;
      localStorage.setItem("mcp_admin_token", currentToken);
      document.getElementById("login-modal").classList.remove("active");
      document.getElementById("app-layout").classList.remove("hidden");
      showToast("Bienvenido al panel MCP Gateway", "success");
      loadInitialData();
    } else {
      showToast(data.detail || "Contraseña incorrecta", "error");
    }
  } catch (err) {
    showToast("Error de conexión: " + err.message, "error");
  }
});

document.getElementById("btn-logout").addEventListener("click", () => {
  localStorage.removeItem("mcp_admin_token");
  currentToken = "";
  document.getElementById("app-layout").classList.add("hidden");
  document.getElementById("login-modal").classList.add("active");
});

// --- Tab Navigation ---
document.querySelectorAll(".nav-tab").forEach(tab => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".nav-tab").forEach(t => t.classList.remove("active"));
    document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));

    tab.classList.add("active");
    const targetTab = tab.getAttribute("data-tab");
    document.getElementById(`tab-${targetTab}`).classList.add("active");

    if (targetTab === "tester") loadTesterTools();
    if (targetTab === "clients") updateClientSnippets();
    if (targetTab === "logs") loadLogs();
  });
});

// --- Load Services List ---
async function loadServices() {
  try {
    const res = await apiFetch("/api/admin/services");
    if (!res.ok) throw new Error("Error cargando servicios");
    const services = await res.json();
    loadedServices = services;
    renderServicesGrid(services);
    updateStats(services);
  } catch (err) {
    showToast(err.message, "error");
  }
}

function updateStats(services) {
  let totalTools = 0;
  services.forEach(s => {
    if (s.enabled && s.configured) totalTools += s.tools_count;
  });
  document.getElementById("stat-total-services").innerText = services.length;
  document.getElementById("stat-active-tools").innerText = totalTools;
}

function renderServicesGrid(services) {
  const grid = document.getElementById("services-grid");
  grid.innerHTML = "";

  services.forEach(s => {
    const isConfigured = s.configured;
    const isEnabled = s.enabled;

    let badgeClass = "badge-warning";
    let badgeText = "Sin Configurar";
    if (isConfigured && isEnabled) {
      badgeClass = "badge-success";
      badgeText = "Activo";
    } else if (!isEnabled) {
      badgeClass = "badge-error";
      badgeText = "Inactivo";
    }

    const card = document.createElement("div");
    card.className = "service-card glass-panel";
    card.innerHTML = `
      <div class="service-card-top">
        <div class="service-header">
          <div class="service-icon-box">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
          </div>
          <span class="badge ${badgeClass}">${badgeText}</span>
        </div>
        <div class="service-meta">
          <h3>${s.name}</h3>
          <p class="service-desc">${s.description}</p>
        </div>
        <div class="service-subroutes">
          <div>Subruta aislada: <span>/${s.id}</span></div>
          <div>Tools disponibles: <b>${s.tools_count}</b></div>
        </div>
      </div>
      <div class="service-card-bottom">
        <div class="service-toggle-wrap">
          <label class="switch">
            <input type="checkbox" ${isEnabled ? "checked" : ""} class="service-toggle" data-id="${s.id}">
            <span class="slider"></span>
          </label>
          <span>${isEnabled ? "Habilitado" : "Deshabilitado"}</span>
        </div>
        <button class="btn btn-secondary btn-sm btn-config-service" data-id="${s.id}">
          Configurar
        </button>
      </div>
    `;
    grid.appendChild(card);
  });

  // Attach event listeners for toggles and config buttons
  document.querySelectorAll(".service-toggle").forEach(toggle => {
    toggle.addEventListener("change", async (e) => {
      const sId = e.target.getAttribute("data-id");
      const enabled = e.target.checked;
      await toggleServiceState(sId, enabled);
    });
  });

  document.querySelectorAll(".btn-config-service").forEach(btn => {
    btn.addEventListener("click", (e) => {
      const sId = e.target.getAttribute("data-id");
      if (sId === "passbolt") openPassboltModal();
    });
  });
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

// --- Passbolt Configuration Modal ---
function openPassboltModal() {
  const modal = document.getElementById("passbolt-modal");
  const s = loadedServices.find(x => x.id === "passbolt");
  
  if (s && s.config) {
    document.getElementById("pb-url").value = s.config.base_url || "";
    document.getElementById("pb-email").value = s.config.user_email || "";
    document.getElementById("pb-fingerprint").value = s.config.fingerprint || "";
    
    const fileLabel = document.getElementById("file-status-label");
    if (s.has_private_key) {
      fileLabel.innerText = "✓ Clave privada ya configurada en SQLite";
      fileLabel.className = "file-status-label loaded";
    } else {
      fileLabel.innerText = "Ningún archivo cargado aún";
      fileLabel.className = "file-status-label";
    }

    if (s.has_passphrase) {
      document.getElementById("pb-passphrase").placeholder = "•••••••••••• (Guardada en SQLite)";
    }
  }

  document.getElementById("pb-test-feedback").classList.add("hidden");
  modal.classList.add("active");
}

// Close Modal helper
document.querySelectorAll(".modal-close").forEach(btn => {
  btn.addEventListener("click", () => {
    const targetModal = btn.getAttribute("data-modal");
    document.getElementById(targetModal).classList.remove("active");
  });
});

// File Drag & Drop for GPG Key
const dropArea = document.getElementById("file-drop-area");
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
  if (files.length) handleKeyFile(files[0]);
});

fileInput.addEventListener("change", (e) => {
  if (e.target.files.length) handleKeyFile(e.target.files[0]);
});

function handleKeyFile(file) {
  const reader = new FileReader();
  reader.onload = (e) => {
    passboltArmoredKey = e.target.result;
    const label = document.getElementById("file-status-label");
    label.innerText = `✓ Archivo cargado: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
    label.className = "file-status-label loaded";
    document.getElementById("pb-private-key").value = passboltArmoredKey;
    showToast("Clave privada GPG leída correctamente", "info");
  };
  reader.readAsText(file);
}

// Toggle password visibility
document.querySelectorAll(".btn-toggle-pwd").forEach(btn => {
  btn.addEventListener("click", () => {
    const targetId = btn.getAttribute("data-target");
    const input = document.getElementById(targetId);
    input.type = input.type === "password" ? "text" : "password";
  });
});

// Save Passbolt Config Form
document.getElementById("passbolt-config-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  
  const base_url = document.getElementById("pb-url").value.trim();
  const user_email = document.getElementById("pb-email").value.trim();
  const fingerprint = document.getElementById("pb-fingerprint").value.trim();
  const passphrase = document.getElementById("pb-passphrase").value;
  const private_key = document.getElementById("pb-private-key").value.trim() || passboltArmoredKey;

  const payload = {
    enabled: true,
    config: { base_url, user_email, fingerprint, verify_ssl: true },
    secrets: { passphrase, private_key }
  };

  try {
    const res = await apiFetch("/api/admin/services/passbolt", {
      method: "POST",
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (res.ok) {
      showToast("Configuración de Passbolt guardada con éxito en SQLite", "success");
      document.getElementById("passbolt-modal").classList.remove("active");
      loadServices();
    } else {
      showToast(data.detail || "Error al guardar configuración", "error");
    }
  } catch (err) {
    showToast(err.message, "error");
  }
});

// Test Passbolt Connection Live
document.getElementById("btn-test-passbolt").addEventListener("click", async () => {
  const feedback = document.getElementById("pb-test-feedback");
  feedback.className = "test-feedback-box";
  feedback.innerText = "Ejecutando handshake GPG con el servidor Passbolt...";
  feedback.classList.remove("hidden");

  // Collect current modal values to test without having to save first
  const base_url = document.getElementById("pb-url").value.trim();
  const user_email = document.getElementById("pb-email").value.trim();
  const fingerprint = document.getElementById("pb-fingerprint").value.trim();
  const passphrase = document.getElementById("pb-passphrase").value;
  const private_key = document.getElementById("pb-private-key").value.trim() || passboltArmoredKey;

  try {
    const res = await apiFetch("/api/admin/services/passbolt/test", {
      method: "POST",
      body: JSON.stringify({
        base_url, user_email, fingerprint, passphrase, private_key
      })
    });
    const result = await res.json();
    if (result.ok) {
      feedback.className = "test-feedback-box success";
      feedback.innerText = "✓ " + result.message;
      showToast("Prueba de conexión exitosa", "success");
    } else {
      feedback.className = "test-feedback-box error";
      feedback.innerText = "✗ " + result.message;
      showToast("Prueba de conexión fallida", "error");
    }
  } catch (err) {
    feedback.className = "test-feedback-box error";
    feedback.innerText = "✗ Error: " + err.message;
  }
});

// --- Tester / Inspector Tab ---
async function loadTesterTools() {
  const scope = document.getElementById("tester-scope").value;
  const select = document.getElementById("tester-tool-select");
  select.innerHTML = "<option value=''>Cargando herramientas...</option>";

  try {
    const res = await apiFetch(`/api/admin/tools?scope=${scope}`);
    const data = await res.json();
    select.innerHTML = "";
    if (!data.tools || data.tools.length === 0) {
      select.innerHTML = "<option value=''>No hay herramientas activas en este scope</option>";
      return;
    }
    data.tools.forEach(t => {
      const opt = document.createElement("option");
      opt.value = t.name;
      opt.innerText = `${t.name} — ${t.description.substring(0, 60)}...`;
      select.appendChild(opt);
    });
  } catch (err) {
    select.innerHTML = `<option value=''>Error cargando tools: ${err.message}</option>`;
  }
}

document.getElementById("tester-scope").addEventListener("change", loadTesterTools);

document.getElementById("btn-run-tool").addEventListener("click", async () => {
  const scope = document.getElementById("tester-scope").value;
  const toolName = document.getElementById("tester-tool-select").value;
  const rawArgs = document.getElementById("tester-args").value.trim();
  const outputBox = document.getElementById("tester-output");
  const badge = document.getElementById("tester-status-badge");

  if (!toolName) {
    showToast("Selecciona una herramienta", "warning");
    return;
  }

  let parsedArgs = {};
  if (rawArgs) {
    try {
      parsedArgs = JSON.parse(rawArgs);
    } catch (e) {
      showToast("El campo de argumentos debe ser un JSON válido", "error");
      return;
    }
  }

  badge.className = "badge badge-info";
  badge.innerText = "Ejecutando...";
  outputBox.innerText = "Enviando JSON-RPC request...";

  try {
    const res = await apiFetch("/api/admin/tester/call", {
      method: "POST",
      body: JSON.stringify({
        scope,
        tool: toolName,
        arguments: parsedArgs
      })
    });
    const result = await res.json();
    outputBox.innerText = JSON.stringify(result, null, 2);
    if (res.ok && !result.error && !(result.result && result.result.isError)) {
      badge.className = "badge badge-success";
      badge.innerText = "Éxito (200 OK)";
    } else {
      badge.className = "badge badge-error";
      badge.innerText = "Error";
    }
  } catch (err) {
    outputBox.innerText = "Error: " + err.message;
    badge.className = "badge badge-error";
    badge.innerText = "Fallo de Red";
  }
});

// --- Client Snippets ---
function updateClientSnippets() {
  const origin = window.location.origin;
  
  const cursorConfig = {
    mcpServers: {
      "vps-mcp-passbolt": {
        url: `${origin}/passbolt/sse`,
        headers: {
          Authorization: "Bearer TU_MCP_API_KEY_AQUI"
        }
      },
      "vps-mcp-unified": {
        url: `${origin}/unified/sse`,
        headers: {
          Authorization: "Bearer TU_MCP_API_KEY_AQUI"
        }
      }
    }
  };
  document.getElementById("snippet-cursor").innerText = JSON.stringify(cursorConfig, null, 2);

  const webuiConfig = {
    name: "VPS MCP Gateway",
    endpoint: `http://mcp-gateway:8000/unified/sse`,
    type: "sse",
    auth: "Bearer TU_MCP_API_KEY_AQUI"
  };
  document.getElementById("snippet-webui").innerText = JSON.stringify(webuiConfig, null, 2);
}

document.querySelectorAll(".copy-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    const targetId = btn.getAttribute("data-target");
    const text = document.getElementById(targetId).innerText;
    navigator.clipboard.writeText(text).then(() => {
      showToast("Snippet copiado al portapapeles", "success");
    });
  });
});

// --- Audit Logs ---
async function loadLogs() {
  const tbody = document.getElementById("logs-tbody");
  tbody.innerHTML = "<tr><td colspan='5' class='text-center'>Cargando registros...</td></tr>";

  try {
    const res = await apiFetch("/api/admin/logs");
    const logs = await res.json();
    if (!logs || logs.length === 0) {
      tbody.innerHTML = "<tr><td colspan='5' class='text-center'>No hay actividad registrada aún.</td></tr>";
      return;
    }
    tbody.innerHTML = "";
    logs.forEach(log => {
      const tr = document.createElement("tr");
      const statusClass = log.status === "success" ? "text-success" : (log.status === "error" ? "text-danger" : "");
      tr.innerHTML = `
        <td>${log.timestamp}</td>
        <td><span class="badge badge-accent">${log.service}</span></td>
        <td><code>${log.action}</code></td>
        <td class="${statusClass}"><b>${log.status}</b></td>
        <td>${log.details || "-"}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan='5' class='text-center text-error'>Error: ${err.message}</td></tr>`;
  }
}

document.getElementById("btn-refresh-services").addEventListener("click", loadServices);
document.getElementById("btn-refresh-logs").addEventListener("click", loadLogs);

// --- Initialization ---
function loadInitialData() {
  loadServices();
}

// Auto-login check on page load
window.addEventListener("DOMContentLoaded", () => {
  if (currentToken) {
    document.getElementById("login-modal").classList.remove("active");
    document.getElementById("app-layout").classList.remove("hidden");
    loadInitialData();
  } else {
    document.getElementById("login-modal").classList.add("active");
  }
});
