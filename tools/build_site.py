# -*- coding: utf-8 -*-
"""小判鮫 公式サイト 生成スクリプト（2026-10-01 repo同梱版：GitHub Actions が data/products.json の変更時に実行）
共通ヘッダー・フッター・構造化データを1か所で管理し、全ページを書き出す。
価格はチャネル別（マクドナルド方式）: data/products.json の prices.site をサイトに表示する。
"""
import json, os, html

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo のルート（tools/ の1つ上）
BASE = 'https://kobanzame-site.pages.dev'   # 独自ドメイン取得後はここだけ差し替える
# 更新日：環境変数 SITE_TODAY があればそれ、無ければ日本時間の今日（GitHub Actions で自動生成するため）
import datetime
TODAY = os.environ.get('SITE_TODAY') or datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y-%m-%d')

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
}
ADDR = f"〒{SHOP['postal']} {SHOP['region']}{SHOP['locality']}{SHOP['street']}"

products = json.load(open(os.path.join(ROOT, 'data/products.json'), encoding='utf-8'))

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

def head(title, desc, path, og_type='website', image=None, extra_ld=None, noindex=False):
    url = BASE + path
    img = image or 'https://assets.mercari-shops-static.com/-/large/plain/2JX8ZaipBiPKYk5f7ApJKD.jpg'
    ld = extra_ld if extra_ld is not None else {'@context': 'https://schema.org', '@graph': [org_node()]}
    return f'''<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}">
{'<meta name="robots" content="noindex">' if noindex else ''}
<meta property="og:type" content="{og_type}">
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{img}">
<meta property="og:site_name" content="{SHOP['name']}">
<meta property="og:locale" content="ja_JP">
<meta name="twitter:card" content="summary_large_image">
<link rel="canonical" href="{url}">
<link rel="alternate" type="text/plain" title="llms.txt" href="/llms.txt">
<link rel="stylesheet" href="/journal/style.css">
{jld(ld)}
</head>
<body>
<header class="site"><div class="wrap">
  <a class="brand" href="/">小判鮫<small>KOBANZAME・KAWAGOE</small></a>
  <nav class="site"><a href="/#about">店について</a><a href="/journal/">ジャーナル</a><a href="/#faq">Q&amp;A</a></nav>
</div></header>
'''

FOOT = f'''<footer class="site"><div class="wrap">
  <div class="sns">
    <a href="{SHOP['instagram']}" rel="noopener">Instagram</a>
    <a href="{SHOP['mercari']}" rel="noopener">メルカリShops</a>
  </div>
  <div class="fnote">
    古着屋 小判鮫（KOBANZAME）／{ADDR}／{SHOP['hours']}<br>
    運営：{SHOP['company']}　・　古物商許可：{SHOP['kobutsu']}<br>
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

def yen(n):
    return f'{n:,}円'

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

# ---------- トップ ----------
top_ld = {'@context': 'https://schema.org', '@graph': [org_node(), faq_ld(),
          {'@type': 'WebSite', '@id': BASE + '/#website', 'url': BASE + '/', 'name': SHOP['name'], 'inLanguage': 'ja',
           'publisher': {'@id': BASE + '/#store'}}]}
faq_html = '\n'.join(f'      <dt>{html.escape(q)}</dt><dd>{html.escape(a)}</dd>' for q, a in FAQ)
live = [p for p in products if p.get('published')]
cards = '\n'.join(f'''    <a href="/journal/{p['slug']}/">
      <img class="thumb" src="{p['thumb']}" alt="{html.escape(p['product_name'])}" loading="lazy" style="object-fit:cover;width:100%;height:100%">
      <div class="tx">
        <b>{html.escape(p['title'])}</b>
        <span>{html.escape(p['brand'])} ・ {yen(p['prices']['site'])}（送料込み） ・ {p['published_date'].replace('-', '.')}{' ・ SOLD' if p.get('status') == 'sold' else ''}</span>
      </div>
    </a>''' for p in live)
top = head('古着屋 小判鮫 KOBANZAME｜埼玉・川越の古民家ヴィンテージ古着店',
           '埼玉県川越市元町、築約80年の古民家で営業する古着屋 小判鮫（KOBANZAME）。海外のヴィンテージ古着と、オリジナルのリメイクアクセサリー「GAW」。すべて一点もの。サイトからクレジットカードで購入できます（送料込み）。',
           '/', extra_ld=top_ld) + f'''
<main class="wrap">
  <div class="hero">
    <div class="en">KAWAGOE ・ VINTAGE</div>
    <h1>一点ものの古着と、<br>手仕事のアクセサリー。</h1>
    <p>埼玉・川越、築約八〇年の古民家で営んでいます。</p>
  </div>

  <img src="https://assets.mercari-shops-static.com/-/large/plain/2JX8ZaipBiPKYk5f7ApJKD.jpg" alt="小判鮫オリジナル GAWのスプーンペンダント" loading="lazy" style="width:100%;aspect-ratio:16/10;object-fit:cover;display:block;border-radius:6px;margin:26px 0 6px">

  <section class="block" id="online">
    <h2>オンラインで買える一点もの</h2>
    <p>このサイトからクレジットカードで購入できます。送料込み、3日以内に発送（月・火の定休日を除く）。</p>
    <div class="cardlist">
{cards}
    </div>
  </section>

  <section class="block" id="about">
    <h2>店について</h2>
    <p>古着屋 小判鮫（KOBANZAME）は、埼玉県川越市元町にある築約八〇年の古民家で営業している古着屋です。海外のヴィンテージ古着と、小判鮫オリジナルのリメイクアクセサリー「GAW」を扱っています。ブランドや流行ではなく、素材・質感・その一点にしかない気配で選んでいます。</p>
  </section>

  <section class="block">
    <h2>取扱い</h2>
    <p>ヴィンテージ古着（メンズ／レディース）、ヨーロッパ・アメリカの古着、小判鮫オリジナルのリメイクアクセサリー「GAW」。すべて一点ものです。</p>
    <div class="links">
      <a href="/journal/">ジャーナル（オンラインで買える商品）　→</a>
    </div>
  </section>

  <section class="block" id="faq">
    <h2>よくある質問</h2>
    <dl class="faq">
{faq_html}
    </dl>
  </section>

  <section class="block">
    <h2>アクセス・営業</h2>
    <div class="info"><dl>
      <dt>住所</dt><dd>{ADDR}</dd>
      <dt>営業</dt><dd>{SHOP['hours']}</dd>
      <dt>運営</dt><dd>{SHOP['company']}</dd>
      <dt>お問い合わせ</dt><dd>{SHOP['email']}</dd>
    </dl></div>
  </section>
</main>

''' + FOOT
write('/index.html', top)

# ---------- 記事（商品ページ） ----------
for p in products:
    path = f"/journal/{p['slug']}/"
    price = p['prices']['site']
    sold = p.get('status') == 'sold'
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
         'material': p['material'], 'category': p['category'], 'offers': offer},
        {'@type': 'BlogPosting', '@id': BASE + path + '#article', 'headline': p['title'], 'image': p['images'][0],
         'datePublished': p['published_date'], 'dateModified': TODAY, 'inLanguage': 'ja',
         'author': author, 'publisher': {'@id': BASE + '/#store'}, 'about': {'@id': BASE + path + '#product'},
         'mainEntityOfPage': BASE + path},
        {'@type': 'BreadcrumbList', 'itemListElement': [
            {'@type': 'ListItem', 'position': 1, 'name': 'HOME', 'item': BASE + '/'},
            {'@type': 'ListItem', 'position': 2, 'name': 'JOURNAL', 'item': BASE + '/journal/'},
            {'@type': 'ListItem', 'position': 3, 'name': p['title'], 'item': BASE + path}]},
        org_node()]}
    gallery = ''.join(
        f'<img class="shot{" big" if i == 0 else ""}" src="{u}" alt="{html.escape(p["product_name"])} 写真{i+1}" loading="lazy">'
        for i, u in enumerate(p['images']))
    summary = ''.join(f'<li>{html.escape(s)}</li>' for s in p['summary_points'])
    spec = ''.join(f'<dt>{html.escape(k)}</dt><dd>{html.escape(v)}</dd>' for k, v in p['spec'])
    body = p['body_html']
    if sold:
        buy = '<span class="soldout">SOLD OUT（この一点は旅立ちました）<small>記録としてページを残しています</small></span>'
    elif p['links'].get('square'):
        buy = (f'<a class="buy" href="{p["links"]["square"]}" rel="noopener">購入する（クレジットカード）'
               f'<small>一点もの・在庫1点／Square の安全な決済ページへ移動します</small></a>')
    else:
        buy = '<span class="soldout">準備中（まもなく購入できるようになります）</span>'
    page = head(f"{p['title']}｜{SHOP['name']}（川越）", p['summary_text'], path, og_type='article',
                image=p['images'][0], extra_ld=ld, noindex=p.get('noindex', False)) + f'''
<main class="wrap">
  <div class="crumb"><a href="/">HOME</a> ／ <a href="/journal/">JOURNAL</a> ／ {html.escape(p['sku'])}</div>
  <h1>{html.escape(p['title'])}</h1>
  <div class="meta">{html.escape(p['brand'])} ／ 一点もの ・ {p['published_date'].replace('-', '.')}</div>
  <div class="gallery">{gallery}</div>
  <div class="summary"><b>この商品について</b><ul>{summary}</ul></div>
  <p class="lead">{html.escape(p['lead'])}</p>
  <article>
{body}
    <div class="spec"><dl>{spec}</dl></div>
    <p class="byline">文：小判鮫オーナー・専属バイヤー 龍</p>
  </article>
  <div class="buybox">
    <p class="price">{yen(price)}<small>税込・送料込み</small></p>
    {buy}
    <p class="note-oneoff">店頭・他の販路で先に売れた場合は、ご注文をお受けできないことがあります（その際は全額返金いたします）。</p>
  </div>
</main>

''' + FOOT
    write(path + 'index.html', page)

# ---------- ジャーナル一覧 ----------

list_ld = {'@context': 'https://schema.org', '@graph': [org_node(),
           {'@type': 'CollectionPage', 'name': 'ジャーナル｜' + SHOP['name'], 'url': BASE + '/journal/',
            'mainEntity': {'@type': 'ItemList', 'itemListElement': [
                {'@type': 'ListItem', 'position': i + 1, 'url': BASE + f"/journal/{p['slug']}/", 'name': p['title']}
                for i, p in enumerate(live)]}}]}
jl = head('ジャーナル｜古着屋 小判鮫 KOBANZAME', '一点ものの古着とGAWアクセサリーの成り立ちの記録。掲載中の商品はクレジットカードで購入できます（送料込み）。',
          '/journal/', extra_ld=list_ld) + f'''
<main class="wrap">
  <div class="crumb"><a href="/">HOME</a> ／ JOURNAL</div>
  <div class="hero">
    <div class="en">JOURNAL</div>
    <h1>一点ものの、<br>成り立ちの記録。</h1>
    <p>古着とGAWアクセサリーの背景を、少しずつ書いています。掲載中の商品は、このサイトから購入できます。</p>
  </div>
  <div class="cardlist">
{cards}
  </div>
</main>

''' + FOOT
write('/journal/index.html', jl)

# ---------- 404 ----------
nf = head('ページが見つかりません｜古着屋 小判鮫 KOBANZAME', 'お探しのページは見つかりませんでした。', '/404.html', noindex=True) + """
<main class="wrap">
  <div class="hero">
    <div class="en">NOT FOUND</div>
    <h1>このページは、<br>もう旅立ったようです。</h1>
    <p>お探しのページは見つかりませんでした。売れた商品のページは削除されることがあります。</p>
  </div>
  <div class="links" style="text-align:center;margin:30px 0">
    <a href="/journal/">オンラインで買える一点もの　→</a>
  </div>
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
<main class="wrap legal lawtable">
  <h1>特定商取引法に基づく表記</h1>
  <dl>{law_html}</dl>
  <p style="color:#8b8173;font-size:13px;margin-top:24px">制定：2026年9月30日</p>
</main>

''' + FOOT
write('/tokushoho/index.html', tk)

# ---------- プライバシーポリシー ----------
pv = head('プライバシーポリシー｜古着屋 小判鮫', '古着屋 小判鮫（運営：株式会社プラグ）のプライバシーポリシー。', '/privacy/') + f'''
<main class="wrap legal">
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
  <p style="color:#8b8173;font-size:13px;margin-top:20px">制定：2026年9月／改定：2026年9月30日</p>
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
items = '\n'.join(f"- [{p['title']}]({BASE}/journal/{p['slug']}/): {p['product_name']}。{yen(p['prices']['site'])}（税込・送料込み）。{'販売終了' if p.get('status') == 'sold' else '在庫1点'}"
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
