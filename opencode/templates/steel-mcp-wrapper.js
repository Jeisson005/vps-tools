#!/usr/bin/env node

/**
 * Steel Browser MCP Wrapper for Playwright
 * Dynamically resolves the CDP endpoint from Steel Browser container (port 9223)
 * and passes the concrete WebSocket URL to @playwright/mcp.
 * If Steel Browser is unavailable, falls back gracefully to standard Playwright.
 */

const http = require('http');
const { spawn } = require('child_process');
const path = require('path');

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
            // Ensure port is included in URL
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

async function main() {
  const wsUrl = await getCDPEndpoint();
  const mcpCli = path.join(__dirname, 'node_modules/@playwright/mcp/cli.js');
  
  let args = [];
  if (wsUrl) {
    args = ['--cdp-endpoint', wsUrl];
  }
  
  const child = spawn(process.execPath, [mcpCli, ...args, ...process.argv.slice(2)], {
    stdio: 'inherit'
  });
  
  child.on('exit', (code) => process.exit(code || 0));
}

main();
