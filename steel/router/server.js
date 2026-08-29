/**
 * Steel Browser Smart Elastic Router & Auto-Scaler
 * 
 * Features:
 * 1. Scale-to-One Architecture: Maintains 1 fixed primary container (steel-1) for zero-latency response.
 * 2. On-Demand Scaling: Automatically starts elastic workers (steel-2, steel-3) via Docker socket when load requires it.
 * 3. Auto-Shutdown: Automatically stops secondary workers after idle timeout (default: 3 minutes) to free RAM.
 * 4. Session Stickiness: Seamlessly routes HTTP and WebSockets (CDP + Live Viewer) to the assigned container.
 */

const http = require('http');
const net = require('net');
const { URL } = require('url');

const PORT = parseInt(process.env.PORT || '3000', 10);
const STEEL_API_KEY = process.env.STEEL_API_KEY || '';
const IDLE_TIMEOUT_SEC = parseInt(process.env.IDLE_TIMEOUT_SEC || '180', 10); // 3 minutes

const BACKENDS = [
  { id: 'steel-1', name: 'steel-browser-1', url: 'http://steel-1:3000', isPrimary: true, idleSince: null },
  { id: 'steel-2', name: 'steel-browser-2', url: 'http://steel-2:3000', isPrimary: false, idleSince: Date.now() },
  { id: 'steel-3', name: 'steel-browser-3', url: 'http://steel-3:3000', isPrimary: false, idleSince: Date.now() },
];

// Map sessionId -> backendUrl
const sessionMap = new Map();

/* -------------------------------------------------------------
 * Docker Engine API Helpers (via UNIX socket)
 * ------------------------------------------------------------- */
function dockerApi(path, method = 'GET') {
  return new Promise((resolve) => {
    const req = http.request({
      socketPath: '/var/run/docker.sock',
      path: path,
      method: method,
      timeout: 15000
    }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          resolve({ status: res.statusCode, data: JSON.parse(data) });
        } catch (e) {
          resolve({ status: res.statusCode, data });
        }
      });
    });
    req.on('error', (err) => resolve({ status: 500, error: err.message }));
    req.on('timeout', () => { req.destroy(); resolve({ status: 504, error: 'timeout' }); });
    req.end();
  });
}

async function isContainerRunning(containerName) {
  const res = await dockerApi(`/v1.43/containers/${containerName}/json`);
  if (res && res.data && res.data.State) {
    return res.data.State.Running === true;
  }
  return false;
}

async function startContainer(containerName) {
  console.log(`[scaler] ⚡ Starting elastic worker container ${containerName}...`);
  const res = await dockerApi(`/v1.43/containers/${containerName}/start`, 'POST');
  return res.status === 204 || res.status === 304;
}

async function stopContainer(containerName) {
  console.log(`[scaler] 💤 Stopping idle worker container ${containerName}...`);
  const res = await dockerApi(`/v1.43/containers/${containerName}/stop?t=3`, 'POST');
  return res.status === 204 || res.status === 304;
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function waitForBackendReady(backendUrl, maxWaitMs = 12000) {
  const startTime = Date.now();
  while (Date.now() - startTime < maxWaitMs) {
    const res = await queryBackend(backendUrl, '/v1/sessions');
    if (res && res.statusCode === 200) {
      return true;
    }
    await sleep(400);
  }
  return false;
}

/* -------------------------------------------------------------
 * HTTP & WebSocket Backend Communication
 * ------------------------------------------------------------- */
function extractSessionId(reqUrl) {
  try {
    const parsed = new URL(reqUrl, 'http://localhost');
    const qSid = parsed.searchParams.get('sessionId');
    if (qSid) return qSid;
    const match = parsed.pathname.match(/\/sessions\/([0-9a-fA-F-]+)/);
    if (match) return match[1];
  } catch (e) {}
  return null;
}

function queryBackend(backendUrl, path, method = 'GET', data = null, headers = {}) {
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
        timeout: 4000
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

async function findSessionOwner(sessionId) {
  if (sessionMap.has(sessionId)) return sessionMap.get(sessionId);

  for (const b of BACKENDS) {
    const running = await isContainerRunning(b.name);
    if (!running) continue;
    const res = await queryBackend(b.url, '/v1/sessions');
    if (res && res.data && Array.isArray(res.data.sessions)) {
      const found = res.data.sessions.some(s => s.id === sessionId);
      if (found) {
        sessionMap.set(sessionId, b.url);
        b.idleSince = null;
        return b.url;
      }
    }
  }
  return null;
}

/**
 * Intelligent Backend Dispatcher with Scale-to-One
 */
async function selectBestBackend() {
  // Count actively mapped sessions for each backend
  const loads = new Map(BACKENDS.map(b => [b.url, 0]));
  for (const backendUrl of sessionMap.values()) {
    if (loads.has(backendUrl)) {
      loads.set(backendUrl, loads.get(backendUrl) + 1);
    }
  }

  // 1. Prefer primary backend (steel-1) if it has 0 active sessions
  const primary = BACKENDS.find(b => b.isPrimary);
  if (primary && loads.get(primary.url) === 0) {
    primary.idleSince = null;
    return primary.url;
  }

  // 2. If primary is busy, look for an available elastic secondary worker
  for (const b of BACKENDS) {
    if (b.isPrimary) continue;

    if (loads.get(b.url) === 0) {
      // Check if container is running; if not, spin it up on-demand!
      const running = await isContainerRunning(b.name);
      if (!running) {
        console.log(`[scaler] Primary container busy. Booting elastic worker ${b.name}...`);
        await startContainer(b.name);
        const ready = await waitForBackendReady(b.url);
        if (!ready) {
          console.error(`[scaler] Worker ${b.name} failed to become ready in time`);
          continue;
        }
      }
      b.idleSince = null;
      console.log(`[scaler] Dispatched to elastic worker ${b.name}`);
      return b.url;
    }
  }

  // 3. If all backends are already in use, pick backend with minimum load
  let minLoad = Infinity;
  let chosenUrl = primary ? primary.url : BACKENDS[0].url;
  for (const [url, load] of loads.entries()) {
    if (load < minLoad) {
      minLoad = load;
      chosenUrl = url;
    }
  }

  return chosenUrl;
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

const server = http.createServer(async (req, res) => {
  const reqUrl = req.url || '/';
  const sid = extractSessionId(reqUrl);

  // 1. Health check & Pool status
  if (reqUrl === '/healthz' || reqUrl === '/router/health') {
    const statusList = [];
    for (const b of BACKENDS) {
      const running = await isContainerRunning(b.name);
      const activeCount = [...sessionMap.values()].filter(u => u === b.url).length;
      statusList.push({ id: b.id, name: b.name, running, activeSessions: activeCount, isPrimary: b.isPrimary });
    }
    res.writeHead(200, { 'Content-Type': 'application/json' });
    return res.end(JSON.stringify({
      status: 'ok',
      pool: statusList,
      totalMappedSessions: sessionMap.size,
      idleTimeoutSec: IDLE_TIMEOUT_SEC
    }));
  }

  // 2. Global session aggregation: GET /v1/sessions
  if (req.method === 'GET' && (reqUrl === '/v1/sessions' || reqUrl.startsWith('/v1/sessions?'))) {
    const promises = BACKENDS.map(async (b) => {
      const running = await isContainerRunning(b.name);
      if (!running) return null;
      return queryBackend(b.url, reqUrl, 'GET', null, req.headers);
    });
    const results = await Promise.all(promises);
    const aggregated = [];
    for (const r of results) {
      if (r && r.data && Array.isArray(r.data.sessions)) {
        aggregated.push(...r.data.sessions);
      }
    }
    res.writeHead(200, { 'Content-Type': 'application/json', Connection: 'close' });
    return res.end(JSON.stringify({ sessions: aggregated }));
  }

  // 3. New session creation: POST /v1/sessions
  if (req.method === 'POST' && (reqUrl === '/v1/sessions' || reqUrl.startsWith('/v1/sessions?'))) {
    const chosenBackend = await selectBestBackend();
    return proxyHttpRequest(chosenBackend, req, res, (resJson) => {
      if (resJson && resJson.id) {
        sessionMap.set(resJson.id, chosenBackend);
        const bObj = BACKENDS.find(b => b.url === chosenBackend);
        if (bObj) bObj.idleSince = null;
        console.log(`[router] Mapped session ${resJson.id} -> ${chosenBackend}`);
      }
    });
  }

  // 4. Session-specific requests (by ID)
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
          const bObj = BACKENDS.find(b => b.url === targetBackend);
          if (bObj && !bObj.isPrimary) {
            const remaining = [...sessionMap.values()].filter(u => u === targetBackend).length;
            if (remaining === 0) bObj.idleSince = Date.now();
          }
          console.log(`[router] Unmapped released session ${sid}`);
        }
      });
    }
  }

  // 5. Default fallback to primary backend
  const defaultBackend = BACKENDS[0].url;
  return proxyHttpRequest(defaultBackend, req, res);
});

// WebSocket / Upgrade proxying
server.on('upgrade', async (req, clientSocket, head) => {
  const sid = extractSessionId(req.url || '');
  let targetBackend = sid ? (sessionMap.get(sid) || await findSessionOwner(sid)) : BACKENDS[0].url;
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

/* -------------------------------------------------------------
 * Background Elastic Reaper (Auto-Shutdown of Idle Workers)
 * ------------------------------------------------------------- */
async function runElasticReaper() {
  for (const b of BACKENDS) {
    if (b.isPrimary) continue; // Never stop steel-1

    const activeCount = [...sessionMap.values()].filter(u => u === b.url).length;
    if (activeCount > 0) {
      b.idleSince = null;
      continue;
    }

    if (!b.idleSince) {
      b.idleSince = Date.now();
      continue;
    }

    const idleSeconds = Math.round((Date.now() - b.idleSince) / 1000);
    if (idleSeconds >= IDLE_TIMEOUT_SEC) {
      const running = await isContainerRunning(b.name);
      if (running) {
        console.log(`[reaper] 💤 Worker ${b.name} has been idle for ${idleSeconds}s >= ${IDLE_TIMEOUT_SEC}s. Auto-stopping...`);
        await stopContainer(b.name);
        console.log(`[reaper] 🛑 Worker ${b.name} stopped. RAM liberated!`);
      }
    }
  }
}

// Run reaper check every 20 seconds
setInterval(runElasticReaper, 20000);

server.listen(PORT, '0.0.0.0', async () => {
  console.log(`=======================================================`);
  console.log(`🚀 Steel Elastic Router listening on 0.0.0.0:${PORT}`);
  console.log(`🛡️  Fixed Primary: ${BACKENDS[0].name} (Always ON)`);
  console.log(`⚡ Elastic Workers: steel-browser-2, steel-browser-3 (On-Demand)`);
  console.log(`⏱️  Auto-shutdown idle timeout: ${IDLE_TIMEOUT_SEC}s`);
  console.log(`=======================================================`);

  // On boot, stop any idle elastic workers to immediately save RAM
  setTimeout(runElasticReaper, 5000);
});
