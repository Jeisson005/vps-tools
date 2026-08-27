#!/usr/bin/env node

/**
 * Steel Browser Session Helper CLI
 * Usage:
 *   steel-session create [url]    -> Creates a session, optionally navigates to URL, and outputs live viewer link
 *   steel-session list            -> Lists active sessions
 *   steel-session release <id>    -> Releases an active session
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const http = require('http');
const https = require('https');

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
const STEEL_API_PORT = process.env.STEEL_PORT || '3000';
const PROTOCOL = useSsl ? 'https' : 'http';

async function apiRequest(endpoint, method = 'GET', data = null) {
  return new Promise((resolve, reject) => {
    const options = {
      hostname: '127.0.0.1',
      port: STEEL_API_PORT,
      path: endpoint,
      method: method,
      headers: {
        'Content-Type': 'application/json',
        'x-steel-api-key': steelApiKey
      }
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
    if (data) req.write(JSON.stringify(data));
    req.end();
  });
}

async function createSession(targetUrl) {
  const session = await apiRequest('/v1/sessions', 'POST', { useProxy: false });
  if (!session || !session.id) {
    console.error('[-] Error al crear sesión en Steel Browser:', session);
    process.exit(1);
  }

  const liveViewerUrl = `${PROTOCOL}://${STEEL_PUBLIC_DOMAIN}/v1/sessions/debug?sessionId=${session.id}`;
  const cdpWsUrl = `ws://127.0.0.1:${STEEL_API_PORT}/?sessionId=${session.id}&apiKey=${steelApiKey}`;

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
    targetUrl: targetUrl || null
  }, null, 2));
}

async function listSessions() {
  const result = await apiRequest('/v1/sessions', 'GET');
  console.log(JSON.stringify(result, null, 2));
}

async function releaseSession(sessionId) {
  const result = await apiRequest(`/v1/sessions/${sessionId}/release`, 'POST');
  console.log(JSON.stringify(result, null, 2));
}

const command = process.argv[2] || 'list';
const arg = process.argv[3] || '';

if (command === 'create') {
  createSession(arg);
} else if (command === 'list') {
  listSessions();
} else if (command === 'release') {
  releaseSession(arg);
} else {
  console.log('Usage: steel-session <create [url] | list | release <id>>');
}
