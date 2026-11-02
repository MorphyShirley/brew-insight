#!/usr/bin/env node
// 源码加密：coffee.html <-> coffee.src.enc
// 公开仓库只保存密文，明文源码仅留在本地 / CI 临时目录。
//
// 用法:
//   node src_crypt.mjs seal   # coffee.html -> coffee.src.enc（提交用）
//   node src_crypt.mjs open   # coffee.src.enc -> coffee.html（本地/CI 构建用）
//
// 密钥: 环境变量 SRC_KEY，或项目根目录 .env 中的 SRC_KEY（base64，32 字节）
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { gzipSync, gunzipSync } from 'node:zlib';
import { webcrypto } from 'node:crypto';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = dirname(fileURLToPath(import.meta.url));
const SRC = join(ROOT, 'coffee.html');
const ENC = join(ROOT, 'coffee.src.enc');
const subtle = webcrypto.subtle;

function readEnvFile() {
  const p = join(ROOT, '.env');
  if (!existsSync(p)) return {};
  const out = {};
  for (const line of readFileSync(p, 'utf8').split('\n')) {
    const s = line.trim();
    if (!s || s.startsWith('#')) continue;
    const i = s.indexOf('=');
    if (i < 0) continue;
    out[s.slice(0, i).trim()] = s.slice(i + 1).trim();
  }
  return out;
}

const env = readEnvFile();
const keyB64 = process.env.SRC_KEY || env.SRC_KEY;
if (!keyB64) {
  console.error('❌ 缺少 SRC_KEY（环境变量或 .env 中配置 base64 的 32 字节密钥）');
  process.exit(1);
}
const key = new Uint8Array(Buffer.from(keyB64, 'base64'));
if (key.length !== 32) {
  console.error('❌ SRC_KEY 必须是 32 字节（base64 编码）');
  process.exit(1);
}

async function seal() {
  if (!existsSync(SRC)) { console.error('❌ 找不到 coffee.html'); process.exit(1); }
  const raw = gzipSync(readFileSync(SRC), { level: 9 });
  const iv = webcrypto.getRandomValues(new Uint8Array(12));
  const k = await subtle.importKey('raw', key, { name: 'AES-GCM' }, false, ['encrypt']);
  const ct = new Uint8Array(await subtle.encrypt({ name: 'AES-GCM', iv }, k, raw));
  writeFileSync(ENC, JSON.stringify({
    v: 1, alg: 'AES-256-GCM', zip: 'gzip',
    iv: Buffer.from(iv).toString('base64'),
    ct: Buffer.from(ct).toString('base64'),
  }));
  console.log(`🔒 源码已加密 → coffee.src.enc（${Math.round(ct.length / 1024)} KB）`);
}

async function open() {
  if (!existsSync(ENC)) { console.error('❌ 找不到 coffee.src.enc'); process.exit(1); }
  const box = JSON.parse(readFileSync(ENC, 'utf8'));
  const k = await subtle.importKey('raw', key, { name: 'AES-GCM' }, false, ['decrypt']);
  const pt = await subtle.decrypt(
    { name: 'AES-GCM', iv: new Uint8Array(Buffer.from(box.iv, 'base64')) },
    k, new Uint8Array(Buffer.from(box.ct, 'base64'))
  );
  writeFileSync(SRC, gunzipSync(Buffer.from(pt)));
  console.log(`🔓 源码已解密 → coffee.html（${Math.round(Buffer.byteLength(gunzipSync(Buffer.from(pt))) / 1024)} KB）`);
}

const cmd = process.argv[2] || 'seal';
if (cmd === 'seal') await seal();
else if (cmd === 'open') await open();
else { console.error('用法: node src_crypt.mjs [seal|open]'); process.exit(1); }
