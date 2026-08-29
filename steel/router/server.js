/**
 * Steel Browser Smart Session Router
 * 
 * Multiplexes incoming HTTP & WebSocket requests across a pool of isolated Steel Browser containers.
 * Maintains session stickiness so each session ID communicates exclusively with its dedicated container.
 * Seamlessly integrates with Nginx reverse proxy on browser.jeisson.top.
 */

const http = require('http');
const net = require('net');
const { URL } = require('url');

const PORT = parseInt(process.env.PORT || '3000', 10);
const BACKENDS = (process.env.POOL_BACKENDS || 'http://steel-1:3000,http://steel-2:3000')
  .split(',')
  .map(b => b.trim())
  .filter(Boolean);

const STEEL_API_KEY = process.env.STEEL_API_KEY || '';

// Map sessionId -> backendUrl
const sessionMap = new Map();

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
      const reqHeaders = { ...headers, Connection: 'close' };
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
        timeout: 5000
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

  for (const backend of BACKENDS) {
    const res = await queryBackend(backend, '/v1/sessions');
    if (res && res.data && Array.isArray(res.data.sessions)) {
      const found = res.data.sessions.some(s => s.id === sessionId);
      if (found) {
        sessionMap.set(sessionId, backend);
        return backend;
      }
    }
  }
  return null;
}

let roundRobinIndex = 0;

async function selectBestBackend() {
  // Count active sessions currently mapped in the router for each backend
  const backendLoads = new Map(BACKENDS.map(b => [b, 0]));
  for (const backend of sessionMap.values()) {
    if (backendLoads.has(backend)) {
      backendLoads.set(backend, backendLoads.get(backend) + 1);
    }
  }

  // Find minimum load
  let minLoad = Infinity;
  for (const load of backendLoads.values()) {
    if (load < minLoad) minLoad = load;
  }

  const candidates = BACKENDS.filter(b => backendLoads.get(b) === minLoad);
  roundRobinIndex = (roundRobinIndex + 1) % candidates.length;
  const chosen = candidates[roundRobinIndex];
  console.log(`[router] Current pool loads:`, Object.fromEntries(backendLoads), `-> Selected: ${chosen}`);
  return chosen;
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

  // 1. Health check for router
  if (reqUrl === '/healthz' || reqUrl === '/router/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    return res.end(JSON.stringify({ status: 'ok', backends: BACKENDS, mappedSessions: sessionMap.size }));
  }

  // 2. Global session list aggregation: GET /v1/sessions
  if (req.method === 'GET' && (reqUrl === '/v1/sessions' || reqUrl.startsWith('/v1/sessions?'))) {
    const promises = BACKENDS.map(b => queryBackend(b, reqUrl, 'GET', null, req.headers));
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
    console.log(`[router] Dispatching new session creation to ${chosenBackend}`);
    return proxyHttpRequest(chosenBackend, req, res, (resJson) => {
      if (resJson && resJson.id) {
        sessionMap.set(resJson.id, chosenBackend);
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
      // Check if session release
      const isRelease = req.method === 'POST' && reqUrl.includes('/release');
      return proxyHttpRequest(targetBackend, req, res, (resJson) => {
        if (isRelease && resJson && resJson.success) {
          sessionMap.delete(sid);
          console.log(`[router] Unmapped released session ${sid}`);
        }
      });
    }
  }

  // 5. Default fallback to primary backend (for root assets, static pages)
  const defaultBackend = BACKENDS[0];
  return proxyHttpRequest(defaultBackend, req, res);
});

// WebSocket / Upgrade proxying
server.on('upgrade', async (req, clientSocket, head) => {
  const sid = extractSessionId(req.url || '');
  let targetBackend = sid ? (sessionMap.get(sid) || await findSessionOwner(sid)) : BACKENDS[0];
  if (!targetBackend) targetBackend = BACKENDS[0];

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
  console.log(`🚀 Steel Session Router listening on 0.0.0.0:${PORT}`);
  console.log(`📦 Configured backends: ${BACKENDS.join(', ')}`);
  console.log(`=======================================================`);
});
