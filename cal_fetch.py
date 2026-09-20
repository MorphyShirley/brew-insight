#!/usr/bin/env python3
"""
饮力情报局 · 营销节点日历数据抓取（数据源：adguider.com/calendar）
按月份调用 AdGuider 营销热点日历 API，把农历/公历等节点归一为公历日期，
固化写入 coffee.html 的 MARKET_CAL 常量（与全站“数据内嵌”架构一致）。

用法:
  python3 cal_fetch.py          # 抓取并写回 coffee.html
  python3 cal_fetch.py --dry-run  # 只打印将写入的月份与条目数
"""
import calendar
import datetime
import json
import re
import sys
import urllib.request

API = 'https://www.adguider.com/sv1/calendar/getCalendarAjax'
FD_LIST = [13, 4, 3, 10, 5, 6, 7, 8, 9, 11]  # 节气/公历/农历/纪念日/国际节日/颁奖/影视/重要事件/展会/品牌日
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
GRAY_HISTORY = ('纪念日', '影视上映', '颁奖典礼', '重要事件')

# 默认展示分类（营销高相关，取数据源真实分类名）→ 前端可自行切换
DEFAULT_CATS = ['国际节日', '品牌日', '公历', '农历', '展会活动', '重要事件']
CAT_COLORS = {
    '节气': '#16a34a', '公历节日': '#2563eb', '农历节日': '#7c3aed', '国际节日': '#f59e0b',
    '纪念日': '#64748b', '品牌日': '#f97316', '展会活动': '#14b8a6', '影视上映': '#ec4899',
    '颁奖典礼': '#f43f5e', '重要事件': '#57534e',
}


def fetch_month(year, month):
    """抓取指定月份节点，返回 [{d, t, c, u}]（已归一为公历日）"""
    start = f'{year:04d}-{month:02d}-01'
    end = f'{year:04d}-{month:02d}-{calendar.monthrange(year, month)[1]:02d}'
    payload = json.dumps({'startTime': start, 'endTime': end, 'fdIdList': FD_LIST}).encode()
    req = urllib.request.Request(API, data=payload, headers={
        'Content-Type': 'application/json', 'User-Agent': UA,
        'Referer': 'https://www.adguider.com/calendar',
    })
    with urllib.request.urlopen(req, timeout=45) as resp:
        data = json.loads(resp.read().decode())
    out = []
    for ft in data.get('data', []):
        cname = ft.get('ftName', '')
        for it in ft.get('adFestivalFixedVos') or []:
            dd = resolve_day(it, year, month)
            if not dd:
                continue
            if ft.get('ftName') == '节气' and not cname:
                continue
            out.append({'d': dd, 't': it.get('ffName', ''), 'c': cname, 'u': it.get('ffUrl') or ''})
    return out


def resolve_day(item, year, month):
    """把节点日期归一到公历日；不在本月则返回 None"""
    fm = (item.get('ffTimeForMat') or '').strip()
    m = re.match(r'^(\d{1,2})-(\d{1,2})$', fm)
    if not m:
        return None
    mm, dd = int(m.group(1)), int(m.group(2))
    typ = item.get('ffTimeType')
    if typ == 2:  # 农历 → 公历
        try:
            import lunardate
        except ImportError:
            return None
        try:
            sol = lunardate.LunarDate(year, mm, dd).to_solar_date()
        except Exception:
            return None
        return sol.day if sol.month == month else None
    # 公历固定日期
    return dd if mm == month else None


def year_range():
    now = datetime.date.today()
    start = datetime.date(now.year, now.month, 1) - datetime.timedelta(days=32)  # 回退约1个月
    months = []
    for i in range(12):
        y, m = (start.year, start.month)
        months.append((y, m))
        start = start.replace(day=28) + datetime.timedelta(days=7)
    return months


def build_market_cal():
    cal = {}
    for y, m in year_range():
        key = f'{y:04d}-{m:02d}'
        items = fetch_month(y, m)
        cal[key] = items
        print(f'  {key}: {len(items)} 条')
    return cal


def main():
    dry = '--dry-run' in sys.argv
    html_path = 'coffee.html'
    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()
    if 'const MARKET_CAL' not in html:
        print('❌ coffee.html 未找到 MARKET_CAL 占位符，请先加入 JS 代码')
        sys.exit(1)

    print('⏳ 拉取数据源 adguider...')
    cal = build_market_cal()
    total = sum(len(v) for v in cal.values())
    print(f'✅ 共 {len(cal)} 个月，{total} 条节点')

    if dry:
        return

    meta = {
        'start': min(cal), 'end': max(cal),
        'updated': datetime.date.today().isoformat(),
        'source': 'adguider.com/calendar',
        'default_cats': DEFAULT_CATS,
        'colors': CAT_COLORS,
    }
    block = 'const MARKET_CAL = ' + json.dumps(cal, ensure_ascii=False) + ';\n'
    block += 'const MARKET_CAL_META = ' + json.dumps(meta, ensure_ascii=False) + ';\n'
    marker = re.compile(r'//@MARKET_CAL_START.*?//@MARKET_CAL_END', re.DOTALL)
    if not marker.search(html):
        print('❌ 未找到 //@MARKET_CAL_START/END 标记')
        sys.exit(1)
    new_html = marker.sub('//@MARKET_CAL_START\n' + block + '//@MARKET_CAL_END', html, count=1)
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(new_html)
    print(f'✅ 已写入 {html_path}（{len(new_html)} 字节）')


if __name__ == '__main__':
    main()