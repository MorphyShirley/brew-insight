#!/usr/bin/env python3
"""
把 brand-menu-intel 技能库的菜单数据导入本项目 menu_data.json。
- 合并「外送 + 小程序」双渠道（按菜品名）
- 价格口径：到手价（缺失用现价），保留原价/折扣/月售/小程序价
用法: python3 menu_import_skill.py
"""
import json
import os
import re

SKILL = os.path.expanduser('~/.workbuddy/skills/brand-menu-intel')
OUT = 'menu_data.json'

# 技能库品牌名 → 本站品牌名
BRAND_MAP = {
    'Tims': 'Tims天好咖啡', '星巴克': '星巴克中国', '瑞幸': '瑞幸咖啡',
    'Manner': 'Manner', 'MStand': 'M Stand', '库迪': '库迪咖啡',
    'Peets': 'Peets Coffee', '肯悦': '肯悦咖啡',
    '麦当劳': '麦当劳', '肯德基': '肯德基', '汉堡王': '汉堡王', '赛百味': '赛百味', 'Popeyes': 'Popeyes',
}
ORDER = ['瑞幸咖啡', '星巴克中国', '库迪咖啡', 'Manner', 'M Stand', 'Peets Coffee', 'Tims天好咖啡', '肯悦咖啡',
         '麦当劳', '肯德基', '汉堡王', '赛百味', 'Popeyes']

NOISE = re.compile(r'^(月售[\d.]+\+?|近期[\d.]+人?\+?下单|已售[\d.]*|下单|￥[\d.]+)$')


def clean_tags(s):
    if not s:
        return []
    parts = [p.strip() for p in str(s).split('｜')]
    out = []
    for p in parts:
        if not p or NOISE.match(p):
            continue
        if p in out:
            continue
        out.append(p)
        if len(out) >= 4:
            break
    return out


def price_of(x):
    v = x.get('到手价')
    if v in (None, ''):
        v = x.get('现价')
    try:
        return round(float(v), 1) if v not in (None, '') else None
    except (TypeError, ValueError):
        return None


def num(x, k):
    v = x.get(k)
    if v in (None, ''):
        return None
    try:
        return round(float(v), 2) if k == '折扣(折)' else round(float(v), 0)
    except (TypeError, ValueError):
        return None


def build():
    meta = json.load(open(os.path.join(SKILL, 'data/meta.json'), encoding='utf-8'))
    snapshot = meta.get('snapshot', '')
    brands = {}
    for src, dst in BRAND_MAP.items():
        path = os.path.join(SKILL, 'data/menus', src + '.json')
        if not os.path.exists(path):
            print('⚠️ 缺少', path)
            continue
        d = json.load(open(path, encoding='utf-8'))
        dl = d.get('delivery', []) or []
        ma = d.get('mini_app', []) or []
        dl_map = {}
        for x in dl:
            dl_map.setdefault(x.get('菜品名', ''), x)
        ma_map = {}
        for x in ma:
            ma_map.setdefault(x.get('菜品名', ''), x)

        seen, items = set(), []
        for name in list(dl_map.keys()) + [n for n in ma_map.keys() if n not in dl_map]:
            if not name or name in seen:
                continue
            seen.add(name)
            base = dl_map.get(name) or ma_map.get(name)
            price = price_of(base)
            if price is None:
                continue
            mini = price_of(ma_map[name]) if name in ma_map else None
            item = {
                'name': name,
                'cat': base.get('菜单分类') or '未分类',
                'type': (base.get('类型') or '单品'),
                'price': price,
                'tags': clean_tags(base.get('活动角标 / 标签')),
            }
            orig = num(base, '原价')
            disc = num(base, '折扣(折)')
            sales = num(base, '月售')
            if orig is not None:
                item['orig'] = round(orig, 1)
            if disc is not None:
                item['disc'] = disc
            if sales is not None:
                item['sales'] = int(sales)
            if mini is not None:
                item['mini'] = mini
            items.append(item)

        brands[dst] = {
            'updated': snapshot,
            'source': '菜单截图抽取 · 美团外送+小程序',
            'items': items,
        }
        print(f'  {dst}: {len(items)} SKU')

    data = {'config': {'brands': ORDER}, 'brands': brands}
    json.dump(data, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    total = sum(len(v['items']) for v in brands.values())
    print(f'✅ 写入 {OUT} · 13 品牌 · {total} SKU')


if __name__ == '__main__':
    build()