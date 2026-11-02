#!/usr/bin/env node
// 校验某个 index.html 是否能被指定密码解开（供 security_check.py 调用）
// 用法: OWNER_PASSWORD=xxx node verify_page.mjs [path]
// 输出: {"ok":true,"cards":123,"latest":"MM/DD"} 或 {"ok":false,"error":"..."}
import { readFileSync } from 'node:fs';
import { webcrypto } from 'node:crypto';
import { gunzipSync } from 'node:zlib';

const path = process.argv[2] || 'index.html';
const pw = process.env.OWNER_PASSWORD || '';
const subtle = webcrypto.subtle;
const b64u = s => new Uint8Array(Buffer.from(s, 'base64'));
const ENC = new TextEncoder(), DEC = new TextDecoder();

try {
  if (!pw) throw new Error('缺少 OWNER_PASSWORD');
  const html = readFileSync(path, 'utf8');
  const m = html.match(/const LOCK = (\{[\s\S]*?\});/);
  if (!m) throw new Error('页面里没有 LOCK（可能不是加密版）');
  const LOCK = JSON.parse(m[1]);
  const km = await subtle.importKey('raw', ENC.encode(pw), 'PBKDF2', false, ['deriveBits']);
  const kb = await subtle.deriveBits(
    { name: 'PBKDF2', hash: 'SHA-256', salt: b64u(LOCK.s), iterations: 150000 }, km, 256);
  const key = await subtle.importKey('raw', kb, { name: 'AES-GCM' }, false, ['decrypt']);
  const pt = await subtle.decrypt({ name: 'AES-GCM', iv: b64u(LOCK.iv) }, key, b64u(LOCK.ct));
  const js = JSON.parse(DEC.decode(LOCK.zip === 1 ? gunzipSync(Buffer.from(pt)) : pt)).js;
  const times = [...js.matchAll(/time:'(\d{2})\/(\d{2})'/g)].map(x => x[1] + '/' + x[2]).sort();
  console.log(JSON.stringify({ ok: true, cards: times.length, latest: times[times.length - 1] || null }));
} catch (e) {
  console.log(JSON.stringify({ ok: false, error: String(e.message || e) }));
  process.exit(0);
}
