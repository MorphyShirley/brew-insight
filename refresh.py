#!/usr/bin/env python3
"""
饮力情报局 · 自动数据刷新脚本
每天自动抓取各品牌最新资讯，更新产品数据并部署。
"""

import re
import json
import time
import html as html_module
from datetime import datetime, timezone, timedelta
import xml.etree.ElementTree as ET

try:
    import requests
except ImportError:
    requests = None

# ── 品牌与搜索关键词 ──
BRANDS = {
    '瑞幸咖啡': {'kw': '瑞幸咖啡 新品'},
    '星巴克中国': {'kw': '星巴克 新品'},
    '喜茶': {'kw': '喜茶 新品'},
    '奈雪的茶': {'kw': '奈雪 新品'},
    '霸王茶姬': {'kw': '霸王茶姬 新品'},
    '蜜雪冰城': {'kw': '蜜雪冰城 新品'},
    '库迪咖啡': {'kw': '库迪咖啡 新品'},
    '茶百道': {'kw': '茶百道 新品'},
    'Tims天好咖啡': {'kw': 'Tims 咖啡 新品'},
    'Manner': {'kw': 'Manner 咖啡 新品'},
    'M Stand': {'kw': 'M Stand 咖啡 新品'},
    '乐乐茶': {'kw': '乐乐茶 新品'},
    '肯德基': {'kw': '肯德基 咖啡 新品'},
    '麦当劳': {'kw': '麦当劳 咖啡 新品'},
}

SOURCE_DISPLAY = {
    '瑞幸咖啡': '瑞幸', '星巴克中国': '星巴克', '喜茶': '喜茶',
    '奈雪的茶': '奈雪', '霸王茶姬': '霸王茶姬', '蜜雪冰城': '蜜雪冰城',
    '库迪咖啡': '库迪', '茶百道': '茶百道', 'Tims天好咖啡': 'Tims',
    'Manner': 'Manner', 'M Stand': 'M Stand', '乐乐茶': '乐乐茶',
    '肯德基': '肯德基', '麦当劳': '麦当劳',
}

BRAND_ICONS = {
    '瑞幸咖啡': ['瑞', '#1a3a2a'], '星巴克中国': ['星', '#006241'],
    '喜茶': ['喜', '#d4543a'], '奈雪的茶': ['奈', '#8b2c6e'],
    '霸王茶姬': ['霸', '#b07d3a'], '蜜雪冰城': ['蜜', '#e8432a'],
    '库迪咖啡': ['库', '#3a6a8a'], '茶百道': ['茶', '#2a6e4a'],
    'Tims天好咖啡': ['T', '#c0392b'], 'Manner': ['M', '#f5a623'],
    'M Stand': ['M', '#2c2c2c'], '乐乐茶': ['乐', '#e86a8a'],
    '肯德基': ['K', '#d42a2a'], '麦当劳': ['麦', '#f0c040'],
}


def fetch_news(brand_name, keyword, max_results=5):
    """从 Google News RSS 获取品牌最新资讯"""
    results = []
    from urllib.parse import quote
    query = quote(keyword)
    url = f"https://news.google.com/rss/search?q={query}&hl=zh-CN&gl=CN"
    
    try:
        if requests:
            resp = requests.get(url, timeout=15, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                              'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }, verify=False)
            xml_data = resp.content
        else:
            from urllib.request import urlopen, Request
            import ssl
            ctx = ssl._create_unverified_context()
            req = Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                              'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            resp = urlopen(req, timeout=15, context=ctx)
            xml_data = resp.read()
        
        root = ET.fromstring(xml_data)
        channel = root.find('channel')
        if channel is None:
            return results
        
        for item in channel.findall('item'):
            title = item.findtext('title', '')
            pub_date = item.findtext('pubDate', '')
            link = item.findtext('link', '')
            source = item.findtext('source', '')
            
            # 解析日期
            try:
                dt = datetime.strptime(pub_date, '%a, %d %b %Y %H:%M:%S %Z')
            except:
                dt = datetime.now()
            
            # 清洗标题
            title = html_module.unescape(title)
            # 移除来源前缀如 "[36氪] "
            title = re.sub(r'^\[[^\]]*\]\s*', '', title)
            
            results.append({
                'title': title,
                'date': dt.strftime('%Y-%m-%d'),
                'source': source or '行业媒体',
                'link': link,
            })
            
            if len(results) >= max_results:
                break
                
    except Exception as e:
        print(f"  ⚠️  {brand_name}: 抓取失败 - {type(e).__name__}: {str(e)[:60]}")
    
    return results


def extract_product_name(title, brand_name):
    """从文章标题中提取产品名"""
    # 常见模式: "品牌推出「产品名」" 或 "品牌「产品名」上线"
    patterns = [
        r'[「【]([^」】]+)[」】]',  # 书名号内的内容
        r'(?:推出|上线|上新|发布|开卖|开售)(?:\s*)([^，。！？\s]{2,20})',
        r'([^，。！？\s]{2,20})(?:新品|全新升级|正式上线|限时|回归)',
        r'(?:新品|新品尝鲜|夏日限定|季节限定)[：:]\s*([^，。！？\s]{2,20})',
    ]
    
    # 先尝试提取引号内的内容
    for pattern in patterns:
        match = re.search(pattern, title)
        if match:
            name = match.group(1).strip()
            if 2 <= len(name) <= 30:
                return name
    
    # 如果没找到，从标题中截取合理的产品描述
    # 移除品牌名
    clean = re.sub(re.escape(brand_name), '', title).strip()
    # 取前15个字作为产品名
    if clean and len(clean) > 2:
        short = clean[:20]
        return short
    
    return None


def generate_scores(title):
    """根据标题关键词生成评分"""
    base = 78
    if any(kw in title for kw in ['爆款', '热销', '售罄', '排队', '疯抢']):
        base += 12
    if any(kw in title for kw in ['新品', '首发', '全新', '升级']):
        base += 6
    if any(kw in title for kw in ['联名', '限定', '限量']):
        base += 4
    if any(kw in title for kw in ['夏季', '夏日', '冰', '清爽']):
        base += 3
    
    score = min(98, base)
    return {
        '口味': score,
        '包装': score - 5,
        '性价比': score - 8,
        '复购意愿': score - 3,
        '社交传播': score + 2,
    }


def build_product_entry(brand_name, article):
    """根据文章信息生成 PRODUCT_ANALYSIS 条目"""
    product_name = extract_product_name(article['title'], brand_name)
    if not product_name:
        return None
    
    key = f"{product_name}（{brand_name}）"
    scores = generate_scores(article['title'])
    
    entry = {
        'brand': brand_name,
        'date': article['date'],
        'sales': '最新资讯',
        'revenue': '-',
        'rating': round((scores['口味'] + scores['包装'] + scores['性价比'] + 
                         scores['复购意愿'] + scores['社交传播']) / 50, 1),
        'growth': '新资讯',
        'repeat': '待观察',
        'avgPrice': '- 元',
        'scores': scores,
        'pos': ['行业热点', '新品关注'],
        'neg': ['数据待核实'],
        'summary': f"来自 {article['source']} 的最新资讯：{article['title']}",
    }
    
    return key, entry


def format_product_analysis(entries):
    """将 PRODUCT_ANALYSIS 格式化为 JS 代码"""
    lines = ['const PRODUCT_ANALYSIS = {']
    
    for key, data in entries:
        lines.append(f"  '{key}': {{")
        lines.append(f"    brand: '{data['brand']}', date: '{data['date']}',")
        lines.append(f"    sales: '{data['sales']}', revenue: '{data['revenue']}', rating: '{data['rating']}',")
        lines.append(f"    growth: '{data['growth']}', repeat: '{data['repeat']}', avgPrice: '{data['avgPrice']}',")
        
        s = data['scores']
        lines.append(f"    scores: {{ 口味: {s['口味']}, 包装: {s['包装']}, 性价比: {s['性价比']}, 复购意愿: {s['复购意愿']}, 社交传播: {s['社交传播']} }},")
        
        pos = "','".join(data['pos'])
        neg = "','".join(data['neg'])
        lines.append(f"    pos: ['{pos}'],")
        lines.append(f"    neg: ['{neg}'],")
        lines.append(f"    summary: '{data['summary']}'")
        lines.append('  },')
    
    lines.append('};')
    return '\n'.join(lines)


def update_html(html_path):
    """主函数：更新 HTML 中的产品数据"""
    print(f"📖 读取 {html_path}")
    
    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    all_entries = []
    
    for brand_name, info in BRANDS.items():
        print(f"\n🔍 搜索 {brand_name}...")
        articles = fetch_news(brand_name, info['kw'])
        
        if not articles:
            print(f"  ⚠️  未获取到 {brand_name} 的最新资讯")
            continue
        
        print(f"  ✅ 获取到 {len(articles)} 条资讯")
        
        for article in articles:
            print(f"     ➜ {article['title'][:40]}...")
            result = build_product_entry(brand_name, article)
            if result:
                all_entries.append(result)
    
    if not all_entries:
        print("\n❌ 未获取到任何新产品数据，保留原有数据")
        return False
    
    # 按日期排序（最新的在前）
    all_entries.sort(key=lambda x: x[1]['date'], reverse=True)
    
    # 最多保留 20 条
    all_entries = all_entries[:20]
    
    print(f"\n✅ 共获取到 {len(all_entries)} 款产品数据")
    
    # 替换 PRODUCT_ANALYSIS
    new_analysis = format_product_analysis(all_entries)
    pattern = r'const PRODUCT_ANALYSIS = \{.*?\};'
    match = re.search(pattern, html, re.DOTALL)
    
    if match:
        html = html[:match.start()] + new_analysis + html[match.end():]
        print("✅ 已更新 PRODUCT_ANALYSIS")
    else:
        print("❌ 未找到 PRODUCT_ANALYSIS 标记")
        return False
    
    # 更新时间戳
    today = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d')
    html = re.sub(
        r'数据更新至 \d{4}-\d{2}-\d{2}',
        f'数据更新至 {today}',
        html
    )
    html = re.sub(
        r'更新于 \d{4}-\d{2}-\d{2}',
        f'更新于 {today}',
        html
    )
    print("✅ 已更新日期戳")
    
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"\n✅ 文件已保存: {html_path}")
    return True


if __name__ == '__main__':
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(script_dir, 'coffee.html')
    
    print(f"☕ 饮力情报局 · 自动数据刷新")
    print(f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    success = update_html(html_path)
    
    if success:
        print("\n🎉 数据刷新完成！")
    else:
        print("\n⚠️  数据刷新未完成")
        exit(1)
