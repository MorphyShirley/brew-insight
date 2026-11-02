#!/usr/bin/env python3
"""饮力情报局 · 月度安全自查

用法:
    python3 security_check.py            # 全量（含服务器 SSH 检查）
    python3 security_check.py --no-ssh   # 跳过服务器检查

检查范围:
    1. 本地仓库    敏感文件是否被跟踪、明文密码/密钥泄漏、远程地址、备份包
    2. GitHub 远端 仓库可见性、文件树有无明文、工作流最近是否失败
    3. 线上页面    是否加密、能否用当前密码解开、数据是否新鲜
    4. 邀请        过期/即将过期的邀请
    5. 服务器      HTTP 是否可用、SSH 是否仅密钥、fail2ban 是否在跑

退出码: 有 FAIL 时返回 1，便于定时任务报警。
"""
import base64
import glob
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.abspath(__file__))
REPO = "MorphyShirley/brew-insight"
SITE = "https://morphyshirley.github.io/brew-insight/"
SERVER = "http://118.196.3.71/"
SSH_KEY = os.path.expanduser("~/.ssh/deploy_brew_ed25519")
SSH_HOST = "root@118.196.3.71"

CHECK_SSH = "--no-ssh" not in sys.argv

results = []  # (level, title, detail)


ICON = {"OK": "\033[32m✅\033[0m", "WARN": "\033[33m⚠️ \033[0m", "FAIL": "\033[31m❌\033[0m"}


def add(level, title, detail=""):
    results.append((level, title, detail))
    print(f"  {ICON[level]} {title}" + (f"  — {detail}" if detail else ""))


def ok(title, detail=""):
    add("OK", title, detail)


def warn(title, detail=""):
    add("WARN", title, detail)


def fail(title, detail=""):
    add("FAIL", title, detail)


def read_env():
    out = {}
    p = os.path.join(ROOT, ".env")
    if not os.path.exists(p):
        return out
    for line in open(p, encoding="utf-8"):
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def http(url, timeout=25, ua="brew-insight-check/1.0"):
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read()


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def section(name):
    print(f"\n\033[1m{name}\033[0m")


ENV = read_env()


# ───────────────────────── 1. 本地仓库 ─────────────────────────
def check_local():
    section("① 本地仓库")

    tracked = git("ls-files").stdout.splitlines()
    leaks = [f for f in tracked if f in (".env", "invites.json", "coffee.html") or f.endswith(".log")]
    if leaks:
        fail("敏感文件被 Git 跟踪", ", ".join(leaks))
    else:
        ok("无敏感文件入库", f"{len(tracked)} 个跟踪文件")

    ignore = ""
    if os.path.exists(os.path.join(ROOT, ".gitignore")):
        ignore = open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()
    missing = [p for p in ("coffee.html", ".env", "invites.json") if p not in ignore]
    if missing:
        warn(".gitignore 缺少规则", ", ".join(missing))
    else:
        warn_if = None
        ok(".gitignore 覆盖明文与密钥", "") if warn_if is None else None

    # 明文密钥扫描（只扫跟踪文件）
    patterns = [
        (r"tvly-[A-Za-z0-9_-]{8,}", "Tavily Key"),
        (r"ghp_[A-Za-z0-9]{20,}", "GitHub Token"),
        (r"github_pat_[A-Za-z0-9_]{20,}", "GitHub PAT"),
        (r"fa6ed0b4299c4cf7abd02657cf9a855a", "旧 Surge Token"),
        (r"-----BEGIN (RSA|OPENSSH|EC) PRIVATE KEY-----", "私钥"),
    ]
    secrets = []
    for f in tracked:
        p = os.path.join(ROOT, f)
        if not os.path.isfile(p) or os.path.getsize(p) > 2 * 1024 * 1024:
            continue
        try:
            txt = open(p, encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        for pat, label in patterns:
            if re.search(pat, txt):
                secrets.append(f"{f}: {label}")
        pw = ENV.get("OWNER_PASSWORD", "")
        if pw and len(pw) >= 8 and pw in txt:
            secrets.append(f"{f}: 登录密码明文")
        sk = ENV.get("SRC_KEY", "")
        if sk and sk in txt:
            secrets.append(f"{f}: SRC_KEY 明文")
    if secrets:
        fail("公文中出现明文密钥/密码", "; ".join(secrets[:5]))
    else:
        ok("跟踪文件中无明文密钥", f"已扫描 {len(tracked)} 个文件")

    # .env 权限
    envp = os.path.join(ROOT, ".env")
    if os.path.exists(envp):
        mode = oct(os.stat(envp).st_mode & 0o777)
        if mode != "0o600":
            warn(".env 权限过宽", f"{mode}（建议 chmod 600）")
        else:
            ok(".env 权限正确", "600")

    # 远程地址是否内嵌 token
    url = git("remote", "get-url", "origin").stdout.strip()
    if re.match(r"https://[^@/]+@", url):
        fail("Git 远程地址内嵌凭据", "请改回 SSH")
    else:
        ok("Git 远程地址干净", "SSH")

    # 与远端是否同步
    git("fetch", "origin", "main", "-q")
    local = git("rev-parse", "HEAD").stdout.strip()
    remote = git("rev-parse", "origin/main").stdout.strip()
    if local and remote and local != remote:
        warn("本地与远端不一致", f"local {local[:7]} / remote {remote[:7]}")
    else:
        ok("本地与远端同步", local[:7])

    # 备份包
    bundles = sorted(glob.glob(os.path.expanduser("~/brew-insight-history-*.bundle")), key=os.path.getmtime)
    if not bundles:
        warn("未找到历史备份包", "建议 git bundle 备份")
    else:
        age = (time.time() - os.path.getmtime(bundles[-1])) / 86400
        if age > 35:
            warn("历史备份较旧", f"{os.path.basename(bundles[-1])}（{age:.0f} 天前）")
        else:
            ok("历史备份存在", f"{os.path.basename(bundles[-1])}（{age:.0f} 天前）")


# ───────────────────────── 2. GitHub 远端 ─────────────────────────
def check_remote():
    section("② GitHub 远端")
    try:
        _, body = http(f"https://api.github.com/repos/{REPO}")
        repo = json.loads(body)
    except Exception as e:
        warn("GitHub API 不可用", str(e)[:60])
        return

    ok("仓库可访问", f"{repo.get('visibility')} · {repo.get('size', 0)} KB")
    if repo.get("visibility") == "public":
        ok("仓库为公开（方案 B）", "仅密文入库")

    try:
        _, body = http(f"https://api.github.com/repos/{REPO}/git/trees/main?recursive=1")
        tree = json.loads(body).get("tree", [])
        bad = [t["path"] for t in tree if t["path"] in ("coffee.html", ".env", "invites.json")]
        if bad:
            fail("远端文件树含敏感文件", ", ".join(bad))
        else:
            ok("远端文件树无明文", f"{len(tree)} 个文件")
    except Exception as e:
        warn("无法读取远端文件树", str(e)[:60])

    try:
        code, _ = http(f"https://raw.githubusercontent.com/{REPO}/main/coffee.html", timeout=15)
        if code == 200:
            fail("远端仍可访问明文 coffee.html")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            ok("明文 coffee.html 不可访问", "404")
        else:
            warn("检查 coffee.html 返回异常", str(e.code))
    except Exception as e:
        warn("检查 coffee.html 超时", str(e)[:40])

    try:
        _, body = http(f"https://api.github.com/repos/{REPO}/actions/runs?per_page=1")
        runs = json.loads(body).get("workflow_runs", [])
        if not runs:
            warn("没有工作流运行记录", "")
        else:
            r = runs[0]
            if r.get("conclusion") == "success":
                ok("最近工作流成功", f"{r['name']} · {r['created_at'][:16]}")
            else:
                warn("最近工作流未成功", f"{r['name']} · {r.get('conclusion')}")
    except Exception as e:
        warn("无法读取工作流状态", str(e)[:50])


# ───────────────────────── 3. 线上页面 ─────────────────────────
def check_site():
    section("③ 线上页面")
    page = os.path.join(ROOT, ".security_page.html")
    try:
        code, body = http(f"{SITE}?t={int(time.time())}", timeout=40)
    except Exception as e:
        fail("线上页面无法访问", str(e)[:60])
        return
    open(page, "w", encoding="utf-8").write(body.decode("utf-8", "ignore"))
    ok("线上页面可访问", f"{code} · {len(body) / 1024:.0f} KB")

    local_index = os.path.join(ROOT, "index.html")
    if os.path.exists(local_index):
        diff = abs(len(body) - os.path.getsize(local_index))
        if diff > 2048:
            warn("线上与本地构建不一致", f"相差 {diff} 字节（可能正在发布）")
        else:
            ok("线上与本地构建一致", "字节数匹配")

    html = body.decode("utf-8", "ignore")
    if "const LOCK" not in html:
        fail("线上页面缺少加密壳", "可能已被替换")
    elif "buildOwnBrandPage" in html or "爷爷不泡茶" in html:
        fail("线上页面疑似含明文数据")
    else:
        ok("线上页面为密文", "未发现明文数据特征")

    if not ENV.get("OWNER_PASSWORD"):
        warn("无法验证解密", "缺少 OWNER_PASSWORD")
        return
    try:
        r = subprocess.run(
            ["node", os.path.join(ROOT, "verify_page.mjs"), page],
            cwd=ROOT, capture_output=True, text=True, timeout=60,
            env={**os.environ, "OWNER_PASSWORD": ENV["OWNER_PASSWORD"]},
        )
        data = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception as e:
        warn("解密校验执行失败", str(e)[:60])
        return
    if not data.get("ok"):
        fail("当前密码无法解开线上页面", data.get("error", ""))
        return
    ok("当前密码可解密", f"{data.get('cards')} 条资讯")

    latest = data.get("latest")
    if latest:
        try:
            mm, dd = map(int, latest.split("/"))
            now = datetime.now()
            d = datetime(now.year, mm, dd)
            delta = (now - d).days
            if delta < -180:
                delta += 365
            if delta > 4:
                warn("资讯数据偏旧", f"最新 {latest}（{delta} 天前）")
            else:
                ok("资讯数据新鲜", f"最新 {latest}（{delta} 天前）")
        except Exception:
            pass
    os.remove(page)


# ───────────────────────── 4. 邀请 ─────────────────────────
def check_invites():
    section("④ 邀请")
    p = os.path.join(ROOT, "invites.json")
    if not os.path.exists(p):
        ok("暂无邀请", "invites.json 不存在")
        return
    try:
        items = json.load(open(p, encoding="utf-8"))
    except Exception as e:
        warn("邀请文件解析失败", str(e)[:50])
        return
    now = time.time() * 1000
    expired = [x for x in items if x.get("exp", 0) < now]
    active = [x for x in items if x.get("exp", 0) >= now]
    for x in active:
        left = (x["exp"] / 1000 - time.time()) / 86400
        label = x.get("label", x.get("id"))
        if left < 2:
            warn("邀请即将过期", f"{label} · 剩 {left:.1f} 天")
        else:
            ok("邀请有效", f"{label} · 剩 {left:.0f} 天")
    if expired:
        warn("存在已过期邀请", f"{len(expired)} 条（可执行 node invite.mjs prune）")
    if not active and not expired:
        ok("邀请列表为空", "")


# ───────────────────────── 5. 服务器 ─────────────────────────
def check_server():
    section("⑤ 服务器")
    if not CHECK_SSH:
        warn("已跳过服务器检查", "--no-ssh")
        return
    try:
        code, body = http(SERVER, timeout=12)
        if code == 200:
            local = os.path.join(ROOT, "index.html")
            if os.path.exists(local) and abs(len(body) - os.path.getsize(local)) < 2048:
                ok("服务器页面正常", f"{len(body) / 1024:.0f} KB · 与本地一致")
            else:
                warn("服务器页面版本偏旧", f"{len(body) / 1024:.0f} KB")
        else:
            warn("服务器返回异常", str(code))
    except Exception as e:
        warn("服务器 HTTP 不可用", str(e)[:50])

    if not os.path.exists(SSH_KEY):
        warn("未找到 SSH 密钥", SSH_KEY)
        return
    cmd = ("echo PA=$(sshd -T 2>/dev/null | awk '/^passwordauthentication/{print $2}'); "
           "echo F2B=$(systemctl is-active fail2ban 2>/dev/null); "
           "echo HTTPS=$(ss -tln | grep -c ':443 ')")
    try:
        r = subprocess.run(
            ["ssh", "-i", SSH_KEY, "-o", "ConnectTimeout=10", "-o", "BatchMode=yes", SSH_HOST, cmd],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            warn("SSH 连接失败", (r.stderr or "").strip()[:60])
            return
        out = dict(line.split("=", 1) for line in r.stdout.strip().splitlines() if "=" in line)
        if out.get("PA") == "no":
            ok("SSH 已关闭密码登录", "仅密钥")
        else:
            fail("SSH 允许密码登录", f"PasswordAuthentication={out.get('PA')}")
        if out.get("F2B") == "active":
            ok("fail2ban 运行中", "")
        else:
            warn("fail2ban 未运行", out.get("F2B", ""))
        if out.get("HTTPS", "0") == "0":
            warn("服务器未启用 HTTPS", "备案通过后配置")
        else:
            ok("服务器已启用 HTTPS", "")
    except Exception as e:
        warn("SSH 检查失败", str(e)[:60])


def main():
    print(f"🛡️  饮力情报局 · 安全自查  {datetime.now():%Y-%m-%d %H:%M}")
    check_local()
    check_remote()
    check_site()
    check_invites()
    check_server()

    counts = {k: sum(1 for r in results if r[0] == k) for k in ("OK", "WARN", "FAIL")}
    print(f"\n\033[1m汇总\033[0m  通过 {counts['OK']} · 警告 {counts['WARN']} · 失败 {counts['FAIL']}")
    if counts["FAIL"]:
        print("\033[31m存在需要处理的问题，请查看上方 ❌ 项。\033[0m")
        sys.exit(1)
    if counts["WARN"]:
        print("\033[33m有非阻塞性提醒，建议抽空处理。\033[0m")
    else:
        print("\033[32m各项检查全部通过。\033[0m")


if __name__ == "__main__":
    main()
