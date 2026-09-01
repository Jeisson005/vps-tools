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
 * This enables unlimited concurrent sessions across OpenCode and Hermes without collisions.
 *
 * MCP proxy layer:
 * The wrapper sits between OpenCode and the real @playwright/mcp process (an
 * MCP client talking to the real server, and an MCP server talking to OpenCode)
 * so it can inject one extra tool, `steel_get_session_info`. Because the Steel
 * sessionId created above is otherwise only ever printed to stderr, an agent
 * driving the browser via the `playwright`/`playwright-persistent` MCP tools has
 * no in-band way to learn which Steel session it is actually attached to - it
 * has to guess from `steel-session list`, which is ambiguous whenever more than
 * one session is active. `steel_get_session_info` answers that deterministically
 * from the exact session this wrapper instance created.
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
    if (matchSsl) {
      useSsl = matchSsl[1].trim().toLowerCase() !== 'false';
    }
  }
}

const STEEL_PUBLIC_DOMAIN = steelDomain || 'browser.localhost';
const PROTOCOL = useSsl ? 'https' : 'http';
const PERSISTENT_DIR = path.join(homeDir, '.config/steel/profiles/persistent');
const PERSISTENT_CONTEXT_FILE = path.join(PERSISTENT_DIR, 'context.json');

// Check CLI arguments for mode
const rawArgs = process.argv.slice(2);
const isIsolated = rawArgs.includes('--isolated');
const isExplicitPersistent = rawArgs.includes('--persistent') || rawArgs.includes('--shared-browser-context') || rawArgs.some(a => a.startsWith('--user-data-dir'));
const isPersistent = !isIsolated || isExplicitPersistent;

// Safe forward arguments for Playwright MCP (strip custom wrapper flags)
const forwardArgs = rawArgs.filter(arg =>
  arg !== '--isolated' &&
  arg !== '--persistent' &&
  arg !== '--shared-browser-context' &&
  !arg.startsWith('--user-data-dir')
);

function ensureDirSync(dirPath) {
  if (!fs.existsSync(dirPath)) {
    fs.mkdirSync(dirPath, { recursive: true });
  }
}

async function apiRequest(endpoint, method = 'GET', data = null, retries = 3) {
  const payload = data ? JSON.stringify(data) : null;
  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      return await new Promise((resolve, reject) => {
        const headers = {
          'Content-Type': 'application/json',
          'Connection': 'close',
          'x-steel-api-key': steelApiKey
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
        req.setTimeout(20000, () => {
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
      useProxy: false,
      timeout: 1800000 // 30 min session timeout
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

    const session = await apiRequest('/v1/sessions', 'POST', createPayload);
    if (session && session.id) {
      sessionId = session.id;
      cdpEndpoint = `ws://127.0.0.1:${STEEL_PORT}/?sessionId=${sessionId}&apiKey=${steelApiKey}`;
      console.error(`[steel-mcp] Created isolated Steel session ${sessionId} (mode=${isPersistent ? 'persistent' : 'ephemeral'})`);
    } else {
      failureNote = `Steel API did not return a session ID: ${JSON.stringify(session)}`;
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
      const ctx = await apiRequest(`/v1/sessions/${sessionId}/context`, 'GET');
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
    await apiRequest(`/v1/sessions/${sessionId}/release`, 'POST', {});
    console.error(`[steel-mcp] Released session ${sessionId}.`);
  } catch (e) {
    console.error(`[steel-mcp] Error releasing session: ${e.message}`);
  }
}

// ---------------------------------------------------------------------------
// Legacy path: transparent stdio passthrough (used only if the MCP SDK is not
// available, so this wrapper degrades to its old behavior instead of failing
// outright). No `steel_get_session_info` tool is available in this mode.
// ---------------------------------------------------------------------------
async function runLegacyPassthrough(sessionId, cdpEndpoint) {
  const childArgs = [];
  if (cdpEndpoint) childArgs.push('--cdp-endpoint', cdpEndpoint);
  childArgs.push(...forwardArgs);
  const { command, args } = resolveMcpCommand(childArgs);

  const child = spawn(command, args, { stdio: 'inherit' });

  let cleanupDone = false;
  async function cleanup() {
    if (cleanupDone || !sessionId) return;
    cleanupDone = true;
    await syncAndReleaseSession(sessionId);
  }

  process.on('SIGINT', async () => { await cleanup(); process.exit(130); });
  process.on('SIGTERM', async () => { await cleanup(); process.exit(143); });
  child.on('exit', async (code) => { await cleanup(); process.exit(code || 0); });
}

// ---------------------------------------------------------------------------
// Proxy path: this wrapper acts as its own MCP server towards OpenCode, and as
// an MCP client towards the real @playwright/mcp process, so it can splice in
// the extra `steel_get_session_info` tool.
// ---------------------------------------------------------------------------
async function runMcpProxy(sdkRoot, sessionId, cdpEndpoint, failureNote) {
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

  const liveViewerUrl = sessionId
    ? `${PROTOCOL}://${STEEL_PUBLIC_DOMAIN}/v1/sessions/debug?sessionId=${sessionId}`
    : null;

  const sessionInfo = sessionId
    ? { success: true, sessionId, liveViewerUrl, cdpWsUrl: cdpEndpoint, mode: isPersistent ? 'persistent' : 'ephemeral' }
    : { success: false, sessionId: null, liveViewerUrl: null, cdpWsUrl: null, mode: 'local-fallback', note: failureNote || 'No Steel session is active; this MCP connection is driving a local, unrecorded browser.' };

  const childArgs = [];
  if (cdpEndpoint) childArgs.push('--cdp-endpoint', cdpEndpoint);
  childArgs.push(...forwardArgs);
  const { command, args } = resolveMcpCommand(childArgs);

  const clientTransport = new StdioClientTransport({ command, args });
  const upstream = new Client({ name: 'steel-mcp-wrapper-upstream-client', version: '1.0.0' });
  await upstream.connect(clientTransport);

  const server = new Server({ name: 'steel-mcp-wrapper', version: '1.0.0' }, { capabilities: { tools: {} } });

  server.setRequestHandler(ListToolsRequestSchema, async () => {
    const { tools } = await upstream.listTools();
    return { tools: [...tools, SESSION_INFO_TOOL] };
  });

  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    if (request.params.name === SESSION_INFO_TOOL_NAME) {
      return { content: [{ type: 'text', text: JSON.stringify(sessionInfo, null, 2) }] };
    }
    return upstream.callTool(request.params);
  });

  let cleanupDone = false;
  async function cleanup() {
    if (cleanupDone || !sessionId) return;
    cleanupDone = true;
    await syncAndReleaseSession(sessionId);
  }

  process.on('SIGINT', async () => { await cleanup(); process.exit(130); });
  process.on('SIGTERM', async () => { await cleanup(); process.exit(143); });

  clientTransport.onclose = async () => { await cleanup(); process.exit(1); };
  clientTransport.onerror = (err) => { console.error(`[steel-mcp] Upstream @playwright/mcp error: ${err.message}`); };

  const serverTransport = new StdioServerTransport();
  serverTransport.onclose = async () => { await cleanup(); process.exit(0); };

  await server.connect(serverTransport);
}

async function main() {
  const { sessionId, cdpEndpoint, failureNote } = await createSteelSession();
  const sdkRoot = resolveSdkRoot();

  if (!sdkRoot) {
    console.error('[steel-mcp] Warning: @modelcontextprotocol/sdk not found; running in legacy passthrough mode (no steel_get_session_info tool).');
    return runLegacyPassthrough(sessionId, cdpEndpoint);
  }

  return runMcpProxy(sdkRoot, sessionId, cdpEndpoint, failureNote);
}

main().catch((err) => {
  console.error(`[steel-mcp] Fatal error: ${err.stack || err.message}`);
  process.exit(1);
});
