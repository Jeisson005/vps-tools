#!/usr/bin/env node

/**
 * Steel Browser MCP Wrapper for Playwright
 * Dynamically resolves the CDP endpoint from Steel Browser container (port 9223)
 * and passes the concrete WebSocket URL to @playwright/mcp.
 * Supports passing custom Playwright options (e.g. --user-data-dir, --shared-browser-context).
 * If Steel Browser is unavailable, falls back gracefully to standard Playwright.
 */

const http = require('http');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const CDP_HOST = process.env.STEEL_CDP_HOST || '127.0.0.1';
const CDP_PORT = process.env.STEEL_CDP_PORT || '9223';

async function getCDPEndpoint() {
  return new Promise((resolve) => {
    const req = http.get(`http://${CDP_HOST}:${CDP_PORT}/json/version`, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const json = JSON.parse(data);
          let wsUrl = json.webSocketDebuggerUrl;
          if (wsUrl) {
            wsUrl = wsUrl.replace(`ws://${CDP_HOST}/`, `ws://${CDP_HOST}:${CDP_PORT}/`);
            resolve(wsUrl);
            return;
          }
          resolve(null);
        } catch (e) {
          resolve(null);
        }
      });
    });
    req.on('error', () => resolve(null));
    req.setTimeout(2000, () => {
      req.destroy();
      resolve(null);
    });
  });
}

function resolveMcpCli() {
  const possiblePaths = [
    path.join(__dirname, '../node_modules/@playwright/mcp/cli.js'),
    path.join(os.homedir(), '.config/opencode/node_modules/@playwright/mcp/cli.js'),
    path.join(os.homedir(), '.npm-global/lib/node_modules/@playwright/mcp/cli.js'),
  ];
  for (const p of possiblePaths) {
    if (fs.existsSync(p)) return p;
  }
  return 'npx @playwright/mcp';
}

async function main() {
  const wsUrl = await getCDPEndpoint();
  const mcpCli = resolveMcpCli();
  
  let args = [];
  if (wsUrl) {
    args = ['--cdp-endpoint', wsUrl];
  }
  
  const forwardArgs = process.argv.slice(2);
  
  let child;
  if (mcpCli.startsWith('npx')) {
    child = spawn('npx', ['-y', '@playwright/mcp', ...args, ...forwardArgs], { stdio: 'inherit' });
  } else {
    child = spawn(process.execPath, [mcpCli, ...args, ...forwardArgs], { stdio: 'inherit' });
  }
  
  child.on('exit', (code) => process.exit(code || 0));
}

main();
