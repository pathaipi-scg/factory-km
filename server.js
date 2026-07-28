const http = require('http');
const fs = require('fs');
const path = require('path');
const { spawn, spawnSync } = require('child_process');

// Resolve the Python interpreter used by the Office->PNG converters. A bare
// 'python' often resolves to a non-functional Windows Store stub (no PATH
// entry), making converters emit no JSON so every conversion reports
// ConversionFailed. Prefer PYTHON_BIN env, else newest per-user CPython, else 'python'.
const PYTHON_BIN = (function () {
  if (process.env.PYTHON_BIN) return process.env.PYTHON_BIN;
  // Prefer 'python' on PATH when it actually runs. This keeps production
  // (where python is on PATH) on its known-good interpreter, unchanged.
  try {
    const r = spawnSync('python', ['--version'], { encoding: 'utf8' });
    if (!r.error && r.status === 0 && /Python \d/.test((r.stdout || '') + (r.stderr || ''))) return 'python';
  } catch (e) { /* PATH python missing/broken; auto-detect below */ }
  const base = path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python');
  try {
    const dirs = fs.readdirSync(base).filter(function (d) { return /^Python\d+/i.test(d); }).sort().reverse();
    for (const d of dirs) {
      const exe = path.join(base, d, 'python.exe');
      if (fs.existsSync(exe)) return exe;
    }
  } catch (e) { /* fall back to PATH */ }
  return 'python';
})();
console.log('PYTHON_BIN =', PYTHON_BIN);
const CONFIG = require('./assets/js/config_multi.js');
const PORT = process.env.PORT || 3006;
const PUBLIC_ROOT = path.join(__dirname);

// --- Minimal .env loader (no dependency). Reads KEY=VALUE lines from a .env
// file in the project root into process.env without overriding existing vars. ---
const crypto = require('crypto');
(function loadDotEnv() {
  try {
    const raw = fs.readFileSync(path.join(__dirname, '.env'), 'utf8');
    raw.split(/\r?\n/).forEach(line => {
      const m = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$/);
      if (!m) return;
      let val = m[2];
      if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
        val = val.slice(1, -1);
      }
      if (!(m[1] in process.env)) process.env[m[1]] = val;
    });
  } catch (e) { /* no .env: fall back to defaults / real environment */ }
})();

// --- Rough login for testing. Two users; credentials come from .env (with safe
// defaults so it still runs if .env is missing). Sessions are in-memory and
// reset on restart — fine for a test login. ---
const USERS = {
  [process.env.FACTORY_USER || 'factory']: {
    password: process.env.FACTORY_PASS || 'factory123', role: 'factory', name: 'พนักงานโรงงาน'
  },
  [process.env.HR_USER || 'hr']: {
    password: process.env.HR_PASS || 'hr123', role: 'hr', name: 'ฝ่ายบุคคล (HR)'
  }
};
const sessions = new Map(); // token -> { username, role, name }

function parseCookies(req) {
  const out = {};
  (req.headers.cookie || '').split(';').forEach(p => {
    const i = p.indexOf('=');
    if (i > -1) out[p.slice(0, i).trim()] = decodeURIComponent(p.slice(i + 1).trim());
  });
  return out;
}
function getSession(req) {
  const token = parseCookies(req).km_session;
  return token ? (sessions.get(token) || null) : null;
}
// Viewer sessions (role 'viewer') can read/ask but not write. Use this to gate
// any endpoint that mutates the vault; it 401s viewers and the unauthenticated.
function requireWriteSession(req, res) {
  const s = getSession(req);
  if (!s || s.role === 'viewer') {
    res.writeHead(403, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ success: false, error: 'โหมด viewer ไม่มีสิทธิ์แก้ไข กรุณาเข้าสู่ระบบ' }));
    return null;
  }
  return s;
}
function readReqBody(req) {
  return new Promise(resolve => {
    let b = '';
    req.on('data', c => { b += c; });
    req.on('end', () => resolve(b));
  });
}
const KM_ROOT = process.env.KM_VAULT_ROOT || 'D:\\KM\\Vault';
// Plant tag written into generated CB/Jarvis case files (YAML `plant:` field).
// This server is the CB site, so default to CB; override via CASE_PLANT env
// (e.g. a local dev box can set CASE_PLANT=test).
const CASE_PLANT = process.env.CASE_PLANT || 'CB';

// Maps an uploaded file extension to the Python script that converts it into
// Slide###.png images. To support a new file type, drop a converter script in
// assets/python and register its extension(s) here.
const CONVERTERS = {
  '.ppt': 'ppt_to_png.py',
  '.pptx': 'ppt_to_png.py',
  '.xls': 'excel_to_png.py',
  '.xlsx': 'excel_to_png.py',
  '.pdf': 'pdf_to_png.py',
  '.doc': 'docx_to_png.py',
  '.docx': 'docx_to_png.py',
};

function getContentType(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  switch (ext) {
    case '.html': return 'text/html; charset=utf-8';
    case '.css': return 'text/css; charset=utf-8';
    case '.js': return 'application/javascript; charset=utf-8';
    case '.json': return 'application/json; charset=utf-8';
    case '.png': return 'image/png';
    case '.jpg': case '.jpeg': return 'image/jpeg';
    case '.svg': return 'image/svg+xml';
    default: return 'application/octet-stream';
  }
}

// POST plain text (JSON {content}) to a webhook and return its text reply.
function postTextToWebhook(content, webhookUrl) {
  return new Promise(resolve => {
    let payload;
    try {
      payload = JSON.stringify({ content });
    } catch {
      resolve({ success: false, text: '' });
      return;
    }
    const urlObj = new URL(webhookUrl);
    const proto = urlObj.protocol === 'https:' ? require('https') : require('http');
    const reqOpt = {
      method: 'POST',
      hostname: urlObj.hostname,
      port: urlObj.port || (urlObj.protocol === 'https:' ? 443 : 80),
      path: urlObj.pathname,
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(payload)
      }
    };
    const r = proto.request(reqOpt, res2 => {
      let body = '';
      res2.on('data', chunk => { body += chunk.toString(); });
      res2.on('end', () => {
        if (res2.statusCode >= 200 && res2.statusCode < 300) {
          resolve({ success: true, text: body });
        } else {
          resolve({ success: false, text: '' });
        }
      });
    });
    r.on('error', () => resolve({ success: false, text: '' }));
    r.write(payload);
    r.end();
  });
}

// Extract the "# Slide Analysis" section (Thai or English header) to end of doc.
function extractSlideAnalysisSection(mdText) {
  const match =
    mdText.match(/^# Slide Analysis\s*$/m) ||
    mdText.match(/^# การวิเคราะห์สไลด์\s*$/m);
  if (!match) return '';
  return mdText.slice(match.index).trim();
}

// Build a KM metadata block (and slide embeds if converted). One per file.
function buildKmMetadata(o) {
  let md = `# KM Information
KM_ID : ${o.kmId}
Source_File : ${o.sourceFile}
Target_Path : ${o.cleanTargetPath}
Category : ${o.category}
Machine : ${o.machine}
Status : Active
Version : 1
Processing_Status : ${o.status}
Slide_Count : ${o.slideCount}
PNG_Count : ${o.pngCount}
Converted_At : ${o.convertedAt}
Conversion_Duration_Sec : ${o.durationSec}
Asset_Folder : ${o.kmId}
Created : ${o.createdAt}
Training_Status : NotTrained
Training_Date :
Training_Model :
Training_Slides : 0
Training_Progress : 0
Training_Version : 0
`;
  if (o.status === 'Converted' && o.pngCount > 0) {
    md += `\n# Slides\n`;
    for (let i = 1; i <= o.pngCount; i++) {
      md += `![[${o.kmId}/Slide${String(i).padStart(3, '0')}.png]]\n\n`;
    }
  }
  return md;
}

// Convert one uploaded file to PNGs and update its KM metadata.
// Returns a Promise so multiple files can be converted sequentially (Office
// COM automation does not like several PowerPoint/Excel instances at once).
function convertKmFile(opts) {
  const { kmId, sourceFile, filePath, assetFolderPath, markdownPath,
    cleanTargetPath, category, machine, createdAt } = opts;

  const ext = path.extname(filePath).toLowerCase();
  const script = CONVERTERS[ext];
  if (!script) return Promise.resolve(); // non-convertible: leave as Uploaded

  const pythonScript = path.join(__dirname, 'assets', 'python', script);
  const fileType = ext.replace('.', '');

  // Office COM conversion fails intermittently for transient reasons (clipboard
  // contention during CopyPicture, a lingering Excel/PowerPoint instance, COM
  // timing), so the SAME file can fail one run and succeed the next. Retry a few
  // times before giving up instead of reporting ConversionFailed on a hiccup.
  const MAX_ATTEMPTS = 3;

  const writeMeta = (status, slideCount, pngCount, convertedAt, durationSec) => {
    fs.writeFileSync(markdownPath, buildKmMetadata({
      kmId, sourceFile, cleanTargetPath, category, machine, createdAt,
      status, slideCount, pngCount, convertedAt,
      durationSec: status === 'Converted' ? durationSec : 0
    }));
  };

  // Remove any partial Slide###.png left by a failed attempt so the next
  // attempt (and the final pngCount) start from a clean folder.
  const clearSlides = () => {
    try {
      fs.readdirSync(assetFolderPath)
        .filter(n => /^Slide\d{3}\.png$/.test(n))
        .forEach(n => { try { fs.unlinkSync(path.join(assetFolderPath, n)); } catch (e) { } });
    } catch (e) { /* folder missing: nothing to clear */ }
  };

  // One conversion attempt. Resolves with the parsed outcome (never rejects).
  const runOnce = (attempt) => new Promise(resolve => {
    const conversionStart = Date.now();
    let stdout = '', stderr = '';

    console.log(`--- ${fileType.toUpperCase()} to PNG conversion DEBUG (${kmId}) attempt ${attempt}/${MAX_ATTEMPTS} ---`);
    console.log('python script path:', pythonScript);
    console.log('source file path:', filePath);
    console.log('output folder:', assetFolderPath);

    let child;
    try {
      child = spawn(PYTHON_BIN, [pythonScript, filePath, assetFolderPath], { stdio: ['ignore', 'pipe', 'pipe'] });
    } catch (e) {
      resolve({ ok: false, code: -1 });
      return;
    }
    child.stdout.on('data', c => { stdout += c.toString(); });
    child.stderr.on('data', c => { stderr += c.toString(); });
    child.on('close', code => {
      const durationSec = Math.round((Date.now() - conversionStart) / 1000);
      let ok = false, slideCount = 0, convertedAt = '';
      console.log(`[${kmId}] stdout:`, stdout.trim());
      console.log(`[${kmId}] stderr:`, stderr.trim());
      console.log(`[${kmId}] exit code:`, code);
      try {
        const parsed = JSON.parse(stdout.trim());
        if (code === 0 && parsed.success) {
          ok = true;
          slideCount = parsed.slideCount || parsed.sheetCount || 0;
          convertedAt = new Date().toISOString().replace('T', ' ').split('.')[0];
        }
      } catch (e) { /* ok stays false */ }
      let pngCount = 0;
      try {
        pngCount = fs.readdirSync(assetFolderPath).filter(n => /^Slide\d{3}\.png$/.test(n)).length;
      } catch (e) { pngCount = 0; }
      resolve({ ok, slideCount, pngCount, convertedAt, durationSec, code });
    });
    child.on('error', err => {
      console.error('conversion spawn error:', err);
      resolve({ ok: false, code: -1 });
    });
  });

  return (async () => {
    let r = { ok: false };
    for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
      r = await runOnce(attempt);
      if (r.ok) break;
      if (attempt < MAX_ATTEMPTS) {
        console.log(`[${kmId}] conversion attempt ${attempt} failed (code ${r.code}); clearing partial output and retrying...`);
        clearSlides(); // drop half-written PNGs before the next try
        await new Promise(res => setTimeout(res, 1500)); // let Excel/clipboard settle
      }
    }
    if (r.ok) {
      writeMeta('Converted', r.slideCount, r.pngCount, r.convertedAt, r.durationSec);
    } else {
      clearSlides();
      writeMeta('ConversionFailed', 0, 0, '', 0);
    }
    console.log('KM conversion result:', {
      KM_ID: kmId, sourceFile,
      slideCount: r.ok ? r.slideCount : 0,
      pngCount: r.ok ? r.pngCount : 0,
      status: r.ok ? 'Converted' : 'ConversionFailed'
    });
  })();
}

// Derive the meeting date and case_id prefix for a CB/Jarvis case file from the
// KM's Source_File (e.g. "..._20260612_..." or "CB120626..."), falling back to
// the Created timestamp. Returns { date: 'YYYY-MM-DD', baseId: 'MTN-ddmmyy' }.
function deriveCaseDate(sourceFile, kmStem, created) {
  for (const s of [sourceFile, kmStem]) {
    if (!s) continue;
    let m = s.match(/(20\d{2})(\d{2})(\d{2})/); // yyyymmdd (most reliable)
    if (m) return { date: `${m[1]}-${m[2]}-${m[3]}`, baseId: `MTN-${m[3]}${m[2]}${m[1].slice(2)}` };
    m = s.match(/CB(\d{2})(\d{2})(\d{2})/); // CBddmmyy
    if (m) return { date: `20${m[3]}-${m[2]}-${m[1]}`, baseId: `MTN-${m[1]}${m[2]}${m[3]}` };
  }
  const d = (created || '').split(' ')[0];
  return { date: d, baseId: 'MTN-' + d.replace(/-/g, '') };
}

// Build CB/Jarvis case-based markdown from the cases[] returned by md_cases.
// One YAML block + 4 sections (อาการ/สาเหตุ/วิธีแก้/ผลลัพธ์) per case, split by
// blank lines. plant/department are fixed to test/CB for now.
function buildCaseMarkdown(cases, date, baseId, sourceFile) {
  const blocks = cases.map((c, i) => {
    const suffix = cases.length > 1 ? `-${String(i + 1).padStart(2, '0')}` : '';
    let result = (c.result || '').trim() || 'ไม่ทราบผลลัพธ์';
    result += ` (จากประชุม morning talk CB ${date}, ไฟล์ต้นทาง: ${sourceFile})`;
    const tags = Array.isArray(c.tags) && c.tags.length ? c.tags : ['morning_talk'];
    const out = `---
case_id: ${baseId}${suffix}
date: ${date}
source: morning_meeting
plant: ${CASE_PLANT}
department: CB
line:
machine: ${(c.machine || '').trim()}
component: ${(c.component || '').trim()}
category: ${(c.category || '').trim()}
severity: ${(c.severity || '').trim()}
status: review
downtime_min: 0
parts_used:
tags: [${tags.join(', ')}]
---

# อาการ (Symptom)
${(c.symptom || '').trim()}

# สาเหตุ (Root cause)
${(c.cause || '').trim()}

# วิธีแก้ (Solution)
${(c.solution || '').trim()}

# ผลลัพธ์ (Result)
${result}
`;
    return out.replace(/\n{3,}/g, '\n\n').trim();
  });
  return blocks.join('\n\n') + '\n';
}

function isIgnoredDir(name) {
  // Ignore system folders
  if (name === '.obsidian') return true;

  // Ignore all KM metadata and image folders (KM_YYYYMMDD_HHMMSS format)
  if (/^KM_/.test(name)) return true;

  // All other folder names are valid logical nodes (Process/Machine/SubMachine)
  return false;
}

function readFolderTree(dir) {
  let entries;
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch (e) {
    return [];
  }

  // Filter to directories only, exclude ignored folders
  const validFolders = entries.filter(entry =>
    entry.isDirectory() && !isIgnoredDir(entry.name)
  );

  // Build tree recursively
  return validFolders.map(entry => {
    const fullPath = path.join(dir, entry.name);
    const children = readFolderTree(fullPath);
    const node = { name: entry.name };
    if (children.length > 0) {
      node.children = children;
    }
    return node;
  });
}

function parseContentDisposition(disposition) {
  const result = {};
  const parts = disposition.split(';').map(part => part.trim());
  parts.forEach(part => {
    const [key, value] = part.split('=');
    if (value) {
      result[key] = value.replace(/^"|"$/g, '');
    } else {
      result.type = key;
    }
  });
  return result;
}

function parseMultipart(bodyBuffer, boundary) {
  const boundaryBuffer = Buffer.from(boundary);
  const parts = [];
  let start = bodyBuffer.indexOf(boundaryBuffer);
  if (start === -1) return parts;
  start += boundaryBuffer.length;

  while (start < bodyBuffer.length) {
    const end = bodyBuffer.indexOf(boundaryBuffer, start);
    if (end === -1) break;
    let part = bodyBuffer.slice(start, end);
    if (part.slice(0, 2).equals(Buffer.from('\r\n'))) {
      part = part.slice(2);
    }
    if (part.slice(-2).equals(Buffer.from('\r\n'))) {
      part = part.slice(0, -2);
    }
    const headerEnd = part.indexOf(Buffer.from('\r\n\r\n'));
    if (headerEnd === -1) break;
    const headerText = part.slice(0, headerEnd).toString('utf8');
    const content = part.slice(headerEnd + 4);
    const headers = {};
    headerText.split('\r\n').forEach(line => {
      const idx = line.indexOf(':');
      if (idx !== -1) {
        const key = line.slice(0, idx).trim().toLowerCase();
        const value = line.slice(idx + 1).trim();
        headers[key] = value;
      }
    });
    parts.push({ headers, content });
    start = end + boundaryBuffer.length;
  }
  return parts;
}

function sanitizeTargetPath(targetPath) {
  if (!targetPath) return '';
  return targetPath.replace(/\\/g, '/').replace(/\.\./g, '').replace(/^\//, '').replace(/\/$/, '');
}

function formatKmId(now = new Date()) {
  const pad = n => String(n).padStart(2, '0');
  const date = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}`;
  const time = `${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`;
  return `KM_${date}_${time}`;
}

const SERVER_START_TIME = new Date().toISOString();

const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);

  // --- Auth: login / logout / whoami (rough, for testing) ---
  if (req.method === 'POST' && url.pathname === '/api/login') {
    readReqBody(req).then(body => {
      let data = {};
      try { data = JSON.parse(body || '{}'); } catch (e) { /* invalid json */ }
      const username = (data.username || '').trim();
      const u = USERS[username];
      if (!u || u.password !== data.password) {
        res.writeHead(401, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ success: false, error: 'username หรือ password ไม่ถูกต้อง' }));
        return;
      }
      const token = crypto.randomBytes(24).toString('hex');
      sessions.set(token, { username, role: u.role, name: u.name });
      res.writeHead(200, {
        'Content-Type': 'application/json',
        'Set-Cookie': `km_session=${token}; HttpOnly; Path=/; SameSite=Lax; Max-Age=86400`
      });
      res.end(JSON.stringify({ success: true, role: u.role, name: u.name }));
    });
    return;
  }

  // --- Viewer login: no password. Creates a read-only ('viewer') session so
  // shop-floor users can ask without typing credentials. Write endpoints reject
  // this role via requireWriteSession. ---
  if (req.method === 'POST' && url.pathname === '/api/login/viewer') {
    const token = crypto.randomBytes(24).toString('hex');
    sessions.set(token, { username: 'viewer', role: 'viewer', name: 'ผู้ชม (Viewer)' });
    res.writeHead(200, {
      'Content-Type': 'application/json',
      'Set-Cookie': `km_session=${token}; HttpOnly; Path=/; SameSite=Lax; Max-Age=86400`
    });
    res.end(JSON.stringify({ success: true, role: 'viewer', name: 'ผู้ชม (Viewer)' }));
    return;
  }

  if (req.method === 'POST' && url.pathname === '/api/logout') {
    const token = parseCookies(req).km_session;
    if (token) sessions.delete(token);
    res.writeHead(200, {
      'Content-Type': 'application/json',
      'Set-Cookie': 'km_session=; HttpOnly; Path=/; Max-Age=0'
    });
    res.end(JSON.stringify({ success: true }));
    return;
  }

  if (req.method === 'GET' && url.pathname === '/api/me') {
    const s = getSession(req);
    res.writeHead(s ? 200 : 401, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(s
      ? { loggedIn: true, username: s.username, role: s.role, name: s.name }
      : { loggedIn: false }));
    return;
  }

  if (req.method === 'GET' && url.pathname === '/api/km-folders') {
    console.log('\n=== DEBUG: /api/km-folders ===');
    console.log('Server started:', SERVER_START_TIME);
    console.log('Server.js path:', __filename);
    console.log('isIgnoredDir("KM_20260602_095214"):', isIgnoredDir('KM_20260602_095214'));
    console.log('==============================\n');

    const folders = readFolderTree(KM_ROOT);
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(folders));
    return;
  }

  if (req.method === 'POST' && url.pathname === '/api/km/upload') {
    if (!requireWriteSession(req, res)) return;
    // Conversion validation checklist:
    // - 1 slide PPT
    // - 10 slide PPT
    // - 100 slide PPT
    // - corrupted PPT
    // - password protected PPT
    // - empty PPT
    // Expected behavior:
    // - upload succeeds immediately
    // - PPT conversion runs in background
    // - metadata updated in-place
    // - no duplicate metadata files
    // - no orphan POWERPNT.EXE processes
    const contentType = req.headers['content-type'] || '';
    const match = contentType.match(/boundary=(.+)$/);
    if (!match) {
      res.writeHead(400, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Missing boundary in content-type' }));
      return;
    }
    const boundary = `--${match[1]}`;
    const chunks = [];
    req.on('data', chunk => chunks.push(chunk));
    req.on('end', () => {
      const bodyBuffer = Buffer.concat(chunks);
      const parts = parseMultipart(bodyBuffer, boundary);
      const files = [];
      let targetPath = '';

      parts.forEach(part => {
        const disposition = part.headers['content-disposition'];
        if (!disposition) return;
        const meta = parseContentDisposition(disposition);
        if (meta.name === 'targetPath') {
          targetPath = part.content.toString('utf8').trim();
          return;
        }
        if (meta.filename) {
          files.push({ filename: meta.filename, content: part.content });
        }
      });

      const cleanTargetPath = sanitizeTargetPath(targetPath);
      if (!cleanTargetPath) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Invalid targetPath' }));
        return;
      }

      if (files.length === 0) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'No files uploaded' }));
        return;
      }

      const destinationDir = path.join(KM_ROOT, cleanTargetPath);
      if (!destinationDir.startsWith(KM_ROOT)) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Invalid targetPath' }));
        return;
      }

      try {
        fs.mkdirSync(destinationDir, { recursive: true });
      } catch (e) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Unable to create target directory' }));
        return;
      }

      // Derive Category and Machine from target path (shared across files).
      const segments = cleanTargetPath.split('/').filter(Boolean);
      const category = segments.length ? segments[0] : '';
      const machine = segments.length ? segments[segments.length - 1] : '';
      const createdAt = new Date().toISOString().replace('T', ' ').split('.')[0];

      // One KM per uploaded file. KM_IDs must keep the KM_YYYYMMDD_HHMMSS shape
      // (other endpoints match it), so bump the second to keep each unique.
      const uniqueKmMs = startMs => {
        let t = startMs;
        while (fs.existsSync(path.join(destinationDir, formatKmId(new Date(t)) + '.md'))) {
          t += 1000;
        }
        return t;
      };

      const created = [];
      let nextMs = Date.now();
      files.forEach(file => {
        const safeFilename = path.basename(file.filename);
        const ms = uniqueKmMs(nextMs);
        nextMs = ms + 1000;
        const kmId = formatKmId(new Date(ms));

        const filePath = path.join(destinationDir, safeFilename);
        fs.writeFileSync(filePath, file.content);

        const assetFolderPath = path.join(destinationDir, kmId);
        try { fs.mkdirSync(assetFolderPath, { recursive: true }); } catch (e) { /* non-fatal */ }

        const markdownPath = path.join(destinationDir, `${kmId}.md`);
        fs.writeFileSync(markdownPath, buildKmMetadata({
          kmId, sourceFile: safeFilename, cleanTargetPath, category, machine, createdAt,
          status: 'Uploaded', slideCount: 0, pngCount: 0, convertedAt: '', durationSec: 0
        }));

        const ext = path.extname(safeFilename).toLowerCase();
        created.push({
          kmId, sourceFile: safeFilename, filePath, assetFolderPath, markdownPath,
          convertible: !!CONVERTERS[ext]
        });
      });

      console.log('KMs created =', created.map(c => c.kmId).join(', '));

      // Stream upload+conversion progress as NDJSON (one {type:'progress'} line
      // per file, then a {type:'done'} line). The client keeps its UI open until
      // 'done' so files are never trainable while still being converted.
      res.writeHead(200, { 'Content-Type': 'application/x-ndjson; charset=utf-8' });
      const total = created.length;

      // Convert each convertible file one after another (sequential — Office COM
      // automation does not tolerate multiple PowerPoint/Excel instances at once).
      (async () => {
        let done = 0;
        res.write(JSON.stringify({ type: 'progress', done: 0, total }) + '\n');
        try {
          for (const c of created) {
            // Announce the file we're about to process so the UI shows the
            // file currently being uploaded/converted (not the one just done).
            res.write(JSON.stringify({ type: 'progress', done, total, current: c.sourceFile }) + '\n');
            if (c.convertible) {
              await convertKmFile({
                kmId: c.kmId, sourceFile: c.sourceFile, filePath: c.filePath,
                assetFolderPath: c.assetFolderPath, markdownPath: c.markdownPath,
                cleanTargetPath, category, machine, createdAt
              });
            }
            done++;
            res.write(JSON.stringify({ type: 'progress', done, total, current: c.sourceFile }) + '\n');
          }
          res.write(JSON.stringify({
            type: 'done',
            success: true,
            targetPath: cleanTargetPath,
            count: created.length,
            kms: created.map(c => ({ kmId: c.kmId, sourceFile: c.sourceFile }))
          }) + '\n');
        } catch (e) {
          // Files are already written; surface the error but still close the
          // stream so the client UI never hangs.
          console.error('upload conversion error:', e);
          res.write(JSON.stringify({ type: 'done', success: false, error: e.message }) + '\n');
        }
        res.end();
      })();
    });
    return;
  }

  if (req.method === 'POST' && url.pathname === '/api/km/train') {
    if (!requireWriteSession(req, res)) return;
    let body = '';
    req.on('data', chunk => { body += chunk.toString(); });
    req.on('end', async () => {
      try {
        const data = JSON.parse(body);
        const kmIds = Array.isArray(data.kmIds) ? data.kmIds.filter(x => !!x) : [];
        if (!kmIds.length) {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ success: false, error: 'Missing kmIds' }));
          return;
        }
        const webhookUrl = (typeof CONFIG.N8N_KM_URL !== 'undefined' && CONFIG.N8N_KM_URL)
          ? CONFIG.N8N_KM_URL
          : 'http://localhost:1889/webhook/md_pic';
        const summaryUrl = (typeof CONFIG.N8N_SUMMARY_URL !== 'undefined' && CONFIG.N8N_SUMMARY_URL)
          ? CONFIG.N8N_SUMMARY_URL
          : 'http://localhost:1889/webhook/md_summary';
        const casesUrl = (typeof CONFIG.N8N_CASES_URL !== 'undefined' && CONFIG.N8N_CASES_URL)
          ? CONFIG.N8N_CASES_URL
          : 'http://localhost:1889/webhook/md_cases';
        let updated = 0;
        let results = [];
        const now = new Date().toISOString().replace('T', ' ').split('.')[0];

        // Utility: Read and parse metadata field from md file
        function readMetaField(mdText, key) {
          const m = mdText.match(new RegExp(`^${key} *: *(.*)$`, 'm'));
          return m ? m[1].trim() : '';
        }
        // Utility: Find SlideNNN.png in assetFolder
        function findSlidePNGs(assetFolder) {
          try {
            return fs.readdirSync(assetFolder)
              .filter(name => /^Slide\d{3}\.png$/.test(name))
              .sort()
              .map(name => path.join(assetFolder, name));
          } catch {
            return [];
          }
        }
        // POST PNG with error-handling
        function postPngToWebhook(pngPath, webhookUrl) {
          return new Promise((resolve, reject) => {
            const boundary = '----WebKitFormBoundary' + Math.random().toString(16).slice(2);
            const data = [];
            fs.readFile(pngPath, (err, fileBuf) => {
              if (err) {
                // If PNG read fails, resolve error markdown
                resolve({ success: false, markdown: `**[Error: ไม่พบไฟล์ ${path.basename(pngPath)}]**` });
                return;
              }
              data.push(Buffer.from(`--${boundary}\r\n`));
              data.push(Buffer.from(`Content-Disposition: form-data; name="data"; filename="${path.basename(pngPath)}"\r\n`));
              data.push(Buffer.from('Content-Type: image/png\r\n\r\n'));
              data.push(fileBuf);
              data.push(Buffer.from(`\r\n--${boundary}--\r\n`));
              const urlObj = new URL(webhookUrl);
              const proto = urlObj.protocol === 'https:' ? require('https') : require('http');
              const reqOpt = {
                method: 'POST',
                hostname: urlObj.hostname,
                port: urlObj.port || (urlObj.protocol === 'https:' ? 443 : 80),
                path: urlObj.pathname,
                headers: {
                  'Content-Type': 'multipart/form-data; boundary=' + boundary,
                  'Content-Length': Buffer.concat(data).length
                }
              };
              const req = proto.request(reqOpt, res => {
                let body = '';
                res.on('data', chunk => { body += chunk.toString(); });
                res.on('end', () => {
                  if (res.statusCode >= 200 && res.statusCode < 300) {
                    resolve({ success: true, markdown: body });
                  } else {
                    resolve({ success: false, markdown: `**[Error: Slide ส่ง n8n ล้มเหลว status ${res.statusCode}]**` });
                  }
                });
              });
              req.on('error', err => resolve({ success: false, markdown: `**[Error: ส่ง n8n ล้มเหลว: ${err.message}]**` }));
              req.write(Buffer.concat(data));
              req.end();
            });
          });
        }
        // Remove existing # Slide Analysis section
        function removeSlideAnalysis(mdText) {
          return mdText.replace(/\n# Slide Analysis[\s\S]*$/m, '');
        }

        // Pre-count total slides across all selected KMs so progress is per-slide
        // (smooth even when a single file has many slides).
        let totalSlides = 0;
        for (const id of kmIds) {
          let mp = null;
          (function find(dir) {
            let entries;
            try { entries = fs.readdirSync(dir, { withFileTypes: true }); } catch { return; }
            for (const e of entries) {
              const p = path.join(dir, e.name);
              if (e.isDirectory()) find(p);
              else if (e.isFile() && e.name === id + '.md') mp = p;
            }
          })(KM_ROOT);
          if (!mp) continue;
          let txt;
          try { txt = fs.readFileSync(mp, 'utf8'); } catch { continue; }
          const af = readMetaField(txt, 'Asset_Folder');
          const folder = af ? path.join(path.dirname(mp), af) : null;
          totalSlides += folder ? findSlidePNGs(folder).length : 0;
        }

        // Stream progress as NDJSON (per slide), then a {type:'done'} line.
        res.writeHead(200, { 'Content-Type': 'application/x-ndjson; charset=utf-8' });
        const total = totalSlides;
        let slidesDone = 0;
        res.write(JSON.stringify({ type: 'progress', done: 0, total }) + '\n');
        for (const kmId of kmIds) {
          // 1. Find KM markdown
          let mdPath;
          function walkFindMd(dir) {
            const entries = fs.readdirSync(dir, { withFileTypes: true });
            for (const entry of entries) {
              const entryPath = path.join(dir, entry.name);
              if (entry.isDirectory()) {
                walkFindMd(entryPath);
              } else if (entry.isFile() && entry.name === kmId + '.md') {
                mdPath = entryPath;
              }
            }
          }
          walkFindMd(KM_ROOT);
          if (!mdPath) {
            results.push({ kmId, updated: false, error: 'KM markdown not found' });
            continue;
          }
          // 2. Read Asset_Folder from markdown
          let mdText = fs.readFileSync(mdPath, 'utf8');
          const sourceFile = readMetaField(mdText, 'Source_File');
          const assetFolderId = readMetaField(mdText, 'Asset_Folder');
          const assetFolder = assetFolderId
            ? path.join(path.dirname(mdPath), assetFolderId)
            : null;
          // 3. Find Slide*.png
          const slides = assetFolder ? findSlidePNGs(assetFolder) : [];
          if (!slides.length) {
            // Update "Training" meta fields and blank Slide Analysis
            let out = removeSlideAnalysis(mdText);
            out += `\n# Slide Analysis\n\n**[Error: ไม่พบไฟล์ Slide PNG]**\n`;
            out = out.replace(/Training_Status[^\n]*:.*/, 'Training_Status : NotTrained');
            out = out.replace(/Training_Date[^\n]*:.*/, `Training_Date : ${now}`);
            out = out.replace(/Training_Slides[^\n]*:.*/, `Training_Slides : 0`);
            fs.writeFileSync(mdPath, out, 'utf8');
            results.push({ kmId, updated: false, error: 'No Slide PNG' });
            continue;
          }
          // 4-5. Send in batches of 5, collect markdown for each
          let slideMarkdowns = [];
          let allSuccess = true;
          for (let i = 0; i < slides.length; i += 5) {
            const batch = slides.slice(i, i + 5);
            // Still send 5 at a time (speed), but report each slide as it finishes
            // so the count moves one-by-one. Promise.all keeps result order.
            const batchResults = await Promise.all(
              batch.map(async slide => {
                const r = await postPngToWebhook(slide, webhookUrl);
                slidesDone += 1;
                res.write(JSON.stringify({ type: 'progress', done: slidesDone, total, current: sourceFile }) + '\n');
                return r;
              })
            );
            // push all returned markdown (error or success)
            slideMarkdowns.push(...batchResults.map(r => r.markdown));
            // mark as not all success if any failed
            if (batchResults.some(r => !r.success)) allSuccess = false;
          }
          // 6. Remove old Slide Analysis and append new
          let out = removeSlideAnalysis(mdText);
          out += '\n# Slide Analysis\n\n' + slideMarkdowns.map((md, i) => `## Slide ${i + 1}\n${md}`).join('\n\n');
          // 7-9. Update metadata: set Trained only if all succeeded, set Training_Date, Training_Slides
          if (allSuccess) {
            out = out.replace(/Training_Status[^\n]*:.*/, 'Training_Status : Trained');
          } else {
            out = out.replace(/Training_Status[^\n]*:.*/, 'Training_Status : TrainingError');
          }
          out = out.replace(/Training_Date[^\n]*:.*/, `Training_Date : ${now}`);
          out = out.replace(/Training_Slides[^\n]*:.*/, `Training_Slides : ${slides.length}`);
          fs.writeFileSync(mdPath, out, 'utf8');

          // Generate a condensed summary file alongside the trained KM, so Ask-KM
          // can send both the full analysis and a short overview. Only for fully
          // trained KMs (we have real analysis to summarize).
          if (allSuccess) {
            const analysisText = slideMarkdowns.map((md, i) => `## Slide ${i + 1}\n${md}`).join('\n\n');
            const summaryRes = await postTextToWebhook(analysisText, summaryUrl);
            if (summaryRes.success && summaryRes.text.trim()) {
              // Reuse the trained file's metadata header so the summary file keeps
              // the same format, then put the summary under # Slide Analysis.
              const headerPart = out.split(/\n# Slides|\n# Slide Analysis/)[0].trimEnd();
              const summaryMd = `${headerPart}\n\n# Slide Analysis\n\n${summaryRes.text.trim()}\n`;
              const summaryPath = mdPath.replace(/\.md$/, '_summary.md');
              try {
                fs.writeFileSync(summaryPath, summaryMd, 'utf8');
                console.log('Summary written =', summaryPath); // log
              } catch (e) {
                console.log('Summary write failed =', e.message); // log
              }
            } else {
              console.log('Summary skipped (md_summary returned nothing) for', kmId); // log
            }
          }

          // Third output: a CB/Jarvis case file, but only for Morning Talk KMs.
          // Detect by the KM's Category (normalised so "Morning Talk" and
          // "MorningTalk" both match). The Slide Analysis is sent to the md_cases
          // webhook, which returns {cases:[...]}; we format those into case-based
          // markdown and write CB<ddmmyy>.md under cases/<plant>/CB. plant/
          // department are fixed to test/CB for now (future: filter by department).
          // Best-effort: any failure is logged and never blocks the response.
          if (allSuccess) {
            const catNorm = readMetaField(mdText, 'Category').replace(/\s+/g, '').toLowerCase();
            if (catNorm === 'morningtalk' || catNorm === 'moringtalk') {
              try {
                const analysisText = slideMarkdowns.map((md, i) => `## Slide ${i + 1}\n${md}`).join('\n\n');
                const casesRes = await postTextToWebhook(analysisText, casesUrl);
                let cases = [];
                if (casesRes.success) {
                  try {
                    const parsed = JSON.parse(casesRes.text);
                    if (parsed && Array.isArray(parsed.cases)) cases = parsed.cases;
                  } catch (e) {
                    console.log('Cases JSON parse failed for', kmId, '=', e.message); // log
                  }
                }
                if (cases.length) {
                  const { date, baseId } = deriveCaseDate(sourceFile, kmId, readMetaField(mdText, 'Created'));
                  const ddmmyy = baseId.replace('MTN-', '');
                  const outName = /^\d{6}$/.test(ddmmyy) ? `CB${ddmmyy}.md` : `${kmId}.md`;
                  const casesDir = path.join(KM_ROOT, 'cases', 'CB');
                  const casesPath = path.join(casesDir, outName);
                  try {
                    fs.mkdirSync(casesDir, { recursive: true });
                    fs.writeFileSync(casesPath, buildCaseMarkdown(cases, date, baseId, sourceFile), 'utf8');
                    console.log('Cases file written =', casesPath, `(${cases.length} cases)`); // log
                  } catch (e) {
                    console.log('Cases write failed =', e.message); // log
                  }
                } else {
                  console.log('Cases skipped (md_cases returned no cases) for', kmId); // log
                }
              } catch (e) {
                console.log('Cases convert error =', e.message); // log
              }
            }
          }

          updated++;
          results.push({ kmId, updated: true, slideCount: slides.length, success: allSuccess });
        }
        res.write(JSON.stringify({ type: 'done', success: true, updated, results }) + '\n');
        res.end();
      } catch (e) {
        if (res.headersSent) {
          try { res.write(JSON.stringify({ type: 'done', success: false, error: e.message }) + '\n'); } catch (e2) { }
          res.end();
        } else {
          res.writeHead(500, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ success: false, error: e.message }));
        }
      }
    });
    return;
  }

  if (req.method === 'GET' && url.pathname === '/api/km/not-trained') {
    function walkVault(dir, output) {
      let entries;
      try {
        entries = fs.readdirSync(dir, { withFileTypes: true });
      } catch (e) {
        return;
      }
      for (const entry of entries) {
        const entryPath = path.join(dir, entry.name);
        if (entry.isDirectory()) {
          // Ignore asset folders (KM_YYYYMMDD_HHMMSS format)
          if (/^KM_\d{8}_\d{6}$/.test(entry.name)) continue;
          // Skip .obsidian or similar
          if (entry.name === '.obsidian') continue;
          walkVault(entryPath, output);
        } else if (entry.isFile() && /^KM_\d{8}_\d{6}\.md$/.test(entry.name)) {
          // Try read the metadata
          const mdPath = entryPath;
          let contents;
          try {
            contents = fs.readFileSync(mdPath, 'utf8');
          } catch (e) {
            continue;
          }
          // Extract metadata fields
          // Training_Status
          const getMeta = (field) => {
            const m = contents.match(new RegExp(`${field} *: *(.+)$`, 'm'));
            return m ? m[1].trim() : '';
          };
          const trainingStatus = getMeta('Training_Status');
          if (trainingStatus !== 'NotTrained') continue;
          const kmId = getMeta('KM_ID') || entry.name.replace(/\.md$/, '');
          const sourceFile = getMeta('Source_File');
          const category = getMeta('Category');
          const machine = getMeta('Machine');
          let slideCount = parseInt(getMeta('Slide_Count'), 10);
          if (isNaN(slideCount)) slideCount = 0;
          output.push({
            kmId,
            sourceFile,
            category,
            machine,
            slideCount,
            mdPath
          });
        }
      }
    }
    const output = [];
    walkVault(KM_ROOT, output);
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(output));
    return;
  }

  // --- List trained KMs (for Add Summary) ---
  if (req.method === 'GET' && url.pathname === '/api/km/trained-list') {
    function walkVault(dir, output) {
      let entries;
      try {
        entries = fs.readdirSync(dir, { withFileTypes: true });
      } catch (e) {
        return;
      }
      for (const entry of entries) {
        const entryPath = path.join(dir, entry.name);
        if (entry.isDirectory()) {
          if (/^KM_\d{8}_\d{6}$/.test(entry.name)) continue;
          if (entry.name === '.obsidian') continue;
          walkVault(entryPath, output);
        } else if (entry.isFile() && /^KM_\d{8}_\d{6}\.md$/.test(entry.name)) {
          let contents;
          try {
            contents = fs.readFileSync(entryPath, 'utf8');
          } catch (e) {
            continue;
          }
          const getMeta = (field) => {
            const m = contents.match(new RegExp(`${field} *: *(.+)$`, 'm'));
            return m ? m[1].trim() : '';
          };
          if (getMeta('Training_Status') !== 'Trained') continue;
          output.push({
            kmId: getMeta('KM_ID') || entry.name.replace(/\.md$/, ''),
            sourceFile: getMeta('Source_File'),
            category: getMeta('Category'),
            machine: getMeta('Machine'),
            hasSummary: fs.existsSync(entryPath.replace(/\.md$/, '_summary.md'))
          });
        }
      }
    }
    const output = [];
    walkVault(KM_ROOT, output);
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(output));
    return;
  }

  // --- Generate summary files for already-trained KMs (no re-training) ---
  if (req.method === 'POST' && url.pathname === '/api/km/summarize') {
    if (!requireWriteSession(req, res)) return;
    let body = '';
    req.on('data', chunk => { body += chunk.toString(); });
    req.on('end', async () => {
      try {
        const data = JSON.parse(body);
        const kmIds = Array.isArray(data.kmIds) ? data.kmIds.filter(x => !!x) : [];
        if (!kmIds.length) {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ success: false, error: 'Missing kmIds' }));
          return;
        }
        const summaryUrl = (typeof CONFIG.N8N_SUMMARY_URL !== 'undefined' && CONFIG.N8N_SUMMARY_URL)
          ? CONFIG.N8N_SUMMARY_URL
          : 'http://localhost:1889/webhook/md_summary';

        function findMd(dir, kmId) {
          let found = null;
          let entries;
          try {
            entries = fs.readdirSync(dir, { withFileTypes: true });
          } catch {
            return null;
          }
          for (const entry of entries) {
            const entryPath = path.join(dir, entry.name);
            if (entry.isDirectory()) {
              const r = findMd(entryPath, kmId);
              if (r) found = r;
            } else if (entry.isFile() && entry.name === kmId + '.md') {
              found = entryPath;
            }
          }
          return found;
        }

        let updated = 0;
        const results = [];
        // Stream progress as NDJSON (one line per item, then a done line).
        res.writeHead(200, { 'Content-Type': 'application/x-ndjson; charset=utf-8' });
        const total = kmIds.length;
        for (let ki = 0; ki < kmIds.length; ki++) {
          const kmId = kmIds[ki];
          res.write(JSON.stringify({ type: 'progress', done: ki, total, current: kmId }) + '\n');
          const mdPath = findMd(KM_ROOT, kmId);
          if (!mdPath) {
            results.push({ kmId, updated: false, error: 'KM markdown not found' });
            continue;
          }
          let mdText;
          try {
            mdText = fs.readFileSync(mdPath, 'utf8');
          } catch {
            results.push({ kmId, updated: false, error: 'read failed' });
            continue;
          }
          // Reuse the analysis already in the trained file — no images re-sent.
          const analysis = extractSlideAnalysisSection(mdText);
          if (!analysis) {
            results.push({ kmId, updated: false, error: 'No Slide Analysis' });
            continue;
          }
          const summaryRes = await postTextToWebhook(analysis, summaryUrl);
          if (!summaryRes.success || !summaryRes.text.trim()) {
            results.push({ kmId, updated: false, error: 'md_summary failed' });
            continue;
          }
          // Keep the trained file's metadata header so the format matches.
          const headerPart = mdText.split(/\n# Slides|\n# Slide Analysis/)[0].trimEnd();
          const summaryMd = `${headerPart}\n\n# Slide Analysis\n\n${summaryRes.text.trim()}\n`;
          const summaryPath = mdPath.replace(/\.md$/, '_summary.md');
          try {
            fs.writeFileSync(summaryPath, summaryMd, 'utf8');
            console.log('Summary written =', summaryPath); // log
            updated++;
            results.push({ kmId, updated: true });
          } catch (e) {
            results.push({ kmId, updated: false, error: e.message });
          }
        }
        res.write(JSON.stringify({ type: 'done', success: true, updated, results }) + '\n');
        res.end();
      } catch (e) {
        if (res.headersSent) {
          try { res.write(JSON.stringify({ type: 'done', success: false, error: e.message }) + '\n'); } catch (e2) { }
          res.end();
        } else {
          res.writeHead(500, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ success: false, error: e.message }));
        }
      }
    });
    return;
  }

  // --- ASK_KM: Query trained KM knowledge ---
  if (req.method === 'POST' && url.pathname === '/api/ask_km') {
    console.log('ASK_KM HIT'); // log 
    let body = '';

    req.on('data', chunk => {
      body += chunk.toString();
    });

    req.on('end', async () => {
      try {
        const data = JSON.parse(body);
        const question =
          typeof data.question === 'string'
            ? data.question.trim()
            : '';

        if (!question) {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({
            success: false,
            error: 'Missing question'
          }));
          return;
        }

        // Optional folder scope: only pull KM knowledge from this sub-folder
        // (and below) so answers don't draw on unrelated files. Empty = whole vault.
        const folder = typeof data.folder === 'string'
          ? data.folder.trim().replace(/^[\/\\]+|[\/\\]+$/g, '')
          : '';

        function walkTrainedVault(dir, output) {
          let entries;

          try {
            entries = fs.readdirSync(dir, { withFileTypes: true });
          } catch {
            return;
          }

          for (const entry of entries) {
            const entryPath = path.join(dir, entry.name);

            if (entry.isDirectory()) {
              if (/^KM_\d{8}_\d{6}$/.test(entry.name)) continue;
              if (entry.name === '.obsidian') continue;

              walkTrainedVault(entryPath, output);
            } else if (
              entry.isFile() &&
              /^KM_\d{8}_\d{6}\.md$/.test(entry.name)
            ) {
              let contents;

              try {
                contents = fs.readFileSync(entryPath, 'utf8');
              } catch {
                continue;
              }

              const getMeta = field => {
                const m = contents.match(
                  new RegExp(`${field} *: *(.+)$`, 'm')
                );
                return m ? m[1].trim() : '';
              };

              if (getMeta('Training_Status') !== 'Trained') continue;

              output.push({
                kmId:
                  getMeta('KM_ID') ||
                  entry.name.replace(/\.md$/, ''),
                sourceFile: getMeta('Source_File'),
                category: getMeta('Category'),
                machine: getMeta('Machine'),
                mdPath: entryPath
              });
            }
          }
        }
        /*
              function extractSlideAnalysis(mdText) {
        
                //const headerRegex = /^# การวิเคราะห์สไลด์\s*$/m;
                //const match = headerRegex.exec(mdText);
        
                const match =
                mdText.match(/^# Slide Analysis\s*$/m)
             || mdText.match(/^# การวิเคราะห์สไลด์\s*$/m);
          
        
                if (!match) return '';
        
                const start = match.index + match[0].length;
                const rest = mdText.slice(start);
        
                const nextHeader = rest.search(/^\s*#\s+/m);
        
                if (nextHeader === -1) {
                  return rest.trim();
                }
        
                return rest.slice(0, nextHeader).trim();
              } */

        function extractSlideAnalysis(mdText) {

          const match =
            mdText.match(/^# Slide Analysis\s*$/m)
            || mdText.match(/^# การวิเคราะห์สไลด์\s*$/m);

          if (!match) return '';

          return mdText.slice(match.index).trim();
        }


        const kmList = [];
        let walkRoot = KM_ROOT;
        if (folder) {
          const scoped = path.join(KM_ROOT, folder);
          // Keep the scope inside the vault; fall back to the whole vault if not.
          if (scoped.startsWith(KM_ROOT) && fs.existsSync(scoped)) {
            walkRoot = scoped;
          }
        }
        console.log('ASK_KM folder scope =', folder || '(all)', '->', walkRoot); // log
        walkTrainedVault(walkRoot, kmList);
        console.log("KM Found =", kmList.length); // log
        const candidates = [];

        for (const {
          kmId,
          sourceFile,
          category,
          machine,
          mdPath
          // } of kmList.slice(0, 5)) {   // slide file to AI
        } of kmList) {
          let md;

          try {
            md = fs.readFileSync(mdPath, 'utf8');
          } catch {
            continue;
          }

          const section = extractSlideAnalysis(md);

          console.log(     // log
            'KM',
            kmId,
            'section length',
            section.length
          );

          if (!section) continue;

          // 1) The full trained analysis.
          candidates.push({
            analysis: section,
            references: {
              KM_ID: kmId,
              Source_File: sourceFile,
              Category: category,
              Machine: machine,
              Kind: 'เอกสารเทรน (ฉบับเต็ม)'
            }
          });

          // 2) The condensed summary file, if it was generated, as a separate doc.
          const summaryPath = mdPath.replace(/\.md$/, '_summary.md');
          if (fs.existsSync(summaryPath)) {
            let smd;
            try {
              smd = fs.readFileSync(summaryPath, 'utf8');
            } catch {
              smd = '';
            }
            const ssection = smd ? extractSlideAnalysis(smd) : '';
            console.log('KM', kmId, 'summary length', ssection.length); // log
            if (ssection) {
              candidates.push({
                analysis: ssection,
                references: {
                  KM_ID: kmId,
                  Source_File: sourceFile,
                  Category: category,
                  Machine: machine,
                  Kind: 'สรุป (summary)'
                }
              });
            }
          }
        }
        console.log("Candidates =", candidates.length); // log
        // Label each document so the AI can tell the sources apart and answer
        // questions that target a specific file/machine. Without a header every
        // block starts with an identical "# Slide Analysis", so the model cannot
        // distinguish them.
        const context = candidates
          .map((c, i) => {
            const r = c.references || {};
            const header =
              `=== เอกสารที่ ${i + 1} ===\n` +
              `Source_File: ${r.Source_File || '-'} | ประเภท: ${r.Kind || '-'}\n` +
              `Category: ${r.Category || '-'} | Machine: ${r.Machine || '-'} | KM_ID: ${r.KM_ID || '-'}`;
            return `${header}\n\n${c.analysis}`;
          })
          .join('\n\n---\n\n');
        console.log("Context Length =", context.length); // log
        console.log(context);  // log 
        const askPayload = {
          context,
          question
        };

        const targetUrl = CONFIG.N8N_ASK_KM_URL;

        const urlObj = new URL(targetUrl);

        const proto =
          urlObj.protocol === 'https:'
            ? require('https')
            : require('http');

        const fwdReq = proto.request(
          {
            method: 'POST',
            hostname: urlObj.hostname,
            port:
              urlObj.port ||
              (urlObj.protocol === 'https:' ? 443 : 80),
            path: urlObj.pathname + (urlObj.search || ''),
            headers: {
              'Content-Type': 'application/json'
            }
          },
          askRes => {
            let responseBody = '';

            askRes.on('data', chunk => {
              responseBody += chunk.toString();
            });

            askRes.on('end', () => {
              res.writeHead(
                askRes.statusCode || 200,
                {
                  'Content-Type':
                    askRes.headers['content-type'] ||
                    'application/json'
                }
              );

              res.end(responseBody);
            });
          }
        );

        fwdReq.on('error', err => {
          res.writeHead(502, {
            'Content-Type': 'application/json'
          });

          res.end(
            JSON.stringify({
              success: false,
              error: err.message
            })
          );
        });

        fwdReq.write(JSON.stringify(askPayload));
        fwdReq.end();
      } catch (e) {
        res.writeHead(500, {
          'Content-Type': 'application/json'
        });

        res.end(
          JSON.stringify({
            success: false,
            error: e.message
          })
        );
      }
    });

    return;
  }

  // --- Gate the main app behind login (rough). Unauthenticated requests for the
  // app shell are redirected to the login page; the login page and static assets
  // (css/js/images) stay open so the login screen can render. ---
  if ((url.pathname === '/' || url.pathname === '/index.html') && !getSession(req)) {
    // ?mode=viewer enters read-only without login (for shop-floor links/QR).
    // Set a viewer cookie and serve the app instead of bouncing to login.
    if (url.searchParams.get('mode') === 'viewer') {
      const token = crypto.randomBytes(24).toString('hex');
      sessions.set(token, { username: 'viewer', role: 'viewer', name: 'ผู้ชม (Viewer)' });
      res.setHeader('Set-Cookie', `km_session=${token}; HttpOnly; Path=/; SameSite=Lax; Max-Age=86400`);
    } else {
      res.writeHead(302, { Location: '/login.html' });
      res.end();
      return;
    }
  }

  // --- Existing static file serving ---
  let filePath = path.join(PUBLIC_ROOT, url.pathname === '/' ? 'index.html' : url.pathname);
  if (!filePath.startsWith(PUBLIC_ROOT)) {
    res.writeHead(403);
    res.end('Forbidden');
    return;
  }

  fs.stat(filePath, (err, stats) => {
    if (err) {
      res.writeHead(404);
      res.end('Not found');
      return;
    }
    if (stats.isDirectory()) {
      filePath = path.join(filePath, 'index.html');
    }
    fs.readFile(filePath, (readErr, content) => {
      if (readErr) {
        res.writeHead(500);
        res.end('Server error');
        return;
      }
      res.writeHead(200, { 'Content-Type': getContentType(filePath) });
      res.end(content);
    });
  });
});



server.listen(PORT, () => {
  console.log(`Server running at http://localhost:${PORT}`);
  console.log(`KM vault root: ${KM_ROOT}`);
  console.log('CONFIG=', CONFIG);
  console.log('N8N_KM_URL=', CONFIG?.N8N_KM_URL);

});

