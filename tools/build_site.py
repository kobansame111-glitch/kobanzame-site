# -*- coding: utf-8 -*-
"""小判鮫 公式サイト 生成スクリプト v2（2026-10-04 改訂：見た目を作り直し・離脱防止の仕組みを追加）
GitHub Actions が data/products.json か このファイルの変更時（mainブランチ）に実行する。

v2で増えたこと
- 見た目：白地×黒の太字・写真グリッド・角は四角（ドクターマーチン公式サイトの売り場のつくり方を参考）
- 公開の流れ（A案）：products.json の "release" が "draft" の商品は「下書き」＝ページは作るが検索に出さず一覧にも出さない。
  水曜朝のGASが "draft" → "live" に書き換えると、一覧に並ぶ（"release" が無い商品は従来どおり published で判断）
- 売れた商品（status=sold）は一覧から消さずSOLD表示で残す（「売れた一点ものも見る」で表示）
- サイズで探す（身幅±3cm）／店頭で見たい・取り置き（2日間）／こちらも一点もの
- 価格表示：ADD_TAX=True にすると「Square登録価格（税抜）×1.1」を税込として表示する。
  ※Squareのオンライン決済にも消費税がかかる設定にしてから True にすること（表示と請求額をそろえるため）
- アクセス解析：CF_BEACON_TOKEN に Cloudflare Web Analytics のトークンを入れると全ページに計測タグが入る
"""
import json, os, html, re, math, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo のルート（tools/ の1つ上）
BASE = 'https://kobanzame-site.pages.dev'   # 独自ドメイン取得後はここだけ差し替える
TODAY = os.environ.get('SITE_TODAY') or datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y-%m-%d')

ADD_TAX = False          # Squareのオンライン決済に消費税がかかる設定にしたら True（龍さん決定A・2026-10-04）
TAX_RATE = 0.10
CF_BEACON_TOKEN = ''     # Cloudflare Web Analytics のトークン（空なら計測タグを入れない）
HOLD_DAYS = 2            # 店頭取り置きの日数（2026-10-04 決定）
NEW_ARRIVAL_DAY = '水曜'  # 新着の曜日（2026-10-04 決定）

SHOP = {
    'name': '古着屋 小判鮫 KOBANZAME',
    'company': '株式会社プラグ',
    'postal': '350-0062',
    'region': '埼玉県',
    'locality': '川越市',
    'street': '元町1-14-5',
    'hours': '12:00–20:00・月曜・火曜定休',
    'email': 'kobansame111@gmail.com',
    'kobutsu': '埼玉県公安委員会 第431080060786号',
    'instagram': 'https://www.instagram.com/remora__used372/',
    'mercari': 'https://jp.mercari.com/shops/profile/mCEGcCeE7gengRWWZYg9zV',
    'gmaps': 'https://www.google.com/maps/search/%E5%8F%A4%E7%9D%80%E5%B1%8B+%E5%B0%8F%E5%88%A4%E9%AE%AB+%E5%B7%9D%E8%B6%8A',
}
ADDR = f"〒{SHOP['postal']} {SHOP['region']}{SHOP['locality']}{SHOP['street']}"

products = json.load(open(os.path.join(ROOT, 'data/products.json'), encoding='utf-8'))

def esc(s):
    return html.escape(str(s))

def site_price(p):
    base = int(p['prices']['site'])
    return math.floor(base * (1 + TAX_RATE)) if ADD_TAX else base

def yen(n):
    return f'{n:,}円'

def release(p):
    """live / draft / hidden を返す。release が無い商品は published で判断（v1互換）"""
    r = p.get('release')
    if r in ('live', 'draft'):
        return r if p.get('published', True) else 'hidden'
    return 'live' if p.get('published') else 'hidden'

def is_sold(p):
    return p.get('status') == 'sold'

def cat_of(p):
    c = p.get('category', '')
    if 'アクセサリー' in c:
        return 'acc'
    if 'アウター' in c or 'ジャケット' in c or 'コート' in c:
        return 'outer'
    if 'トップス' in c or 'シャツ' in c or 'ニット' in c or 'スウェット' in c:
        return 'tops'
    if 'パンツ' in c or 'ボトムス' in c or 'スカート' in c or 'ワンピース' in c:
        return 'bottoms'
    if '靴' in c or 'シューズ' in c or 'ブーツ' in c:
        return 'shoes'
    return 'other'

CAT_LABEL = {'outer': ('アウター', 'Outer'), 'tops': ('トップス', 'Tops'), 'bottoms': ('ボトムス・ワンピース', 'Bottoms'),
             'shoes': ('靴', 'Shoes'), 'acc': ('アクセサリー・GAW', 'Accessories'), 'other': ('小物・雑貨', 'Goods')}

def body_width(p):
    for k, v in p.get('spec', []):
        if k == 'サイズ':
            m = re.search(r'身幅\s*([\d.]+)', v)
            if m:
                return float(m.group(1))
    return None

def cond_rank(p):
    for k, v in p.get('spec', []):
        if k == '状態':
            if re.match(r'^[ABC]：', v):
                return '状態 ' + v[0]
            if '新品' in v or 'デッドストック' in v:
                return '新品・未使用'
            return 'ヴィンテージ（経年あり）'
    return ''

def thumb_of(p):
    return p.get('thumb') or p['images'][0].replace('/large/', '/medium/')

CSS = r'''
:root{--ink:#141312;--paper:#ffffff;--mount:#efeeeb;--rule:#d9d6d0;--muted:#58554f;--brass:#c99a2e;--sale:#b3261e;
--display:"Archivo","Zen Kaku Gothic New",system-ui,sans-serif;--jp:"Zen Kaku Gothic New","Hiragino Sans","Yu Gothic",system-ui,sans-serif;--gutter:16px;color-scheme:light}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--paper);color:var(--ink);font-family:var(--jp);font-size:15px;line-height:1.75;-webkit-font-smoothing:antialiased}
img{display:block;max-width:100%}a{color:inherit}button{font:inherit;color:inherit;background:none;border:0;cursor:pointer}
:focus-visible{outline:3px solid var(--brass);outline-offset:2px}
.wrap{max-width:1280px;margin:0 auto;padding-inline:var(--gutter)}
.stitch{height:0;border-top:2px dashed var(--brass)}
.util{background:var(--ink);color:var(--paper);font-size:12px;letter-spacing:.06em;text-align:center;padding:8px var(--gutter)}
header.site{position:sticky;top:0;z-index:20;background:var(--paper);border-bottom:1px solid var(--rule)}
header.site .wrap{display:flex;align-items:center;justify-content:space-between;gap:16px;min-height:60px}
.logo{display:flex;align-items:baseline;gap:10px;text-decoration:none}
.logo b{font-weight:900;font-size:20px;letter-spacing:.08em}
.logo span{font-family:var(--display);font-stretch:62%;font-weight:800;font-size:13px;letter-spacing:.18em}
nav.cats{display:flex;gap:20px}
nav.cats a{font-size:13px;font-weight:700;letter-spacing:.06em;padding:6px 0;border-bottom:2px solid transparent;text-decoration:none;white-space:nowrap}
nav.cats a:hover{border-bottom-color:var(--ink)}
@media(max-width:720px){.logo span{display:none}nav.cats{gap:14px;overflow-x:auto;scrollbar-width:none}nav.cats a{font-size:12px}}
.hero{background:var(--ink);color:var(--paper);overflow:hidden}
.hero .wrap{display:grid;grid-template-columns:minmax(0,1fr)}
.hero-img{width:100%;aspect-ratio:4/3;object-fit:cover;object-position:center 30%}
.hero-copy{padding:28px 0 32px}
.hero h1{font-family:var(--display);font-stretch:62%;font-weight:900;font-size:clamp(56px,13vw,132px);line-height:.86;text-transform:uppercase}
.hero h1 em{font-style:normal;color:var(--brass)}
.hero p{font-size:16px;font-weight:500;margin-top:14px;max-width:30em}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:10px;min-height:52px;padding:0 28px;font-weight:700;letter-spacing:.08em;text-decoration:none;border:2px solid currentColor;text-align:center}
.btn.solid{background:var(--paper);color:var(--ink);border-color:var(--paper)}
.btn.dark{background:var(--ink);color:var(--paper);border-color:var(--ink);width:100%}
.btn.line{background:var(--paper);color:var(--ink);border-color:var(--ink);width:100%}
.hero .btn{margin-top:22px}
@media(min-width:900px){.hero .wrap{grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);align-items:end;gap:48px}.hero-img{aspect-ratio:4/5;height:620px}.hero-copy{padding:0 0 48px}}
.catrow{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:8px;margin-top:32px}
.catrow button{border:2px solid var(--ink);min-height:64px;font-weight:900;font-size:14px;display:flex;flex-direction:column;align-items:center;justify-content:center;line-height:1.3;padding:6px}
.catrow button small{font-family:var(--display);font-stretch:68%;font-weight:700;font-size:12px;letter-spacing:.14em;color:var(--muted)}
.catrow button[aria-pressed="true"]{background:var(--ink);color:var(--paper)}
.catrow button[aria-pressed="true"] small{color:var(--brass)}
.sec-head{display:flex;align-items:baseline;justify-content:space-between;gap:12px;margin:40px 0 16px}
.sec-head h2,.store h2,.related h2{font-family:var(--display);font-stretch:62%;font-weight:900;font-size:40px;line-height:1;text-transform:uppercase}
.sec-head h2 small,.related h2 small{display:block;font-family:var(--jp);font-weight:700;font-size:14px;margin-top:6px;text-transform:none}
.sec-head .count{font-size:13px;color:var(--muted);font-variant-numeric:tabular-nums}
.finder{display:flex;flex-wrap:wrap;align-items:center;gap:10px 16px;margin-bottom:20px;padding:14px 0;border-block:1px solid var(--rule)}
.finder label{font-size:13px;font-weight:700}
.finder input[type=number]{width:5.5em;height:40px;border:2px solid var(--ink);border-radius:0;padding:0 8px;font:inherit;font-weight:700}
.finder .hint{font-size:12px;color:var(--muted);flex-basis:100%}
.finder .chk{display:flex;align-items:center;gap:6px;font-weight:500}
.finder button.clear{font-size:12px;text-decoration:underline}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px 10px}
@media(min-width:900px){.grid{grid-template-columns:repeat(3,minmax(0,1fr));gap:36px 16px}}
.card{display:flex;flex-direction:column;gap:8px;min-width:0;text-decoration:none}
.card .ph{position:relative;background:var(--mount);aspect-ratio:4/5;overflow:hidden}
.card .ph img{width:100%;height:100%;object-fit:cover;transition:transform .4s ease}
.card:hover .ph img{transform:scale(1.03)}
.tag{position:absolute;left:0;top:10px;background:var(--ink);color:var(--paper);font-size:11px;font-weight:700;letter-spacing:.08em;padding:3px 8px}
.card .brand{font-family:var(--display);font-stretch:68%;font-weight:800;font-size:13px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}
.card .nm{font-weight:700;font-size:14px;line-height:1.5;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.card .pr{font-weight:900;font-size:16px;font-variant-numeric:tabular-nums}
.card .pr small{font-weight:500;font-size:11px;color:var(--muted);margin-left:4px}
.card .fit{font-size:12px;font-weight:700;background:var(--mount);padding:2px 6px;align-self:flex-start}
.card.sold .ph:after{content:"SOLD";position:absolute;inset:0;display:grid;place-items:center;background:rgba(255,255,255,.55);font-family:var(--display);font-stretch:62%;font-weight:900;font-size:40px;color:var(--sale)}
.empty{grid-column:1/-1;border:2px dashed var(--rule);padding:28px 16px;text-align:center;color:var(--muted);font-size:14px}
.trust{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1px;background:var(--rule);border-block:1px solid var(--rule);margin-top:56px}
@media(min-width:900px){.trust{grid-template-columns:repeat(4,minmax(0,1fr))}}
.trust div{background:var(--paper);padding:20px 16px;min-width:0}
.trust b{display:block;font-weight:900;font-size:15px}
.trust span{font-size:13px;color:var(--muted)}
.trust a{font-weight:700;color:var(--ink)}
.store{display:grid;grid-template-columns:minmax(0,1fr);gap:24px;padding-block:48px}
@media(min-width:900px){.store{grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:56px}}
.store p{margin-top:12px;max-width:34em}
.store dl,.lawtable dl{display:grid;grid-template-columns:7em minmax(0,1fr);gap:10px 12px;border-top:2px solid var(--ink);padding-top:16px;font-size:14px}
.store dt,.lawtable dt{font-weight:700}
.faq{padding-block:8px 48px;max-width:860px}
.faq details{border-bottom:1px solid var(--rule)}
details summary{list-style:none;cursor:pointer;display:flex;justify-content:space-between;align-items:center;gap:12px;padding:16px 0;font-weight:900;font-size:15px}
details summary::-webkit-details-marker{display:none}
details summary:after{content:"+";font-family:var(--display);font-size:22px;line-height:1}
details[open] summary:after{content:"−"}
.faq details p{padding-bottom:16px;font-size:14px}
footer.site{background:var(--ink);color:var(--paper);padding-block:36px;font-size:12px;line-height:1.9}
footer.site .wrap{display:grid;gap:14px}
footer.site .big{font-family:var(--display);font-stretch:62%;font-weight:900;font-size:56px;line-height:.9}
footer.site a{color:var(--paper)}
.crumb{font-size:12px;color:var(--muted);padding-block:14px;display:flex;gap:6px;flex-wrap:wrap}
.pdp{display:grid;grid-template-columns:minmax(0,1fr);gap:24px;padding-bottom:40px}
@media(min-width:900px){.pdp{grid-template-columns:minmax(0,1.4fr) minmax(0,1fr);gap:48px}}
.gal{display:flex;gap:8px;overflow-x:auto;scroll-snap-type:x mandatory;margin-inline:calc(var(--gutter)*-1);padding-inline:var(--gutter);scrollbar-width:none}
.gal::-webkit-scrollbar{display:none}
.gal img{flex:0 0 86%;aspect-ratio:4/5;object-fit:cover;background:var(--mount);scroll-snap-align:center}
.gal.one img{flex-basis:100%}
.galcount{font-size:12px;color:var(--muted);margin-top:8px;font-variant-numeric:tabular-nums}
@media(min-width:900px){.gal{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));overflow:visible;margin:0;padding:0}.gal img{width:100%}.gal.one{grid-template-columns:minmax(0,1fr)}.galcount{display:none}}
.info{min-width:0}
@media(min-width:900px){.info{position:sticky;top:84px;align-self:start}}
.info .brand{font-family:var(--display);font-stretch:68%;font-weight:800;font-size:15px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}
.info h1{font-weight:900;font-size:22px;line-height:1.45;margin-top:4px;text-wrap:balance}
.info .ttl{font-size:14px;color:var(--muted);margin-top:4px}
.info .sku{font-family:var(--display);font-stretch:75%;font-weight:600;font-size:12px;letter-spacing:.14em;color:var(--muted);margin-top:4px}
.info .price{font-weight:900;font-size:28px;margin-top:14px;font-variant-numeric:tabular-nums}
.info .price small{font-size:12px;font-weight:500;color:var(--muted);margin-left:6px}
.facts{display:flex;flex-wrap:wrap;gap:6px;margin-top:14px}
.facts span{border:1px solid var(--ink);font-size:12px;font-weight:700;padding:4px 10px}
.facts span.one{background:var(--ink);color:var(--paper)}
.facts span.soldf{background:var(--sale);border-color:var(--sale);color:var(--paper)}
.buybox{margin-top:18px;display:grid;gap:10px}
.soldout{display:block;border:2px solid var(--sale);color:var(--sale);font-weight:900;text-align:center;padding:14px}
.ship{font-size:13px;color:var(--muted);line-height:1.7}
.ship b{color:var(--ink)}
.holdbox{border:2px solid var(--ink);padding:14px;font-size:14px;display:grid;gap:8px}
.holdbox code{font-family:var(--jp);font-weight:700;background:var(--mount);padding:2px 6px;user-select:all}
.points{margin-top:20px;border-top:2px solid var(--ink)}
.points li{list-style:none;padding:10px 0 10px 18px;border-bottom:1px solid var(--rule);position:relative;font-size:14px}
.points li:before{content:"";position:absolute;left:0;top:19px;width:8px;height:0;border-top:2px dashed var(--brass)}
.info details{border-bottom:1px solid var(--rule)}
.story{padding-bottom:16px;font-size:15px}
.story h2{font-size:14px;font-weight:900;margin:16px 0 4px}
.story h2:first-child{margin-top:0}
.spec{display:grid;grid-template-columns:6em minmax(0,1fr);gap:8px 12px;font-size:14px;padding-bottom:12px}
.spec dt{color:var(--muted)}
.howto{font-size:13px;color:var(--muted);padding-bottom:16px}
.byline{font-size:12px;color:var(--muted);padding-block:14px}
.related{border-top:2px solid var(--ink);padding-block:32px 140px}
@media(min-width:900px){.related{padding-bottom:64px}}
.related h2{font-size:36px;margin-bottom:16px}
@media(max-width:600px){.related .grid>:nth-child(3){display:none}}
.bar{position:fixed;left:0;right:0;bottom:0;z-index:30;background:var(--paper);border-top:2px solid var(--ink);padding:10px var(--gutter) calc(10px + env(safe-area-inset-bottom,0px));display:flex;align-items:center;gap:12px}
.bar b{font-size:19px;font-weight:900;white-space:nowrap;font-variant-numeric:tabular-nums}
.bar .btn{min-height:48px;flex:1}
@media(min-width:900px){.bar{display:none!important}}
.draftnote{background:var(--brass);color:var(--ink);font-size:13px;font-weight:700;text-align:center;padding:8px var(--gutter)}
.page{padding-block:32px 64px;max-width:860px}
.page h1{font-weight:900;font-size:26px;margin-bottom:16px}
.page h2{font-weight:900;font-size:16px;margin:22px 0 6px}
.nf{padding-block:64px;text-align:center}
.nf h1{font-family:var(--display);font-stretch:62%;font-weight:900;font-size:72px;line-height:.9;text-transform:uppercase}
.nf p{margin:16px auto 24px;max-width:28em}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
'''

def head(title, desc, path, og_type='website', image=None, extra_ld=None, noindex=False):
    url = BASE + path
    img = image or 'https://assets.mercari-shops-static.com/-/large/plain/2JX8ZaipBiPKYk5f7ApJKD.jpg'
    ld = extra_ld if extra_ld is not None else {'@context': 'https://schema.org', '@graph': [org_node()]}
    beacon = (f'<script defer src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon=\'{{"token": "{CF_BEACON_TOKEN}"}}\'></script>'
              if CF_BEACON_TOKEN else '')
    return f'''<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
{'<meta name="robots" content="noindex">' if noindex else ''}
<meta property="og:type" content="{og_type}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{img}">
<meta property="og:site_name" content="{SHOP['name']}">
<meta property="og:locale" content="ja_JP">
<meta name="twitter:card" content="summary_large_image">
<link rel="canonical" href="{url}">
<link rel="alternate" type="text/plain" title="llms.txt" href="/llms.txt">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,400..900&family=Zen+Kaku+Gothic+New:wght@400;500;700;900&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/site.css">
{jld(ld)}
{beacon}
</head>
<body>
<div class="util"><b>毎週{NEW_ARRIVAL_DAY} 新着入荷</b>　送料込み・決済確認後3日以内に発送（月・火定休を除く）</div>
<header class="site"><div class="wrap">
  <a class="logo" href="/"><b>小判鮫</b><span>KOBANZAME · KAWAGOE</span></a>
  <nav class="cats" aria-label="サイト内">
    <a href="/#list">商品一覧</a><a href="/#store">店舗</a><a href="/#faq">Q&amp;A</a>
  </nav>
</div></header>
'''

def jld(obj):
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False, separators=(',', ':')) + '</script>'

def org_node():
    return {
        '@type': 'ClothingStore', '@id': BASE + '/#store',
        'name': SHOP['name'], 'alternateName': ['小判鮫', 'KOBANZAME', 'こばんざめ'],
        'description': '埼玉県川越市、築約80年の古民家で営業する古着屋。海外のヴィンテージ古着と、小判鮫オリジナルのリメイクアクセサリー「GAW」を扱う。商品はすべて一点もの。',
        'url': BASE + '/', 'email': SHOP['email'],
        'address': {'@type': 'PostalAddress', 'postalCode': SHOP['postal'], 'addressRegion': SHOP['region'],
                    'addressLocality': SHOP['locality'], 'streetAddress': SHOP['street'], 'addressCountry': 'JP'},
        'openingHours': 'We-Su 12:00-20:00',
        'currenciesAccepted': 'JPY',
        'paymentAccepted': 'クレジットカード',
        'parentOrganization': {'@type': 'Organization', 'name': SHOP['company']},
        'sameAs': [SHOP['instagram'], SHOP['mercari']],
    }

FOOT = f'''<footer class="site"><div class="wrap">
  <div class="big">KOBANZAME</div>
  <div class="stitch"></div>
  <div>古着屋 小判鮫／{ADDR}／{SHOP['hours']}<br>
    運営：{SHOP['company']}　・　古物商許可：{SHOP['kobutsu']}<br>
    <a href="{SHOP['instagram']}" rel="noopener">Instagram</a>　・　<a href="{SHOP['mercari']}" rel="noopener">メルカリShops</a>　・　<a href="{SHOP['gmaps']}" rel="noopener">Googleマップ</a><br>
    <a href="/tokushoho/">特定商取引法に基づく表記</a>　・　<a href="/privacy/">プライバシーポリシー</a>
  </div>
</div></footer>
</body>
</html>
'''

def write(path, text):
    full = os.path.join(ROOT, path.lstrip('/'))
    os.makedirs(os.path.dirname(full), exist_ok=True)
    open(full, 'w', encoding='utf-8').write(text)

write('/assets/site.css', CSS.strip() + '\n')

def card_html(p, lazy=True):
    w = body_width(p)
    sold = is_sold(p)
    lz = ' loading="lazy"' if lazy else ''
    tag = '' if sold else '<span class="tag">1点限り</span>'
    wv = w if w is not None else ''
    return (f'<a class="card{" sold" if sold else ""}" href="/journal/{p["slug"]}/" data-cat="{cat_of(p)}" '
            f'data-w="{wv}" data-sold="{1 if sold else 0}">'
            f'<div class="ph"><img src="{esc(thumb_of(p))}" alt="{esc(p["product_name"])}"{lz}>{tag}</div>'
            f'<div class="brand">{esc(p["brand"])}</div><div class="nm">{esc(p["product_name"])}</div>'
            f'<span class="fit" hidden></span>'
            f'<div class="pr">{yen(site_price(p))}<small>税込</small></div></a>')


# ---------- FAQ（事実だけ・AIに引用されやすい一問一答） ----------
FAQ = [
    ('小判鮫はどこにある古着屋ですか？', f'埼玉県川越市元町1-14-5（〒350-0062）にある、築約80年の古民家で営業している古着屋です。運営は{SHOP["company"]}です。'),
    ('営業時間と定休日は？', '12:00〜20:00の営業で、毎週月曜日・火曜日が定休日です。臨時の休みや営業時間の変更はInstagramでお知らせします。'),
    ('どんなものを扱っていますか？', '海外のヴィンテージ古着（メンズ・レディース）と、小判鮫オリジナルのリメイクアクセサリー「GAW」を扱っています。商品はすべて一点ものです。'),
    ('GAWとは何ですか？', '小判鮫オリジナルのリメイクアクセサリーのラインです。古いスプーンなどの素材を、ペンダントやバングルなどの一点ものに作り直しています。'),
    ('通販で買えますか？', 'はい。このサイトのジャーナルに載っている商品は、クレジットカード（Square決済）でそのまま購入できます。メルカリShopsでも販売しています。'),
    ('送料はかかりますか？', 'このサイトで購入した場合、表示価格は税込・送料込みです。'),
    ('いつ届きますか？', 'ご注文（決済）の確認後、3日以内（定休日を除く）に発送します。'),
    ('返品はできますか？', '古着・一点ものの性質上、お客様都合による返品はお受けしていません。商品説明と著しく異なる場合や発送間違いの場合は、到着後4日以内にメールでご連絡ください。'),
]

def faq_ld():
    return {'@type': 'FAQPage', '@id': BASE + '/#faq',
            'mainEntity': [{'@type': 'Question', 'name': q, 'acceptedAnswer': {'@type': 'Answer', 'text': a}} for q, a in FAQ]}



# ---------- 一覧・絞り込みの共通部品 ----------
live = [p for p in products if release(p) == 'live']
avail_live = [p for p in live if not is_sold(p)]
cats_present = [c for c in ['outer', 'tops', 'bottoms', 'shoes', 'acc', 'other'] if any(cat_of(p) == c for p in live)]
catrow = ''.join(f'<button type="button" data-filter="{c}" aria-pressed="false">{CAT_LABEL[c][0]}<small>{CAT_LABEL[c][1]}</small></button>'
                 for c in cats_present)

FINDER = '''<div class="finder">
  <label for="myw">手持ちの服の身幅</label>
  <input type="number" id="myw" inputmode="decimal" min="30" max="90" step="0.5" placeholder="例 55">
  <span>cm ±3cmの服を表示</span>
  <label class="chk"><input type="checkbox" id="showsold"> 売れた一点ものも見る</label>
  <button type="button" class="clear" id="clear">条件をクリア</button>
  <span class="hint">身幅＝脇の下から脇の下までを平らに置いて測った長さ。いちばん気に入っている服で測るのがおすすめです。</span>
</div>'''

LIST_JS = '''<script>
(function(){
  var filter=null, grid=document.getElementById('grid'); if(!grid) return;
  var myw=document.getElementById('myw'), showsold=document.getElementById('showsold'), cnt=document.getElementById('count');
  var empty=document.createElement('div'); empty.className='empty'; empty.hidden=true; grid.appendChild(empty);
  function apply(){
    var my=parseFloat(myw.value), n=0;
    grid.querySelectorAll('.card').forEach(function(c){
      var ok=(!filter||c.dataset.cat===filter)&&(showsold.checked||c.dataset.sold!=='1');
      var w=c.dataset.w===''?null:parseFloat(c.dataset.w), fit=c.querySelector('.fit');
      if(!isNaN(my)){ ok=ok&&w!==null&&Math.abs(w-my)<=3; }
      if(!isNaN(my)&&w!==null){var d=w-my; fit.textContent='身幅'+w+'cm（'+(d===0?'同じ':(d>0?'+':'')+d.toFixed(1)+'cm')+'）'; fit.hidden=false;} else fit.hidden=true;
      c.hidden=!ok; if(ok) n++;
    });
    empty.hidden=n>0;
    empty.textContent=!isNaN(my)?('身幅'+my+'cm前後の服は、いまはありません。毎週'+(window.KBZ_DAY||'水曜')+'に新着が入ります。'):'条件に合う一点ものは、いまはありません。';
    if(cnt) cnt.textContent=n+'点';
    document.querySelectorAll('.catrow button').forEach(function(b){b.setAttribute('aria-pressed',String(b.dataset.filter===filter));});
  }
  document.querySelectorAll('.catrow button').forEach(function(b){b.addEventListener('click',function(){filter=(filter===b.dataset.filter?null:b.dataset.filter);apply();});});
  myw.addEventListener('input',apply); showsold.addEventListener('change',apply);
  document.getElementById('clear').addEventListener('click',function(){myw.value='';showsold.checked=false;filter=null;apply();});
  apply();
})();
</script>'''

all_cards = '\n'.join(card_html(p) for p in live)
day_js = f'<script>window.KBZ_DAY="{NEW_ARRIVAL_DAY}";</script>'

# ---------- トップ ----------
top_ld = {'@context': 'https://schema.org', '@graph': [org_node(), faq_ld(),
          {'@type': 'WebSite', '@id': BASE + '/#website', 'url': BASE + '/', 'name': SHOP['name'], 'inLanguage': 'ja',
           'publisher': {'@id': BASE + '/#store'}}]}
faq_html = '\n'.join(f'    <details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>' for q, a in FAQ)
hero_p = next((p for p in avail_live if cat_of(p) == 'outer'), avail_live[0] if avail_live else (live[0] if live else None))
hero_img = hero_p['images'][0] if hero_p else 'https://assets.mercari-shops-static.com/-/large/plain/2JX8ZaipBiPKYk5f7ApJKD.jpg'
hero_alt = hero_p['product_name'] if hero_p else '小判鮫の一点もの'

top = head('古着屋 小判鮫 KOBANZAME｜埼玉・川越の古民家ヴィンテージ古着店',
           '埼玉県川越市元町、築約80年の古民家で営業する古着屋 小判鮫（KOBANZAME）。海外のヴィンテージ古着と、オリジナルのリメイクアクセサリー「GAW」。すべて一点もの。サイトからクレジットカードで購入できます（送料込み）。',
           '/', extra_ld=top_ld) + f'''
<main>
  <section class="hero">
    <div class="wrap">
      <img class="hero-img" src="{esc(hero_img)}" alt="{esc(hero_alt)}" fetchpriority="high">
      <div class="hero-copy">
        <h1>One<br>of <em>One.</em></h1>
        <p>埼玉・川越、築約80年の古民家から。海外のヴィンテージ古着と、オリジナルの「GAW」。どれも一点もので、同じものはありません。</p>
        <a class="btn solid" href="#list">一点ものを見る</a>
      </div>
    </div>
  </section>

  <div class="wrap">
    <div class="catrow" role="group" aria-label="カテゴリで絞り込む">{catrow}</div>
    <div class="sec-head" id="list">
      <h2>In Stock<small>オンラインで買える一点もの（毎週{NEW_ARRIVAL_DAY}更新）</small></h2>
      <span class="count" id="count">{len(avail_live)}点</span>
    </div>
    {FINDER}
    <div class="grid" id="grid">
{all_cards}
    </div>
  </div>

  <div class="wrap"><div class="trust">
    <div><b>送料込み</b><span>表示価格は税込・送料込み</span></div>
    <div><b>3日以内に発送</b><span>決済確認後（月・火定休を除く）</span></div>
    <div><b>川越の実店舗</b><span>古物商許可 {SHOP['kobutsu']}</span></div>
    <div><b>お店の評判</b><span><a href="{SHOP['gmaps']}" rel="noopener">Googleマップでクチコミを見る</a></span></div>
  </div></div>

  <div class="wrap">
    <section class="store" id="store">
      <div>
        <h2>The Shop</h2>
        <p>古着屋 小判鮫（KOBANZAME）は、埼玉県川越市元町にある築約80年の古民家で営業している古着屋です。海外のヴィンテージ古着と、小判鮫オリジナルのリメイクアクセサリー「GAW」を扱っています。ブランドや流行ではなく、素材・質感・その一点にしかない気配で選んでいます。サイトに載っている商品は、店頭にも並んでいます。</p>
      </div>
      <dl>
        <dt>住所</dt><dd>{ADDR}</dd>
        <dt>営業</dt><dd>12:00–20:00</dd>
        <dt>定休日</dt><dd>月曜・火曜</dd>
        <dt>運営</dt><dd>{SHOP['company']}</dd>
        <dt>お問い合わせ</dt><dd>{SHOP['email']}</dd>
      </dl>
    </section>
    <section class="faq" id="faq">
      <div class="sec-head" style="margin-top:0"><h2>Q&amp;A<small>よくある質問</small></h2></div>
{faq_html}
    </section>
  </div>
</main>
{day_js}
{LIST_JS}
''' + FOOT
write('/index.html', top)

# ---------- 商品ページ ----------
GAL_JS = '''<script>
(function(){
  var g=document.getElementById('gal'), c=document.getElementById('galcount'); if(!g||!c) return;
  var n=g.children.length;
  function upd(){var w=g.firstElementChild.getBoundingClientRect().width+8; c.textContent=(Math.round(g.scrollLeft/w)+1)+' / '+n;}
  g.addEventListener('scroll',upd,{passive:true}); upd();
  var hb=document.getElementById('holdbtn'), hx=document.getElementById('holdbox');
  if(hb&&hx){hb.addEventListener('click',function(){hx.hidden=!hx.hidden; hb.setAttribute('aria-expanded',String(!hx.hidden));});}
})();
</script>'''

def related_for(p):
    pool = [x for x in avail_live if x['sku'] != p['sku']]
    pool.sort(key=lambda x: (cat_of(x) != cat_of(p), x.get('published_date', '')), reverse=False)
    return pool[:3]

for p in products:
    rel = release(p)
    if rel == 'hidden':
        continue
    path = f"/journal/{p['slug']}/"
    price = site_price(p)
    sold = is_sold(p)
    avail = 'https://schema.org/SoldOut' if sold else 'https://schema.org/InStock'
    offer = {'@type': 'Offer', 'price': str(price), 'priceCurrency': 'JPY', 'availability': avail,
             'itemCondition': 'https://schema.org/' + p.get('item_condition', 'UsedCondition'), 'url': BASE + path,
             'seller': {'@id': BASE + '/#store'},
             'shippingDetails': {'@type': 'OfferShippingDetails',
                                 'shippingRate': {'@type': 'MonetaryAmount', 'value': '0', 'currency': 'JPY'},
                                 'shippingDestination': {'@type': 'DefinedRegion', 'addressCountry': 'JP'},
                                 'deliveryTime': {'@type': 'ShippingDeliveryTime',
                                                  'handlingTime': {'@type': 'QuantitativeValue', 'minValue': 0, 'maxValue': 3, 'unitCode': 'DAY'},
                                                  'transitTime': {'@type': 'QuantitativeValue', 'minValue': 1, 'maxValue': 3, 'unitCode': 'DAY'}}}}
    author = {'@type': 'Person', 'name': '龍', 'jobTitle': '小判鮫オーナー・専属バイヤー', 'worksFor': {'@id': BASE + '/#store'}}
    ld = {'@context': 'https://schema.org', '@graph': [
        {'@type': 'Product', '@id': BASE + path + '#product', 'name': p['product_name'], 'sku': p['sku'],
         'description': p['summary_text'], 'image': p['images'], 'brand': {'@type': 'Brand', 'name': p['brand']},
         'material': p.get('material', ''), 'category': p.get('category', ''), 'offers': offer},
        {'@type': 'BlogPosting', '@id': BASE + path + '#article', 'headline': p['title'], 'image': p['images'][0],
         'datePublished': p.get('published_date', TODAY), 'dateModified': TODAY, 'inLanguage': 'ja',
         'author': author, 'publisher': {'@id': BASE + '/#store'}, 'about': {'@id': BASE + path + '#product'},
         'mainEntityOfPage': BASE + path},
        {'@type': 'BreadcrumbList', 'itemListElement': [
            {'@type': 'ListItem', 'position': 1, 'name': 'HOME', 'item': BASE + '/'},
            {'@type': 'ListItem', 'position': 2, 'name': CAT_LABEL[cat_of(p)][0], 'item': BASE + '/#list'},
            {'@type': 'ListItem', 'position': 3, 'name': p['product_name'], 'item': BASE + path}]},
        org_node()]}
    imgs = p['images']
    gallery = ''.join('<img src="{}" alt="{} 写真{}"{}>'.format(
        esc(u), esc(p['product_name']), i + 1, ' fetchpriority="high"' if i == 0 else ' loading="lazy"')
        for i, u in enumerate(imgs))
    points = ''.join(f'<li>{esc(s)}</li>' for s in p['summary_points'] if not s.startswith('価格'))
    spec = ''.join(f'<dt>{esc(k)}</dt><dd>{esc(v)}</dd>' for k, v in p['spec'])
    w = body_width(p)
    facts = ('<span class="soldf">SOLD</span>' if sold else '<span class="one">在庫1点</span>')
    rk = cond_rank(p)
    facts += (f'<span>{rk}</span>' if rk else '') + (f'<span>身幅 {w:g}cm</span>' if w is not None else '')
    if sold:
        buy = '<span class="soldout">SOLD OUT（この一点は旅立ちました）</span>'
        bar = ''
    elif p['links'].get('square'):
        buy = f'<a class="btn dark" href="{esc(p["links"]["square"])}" rel="noopener">購入する（クレジットカード）</a>'
        bar = f'<div class="bar"><b>{yen(price)}</b><a class="btn dark" href="{esc(p["links"]["square"])}" rel="noopener">購入する</a></div>'
    else:
        buy = '<span class="soldout">準備中（まもなく購入できるようになります）</span>'
        bar = ''
    hold = '' if sold else f'''<button type="button" class="btn line" id="holdbtn" aria-expanded="false" aria-controls="holdbox">店頭で見たい・取り置きする（{HOLD_DAYS}日間）</button>
          <div class="holdbox" id="holdbox" hidden>
            <p>川越・元町の店頭で{HOLD_DAYS}日間お取り置きします。下の内容をInstagramのDMかメールで送ってください。</p>
            <p><code>取り置き希望／{esc(p['sku'])}／来店予定日：　月　日／お名前：</code></p>
            <p>送り先：<a href="{SHOP['instagram']}" rel="noopener">Instagram（@remora__used372）</a> ／ メール <code>{SHOP['email']}</code></p>
            <p class="ship">店頭やネットで先に売れていた場合は、こちらからご連絡します。</p>
          </div>'''
    draft_banner = '<div class="draftnote">下書き（まだ公開していません）｜毎週' + NEW_ARRIVAL_DAY + 'の朝に公開されます</div>' if rel == 'draft' else ''
    rel_cards = ''.join(card_html(x) for x in related_for(p))
    related = f'''<section class="related"><h2>Also One of One<small>こちらも一点もの</small></h2><div class="grid">{rel_cards}</div></section>''' if rel_cards else ''
    page = head(f"{p['title']}｜{SHOP['name']}（川越）", p['summary_text'], path, og_type='article',
                image=imgs[0], extra_ld=ld, noindex=(p.get('noindex', False) or rel == 'draft')) + f'''{draft_banner}
<main class="wrap">
  <div class="crumb"><a href="/">HOME</a><span>／</span><a href="/#list">{CAT_LABEL[cat_of(p)][0]}</a><span>／</span><span>{esc(p['sku'])}</span></div>
  <div class="pdp">
    <div>
      <div class="gal{' one' if len(imgs) == 1 else ''}" id="gal">{gallery}</div>
      <div class="galcount" id="galcount"></div>
    </div>
    <div class="info">
      <div class="brand">{esc(p['brand'])}</div>
      <h1>{esc(p['product_name'])}</h1>
      <div class="ttl">{esc(p['title'])}</div>
      <div class="sku">ITEM NO. {esc(p['sku'])}</div>
      <div class="price">{yen(price)}<small>税込・送料込み</small></div>
      <div class="facts">{facts}</div>
      <div class="buybox">
        {buy}
        {hold}
        <div class="ship"><b>一点もの・在庫1点。</b>Squareの安全な決済ページへ進みます。店頭・他の販路で先に売れた場合は、ご注文をお受けできないことがあります（その際は全額返金いたします）。<br>決済確認後3日以内に発送（月・火定休を除く）</div>
      </div>
      <ul class="points">{points}</ul>
      <details open><summary>この一着の話</summary><div class="story"><p>{esc(p['lead'])}</p>
{p['body_html']}</div></details>
      <details><summary>仕様・サイズ</summary><dl class="spec">{spec}</dl><p class="howto">実寸は平置きで測っています。身幅＝脇の下から脇の下、着丈＝襟のつけ根から裾まで。お手持ちの服を同じように測って比べると、サイズの失敗が減ります。</p></details>
      <details><summary>配送・返品</summary><div class="story"><p>送料込み。決済確認後3日以内（月・火定休を除く）に、川越の店舗から発送します。古着・一点ものの性質上、お客様都合の返品はお受けしていません。商品説明と著しく異なる場合や発送間違いの場合は、到着後4日以内にメールでご連絡ください。</p></div></details>
      <div class="byline">文：小判鮫オーナー・専属バイヤー 龍</div>
    </div>
  </div>
  {related}
</main>
{bar}
{GAL_JS}
''' + FOOT
    write(path + 'index.html', page)

# ---------- ジャーナル（一覧の別入口・v1のURLを残す） ----------
list_ld = {'@context': 'https://schema.org', '@graph': [org_node(),
           {'@type': 'CollectionPage', 'name': 'ジャーナル｜' + SHOP['name'], 'url': BASE + '/journal/',
            'mainEntity': {'@type': 'ItemList', 'itemListElement': [
                {'@type': 'ListItem', 'position': i + 1, 'url': BASE + f"/journal/{p['slug']}/", 'name': p['product_name']}
                for i, p in enumerate(live)]}}]}
jl = head('ジャーナル｜古着屋 小判鮫 KOBANZAME', '一点ものの古着とGAWアクセサリーの成り立ちの記録。掲載中の商品はクレジットカードで購入できます（送料込み）。',
          '/journal/', extra_ld=list_ld) + f'''
<main class="wrap">
  <div class="crumb"><a href="/">HOME</a><span>／</span><span>JOURNAL</span></div>
  <div class="catrow" role="group" aria-label="カテゴリで絞り込む" style="margin-top:8px">{catrow}</div>
  <div class="sec-head"><h2>Journal<small>一点ものの、成り立ちの記録</small></h2><span class="count" id="count">{len(avail_live)}点</span></div>
  {FINDER}
  <div class="grid" id="grid">
{all_cards}
  </div>
  <div style="height:64px"></div>
</main>
{day_js}
{LIST_JS}
''' + FOOT
write('/journal/index.html', jl)


# ---------- 404 ----------
nf = head('ページが見つかりません｜古着屋 小判鮫 KOBANZAME', 'お探しのページは見つかりませんでした。', '/404.html', noindex=True) + """
<main class="wrap nf">
  <h1>Not Found</h1>
  <p>お探しのページは見つかりませんでした。売れた商品も、ふだんはSOLDとしてページを残しています。</p>
  <a class="btn dark" style="width:auto" href="/#list">オンラインで買える一点もの</a>
</main>

""" + FOOT
write('/404.html', nf)

# ---------- 特定商取引法に基づく表記 ----------
LAW = [
    ('販売業者', SHOP['company']),
    ('運営統括責任者', '嶋崎龍'),
    ('所在地', ADDR),
    ('電話番号', '請求があった場合には遅滞なく開示いたします。'),
    ('メールアドレス', SHOP['email']),
    ('販売価格', '各商品ページに税込価格で表示しています。'),
    ('商品代金以外の必要料金', '送料は販売価格に含まれます（当店負担）。決済手数料はかかりません。'),
    ('支払方法', 'クレジットカード（Square の決済ページで決済）'),
    ('支払時期', 'ご注文時に決済が確定します。'),
    ('引渡時期', 'ご注文（決済）の確認後、3日以内（定休日を除く）に発送します。'),
    ('販売数量', '各商品とも1点限りです。'),
    ('返品・交換', '古着・一点ものの性質上、お客様都合による返品・交換はお受けしておりません。商品説明と著しく異なる場合や当店の発送間違いの場合は、商品到着後4日以内にメールでご連絡ください。返品送料は当店が負担し、返金または交換にて対応いたします。'),
    ('申込みの撤回・解除', '通信販売にはクーリング・オフ制度は適用されません。上記「返品・交換」の条件に従います。'),
    ('品切れの場合', '店頭・他の販路で先に売れた場合は、ご注文をお受けできないことがあります。その際はご連絡のうえ全額返金いたします。'),
    ('古物商許可', f"{SHOP['kobutsu']}（{SHOP['company']}）"),
]
law_html = ''.join(f'<dt>{html.escape(k)}</dt><dd>{html.escape(v)}</dd>' for k, v in LAW)
tk = head('特定商取引法に基づく表記｜古着屋 小判鮫', '古着屋 小判鮫（運営：株式会社プラグ）の特定商取引法に基づく表記。', '/tokushoho/') + f'''
<main class="wrap page lawtable">
  <h1>特定商取引法に基づく表記</h1>
  <dl>{law_html}</dl>
  <p style="color:var(--muted);font-size:13px;margin-top:24px">制定：2026年9月30日</p>
</main>

''' + FOOT
write('/tokushoho/index.html', tk)

# ---------- プライバシーポリシー ----------
pv = head('プライバシーポリシー｜古着屋 小判鮫', '古着屋 小判鮫（運営：株式会社プラグ）のプライバシーポリシー。', '/privacy/') + f'''
<main class="wrap page">
  <h1>プライバシーポリシー</h1>
  <p>古着屋 小判鮫（運営：{SHOP['company']}。以下「当店」）は、お客様の個人情報を適切に取り扱います。</p>
  <h2>取得する情報</h2>
  <p>ご注文・お問い合わせ・販売（外部プラットフォームを含む）に際して、お名前・連絡先・配送先など、取引に必要な範囲の情報を取得します。</p>
  <h2>利用目的</h2>
  <p>商品の発送、お問い合わせへの対応、取引に必要なご連絡のために利用し、目的の範囲を超えて利用しません。</p>
  <h2>決済について</h2>
  <p>本サイトでのお支払いは Square 株式会社の決済ページで処理されます。当店はクレジットカード番号を取得・保存しません。</p>
  <h2>第三者提供</h2>
  <p>法令に基づく場合を除き、ご本人の同意なく第三者に提供しません。配送など取引に必要な範囲で委託先に提供する場合があります。</p>
  <h2>アクセス解析</h2>
  <p>サイトの改善のためアクセス状況を測定することがあります。個人を特定する情報は含みません。</p>
  <h2>お問い合わせ</h2>
  <p>本ポリシーに関するお問い合わせは {SHOP['email']} までお願いいたします。</p>
  <p style="color:var(--muted);font-size:13px;margin-top:20px">制定：2026年9月／改定：2026年9月30日</p>
</main>

''' + FOOT
write('/privacy/index.html', pv)

# ---------- robots.txt / sitemap.xml / llms.txt（AIO/LLMO） ----------
pages = ['/', '/journal/'] + [f"/journal/{p['slug']}/" for p in live] + ['/tokushoho/', '/privacy/']
write('/robots.txt', f'''# 小判鮫 公式サイト：検索エンジン・AI検索のどちらにも公開
User-agent: *
Allow: /

User-agent: GPTBot
Allow: /

User-agent: OAI-SearchBot
Allow: /

User-agent: ClaudeBot
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: Google-Extended
Allow: /

Sitemap: {BASE}/sitemap.xml
''')
write('/sitemap.xml', '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
      ''.join(f'  <url><loc>{BASE}{u}</loc><lastmod>{TODAY}</lastmod></url>\n' for u in pages) + '</urlset>\n')
items = '\n'.join(f"- [{p['title']}]({BASE}/journal/{p['slug']}/): {p['product_name']}。{yen(site_price(p))}（税込・送料込み）。{'販売終了' if p.get('status') == 'sold' else '在庫1点'}"
                  for p in live)
write('/llms.txt', f'''# 古着屋 小判鮫（KOBANZAME）

> 埼玉県川越市元町1-14-5の、築約80年の古民家で営業している古着屋。海外のヴィンテージ古着と、小判鮫オリジナルのリメイクアクセサリー「GAW」を扱う。商品はすべて一点もの。運営は{SHOP['company']}。

## 基本情報
- 店名: 古着屋 小判鮫（こばんざめ / KOBANZAME）
- 所在地: {ADDR}
- 営業時間: 12:00〜20:00（月曜・火曜定休）
- 取扱い: ヴィンテージ古着（メンズ・レディース）、ヨーロッパ・アメリカの古着、オリジナルのリメイクアクセサリー「GAW」
- 買い方: 店頭／このサイト（クレジットカード・Square決済・送料込み）／メルカリShops
- 発送: 決済確認後3日以内（月曜・火曜の定休日を除く）
- 古物商許可: {SHOP['kobutsu']}
- お問い合わせ: {SHOP['email']}
- Instagram: {SHOP['instagram']}

## ページ
- [トップ・よくある質問]({BASE}/): 店の紹介、アクセス、FAQ
- [ジャーナル]({BASE}/journal/): 一点ものの成り立ちの記録（掲載商品はサイトで購入可）
- [特定商取引法に基づく表記]({BASE}/tokushoho/)
- [プライバシーポリシー]({BASE}/privacy/)

## 掲載中の商品
{items}
''')
print('built', len(pages), 'pages')
