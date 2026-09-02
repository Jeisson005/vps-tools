#!/usr/bin/env node
// Baileys multi-session bridge for the VPS MCP gateway.
// Run on the HOST (Node + baileys):  node whatsapp-bridge.js --port 3010 --session-dir ./sessions/personal
// Exposes:
//   GET  /status    -> { connected, loggedIn, qr }
//   GET  /chats     -> [{ id, name }]
//   GET  /messages?chatId=<jid> -> [{ id, fromMe, text, ts }]
//   POST /send      -> { chatId, text } (JSON body)
const http = require('http');
const { useMultiFileAuthState, fetchLatestBaileysVersion, makeWASocket, DisconnectReason } = require('@whiskeysockets/baileys');
const pino = require('pino');

const args = process.argv.slice(2);
function opt(name, def) {
  const i = args.indexOf(name);
  return i >= 0 ? args[i + 1] : def;
}
const PORT = parseInt(opt('--port', String(Number(process.env.PORT || 3010))), 10);
const SESSION_DIR = opt('--session-dir', process.env.SESSION_DIR || './sessions/wa');

const logger = pino({ level: 'silent' });
let sock = null;
let qr = '';
let loggedIn = false;
const socketStore = { chats: [], messages: {} };

const log = (...a) => console.log(new Date().toISOString(), ...a);

async function start() {
  const { state, saveCreds } = await useMultiFileAuthState(SESSION_DIR);
  const { version } = await fetchLatestBaileysVersion();
  const makeSocket = () => makeWASocket({
    version,
    auth: state,
    printQRInTerminal: false,
    logger,
    browser: ['Ubuntu', 'Chrome', '22.04'],
  });

  sock = makeSocket();
  sock.ev.on('creds.update', saveCreds);
  sock.ev.on('connection.update', (update) => {
    const { connection, lastDisconnect, qr: q } = update;
    if (q) qr = q;
    if (connection === 'open') { loggedIn = true; qr = ''; log('connected'); }
    if (connection === 'close') {
      loggedIn = false;
      const code = lastDisconnect?.error?.output?.statusCode;
      if (code !== DisconnectReason.loggedOut) {
        setTimeout(() => { sock = makeSocket(); bind(sock); }, 3000);
      }
    }
  });
  sock.ev.on('messages.upsert', ({ messages }) => {
    for (const m of messages || []) {
      const jid = m.key?.remoteJid || 'unknown';
      if (!socketStore.messages[jid]) socketStore.messages[jid] = [];
      socketStore.messages[jid].unshift({
        id: m.key?.id, fromMe: !!m.key?.fromMe,
        text: m.message?.conversation || m.message?.extendedTextMessage?.text || '',
        ts: m.messageTimestamp,
      });
      if (socketStore.messages[jid].length > 100) socketStore.messages[jid].pop();
      if (!socketStore.chats.find(c => c.id === jid)) socketStore.chats.push({ id: jid, name: jid });
    }
  });
  bind(sock);
}

function bind(s) {
  if (!s.ev) return;
}

async function send(chatId, text) {
  if (!sock) throw new Error('not connected');
  await sock.sendMessage(chatId, { text });
  return { status: 'sent', chatId, text };
}

const server = http.createServer(async (req, res) => {
  const json = (o) => { res.writeHead(200, { 'Content-Type': 'application/json' }); res.end(JSON.stringify(o)); };
  try {
    const url = new URL(req.url, `http://localhost:${PORT}`);
    if (url.pathname === '/status') {
      return json({ connected: loggedIn, loggedIn, qr });
    }
    if (url.pathname === '/chats') {
      return json({ chats: socketStore.chats });
    }
    if (url.pathname === '/messages') {
      const chatId = url.searchParams.get('chatId');
      return json({ messages: socketStore.messages[chatId] || [] });
    }
    if (url.pathname === '/send' && req.method === 'POST') {
      let body = '';
      for await (const chunk of req) body += chunk;
      const { chatId, text } = JSON.parse(body || '{}');
      return json(await send(chatId, text));
    }
    res.writeHead(404); res.end('not found');
  } catch (e) {
    res.writeHead(500, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: String(e && e.message || e) }));
  }
});

server.listen(PORT, '0.0.0.0', () => {
  log(`bridge listening on ${PORT}, session dir ${SESSION_DIR}`);
  start().catch(e => log('start error', e));
});
