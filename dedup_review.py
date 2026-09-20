#!/usr/bin/env python3
"""
饮力情报局 · 对抗式审查 + 去重
对 CARDS 进行一次性的对抗式质量审查与重复信息合并：
1) 对抗式审查（Adversarial Review）：
   - 剔除繁体/港台风噪资讯（面向简体读者）
   - 剔除个人社交噪音（facebook/instagram 打卡、撤奖、个人试喝日记等）
   - 保留可信行业媒体（36氪、界面、新华、证券日报、咖门等）
2) 去重（同一事件只保留信息量最高的一条）：
   - 同品牌内用「标题字符二元组 Jaccard」相似度判定同源资讯
   - 保留评分更高、来源更权威的一条
用法:
  python3 dedup_review.py               # 干跑：只打印将删除/合并的清单
  python3 dedup_review.py --apply        # 应用：重写 coffee.html 的 CARDS
"""
import re
import sys
import difflib
import html as html_module

HTML_PATH = 'coffee.html'

BLOCKED_DOMAINS = {'facebook.com', 'instagram.com', 'm.facebook.com'}
# 港台/繁体媒体域名（面向简体读者剔除）
TW_HK_DOMAINS = (
    'travel.yam.com', 'niusnews.com', 'womenshealthmag.com', 'cmnews.com.tw',
    'ufood.com.hk', 'orangenews.hk', 'ulapp.hk', 'thestormmedia.com',
    'hk01.com', 'hket.com', 'am730.com.hk', 'singtao.com', 'mingpao.com',
)
NOISE_TITLE = [
    '抽奖', '抽2万', '0.01元', '薅羊毛', '未中奖', '兑换码', '免费下载', '官方正版',
    '好喝', '蹭空调', '蹭wifi', '惬意', '日常饮食记录', '小红书背景图', '背景图',
    '手记', '打卡', '探店', '三轮摩托', '摩托车', 'vip', 'VIP', '博主', '吃瓜',
    '应用宝', 'Uber Eats', 'app下载', '日常vlog', '第一视角', '沉浸式体验',
]
NOISE_DESC = ['换号拉满', '去换号', '评论区抽', '私信领', '送杯']
SRC_RANK = ['36kr.com', 'm.36kr.com', 'jiemian.com', 'cbndata.com', 'news.cn',
            'zqrb.cn', 'jjckb.xinhuanet.com', 'foodinc.com.cn', 'm.canyin88.com',
            'eastmoney.com', 'wap.eastmoney.com', 'news.tom.com', 'sina.cn',
            'weibo.com', '4anet.com', 'sohu.com', 'm.sohu.com']


def is_trad_heavy(text):
    if not text:
        return False
    cjk = sum(1 for ch in text if '\u4e00' <= ch <= '\u9fff')
    if cjk == 0:
        return False
    TRAD = '熱銷賣開時這門發廣營賓觀點內聯產國裏臺灣風來憶嗎爺準確紅個買單幫體強'
    trad = sum(1 for ch in text if ch in TRAD)
    return (trad / cjk) > 0.12


def strip_source_suffix(t):
    """剥掉标题尾部的来源后缀（如 -36氪 / _东方财富网 / |搜狐网）"""
    for _ in range(3):
        m = re.search(r'[\s_|—-]+((?:[^，。！？\s]{1,12})?(?:网|报|社|氪|新闻|财经|影视|杂志|网站|传媒|媒体|客户端|观察|频道|专题|栏目|Bianews|DoNews))$', t)
        if not m:
            break
        t = t[:m.start()].rstrip(' -_|—-：:')
    return t


def normalize_title(title):
    t = title.lower()
    t = t.split('|')[0].strip()
    t = strip_source_suffix(t)
    t = re.split(r'\s*-\s*(?:36氪|CBNData|搜狐|新浪|搜狐网|界面|每日经济|证券日报|新华)', t)[0]
    t = t.strip('|_- .')
    zh = re.compile(r'[\u4e00-\u9fff0-9a-z]')
    return ''.join(zh.findall(t))


def bigrams(s):
    return set(s[i:i + 2] for i in range(len(s) - 1))


def jaccard(a, b):
    A, B = bigrams(a), bigrams(b)
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


FIELD_RX = re.compile(
    r"id:(\d+),?\s*|brand:'([^']*)',?\s*|time:'([^']*)',?\s*|score:([\d.]+),?\s*"
    r"|title:'((?:[^'\\]|\\.)*)',?\s*|desc:'((?:[^'\\]|\\.)*)',?\s*"
    r"|tags:\[([^\]]*)\],?\s*|src:'([^']*)',?\s*|url:'((?:[^'\\]|\\.)*)'"
)


def parse_card_line(line):
    fields = [g for mm in FIELD_RX.finditer(line) for g in mm.groups() if g is not None]
    if len(fields) < 9 or not fields[0].isdigit():
        return None
    return {
        'line': line, 'id': int(fields[0]), 'brand': fields[1], 'time': fields[2],
        'score': float(fields[3]), 'title': fields[4], 'desc': fields[5],
        'tags': re.findall(r"'([^']*)'", fields[6]), 'src': fields[7], 'url': fields[8],
    }


def parse_cards(html):
    m = re.search(r'const CARDS = \[(.*?)\n\];', html, re.DOTALL)
    if not m:
        raise SystemExit('❌ 未找到 CARDS')
    block = m.group(1)
    cards = []
    for line in block.split('\n'):
        c = parse_card_line(line)
        if c:
            cards.append(c)
    return cards


def domain_rank(src):
    for i, d in enumerate(SRC_RANK):
        if src in d or d in src:
            return i
    return len(SRC_RANK)


def adversarial_review(c):
    """返回 (是否剔除, 理由)"""
    if not re.search(r'[\u4e00-\u9fff]', c['title']) and not re.search(r'[\u4e00-\u9fff]', c['desc']):
        return True, '无中文内容'
    if any(d in c['src'] for d in TW_HK_DOMAINS) or is_trad_heavy(c['title']):
        return True, '繁体/港台风资讯'
    if any(b in c['src'] for b in BLOCKED_DOMAINS):
        return True, f'个人社交噪音 ({c["src"]})'
    if '不好喝' in c['title']:
        return False, ''
    for kw in NOISE_TITLE:
        if kw in c['title']:
            return True, f'低质噪音 (标题含"{kw}")'
    for kw in NOISE_DESC:
        if kw in (c.get('desc') or ''):
            return True, f'低质噪音 (内容含"{kw}")'
    return False, ''


def is_dup(a, b):
    """同品牌两标题是否同一事件（模糊匹配）"""
    na, nb = normalize_title(a), normalize_title(b)
    if len(na) < 8 or len(nb) < 8:
        return False
    return difflib.SequenceMatcher(None, na, nb).ratio() >= 0.50


def main():
    apply_ = '--apply' in sys.argv
    with open(HTML_PATH, 'r', encoding='utf-8') as f:
        html = f.read()
    cards = parse_cards(html)
    print(f'📋 解析到 {len(cards)} 条卡片\n')

    # 1) 对抗式审查
    dropped = []
    survivors = []
    for c in cards:
        bad, reason = adversarial_review(c)
        if bad:
            dropped.append((c, reason))
        else:
            survivors.append(c)

    # 2) 去重（同品牌内 标题二元组Jaccard >= 阈值）
    dup_removed = []
    by_brand = {}
    for c in survivors:
        by_brand.setdefault(c['brand'], []).append(c)

    final = []
    for brand, group in by_brand.items():
        group = sorted(group, key=lambda x: (x['time'], x['score']), reverse=True)
        keep = []
        for c in group:
            if any(is_dup(c['title'], k['card']['title']) for k in keep):
                rep = next(k['card'] for k in keep if is_dup(c['title'], k['card']['title']))
                if c['score'] > rep['score'] or (c['score'] == rep['score'] and domain_rank(c['src']) < domain_rank(rep['src'])):
                    dup_removed.append((rep, c))
                    keep = [k for k in keep if k['card']['id'] != rep['id']] + [{'card': c}]
                else:
                    dup_removed.append((c, rep))
                continue
            keep.append({'card': c})
        final.extend(k['card'] for k in keep)

    print('🔻 对抗式审查剔除:')
    for c, reason in dropped:
        print(f'  ✗ [{c["id"]}] {c["brand"]} {c["time"]} | {reason} | {c["title"][:38]}')
    print('\n🔁 重复信息合并:')
    for gone, rep in dup_removed:
        print(f'  ✗ [{gone["id"]}] {gone["brand"]} {gone["time"]} (评分{gone["score"]:.0f}/{rep["score"]:.0f}) "{gone["title"][:30]}"')
        print(f'      └ 保留 [id:{rep["id"]}] "{rep["title"][:30]}"')

    total_remove = len(dropped) + len(dup_removed)
    print(f'\n📊 原 {len(cards)} 条 → 保留 {len(final)} 条，移除 {total_remove} 条')

    if not apply_:
        print('\n(干跑模式，未写文件。加 --apply 应用)')
        return

    # 3) 重写 CARDS 数组（按时间倒序，最新在前）
    final = sorted(final, key=lambda c: (c['time'], c['score']), reverse=True)
    new_block_lines = [c['line'] for c in final]
    replacement = 'const CARDS = [\n' + '\n'.join(line.rstrip() if line.strip() else line for line in new_block_lines) + '\n];'
    new_html = html[:re.search(r'const CARDS = \[(.*?)\n\];', html, re.DOTALL).start()] + replacement + html[re.search(r'const CARDS = \[(.*?)\n\];', html, re.DOTALL).end():]
    with open(HTML_PATH, 'w', encoding='utf-8') as f:
        f.write(new_html)
    print(f'✅ 已写入 {HTML_PATH}')


if __name__ == '__main__':
    main()