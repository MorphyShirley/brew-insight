# ☕ 饮力情报局 · 咖啡茶饮行业热点聚合

自动抓取各大品牌最新资讯，生成行业情报看板。

## 部署方式

### GitHub Actions 自动部署（推荐）

1. **Fork 或 Push 此仓库到 GitHub**

2. **在 GitHub 仓库设置中添加 Secrets**：
   - `Settings` → `Secrets and variables` → `Actions`
   - 添加 `SURGE_TOKEN` = `fa6ed0b4299c4cf7abd02657cf9a855a`

3. **启用 GitHub Pages**（可选，用于直接访问）：
   - `Settings` → `Pages`
   - Source: `GitHub Actions`

4. **Workflow 自动运行**：
   - 每天 UTC 2:00 和 8:00（北京时间 10:00 和 16:00）
   - 也可在 Actions 页手动触发 `workflow_dispatch`

### 手动部署

```bash
# 安装依赖
pip install -r requirements.txt

# 刷新数据
python refresh.py

# 部署到 surge
cp coffee.html index.html
npx surge ./ brew-insight.surge.sh
```

## 访问地址

- Surge: https://brew-insight.surge.sh
- GitHub Pages: (待配置)

## 数据来源

- Google News RSS
- 36氪、新浪财经、网易等公开资讯
