#!/usr/bin/env python3
"""
饮力情报局 · 现有菜单数据注入
把 menu_data.json 写入 coffee.html 的 MENU_DATA（不手改 HTML）。
用法:
  python3 menu_build.py            # 注入并打印各品牌 SKU 数
  python3 menu_build.py --check    # 只校验 menu_data.json 结构
字段（每条 item）：
  name  产品名（必填）
  cat   品类，如 "咖啡·拿铁"（选填，默认"未分类"）
  price 单价（元，数字；不同杯型拆多条或留空）
  cup   杯型，如 "大杯"
  temp  温度，如 "冷/热"
  tags  标签数组，如 ["常驻","新品","季节限定"]
  note  备注
"""
import json
import re
import sys

HTML = 'coffee.html'
JSONF = 'menu_data.json'
REQ = {'name'}
ALLOWED = {'name', 'cat', 'price', 'cup', 'temp', 'tags', 'note'}


def load():
    with open(JSONF, encoding='utf-8') as f:
        return json.load(f)


def validate(data):
    errs, total = [], 0
    if not isinstance(data.get('brands'), dict):
        return ['缺少 brands 对象']
    if not data.get('config', {}).get('brands'):
        errs.append('缺少 config.brands 品牌顺序列表')
    allow_brands = set(data.get('config', {}).get('brands', []))
    for b, blk in data['brands'].items():
        if b not in allow_brands:
            errs.append(f'品牌 {b} 不在 config.brands 中（将不会显示）')
        items = blk.get('items', [])
        if not isinstance(items, list):
            errs.append(f'{b}.items 必须是数组'); continue
        for i, it in enumerate(items):
            if not isinstance(it, dict):
                errs.append(f'{b}[{i}] 不是对象'); continue
            for k in REQ:
                if not it.get(k):
                    errs.append(f'{b}[{i}] 缺少必填字段 {k}')
            extra = set(it) - ALLOWED
            if extra:
                errs.append(f'{b}[{i}] 含未知字段 {sorted(extra)}')
            if it.get('price') not in (None, '') and not isinstance(it['price'], (int, float)):
                errs.append(f'{b}[{i}].price 应为数字')
            total += 1
    return errs, total


def main():
    data = load()
    errs, total = validate(data)
    if errs:
        print('❌ 校验未通过：')
        for e in errs[:30]:
            print('   -', e)
        sys.exit(1)
    print('✅ 结构校验通过')
    for b in data['config']['brands']:
        n = len(data['brands'].get(b, {}).get('items', []))
        print(f'   {b}: {n} SKU')
    print(f'   合计 {total} SKU')

    if '--check' in sys.argv:
        return

    html = open(HTML, encoding='utf-8').read()
    block = ('//@MENU_START\n// 现有菜单数据（由 menu_build.py 注入，勿手改此处）\n'
             'const MENU_DATA = ' + json.dumps(data, ensure_ascii=False) + ';\n//@MENU_END')
    marker = re.compile(r'//@MENU_START.*?//@MENU_END', re.DOTALL)
    if not marker.search(html):
        print('❌ 未找到 //@MENU_START/END 标记')
        sys.exit(1)
    open(HTML, 'w', encoding='utf-8').write(marker.sub(block, html, count=1))
    print(f'✅ 已写入 {HTML}（接着运行 node lock.mjs 生成加密版）')


if __name__ == '__main__':
    main()