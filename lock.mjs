#!/usr/bin/env node
// 饮力情报局 · 内容级加密构建
// 读取 coffee.html（源码），把「应用结构 + 全部数据脚本」用 AES-256-GCM 加密，
// 产出 index.html（仅含登录壳 + 密文）。源码中不出现明文数据。
//
// 用法: node lock.mjs [password]          默认密码 morphyshirley999
import { readFileSync, writeFileSync } from 'node:fs';
import { webcrypto } from 'node:crypto';
const subtle = webcrypto.subtle;

const PASSWORD = process.argv[2] || 'morphyshirley999';
const enc = new TextEncoder();
const dec = new TextDecoder();

function b64(bytes) { return Buffer.from(bytes).toString('base64'); }
function b64ToU8(s) { return new Uint8Array(Buffer.from(s, 'base64')); }

// 与浏览器端完全一致的 KDF 参数
async function deriveKey(pass, salt) {
  const km = await subtle.importKey('raw', enc.encode(pass), 'PBKDF2', false, ['deriveBits']);
  return subtle.deriveBits({ name: 'PBKDF2', hash: 'SHA-256', salt, iterations: 150000 }, km, 256);
}
async function aesEncrypt(keyBits, iv, data) {
  const k = await subtle.importKey('raw', keyBits, { name: 'AES-GCM' }, false, ['encrypt']);
  const ct = await subtle.encrypt({ name: 'AES-GCM', iv }, k, enc.encode(data));
  return new Uint8Array(ct);
}

// ── 源文件解析 ──
const src = readFileSync('coffee.html', 'utf8');
const iApp = src.indexOf('<div class="app">');
if (iApp < 0) { console.error('未找到 <div class="app">'); process.exit(1); }
const iScript = src.indexOf('<script>', iApp);
const iScriptEnd = src.indexOf('</script>', iScript);
if (iScript < 0 || iScriptEnd < 0) { console.error('未找到主脚本'); process.exit(1); }
const appHTML = src.slice(iApp, iScript).replace(/\s+$/, '');
let js = src.slice(iScript + '<script>'.length, iScriptEnd);

// 从脚本中剔除鉴权块（由登录壳负责），并把结尾启动改成交给 shell 的 appMain()
js = js.replace(/\/\/ ═══ AUTH ═══[\s\S]*?function boot\(\) \{ switchPage\('featured'\); initChartTip\(\); \}\n?/, '');
js = js.replace(/if \(!AUTH\.enabled \|\| sessionStorage\.getItem\('brew_auth'\) === '1'\) \{ boot\(\); \}\nelse \{ showLogin\(\); \}\n?/, '');
js = js.trimEnd() + '\nappMain();\n';

const payload = JSON.stringify({ body: appHTML, js });
const salt = webcrypto.getRandomValues(new Uint8Array(16));
const iv = webcrypto.getRandomValues(new Uint8Array(12));
const keyBits = await deriveKey(PASSWORD, salt);
const ct = await aesEncrypt(keyBits, iv, payload);

const LOCK = {
  s: b64(salt), iv: b64(iv), ct: b64(ct),
  user: '5a2dc66616e9f5c666362e6374c245853a8bbe084a378700085b91e007bc1488',
  pass: '5f291e764b3dfde97ed9009c686ef0ef5857b38dfaccbba475012efee5203539',
};
const lockJson = JSON.stringify(LOCK);

// ── 生成加密版 index.html（登录壳）──
const shell = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>饮力情报局</title>
<style>
  html,body{margin:0;background:#0a0f18;height:100%;}
  #loginMask{position:fixed;inset:0;z-index:2000;background:radial-gradient(1200px 600px at 50% -10%,#16233c,#0a0f18 60%);display:flex;align-items:center;justify-content:center;}
  .lg-box{width:min(92vw,360px);background:#0e1526;border:1px solid rgba(59,130,246,.25);border-radius:14px;padding:28px 26px 22px;box-shadow:0 20px 60px rgba(0,0,0,.5);}
  .lg-box .lg-logo{font-size:26px;text-align:center;}
  .lg-box .lg-title{font-size:16px;font-weight:800;color:#e0e6f0;text-align:center;margin:8px 0 2px;}
  .lg-box .lg-sub{font-size:11px;color:#6b7a92;text-align:center;margin-bottom:18px;}
  .lg-box input{width:100%;box-sizing:border-box;background:#0a1220;border:1px solid rgba(59,130,246,.18);color:#e0e6f0;border-radius:8px;padding:10px 12px;font-size:13px;margin-bottom:12px;outline:none;}
  .lg-box input:focus{border-color:#3b82f6;}
  .lg-box .lg-btn{width:100%;background:linear-gradient(135deg,#3b82f6,#2563eb);color:#fff;border:none;border-radius:8px;padding:11px;font-size:14px;font-weight:700;cursor:pointer;}
  .lg-box .lg-btn:hover{filter:brightness(1.08);}
  .lg-box .lg-err{color:#f87171;font-size:11px;margin-top:8px;min-height:14px;}
  .lg-box .lg-hint{font-size:10px;color:#4a5568;text-align:center;margin-top:12px;}
</style>
</head>
<body>
<div id="loginMask">
  <form class="lg-box" onsubmit="onLogin(event)" autocomplete="off">
    <div class="lg-logo">☕</div>
    <div class="lg-title">饮力情报局</div>
    <div class="lg-sub">请输入账号密码解密内容</div>
    <input id="lgUser" type="text" placeholder="账号" autocomplete="username" required>
    <input id="lgPass" type="password" placeholder="密码" autocomplete="current-password" required>
    <button class="lg-btn" type="submit">解 锁</button>
    <div class="lg-err" id="lgErr"></div>
    <div class="lg-hint">内容已加密存储 · 解密仅在本机内存进行，源码中无明文数据</div>
  </form>
</div>
<div id="appRoot"></div>
<script>
const LOCK = ${lockJson};
const ENC = new TextEncoder(), DEC = new TextDecoder();
function b64ToU8(s){ const bin=atob(s); const u=new Uint8Array(bin.length); for(let i=0;i<bin.length;i++)u[i]=bin.charCodeAt(i); return u; }
async function sha256(s){ const buf=await crypto.subtle.digest('SHA-256', ENC.encode(s)); return Array.from(new Uint8Array(buf)).map(b=>b.toString(16).padStart(2,'0')).join(''); }
async function deriveKey(pass){ 
  const km=await crypto.subtle.importKey('raw', ENC.encode(pass), 'PBKDF2', false, ['deriveBits']);
  return crypto.subtle.deriveBits({name:'PBKDF2', hash:'SHA-256', salt:b64ToU8(LOCK.s), iterations:150000}, km, 256);
}
async function onLogin(ev){
  ev.preventDefault();
  const u=(document.getElementById('lgUser').value||'').trim();
  const p=document.getElementById('lgPass').value||'';
  const err=document.getElementById('lgErr');
  err.textContent='解密中…';
  if (!window.isSecureContext){ err.textContent='当前非安全环境(非HTTPS)，WebCrypto不可用，请用 https 访问'; return; }
  if ((await sha256(u))!==LOCK.user || (await sha256(p))!==LOCK.pass){ err.textContent='账号或密码错误，请重试'; return; }
  let keyBits;
  try { keyBits=await deriveKey(p); }
  catch(e){ err.textContent='密钥派生失败：'+e.message; return; }
  let data;
  try { data=await decryptData(keyBits); }
  catch(e){ err.textContent='解密失败：'+e.message; return; }
  try { injectData(data); }
  catch(e){ console.error(e); err.textContent='内容渲染失败，请刷新重试：'+e.message; return; }
  try { sessionStorage.setItem('brew_key', bufToB64(keyBits)); sessionStorage.setItem('brew_auth','1'); } catch(e){}
  document.getElementById('loginMask').style.display='none';
  err.textContent='';
}
function bufToB64(u8){ let s=''; for(const c of u8) s+=String.fromCharCode(c); return btoa(s); }
async function decryptData(keyBits){
  const key=await crypto.subtle.importKey('raw', keyBits, {name:'AES-GCM'}, false, ['decrypt']);
  const pt=await crypto.subtle.decrypt({name:'AES-GCM', iv:b64ToU8(LOCK.iv)}, key, b64ToU8(LOCK.ct));
  return JSON.parse(DEC.decode(pt));
}
function injectData(data){
  document.getElementById('appRoot').innerHTML=data.body;
  const s=document.createElement('script'); s.textContent=data.js; document.body.appendChild(s);
  appMain();
}
function appMain(){ try{ switchPage('featured'); initChartTip(); }catch(e){ console.error(e); } }
function logout(){ try{ sessionStorage.removeItem('brew_auth'); sessionStorage.removeItem('brew_key'); }catch(e){} location.reload(); }
// 本会话已解锁过（存有派生密钥，非密码明文），刷新后自动解密
(async function(){
  const k=sessionStorage.getItem('brew_key');
  if (k) {
    try{ injectData(await decryptData(b64ToU8(k))); document.getElementById('loginMask').style.display='none'; }
    catch(e){ try{ sessionStorage.removeItem('brew_key'); sessionStorage.removeItem('brew_auth'); }catch(e){} }
  }
})();
</script>
</body>
</html>
`;
writeFileSync('index.html', shell);
console.log(`✅ 已生成加密版 index.html（${(shell.length/1024).toFixed(0)} KB，明文内容未出现在源码）`);