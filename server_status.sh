#!/usr/bin/env bash
# 云服务器一键巡检（火山引擎 118.196.3.71）
# 用法: ./server_status.sh
set -euo pipefail
cd "$(dirname "$0")"
KEY="$HOME/.ssh/deploy_brew_ed25519"
HOST="root@118.196.3.71"

ssh -i "$KEY" "$HOST" 'bash -s' <<'EOF'
echo "════════════════════════════════════"
echo "🗄️  饮力情报局 · 服务器巡检"
echo "主机: $(hostname) · $(date '+%Y-%m-%d %H:%M:%S')"
echo "════════════════════════════════════"

echo
echo "── 🟢 1. Nginx ──"
systemctl is-active nginx >/dev/null && echo "运行中（自启已开: $(systemctl is-enabled nginx)）" || echo "✗ 未运行！"
echo "进程数: $(pgrep -c nginx || echo 0)"

echo
echo "── 📁 2. 站点文件 ──"
ls -la /var/www/brew-insight/
curl -s -o /dev/null -w "本机访问: HTTP %{http_code} · %{size_download} bytes\n" http://127.0.0.1/ || echo "本机访问失败"

echo
echo "── 🖥️  3. 系统资源 ──"
echo "CPU 核数: $(nproc) | 负载: $(cat /proc/loadavg | awk '{print $1}')"
free -h | awk 'NR==1||NR==2{print}'
df -h / | awk 'NR==1||NR==2{print}'

echo
echo "── 🔌 4. 网络监听（80/443/22） ──"
ss -tlnp 2>/dev/null | grep -E ':80 |:443 |:22 ' || ss -tlnp | grep -E ':80|:443|:22'

echo
echo "── 🔐 5. 最近登录 & 安全 ──"
last -5 2>/dev/null | head -5 || true
echo "失败登录尝试(近3天): $(grep -c 'Failed password' /var/log/auth.log 2>/dev/null || echo 0)"

echo
echo "── 💾 6. 备份提醒 ──"
ls /var/backups/brew-insight* 2>/dev/null | head -3 || echo "尚未配置自动备份（可稍后加上）"

echo
echo "════════════════════════════════════"
echo "✅ 巡检完成（待域名备案通过后补 HTTPS 检查）"
EOF