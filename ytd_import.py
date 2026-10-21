#!/usr/bin/env python3
"""
本品牌菜单 · Tims 外送菜单 YTD 数据导入
读取 ~/.workbuddy/skills/brand-menu-intel/data/ytd/*.json，
聚合成紧凑的 BRAND_YTD 结构写入 coffee.html（按品牌分层，便于扩展其他品牌）。

用法: python3 ytd_import.py
"""
import datetime
import json
import os
import re

SKILL = os.path.expanduser('~/.workbuddy/skills/brand-menu-intel/data/ytd')
HTML = 'coffee.html'
BRAND = 'Tims天好咖啡'


def load(name):
    with open(os.path.join(SKILL, name + '.json'), encoding='utf-8') as f:
        return json.load(f)


def build():
    meta = load('meta')
    stats = load('stats')
    periods = load('periods')['rows']
    price = load('price')
    stores = load('stores')
    launch = load('launch')['rows']

    dq = stats['档期']
    st = stats['上新结构']
    life = stats['生命周期']
    cat = stats['类目']
    shop = stats['门店']
    chg = stats['调价']

    # 档期节奏
    periodRows = [{
        'p': r['档期'], 'alive': r['在售SKU'], 'launch': r['新上SKU'],
        'ala': r['新上ALA'], 'set': r['新上套餐'], 'off': r['当档下架'], 'net': r['净变化'],
    } for r in periods]

    # 全量上新（供档期下钻；同一 SKU 多杯型行按名称去重）
    launchAll, _seen = [], set()
    for r in launch:
        key = (r['首次档期'], r['商品名称'])
        if key in _seen:
            continue
        _seen.add(key)
        launchAll.append({
            'p': r['首次档期'], 'name': r['商品名称'], 'type': r['类型'], 'cat': r['类目'],
            'price': r.get('上新D5价', ''), 'status': r.get('当前状态', ''),
        })

    # SKU 生命周期明细（供生命周期下钻）
    skuLife = [{
        'name': s['商品名称'], 'cat': s['类目'], 'type': s['类型'],
        'price': s.get('基准价'), 'periods': s.get('在售档期数'),
        'first': s.get('首次档期'), 'status': s.get('最新状态', ''),
    } for s in load('sku')['skus']]

    # 城市明细（供门店下钻）
    cityDetail = [{
        'city': r['城市'], 'total': r['门店数'], 'std': r.get('标准店', 0),
        'go': r.get('GO店', 0), 'express': r.get('Express店', 0),
        'snpc': r.get('中石化店', 0), 'share': r.get('标准店占比', 0),
    } for r in stores['城市分布']]

    # 最近档期上新
    recentPeriods = [periods[-1]['档期'], periods[-2]['档期']]
    recent = []
    for p in recentPeriods:
        items = [r for r in launch if r['首次档期'] == p][:10]
        recent.append({
            'period': p,
            'n': len([r for r in launch if r['首次档期'] == p]),
            'items': [{'name': r['商品名称'], 'type': r['类型'], 'cat': r['类目'],
                       'status': r.get('当前状态', ''), 'price': r.get('上新D5价', '')} for r in items],
        })

    # 生命周期
    lifeRows = [{'lab': k, 'n': v} for k, v in life['分布'].items()]
    catRows = [{'cat': k, 'sku': v['SKU'], 'alive': v['在售'], 'rate': v['在售率']} for k, v in cat.items()]

    # 价盘
    priceCats = [{
        'cat': r['类目'], 'sku': r['SKU数'], 'single': r['单一价SKU'],
        'd5avg': r['D5均价'], 'd5med': r['D5中位'], 'd5range': r['D5区间'],
        'd2avg': r['D2均价'], 'diff': r['D2减D5'], 'pkg': r['打包费'],
    } for r in price['类目价盘']]
    priceHigh = price['高端Top8']
    priceLow = price['低端Top8']
    priceChanges = price['调价明细'][:12]

    # 门店
    types = [{'name': r['菜单类型'], 'n': r['门店数'], 'share': r['占比']} for r in stores['店型分布'][:6]]
    cities = [{'name': r['城市'], 'n': r['门店数']} for r in stores['城市分布'][:12]]
    modes = [{'name': r['经营方式'], 'n': r['门店数'], 'share': r['占比']} for r in stores['经营方式']]

    # 建议（数据驱动）
    rnd = [
        {'icon': '⏱️', 'title': '档期节奏：双周小档 + 月度大档',
         'action': '保持双周上新，大档集中 20+ SKU',
         'metrics': [f"平均 {dq['平均每档新上']}/档", '大档 20+', f"零上新 {len(dq['零上新档期'])} 档"],
         'detail': f"参考 {'、'.join(x['档期'] for x in dq['上新最多档期'][1:])} 的大档节奏；避免连续零上新导致菜单老化。"},
        {'icon': '🧬', 'title': '结构：套餐化承接客单',
         'action': '继续「咖啡+贝果/暖食」套餐，保留约 40% ALA',
         'metrics': [f"套餐 {st['前段']['套餐占比']*100:.0f}%→{st['后段']['套餐占比']*100:.0f}%", f"全期 {st['总'] if False else st['套餐占比']*100:.0f}%"],
         'detail': '套餐占新上比重持续上升，说明组合场景有效；ALA 保留尝鲜与复购入口，避免菜单过度套餐化。'},
        {'icon': '♻️', 'title': '生命周期：建「爆款池」',
         'action': '活过 9 档的 SKU 进入常青池，潜力款给二次档期',
         'metrics': [f"短期+闪现 {life['分布']['短期(3-8)']+life['分布']['闪现(1-2)']} 款", f"全程在售 {life['分布']['全程在售(27)']}"],
         'detail': '短期与闪现款合计占约 59%，一次性上新偏多；把验证过的产品二次投放，可摊薄研发与推广成本。'},
        {'icon': '💲', 'title': '价盘：补 20–25 元咖啡带',
         'action': '咖啡补 20–25 元价格带，烘焙做 12–18 元小食组合',
         'metrics': [f"咖啡 D5 中位 {stats['价格带']['咖啡']['中位']:.0f}", f"区间 {stats['价格带']['咖啡']['最低']:.0f}–{stats['价格带']['咖啡']['最高']:.0f}"],
         'detail': '咖啡价格集中在 28 元附近，20–25 元带供给偏薄；烘焙 6–35 元跨度大，适合做引流组合。'},
        {'icon': '🥯', 'title': '品类：聚焦贝果/可颂成功率',
         'action': '烘焙聚焦 3–5 个核心 SKU，减少长尾',
         'metrics': [f"在售率 非咖 {cat['非咖饮品']['在售率']*100:.0f}%", f"咖啡 {cat['咖啡']['在售率']*100:.0f}%", f"烘焙 {cat['烘焙小食']['在售率']*100:.0f}%"],
         'detail': '烘焙小食汰换最快，SKU 数量最多但成功率不高，应收敛到少数高复购单品再扩口味。'},
        {'icon': '🌿', 'title': '风味：季节限定 + 果咖/茶咖',
         'action': '结合节气与市场风味做季节限定',
         'metrics': ['果咖', '气泡美式', '茶咖', '低GI'],
         'detail': '横向市场显示果咖/气泡/茶咖与健康化是主要增量方向，建议按节气（立秋/中秋/冬季暖饮）排限定。'},
    ]
    supply = [
        {'icon': '📦', 'title': '档期备货：提前 2 周，大档 3 周',
         'action': '按 27 个档期排产，大档提前锁定原料与包装',
         'metrics': ['27 档期', '大档 3 个', '提前 2 周'],
         'detail': f"大档为 {'、'.join(x['档期'] for x in dq['上新最多档期'][1:])}；包装与限定原料需更早下单。"},
        {'icon': '🏷️', 'title': '常备库存：83 款常青 + 长销',
         'action': '常青/长销款保安全库存，新品小批量试产',
         'metrics': [f"常青 {life['分布']['全程在售(27)']}", f"长销 {life['分布']['长销(18-26)']}", '新品 ≤30%'],
         'detail': '常备款保障日常供应与复购；新品首批按常规量 30% 以内试产，按档期表现追加。'},
        {'icon': '⚠️', 'title': '汰换预警：连续 2 档零动销停补',
         'action': '建立下架清单，短期/闪现款快清库',
         'metrics': [f"累计下架 {dq['累计下架']} 次", f"短期 {life['分布']['短期(3-8)']}", f"闪现 {life['分布']['闪现(1-2)']}"],
         'detail': '长尾原料是主要积压来源；对连续两档零动销 SKU 停止补货，避免临期与报废。'},
        {'icon': '💱', 'title': '价格版本：成本按 D5，结算按 D2',
         'action': '成本核算用 D5，渠道结算用 D2，另计打包费',
         'metrics': [f"D2 高 5–8%", '打包费 1.3–2.7', f"调价 {chg['调价SKU数']} 款"],
         'detail': 'D2 全线高于 D5 约 1.3–2.6 元；混用会低估成本或高估毛利，需在系统内区分价盘版本。'},
        {'icon': '🏙️', 'title': '门店与城市：分店型、保五城',
         'action': 'GO/Express 精简 SKU；优先保障 Top5 城市冷链',
         'metrics': [f"标准店 {shop['标准店占比']*100:.0f}%", f"Top5 {shop['Top5集中度']*100:.0f}%", f"{shop['城市数']} 城"],
         'detail': '标准店 80.8%，其余为 GO/Express/中石化/交通枢纽；五城集中度高，冷链与小食周转优先保障。'},
    ]
    strategy = [
        {'p': 'P0', 'title': '私域价差', 'desc': '小程序 7.71 折 vs 外送 6.22 折，有折扣 SKU 仅 29%', 'metric': '核心 20 款再降 2–3 元'},
        {'p': 'P0', 'title': '外送常驻爆款', 'desc': '鲜萃黑咖月售 1000/800（到手 13.5 元）验证价格带', 'metric': '13.5 元做成常驻价'},
        {'p': 'P1', 'title': '套餐标准化', 'desc': '套餐占 27% 但组合散落，缺固定档位', 'metric': '15/20/25 元三档'},
        {'p': 'P1', 'title': '中端双锚', 'desc': '单品到手均价 16.9 元，上下受挤', 'metric': '12–15 守量 / 20+ 拉客单'},
        {'p': 'P2', 'title': '周边联名空白', 'desc': '周边 SKU 为 0，竞品用联名/盲盒溢价', 'metric': '先小程序限定测款'},
    ]
    risk = [
        'YTD 价格为线上原价（D5/D2），非到手价，不可与横向快照的到手价直接比较',
        '163 个套餐中 129 个为区间价（组合上下限），不可当作单一价格比较',
        '仅覆盖标准店价盘（80.8%），全国性定价结论需注明口径',
        '上新存活率存在生存偏差：越早的档期经历的下架窗口越多',
    ]
    advice = {'rnd': rnd, 'supply': supply, 'risk': risk, 'strategy': strategy}

    return {
        'config': {'brands': [BRAND], 'active': BRAND},
        'brands': {
            BRAND: {
                'meta': {
                    'label': meta.get('label'), 'channel': (meta.get('channel') or '外送').replace('美团', '美团&淘闪'),
                    'source': meta.get('source_file'), 'extracted': meta.get('extracted_at'),
                },
                'kpi': {
                    'periods': dq['档期数'], 'sku': dq['累计新上SKU'], 'launch': dq['档期内真实新增'],
                    'baseline': dq['基线盘'], 'alive': life['最新档期在售'], 'aliveRate': life['在售率'],
                    'avgLaunch': dq['平均每档新上'], 'stores': shop['在营门店'], 'cities': shop['城市数'],
                    'stdShare': shop['标准店占比'], 'offTotal': dq['累计下架'], 'changes': chg['调价SKU数'],
                },
                'periods': periodRows,
                'structure': {
                    'total': {'ala': st['ALA'], 'set': st['套餐'], 'share': st['套餐占比']},
                    'front': {'range': st['前段']['档期'], 'ala': st['前段']['ALA'], 'set': st['前段']['套餐'], 'share': st['前段']['套餐占比']},
                    'back': {'range': st['后段']['档期'], 'ala': st['后段']['ALA'], 'set': st['后段']['套餐'], 'share': st['后段']['套餐占比']},
                },
                'life': {
                    'dist': lifeRows, 'sku': life['SKU总数'], 'alive': life['最新档期在售'],
                    'dead': life['已下市'], 'rate': life['在售率'], 'byCat': catRows,
                },
                'price': {'cats': priceCats, 'high': priceHigh, 'low': priceLow, 'changes': priceChanges},
                'stores': {
                    'total': shop['在营门店'], 'citiesCount': shop['城市数'], 'stdShare': shop['标准店占比'],
                    'top5Share': shop['Top5集中度'], 'types': types, 'cities': cities, 'modes': modes,
                },
                'launchAll': launchAll,
                'skuLife': skuLife,
                'cityDetail': cityDetail,
                'launchRecent': recent,
                'advice': advice,
            }
        },
    }


def main():
    data = build()
    block = '//@YTD_START\nconst BRAND_YTD = ' + json.dumps(data, ensure_ascii=False) + ';\n//@YTD_END'
    html = open(HTML, encoding='utf-8').read()
    marker = re.compile(r'//@YTD_START.*?//@YTD_END', re.S)
    if not marker.search(html):
        print('❌ 未找到 //@YTD_START/END 标记')
        raise SystemExit(1)
    open(HTML, 'w', encoding='utf-8').write(marker.sub(lambda m: block, html, count=1))
    b = data['brands'][BRAND]
    print(f"✅ 已写入 {HTML}")
    print(f"   档期 {b['kpi']['periods']} · SKU {b['kpi']['sku']} · 新增 {b['kpi']['launch']} · 在售 {b['kpi']['alive']}")


if __name__ == '__main__':
    main()