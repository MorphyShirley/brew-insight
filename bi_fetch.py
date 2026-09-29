#!/usr/bin/env python3
"""
饮力情报局 · 观远BI数据接入（静态图高程转化为内嵌数据）
从观远 BI 拉取指定品牌页面卡片的聚合结果，规整后写入 coffee.html 的 BI_BRANDS，
结构按“品牌”分层，未来新增品牌只需在 BRANDS_SOURCES 增加一项。

用法:
  python3 bi_fetch.py            # 抓取并写回 coffee.html
  python3 bi_fetch.py --dry-run  # 只打印将写入的品牌与卡片数据概览

数据源（当前配置）:
  Tims天好咖啡 → 页面「产品数据看板_2026」卡片「Product Overview」
    口径: 2026-01-01 起，按页面默认筛选（日期、经营类型=直营），产品级 Qty/NS/门店/AUD/到手价/折扣/毛利率
"""
import csv
import datetime
import io
import json
import re
import subprocess
import sys

HTML = 'coffee.html'

# 品牌 → 观远 页面/卡片 配置（未来加品牌在此扩展一项即可）
BI_SOURCES = {
    'Tims天好咖啡': {
        'page': 'f9813530220a14a7f9a0e239', 'page_name': '产品数据看板_2026',
        'card': 'g1ef1060e0c404d88afd4314', 'card_name': 'Product Overview',
        'note': '口径：2026-01-01 起 · 页面默认筛选（日期/经营类型）',
        'outlet': '直营',
    },
}


def run_guancli(args):
    r = subprocess.run(['guancli'] + args, capture_output=True, text=True,
                       cwd=sys.path[0] or '.', timeout=180)
    if r.returncode != 0:
        raise RuntimeError('guancli 失败: %s\n%s' % (' '.join(args), r.stderr[-800:]))
    return r.stdout


def fetch_card_json(card, page):
    out = run_guancli(['card', 'preview', card, '--page-id', page,
                       '--with-default-filters', '--value-format', 'raw', '-f', 'json'])
    # 去掉 stdout 第一行 提示
    lines = out.splitlines()
    if lines and '已应用页面默认筛选' in lines[0]:
        lines = lines[1:]
    raw = '\n'.join(lines)
    return json.loads(raw)


def num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


# 字段前缀（观远 raw json 的列名以 "Unknown > " 开头）
K = {'name': '产品',
     'qty': 'Unknown > Qty', 'ns': 'Unknown > NS', 'share': 'Unknown > NS [2]',
     'stores': 'Unknown > 门店数', 'sold': 'Unknown > 有售出门店',
     'ads': 'Unknown > ADS', 'aud': 'Unknown > AUD',
     'price': 'Unknown > 到手价', 'disc': 'Unknown > Discount%', 'gm': 'Unknown > 毛利率'}


def build_brand_block(rows):
    kpis, products = [], {}
    for r in rows:
        name = r.get(K['name'], '')
        rec = {k2: num(r.get(k1)) for k2, k1 in K.items() if k2 != 'name'}
        rec['name'] = name
        if name == '总计':
            kpis = rec
        else:
            products[name] = rec
    items = sorted([p for p in products.values() if p['qty'] is not None],
                   key=lambda p: -p['qty'])[:20]
    return {'kpis': kpis, 'top20': items}


def main():
    dry = '--dry-run' in sys.argv
    data = {}
    for brand, cfg in BI_SOURCES.items():
        print(f"🔍 拉取 {brand} · 页面[{cfg['page_name']}] 卡片[{cfg['card_name']}] ...")
        csv_rows = fetch_card_json(cfg['card'], cfg['page'])
        block = build_brand_block(csv_rows)
        data[brand] = {
            'source': {'page': cfg['page'], 'card': cfg['card'],
                       'pageName': cfg['page_name'], 'cardName': cfg['card_name'],
                       'note': cfg['note'], 'outlet': cfg['outlet']},
            'updated': datetime.datetime.now().strftime('%Y-%m-%d'),
            **block,
        }
        print(f"   KPI: NS={block['kpis'].get('ns')}, Qty={block['kpis'].get('qty')}, "
              f"AUD={block['kpis'].get('aud')}, 产品数={len(block['top20'])}")
    print(f"\n✅ 共 {len(data)} 个品牌（{sum(len(v['top20']) for v in data.values())} 条产品记录）")

    if dry:
        return

    html = open(HTML, encoding='utf-8').read()
    block_json = json.dumps({'config': {'selector': 'Tims天好咖啡', 'brands': list(data)}, 'brands': data},
                            ensure_ascii=False)
    marker = re.compile(r'//@BI_START.*?//@BI_END', re.DOTALL)
    if not marker.search(html):
        print('❌ 未找到 //@BI_START/END 标记，请先加入占位')
        sys.exit(1)
    new_html = marker.sub('//@BI_START\nconst BI_DATA = ' + block_json + ';\n//@BI_END', html, count=1)
    open(HTML, 'w', encoding='utf-8').write(new_html)
    print(f'✅ 已写入 {HTML}')


if __name__ == '__main__':
    main()