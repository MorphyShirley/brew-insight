#!/usr/bin/env node
// 饮力情报局 · 邀请链接管理
// 用法:
//   node invite.mjs new --label "张三" [--days 7]   # 生成邀请链接（自动重建 index.html）
//   node invite.mjs list                            # 列出所有邀请及链接
//   node invite.mjs revoke <id>                     # 撤销某个邀请（自动重建）
//
// 说明：invites.json 存 token（仅本地，不入库）；invites.lock.json 存封装后的条目（可入库，CI 复用）。
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { randomBytes } from 'node:crypto';
import { execFileSync } from 'node:child_process';

const FILE = 'invites.json';
const BASE = 'https://morphyshirley.github.io/brew-insight/';
const argv = process.argv.slice(2);
const cmd = argv[0] || 'list';

function load() { try { return JSON.parse(readFileSync(FILE, 'utf8')); } catch (e) { return []; } }
function save(a) { writeFileSync(FILE, JSON.stringify(a, null, 1)); }
function get(flag, def) { const i = argv.indexOf(flag); return i > 0 ? argv[i + 1] : def; }
function rebuild() { execFileSync('node', ['lock.mjs'], { stdio: 'inherit' }); }
function link(it) { return BASE + '?k=' + it.id + '.' + it.token; }
function fmtExp(exp) { return exp ? new Date(exp).toLocaleString('zh-CN', { hour12: false }) : '永久'; }

if (cmd === 'new') {
  const label = get('--label', '未命名');
  const days = parseInt(get('--days', '7'), 10) || 7;
  const list = load();
  const id = randomBytes(3).toString('hex');            // 6 位
  const token = randomBytes(32).toString('base64url');  // 43 字符
  const salt = randomBytes(16).toString('base64');
  const exp = days > 0 ? Date.now() + days * 86400000 : 0;
  const it = { id, label, exp, token, salt };
  list.push(it);
  save(list);
  rebuild();
  console.log('✅ 已生成邀请');
  console.log('   对象:', label);
  console.log('   有效期至:', fmtExp(exp));
  console.log('   链接:', link(it));
} else if (cmd === 'revoke') {
  const id = argv[1];
  const list = load();
  const next = list.filter(x => x.id !== id);
  if (next.length === list.length) { console.log('❌ 未找到邀请', id); process.exit(1); }
  save(next);
  rebuild();
  console.log('✅ 已撤销', id, '（其余', next.length, '个保留）');
} else {
  const list = load();
  if (!list.length) { console.log('暂无邀请。生成：node invite.mjs new --label "张三" --days 7'); process.exit(0); }
  console.log('共', list.length, '个邀请：\n');
  const now = Date.now();
  list.forEach(it => {
    const expired = it.exp && now > it.exp;
    console.log(`[${it.id}] ${it.label}  有效期至 ${fmtExp(it.exp)}${expired ? '  ⚠️已过期' : ''}`);
    console.log('     ' + link(it) + '\n');
  });
}