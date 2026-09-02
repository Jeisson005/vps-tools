#!/usr/bin/env node
// Baileys multi-session bridge for the VPS MCP gateway.
// Run on the HOST (Node + baileys):  node whatsapp-bridge.js --port 3010 --session-dir ./sessions/personal
// Exposes:
//   GET  /status    -> { connected, loggedIn, qr }
//   GET  /chats     -> [{ id, name }]
//   GET  /messages?chatId=<jid> -> [{ id, fromMe, text, ts }]
//   POST /send      -> { chatId, text } (JSON body)
const http = require('http');
const fs = require('fs');
const path = require('path');
const { useMultiFileAuthState, fetchLatestBaileysVersion, makeWASocket, DisconnectReason, downloadMediaMessage } = require('@whiskeysockets/baileys');
const pino = require('pino');

const args = process.argv.slice(2);
function opt(name, def) {
  const i = args.indexOf(name);
  return i >= 0 ? args[i + 1] : def;
}
const PORT = parseInt(opt('--port', String(Number(process.env.PORT || 3010))), 10);
const SESSION_DIR = opt('--session-dir', process.env.SESSION_DIR || './sessions/wa');
// Max messages kept per chat in-memory (fast/media). Default 10000. RAM grows as
// chats x limit, so keep it moderate; older messages persist to disk.
const MESSAGE_LIMIT = parseInt(process.env.WHATSAPP_MESSAGE_LIMIT || '10000', 10);
// Max persisted history lines per chat on disk (real, restart-proof history).
const HISTORY_LIMIT = parseInt(process.env.WHATSAPP_HISTORY_LIMIT || '100000', 10);
const HISTORY_DIR = path.join(SESSION_DIR, 'history');
const MEDIA_DIR = path.join(SESSION_DIR, 'media');

let appendCounter = 0;
function ensureDir(d) { if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true }); }
ensureDir(HISTORY_DIR);
ensureDir(MEDIA_DIR);

const EXT_BY_MIME = {
  'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp', 'image/gif': 'gif',
  'video/mp4': 'mp4', 'video/3gp': '3gp', 'audio/ogg': 'oga', 'audio/opus': 'opus',
  'audio/mp4': 'm4a', 'audio/mpeg': 'mp3', 'application/pdf': 'pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx',
};
function extForMime(mime) { return EXT_BY_MIME[(mime || '').toLowerCase()] || 'bin'; }
function mediaFileFor(id, mime) { return `${id}.${extForMime(mime)}`; }
// Inline base64 only for small media; larger media is exposed as a download URL.
const MAX_INLINE = 4 * 1024 * 1024; // 4 MB

function historyFile(jid) {
  return path.join(HISTORY_DIR, (jid || 'unknown').replace(/[^a-zA-Z0-9@.\-_]/g, '_') + '.jsonl');
}

function appendHistory(jid, obj) {
  ensureDir(HISTORY_DIR);
  try {
    fs.appendFileSync(historyFile(jid), JSON.stringify(obj) + '\n', 'utf8');
  } catch (e) { /* ignore */ }
  // Occasionally trim the file to HISTORY_LIMIT lines to bound disk usage.
  if (++appendCounter % 250 === 0) pruneHistory(jid);
}

function pruneHistory(jid) {
  try {
    const f = historyFile(jid);
    if (!fs.existsSync(f)) return;
    const lines = fs.readFileSync(f, 'utf8').split('\n').filter(Boolean);
    if (lines.length > HISTORY_LIMIT) {
      // Delete media of messages being dropped before rewriting the file.
      const dropped = lines.slice(0, lines.length - HISTORY_LIMIT);
      for (const l of dropped) { try { const o = JSON.parse(l); if (o.id) deleteMedia(o.id); } catch (e) {} }
      fs.writeFileSync(f, lines.slice(lines.length - HISTORY_LIMIT).join('\n') + '\n', 'utf8');
    }
  } catch (e) { /* ignore */ }
}

function readHistory(jid, limit) {
  try {
    const f = historyFile(jid);
    if (!fs.existsSync(f)) return [];
    const lines = fs.readFileSync(f, 'utf8').split('\n').filter(Boolean);
    return lines.slice(Math.max(0, lines.length - limit)).map(l => { try { return JSON.parse(l); } catch (e) { return null; } }).filter(Boolean);
  } catch (e) { return []; }
}

const logger = pino({ level: 'silent' });
let sock = null;
let qr = '';
let loggedIn = false;
let makeSocket = null;
let saveCreds = null;
const socketStore = { chats: [], messages: {}, byId: {}, names: {}, lidJid: {} };

function contactName(jid) {
  return socketStore.names[jid] || '';
}
function resolveChatName(jid) {
  return contactName(jid) || jid;
}
function storeContactName(jid, name) {
  if (jid && name) socketStore.names[jid] = name;
}
function storeLidMapping(lidJid, realJid) {
  if (lidJid && realJid) socketStore.lidJid[lidJid] = realJid;
}
function realJidFor(jid) {
  return socketStore.lidJid[jid] || jid;
}

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
  s.ev.on('contacts.set', ({ contacts }) => {
    for (const c of contacts || []) { if (c?.jid) storeContactName(c.jid, c.notify || c.verifiedName || c.name || ''); }
  });
  s.ev.on('contacts.update', (contacts) => {
    for (const c of contacts || []) {
      if (!c?.jid) continue;
      storeContactName(c.jid, c.notify || c.verifiedName || c.name || '');
      if (c.lid) storeLidMapping(c.lid, c.jid);
    }
  });
  // Preload a window of history at connect (bounded by what WhatsApp syncs).
  s.ev.on('messaging-history.set', async ({ messages, contacts, chats }) => {
    for (const c of contacts || []) { if (c?.jid) storeContactName(c.jid, c.notify || c.verifiedName || c.name || ''); }
    for (const ch of chats || []) {
      if (ch?.id && ch.name) storeContactName(ch.id, ch.name);
      if (ch?.id && !socketStore.chats.find(x => x.id === ch.id)) socketStore.chats.push({ id: ch.id, name: ch.name || ch.id });
    }
    for (const m of messages || []) await ingestMessage(m);
  });

  s.ev.on('messages.upsert', async ({ messages }) => {
    for (const m of messages || []) await ingestMessage(m);
  });
}

async function ingestMessage(m) {
  const jid = m.key?.remoteJid || 'unknown';
  const id = m.key?.id;
  if (id && socketStore.byId[id]) return; // already ingested
  if (id) socketStore.byId[id] = m;
  if (m.pushName) storeContactName(realJidFor(jid), m.pushName);
  const senderKey = realJidFor(jid);
  const senderName = contactName(senderKey) || m.pushName || (jid === senderKey ? jid : senderKey);
  if (!socketStore.messages[jid]) socketStore.messages[jid] = [];
  const mediaType = mediaTypeOf(m.message);
  let mediaFile = '';
  if (mediaType) mediaFile = await persistMedia(m).catch(() => '');
  const entry = {
    id, fromMe: !!m.key?.fromMe,
    media: mediaType,
    mediaFile,
    sender: senderName,
    text: m.message?.conversation || m.message?.extendedTextMessage?.text || '',
    ts: m.messageTimestamp,
  };
  // Avoid duplicates from history + live sync by checking the tail.
  if (socketStore.messages[jid].some(x => x.id === id)) return;
  appendHistory(jid, entry);
  socketStore.messages[jid].unshift(entry);
  if (socketStore.messages[jid].length > MESSAGE_LIMIT) {
    const dropped = socketStore.messages[jid].pop();
    if (dropped && socketStore.byId[dropped.id]) delete socketStore.byId[dropped.id];
  }
  if (!socketStore.chats.find(c => c.id === jid)) socketStore.chats.push({ id: jid, name: resolveChatName(jid) });
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

async function persistMedia(m) {
  if (!m?.message || !mediaTypeOf(m.message) || !m.key?.id) return '';
  try {
    const { buf, type, mimetype } = await getMediaBuffer(m);
    if (!buf || !buf.length) return '';
    const file = mediaFileFor(m.key.id, mimetype || '');
    fs.writeFileSync(path.join(MEDIA_DIR, file), buf);
    return file;
  } catch (e) { return ''; }
}

function readMediaFile(filename) {
  try {
    const p = path.join(MEDIA_DIR, filename);
    if (!fs.existsSync(p)) return null;
    return fs.readFileSync(p);
  } catch (e) { return null; }
}

function findMediaFile(id) {
  try {
    const files = fs.readdirSync(MEDIA_DIR).filter(f => f.indexOf(id + '.') === 0);
    return files[0] || null;
  } catch (e) { return null; }
}

function deleteMedia(id) {
  try {
    const f = findMediaFile(id);
    if (f) fs.unlinkSync(path.join(MEDIA_DIR, f));
  } catch (e) { /* ignore */ }
}

function mimetypeForExt(ext) {
  const map = { jpg: 'image/jpeg', png: 'image/png', webp: 'image/webp', gif: 'image/gif', mp4: 'video/mp4',
    oga: 'audio/ogg', opus: 'audio/opus', m4a: 'audio/mp4', mp3: 'audio/mpeg', pdf: 'application/pdf',
    docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', bin: 'application/octet-stream' };
  return map[ext] || 'application/octet-stream';
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
      const set = new Set();
      const out = [];
      for (const c of socketStore.chats) {
        if (set.has(c.id)) continue;
        set.add(c.id);
        out.push({ id: c.id, name: resolveChatName(c.id) || c.name || c.id, realJid: realJidFor(c.id) });
      }
      // Include chats we have persisted history for (may not be in the live buffer).
      try {
        for (const f of fs.readdirSync(HISTORY_DIR)) {
          const id = f.replace(/\.jsonl$/, '');
          if (set.has(id)) continue;
          set.add(id);
          out.push({ id, name: resolveChatName(id) || id, realJid: realJidFor(id) });
        }
      } catch (e) { /* ignore */ }
      return json({ chats: out });
    }
    if (url.pathname === '/messages') {
      const chatId = url.searchParams.get('chatId');
      let msgs = socketStore.messages[chatId] || [];
      // If not in the live buffer, fall back to the persisted history.
      if (!msgs.length) msgs = readHistory(chatId, parseInt(url.searchParams.get('limit') || '50', 10) || 50);
      const mapped = msgs.map(x => ({ ...x, sender: x.sender || resolveChatName(x.id) || "" }));
      return json({ messages: mapped });
    }
    if (url.pathname === '/history') {
      const chatId = url.searchParams.get('chatId');
      const limit = parseInt(url.searchParams.get('limit') || '50', 10) || 50;
      return json({ messages: readHistory(chatId, Math.min(limit, HISTORY_LIMIT)) });
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
    const serveMedia = async (id) => {
      const existing = findMediaFile(id);
      if (existing) {
        const full = path.join(MEDIA_DIR, existing);
        const ext = existing.split('.').pop();
        const mimetype = mimetypeForExt(ext);
        const size = fs.statSync(full).size;
        return { id, type: 'media', mimetype, size, url: `/download?id=${id}`, base64: size <= MAX_INLINE ? fs.readFileSync(full).toString('base64') : '' };
      }
      const m = socketStore.byId[id];
      if (!m) throw new Error('mensaje no encontrado en buffer ni en disco');
      const { buf, type, mimetype } = await getMediaBuffer(m);
      return { id, type, mimetype, size: buf.length, url: `/download?id=${id}`, base64: buf.length <= MAX_INLINE ? buf.toString('base64') : '' };
    };
    if (url.pathname === '/media') {
      return json(await serveMedia(url.searchParams.get('id')));
    }
    if (url.pathname === '/download') {
      const id = url.searchParams.get('id');
      const existing = findMediaFile(id);
      if (existing) {
        const full = path.join(MEDIA_DIR, existing);
        const ext = existing.split('.').pop();
        const buf = fs.readFileSync(full);
        res.writeHead(200, { 'Content-Type': mimetypeForExt(ext), 'Content-Length': buf.length });
        return res.end(buf);
      }
      const m = socketStore.byId[id];
      if (!m) { res.writeHead(404); res.end('not found'); return; }
      const { buf, mimetype } = await getMediaBuffer(m);
      res.writeHead(200, { 'Content-Type': mimetype });
      return res.end(buf);
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
