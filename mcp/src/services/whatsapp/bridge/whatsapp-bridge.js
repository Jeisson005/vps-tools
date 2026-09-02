#!/usr/bin/env node
// Baileys multi-session bridge for the VPS MCP gateway.
// Run on the HOST (Node + baileys):  node whatsapp-bridge.js --port 3010 --session-dir ./sessions/personal
// Exposes:
//   GET  /status    -> { connected, loggedIn, qr }
//   GET  /chats     -> [{ id, name }]
//   GET  /messages?chatId=<jid> -> [{ id, fromMe, text, ts }]
//   POST /send      -> { chatId, text } (JSON body)
const http = require('http');
const { useMultiFileAuthState, fetchLatestBaileysVersion, makeWASocket, DisconnectReason, downloadMediaMessage } = require('@whiskeysockets/baileys');
const pino = require('pino');

const args = process.argv.slice(2);
function opt(name, def) {
  const i = args.indexOf(name);
  return i >= 0 ? args[i + 1] : def;
}
const PORT = parseInt(opt('--port', String(Number(process.env.PORT || 3010))), 10);
const SESSION_DIR = opt('--session-dir', process.env.SESSION_DIR || './sessions/wa');
// Max messages kept per chat (in-memory). Default 10000. Bounded per chat: total
// RAM grows as chats x limit, so lower it on very chat-heavy accounts.
const MESSAGE_LIMIT = parseInt(process.env.WHATSAPP_MESSAGE_LIMIT || '10000', 10);

const logger = pino({ level: 'silent' });
let sock = null;
let qr = '';
let loggedIn = false;
let makeSocket = null;
let saveCreds = null;
const socketStore = { chats: [], messages: {}, byId: {} };

const log = (...a) => console.log(new Date().toISOString(), ...a);

let everOpen = false;

function attach(s) {
  s.ev.on('creds.update', saveCreds);
  s.ev.on('connection.update', (update) => {
    const { connection, lastDisconnect, qr: q } = update;
    if (q) qr = q;
    if (connection === 'open') {
      everOpen = true;
      loggedIn = true;
      qr = '';
      log('connected');
    }
    if (connection === 'close') {
      loggedIn = false;
      const code = lastDisconnect?.error?.output?.statusCode;
      if (code !== DisconnectReason.loggedOut) {
        // Reconnect, but with a pause: an early reconnect regenerates the QR and
        // can invalidate the code the user is about to scan. Only reconnect
        // quickly if we were already linked; otherwise wait longer.
        const delay = everOpen ? 3000 : 10000;
        setTimeout(() => {
          if (!loggedIn) {
            sock = makeSocket();
            attach(sock);
          }
        }, delay);
      }
    }
  });
  s.ev.on('messages.upsert', ({ messages }) => {
    for (const m of messages || []) {
      const jid = m.key?.remoteJid || 'unknown';
      if (m.key?.id) socketStore.byId[m.key.id] = m;
      if (!socketStore.messages[jid]) socketStore.messages[jid] = [];
      socketStore.messages[jid].unshift({
        id: m.key?.id, fromMe: !!m.key?.fromMe,
        media: mediaTypeOf(m.message),
        text: m.message?.conversation || m.message?.extendedTextMessage?.text || '',
        ts: m.messageTimestamp,
      });
      if (socketStore.messages[jid].length > MESSAGE_LIMIT) {
        const dropped = socketStore.messages[jid].pop();
        if (dropped && socketStore.byId[dropped.id]) delete socketStore.byId[dropped.id];
      }
      if (!socketStore.chats.find(c => c.id === jid)) socketStore.chats.push({ id: jid, name: jid });
    }
  });
}

function mediaTypeOf(msg) {
  if (!msg) return null;
  if (msg.imageMessage) return 'image';
  if (msg.videoMessage) return 'video';
  if (msg.audioMessage) return 'audio';
  if (msg.stickerMessage) return 'sticker';
  if (msg.documentMessage) return 'document';
  return null;
}

async function getMediaBuffer(m) {
  const content = m?.message;
  const type = mediaTypeOf(content);
  if (!type) throw new Error('mensaje sin media');
  const opts = {};
  if (content.documentMessage) opts.mimeType = content.documentMessage.mimetype;
  const buf = await downloadMediaMessage(m, 'buffer', opts, logger).catch(() => null) ||
               await downloadMediaMessage(m, 'buffer', {}, logger);
  let mimetype = content.documentMessage?.mimetype || content.imageMessage?.mimetype ||
                 content.videoMessage?.mimetype || content.audioMessage?.mimetype || 'application/octet-stream';
  return { buf, type, mimetype };
}

const MIME_BY_TYPE = {
  image: 'image/jpeg',
  video: 'video/mp4',
  audio: 'audio/ogg',
  sticker: 'image/webp',
  document: 'application/octet-stream',
};

async function sendMedia(chatId, mediaType, base64, caption, filename) {
  if (!sock) throw new Error('not connected');
  const buf = Buffer.from(base64, 'base64');
  const content = { caption: caption || '' };
  if (mediaType === 'image') content.image = buf;
  else if (mediaType === 'video') content.video = buf;
  else if (mediaType === 'audio') { content.audio = buf; content.ptt = false; }
  else if (mediaType === 'voice') { content.audio = buf; content.ptt = true; }
  else if (mediaType === 'sticker') content.sticker = buf;
  else { content.document = buf; content.mimetype = MIME_BY_TYPE.document; if (filename) content.fileName = filename; }
  const sent = await sock.sendMessage(chatId, content);
  return { status: 'sent', chatId, mediaType, id: sent?.key?.id };
}

async function start() {
  const { state, saveCreds: _saveCreds } = await useMultiFileAuthState(SESSION_DIR);
  saveCreds = _saveCreds;
  const { version } = await fetchLatestBaileysVersion();
  makeSocket = () => makeWASocket({
    version,
    auth: state,
    printQRInTerminal: false,
    logger,
    browser: ['Windows', 'Chrome', 'Chrome 127.0.0.0'],
    markOnlineOnConnect: false,
  });
  sock = makeSocket();
  attach(sock);
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
    if (url.pathname === '/send-media' && req.method === 'POST') {
      let body = '';
      for await (const chunk of req) body += chunk;
      const { chatId, mediaType, base64, caption, filename } = JSON.parse(body || '{}');
      return json(await sendMedia(chatId, mediaType, base64, caption, filename));
    }
    if (url.pathname === '/media') {
      const id = url.searchParams.get('id');
      const m = socketStore.byId[id];
      if (!m) throw new Error('mensaje no encontrado en buffer');
      const { buf, type, mimetype } = await getMediaBuffer(m);
      return json({ id, type, mimetype, base64: buf.toString('base64') });
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
