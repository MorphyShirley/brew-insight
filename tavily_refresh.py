#!/usr/bin/env python3
"""
饮力情报局 · Tavily 自动数据刷新
用 Tavily Search API 抓取 14 个品牌最新资讯，增量更新 CARDS 并部署上线。

用法:
  python3 tavily_refresh.py                # 抓取并更新本地 coffee.html
  python3 tavily_refresh.py --deploy       # 抓取 + commit + push 部署
  python3 tavily_refresh.py --dry-run      # 只显示将要新增的卡片，不写文件

环境变量:
  TAVILY_API_KEY       必填

配置:
  --max-new  每次最多新增条数 (默认 12)
  --top-k    每个品牌抓取条数 (默认 5)
"""

import os
import re
import sys
import html as html_module
import urllib.parse
from datetime import datetime

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

DAYS_BACK = 30  # 只保留最近 N 天的资讯

# 域 → 显示名
SRC_DISPLAY = {
    'news.google.com': 'Google News', '36kr.com': '36氪', 'finance.sina.com.cn': '新浪财经',
    'canyin88.com': '红餐网', 'jiemian.com': '界面新闻', 'thepaper.cn': '澎湃新闻',
    'eastmoney.com': '东方财富', '163.com': '网易', 'qq.com': '腾讯新闻',
    'sohu.com': '搜狐', 'baidu.com': '百度', 'zhihu.com': '知乎',
    'xueqiu.com': '雪球', 'cls.cn': '财联社', 'yicai.com': '第一财经',
    'nbd.com.cn': '每经', 'cnfin.com': '中国金融信息', 'gmw.cn': '光明网',
    'people.com.cn': '人民网', 'ce.cn': '中国经济网', 'xinmin.cn': '新民晚报',
}

def tavily_search(api_key, query, max_results=5):
    """调用 Tavily Search API"""
    import urllib.request
    import json as _json
    url = 'https://api.tavily.com/search'
    payload = _json.dumps({
        'api_key': api_key,
        'query': query,
        'search_depth': 'basic',
        'max_results': max_results,
        'include_domains': [],
        'topic': 'news',
    }).encode()
    req = urllib.request.Request(url, data=payload, headers={
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = _json.loads(resp.read().decode())
    results = []
    for r in data.get('results', []):
        results.append({
            'title': html_module.unescape(r.get('title', '')),
            'url': r.get('url', ''),
            'domain': (urllib.parse.urlparse(r.get('url', '')).netloc or ''),
            'published_date': r.get('published_date', ''),
            'content': (r.get('content', '') or '')[:400],
        })
    return results

def extract_date(published_date):
    """从 Tavily 的日期字符串解析 MM/DD，并返回 (MMDD, 完整日期对象)"""
    if not published_date:
        return None, None
    s = published_date.strip()
    year = None; month = None; day = None
    m = re.match(r'\w{3}, (\d{2}) (\w{3}) (\d{4})', s)
    if m:
        months = {'Jan':1,'Feb':2,'Mar':3,'Apr':4,'May':5,'Jun':6,
                  'Jul':7,'Aug':8,'Sep':9,'Oct':10,'Nov':11,'Dec':12}
        day = int(m.group(1)); month = months.get(m.group(2)); year = int(m.group(3))
    else:
        m = re.search(r'(\d{4})-(\d{2})-(\d{2})', s)
        if m:
            year = int(m.group(1)); month = int(m.group(2)); day = int(m.group(3))
    if not (year and month and day):
        return None, None
    return f'{month:02d}/{day:02d}', (year, month, day)

def is_trad_heavy(text):
    """判断文本是否繁体为主"""
    if not text:
        return False
    TRAD = '熱銷賣開時這門發廣營賓觀點內聯活產國裏臺臺灣風來憶嗎爺準確紅發個買單幫體強調辭億擼鮮隨杯分店星冰樂忌廉紙袋免費貼紙追蹤從頭調整響應運營寶貝們戰隊出圈圖源貼' 
    cjk = sum(1 for ch in text if '\u4e00' <= ch <= '\u9fff')
    if cjk == 0:
        return False
    trad = sum(1 for ch in text if ch in TRAD)
    return (trad / cjk) > 0.15

def is_relevant(title, desc=''):
    """质量过滤：保留简体中文的行业资讯"""
    # 纯英文/无中文字符 → 剔除（看板面向中文读者）
    if not re.search(r'[\u4e00-\u9fff]', title):
        return False
    # 繁体特征检测（港台/海外媒体剔除）
    if is_trad_heavy(title) or is_trad_heavy(desc):
        return False
    # 行业关键词必有其一
    HIT = ['新品', '上市', '首发', '上新', '财报', '业绩', '营收', '利润', '门店', '开店', '扩张',
           '闭店', '关店', '联名', '合作', '营销', '销量', '爆款', '会员', '出海', '海外', '咖啡',
           '奶茶', '茶饮', '饮品', '品牌', '增长', '亏损', '融资', '收购', 'IPO', '瑞幸', '星巴克',
           '喜茶', '奈雪', '霸王茶姬', '蜜雪', '库迪', '茶百道', 'Tims', 'Manner', '乐乐茶',
           '肯德基', '麦当劳', '麦咖啡', '果咖', '果茶', '鲜奶', '特调', 'Gelato', '冰淇淋',
           '代言', '下架', '整改', '套餐', '产品', '创新', '供应链']
    kw = sum(1 for k in HIT if k in title)
    if kw == 0:
        return False
    return True

def generate_score(title):
    base = 78
    if any(k in title for k in ['爆款', '热销', '售罄', '排队', '疯抢']): base += 12
    if any(k in title for k in ['新品', '首发', '全新', '升级']): base += 6
    if any(k in title for k in ['联名', '限定', '限量']): base += 4
    if any(k in title for k in ['财报', '营收', '利润', '增长']): base += 5
    if any(k in title for k in ['门店', '开店', '扩张']): base += 3
    return min(98, base)

def generate_tags(title):
    tags = []
    if re.search(r'新品|首发|全新|升级|上市|上新', title): tags.append('🆕 新品')
    if re.search(r'联名|合作|联动', title): tags.append('🥂 联名')
    if re.search(r'财报|业绩|营收|利润|亏', title): tags.append('📊 财报')
    if re.search(r'门店|开店|扩张|闭店|关店|万店', title): tags.append('🏪 门店')
    if re.search(r'营销|活动|热搜|销量|破纪录', title): tags.append('🎯 营销')
    if re.search(r'海外|出海|全球|泰国|东南亚|美国', title): tags.append('🌍 出海')
    if not tags:
        tags.append('📈 行业')
    return tags[:3]

def js_escape(s):
    """转义 JS 单引号字符串"""
    if not s:
        return ''
    return s.replace('\\', '\\\\').replace("'", "\\'").replace('\n', ' ').replace('\r', ' ')

def source_display(domain):
    if not domain:
        return '行业媒体'
    return SRC_DISPLAY.get(domain, domain.replace('www.', ''))

def build_search_url(title):
    """搜索该标题原文"""
    q = urllib.parse.quote(title)
    return f'https://www.bing.com/search?q={q}'

def parse_cards(html):
    """从 HTML 中解析现有 CARDS 数组（返回 id 列表 + 现有标题/URL 集合）"""
    m = re.search(r'const CARDS = \[(.*?)\n\];', html, re.DOTALL)
    if not m:
        return set(), set(), 0
    block = m.group(1)
    ids = [int(x) for x in re.findall(r'id:\s*(\d+)', block)]
    titles = set(re.findall(r"title:\s*'([^']*)'", block))
    urls = set(re.findall(r"url:\s*'([^']*)'", block))
    max_id = max(ids) if ids else 0
    return titles, urls, max_id

def build_new_cards(news_items, existing_titles, existing_urls, next_id):
    """把 Tavily 结果转为 CARDS 条目（去重 + 生成）"""
    cards = []
    for it in news_items:
        if not it['title'] or not it['url']:
            continue
        if not is_relevant(it['title'], it.get('content') or ''):
            continue
        if it['title'] in existing_titles or it['url'] in existing_urls:
            continue
        time, full_date = extract_date(it['published_date'])
        if not time:
            continue
        # 时间过滤：只保留最近 N 天内
        now = datetime.now()
        if full_date:
            y, m, d = full_date
            try:
                delta = (now - datetime(y, m, d)).days
                if delta < 0 or delta > DAYS_BACK:
                    continue
            except ValueError:
                continue
        score = generate_score(it['title'])
        tags = generate_tags(it['title'])
        src = source_display(it['domain'])
        url = it['url'] if it['url'].startswith('http') else build_search_url(it['title'])
        desc = it['content'] or it['title']
        # 截断到 130 字并加省略号（避免卡片过胖）
        if len(desc) > 130:
            desc = desc[:130].rstrip() + '…'
        cards.append({
            'id': next_id, 'brand': it['brand'], 'time': time, 'score': score,
            'title': it['title'], 'desc': desc, 'tags': tags, 'src': src, 'url': url,
        })
        next_id += 1
    # 按发布时间从新到旧排序
    def sort_key(c):
        for it2 in news_items:
            if it2['title'] == c['title']:
                _, fd = extract_date(it2['published_date'])
                return fd or (0, 0, 0)
        return (0, 0, 0)
    cards.sort(key=sort_key, reverse=True)
    return cards

def fmt_card(c):
    tags = "','".join(c['tags'])
    return (f"  {{ id:{c['id']}, brand:'{js_escape(c['brand'])}', time:'{c['time']}', score:{c['score']}, "
            f" title:'{js_escape(c['title'])}',  desc:'{js_escape(c['desc'])}', "
            f" tags:['{tags}'], src:'{js_escape(c['src'])}', url:'{js_escape(c['url'])}' }},")

def update_html(html, new_cards):
    """把新卡片插到 CARDS 数组头部"""
    if not new_cards:
        return html
    # 匹配 CARDS 数组：从 const CARDS = [ 到第一个独占一行的 ]; 结束
    m = re.search(r'const CARDS = \[(.*?)\n\];', html, re.DOTALL)
    if not m:
        print('❌ 未找到 CARDS 标记')
        return html
    old_block = m.group(1)
    new_block = ''.join(fmt_card(c) + '\n' for c in new_cards)
    replacement = f'const CARDS = [\n{new_block}{old_block.strip()}\n];'
    new_html = html[:m.start()] + replacement + html[m.end():]

    # 更新时间戳
    today = datetime.now().strftime('%Y-%m-%d')
    new_html = re.sub(r'更新于 \d{4}-\d{2}-\d{2}', f'更新于 {today}', new_html)
    new_html = re.sub(r'数据更新至 \d{4}-\d{2}-\d{2}', f'数据更新至 {today}', new_html)
    return new_html

def main():
    global DAYS_BACK
    deploy = '--deploy' in sys.argv
    dry = '--dry-run' in sys.argv
    if dry: deploy = False
    if '--days' in sys.argv:
        try:
            DAYS_BACK = int(sys.argv[sys.argv.index('--days') + 1])
        except (IndexError, ValueError):
            pass

    api_key = os.environ.get('TAVILY_API_KEY', '').strip()
    if not api_key:
        print('❌ 未设置 TAVILY_API_KEY 环境变量')
        sys.exit(1)

    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'coffee.html')
    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()

    existing_titles, existing_urls, max_id = parse_cards(html)
    print(f"📋 现有卡片: {len(existing_titles)} 条, 最大 id={max_id}")

    all_news = []
    for brand, info in BRANDS.items():
        print(f"\n🔍 搜索 {brand}...")
        try:
            results = tavily_search(api_key, info['kw'])
        except Exception as e:
            print(f"  ⚠️  {brand} 失败: {type(e).__name__}: {str(e)[:80]}")
            continue
        if not results:
            print(f"  ⚠️  无结果")
            continue
        for r in results:
            r['brand'] = brand
        all_news.extend(results)
        print(f"  ✅ {len(results)} 条")

    new_cards = build_new_cards(all_news, existing_titles, existing_urls, max_id + 1)
    print(f"\n✨ 待新增卡片: {len(new_cards)} 条")

    if dry:
        for c in new_cards:
            print(f"  → [{c['time']}] [{c['brand']}] {c['title'][:50]}")
        return

    if not new_cards:
        print('ℹ️  无新资讯，跳过更新')
        return

    updated = update_html(html, new_cards)
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(updated)
    print(f"✅ 已更新 {html_path}")

    if deploy:
        import subprocess
        repo = os.path.dirname(os.path.abspath(__file__))
        date = datetime.now().strftime('%Y-%m-%d')
        subprocess.run(['git', 'add', 'coffee.html', 'index.html'], cwd=repo, check=True)
        subprocess.run(['git', 'commit', '-m', f'🤖 自动刷新资讯 {date} (+{len(new_cards)})'], cwd=repo, check=True)
        subprocess.run(['git', 'push', 'origin', 'main'], cwd=repo, check=True)
        print('🚀 已自动部署')

if __name__ == '__main__':
    main()