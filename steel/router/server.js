/**
 * Steel Browser Router (3 workers fijos)
 *
 * Modelo real de Steel auto-hospedado (v0.5.x): 1 sesión = 1 navegador = 1 instancia.
 * Este router reparte cada sesión nueva a una instancia LIBRE (0 sesiones activas)
 * y enruta después todo el tráfico (HTTP, CDP y Live Viewer) a la instancia dueña.
 *
 * Garantías:
 *  1. Sin acceso a Docker: el router es un proxy puro (no monta docker.sock).
 *  2. Creación de sesiones SERIALIZADA: evita que dos creaciones simultáneas
 *     caigan en la misma instancia (SingletonLock de Chromium).
 *  3. Reintento automático: si una instancia está degradada (launch_failed),
 *     prueba con la siguiente libre.
 *  4. Si las 3 instancias están ocupadas responde 503 (NUNCA desplaza una sesión viva).
 *
 * El reciclado de instancias (limpiar SingletonLock/zombies) lo hace el host
 * vía scripts/recycle_workers.sh (cron), no el router.
 */

const http = require('http');
const net = require('net');
const fs = require('fs');
const path = require('path');
const { URL } = require('url');

let DASHBOARD_HTML = '';
try {
  DASHBOARD_HTML = fs.readFileSync(path.join(__dirname, 'dashboard.html'), 'utf8');
} catch (e) {
  console.warn('[router] Could not pre-load dashboard.html:', e.message);
}

const PORT = parseInt(process.env.PORT || '3000', 10);
const STEEL_API_KEY = process.env.STEEL_API_KEY || '';

const BACKENDS = [
  { id: 'steel-1', name: 'steel-browser-1', url: 'http://steel-1:3000', isPrimary: true },
  { id: 'steel-2', name: 'steel-browser-2', url: 'http://steel-2:3000', isPrimary: false },
  { id: 'steel-3', name: 'steel-browser-3', url: 'http://steel-3:3000', isPrimary: false },
];

// Map sessionId -> backendUrl
const sessionMap = new Map();

/* -------------------------------------------------------------
 * Backend HTTP helpers
 * ------------------------------------------------------------- */
function queryBackend(backendUrl, path, method = 'GET', data = null, headers = {}, timeoutMs = 4000) {
  return new Promise((resolve) => {
    try {
      const u = new URL(path, backendUrl);
      const reqHeaders = { ...headers, Connection: 'close', host: 'localhost:3000' };
      if (STEEL_API_KEY && !reqHeaders['x-steel-api-key']) {
        reqHeaders['x-steel-api-key'] = STEEL_API_KEY;
      }
      let payload = null;
      if (data) {
        payload = typeof data === 'string' ? data : JSON.stringify(data);
        reqHeaders['Content-Type'] = reqHeaders['Content-Type'] || 'application/json';
        reqHeaders['Content-Length'] = Buffer.byteLength(payload);
      }
      const req = http.request({
        hostname: u.hostname,
        port: parseInt(u.port, 10),
        path: u.pathname + u.search,
        method: method,
        headers: reqHeaders,
        timeout: timeoutMs
      }, (res) => {
        let body = '';
        res.on('data', chunk => body += chunk);
        res.on('end', () => {
          try {
            resolve({ statusCode: res.statusCode, data: JSON.parse(body), headers: res.headers });
          } catch (e) {
            resolve({ statusCode: res.statusCode, data: body, headers: res.headers });
          }
        });
      });
      req.on('error', () => resolve(null));
      req.on('timeout', () => { req.destroy(); resolve(null); });
      if (payload) req.write(payload);
      req.end();
    } catch (e) {
      resolve(null);
    }
  });
}

// Steel mantiene SIEMPRE una sesión "placeholder" en estado `idle` (navegador base).
// Solo el estado `live` ocupa la instancia; `idle`/`released`/`failed` = libre.
function isActiveSession(s) {
  return !!s && s.status === 'live';
}

async function getBackendState(b) {
  const res = await queryBackend(b.url, '/v1/sessions');
  if (!res || res.statusCode !== 200 || !res.data || !Array.isArray(res.data.sessions)) {
    return { reachable: false, active: 0 };
  }
  return { reachable: true, active: res.data.sessions.filter(isActiveSession).length };
}

/**
 * Devuelve la primera instancia LIBRE (primary primero) de las no excluidas.
 * Libre = responde y tiene 0 sesiones activas (1 sesión por instancia).
 */
async function selectFreeBackend(exclude = new Set()) {
  const ordered = [
    BACKENDS.find(b => b.isPrimary),
    ...BACKENDS.filter(b => !b.isPrimary)
  ].filter(Boolean);

  for (const b of ordered) {
    if (exclude.has(b.url)) continue;
    const st = await getBackendState(b);
    if (st.reachable && st.active === 0) return b;
  }
  return null;
}

/* -------------------------------------------------------------
 * Create lock (serializa POST /v1/sessions)
 * ------------------------------------------------------------- */
let createQueue = Promise.resolve();
function withCreateLock(fn) {
  const run = createQueue.then(fn, fn);
  createQueue = run.then(() => {}, () => {});
  return run;
}

function readRequestBody(req) {
  return new Promise((resolve) => {
    const chunks = [];
    req.on('data', c => chunks.push(c));
    req.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
    req.on('error', () => resolve(''));
  });
}

/* -------------------------------------------------------------
 * Session id extraction
 * ------------------------------------------------------------- */
const UUID_REGEX = /([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})/;

function extractSessionId(reqUrl, headers = {}) {
  try {
    const parsed = new URL(reqUrl, 'http://localhost');
    const qSid = parsed.searchParams.get('sessionId') || parsed.searchParams.get('session_id') || parsed.searchParams.get('id');
    if (qSid) {
      const m = qSid.match(UUID_REGEX);
      if (m) return m[1];
    }
    const match = parsed.pathname.match(UUID_REGEX);
    if (match) return match[1];

    if (headers && headers.referer) {
      const refUrl = new URL(headers.referer, 'http://localhost');
      const refSid = refUrl.searchParams.get('sessionId') || refUrl.searchParams.get('session_id') || refUrl.searchParams.get('id');
      if (refSid) {
        const m = refSid.match(UUID_REGEX);
        if (m) return m[1];
      }
      const refMatch = refUrl.pathname.match(UUID_REGEX);
      if (refMatch) return refMatch[1];
    }

    if (headers && headers.cookie) {
      const cMatch = headers.cookie.match(/steel_sid=([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})/);
      if (cMatch) return cMatch[1];
    }

    if (headers && headers['x-steel-session-id']) {
      const hMatch = headers['x-steel-session-id'].match(UUID_REGEX);
      if (hMatch) return hMatch[1];
    }
  } catch (e) {}
  return null;
}

async function findSessionOwner(sessionId) {
  if (sessionMap.has(sessionId)) return sessionMap.get(sessionId);

  for (const b of BACKENDS) {
    const res = await queryBackend(b.url, '/v1/sessions');
    if (res && res.data && Array.isArray(res.data.sessions)) {
      const found = res.data.sessions.some(s => s.id === sessionId && isActiveSession(s));
      if (found) {
        sessionMap.set(sessionId, b.url);
        return b.url;
      }
    }
  }
  return null;
}

function proxyHttpRequest(targetBackendUrl, req, res, onResponseJson = null) {
  const target = new URL(req.url, targetBackendUrl);
  const forwardHeaders = { ...req.headers };
  forwardHeaders.host = 'localhost:3000';
  forwardHeaders.connection = 'close';

  const proxyReq = http.request({
    hostname: target.hostname,
    port: parseInt(target.port, 10),
    path: target.pathname + target.search,
    method: req.method,
    headers: forwardHeaders
  }, (proxyRes) => {
    if (onResponseJson) {
      let body = '';
      proxyRes.on('data', chunk => body += chunk);
      proxyRes.on('end', () => {
        try {
          const json = JSON.parse(body);
          onResponseJson(json);
        } catch (e) {}
        res.writeHead(proxyRes.statusCode, proxyRes.headers);
        res.end(body);
      });
    } else {
      res.writeHead(proxyRes.statusCode, proxyRes.headers);
      proxyRes.pipe(res);
    }
  });

  proxyReq.on('error', (err) => {
    console.error(`[router] Proxy HTTP Error to ${targetBackendUrl}:`, err.message);
    if (!res.headersSent) {
      res.writeHead(502, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Bad Gateway in Steel Router', details: err.message }));
    }
  });

  req.pipe(proxyReq);
}

/* -------------------------------------------------------------
 * HTTP server
 * ------------------------------------------------------------- */
const server = http.createServer(async (req, res) => {
  const reqUrl = req.url || '/';
  const sid = extractSessionId(reqUrl);

  // 1. Health check & pool status
  if (reqUrl === '/healthz' || reqUrl === '/router/health') {
    const statusList = [];
    for (const b of BACKENDS) {
      const st = await getBackendState(b);
      const mapped = [...sessionMap.values()].filter(u => u === b.url).length;
      statusList.push({
        id: b.id,
        name: b.name,
        running: st.reachable,
        activeSessions: st.active,
        mappedSessions: mapped,
        isPrimary: b.isPrimary
      });
    }
    res.writeHead(200, { 'Content-Type': 'application/json' });
    return res.end(JSON.stringify({
      status: 'ok',
      mode: '3-fixed-workers (1 session per worker)',
      pool: statusList,
      totalMappedSessions: sessionMap.size
    }));
  }

  // 2. Dashboard on / and /ui
  if (req.method === 'GET' && (reqUrl === '/' || reqUrl === '/ui' || reqUrl === '/ui/')) {
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    return res.end(DASHBOARD_HTML);
  }

  // 3. Proxy to native Steel UI on /native-ui
  if (reqUrl.startsWith('/native-ui')) {
    req.url = reqUrl.replace(/^\/native-ui/, '/ui');
    return proxyHttpRequest(BACKENDS[0].url, req, res);
  }

  // 4. Global session aggregation: GET /v1/sessions
  if (req.method === 'GET' && (reqUrl === '/v1/sessions' || reqUrl.startsWith('/v1/sessions?'))) {
    const results = await Promise.all(
      BACKENDS.map(b => queryBackend(b.url, reqUrl, 'GET', null, req.headers))
    );
    const aggregated = [];
    for (const r of results) {
      if (r && r.data && Array.isArray(r.data.sessions)) {
        for (const s of r.data.sessions) {
          if (s.debugUrl && !s.debugUrl.includes('sessionId=')) {
            s.debugUrl += `${s.debugUrl.includes('?') ? '&' : '?'}sessionId=${s.id}`;
          }
          if (s.debuggerUrl && !s.debuggerUrl.includes('sessionId=')) {
            s.debuggerUrl += `${s.debuggerUrl.includes('?') ? '&' : '?'}sessionId=${s.id}`;
          }
          s.activeInPool = sessionMap.has(s.id);
          aggregated.push(s);
        }
      }
    }
    res.writeHead(200, { 'Content-Type': 'application/json', Connection: 'close' });
    return res.end(JSON.stringify({ sessions: aggregated }));
  }

  // 5. New session creation: POST /v1/sessions (serializado + reintento)
  if (req.method === 'POST' && (reqUrl === '/v1/sessions' || reqUrl.startsWith('/v1/sessions?'))) {
    return withCreateLock(async () => {
      let body = '';
      try { body = await readRequestBody(req); } catch (e) {}

      const tried = new Set();
      const errors = [];

      for (let i = 0; i < BACKENDS.length; i++) {
        const backend = await selectFreeBackend(tried);
        if (!backend) break;
        tried.add(backend.url);

        const r = await queryBackend(backend.url, reqUrl, 'POST', body || null, req.headers, 90000);
        if (r && r.statusCode >= 200 && r.statusCode < 300 && r.data && r.data.id) {
          sessionMap.set(r.data.id, backend.url);
          console.log(`[router] Mapped session ${r.data.id} -> ${backend.url}`);
          res.writeHead(200, { 'Content-Type': 'application/json', Connection: 'close' });
          return res.end(typeof r.data === 'string' ? r.data : JSON.stringify(r.data));
        }

        const msg = (r && r.data && r.data.message)
          ? String(r.data.message).slice(0, 240)
          : `HTTP ${r ? r.statusCode : 'sin respuesta'}`;
        errors.push(`${backend.name}: ${msg}`);
        console.error(`[router] Create failed on ${backend.name}: ${msg}`);
      }

      if (tried.size === 0) {
        res.writeHead(503, { 'Content-Type': 'application/json' });
        return res.end(JSON.stringify({
          error: 'Steel pool ocupado',
          message: `Las ${BACKENDS.length} instancias tienen una sesión activa. Libera una y reintenta.`,
          pool: BACKENDS.length
        }));
      }

      res.writeHead(502, { 'Content-Type': 'application/json' });
      return res.end(JSON.stringify({
        error: 'Sin instancias Steel utilizables',
        message: 'Todas las instancias libres fallaron al lanzar el navegador (posible SingletonLock). El reciclado automático las reiniciará.',
        details: errors
      }));
    });
  }

  // 6. Debug viewer & DevTools security check (Capability Token)
  const isDebugView = reqUrl.startsWith('/v1/sessions/debug');
  const isDevtools = reqUrl.startsWith('/v1/devtools');

  if (isDebugView || isDevtools) {
    if (!sid) {
      res.writeHead(403, { 'Content-Type': 'text/html; charset=utf-8' });
      return res.end(`<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>403 Acceso Denegado</title><style>body{font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;background:#0f172a;color:#f8fafc;}.card{background:#1e293b;padding:2.5rem;border-radius:12px;box-shadow:0 10px 25px rgba(0,0,0,0.5);text-align:center;max-width:480px;}h1{color:#ef4444;margin-top:0;}p{color:#94a3b8;line-height:1.5;}code{background:#334155;padding:2px 6px;border-radius:4px;color:#38bdf8;}</style></head><body><div class="card"><h1>🔒 403 Prohibido</h1><p>Se requiere un identificador de sesión activo (<code>?sessionId=UUID</code>) para ver el navegador en vivo.</p></div></body></html>`);
    }

    let targetBackend = sessionMap.get(sid);
    if (targetBackend) {
      const res2 = await queryBackend(targetBackend, '/v1/sessions');
      const active = res2 && res2.data && Array.isArray(res2.data.sessions)
        && res2.data.sessions.some(s => s.id === sid && isActiveSession(s));
      if (!active) {
        sessionMap.delete(sid);
        targetBackend = null;
      }
    }

    if (!targetBackend) {
      targetBackend = await findSessionOwner(sid);
    }

    if (!targetBackend) {
      res.writeHead(404, { 'Content-Type': 'text/html; charset=utf-8' });
      return res.end(`<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>404 Sesión No Encontrada</title><style>body{font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;background:#0f172a;color:#f8fafc;}.card{background:#1e293b;padding:2.5rem;border-radius:12px;box-shadow:0 10px 25px rgba(0,0,0,0.5);text-align:center;max-width:480px;}h1{color:#f59e0b;margin-top:0;}p{color:#94a3b8;line-height:1.5;}code{background:#334155;padding:2px 6px;border-radius:4px;color:#38bdf8;}</style></head><body><div class="card"><h1>⚠️ Sesión No Encontrada</h1><p>La sesión <code>${sid}</code> no existe o ya ha sido liberada.</p></div></body></html>`);
    }

    res.setHeader('Set-Cookie', `steel_sid=${sid}; Path=/; HttpOnly; SameSite=Lax`);
    return proxyHttpRequest(targetBackend, req, res);
  }

  // 7. Session-specific requests (by ID)
  if (sid) {
    let targetBackend = sessionMap.get(sid);
    if (!targetBackend) {
      targetBackend = await findSessionOwner(sid);
    }

    if (targetBackend) {
      const isRelease = req.method === 'POST' && reqUrl.includes('/release');
      return proxyHttpRequest(targetBackend, req, res, (resJson) => {
        if (isRelease && resJson && resJson.success) {
          sessionMap.delete(sid);
          console.log(`[router] Unmapped released session ${sid}`);
        } else if (resJson && resJson.id) {
          if (resJson.debugUrl && !resJson.debugUrl.includes('sessionId=')) {
            resJson.debugUrl += `${resJson.debugUrl.includes('?') ? '&' : '?'}sessionId=${resJson.id}`;
          }
          if (resJson.debuggerUrl && !resJson.debuggerUrl.includes('sessionId=')) {
            resJson.debuggerUrl += `${resJson.debuggerUrl.includes('?') ? '&' : '?'}sessionId=${resJson.id}`;
          }
        }
      });
    }
  }

  // 8. Default fallback to primary backend
  const defaultBackend = BACKENDS[0].url;
  return proxyHttpRequest(defaultBackend, req, res);
});

// WebSocket / Upgrade proxying
server.on('upgrade', async (req, clientSocket, head) => {
  const sid = extractSessionId(req.url || '', req.headers);
  const isCast = (req.url || '').includes('/cast') || (req.url || '').includes('/devtools') || (req.url || '').includes('/ws');

  if (isCast && !sid) {
    clientSocket.write('HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\nMissing sessionId for live stream');
    return clientSocket.destroy();
  }

  let targetBackend = sid ? (sessionMap.get(sid) || await findSessionOwner(sid)) : null;

  if (isCast && !targetBackend) {
    clientSocket.write('HTTP/1.1 404 Not Found\r\nConnection: close\r\n\r\nSession not found or expired');
    return clientSocket.destroy();
  }

  if (!targetBackend) targetBackend = BACKENDS[0].url;

  try {
    const target = new URL(req.url, targetBackend);
    const targetPort = parseInt(target.port, 10);
    const targetHost = target.hostname;

    const serverSocket = net.connect({ host: targetHost, port: targetPort }, () => {
      let handshake = `${req.method} ${target.pathname}${target.search} HTTP/${req.httpVersion}\r\n`;
      for (let i = 0; i < req.rawHeaders.length; i += 2) {
        const key = req.rawHeaders[i];
        const val = req.rawHeaders[i + 1];
        if (key.toLowerCase() === 'host') {
          handshake += `Host: localhost:3000\r\n`;
        } else {
          handshake += `${key}: ${val}\r\n`;
        }
      }
      handshake += '\r\n';

      serverSocket.write(handshake);
      if (head && head.length > 0) {
        serverSocket.write(head);
      }

      clientSocket.pipe(serverSocket);
      serverSocket.pipe(clientSocket);
    });

    serverSocket.on('error', (e) => {
      console.error(`[router] WS ServerSocket error (${targetBackend}):`, e.message);
      clientSocket.destroy();
    });

    clientSocket.on('error', (e) => {
      console.error(`[router] WS ClientSocket error:`, e.message);
      serverSocket.destroy();
    });
  } catch (e) {
    console.error(`[router] Error handling upgrade:`, e.message);
    clientSocket.destroy();
  }
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`=======================================================`);
  console.log(`🚀 Steel Router listening on 0.0.0.0:${PORT}`);
  console.log(`🧩 Mode: 3 fixed workers, 1 session per worker`);
  console.log(`🔒 No Docker socket access (pure proxy)`);
  console.log(`⏳ Session creates are serialized with retry`);
  console.log(`=======================================================`);
});
