/**
 * Shared helpers for safely updating the persistent Steel browser profile
 * (~/.config/steel/profiles/persistent/context.json).
 *
 * Multiple concurrent persistent sessions (Hermes + OpenCode's
 * playwright-persistent, two Hermes chats at once, etc.) can each be syncing
 * their own cookie/localStorage snapshot back to this single shared file. A
 * plain overwrite is a lost-update race: whichever session releases last wins
 * and silently drops any login state the other session captured. Instead we
 * merge each incoming snapshot into whatever is currently on disk, and guard
 * the read-merge-write cycle with a short-lived lock so two processes syncing
 * at the same instant can't still race each other.
 *
 * Note this only ever adds/updates entries - it does not propagate deletions
 * (e.g. a cookie cleared by a logout in one session can be reintroduced by
 * another session's stale snapshot). For a profile whose whole purpose is
 * "stay logged in", losing a session's login silently is worse than an
 * occasional stale cookie, so this tradeoff is intentional.
 */

const fs = require('fs');
const { execSync } = require('child_process');

function isPlainObject(v) {
  return v !== null && typeof v === 'object' && !Array.isArray(v);
}

function mergeContext(existing, incoming) {
  existing = isPlainObject(existing) ? existing : {};
  incoming = isPlainObject(incoming) ? incoming : {};
  const merged = { ...existing, ...incoming };

  // Cookies: array of {domain, path, name, ...}. Merge by identity key,
  // incoming wins on conflict since it is the freshest snapshot.
  if (Array.isArray(existing.cookies) || Array.isArray(incoming.cookies)) {
    const cookieKey = (c) => `${c.domain || ''}|${c.path || ''}|${c.name || ''}`;
    const cookieMap = new Map();
    for (const c of (existing.cookies || [])) cookieMap.set(cookieKey(c), c);
    for (const c of (incoming.cookies || [])) cookieMap.set(cookieKey(c), c);
    merged.cookies = Array.from(cookieMap.values());
  }

  // Per-origin storage maps: { "<origin>": { "<key>": "<value>", ... } }.
  // Merge origin-by-origin so a session that only touched origin A never
  // wipes out entries a different session captured for origin B.
  for (const field of ['localStorage', 'sessionStorage', 'indexedDB']) {
    const existingField = existing[field];
    const incomingField = incoming[field];
    if (!isPlainObject(existingField) && !isPlainObject(incomingField)) continue;

    const mergedField = { ...(isPlainObject(existingField) ? existingField : {}) };
    const incomingOrigins = isPlainObject(incomingField) ? incomingField : {};
    for (const origin of Object.keys(incomingOrigins)) {
      const existingOrigin = mergedField[origin];
      const incomingOrigin = incomingOrigins[origin];
      mergedField[origin] = (isPlainObject(existingOrigin) && isPlainObject(incomingOrigin))
        ? { ...existingOrigin, ...incomingOrigin }
        : incomingOrigin;
    }
    merged[field] = mergedField;
  }

  return merged;
}

function readJsonSafe(filePath) {
  try {
    if (!fs.existsSync(filePath)) return null;
    const parsed = JSON.parse(fs.readFileSync(filePath, 'utf8'));
    return isPlainObject(parsed) ? parsed : null;
  } catch (e) {
    return null;
  }
}

function sleepMs(ms) {
  try { execSync(`sleep ${Math.max(ms, 10) / 1000}`); } catch (e) {}
}

// Atomic mkdir-based mutual exclusion. Best-effort: a crash between mkdir and
// rmdir leaves a stale lock, so a lock older than `timeoutMs` is reclaimed
// rather than blocked on forever.
function withFileLock(lockDir, fn, { timeoutMs = 5000, retryMs = 50 } = {}) {
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    try {
      fs.mkdirSync(lockDir);
      break;
    } catch (e) {
      if (e.code !== 'EEXIST') throw e;
      if (Date.now() > deadline) {
        try { fs.rmdirSync(lockDir); } catch (e2) {}
        continue;
      }
      sleepMs(retryMs);
    }
  }
  try {
    return fn();
  } finally {
    try { fs.rmdirSync(lockDir); } catch (e) {}
  }
}

// Reads the current persistent context, merges `incoming` into it, and
// atomically (write-tmp + rename) writes the result back.
function mergeAndWriteContext(contextFile, incoming) {
  return withFileLock(`${contextFile}.lock`, () => {
    const existing = readJsonSafe(contextFile) || {};
    const merged = mergeContext(existing, incoming);
    const tmpFile = `${contextFile}.${process.pid}.tmp`;
    fs.writeFileSync(tmpFile, JSON.stringify(merged, null, 2), 'utf8');
    fs.renameSync(tmpFile, contextFile);
    return merged;
  });
}

module.exports = { mergeContext, mergeAndWriteContext };
