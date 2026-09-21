#!/usr/bin/env node

/**
 * Steel Browser MCP Wrapper for Playwright
 * Dynamically creates an isolated browser session via Steel API (port 3000)
 * and passes the dedicated session WebSocket endpoint to @playwright/mcp.
 *
 * Supports two distinct modes:
 *  1. Ephemeral (--isolated):
 *     Creates a completely fresh, in-memory browser session. Releases on exit.
 *  2. Persistent (--persistent, --user-data-dir, default):
 *     Loads existing profile state (cookies, localStorage, etc.) from disk,
 *     spawns an independent session preloaded with user logins, and on exit
 *     syncs updated state back to disk before releasing the session.
 *
 * Session lifecycle (leases):
 *  - The Steel session is created with a rolling lease (`x-steel-lease-ttl`).
 *  - While there is MCP activity, this wrapper sends periodic heartbeats that
 *    renew the lease; when the client stays idle past STEEL_ACTIVE_WINDOW_SEC
 *    the heartbeats stop and the router releases the session automatically.
 *  - On the next tool call, if the session is gone, the wrapper transparently
 *    creates a replacement session and re-spawns the upstream Playwright MCP,
 *    so the agent/user never has to manage this manually.
 *  - Persistent profiles are synced to disk periodically, so an automatic
 *    (non-graceful) release loses at most STEEL_CONTEXT_SYNC_SEC of cookies.
 *
 * MCP proxy layer:
 * The wrapper sits between OpenCode and the real @playwright/mcp process so it
 * can inject one extra tool, `steel_get_session_info`, which reports the exact
 * Steel session this MCP connection is driving right now.
 */

const http = require('http');
const { spawn } = require('child_process');
const path = require('path');
const os = require('os');
const fs = require('fs');
const { mergeAndWriteContext } = require('./context-merge');

// 1. Resolve environment variables
const homeDir = os.homedir();
let steelApiKey = process.env.STEEL_API_KEY || '';
let steelDomain = process.env.STEEL_DOMAIN || '';
let useSsl = process.env.USE_SSL === 'false' ? false : true;
const STEEL_PORT = process.env.STEEL_PORT || '3000';

function envInt(name, def) {
  const n = parseInt(process.env[name], 10);
  return Number.isFinite(n) && n >= 0 ? n : def;
}
let leaseTtlSec = envInt('STEEL_LEASE_TTL_SEC', 300);
let activeWindowSec = envInt('STEEL_ACTIVE_WINDOW_SEC', 1800);
let heartbeatIntervalSec = envInt('STEEL_HEARTBEAT_INTERVAL_SEC', 60);
let contextSyncSec = envInt('STEEL_CONTEXT_SYNC_SEC', 300);

// Allow requiring modules installed alongside OpenCode's own MCP servers
// (e.g. @modelcontextprotocol/sdk, which ships as a dependency of @playwright/mcp).
const opencodeModules = path.join(homeDir, '.config/opencode/node_modules');
if (fs.existsSync(opencodeModules) && !module.paths.includes(opencodeModules)) {
  module.paths.unshift(opencodeModules);
}

const possibleEnvPaths = [
  path.join(homeDir, 'vps-tools/steel/.env'),
  path.resolve(__dirname, '../.env'),
  path.resolve(__dirname, '../../steel/.env')
];

for (const envPath of possibleEnvPaths) {
  if (fs.existsSync(envPath)) {
    const envContent = fs.readFileSync(envPath, 'utf8');
    if (!steelApiKey) {
      const matchKey = envContent.match(/^STEEL_API_KEY=(.*)$/m);
      if (matchKey) steelApiKey = matchKey[1].trim().replace(/^["']|["']$/g, '');
    }
    if (!steelDomain) {
      const matchDomain = envContent.match(/^STEEL_DOMAIN=(.*)$/m);
      if (matchDomain) steelDomain = matchDomain[1].trim().replace(/^["']|["']$/g, '');
    }
    const matchSsl = envContent.match(/^USE_SSL=(.*)$/m);
    if (matchSsl) useSsl = matchSsl[1].trim().toLowerCase() !== 'false';
    if (!process.env.STEEL_LEASE_TTL_SEC) {
      const m = envContent.match(/^STEEL_LEASE_TTL_SEC=(.*)$/m);
      if (m) leaseTtlSec = parseInt(m[1], 10) || leaseTtlSec;
    }
    if (!process.env.STEEL_ACTIVE_WINDOW_SEC) {
      const m = envContent.match(/^STEEL_ACTIVE_WINDOW_SEC=(.*)$/m);
      if (m) activeWindowSec = parseInt(m[1], 10) || activeWindowSec;
    }
    if (!process.env.STEEL_HEARTBEAT_INTERVAL_SEC) {
      const m = envContent.match(/^STEEL_HEARTBEAT_INTERVAL_SEC=(.*)$/m);
      if (m) heartbeatIntervalSec = parseInt(m[1], 10) || heartbeatIntervalSec;
    }
    if (!process.env.STEEL_CONTEXT_SYNC_SEC) {
      const m = envContent.match(/^STEEL_CONTEXT_SYNC_SEC=(.*)$/m);
      if (m) contextSyncSec = parseInt(m[1], 10) || contextSyncSec;
    }
  }
}

const STEEL_PUBLIC_DOMAIN = steelDomain || 'browser.localhost';
const PROTOCOL = useSsl ? 'https' : 'http';
// Check CLI arguments for mode
const rawArgs = process.argv.slice(2);
let customUserDataDir = null;
const forwardArgs = [];
for (let i = 0; i < rawArgs.length; i++) {
  const arg = rawArgs[i];
  if (arg === '--isolated' || arg === '--persistent' || arg === '--shared-browser-context') {
    continue;
  }
  if (arg === '--user-data-dir') {
    if (i + 1 < rawArgs.length && !rawArgs[i + 1].startsWith('--')) {
      customUserDataDir = rawArgs[i + 1];
      i++;
    }
    continue;
  }
  if (arg.startsWith('--user-data-dir=')) {
    customUserDataDir = arg.slice('--user-data-dir='.length);
    continue;
  }
  forwardArgs.push(arg);
}

const isIsolated = rawArgs.includes('--isolated');
const isExplicitPersistent = rawArgs.includes('--persistent') || rawArgs.includes('--shared-browser-context') || customUserDataDir !== null || rawArgs.some(a => a.startsWith('--user-data-dir'));
const isPersistent = !isIsolated || isExplicitPersistent;

const PERSISTENT_DIR = customUserDataDir || path.join(homeDir, '.config/steel/profiles/persistent');
const PERSISTENT_CONTEXT_FILE = path.join(PERSISTENT_DIR, 'context.json');

function ensureDirSync(dirPath) {
  if (!fs.existsSync(dirPath)) {
    fs.mkdirSync(dirPath, { recursive: true });
  }
}

async function apiRequest(endpoint, method = 'GET', data = null, opts = {}) {
  const { retries = 3, timeoutMs = 20000, headers: extraHeaders = {} } = opts;
  const payload = data ? JSON.stringify(data) : null;
  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      return await new Promise((resolve, reject) => {
        const headers = {
          'Content-Type': 'application/json',
          'Connection': 'close',
          'x-steel-api-key': steelApiKey,
          ...extraHeaders
        };
        if (payload) {
          headers['Content-Length'] = Buffer.byteLength(payload);
        }
        const options = {
          hostname: '127.0.0.1',
          port: STEEL_PORT,
          path: endpoint,
          method: method,
          headers: headers
        };
        const req = http.request(options, (res) => {
          let body = '';
          res.on('data', chunk => body += chunk);
          res.on('end', () => {
            try {
              resolve(JSON.parse(body));
            } catch (e) {
              resolve(body);
            }
          });
        });
        req.on('error', reject);
        req.setTimeout(timeoutMs, () => {
          req.destroy();
          reject(new Error(`API request timed out: ${endpoint}`));
        });
        if (payload) req.write(payload);
        req.end();
      });
    } catch (err) {
      if (attempt === retries) throw err;
      await new Promise(r => setTimeout(r, 500 * attempt));
    }
  }
}

function resolveMcpCommand(argsForChild) {
  const possiblePaths = [
    path.join(__dirname, '../node_modules/@playwright/mcp/cli.js'),
    path.join(homeDir, '.config/opencode/node_modules/@playwright/mcp/cli.js'),
    path.join(homeDir, '.npm-global/lib/node_modules/@playwright/mcp/cli.js'),
  ];
  for (const p of possiblePaths) {
    if (fs.existsSync(p)) return { command: process.execPath, args: [p, ...argsForChild] };
  }
  return { command: 'npx', args: ['-y', '@playwright/mcp', ...argsForChild] };
}

function resolveSdkRoot() {
  const possiblePaths = [
    path.join(__dirname, '../node_modules/@modelcontextprotocol/sdk'),
    path.join(homeDir, '.config/opencode/node_modules/@modelcontextprotocol/sdk'),
    path.join(homeDir, '.npm-global/lib/node_modules/@modelcontextprotocol/sdk'),
  ];
  for (const p of possiblePaths) {
    if (fs.existsSync(p)) return p;
  }
  return null;
}

async function createSteelSession() {
  let sessionId = null;
  let cdpEndpoint = null;
  let failureNote = null;

  try {
    const createPayload = {
      useProxy: false
    };

    if (isPersistent) {
      ensureDirSync(PERSISTENT_DIR);
      if (fs.existsSync(PERSISTENT_CONTEXT_FILE)) {
        try {
          const raw = fs.readFileSync(PERSISTENT_CONTEXT_FILE, 'utf8');
          const parsed = JSON.parse(raw);
          if (parsed && typeof parsed === 'object') {
            createPayload.sessionContext = parsed;
          }
        } catch (e) {
          console.error(`[steel-mcp] Warning: Could not parse persistent context: ${e.message}`);
        }
      }
    }

    const session = await apiRequest('/v1/sessions', 'POST', createPayload, {
      retries: 2,
      timeoutMs: 90000,
      headers: { 'x-steel-lease-ttl': String(leaseTtlSec) }
    });
    if (session && session.id) {
      sessionId = session.id;
      cdpEndpoint = `ws://127.0.0.1:${STEEL_PORT}/?sessionId=${sessionId}&apiKey=${steelApiKey}`;
      console.error(`[steel-mcp] Created Steel session ${sessionId} (mode=${isPersistent ? 'persistent' : 'ephemeral'}, lease=${leaseTtlSec}s)`);
    } else {
      failureNote = `Steel API did not return a session ID: ${JSON.stringify(session).slice(0, 300)}`;
      console.error(`[steel-mcp] Warning: ${failureNote}`);
    }
  } catch (err) {
    failureNote = `Failed to connect to Steel API (${err.message}). Falling back to local Playwright.`;
    console.error(`[steel-mcp] Warning: ${failureNote}`);
  }

  return { sessionId, cdpEndpoint, failureNote };
}

async function syncAndReleaseSession(sessionId) {
  try {
    if (isPersistent) {
      console.error(`[steel-mcp] Saving persistent session context for ${sessionId}...`);
      const ctx = await apiRequest(`/v1/sessions/${sessionId}/context`, 'GET', null, { retries: 1 });
      if (ctx && typeof ctx === 'object' && (ctx.cookies || ctx.localStorage)) {
        ensureDirSync(PERSISTENT_DIR);
        const merged = mergeAndWriteContext(PERSISTENT_CONTEXT_FILE, ctx);
        console.error(`[steel-mcp] Merged ${ctx.cookies ? ctx.cookies.length : 0} cookies into persistent storage (${merged.cookies ? merged.cookies.length : 0} total).`);
      }
    }
  } catch (e) {
    console.error(`[steel-mcp] Error saving context: ${e.message}`);
  }

  try {
    console.error(`[steel-mcp] Releasing Steel session ${sessionId}...`);
    await apiRequest(`/v1/sessions/${sessionId}/release`, 'POST', {}, { retries: 1 });
    console.error(`[steel-mcp] Released session ${sessionId}.`);
  } catch (e) {
    console.error(`[steel-mcp] Error releasing session: ${e.message}`);
  }
}

// ---------------------------------------------------------------------------
// Legacy path: transparent stdio passthrough (used only if the MCP SDK is not
// available). Heartbeats keep the lease alive, but there is no transparent
// session recreation in this mode.
// ---------------------------------------------------------------------------
async function runLegacyPassthrough(sessionId, cdpEndpoint) {
  const childArgs = [];
  if (cdpEndpoint) childArgs.push('--cdp-endpoint', cdpEndpoint);
  childArgs.push(...forwardArgs);
  const { command, args } = resolveMcpCommand(childArgs);

  const child = spawn(command, args, { stdio: 'inherit' });

  let hbTimer = null;
  if (sessionId && heartbeatIntervalSec > 0) {
    hbTimer = setInterval(() => {
      apiRequest(`/v1/sessions/${sessionId}/heartbeat`, 'POST', {}, {
        retries: 1,
        timeoutMs: 6000,
        headers: { 'x-steel-lease-ttl': String(leaseTtlSec) }
      }).catch(() => {});
    }, heartbeatIntervalSec * 1000);
    hbTimer.unref?.();
  }

  let cleanupDone = false;
  async function cleanup() {
    if (cleanupDone || !sessionId) return;
    cleanupDone = true;
    if (hbTimer) clearInterval(hbTimer);
    await syncAndReleaseSession(sessionId);
  }

  process.on('SIGINT', async () => { await cleanup(); process.exit(130); });
  process.on('SIGTERM', async () => { await cleanup(); process.exit(143); });
  child.on('exit', async (code) => { await cleanup(); process.exit(code || 0); });
}

// ---------------------------------------------------------------------------
// Proxy path: this wrapper acts as its own MCP server towards OpenCode, and as
// an MCP client towards the real @playwright/mcp process, so it can splice in
// the extra `steel_get_session_info` tool and swap the upstream transparently
// when the Steel session is recreated.
// ---------------------------------------------------------------------------
async function runMcpProxy(sdkRoot, initial) {
  const { Client } = require(path.join(sdkRoot, 'dist/cjs/client/index.js'));
  const { StdioClientTransport } = require(path.join(sdkRoot, 'dist/cjs/client/stdio.js'));
  const { Server } = require(path.join(sdkRoot, 'dist/cjs/server/index.js'));
  const { StdioServerTransport } = require(path.join(sdkRoot, 'dist/cjs/server/stdio.js'));
  const { ListToolsRequestSchema, CallToolRequestSchema } = require(path.join(sdkRoot, 'dist/cjs/types.js'));

  const SESSION_INFO_TOOL_NAME = 'steel_get_session_info';
  const SESSION_INFO_TOOL = {
    name: SESSION_INFO_TOOL_NAME,
    description:
      'Returns the Steel Browser session (sessionId, liveViewerUrl, cdpWsUrl) that THIS ' +
      'playwright MCP connection is actually driving right now. Call this before sending the ' +
      'user a live-viewer link for a page you are already navigating - do not guess the ' +
      'sessionId from `steel-session list`, since multiple Steel sessions can be active at ' +
      'once and only this tool tells you which one is yours.',
    inputSchema: { type: 'object', properties: {}, additionalProperties: false }
  };

  const state = {
    sessionId: initial.sessionId,
    cdpEndpoint: initial.cdpEndpoint,
    alive: !!initial.sessionId,
    lastActivity: Date.now(),
    failureNote: initial.failureNote || null,
    sessionInfo: null
  };

  function refreshSessionInfo() {
    const liveViewerUrl = state.sessionId
      ? `${PROTOCOL}://${STEEL_PUBLIC_DOMAIN}/v1/sessions/debug?sessionId=${state.sessionId}`
      : null;
    state.sessionInfo = state.sessionId && state.alive
      ? {
          success: true,
          sessionId: state.sessionId,
          liveViewerUrl,
          cdpWsUrl: state.cdpEndpoint,
          mode: isPersistent ? 'persistent' : 'ephemeral',
          leased: true,
          leaseTtlSec
        }
      : {
          success: false,
          sessionId: null,
          liveViewerUrl: null,
          cdpWsUrl: null,
          mode: state.sessionId ? 'steel-session-expired' : 'local-fallback',
          note: state.failureNote || 'No active Steel session; this MCP connection is driving a local, unrecorded browser.'
        };
  }
  refreshSessionInfo();

  function markActivity() {
    state.lastActivity = Date.now();
  }

  function spawnUpstream(cdpEndpoint) {
    const childArgs = [];
    if (cdpEndpoint) childArgs.push('--cdp-endpoint', cdpEndpoint);
    childArgs.push(...forwardArgs);
    const { command, args } = resolveMcpCommand(childArgs);
    return new StdioClientTransport({ command, args });
  }

  let clientTransport = spawnUpstream(state.cdpEndpoint);
  let upstream = new Client({ name: 'steel-mcp-wrapper-upstream-client', version: '1.0.0' });
  await upstream.connect(clientTransport);

  let replacing = false;
  function attachTransport(tr) {
    tr.onclose = async () => {
      if (replacing) return;
      await cleanup();
      process.exit(1);
    };
    tr.onerror = (err) => { console.error(`[steel-mcp] Upstream @playwright/mcp error: ${err.message}`); };
  }
  attachTransport(clientTransport);

  let hbTimer = null;
  let ctxTimer = null;
  function stopLifecycle() {
    if (hbTimer) { clearInterval(hbTimer); hbTimer = null; }
    if (ctxTimer) { clearInterval(ctxTimer); ctxTimer = null; }
  }
  function startLifecycle() {
    stopLifecycle();
    if (!state.sessionId) return;

    if (heartbeatIntervalSec > 0) {
      hbTimer = setInterval(async () => {
        if (!state.alive || !state.sessionId) return;
        const idleSec = (Date.now() - state.lastActivity) / 1000;
        if (idleSec > activeWindowSec) return; // dejar que el lease venza y el router libere
        try {
          const r = await apiRequest(`/v1/sessions/${state.sessionId}/heartbeat`, 'POST', {}, {
            retries: 1,
            timeoutMs: 6000,
            headers: { 'x-steel-lease-ttl': String(leaseTtlSec) }
          });
          if (!r || r.success !== true) {
            state.alive = false;
            refreshSessionInfo();
            console.error('[steel-mcp] Lease lost; a replacement session will be created on the next tool call.');
          }
        } catch (e) { /* transitorio: se reintenta en el siguiente tick */ }
      }, heartbeatIntervalSec * 1000);
    }

    if (isPersistent && contextSyncSec > 0) {
      ctxTimer = setInterval(async () => {
        if (!state.alive || !state.sessionId) return;
        try {
          const ctx = await apiRequest(`/v1/sessions/${state.sessionId}/context`, 'GET', null, { retries: 1 });
          if (ctx && typeof ctx === 'object' && (ctx.cookies || ctx.localStorage)) {
            ensureDirSync(PERSISTENT_DIR);
            mergeAndWriteContext(PERSISTENT_CONTEXT_FILE, ctx);
          }
        } catch (e) { /* contexto aún no disponible */ }
      }, contextSyncSec * 1000);
    }

    if (hbTimer) hbTimer.unref?.();
    if (ctxTimer) ctxTimer.unref?.();
  }

  let recreatePromise = null;
  async function ensureLiveSession() {
    if (state.alive) {
      // Verificación rápida: el lease pudo vencer mientras el MCP estuvo idle.
      // Solo se marca muerta ante un 404 explícito; un error de red no la mata.
      const r = await apiRequest(`/v1/sessions/${state.sessionId}/heartbeat`, 'POST', {}, {
        retries: 1,
        timeoutMs: 5000,
        headers: { 'x-steel-lease-ttl': String(leaseTtlSec) }
      }).catch(() => null);
      if (r && r.success === true) return true;
      if (!r || r.success === undefined) return true; // respuesta ambigua: no la matamos
      state.alive = false;
      refreshSessionInfo();
      console.error('[steel-mcp] Session expired while idle; recreating...');
    }
    if (recreatePromise) return recreatePromise;
    recreatePromise = (async () => {
      console.error('[steel-mcp] Steel session is not alive; creating a replacement session...');
      const created = await createSteelSession();
      if (!created.sessionId) {
        state.failureNote = created.failureNote || 'No Steel session available (pool busy or launch error).';
        refreshSessionInfo();
        return false;
      }

      replacing = true;
      try { await clientTransport.close(); } catch (e) {}
      await new Promise(r => setTimeout(r, 150));
      replacing = false;

      clientTransport = spawnUpstream(created.cdpEndpoint);
      upstream = new Client({ name: 'steel-mcp-wrapper-upstream-client', version: '1.0.0' });
      await upstream.connect(clientTransport);
      attachTransport(clientTransport);

      state.sessionId = created.sessionId;
      state.cdpEndpoint = created.cdpEndpoint;
      state.alive = true;
      state.failureNote = null;
      refreshSessionInfo();
      startLifecycle();
      console.error(`[steel-mcp] Replacement Steel session ready: ${created.sessionId}`);
      return true;
    })().finally(() => { recreatePromise = null; });
    return recreatePromise;
  }

  startLifecycle();

  const server = new Server({ name: 'steel-mcp-wrapper', version: '1.0.0' }, { capabilities: { tools: {} } });

  server.setRequestHandler(ListToolsRequestSchema, async () => {
    // Nota: NO cuenta como actividad. Si el cliente hace polling de tools/list
    // mientras nadie usa el navegador, la sesión debe expirar igualmente.
    const { tools } = await upstream.listTools();
    return { tools: [...tools, SESSION_INFO_TOOL] };
  });

  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    markActivity();
    await ensureLiveSession();

    if (request.params.name === SESSION_INFO_TOOL_NAME) {
      return { content: [{ type: 'text', text: JSON.stringify(state.sessionInfo, null, 2) }] };
    }

    if (!state.alive) {
      return {
        content: [{
          type: 'text',
          text: JSON.stringify({
            success: false,
            error: 'No Steel session available (pool busy or launch error). Retry in a few minutes.',
            detail: state.failureNote
          }, null, 2)
        }],
        isError: true
      };
    }

    return upstream.callTool(request.params);
  });

  let cleanupDone = false;
  async function cleanup() {
    if (cleanupDone) return;
    cleanupDone = true;
    stopLifecycle();
    if (state.sessionId && state.alive) {
      state.alive = false;
      await syncAndReleaseSession(state.sessionId);
    }
  }

  process.on('SIGINT', async () => { await cleanup(); process.exit(130); });
  process.on('SIGTERM', async () => { await cleanup(); process.exit(143); });

  const serverTransport = new StdioServerTransport();
  serverTransport.onclose = async () => { await cleanup(); process.exit(0); };

  await server.connect(serverTransport);
}

async function main() {
  const initial = await createSteelSession();
  const sdkRoot = resolveSdkRoot();

  if (!sdkRoot) {
    console.error('[steel-mcp] Warning: @modelcontextprotocol/sdk not found; running in legacy passthrough mode (no steel_get_session_info tool).');
    return runLegacyPassthrough(initial.sessionId, initial.cdpEndpoint);
  }

  return runMcpProxy(sdkRoot, initial);
}

main().catch((err) => {
  console.error(`[steel-mcp] Fatal error: ${err.stack || err.message}`);
  process.exit(1);
});
