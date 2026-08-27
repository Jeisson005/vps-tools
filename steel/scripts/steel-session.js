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
const http = require('http');
const https = require('https');

// Resolve STEEL_API_KEY
let steelApiKey = process.env.STEEL_API_KEY || '';
const possibleEnvPaths = [
  '/home/jeisson/vps-tools/steel/.env',
  path.join(__dirname, '../.env')
];
for (const envPath of possibleEnvPaths) {
  if (!steelApiKey && fs.existsSync(envPath)) {
    const envContent = fs.readFileSync(envPath, 'utf8');
    const match = envContent.match(/^STEEL_API_KEY=(.*)$/m);
    if (match) steelApiKey = match[1].trim().replace(/^["']|["']$/g, '');
  }
}

const STEEL_API_PORT = process.env.STEEL_PORT || '3000';
const STEEL_PUBLIC_DOMAIN = process.env.STEEL_DOMAIN || 'steel.jeisson.top';

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

  const liveViewerUrl = `https://${STEEL_PUBLIC_DOMAIN}/v1/sessions/debug?sessionId=${session.id}`;
  const cdpWsUrl = `ws://127.0.0.1:${STEEL_API_PORT}/?sessionId=${session.id}&apiKey=${steelApiKey}`;

  if (targetUrl) {
    try {
      const { chromium } = require('playwright');
      const browser = await chromium.connectOverCDP(cdpWsUrl);
      const context = browser.contexts()[0] || await browser.newContext();
      const page = context.pages()[0] || await context.newPage();
      await page.goto(targetUrl, { waitUntil: 'domcontentloaded' });
    } catch (e) {
      console.error('[!] Sesión creada pero falló la navegación inicial:', e.message);
    }
  }

  console.log(JSON.stringify({
    success: true,
    sessionId: session.id,
    liveViewerUrl: liveViewerUrl,
    altLiveViewerUrl: `https://browser.jeisson.top/v1/sessions/debug?sessionId=${session.id}`,
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
