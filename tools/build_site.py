# -*- coding: utf-8 -*-
"""小判鮫 公式サイト 生成スクリプト v2.1（2026-10-04 改訂）
GitHub Actions が data/products.json か このファイルの変更時（mainブランチ）に実行する。

v2で変わったこと
- 見た目：古民家の黒い壁に合わせた「墨・生成り・古金」の3色＋濃淡1色。見出しは明朝、本文は角ゴシック
- 日本語／English の切り替え（英語ページは /en/ 以下。英語の商品説明は data/products_en.json）
- 公開の流れ（A案）：products.json の "release" が "draft" の商品は下書き＝ページは作るが検索に出さず一覧にも出さない。
  水曜朝のGASが "draft" → "live" に書き換えると一覧に並ぶ（"release" が無い商品は従来どおり published で判断）
- 売れた商品（status=sold）は一覧から消さずSOLDで残す（「売れた一点ものも見る」で表示）
- サイズで探す（身幅±3cm）／店頭で見たい・取り置き（2日間）／こちらも一点もの
- 価格：ADD_TAX=True で「Square登録価格（税抜）×1.1 を10円単位に切り上げ」を税込として表示（2026-10-06 から True）。
  ※Squareのオンライン決済にも消費税がかかる設定にしてから True にする（表示と請求額をそろえるため）
- アクセス解析：CF_BEACON_TOKEN に Cloudflare Web Analytics のトークンを入れると全ページに計測タグが入る
- トップの写真：HERO_IMAGE（店内の写真）。写真の上にGoogleマップへのリンク
"""
import json, os, html, re, math, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = 'https://kobanzame-site.pages.dev'   # 独自ドメイン取得後はここだけ差し替える
TODAY = os.environ.get('SITE_TODAY') or datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y-%m-%d')

ADD_TAX = True           # 2026-10-06 龍さん決定B：Square登録価格は税抜 → 表示・請求とも ×1.1 を10円単位に切り上げ（63番の QP.ADD_TAX と必ず同じにする）
TAX_RATE = 0.10
CF_BEACON_TOKEN = ''     # Cloudflare Web Analytics のトークン（空なら計測タグを入れない）
ANALYTICS_URL = 'https://script.google.com/macros/s/AKfycbxxYc9kZztdwiWOvefrpY6mPHlRUlqLb2SndthCdAUn7BeBXAgZO3i6_JoDxyFQiv3q/exec'       # 64番（自前の簡易計測）のウェブアプリURL。空なら計測しない（2026-10-06 龍さん決定A）
GSC_VERIFY = '2pVJ6dksHBkvBUmm0l3gbrdw8Rgpz4v7zoq4X3eL7ys'          # Google Search Console の確認コード（content="…" の中身だけ。空ならタグを入れない）
BING_VERIFY = ''         # Bing Webmaster Tools の確認コード（同上。Search Consoleから取り込むなら空のままでよい）
HOLD_DAYS = 2            # 店頭取り置きの日数（2026-10-04 決定）
HERO_IMAGE = '/assets/hero-shop.jpg'          # 店内の写真（例 '/assets/hero-shop.jpg'）。空なら掲載中のアウターの写真を使う

SHOP = {
    'name': '古着屋 小判鮫 KOBANZAME',
    'company': '株式会社プラグ',
    'postal': '350-0062',
    'email': 'kobansame111@gmail.com',
    'kobutsu': '埼玉県公安委員会 第431080060786号',
    'instagram': 'https://www.instagram.com/remora__used372/',
    'ig_handle': '@remora__used372',
    'mercari': 'https://jp.mercari.com/shops/profile/mCEGcCeE7gengRWWZYg9zV',
    'gmaps': 'https://www.google.com/maps/search/%E5%8F%A4%E7%9D%80%E5%B1%8B+%E5%B0%8F%E5%88%A4%E9%AE%AB+%E5%B7%9D%E8%B6%8A',
}
ADDR = {'ja': '〒350-0062 埼玉県川越市元町1-14-5', 'en': '1-14-5 Motomachi, Kawagoe, Saitama 350-0062, Japan'}

products = json.load(open(os.path.join(ROOT, 'data/products.json'), encoding='utf-8'))
_en_path = os.path.join(ROOT, 'data/products_en.json')
EN = json.load(open(_en_path, encoding='utf-8')) if os.path.exists(_en_path) else {}

# ---------- 文言（日本語／英語） ----------
T = {
 'ja': {
  'util': '<b>毎週水曜 新着入荷</b>　送料込み・決済確認後3日以内に発送（月・火定休を除く）',
  'nav': [('/#list', '商品一覧'), ('/#store', '店舗'), ('/#faq', 'Q&amp;A')],
  'hero_h': 'One<br>of <em>One.</em>',
  'hero_p': '埼玉・川越、築約80年の古民家から。国内外で買い付けたヴィンテージ古着と、オリジナルの「GAW」。どれも一点もので、同じものはありません。',
  'hero_btn': '一点ものを見る',
  'map': '地図を開く ／ 川越市元町1-14-5',
  'list_h': 'In Stock', 'list_s': 'オンラインで買える一点もの（毎週水曜更新）', 'unit': '点',
  'finder_l': '手持ちの服の身幅', 'finder_u': 'cm ±3cmの服を表示', 'finder_sold': '売れた一点ものも見る', 'finder_clear': '条件をクリア',
  'finder_hint': '身幅＝脇の下から脇の下までを平らに置いて測った長さ。いちばん気に入っている服で測るのがおすすめです。',
  'empty_w': '身幅{w}cm前後の服は、いまはありません。毎週水曜に新着が入ります。', 'empty': '条件に合う一点ものは、いまはありません。',
  'fit': '身幅{w}cm（{d}）', 'same': '同じ',
  'one': '1点限り', 'tax': '税込', 'tax_ship': '税込・送料込み',
  'trust': [('送料込み', '表示価格は税込・送料込み'), ('3日以内に発送', '決済確認後（月・火定休を除く）'),
            ('川越の実店舗', '古物商許可 ' + SHOP['kobutsu']), ('お店の評判', '<a href="{gm}" rel="noopener">Googleマップでクチコミを見る</a>')],
  'store_p': '古着屋 小判鮫（KOBANZAME）は、埼玉県川越市元町にある築約80年の古民家で営業している古着屋です。国内外で買い付けたヴィンテージ古着と、小判鮫オリジナルのリメイクアクセサリー「GAW」を扱っています。ブランドや流行ではなく、素材・質感・その一点にしかない気配で選んでいます。サイトに載っている商品は、店頭にも並んでいます。',
  'store_dl': [('住所', None), ('営業', '12:00–20:00'), ('定休日', '月曜・火曜'), ('運営', SHOP['company']), ('お問い合わせ', SHOP['email'])],
  'faq_s': 'よくある質問',
  'buy': '購入する（クレジットカード）', 'buy_s': '購入する', 'soldout': 'SOLD OUT（この一点は旅立ちました）', 'prep': '準備中（まもなく購入できるようになります）',
  'hold_btn': '店頭で見たい・取り置きする（{n}日間）',
  'hold_p': '川越・元町の店頭で{n}日間お取り置きします。下の内容をInstagramのDMかメールで送ってください。',
  'hold_code': '取り置き希望／{sku}／来店予定日：　月　日／お名前：',
  'hold_to': '送り先', 'hold_mail': 'メール', 'hold_note': '店頭やネットで先に売れていた場合は、こちらからご連絡します。',
  'ship': '<b>一点もの・在庫1点。</b>Squareの安全な決済ページへ進みます。店頭・他の販路で先に売れた場合は、ご注文をお受けできないことがあります（その際は全額返金いたします）。<br>決済確認後3日以内に発送（月・火定休を除く）',
  'stock1': '在庫1点', 'width': '身幅 {w}cm',
  'story': 'この一着の話', 'specs': '仕様・サイズ', 'delivery': '配送・返品',
  'howto': '実寸は平置きで測っています。身幅＝脇の下から脇の下、着丈＝襟のつけ根から裾まで。お手持ちの服を同じように測って比べると、サイズの失敗が減ります。',
  'delivery_p': '送料込み。決済確認後3日以内（月・火定休を除く）に、川越の店舗から発送します。古着・一点ものの性質上、お客様都合の返品はお受けしていません。商品説明と著しく異なる場合や発送間違いの場合は、到着後4日以内にメールでご連絡ください。',
  'byline': '文：小判鮫オーナー・専属バイヤー 龍',
  'related': 'こちらも一点もの', 'draft': '下書き（まだ公開していません）｜毎週水曜の朝に公開されます',
  'journal_h': 'Journal', 'journal_s': '一点ものの、成り立ちの記録',
  'legal': [('/tokushoho/', '特定商取引法に基づく表記'), ('/privacy/', 'プライバシーポリシー')],
  'gm': 'Googleマップ', 'rank_new': '新品・未使用', 'rank_vin': 'ヴィンテージ（経年あり）', 'rank': '状態 {r}',
  'cats': {'outer': 'アウター', 'tops': 'トップス', 'bottoms': 'ボトムス・ワンピース', 'shoes': '靴', 'acc': 'アクセサリー・GAW', 'other': '小物・雑貨'},
  'nf_p': 'お探しのページは見つかりませんでした。売れた商品も、ふだんはSOLDとしてページを残しています。', 'nf_btn': 'オンラインで買える一点もの',
  'top_title': '古着屋 小判鮫 KOBANZAME｜埼玉・川越の古民家ヴィンテージ古着店',
  'top_desc': '埼玉県川越市元町、築約80年の古民家で営業する古着屋 小判鮫（KOBANZAME）。国内外で買い付けたヴィンテージ古着と、オリジナルのリメイクアクセサリー「GAW」。すべて一点もの。サイトからクレジットカードで購入できます（送料込み）。',
  'jr_title': 'ジャーナル｜古着屋 小判鮫 KOBANZAME', 'jr_desc': '一点ものの古着とGAWアクセサリーの成り立ちの記録。掲載中の商品はクレジットカードで購入できます（送料込み）。',
  'no_en': '',
 },
 'en': {
  'util': '<b>New arrivals every Wednesday</b>　Shipping included · Dispatched within 3 days of payment (closed Mon & Tue)',
  'nav': [('/en/#list', 'Shop'), ('/en/#store', 'Store'), ('/en/#faq', 'FAQ')],
  'hero_h': 'One<br>of <em>One.</em>',
  'hero_p': 'From an 80-year-old wooden house in Kawagoe, Saitama. Vintage clothing sourced in Japan and abroad, and our own remake line, GAW. Every piece is one of a kind.',
  'hero_btn': 'See the pieces',
  'map': 'Open map / 1-14-5 Motomachi, Kawagoe',
  'list_h': 'In Stock', 'list_s': 'One-of-a-kind pieces you can buy online (updated every Wednesday)', 'unit': ' items',
  'finder_l': 'Chest width of a piece you own', 'finder_u': 'cm — show pieces within ±3 cm', 'finder_sold': 'Show sold pieces', 'finder_clear': 'Clear',
  'finder_hint': 'Chest width = measured flat, armpit to armpit. Measure the piece you like best for the closest match.',
  'empty_w': 'Nothing around {w} cm right now. New pieces arrive every Wednesday.', 'empty': 'Nothing matches right now.',
  'fit': 'Chest {w} cm ({d})', 'same': 'same',
  'one': 'Only 1', 'tax': 'tax incl.', 'tax_ship': 'tax & shipping incl.',
  'trust': [('Shipping included', 'Prices include tax and domestic shipping'), ('Ships in 3 days', 'After payment (closed Mon & Tue)'),
            ('A real shop in Kawagoe', 'Licensed secondhand dealer (Saitama Pref. No. 431080060786)'), ('Reviews', '<a href="{gm}" rel="noopener">Read reviews on Google Maps</a>')],
  'store_p': 'Kobanzame is a vintage clothing shop in an 80-year-old wooden house in Motomachi, Kawagoe, Saitama. We carry vintage clothing sourced in Japan and abroad, and GAW, our own line of remade accessories. We choose by material, texture and the feel of each single piece, not by brand or trend. Everything on this site is also in the shop.',
  'store_dl': [('Address', None), ('Hours', '12:00–20:00'), ('Closed', 'Mondays & Tuesdays'), ('Operator', 'Plug Inc.'), ('Contact', SHOP['email'])],
  'faq_s': 'Frequently asked questions',
  'buy': 'Buy now (credit card)', 'buy_s': 'Buy now', 'soldout': 'SOLD OUT', 'prep': 'Coming soon',
  'hold_btn': 'See it in the shop / hold it ({n} days)',
  'hold_p': 'We will hold it at the shop in Kawagoe for {n} days. Send the message below by Instagram DM or email.',
  'hold_code': 'Hold request / {sku} / visit date: / name:',
  'hold_to': 'Send to', 'hold_mail': 'Email', 'hold_note': 'If it sells first in the shop or online, we will let you know.',
  'ship': '<b>One of a kind, 1 in stock.</b> You will go to Square\'s secure checkout. If it sells first elsewhere we may not be able to accept your order, and you will get a full refund.<br>Online checkout ships within Japan. For overseas shipping, please contact us before buying.',
  'stock1': '1 in stock', 'width': 'Chest {w} cm',
  'story': 'The story', 'specs': 'Details & size', 'delivery': 'Shipping & returns',
  'howto': 'Measured flat. Chest = armpit to armpit; length = base of collar to hem. Measure a piece you own the same way to compare.',
  'delivery_p': 'Domestic shipping included. Dispatched from our Kawagoe shop within 3 days of payment (closed Mon & Tue). As these are one-of-a-kind vintage items, we do not accept returns for change of mind. If the item differs significantly from the description or we sent the wrong item, email us within 4 days of arrival.',
  'byline': 'Words: Ryu, owner & buyer at Kobanzame',
  'related': 'Also one of one', 'draft': 'Draft (not yet published) | goes live on Wednesday morning',
  'journal_h': 'Journal', 'journal_s': 'Where each piece comes from',
  'legal': [('/en/legal/', 'Legal notice & privacy')],
  'gm': 'Google Maps', 'rank_new': 'New, unused', 'rank_vin': 'Vintage (signs of age)', 'rank': 'Condition {r}',
  'cats': {'outer': 'Outerwear', 'tops': 'Tops', 'bottoms': 'Bottoms & dresses', 'shoes': 'Shoes', 'acc': 'Accessories & GAW', 'other': 'Goods'},
  'nf_p': 'We could not find that page. Sold pieces usually stay on the site marked SOLD.', 'nf_btn': 'See the pieces',
  'top_title': 'Kobanzame | Vintage clothing in an old wooden house, Kawagoe, Japan',
  'top_desc': 'Kobanzame is a vintage clothing shop in an 80-year-old wooden house in Kawagoe, Saitama. Vintage clothing sourced in Japan and abroad, and our own remade accessories, GAW. Every piece is one of a kind. Buy online by credit card.',
  'jr_title': 'Journal | Kobanzame, Kawagoe', 'jr_desc': 'Where each one-of-a-kind piece comes from. Listed pieces can be bought online.',
  'no_en': 'English description coming soon. The details below are in Japanese.',
 },
}
# ---------- ワークショップ（2026-10-07 龍さん決定A） ----------
# 予約は外部の予約サイト（concentsocket.com）。このサイトには案内と「予約する」ボタンだけを置く。
# WS_FROM より前の日付で作ったときは、ページもメニューの入り口も出さない（予約受付の開始日に合わせる）。
# 料金は「期間限定価格」。終了時期は未定なので、比べる「通常価格」は書かない（二重価格表示にしない）。
WS_FROM = '2026-10-21'
WS_OPEN = TODAY >= WS_FROM
RESERVE = 'https://www.concentsocket.com/location/kobanzame/reserve/'
WORKSHOPS = [
    {'id': 'brass-bangle', 'reserve': RESERVE + 'dedff258-e093-4b81-bc8e-0abf0ac5bf4a', 'price': 1500, 'minutes': 60, 'max': 2,
     'ja': {'name': '真鍮バングルワークショップ',
            'lead': '切り出した真鍮を、店主が目の前で腕の形に曲げます。仕上げの刻印（アルファベット・数字・記号）は、ご自身の手で打っていただきます。完成品はその場でお持ち帰りいただけます。',
            'notes': ['1人1本・刻印つき', 'モニター募集中：作業中の写真を撮らせていただく場合があります（お顔を出したくない方は当日お伝えください。手元だけを撮ります）',
                      '金属アレルギーのある方は、ご予約の前にご相談ください', '真鍮は使い込むと色が変化します']},
     'en': {'name': 'Brass bangle workshop',
            'lead': 'The owner bends a cut brass bar to the shape of your wrist in front of you, and you stamp the finishing marks (letters, numbers, symbols) yourself. Take it home the same day.',
            'notes': ['One bangle per person, stamping included', 'We may take photos of your hands while you work (tell us if you prefer not)',
                      'If you have a metal allergy, please ask us before booking', 'Brass changes colour as you wear it']}},
    {'id': 'stone-beads', 'reserve': RESERVE + '381ebd3c-3e63-4c6c-8f93-2ec4ec346c7f', 'price': 1200, 'minutes': 30, 'max': 2,
     'ja': {'name': '天然石ビーズブレスレットワークショップ',
            'lead': '店頭にある天然石のビーズから1種類を選んで、ブレスレットを作ります。完成品はその場でお持ち帰りいただけます。',
            'notes': ['料金には石1種類分が含まれます', '2種類以上使いたい場合は、1種類につき＋100円（当日店頭でお支払い）', '選べる石は、その日の店頭の在庫によって変わります']},
     'en': {'name': 'Natural stone bead bracelet workshop',
            'lead': 'Choose one kind of natural stone bead from what we have in the shop that day and make your own bracelet. Take it home the same day.',
            'notes': ['The price includes one kind of stone', 'Each additional kind is +100 yen, paid in the shop on the day', 'The stones on offer depend on what is in stock that day']}},
]
if WS_OPEN:
    T_WS_NAV = {'ja': ('/workshop/', 'ワークショップ'), 'en': ('/en/workshop/', 'Workshops')}

CAT_EN = {'outer': 'Outer', 'tops': 'Tops', 'bottoms': 'Bottoms', 'shoes': 'Shoes', 'acc': 'Accessories', 'other': 'Goods'}

FAQ = {
 'ja': [
    ('小判鮫はどこにある古着屋ですか？', f'埼玉県川越市元町1-14-5（〒350-0062）にある、築約80年の古民家で営業している古着屋です。運営は{SHOP["company"]}です。'),
    ('営業時間と定休日は？', '12:00〜20:00の営業で、毎週月曜日・火曜日が定休日です。臨時の休みや営業時間の変更はInstagramでお知らせします。'),
    ('どんなものを扱っていますか？', '国内外で買い付けたヴィンテージ古着（メンズ・レディース）と、小判鮫オリジナルのリメイクアクセサリー「GAW」を扱っています。商品はすべて一点ものです。'),
    ('GAWとは何ですか？', '小判鮫オリジナルのリメイクアクセサリーのラインです。古いスプーンなどの素材を、ペンダントやバングルなどの一点ものに作り直しています。'),
    ('通販で買えますか？', 'はい。このサイトに載っている商品は、クレジットカード（Square決済）でそのまま購入できます。メルカリShopsでも販売しています。'),
    ('送料はかかりますか？', 'このサイトで購入した場合、表示価格は税込・送料込みです。'),
    ('いつ届きますか？', 'ご注文（決済）の確認後、3日以内（定休日を除く）に発送します。'),
    ('返品はできますか？', '古着・一点ものの性質上、お客様都合による返品はお受けしていません。商品説明と著しく異なる場合や発送間違いの場合は、到着後4日以内にメールでご連絡ください。'),
    ('店頭で取り置きできますか？', f'できます。商品ページの「店頭で見たい・取り置きする」から、InstagramのDMかメールでご連絡ください。{HOLD_DAYS}日間お取り置きします。'),
 ],
 'en': [
    ('Where is Kobanzame?', 'At 1-14-5 Motomachi, Kawagoe, Saitama (350-0062), in an 80-year-old wooden house. The shop is run by Plug Inc.'),
    ('Opening hours?', 'Open 12:00–20:00. Closed every Monday and Tuesday. Changes are announced on Instagram.'),
    ('What do you sell?', 'Vintage clothing sourced in Japan and abroad (men\'s and women\'s) and GAW, our own line of remade accessories. Every piece is one of a kind.'),
    ('What is GAW?', 'Kobanzame\'s own remake accessory line. We turn materials such as old spoons into one-of-a-kind pendants, bangles and more.'),
    ('Can I buy online?', 'Yes. Pieces on this site can be bought by credit card through Square. Online checkout ships within Japan; for overseas shipping, contact us first.'),
    ('Is shipping included?', 'Yes. Prices on this site include tax and domestic shipping.'),
    ('When will it arrive?', 'We dispatch within 3 days of payment (excluding our closed days).'),
    ('Can I return it?', 'As these are one-of-a-kind vintage items, we do not accept returns for change of mind. If the item differs significantly from the description or we sent the wrong item, email us within 4 days of arrival.'),
    ('Can you hold a piece for me?', f'Yes. Use "See it in the shop / hold it" on the item page and contact us by Instagram DM or email. We hold it for {HOLD_DAYS} days.'),
 ],
}

# ---------- 共通の小さな関数 ----------
def esc(s):
    return html.escape(str(s))

def pre(lang):
    return '/en' if lang == 'en' else ''

def site_price(p):
    base = int(p['prices']['site'])
    # 税込＝税抜×1.1 を10円単位に切り上げ（小数の誤差を避けるため整数で計算：base*11/100 を切り上げて ×10）
    return (-(-base * 11 // 100)) * 10 if ADD_TAX else base

def money(n, lang):
    return f'¥{n:,}' if lang == 'en' else f'{n:,}円'

def release(p):
    r = p.get('release')
    if r in ('live', 'draft'):
        return r if p.get('published', True) else 'hidden'
    return 'live' if p.get('published') else 'hidden'

def is_sold(p):
    return p.get('status') == 'sold'

def cat_of(p):
    c = p.get('category', '')
    if 'アクセサリー' in c: return 'acc'
    if 'アウター' in c or 'ジャケット' in c or 'コート' in c: return 'outer'
    if 'トップス' in c or 'シャツ' in c or 'ニット' in c or 'スウェット' in c: return 'tops'
    if 'パンツ' in c or 'ボトムス' in c or 'スカート' in c or 'ワンピース' in c: return 'bottoms'
    if '靴' in c or 'シューズ' in c or 'ブーツ' in c: return 'shoes'
    return 'other'

def body_width(p):
    for k, v in p.get('spec', []):
        if k == 'サイズ':
            m = re.search(r'身幅\s*([\d.]+)', v)
            if m:
                return float(m.group(1))
    return None

def cond_rank(p, lang):
    t = T[lang]
    for k, v in p.get('spec', []):
        if k == '状態':
            if re.match(r'^[ABC]：', v): return t['rank'].format(r=v[0])
            if '新品' in v or 'デッドストック' in v: return t['rank_new']
            return t['rank_vin']
    return ''

def abs_url(u):
    """サイト内の画像（/assets/...）を https:// から始まる完全なURLにする（Google・SNSは完全なURLでないと読めない）"""
    return BASE + u if isinstance(u, str) and u.startswith('/') else u

def thumb_of(p):
    return p.get('thumb') or p['images'][0].replace('/large/', '/medium/')

def loc(p, key, lang):
    """英語ページでは products_en.json の値を使う（無ければ日本語のまま）"""
    if lang == 'en' and p['sku'] in EN and key in EN[p['sku']]:
        return EN[p['sku']][key]
    return p[key]

def has_en(p):
    return p['sku'] in EN

NO_BRAND = ('表記なし', 'ノーブランド', 'TEST')

def spec_of(p):
    """仕様表（[[項目, 値], ...]）を辞書にする"""
    return {k: v for k, v in p.get('spec', [])}

def color_of(p):
    """色：かっこ書きを外し、「×」区切りを「/」にする（Googleは100文字まで）"""
    c = re.sub(r'[（(].*?[）)]', '', spec_of(p).get('色', '')).strip()
    return re.sub(r'\s*[×✕]\s*', '/', c)[:100]

def size_of(p):
    """サイズ：表記サイズ（L・US 8.5 D など）を優先。表記が無ければ最初の実寸（身幅55.5cm など）"""
    s = spec_of(p).get('サイズ', '').strip()
    if not s:
        return ''
    head_ = re.split(r'[（(／/]', s)[0].strip()
    head_ = re.sub(r'^(表記|タグ表記|タグ|実寸)\s*', '', head_).strip()
    head_ = head_.split('・')[0].strip()
    return head_[:100]

def gender_of(p):
    c = p.get('category', '')
    return 'male' if c.startswith('メンズ') else 'female' if c.startswith('レディース') else 'unisex'

def brand_of(p):
    b = (p.get('brand') or '').strip()
    return '' if (not b or any(b.startswith(x) for x in NO_BRAND)) else b

def jld(obj):
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False, separators=(',', ':')) + '</script>'

def org_node():
    return {
        '@type': 'ClothingStore', '@id': BASE + '/#store',
        'name': SHOP['name'], 'alternateName': ['小判鮫', 'KOBANZAME', 'こばんざめ'],
        'description': '埼玉県川越市、築約80年の古民家で営業する古着屋。国内外で買い付けたヴィンテージ古着と、小判鮫オリジナルのリメイクアクセサリー「GAW」を扱う。商品はすべて一点もの。',
        'url': BASE + '/', 'email': SHOP['email'],
        'address': {'@type': 'PostalAddress', 'postalCode': SHOP['postal'], 'addressRegion': '埼玉県',
                    'addressLocality': '川越市', 'streetAddress': '元町1-14-5', 'addressCountry': 'JP'},
        'openingHours': 'We-Su 12:00-20:00', 'currenciesAccepted': 'JPY', 'paymentAccepted': 'クレジットカード',
        'hasMap': SHOP['gmaps'],
        'geo': {'@type': 'GeoCoordinates', 'latitude': 35.9253165, 'longitude': 139.4832435},   # Googleマップの店舗ページの座標（2026-10-06）
        'openingHoursSpecification': [{'@type': 'OpeningHoursSpecification',
                                       'dayOfWeek': ['Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'],
                                       'opens': '12:00', 'closes': '20:00'}],
        'parentOrganization': {'@type': 'Organization', 'name': SHOP['company']},
        'sameAs': [SHOP['instagram'], SHOP['mercari']],
    }

# ---------- 見た目 ----------
# 配色の原理：ベース70%＝墨（古民家の黒い壁）／メイン25%＝生成り（文字と紙の面）／アクセント5%＝古金（値段・ボタン・細線だけ）
# ＋濃淡の4色目＝煤竹（写真の台紙や面の区切り。墨より一段明るい黒）。明るさの差で奥行きを出し、色の数は増やさない。
CSS = r'''
:root{
  --sumi:#15130f;      /* ベース：墨（壁の黒） */
  --susu:#1f1c17;      /* 4色目：煤竹（台紙・面の区切り） */
  --kinari:#e9e2d2;    /* メイン：生成り（文字・紙） */
  --kin:#b8945a;       /* アクセント：古金（値段・ボタン・細線） */
  --usu:#a69d8b;       /* 生成りを墨に寄せた補助の文字 */
  --line:#3a352d;      /* 罫線 */
  --sold:#c46a4f;      /* SOLD（弁柄。売れた印だけに使う） */
  --mincho:"Shippori Mincho B1","Hiragino Mincho ProN","Yu Mincho",serif;
  --roman:"Cormorant Garamond","Shippori Mincho B1",serif;
  --gothic:"Zen Kaku Gothic New","Hiragino Sans","Yu Gothic",system-ui,sans-serif;
  --gutter:16px; color-scheme:dark;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--sumi);color:var(--kinari);font-family:var(--gothic);font-size:15px;line-height:1.85;letter-spacing:.02em;-webkit-font-smoothing:antialiased}
img{display:block;max-width:100%}a{color:inherit}button{font:inherit;color:inherit;background:none;border:0;cursor:pointer}
:focus-visible{outline:2px solid var(--kin);outline-offset:3px}
.wrap{max-width:1240px;margin:0 auto;padding-inline:var(--gutter)}
.hair{height:1px;background:linear-gradient(90deg,transparent,var(--kin),transparent);opacity:.7}
.util{background:var(--susu);color:var(--usu);font-size:12px;letter-spacing:.08em;text-align:center;padding:8px var(--gutter);border-bottom:1px solid var(--line)}
.util b{color:var(--kin);font-weight:500}
header.site{position:sticky;top:0;z-index:20;background:rgba(21,19,15,.94);backdrop-filter:blur(6px);border-bottom:1px solid var(--line)}
header.site .wrap{display:flex;align-items:center;justify-content:space-between;gap:16px;min-height:64px}
.logo{display:flex;align-items:baseline;gap:12px;text-decoration:none}
.logo b{font-family:var(--mincho);font-weight:800;font-size:22px;letter-spacing:.14em}
.logo span{font-family:var(--roman);font-size:14px;letter-spacing:.32em;color:var(--kin)}
.hnav{display:flex;align-items:center;gap:22px}
.hnav a{font-size:13px;letter-spacing:.1em;text-decoration:none;color:var(--usu);white-space:nowrap}
.hnav a:hover{color:var(--kinari)}
.lang{display:flex;border:1px solid var(--line)}
.lang a{font-size:12px;padding:4px 10px;color:var(--usu)}
.lang a[aria-current="true"]{background:var(--kinari);color:var(--sumi)}
@media(max-width:760px){.logo span{display:none}.hnav{gap:12px}.hnav a.n{display:none}}
.hero{position:relative;overflow:hidden;border-bottom:1px solid var(--line)}
.hero .wrap{display:grid;grid-template-columns:minmax(0,1fr)}
.hero-ph{position:relative}
.hero-img{width:100%;height:auto;aspect-ratio:1/1;object-fit:cover;object-position:50% 50%}
.maplink{position:absolute;left:12px;bottom:12px;display:inline-flex;align-items:center;gap:8px;background:rgba(21,19,15,.82);border:1px solid var(--kin);color:var(--kinari);font-size:12px;letter-spacing:.06em;padding:8px 12px;text-decoration:none}
.maplink svg{width:14px;height:14px;flex:none}
.hero-copy{padding:32px 0 40px}
.hero h1{font-family:var(--roman);font-weight:500;font-style:italic;font-size:clamp(56px,11vw,120px);line-height:.92;letter-spacing:.01em}
.hero h1 em{font-style:italic;color:var(--kin)}
.hero p{font-family:var(--mincho);font-size:16px;margin-top:18px;max-width:28em;color:var(--kinari)}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:10px;min-height:52px;padding:0 28px;letter-spacing:.12em;text-decoration:none;border:1px solid var(--kin);color:var(--kinari);font-size:14px;text-align:center}
.btn:hover{background:rgba(184,148,90,.12)}
.ws{display:grid;gap:20px;margin-top:24px}
.ws article{border:1px solid var(--line);background:var(--susu);padding:22px 20px}
.ws h2{font-family:var(--mincho);font-size:19px;margin:0 0 6px;color:var(--kinari)}
.ws .price{font-family:var(--mincho);font-size:22px;color:var(--kin)}
.ws .price small{font-size:12px;color:var(--usu);margin-left:8px;letter-spacing:.06em}
.ws .meta{color:var(--usu);font-size:13px;margin:4px 0 12px}
.ws ul{margin:10px 0 18px 1.2em;color:var(--usu);font-size:13px}
@media(min-width:860px){.ws{grid-template-columns:1fr 1fr}}
.btn.kin{background:var(--kin);color:var(--sumi);font-weight:700;width:100%}
.btn.kin:hover{background:#c7a46a}
.btn.ghost{width:100%}
.hero .btn{margin-top:26px}
@media(min-width:900px){.hero .wrap{grid-template-columns:minmax(0,1.2fr) minmax(0,1fr);align-items:center;gap:56px}.hero-img{aspect-ratio:4/5;max-height:680px}.hero-copy{padding:0}}
.catrow{display:flex;flex-wrap:wrap;gap:8px;margin-top:36px}
.catrow button{border:1px solid var(--line);padding:10px 16px;font-size:13px;letter-spacing:.08em;color:var(--usu)}
.catrow button small{font-family:var(--roman);font-size:13px;margin-left:8px;color:var(--kin);letter-spacing:.12em}
.catrow button[aria-pressed="true"]{border-color:var(--kin);color:var(--kinari);background:var(--susu)}
.sec-head{display:flex;align-items:baseline;justify-content:space-between;gap:12px;margin:44px 0 16px}
.sec-head h2,.store h2,.related h2{font-family:var(--roman);font-weight:500;font-size:44px;line-height:1;letter-spacing:.02em}
.sec-head h2 small,.related h2 small{display:block;font-family:var(--mincho);font-size:14px;margin-top:10px;color:var(--usu);letter-spacing:.08em}
.sec-head .count{font-size:13px;color:var(--usu);font-variant-numeric:tabular-nums}
.finder{display:flex;flex-wrap:wrap;align-items:center;gap:10px 16px;margin-bottom:24px;padding:14px 0;border-block:1px solid var(--line);font-size:13px}
.finder input[type=number]{width:5.5em;height:40px;background:var(--susu);color:var(--kinari);border:1px solid var(--kin);border-radius:0;padding:0 8px;font:inherit}
.finder .hint{font-size:12px;color:var(--usu);flex-basis:100%}
.finder .chk{display:flex;align-items:center;gap:6px;color:var(--usu)}
.finder .chk input{accent-color:var(--kin)}
.finder button.clear{font-size:12px;text-decoration:underline;color:var(--usu)}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:28px 12px}
@media(min-width:900px){.grid{grid-template-columns:repeat(3,minmax(0,1fr));gap:44px 20px}}
.card{display:flex;flex-direction:column;gap:6px;min-width:0;text-decoration:none}
.card .ph{position:relative;background:var(--susu);aspect-ratio:4/5;overflow:hidden}
.card .ph img{width:100%;height:100%;object-fit:cover;transition:transform .6s ease,opacity .3s}
.card:hover .ph img{transform:scale(1.025)}
.tag{position:absolute;right:0;top:0;background:var(--sumi);color:var(--kin);font-size:11px;letter-spacing:.12em;padding:4px 10px;border-left:1px solid var(--kin);border-bottom:1px solid var(--kin)}
.card .brand{font-family:var(--roman);font-size:15px;letter-spacing:.14em;color:var(--kin);margin-top:4px}
.card .nm{font-size:13.5px;line-height:1.6;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.card .pr{font-family:var(--mincho);font-weight:700;font-size:17px;font-variant-numeric:tabular-nums}
.card .pr small{font-family:var(--gothic);font-weight:400;font-size:11px;color:var(--usu);margin-left:6px}
.card .fit{font-size:12px;border:1px solid var(--line);padding:1px 6px;align-self:flex-start;color:var(--kinari)}
.card.sold .ph img{opacity:.45}
.card.sold .ph:after{content:"SOLD";position:absolute;inset:0;display:grid;place-items:center;font-family:var(--roman);font-size:34px;letter-spacing:.3em;color:var(--sold)}
.empty{grid-column:1/-1;border:1px dashed var(--line);padding:28px 16px;text-align:center;color:var(--usu);font-size:14px}
.trust{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));border-block:1px solid var(--line);margin-top:64px}
@media(min-width:900px){.trust{grid-template-columns:repeat(4,minmax(0,1fr))}}
.trust div{padding:22px 16px;min-width:0;border-right:1px solid var(--line)}
.trust div:last-child{border-right:0}
.trust b{display:block;font-family:var(--mincho);font-size:15px;color:var(--kin)}
.trust span{font-size:12.5px;color:var(--usu)}
.trust a{color:var(--kinari)}
.store{display:grid;grid-template-columns:minmax(0,1fr);gap:24px;padding-block:56px}
@media(min-width:900px){.store{grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:64px}}
.store p{margin-top:14px;max-width:34em;font-family:var(--mincho)}
.store dl,.lawtable dl{display:grid;grid-template-columns:7.5em minmax(0,1fr);gap:12px 14px;border-top:1px solid var(--kin);padding-top:18px;font-size:14px}
.store dt,.lawtable dt{color:var(--usu)}
.store dd a{color:var(--kin)}
.faq{padding-block:8px 64px;max-width:860px}
details{border-bottom:1px solid var(--line)}
details summary{list-style:none;cursor:pointer;display:flex;justify-content:space-between;align-items:center;gap:12px;padding:16px 0;font-family:var(--mincho);font-weight:700;font-size:15px}
details summary::-webkit-details-marker{display:none}
details summary:after{content:"+";font-family:var(--roman);font-size:24px;line-height:1;color:var(--kin)}
details[open] summary:after{content:"−"}
.faq details p{padding-bottom:16px;font-size:14px;color:var(--usu)}
footer.site{background:var(--susu);border-top:1px solid var(--line);padding-block:40px;font-size:12px;line-height:2;color:var(--usu)}
footer.site .wrap{display:grid;gap:16px}
footer.site .big{font-family:var(--roman);font-style:italic;font-size:48px;line-height:1;color:var(--kinari)}
footer.site a{color:var(--kinari)}
.crumb{font-size:12px;color:var(--usu);padding-block:16px;display:flex;gap:8px;flex-wrap:wrap}
.pdp{display:grid;grid-template-columns:minmax(0,1fr);gap:24px;padding-bottom:40px}
@media(min-width:900px){.pdp{grid-template-columns:minmax(0,1.35fr) minmax(0,1fr);gap:56px}}
.gal{display:flex;gap:8px;overflow-x:auto;scroll-snap-type:x mandatory;margin-inline:calc(var(--gutter)*-1);padding-inline:var(--gutter);scrollbar-width:none}
.gal::-webkit-scrollbar{display:none}
.gal img{flex:0 0 86%;aspect-ratio:4/5;object-fit:cover;background:var(--susu);scroll-snap-align:center}
.gal.one img{flex-basis:100%}
.galcount{font-size:12px;color:var(--usu);margin-top:8px;font-variant-numeric:tabular-nums}
@media(min-width:900px){.gal{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));overflow:visible;margin:0;padding:0}.gal img{width:100%}.gal.one{grid-template-columns:minmax(0,1fr)}.galcount{display:none}}
.info{min-width:0}
@media(min-width:900px){.info{position:sticky;top:90px;align-self:start}}
.info .brand{font-family:var(--roman);font-size:18px;letter-spacing:.16em;color:var(--kin)}
.info h1{font-family:var(--mincho);font-weight:700;font-size:22px;line-height:1.55;margin-top:4px;text-wrap:balance}
.info .ttl{font-family:var(--mincho);font-size:14px;color:var(--usu);margin-top:6px}
.info .sku{font-family:var(--roman);font-size:13px;letter-spacing:.2em;color:var(--usu);margin-top:6px}
.info .price{font-family:var(--mincho);font-weight:700;font-size:30px;margin-top:16px;color:var(--kinari);font-variant-numeric:tabular-nums}
.info .price small{font-family:var(--gothic);font-size:12px;font-weight:400;color:var(--usu);margin-left:8px}
.facts{display:flex;flex-wrap:wrap;gap:6px;margin-top:14px}
.facts span{border:1px solid var(--line);font-size:12px;padding:3px 10px;color:var(--kinari)}
.facts span.one{border-color:var(--kin);color:var(--kin)}
.facts span.soldf{border-color:var(--sold);color:var(--sold)}
.noen{font-size:12px;color:var(--usu);border-left:2px solid var(--kin);padding-left:10px;margin-top:12px}
.buybox{margin-top:20px;display:grid;gap:10px}
.soldout{display:block;border:1px solid var(--sold);color:var(--sold);text-align:center;padding:14px;letter-spacing:.16em}
.ship{font-size:12.5px;color:var(--usu);line-height:1.8}
.ship b{color:var(--kinari);font-weight:500}
.holdbox{border:1px solid var(--line);background:var(--susu);padding:14px;font-size:13.5px;display:grid;gap:8px}
.holdbox code{font-family:var(--gothic);background:var(--sumi);border:1px solid var(--line);padding:3px 8px;user-select:all;display:inline-block}
.holdbox a{color:var(--kin)}
.points{margin-top:22px;border-top:1px solid var(--kin)}
.points li{list-style:none;padding:11px 0 11px 18px;border-bottom:1px solid var(--line);position:relative;font-size:14px}
.points li:before{content:"";position:absolute;left:2px;top:22px;width:6px;height:1px;background:var(--kin)}
.story{padding-bottom:16px;font-family:var(--mincho);font-size:15px;line-height:2}
.story h2{font-size:14px;font-weight:700;margin:18px 0 4px;color:var(--kin)}
.story h2:first-child{margin-top:0}
.spec{display:grid;grid-template-columns:6.5em minmax(0,1fr);gap:8px 12px;font-size:14px;padding-bottom:12px}
.spec dt{color:var(--usu)}
.howto{font-size:12.5px;color:var(--usu);padding-bottom:16px}
.byline{font-size:12px;color:var(--usu);padding-block:16px}
.related{border-top:1px solid var(--line);padding-block:40px 140px}
@media(min-width:900px){.related{padding-bottom:72px}}
.related h2{font-size:36px;margin-bottom:20px}
@media(max-width:600px){.related .grid>:nth-child(3){display:none}}
.bar{position:fixed;left:0;right:0;bottom:0;z-index:30;background:rgba(21,19,15,.96);border-top:1px solid var(--kin);padding:10px var(--gutter) calc(10px + env(safe-area-inset-bottom,0px));display:flex;align-items:center;gap:12px}
.bar b{font-family:var(--mincho);font-size:19px;white-space:nowrap;font-variant-numeric:tabular-nums}
.bar .btn{min-height:48px;flex:1}
@media(min-width:900px){.bar{display:none!important}}
.draftnote{background:var(--kin);color:var(--sumi);font-size:13px;font-weight:700;text-align:center;padding:8px var(--gutter)}
.page{padding-block:36px 72px;max-width:860px}
.page h1{font-family:var(--mincho);font-size:26px;margin-bottom:18px}
.page h2{font-family:var(--mincho);font-size:16px;margin:24px 0 6px;color:var(--kin)}
.page p{color:var(--kinari)}
.nf{padding-block:72px;text-align:center}
.nf h1{font-family:var(--roman);font-style:italic;font-weight:500;font-size:72px;line-height:1}
.nf p{margin:18px auto 26px;max-width:28em;color:var(--usu)}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
'''
PIN = '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 2a7 7 0 0 0-7 7c0 5.2 7 13 7 13s7-7.8 7-13a7 7 0 0 0-7-7zm0 9.5A2.5 2.5 0 1 1 12 6.5a2.5 2.5 0 0 1 0 5z"/></svg>'

def other_path(path, lang):
    """切り替え先（日本語⇔英語）のパス。英語ページが無いもの（特商法・プライバシー）は英語の法務ページへ"""
    if lang == 'ja':
        if path in ('/tokushoho/', '/privacy/'):
            return '/en/legal/'
        return '/en' + path
    p = path[3:] if path.startswith('/en') else path
    return '/tokushoho/' if p == '/legal/' else (p or '/')

# 64番：ページが開かれた時と、決まったボタン（購入・メルカリ・取り置き・Instagram・地図）が押された時に1件ずつ送る。
# 個人を見分ける情報（Cookie・端末ID・IP等）は送らない。スタッフは一度 ?nolog=1 を付けて開くと、その端末からは送られない。
TRACK_JS = """<script>
(function(){var U='__URL__';if(!U||navigator.webdriver||/bot|crawl|spider|slurp|lighthouse|headless/i.test(navigator.userAgent))return;
try{if(/[?&]nolog=1/.test(location.search))localStorage.setItem('kbz_nolog','1');if(/[?&]nolog=0/.test(location.search))localStorage.removeItem('kbz_nolog');if(localStorage.getItem('kbz_nolog')==='1')return;}catch(e){}
function sku(){var el=document.querySelector('.sku');var m=el&&el.textContent.match(/[A-Z]{1,3}\\d{3,6}/);return m?m[0]:'';}
function send(o){o.p=location.pathname;o.sku=sku();o.lang=document.documentElement.lang||'';o.dev=/Mobi|Android|iPhone/i.test(navigator.userAgent)?'m':'d';
try{var h=document.referrer?new URL(document.referrer).hostname:'';o.ref=(h===location.hostname)?'':h;}catch(e){o.ref='';}
var b=JSON.stringify(o);try{if(navigator.sendBeacon&&navigator.sendBeacon(U,new Blob([b],{type:'text/plain'})))return;}catch(e){}
try{fetch(U,{method:'POST',body:b,mode:'no-cors',keepalive:true});}catch(e){}}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',function(){send({t:'pv'});});else send({t:'pv'});
document.addEventListener('click',function(e){var a=e.target.closest&&e.target.closest('a,button');if(!a)return;var h=a.getAttribute('href')||'',k='';
if(a.id==='holdbtn')k='hold';else if(/square\\.link/.test(h))k='buy';else if(/mercari/.test(h))k='mercari';else if(/instagram\\.com/.test(h))k='instagram';else if(/google\\.[a-z.]+\\/maps|maps\\.app\\.goo\\.gl|goo\\.gl\\/maps/.test(h))k='map';
if(k)send({t:'click',btn:k});},true);
})();
</script>"""

def head(lang, title, desc, path, og_type='website', image=None, extra_ld=None, noindex=False):
    t = T[lang]
    url = BASE + path
    img = abs_url(image) or 'https://assets.mercari-shops-static.com/-/large/plain/2JX8ZaipBiPKYk5f7ApJKD.jpg'
    ld = extra_ld if extra_ld is not None else {'@context': 'https://schema.org', '@graph': [org_node()]}
    beacon = ('<script defer src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon=\'{"token": "' + CF_BEACON_TOKEN + '"}\'></script>'
              if CF_BEACON_TOKEN else '')
    track = TRACK_JS.replace('__URL__', ANALYTICS_URL) if ANALYTICS_URL else ''
    verify = ((f'<meta name="google-site-verification" content="{esc(GSC_VERIFY)}">\n' if GSC_VERIFY else '') +
              (f'<meta name="msvalidate.01" content="{esc(BING_VERIFY)}">\n' if BING_VERIFY else '')) if path in ('/', '/en/') else ''
    alt = other_path(path, lang)
    ja_url = BASE + (path if lang == 'ja' else alt)
    en_url = BASE + (path if lang == 'en' else alt)
    navs = ''.join(f'<a class="n" href="{h}">{l}</a>' for h, l in t['nav'] + ([T_WS_NAV[lang]] if WS_OPEN else []))
    ja_cur = 'true' if lang == 'ja' else 'false'
    en_cur = 'true' if lang == 'en' else 'false'
    return f'''<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
{'<meta name="robots" content="noindex">' if noindex else ''}
<meta name="theme-color" content="#15130f">
<meta property="og:type" content="{og_type}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{esc(img)}">
<meta property="og:site_name" content="{SHOP['name']}">
<meta property="og:locale" content="{'en_US' if lang == 'en' else 'ja_JP'}">
<meta name="twitter:card" content="summary_large_image">
<link rel="canonical" href="{url}">
<link rel="alternate" hreflang="ja" href="{ja_url}">
<link rel="alternate" hreflang="en" href="{en_url}">
<link rel="alternate" hreflang="x-default" href="{ja_url}">
<link rel="alternate" type="text/plain" title="llms.txt" href="/llms.txt">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,500;1,500&family=Shippori+Mincho+B1:wght@500;700;800&family=Zen+Kaku+Gothic+New:wght@400;500;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/site.css">
{jld(ld)}
{beacon}{track}
{verify}</head>
<body>
<div class="util">{t['util']}</div>
<header class="site"><div class="wrap">
  <a class="logo" href="{pre(lang)}/"><b>小判鮫</b><span>KOBANZAME</span></a>
  <div class="hnav">{navs}
    <nav class="lang" aria-label="言語 / Language"><a href="{alt if lang == 'en' else path}" lang="ja" aria-current="{ja_cur}">日本語</a><a href="{alt if lang == 'ja' else path}" lang="en" aria-current="{en_cur}">EN</a></nav>
  </div>
</div></header>
'''

def foot(lang):
    t = T[lang]
    legal = '　・　'.join(f'<a href="{h}">{l}</a>' for h, l in t['legal'])
    lic = ('古物商許可：' + SHOP['kobutsu']) if lang == 'ja' else 'Licensed secondhand dealer: Saitama Prefectural Public Safety Commission No. 431080060786'
    op = ('運営：' + SHOP['company']) if lang == 'ja' else 'Operated by Plug Inc.'
    hours = '12:00–20:00・月曜・火曜定休' if lang == 'ja' else '12:00–20:00, closed Mon & Tue'
    return f'''<footer class="site"><div class="wrap">
  <div class="big">Kobanzame</div>
  <div class="hair"></div>
  <div>古着屋 小判鮫／{ADDR[lang]}／{hours}<br>
    {op}　・　{lic}<br>
    <a href="{SHOP['instagram']}" rel="noopener">Instagram</a>　・　<a href="{SHOP['mercari']}" rel="noopener">メルカリShops</a>　・　<a href="{SHOP['gmaps']}" rel="noopener">{t['gm']}</a><br>
    {(chr(60) + 'a href="' + ('/en/workshop/' if lang == 'en' else '/workshop/') + '">' + ('Workshops' if lang == 'en' else 'ワークショップ') + chr(60) + '/a>　・　') if WS_OPEN else ''}<a href="{'/en/guide/' if lang == 'en' else '/guide/'}">{'Kawagoe vintage guide' if lang == 'en' else '川越で古着屋を探している方へ'}</a>　・　{legal}
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

# ---------- 一覧 ----------
live = [p for p in products if release(p) == 'live']
avail_live = [p for p in live if not is_sold(p)]
CATS_PRESENT = [c for c in ['outer', 'tops', 'bottoms', 'shoes', 'acc', 'other'] if any(cat_of(p) == c for p in live)]

def card_html(p, lang, lazy=True):
    t = T[lang]
    w = body_width(p)
    sold = is_sold(p)
    lz = ' loading="lazy"' if lazy else ''
    tag = '' if sold else f'<span class="tag">{t["one"]}</span>'
    wv = '' if w is None else f'{w:g}'
    return (f'<a class="card{" sold" if sold else ""}" href="{pre(lang)}/journal/{p["slug"]}/" data-cat="{cat_of(p)}" data-w="{wv}" data-sold="{1 if sold else 0}">'
            f'<div class="ph"><img src="{esc(thumb_of(p))}" alt="{esc(loc(p, "product_name", lang))}"{lz}>{tag}</div>'
            f'<div class="brand">{esc(p["brand"])}</div><div class="nm">{esc(loc(p, "product_name", lang))}</div>'
            f'<span class="fit" hidden></span>'
            f'<div class="pr">{money(site_price(p), lang)}<small>{t["tax"]}</small></div></a>')

def catrow(lang):
    t = T[lang]
    return ''.join(f'<button type="button" data-filter="{c}" aria-pressed="false">{t["cats"][c]}<small>{CAT_EN[c]}</small></button>' for c in CATS_PRESENT)

def finder(lang):
    t = T[lang]
    return f'''<div class="finder">
  <label for="myw">{t['finder_l']}</label>
  <input type="number" id="myw" inputmode="decimal" min="30" max="90" step="0.5" placeholder="55">
  <span>{t['finder_u']}</span>
  <label class="chk"><input type="checkbox" id="showsold"> {t['finder_sold']}</label>
  <button type="button" class="clear" id="clear">{t['finder_clear']}</button>
  <span class="hint">{t['finder_hint']}</span>
</div>'''

def list_js(lang):
    t = T[lang]
    msg = json.dumps({'empty_w': t['empty_w'], 'empty': t['empty'], 'fit': t['fit'], 'same': t['same'], 'unit': t['unit']}, ensure_ascii=False)
    return '''<script>
(function(){
  var M=''' + msg + ''';
  var filter=null, grid=document.getElementById('grid'); if(!grid) return;
  var myw=document.getElementById('myw'), showsold=document.getElementById('showsold'), cnt=document.getElementById('count');
  var empty=document.createElement('div'); empty.className='empty'; empty.hidden=true; grid.appendChild(empty);
  function apply(){
    var my=parseFloat(myw.value), n=0;
    grid.querySelectorAll('.card').forEach(function(c){
      var ok=(!filter||c.dataset.cat===filter)&&(showsold.checked||c.dataset.sold!=='1');
      var w=c.dataset.w===''?null:parseFloat(c.dataset.w), fit=c.querySelector('.fit');
      if(!isNaN(my)) ok=ok&&w!==null&&Math.abs(w-my)<=3;
      if(!isNaN(my)&&w!==null){var d=w-my; fit.textContent=M.fit.replace('{w}',w).replace('{d}',d===0?M.same:(d>0?'+':'')+d.toFixed(1)+'cm'); fit.hidden=false;} else fit.hidden=true;
      c.hidden=!ok; if(ok) n++;
    });
    empty.hidden=n>0;
    empty.textContent=!isNaN(my)?M.empty_w.replace('{w}',my):M.empty;
    if(cnt) cnt.textContent=n+M.unit;
    document.querySelectorAll('.catrow button').forEach(function(b){b.setAttribute('aria-pressed',String(b.dataset.filter===filter));});
  }
  document.querySelectorAll('.catrow button').forEach(function(b){b.addEventListener('click',function(){filter=(filter===b.dataset.filter?null:b.dataset.filter);apply();});});
  myw.addEventListener('input',apply); showsold.addEventListener('change',apply);
  document.getElementById('clear').addEventListener('click',function(){myw.value='';showsold.checked=false;filter=null;apply();});
  apply();
})();
</script>'''

def faq_ld(lang):
    return {'@type': 'FAQPage', '@id': BASE + pre(lang) + '/#faq',
            'mainEntity': [{'@type': 'Question', 'name': q, 'acceptedAnswer': {'@type': 'Answer', 'text': a}} for q, a in FAQ[lang]]}

hero_p = next((p for p in avail_live if cat_of(p) == 'outer'), avail_live[0] if avail_live else None)
HERO_SRCSET = (' srcset="/assets/hero-shop-800.jpg 800w, /assets/hero-shop.jpg 1200w" sizes="(min-width:900px) 55vw, 100vw" width="1200" height="1600"' if HERO_IMAGE == '/assets/hero-shop.jpg' else '')
HERO_SRC = HERO_IMAGE or (hero_p['images'][0] if hero_p else 'https://assets.mercari-shops-static.com/-/large/plain/2JX8ZaipBiPKYk5f7ApJKD.jpg')

for lang in ('ja', 'en'):
    t = T[lang]
    P = pre(lang)
    cards = '\n'.join(card_html(p, lang) for p in live)
    top_ld = {'@context': 'https://schema.org', '@graph': [org_node(), faq_ld(lang),
              {'@type': 'WebSite', '@id': BASE + P + '/#website', 'url': BASE + P + '/', 'name': SHOP['name'], 'inLanguage': lang,
               'publisher': {'@id': BASE + '/#store'}}]}
    faq_html = '\n'.join(f'    <details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>' for q, a in FAQ[lang])
    trust = ''.join(f'<div><b>{h}</b><span>{s.format(gm=SHOP["gmaps"])}</span></div>' for h, s in t['trust'])
    store_dl = ''.join(f'<dt>{k}</dt><dd>{ADDR[lang] + " ・ <a href=" + chr(34) + SHOP["gmaps"] + chr(34) + " rel=" + chr(34) + "noopener" + chr(34) + ">" + t["gm"] + "</a>" if v is None else v}</dd>' for k, v in t['store_dl'])
    hero_alt = '小判鮫の店内（川越・元町の古民家）' if lang == 'ja' else 'Inside Kobanzame, an old wooden house in Kawagoe'
    top = head(lang, t['top_title'], t['top_desc'], P + '/', extra_ld=top_ld) + f'''
<main>
  <section class="hero">
    <div class="wrap">
      <div class="hero-ph">
        <img class="hero-img" src="{esc(HERO_SRC)}"{HERO_SRCSET} alt="{hero_alt}" fetchpriority="high">
        <a class="maplink" href="{SHOP['gmaps']}" rel="noopener">{PIN}{t['map']}</a>
      </div>
      <div class="hero-copy">
        <h1>{t['hero_h']}</h1>
        <p>{t['hero_p']}</p>
        <a class="btn" href="#list">{t['hero_btn']}</a>
      </div>
    </div>
  </section>
  <div class="wrap">
    <div class="catrow" role="group">{catrow(lang)}</div>
    <div class="sec-head" id="list"><h2>{t['list_h']}<small>{t['list_s']}</small></h2><span class="count" id="count">{len(avail_live)}{t['unit']}</span></div>
    {finder(lang)}
    <div class="grid" id="grid">
{cards}
    </div>
    <div class="trust">{trust}</div>
    <section class="store" id="store">
      <div><h2>The Shop</h2><p>{t['store_p']}</p></div>
      <dl>{store_dl}</dl>
    </section>
    <section class="faq" id="faq">
      <div class="sec-head" style="margin-top:0"><h2>Q&amp;A<small>{t['faq_s']}</small></h2></div>
{faq_html}
    </section>
  </div>
</main>
{list_js(lang)}
''' + foot(lang)
    write(P + '/index.html', top)

    # ジャーナル（一覧の別入口）
    list_ld = {'@context': 'https://schema.org', '@graph': [org_node(),
               {'@type': 'CollectionPage', 'name': t['jr_title'], 'url': BASE + P + '/journal/', 'inLanguage': lang,
                'mainEntity': {'@type': 'ItemList', 'itemListElement': [
                    {'@type': 'ListItem', 'position': i + 1, 'url': BASE + P + f"/journal/{p['slug']}/", 'name': loc(p, 'product_name', lang)}
                    for i, p in enumerate(live)]}}]}
    jl = head(lang, t['jr_title'], t['jr_desc'], P + '/journal/', extra_ld=list_ld) + f'''
<main class="wrap">
  <div class="crumb"><a href="{P}/">HOME</a><span>／</span><span>JOURNAL</span></div>
  <div class="catrow" role="group" style="margin-top:4px">{catrow(lang)}</div>
  <div class="sec-head"><h2>{t['journal_h']}<small>{t['journal_s']}</small></h2><span class="count" id="count">{len(avail_live)}{t['unit']}</span></div>
  {finder(lang)}
  <div class="grid" id="grid">
{cards}
  </div>
  <div style="height:72px"></div>
</main>
{list_js(lang)}
''' + foot(lang)
    write(P + '/journal/index.html', jl)

    # 商品ページ
    GAL_JS = '''<script>
(function(){
  var g=document.getElementById('gal'), c=document.getElementById('galcount'); if(g&&c){
  var n=g.children.length;
  function upd(){var w=g.firstElementChild.getBoundingClientRect().width+8; c.textContent=(Math.round(g.scrollLeft/w)+1)+' / '+n;}
  g.addEventListener('scroll',upd,{passive:true}); upd();}
  var hb=document.getElementById('holdbtn'), hx=document.getElementById('holdbox');
  if(hb&&hx){hb.addEventListener('click',function(){hx.hidden=!hx.hidden; hb.setAttribute('aria-expanded',String(!hx.hidden));});}
})();
</script>'''
    for p in products:
        rel = release(p)
        if rel == 'hidden':
            continue
        path = P + f"/journal/{p['slug']}/"
        price = site_price(p)
        sold = is_sold(p)
        name = loc(p, 'product_name', lang)
        offer = {'@type': 'Offer', 'price': str(price), 'priceCurrency': 'JPY',
                 'availability': 'https://schema.org/SoldOut' if sold else 'https://schema.org/InStock',
                 'itemCondition': 'https://schema.org/' + p.get('item_condition', 'UsedCondition'), 'url': BASE + path,
                 'seller': {'@id': BASE + '/#store'},
                 'shippingDetails': {'@type': 'OfferShippingDetails',
                                     'shippingRate': {'@type': 'MonetaryAmount', 'value': '0', 'currency': 'JPY'},
                                     'shippingDestination': {'@type': 'DefinedRegion', 'addressCountry': 'JP'},
                                     'deliveryTime': {'@type': 'ShippingDeliveryTime',
                                                      'handlingTime': {'@type': 'QuantitativeValue', 'minValue': 0, 'maxValue': 3, 'unitCode': 'DAY'},
                                                      'transitTime': {'@type': 'QuantitativeValue', 'minValue': 1, 'maxValue': 3, 'unitCode': 'DAY'}}}}
        author = {'@type': 'Person', 'name': '龍' if lang == 'ja' else 'Ryu', 'jobTitle': '小判鮫オーナー・専属バイヤー' if lang == 'ja' else 'Owner & buyer, Kobanzame', 'worksFor': {'@id': BASE + '/#store'}}
        ld = {'@context': 'https://schema.org', '@graph': [
            {'@type': 'Product', '@id': BASE + path + '#product', 'name': name, 'sku': p['sku'],
             'description': loc(p, 'summary_text', lang), 'image': [abs_url(u) for u in p['images']], 'brand': {'@type': 'Brand', 'name': p['brand']},
             'material': p.get('material', ''), 'category': p.get('category', ''), 'offers': offer,
             **({'color': color_of(p)} if color_of(p) else {}), **({'size': size_of(p)} if size_of(p) else {}),
             'audience': {'@type': 'PeopleAudience', 'suggestedGender': gender_of(p)},
             'additionalProperty': [{'@type': 'PropertyValue', 'name': k, 'value': v} for k, v in p.get('spec', []) if k not in ('発送',)]},
            {'@type': 'BlogPosting', '@id': BASE + path + '#article', 'headline': loc(p, 'title', lang), 'image': abs_url(p['images'][0]),
             'datePublished': p.get('published_date', TODAY), 'dateModified': TODAY, 'inLanguage': lang,
             'author': author, 'publisher': {'@id': BASE + '/#store'}, 'about': {'@id': BASE + path + '#product'}, 'mainEntityOfPage': BASE + path},
            {'@type': 'BreadcrumbList', 'itemListElement': [
                {'@type': 'ListItem', 'position': 1, 'name': 'HOME', 'item': BASE + P + '/'},
                {'@type': 'ListItem', 'position': 2, 'name': t['cats'][cat_of(p)], 'item': BASE + P + '/#list'},
                {'@type': 'ListItem', 'position': 3, 'name': name, 'item': BASE + path}]},
            org_node()]}
        imgs = p['images']
        gallery = ''.join('<img src="{}" alt="{} {}"{}>'.format(esc(u), esc(name), i + 1, ' fetchpriority="high"' if i == 0 else ' loading="lazy"')
                          for i, u in enumerate(imgs))
        points = ''.join(f'<li>{esc(s)}</li>' for s in loc(p, 'summary_points', lang) if not s.startswith('価格'))
        spec = ''.join(f'<dt>{esc(k)}</dt><dd>{esc(v)}</dd>' for k, v in loc(p, 'spec', lang))
        w = body_width(p)
        facts = f'<span class="soldf">SOLD</span>' if sold else f'<span class="one">{t["stock1"]}</span>'
        rk = cond_rank(p, lang)
        facts += (f'<span>{rk}</span>' if rk else '') + (f'<span>{t["width"].format(w=f"{w:g}")}</span>' if w is not None else '')
        if sold:
            buy, bar = f'<span class="soldout">{t["soldout"]}</span>', ''
        elif p['links'].get('square'):
            sq = esc(p['links']['square'])
            buy = f'<a class="btn kin" href="{sq}" rel="noopener">{t["buy"]}</a>'
            bar = f'<div class="bar"><b>{money(price, lang)}</b><a class="btn kin" href="{sq}" rel="noopener">{t["buy_s"]}</a></div>'
        else:
            buy, bar = f'<span class="soldout">{t["prep"]}</span>', ''
        hold = '' if sold else f'''<button type="button" class="btn ghost" id="holdbtn" aria-expanded="false" aria-controls="holdbox">{t['hold_btn'].format(n=HOLD_DAYS)}</button>
        <div class="holdbox" id="holdbox" hidden>
          <p>{t['hold_p'].format(n=HOLD_DAYS)}</p>
          <p><code>{esc(t['hold_code'].format(sku=p['sku']))}</code></p>
          <p>{t['hold_to']}：<a href="{SHOP['instagram']}" rel="noopener">Instagram（{SHOP['ig_handle']}）</a> ／ {t['hold_mail']} <code>{SHOP['email']}</code></p>
          <p class="ship">{t['hold_note']}</p>
        </div>'''
        noen = f'<p class="noen">{t["no_en"]}</p>' if (lang == 'en' and not has_en(p)) else ''
        draft_banner = f'<div class="draftnote">{t["draft"]}</div>' if rel == 'draft' else ''
        relp = sorted([x for x in avail_live if x['sku'] != p['sku']], key=lambda x: cat_of(x) != cat_of(p))[:3]
        rel_cards = ''.join(card_html(x, lang) for x in relp)
        related = f'<section class="related"><h2>Also One of One<small>{t["related"]}</small></h2><div class="grid">{rel_cards}</div></section>' if rel_cards else ''
        page = head(lang, f"{loc(p, 'title', lang)}｜{SHOP['name']}", loc(p, 'summary_text', lang), path, og_type='article',
                    image=imgs[0], extra_ld=ld, noindex=(p.get('noindex', False) or rel == 'draft')) + f'''{draft_banner}
<main class="wrap">
  <div class="crumb"><a href="{P}/">HOME</a><span>／</span><a href="{P}/#list">{t['cats'][cat_of(p)]}</a><span>／</span><span>{esc(p['sku'])}</span></div>
  <div class="pdp">
    <div>
      <div class="gal{' one' if len(imgs) == 1 else ''}" id="gal">{gallery}</div>
      <div class="galcount" id="galcount"></div>
    </div>
    <div class="info">
      <div class="brand">{esc(p['brand'])}</div>
      <h1>{esc(name)}</h1>
      <div class="ttl">{esc(loc(p, 'title', lang))}</div>
      <div class="sku">ITEM NO. {esc(p['sku'])}</div>
      <div class="price">{money(price, lang)}<small>{t['tax_ship']}</small></div>
      <div class="facts">{facts}</div>
      {noen}
      <div class="buybox">
        {buy}
        {hold}
        <div class="ship">{t['ship']}</div>
      </div>
      <ul class="points">{points}</ul>
      <details open><summary>{t['story']}</summary><div class="story"><p>{esc(loc(p, 'lead', lang))}</p>
{loc(p, 'body_html', lang)}</div></details>
      <details><summary>{t['specs']}</summary><dl class="spec">{spec}</dl><p class="howto">{t['howto']}</p></details>
      <details><summary>{t['delivery']}</summary><div class="story"><p>{t['delivery_p']}</p></div></details>
      <div class="byline">{t['byline']}</div>
    </div>
  </div>
  {related}
</main>
{bar}
{GAL_JS}
''' + foot(lang)
        write(path + 'index.html', page)

    # 404
    if lang == 'ja':
        nf = head('ja', 'ページが見つかりません｜古着屋 小判鮫 KOBANZAME', 'お探しのページは見つかりませんでした。', '/404.html', noindex=True) + f'''
<main class="wrap nf"><h1>Not Found</h1><p>{t['nf_p']}</p><a class="btn" href="/#list">{t['nf_btn']}</a></main>
''' + foot('ja')
        write('/404.html', nf)

# ---------- 特定商取引法に基づく表記（日本語） ----------
LAW = [
    ('販売業者', SHOP['company']), ('運営統括責任者', '嶋崎龍'), ('所在地', ADDR['ja']),
    ('電話番号', '請求があった場合には遅滞なく開示いたします。'), ('メールアドレス', SHOP['email']),
    ('販売価格', '各商品ページに税込価格で表示しています。'),
    ('商品代金以外の必要料金', '送料は販売価格に含まれます（当店負担）。決済手数料はかかりません。'),
    ('支払方法', 'クレジットカード（Square の決済ページで決済）'), ('支払時期', 'ご注文時に決済が確定します。'),
    ('引渡時期', 'ご注文（決済）の確認後、3日以内（定休日を除く）に発送します。'), ('販売数量', '各商品とも1点限りです。'),
    ('返品・交換', '古着・一点ものの性質上、お客様都合による返品・交換はお受けしておりません。商品説明と著しく異なる場合や当店の発送間違いの場合は、商品到着後4日以内にメールでご連絡ください。返品送料は当店が負担し、返金または交換にて対応いたします。'),
    ('申込みの撤回・解除', '通信販売にはクーリング・オフ制度は適用されません。上記「返品・交換」の条件に従います。'),
    ('品切れの場合', '店頭・他の販路で先に売れた場合は、ご注文をお受けできないことがあります。その際はご連絡のうえ全額返金いたします。'),
    ('古物商許可', f"{SHOP['kobutsu']}（{SHOP['company']}）"),
]
law_html = ''.join(f'<dt>{esc(k)}</dt><dd>{esc(v)}</dd>' for k, v in LAW)
write('/tokushoho/index.html', head('ja', '特定商取引法に基づく表記｜古着屋 小判鮫', '古着屋 小判鮫（運営：株式会社プラグ）の特定商取引法に基づく表記。', '/tokushoho/') + f'''
<main class="wrap page lawtable"><h1>特定商取引法に基づく表記</h1><dl>{law_html}</dl><p style="color:var(--usu);font-size:13px;margin-top:24px">制定：2026年9月30日</p></main>
''' + foot('ja'))

write('/privacy/index.html', head('ja', 'プライバシーポリシー｜古着屋 小判鮫', '古着屋 小判鮫（運営：株式会社プラグ）のプライバシーポリシー。', '/privacy/') + f'''
<main class="wrap page">
  <h1>プライバシーポリシー</h1>
  <p>古着屋 小判鮫（運営：{SHOP['company']}。以下「当店」）は、お客様の個人情報を適切に取り扱います。</p>
  <h2>取得する情報</h2><p>ご注文・お問い合わせ・お取り置き・販売（外部プラットフォームを含む）に際して、お名前・連絡先・配送先など、取引に必要な範囲の情報を取得します。</p>
  <h2>利用目的</h2><p>商品の発送、お取り置き、お問い合わせへの対応、取引に必要なご連絡のために利用し、目的の範囲を超えて利用しません。</p>
  <h2>決済について</h2><p>本サイトでのお支払いは Square 株式会社の決済ページで処理されます。当店はクレジットカード番号を取得・保存しません。</p>
  <h2>第三者提供</h2><p>法令に基づく場合を除き、ご本人の同意なく第三者に提供しません。配送など取引に必要な範囲で委託先に提供する場合があります。</p>
  <h2>アクセス解析</h2><p>サイトの改善のためアクセス状況を測定することがあります。個人を特定する情報は含みません。</p>
  <h2>お問い合わせ</h2><p>本ポリシーに関するお問い合わせは {SHOP['email']} までお願いいたします。</p>
  <p style="color:var(--usu);font-size:13px;margin-top:20px">制定：2026年9月／改定：2026年10月</p>
</main>
''' + foot('ja'))

# ---------- 英語の法務ページ（要約。正式な表記は日本語ページ） ----------
write('/en/legal/index.html', head('en', 'Legal notice & privacy | Kobanzame', 'Seller information and privacy summary for Kobanzame (Plug Inc.).', '/en/legal/') + f'''
<main class="wrap page">
  <h1>Legal notice &amp; privacy</h1>
  <p>This is an English summary. The official notices are the Japanese pages: <a href="/tokushoho/">特定商取引法に基づく表記</a> and <a href="/privacy/">プライバシーポリシー</a>.</p>
  <h2>Seller</h2><p>Plug Inc. (Kobanzame). Responsible: Ryu Shimazaki. {ADDR['en']}. Email: {SHOP['email']}. Phone number disclosed on request.</p>
  <h2>Prices and payment</h2><p>Prices are shown including tax and domestic shipping. Payment by credit card through Square's checkout; the order is confirmed at payment.</p>
  <h2>Delivery</h2><p>Dispatched within 3 days of payment (excluding closed days). Online checkout ships within Japan; contact us before buying for overseas shipping.</p>
  <h2>Returns</h2><p>No returns for change of mind on one-of-a-kind vintage items. If the item differs significantly from the description or we sent the wrong item, email us within 4 days of arrival; we cover return shipping and refund or exchange.</p>
  <h2>Licence</h2><p>Licensed secondhand dealer: Saitama Prefectural Public Safety Commission No. 431080060786.</p>
  <h2>Privacy</h2><p>We collect only what an order, hold request or inquiry needs (name, contact, delivery address) and use it only for that purpose. Card details are processed by Square; we never receive or store card numbers. We do not share personal data without consent except as required by law or for delivery.</p>
</main>
''' + foot('en'))

# ---------- ワークショップのページ（WS_FROM 以降だけ作る） ----------
if WS_OPEN:
    for lang in ('ja', 'en'):
        P = pre(lang)
        path = P + '/workshop/'
        if lang == 'ja':
            title = 'ワークショップ｜古着屋 小判鮫（川越・元町の古民家）'
            desc = '川越・元町の古民家古着屋 小判鮫のワークショップ。真鍮バングル、天然石ビーズブレスレット。期間限定価格。ご予約はオンラインで。'
            h1, intro = 'ワークショップ', '小判鮫の店内で、ものづくりの時間を。どちらも完成品はその場でお持ち帰りいただけます。'
            limited = '期間限定価格（税込）'
            end_note = '期間限定価格の終了時期は、決まり次第このページとInstagramでお知らせします。'
            meta = '所要 約{m}分・1回 最大{n}名'
            btn = '予約する（日時を選ぶ）'
            place = f'会場：古着屋 小判鮫（{ADDR["ja"]}）／定休日 月曜・火曜'
        else:
            title = 'Workshops | Kobanzame, Kawagoe'
            desc = 'Workshops at Kobanzame, a vintage shop in an old wooden house in Kawagoe: brass bangle and natural stone bead bracelet. Limited-time prices. Book online.'
            h1, intro = 'Workshops', 'Make something in our old wooden shop. You take your piece home the same day.'
            limited = 'limited-time price, tax incl.'
            end_note = 'We will announce on this page and on Instagram when the limited-time prices end.'
            meta = 'About {m} min · up to {n} people per session'
            btn = 'Book a time'
            place = f'Venue: Kobanzame, {ADDR["en"]} / closed Mondays and Tuesdays'
        cards, svc = '', []
        for w in WORKSHOPS:
            x = w[lang]
            notes = ''.join(f'<li>{esc(n)}</li>' for n in x['notes'])
            cards += (f'<article id="{w["id"]}"><h2>{esc(x["name"])}</h2>'
                      f'<div class="price">{money(w["price"], lang)}<small>{limited}</small></div>'
                      f'<div class="meta">{meta.format(m=w["minutes"], n=w["max"])}</div>'
                      f'<p>{esc(x["lead"])}</p><ul>{notes}</ul>'
                      f'<a class="btn kin" href="{w["reserve"]}" rel="noopener">{btn}</a></article>')
            svc.append({'@type': 'Service', 'name': x['name'], 'description': x['lead'], 'provider': {'@id': BASE + '/#store'},
                        'areaServed': '川越市' if lang == 'ja' else 'Kawagoe',
                        'offers': {'@type': 'Offer', 'price': str(w['price']), 'priceCurrency': 'JPY', 'url': w['reserve']}})
        ld = {'@context': 'https://schema.org', '@graph': [org_node()] + svc}
        write(path + 'index.html', head(lang, title, desc, path, extra_ld=ld) + f'''
<main class="wrap page">
  <h1>{h1}</h1>
  <p>{esc(intro)}</p>
  <div class="ws">{cards}</div>
  <p style="color:var(--usu);font-size:13px;margin-top:20px">{esc(end_note)}<br>{esc(place)}</p>
</main>
''' + foot(lang))

# ---------- 川越で古着屋を探している人向けの案内ページ（AI検索・検索エンジン対策 2026-10-06） ----------
# AIや検索で「川越 古着屋」と聞かれたときに、そのまま答えになる文章を1ページにまとめる。
# 他店との比較や「川越で一番」などの言い切りは書かない（景表法・事実確認できないため）。
_pr = sorted(site_price(p) for p in avail_live)
GUIDE = {
 'ja': {
  'path': '/guide/', 'title': '川越で古着屋を探している方へ｜古着屋 小判鮫（川越・元町の古民家）',
  'desc': '埼玉県川越市元町の古民家古着屋 小判鮫の案内。場所・営業時間・定休日・扱っている古着・価格帯・取り置き・通販の買い方をまとめました。',
  'h1': '川越で古着屋を探している方へ',
  'lead': '古着屋 小判鮫（こばんざめ／KOBANZAME）は、埼玉県川越市元町にある古着屋です。築約80年の古民家をそのまま使った店内に、国内外で買い付けたヴィンテージ古着と、オリジナルのリメイクアクセサリー「GAW」を並べています。川越観光のついでに立ち寄っていただける場所です。',
  'secs': [
   ('場所と営業時間', f'住所は{ADDR["ja"]}。蔵造りの町並みと同じ、川越の元町エリアにあります。営業は12:00〜20:00、定休日は毎週月曜日・火曜日です。臨時の休みや営業時間の変更はInstagram（{SHOP["ig_handle"]}）でお知らせします。'),
   ('どんな古着があるか', 'アメリカ・ヨーロッパなどのヴィンテージ古着を中心に、メンズ・レディースの両方を扱っています。アウター、シャツやTシャツ、ワンピース、靴、小物まで。ブランドや流行ではなく、素材・質感・その一点にしかない雰囲気で選んでいるので、すべて一点ものです。'),
   ('価格の目安', (f'このサイトに掲載中の一点ものは、{money(_pr[0], "ja")}〜{money(_pr[-1], "ja")}（税込・送料込み）です。店頭の価格は商品ごとに異なります。' if _pr else '価格は商品ごとに異なります。サイトに掲載中の商品ページでご確認ください。')),
   ('新着入荷', '毎週水曜日に新しい一点ものが入ります。このサイトにも水曜日の朝に新着を掲載しています。'),
   ('GAW（オリジナルのリメイクアクセサリー）', '古いスプーンなどの素材を、ペンダントやバングルなどに作り直した、小判鮫オリジナルのアクセサリーです。こちらも一点ものです。'),
   ('来店前に見たい・取り置きしたいとき', f'サイトの商品ページにある「店頭で見たい・取り置きする」から、InstagramのDMかメールでご連絡いただくと、店頭で{HOLD_DAYS}日間お取り置きします。'),
   ('遠くて行けないとき', 'このサイトに載っている商品は、クレジットカード（Square決済）でそのまま購入できます。送料込みで、決済確認後3日以内（定休日を除く）に川越の店舗から発送します。メルカリShopsでも販売しています。'),
   ('サイズ選びのコツ', '実寸は平置きで測っています。お手持ちのいちばん気に入っている服の身幅（脇の下から脇の下まで）を測って比べると、サイズの失敗が減ります。トップページの「手持ちの服の身幅」に数字を入れると、近いサイズの服だけを表示できます。'),
  ],
  'faq': [
   ('川越の小判鮫はどこにありますか？', f'{ADDR["ja"]}にあります。築約80年の古民家で営業している古着屋です。'),
   ('定休日はいつですか？', '毎週月曜日・火曜日が定休日です。営業時間は12:00〜20:00です。'),
   ('メンズもレディースもありますか？', 'あります。メンズ・レディースどちらのヴィンテージ古着も扱っています。'),
   ('新しい商品はいつ入りますか？', '毎週水曜日に新着が入ります。'),
   ('川越まで行けなくても買えますか？', 'このサイトからクレジットカードで購入できます（送料込み）。メルカリShopsでも販売しています。'),
  ],
  'cta': '掲載中の一点ものを見る', 'back': '/#list', 'crumb': '川越の古着屋 案内',
 },
 'en': {
  'path': '/en/guide/', 'title': 'Looking for a vintage shop in Kawagoe? | Kobanzame',
  'desc': 'A guide to Kobanzame, a vintage clothing shop in an old wooden house in Motomachi, Kawagoe, Saitama: location, hours, what we carry, prices, holds and buying online.',
  'h1': 'Looking for a vintage shop in Kawagoe?',
  'lead': 'Kobanzame is a vintage clothing shop in Motomachi, Kawagoe, Saitama, set in an 80-year-old wooden house. We carry vintage clothing sourced in Japan and abroad, and GAW, our own line of remade accessories. It is an easy stop while you explore Kawagoe.',
  'secs': [
   ('Location and hours', f'{ADDR["en"]}, in the Motomachi area of Kawagoe, the same area as Kawagoe’s old kurazukuri (clay-walled merchant house) streets. Open 12:00–20:00, closed every Monday and Tuesday. Changes are announced on Instagram ({SHOP["ig_handle"]}).'),
   ('What you will find', 'Mostly vintage clothing from the US and Europe, for men and women: outerwear, shirts and tees, dresses, shoes and small goods. We choose by material, texture and the feel of each piece rather than brand or trend, so everything is one of a kind.'),
   ('Prices', (f'Pieces listed on this site range from {money(_pr[0], "en")} to {money(_pr[-1], "en")} (tax and domestic shipping included). In-store prices vary by item.' if _pr else 'Prices vary by item. See each item page on this site.')),
   ('New arrivals', 'New pieces arrive every Wednesday, and go up on this site on Wednesday morning.'),
   ('GAW', 'Our own accessory line: old materials such as spoons remade into pendants, bangles and more. Each one is one of a kind.'),
   ('Holding a piece', f'Use "See it in the shop / hold it" on any item page and send us an Instagram DM or email. We hold it at the shop for {HOLD_DAYS} days.'),
   ('Buying online', 'Pieces on this site can be bought by credit card through Square. Online checkout ships within Japan; for overseas shipping, please contact us before buying.'),
  ],
  'faq': [
   ('Where is Kobanzame?', f'At {ADDR["en"]}, in an 80-year-old wooden house.'),
   ('When is it closed?', 'Every Monday and Tuesday. Open 12:00–20:00 on other days.'),
   ('Do you have both men\'s and women\'s clothing?', 'Yes, both.'),
   ('When do new pieces arrive?', 'Every Wednesday.'),
  ],
  'cta': 'See the pieces', 'back': '/en/#list', 'crumb': 'Kawagoe vintage guide',
 },
}
for lang, g in GUIDE.items():
    P = pre(lang)
    g_faq_ld = {'@type': 'FAQPage', '@id': BASE + g['path'] + '#faq',
                'mainEntity': [{'@type': 'Question', 'name': q, 'acceptedAnswer': {'@type': 'Answer', 'text': a}} for q, a in g['faq']]}
    g_ld = {'@context': 'https://schema.org', '@graph': [
        org_node(), g_faq_ld,
        {'@type': 'WebPage', '@id': BASE + g['path'] + '#page', 'url': BASE + g['path'], 'name': g['title'], 'inLanguage': lang,
         'about': {'@id': BASE + '/#store'}, 'dateModified': TODAY},
        {'@type': 'BreadcrumbList', 'itemListElement': [
            {'@type': 'ListItem', 'position': 1, 'name': 'HOME', 'item': BASE + P + '/'},
            {'@type': 'ListItem', 'position': 2, 'name': g['crumb'], 'item': BASE + g['path']}]}]}
    secs = ''.join(f'  <h2>{esc(h)}</h2><p>{esc(b)}</p>\n' for h, b in g['secs'])
    gfaq = ''.join(f'  <details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>\n' for q, a in g['faq'])
    write(g['path'] + 'index.html', head(lang, g['title'], g['desc'], g['path'], extra_ld=g_ld) + f'''
<main class="wrap page">
  <h1>{esc(g['h1'])}</h1>
  <p>{esc(g['lead'])}</p>
{secs}  <section class="faq" id="faq"><h2>Q&amp;A</h2>
{gfaq}  </section>
  <p style="margin-top:28px"><a class="btn" href="{g['back']}">{esc(g['cta'])}</a></p>
</main>
''' + foot(lang))

# ---------- robots.txt / sitemap.xml / llms.txt ----------
pages = []
for lang in ('ja', 'en'):
    P = pre(lang)
    pages += [P + '/', P + '/journal/'] + [P + f"/journal/{p['slug']}/" for p in live]
pages += ['/tokushoho/', '/privacy/', '/en/legal/', '/guide/', '/en/guide/'] + (['/workshop/', '/en/workshop/'] if WS_OPEN else [])
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
items = '\n'.join(f"- [{p['title']}]({BASE}/journal/{p['slug']}/): {p['product_name']}。{money(site_price(p), 'ja')}（税込・送料込み）。{'販売終了' if is_sold(p) else '在庫1点'}"
                  for p in live)
write('/llms.txt', f'''# 古着屋 小判鮫（KOBANZAME）

> 埼玉県川越市元町1-14-5の、築約80年の古民家で営業している古着屋。国内外で買い付けたヴィンテージ古着と、小判鮫オリジナルのリメイクアクセサリー「GAW」を扱う。商品はすべて一点もの。運営は{SHOP['company']}。英語ページは {BASE}/en/ 。

## 基本情報
- 店名: 古着屋 小判鮫（こばんざめ / KOBANZAME）
- 所在地: {ADDR['ja']}（地図: {SHOP['gmaps']}）
- 営業時間: 12:00〜20:00（月曜・火曜定休）
- 新着: 毎週水曜
- 取扱い: ヴィンテージ古着（メンズ・レディース）、ヨーロッパ・アメリカの古着、オリジナルのリメイクアクセサリー「GAW」
- 買い方: 店頭／このサイト（クレジットカード・Square決済・送料込み）／メルカリShops
- 取り置き: 店頭で{HOLD_DAYS}日間（InstagramのDMかメールで依頼）
- 発送: 決済確認後3日以内（月曜・火曜の定休日を除く）
- 古物商許可: {SHOP['kobutsu']}
- お問い合わせ: {SHOP['email']}
- Instagram: {SHOP['instagram']}

## ページ
- [トップ・よくある質問]({BASE}/)
- [ジャーナル]({BASE}/journal/)
- [川越で古着屋を探している方へ（案内）]({BASE}/guide/)
{'- [ワークショップ（真鍮バングル・天然石ビーズブレスレット・期間限定価格）](' + BASE + '/workshop/)' + chr(10) if WS_OPEN else ''}- [English]({BASE}/en/)
- [特定商取引法に基づく表記]({BASE}/tokushoho/)
- [プライバシーポリシー]({BASE}/privacy/)

## 掲載中の商品
{items}
''')
# ---------- Google Merchant Center 用の商品一覧（2026-10-06 龍さん決定A） ----------
# Googleのショッピング・AIモード・Googleレンズに無料で載せるための商品データ。
# 載せるのは「公開中・売れていない・購入ボタンがある」商品だけ。売れたら次の再生成で一覧から消える。
# 価格はサイトの表示価格（税込・送料込み）と同じ。古着にはJANコードが無いので identifier_exists=no。
def _x(s):
    return html.escape(str(s), quote=True)
feed_items = []
for p in avail_live:
    if not p['links'].get('square'):
        continue
    imgs = [abs_url(u) for u in p['images'][:11]]
    cond = 'new' if p.get('item_condition') == 'NewCondition' else 'used'
    b = brand_of(p)
    fields = [
        ('g:id', p['sku']), ('title', p['product_name'][:150]),
        ('description', p['summary_text'][:5000]),
        ('link', BASE + '/journal/' + p['slug'] + '/'), ('g:image_link', imgs[0]),
    ] + [('g:additional_image_link', u) for u in imgs[1:]] + [
        ('g:availability', 'in_stock'), ('g:price', f"{site_price(p)} JPY"), ('g:condition', cond),
    ] + ([('g:brand', b)] if b else []) + [
        ('g:identifier_exists', 'no'), ('g:product_type', p.get('category', '').replace('／', ' > ')),
    ] + ([('g:gender', gender_of(p)), ('g:age_group', 'adult')] if not p.get('category', '').startswith('小物') else []) + ([('g:color', color_of(p))] if color_of(p) else []) + ([('g:size', size_of(p))] if size_of(p) else [])
    xml = ''.join(f'      <{k}>{_x(v)}</{k}>\n' for k, v in fields)
    xml += '      <g:shipping><g:country>JP</g:country><g:price>0 JPY</g:price></g:shipping>\n'
    feed_items.append('    <item>\n' + xml + '    </item>\n')
write('/feed/google.xml', '<?xml version="1.0" encoding="UTF-8"?>\n'
      '<rss version="2.0" xmlns:g="http://base.google.com/ns/1.0">\n  <channel>\n'
      f'    <title>{_x(SHOP["name"])}</title>\n    <link>{BASE}/</link>\n'
      '    <description>古着屋 小判鮫の一点もの（税込・送料込み）</description>\n'
      + ''.join(feed_items) + '  </channel>\n</rss>\n')

print('built', len(pages), 'pages', '/ feed', len(feed_items), 'items')
