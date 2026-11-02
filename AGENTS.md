# ☕ 饮力情报局 · 项目上下文（新会话交接）

> 本文件由旧会话「咖啡奶茶行业热点信息推送网页」迁移生成，供新会话直接接手。所有数据与页面内容均已固化在 `~/coffee.html` 与 `~/coffee-site/` 中。

## 这是什么

一个**咖啡+茶饮行业热点聚合看板**单页应用（深色风），聚合 14 个品牌的资讯、产品评分、竞品矩阵、品牌宇宙与深度分析。无后端，数据全部内嵌在 HTML 的 JS 常量中，直接双击打开 HTML 即可运行。

## 关键文件

| 路径 | 说明 |
|---|---|
| `~/coffee.html` | **最新正式版（179KB，2026-08-11 更新）**，已部署上线。后续所有改动都以它为准。 |
| `~/coffee-site/coffee.html` | 仓库内工作副本（已同步为最新版） |
| `~/coffee-site/index.html` | GitHub Pages 入口（已同步为最新版） |
| `~/coffee-site/refresh.py` | Python 自动刷新脚本：抓 Google News RSS → 生成产品数据 → 写入 HTML |
| `~/coffee-site/.github/workflows/refresh.yml` | GitHub Actions：同步 index.html 部署 Pages |
| `~/coffee-site/README.md` | 部署说明 |

## 线上地址

- GitHub Pages（主站）：**https://morphyshirley.github.io/brew-insight/**
- Surge 备用：https://brew-insight.surge.sh

## 页面数据结构（都在 `coffee.html` 内）

- `const PRODUCT_ANALYSIS`（~1041 行起）：产品多维评分，键形如 `'柠打·九窨茉王（喜茶）'`，含 brand/date/sales/rating/growth/scores/pos/neg/summary
- `const BRANDS`（~1579 行起）：14 个品牌定义（颜色、图标、简介）
- `const CARDS`（~1646 行起）：**资讯卡片数组**，字段 `{id, brand, time, score, title, desc, tags, src, url}`，`url` 已做成可点击跳转（Bing 搜索该标题原文）
- 页面含「今日精选 / 全部资讯 / 品牌宇宙 / 竞品矩阵 / 产品分析 / 深度分析」等多个 Tab

## 最近一次数据更新（2026-08-11，含 8 月上旬）

12 条热点资讯已入库：瑞幸 Q2 财报(净收入159亿/+28.5%)、霸王茶姬立秋销量+200%、茉莉奶白瓶装茶进山姆、喜茶康普茶特调、星巴克会员权益升级、古茗 9.9 元+苹果大红袍、茶百道销量 4 倍、奈雪联名刘晓庆财神奶、沪上阿姨利润+58.3%、Manner 南通首店、蜜雪立秋纪录、库迪增长停滞。

## 维护方式

- 半自动：在新会话里让 AI 用 explore subagent 搜索某品牌最新动态 → 手写/更新 `CARDS` 与 `PRODUCT_ANALYSIS` → 用 GitHub API 直接 PUT 到仓库 `index.html`（旧会话曾用此方式，脚本见历史记录）。
- 全自动：`python refresh.py`（抓 Google News RSS，14 品牌 × 5 条）。
- 部署：`cp coffee.html index.html && git add/commit/push`，GitHub Actions 会同步，或直接 API PUT 到 `contents/index.html`。

## 注意事项

- 在线页面有浏览器缓存，更新后要带 `?v=时间戳` 或 `Cmd+Shift+R` 强刷验证。
- git remote 中内嵌了 GitHub token，注意不要泄露到公开仓库。