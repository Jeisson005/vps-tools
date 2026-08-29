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
 */

const http = require('http');
const { spawn } = require('child_process');
const path = require('path');
const os = require('os');
const fs = require('fs');

// 1. Resolve environment variables
const homeDir = os.homedir();
let steelApiKey = process.env.STEEL_API_KEY || '';
let steelDomain = process.env.STEEL_DOMAIN || '';
let useSsl = process.env.USE_SSL === 'false' ? false : true;
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
  }
}

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

function resolveMcpCli() {
  const possiblePaths = [
    path.join(__dirname, '../node_modules/@playwright/mcp/cli.js'),
    path.join(homeDir, '.config/opencode/node_modules/@playwright/mcp/cli.js'),
    path.join(homeDir, '.npm-global/lib/node_modules/@playwright/mcp/cli.js'),
  ];
  for (const p of possiblePaths) {
    if (fs.existsSync(p)) return p;
  }
  return 'npx @playwright/mcp';
}

async function main() {
  let sessionId = null;
  let cdpEndpoint = null;

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
      console.error('[steel-mcp] Warning: Steel API did not return a session ID:', session);
    }
  } catch (err) {
    console.error(`[steel-mcp] Warning: Failed to connect to Steel API (${err.message}). Falling back to local Playwright.`);
  }

  const mcpCli = resolveMcpCli();
  let args = [];
  if (cdpEndpoint) {
    args.push('--cdp-endpoint', cdpEndpoint);
  }
  args.push(...forwardArgs);

  let child;
  if (mcpCli.startsWith('npx')) {
    child = spawn('npx', ['-y', '@playwright/mcp', ...args], { stdio: 'inherit' });
  } else {
    child = spawn(process.execPath, [mcpCli, ...args], { stdio: 'inherit' });
  }

  let cleanupDone = false;
  async function cleanup() {
    if (cleanupDone || !sessionId) return;
    cleanupDone = true;

    try {
      if (isPersistent) {
        console.error(`[steel-mcp] Saving persistent session context for ${sessionId}...`);
        const ctx = await apiRequest(`/v1/sessions/${sessionId}/context`, 'GET');
        if (ctx && typeof ctx === 'object' && (ctx.cookies || ctx.localStorage)) {
          ensureDirSync(PERSISTENT_DIR);
          fs.writeFileSync(PERSISTENT_CONTEXT_FILE, JSON.stringify(ctx, null, 2), 'utf8');
          console.error(`[steel-mcp] Saved ${ctx.cookies ? ctx.cookies.length : 0} cookies to persistent storage.`);
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

  process.on('SIGINT', async () => {
    await cleanup();
    process.exit(130);
  });

  process.on('SIGTERM', async () => {
    await cleanup();
    process.exit(143);
  });

  child.on('exit', async (code) => {
    await cleanup();
    process.exit(code || 0);
  });
}

main();
