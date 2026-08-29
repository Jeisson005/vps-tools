#!/usr/bin/env node

/**
 * Steel Browser Session Helper CLI
 * Manages isolated Steel sessions with automatic persistent profile sync.
 *
 * Usage:
 *   steel-session create [url] [--isolated]   -> Creates session (default: persistent), preloads context, outputs live viewer link
 *   steel-session sync <id>                   -> Pulls latest session context (cookies/storage) and persists to disk
 *   steel-session release <id> [--no-sync]    -> Syncs context and releases session
 *   steel-session list                        -> Lists active sessions
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const http = require('http');

// Setup module search paths if needed
const homeDir = os.homedir();
const opencodeModules = path.join(homeDir, '.config/opencode/node_modules');
if (fs.existsSync(opencodeModules) && !module.paths.includes(opencodeModules)) {
  module.paths.unshift(opencodeModules);
}

// 1. Resolve environment variables from steel/.env or system environment
let steelApiKey = process.env.STEEL_API_KEY || '';
let steelDomain = process.env.STEEL_DOMAIN || '';
let useSsl = process.env.USE_SSL === 'false' ? false : true;
let steelTimeoutMs = process.env.STEEL_TIMEOUT_MS ? parseInt(process.env.STEEL_TIMEOUT_MS, 10) : 1800000;
const STEEL_PORT = process.env.STEEL_PORT || '3000';

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
    const matchTimeout = envContent.match(/^STEEL_TIMEOUT_MS=(.*)$/m);
    if (matchTimeout) {
      const parsed = parseInt(matchTimeout[1].trim().replace(/^["']|["']$/g, ''), 10);
      if (!isNaN(parsed) && parsed > 0) steelTimeoutMs = parsed;
    }
  }
}

const STEEL_PUBLIC_DOMAIN = steelDomain || 'browser.localhost';
const PROTOCOL = useSsl ? 'https' : 'http';
const PERSISTENT_DIR = path.join(homeDir, '.config/steel/profiles/persistent');
const PERSISTENT_CONTEXT_FILE = path.join(PERSISTENT_DIR, 'context.json');

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

async function createSession(targetUrl, options = {}) {
  const isIsolated = Boolean(options.isolated);
  const isPersistent = !isIsolated;

  const createPayload = {
    useProxy: false,
    timeout: steelTimeoutMs
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
        console.error(`[-] Warning loading persistent context: ${e.message}`);
      }
    }
  }

  const session = await apiRequest('/v1/sessions', 'POST', createPayload);
  if (!session || !session.id) {
    console.error('[-] Error al crear sesión en Steel Browser:', session);
    process.exit(1);
  }

  const liveViewerUrl = `${PROTOCOL}://${STEEL_PUBLIC_DOMAIN}/v1/sessions/debug?sessionId=${session.id}`;
  const cdpWsUrl = `ws://127.0.0.1:${STEEL_PORT}/?sessionId=${session.id}&apiKey=${steelApiKey}`;

  if (targetUrl) {
    let navigated = false;
    const possiblePlaywright = [
      'playwright',
      'playwright-core',
      path.join(homeDir, '.config/opencode/node_modules/playwright-core'),
      path.join(homeDir, '.config/opencode/node_modules/playwright')
    ];
    for (const pkg of possiblePlaywright) {
      try {
        const { chromium } = require(pkg);
        const browser = await chromium.connectOverCDP(cdpWsUrl);
        const context = browser.contexts()[0] || await browser.newContext();
        const page = context.pages()[0] || await context.newPage();
        await page.goto(targetUrl, { waitUntil: 'domcontentloaded', timeout: 15000 });
        await browser.close();
        navigated = true;
        break;
      } catch (e) {}
    }

    if (!navigated && typeof WebSocket !== 'undefined') {
      await new Promise((resolve) => {
        try {
          const ws = new WebSocket(cdpWsUrl);
          const timeout = setTimeout(() => { try { ws.close(); } catch(e){} resolve(); }, 8000);
          ws.onopen = () => {
            ws.send(JSON.stringify({ id: 1, method: 'Page.enable' }));
            ws.send(JSON.stringify({ id: 2, method: 'Page.navigate', params: { url: targetUrl } }));
            setTimeout(() => { try { ws.close(); } catch(e){} clearTimeout(timeout); resolve(); }, 1500);
          };
          ws.onerror = () => { clearTimeout(timeout); resolve(); };
        } catch (e) { resolve(); }
      });
    }
  }

  console.log(JSON.stringify({
    success: true,
    sessionId: session.id,
    liveViewerUrl: liveViewerUrl,
    cdpWsUrl: cdpWsUrl,
    mode: isPersistent ? 'persistent' : 'ephemeral',
    targetUrl: targetUrl || null
  }, null, 2));
  process.exit(0);
}

async function syncSession(sessionId) {
  try {
    const ctx = await apiRequest(`/v1/sessions/${sessionId}/context`, 'GET');
    if (ctx && typeof ctx === 'object' && (ctx.cookies || ctx.localStorage)) {
      ensureDirSync(PERSISTENT_DIR);
      fs.writeFileSync(PERSISTENT_CONTEXT_FILE, JSON.stringify(ctx, null, 2), 'utf8');
      console.log(JSON.stringify({
        success: true,
        message: `Context for session ${sessionId} synced to persistent storage.`,
        cookiesCount: ctx.cookies ? ctx.cookies.length : 0,
        path: PERSISTENT_CONTEXT_FILE
      }, null, 2));
    } else {
      console.log(JSON.stringify({ success: false, message: 'No valid context returned.' }));
    }
    process.exit(0);
  } catch (e) {
    console.error(`[-] Error syncing context: ${e.message}`);
    process.exit(1);
  }
}

async function releaseSession(sessionId, syncFirst = true) {
  if (syncFirst) {
    try {
      const ctx = await apiRequest(`/v1/sessions/${sessionId}/context`, 'GET');
      if (ctx && typeof ctx === 'object' && (ctx.cookies || ctx.localStorage)) {
        ensureDirSync(PERSISTENT_DIR);
        fs.writeFileSync(PERSISTENT_CONTEXT_FILE, JSON.stringify(ctx, null, 2), 'utf8');
      }
    } catch (e) {}
  }
  const result = await apiRequest(`/v1/sessions/${sessionId}/release`, 'POST', {});
  console.log(JSON.stringify(result, null, 2));
  process.exit(0);
}

async function listSessions() {
  const result = await apiRequest('/v1/sessions', 'GET');
  if (result && Array.isArray(result.sessions)) {
    result.sessions = result.sessions.map(s => ({
      id: s.id,
      status: s.status,
      liveViewerUrl: `${PROTOCOL}://${STEEL_PUBLIC_DOMAIN}/v1/sessions/debug?sessionId=${s.id}`,
      createdAt: s.createdAt,
      dimensions: s.dimensions
    }));
  }
  console.log(JSON.stringify(result, null, 2));
}

// CLI argument parsing
const args = process.argv.slice(2);
const command = args[0] || 'list';

if (command === 'create') {
  let targetUrl = '';
  let isIsolated = false;
  for (let i = 1; i < args.length; i++) {
    if (args[i] === '--isolated') {
      isIsolated = true;
    } else if (!targetUrl && !args[i].startsWith('--')) {
      targetUrl = args[i];
    }
  }
  createSession(targetUrl, { isolated: isIsolated });
} else if (command === 'sync') {
  const sid = args[1];
  if (!sid) {
    console.error('Usage: steel-session sync <sessionId>');
    process.exit(1);
  }
  syncSession(sid);
} else if (command === 'release') {
  const sid = args[1];
  const noSync = args.includes('--no-sync');
  if (!sid) {
    console.error('Usage: steel-session release <sessionId>');
    process.exit(1);
  }
  releaseSession(sid, !noSync);
} else if (command === 'list') {
  listSessions();
} else {
  console.log('Usage: steel-session <create [url] [--isolated] | sync <id> | release <id> | list>');
}
