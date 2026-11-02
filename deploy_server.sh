#!/usr/bin/env bash
# 一键发布到云服务器（火山引擎 118.196.3.71）
# 用法:
#   ./deploy_server.sh            # 上传加密版 index.html 并 reload nginx
#   ./deploy_server.sh build      # 先 node lock.mjs 重新加密构建，再上传
set -euo pipefail
cd "$(dirname "$0")"
KEY="$HOME/.ssh/deploy_brew_ed25519"
HOST="root@118.196.3.71"
SRC=/var/www/brew-insight/index.html

if [ "${1:-}" = "build" ]; then
  node lock.mjs
  echo "✅ 已重新生成加密版 index.html"
fi

scp -i "$KEY" index.html "$HOST:$SRC"
ssh -i "$KEY" "$HOST" 'systemctl reload nginx && echo "✅ nginx reload 完成"'
echo "🌐 请访问 http://118.196.3.71/（HTTPS 待域名审核通过后配置）"