#!/usr/bin/env node

/**
 * Interactive Steel Browser Live Session Demo
 * Runs an automated browser flow while allowing you to watch and interact via the Live Session Viewer.
 */

const fs = require('fs');
const path = require('path');
const https = require('https');
const http = require('http');

// Setup module search paths if needed
const homeDir = process.env.HOME || '/home/jeisson';
const opencodeModules = path.join(homeDir, '.config/opencode/node_modules');
if (fs.existsSync(opencodeModules) && !module.paths.includes(opencodeModules)) {
  module.paths.unshift(opencodeModules);
}

const { chromium } = require('playwright');

// 1. Resolve STEEL_API_KEY and STEEL_DOMAIN
let steelApiKey = process.env.STEEL_API_KEY || '';
let steelDomain = process.env.STEEL_DOMAIN || '';
let useSsl = process.env.USE_SSL === 'false' ? false : true;

const envPath = path.resolve(__dirname, '../steel/.env');
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
}

const STEEL_PUBLIC_DOMAIN = steelDomain || 'browser.localhost';
const PROTOCOL = useSsl ? 'https' : 'http';
const STEEL_API_URL = process.env.STEEL_API_URL || `${PROTOCOL}://${STEEL_PUBLIC_DOMAIN}`;

async function requestJson(url, options = {}, postData = null) {
  return new Promise((resolve, reject) => {
    const isHttps = url.startsWith('https:');
    const client = isHttps ? https : http;
    const req = client.request(url, options, (res) => {
      let body = '';
      res.on('data', (chunk) => body += chunk);
      res.on('end', () => {
        try {
          resolve(JSON.parse(body));
        } catch (e) {
          resolve(body);
        }
      });
    });
    req.on('error', reject);
    if (postData) req.write(JSON.stringify(postData));
    req.end();
  });
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function main() {
  console.log('\n========================================================================');
  console.log('  🚀 INICIANDO SESIÓN DE PRUEBA EN STEEL BROWSER (HTTPS / WSS)');
  console.log('========================================================================\n');

  console.log('--> 1. Creando nueva sesión en Steel Browser...');
  const createHeaders = {
    'Content-Type': 'application/json',
    'x-steel-api-key': steelApiKey
  };

  const session = await requestJson(`${STEEL_API_URL}/v1/sessions`, {
    method: 'POST',
    headers: createHeaders
  }, {
    useProxy: false
  });

  if (!session || !session.id) {
    console.error('[-] Error creando sesión:', session);
    process.exit(1);
  }

  const sessionId = session.id;
  const liveViewerUrl = `${PROTOCOL}://${STEEL_PUBLIC_DOMAIN}/v1/sessions/debug?sessionId=${sessionId}`;
  const cdpWsUrl = `ws://127.0.0.1:3000/?sessionId=${sessionId}&apiKey=${steelApiKey}`;

  console.log('\n┌────────────────────────────────────────────────────────────────────────┐');
  console.log('│  🌐 ¡SESIÓN EN VIVO CREADA CON ÉXITO!                                   │');
  console.log('├────────────────────────────────────────────────────────────────────────┤');
  console.log(`│  Session ID: ${sessionId}   │`);
  console.log('│                                                                        │');
  console.log('│  👉 HAZ CLIC EN EL ENLACE HTTPS PARA VER LA SESIÓN EN VIVO:          │');
  console.log(`│     \x1b[32;1m${liveViewerUrl}\x1b[0m     │`);
  console.log('│                                                                        │');
  console.log('│  (La sesión permanecerá activa durante 10 minutos para tus pruebas)    │');
  console.log('└────────────────────────────────────────────────────────────────────────┘\n');

  console.log('--> 2. Conectando Playwright vía CDP al sandbox de Steel...');
  const browser = await chromium.connectOverCDP(cdpWsUrl);
  const context = browser.contexts()[0] || await browser.newContext();
  const page = context.pages()[0] || await context.newPage();

  // Step 1: Open Wikipedia
  console.log('\n[Paso 1/4] Navegando a Wikipedia...');
  await page.goto('https://www.wikipedia.org', { waitUntil: 'domcontentloaded' });
  console.log('  ✓ Página cargada: Wikipedia');
  console.log('  ⏳ Pausa de 8s para que puedas observar la pantalla en vivo...');
  await sleep(8000);

  // Step 2: Search term
  console.log('\n[Paso 2/4] Escribiendo búsqueda: "Artificial Intelligence"...');
  await page.fill('input#searchInput', 'Artificial Intelligence');
  await sleep(2500);
  await page.press('input#searchInput', 'Enter');
  await page.waitForLoadState('domcontentloaded');
  console.log('  ✓ Búsqueda completada en Wikipedia.');
  console.log('  ⏳ Pausa de 8s...');
  await sleep(8000);

  // Step 3: Scroll smoothly
  console.log('\n[Paso 3/4] Haciendo scroll hacia abajo en el artículo...');
  await page.evaluate(() => window.scrollBy({ top: 800, behavior: 'smooth' }));
  await sleep(4000);
  await page.evaluate(() => window.scrollBy({ top: 800, behavior: 'smooth' }));
  await sleep(5000);

  // Step 4: Navigate to Hacker News
  console.log('\n[Paso 4/4] Navegando a Hacker News...');
  await page.goto('https://news.ycombinator.com', { waitUntil: 'domcontentloaded' });
  console.log('  ✓ Hacker News cargado con éxito.');

  console.log('\n========================================================================');
  console.log('  🎉 DEMO AUTOMATIZADA FINALIZADA');
  console.log(`  El navegador permanecerá ABIERTO durante 10 minutos (600s)`);
  console.log(`  Puedes interactuar, hacer clic o escribir en:`);
  console.log(`  👉 ${liveViewerUrl}`);
  console.log('========================================================================\n');

  for (let i = 600; i > 0; i -= 15) {
    process.stdout.write(`\r  ⏳ Tiempo restante de sesión: ${i}s (Presiona Ctrl+C para finalizar)... `);
    await sleep(15000);
  }

  console.log('\n\n--> Liberando sesión...');
  await browser.close().catch(() => {});
  await requestJson(`${STEEL_API_URL}/v1/sessions/${sessionId}/release`, {
    method: 'POST',
    headers: createHeaders
  });
  console.log('[+] Sesión liberada con éxito.');
}

main().catch(async (err) => {
  console.error('[-] Error durante la prueba:', err);
});
