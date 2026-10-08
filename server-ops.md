# ☕ 云服务器操作小抄（火山引擎 · Ubuntu 24.04）

> IP: `118.196.3.71` · 登录：仅密钥 · 密钥文件：`~/.ssh/deploy_brew_ed25519`

## 一、登录（用你自己的电脑）
```bash
# 直接登录
ssh -i ~/.ssh/deploy_brew_ed25519 root@118.196.3.71

# 一键巡检（推荐入口）
cd ~/coffee-site && ./server_status.sh
```

## 二、常用运维命令（登进服务器后）
```bash
systemctl status nginx          # 看 nginx 状态
systemctl restart nginx         # 重启 nginx
journalctl -u nginx -n 50       # 看 nginx 最近日志
ls -la /var/www/brew-insight/   # 站点目录
free -h && df -h /              # 内存/磁盘
ss -tlnp                        # 端口监听
```

## 三、更新站点内容（在你的电脑上）
```bash
cd ~/coffee-site
./deploy_server.sh build        # 重新加密构建 + 上传 + reload（正常用这个）
# 或只上传不重新构建：
./deploy_server.sh
```

## 四、备份站点文件（如手动）
```bash
scp -i ~/.ssh/deploy_brew_ed25519 \
  root@118.196.3.71:/var/www/brew-insight/index.html \
  ~/Desktop/index_backup.html
```

## 五、开始用 GitHub Pages（域名审核通过前，日常访问走这里）
```text
https://morphyshirley.github.io/brew-insight/
```

## 六、密钥丢了怎么办
1. 火山引擎控制台 → 该实例 → 「重置密码」或 VNC 登录
2. 重新生成密钥是不行的（原私钥已授权）；要么用新公钥写入 `~/.ssh/authorized_keys`，要么临时开回密码登录

## 七、待办（域名备案通过后）
1. DNS：域名 A 记录 → `118.196.3.71`
2. certbot 签发 Let's Encrypt 证书 + 自动续期
3. Nginx 强制 HTTPS + 443 放行