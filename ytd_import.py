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
        f"上新节奏：双周档期制、平均每档新上 {dq['平均每档新上']} 个，建议保持「双周小档 + 月度大档」，大档集中 20+ SKU（参考 {'、'.join(x['档期'] for x in dq['上新最多档期'][1:])}）",
        f"结构漂移：套餐占新上比重由前段 {st['前段']['套餐占比']*100:.0f}% 升至后段 {st['后段']['套餐占比']*100:.0f}%，建议继续用「咖啡+贝果/暖食」套餐拉客单，但保留约 40% ALA 满足尝鲜与复购",
        f"生命周期：短期(3–8档) {life['分布']['短期(3-8)']} 款、闪现(1–2档) {life['分布']['闪现(1-2)']} 款，合计占 {(life['分布']['短期(3-8)']+life['分布']['闪现(1-2)'])/life['SKU总数']*100:.0f}%；建议建立「爆款池」(活过9档) 并给潜力款二次档期",
        f"价盘机会：咖啡 D5 中位 {stats['价格带']['咖啡']['中位']:.0f} 元、区间 {stats['价格带']['咖啡']['最低']:.0f}–{stats['价格带']['咖啡']['最高']:.0f}；烘焙小食 {stats['价格带']['烘焙小食']['最低']:.0f}–{stats['价格带']['烘焙小食']['最高']:.0f}，建议补 20–25 元咖啡带与 12–18 元小食组合",
        f"品类侧重：非咖饮品在售率 {cat['非咖饮品']['在售率']*100:.0f}% 最高、咖啡 {cat['咖啡']['在售率']*100:.0f}%、烘焙 {cat['烘焙小食']['在售率']*100:.0f}%——烘焙汰换最快，聚焦 3–5 个核心贝果/可颂打成功率",
    ]
    supply = [
        f"档期备货：按 27 个档期提前 2 周备料；大档（{'、'.join(x['档期'] for x in dq['上新最多档期'][1:])}）提前 3 周锁定原料与包装",
        f"常备库存：全程在售 {life['分布']['全程在售(27)']} 款 + 长销 {life['分布']['长销(18-26)']} 款 = {life['分布']['全程在售(27)']+life['分布']['长销(18-26)']} 款设为常备；新品首批按常规量 ≤30% 试产",
        f"汰换预警：下架累计 {dq['累计下架']} 次；对连续 2 档零动销 SKU 停补货，短期/闪现款做小批量、快清库",
        f"价格版本：D2 比 D5 平均高 {sum(r['D2减D5'] for r in price['类目价盘'] if r['类目']!='加料')/4:.1f} 元（5–8%），打包费 1.3–2.7 元；成本核算按 D5、渠道结算按 D2，避免毛利误判",
        f"门店差异：标准店 {shop['标准店占比']*100:.0f}%，其余 GO/Express/中石化/交通枢纽；GO 店少鲜萃、Express 精简 SKU，需分店型备货",
        f"城市集中：Top5 城市占 {shop['Top5集中度']*100:.0f}%，优先保障上海/北京/杭州/深圳/南京的冷链与小食周转",
    ]
    risk = [
        'YTD 价格为线上原价（D5/D2），非到手价，不可与横向快照的到手价直接比较',
        '163 个套餐中 129 个为区间价（组合上下限），不可当作单一价格比较',
        '仅覆盖标准店价盘（80.8%），全国性定价结论需注明口径',
        '上新存活率存在生存偏差：越早的档期经历的下架窗口越多',
    ]

    strategy = [
        'P0 私域价差：小程序折扣 7.71 折、有折扣 SKU 仅 29%，浅于外送 6.22 折；建议核心 20 个 SKU（拿铁/鲜萃/贝果）上线会员专享价，到手再降 2–3 元，覆盖率提至 50%+',
        'P0 外送常驻爆款：鲜萃黑咖月售 1000/800（到手 13.5 元）验证价格带，建议把 13.5 元鲜萃/拿铁做成常驻价或长期秒杀位，稳定外送流量',
        'P1 套餐标准化：套餐占比 27% 居咖啡阵营前列，但组合散落；建议固化「咖啡+贝果/小食」15/20/25 元三档常驻套餐，进外送首屏与会员专区',
        'P1 中端双锚：外送单品到手均价 16.9 元，两头受挤；建议 12–15 元守量、20 元+ 用贝果与季节限定拉客单',
        'P2 周边/联名空白：周边 SKU 为 0，竞品已用联名盲盒/礼盒做溢价；建议先小程序限定发售测款，跑通后进外送满赠',
    ]
    advice = {'rnd': rnd, 'supply': supply, 'risk': risk, 'strategy': strategy}

    return {
        'config': {'brands': [BRAND], 'active': BRAND},
        'brands': {
            BRAND: {
                'meta': {
                    'label': meta.get('label'), 'channel': meta.get('channel'),
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