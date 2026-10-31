# -*- coding: utf-8 -*-
"""小判鮫 公式サイト 生成スクリプト v2.1（2026-10-04 改訂）
GitHub Actions が data/products.json か このファイルの変更時（mainブランチ）に実行する。

v2で変わったこと
- 見た目：古民家の黒い壁に合わせた「墨・生成り・古金」の3色＋濃淡1色。見出しは明朝、本文は角ゴシック
- 日本語／English の切り替え（英語ページは /en/ 以下。英語の商品説明は data/products_en.json）
- 公開の流れ（A案）：products.json の "release" が "draft" の商品は下書き＝ページは作るが検索に出さず一覧にも出さない。
  水曜夜（20時台）のGASが "draft" → "live" に書き換えると一覧に並ぶ（"release" が無い商品は従来どおり published で判断）
- 売れた商品（status=sold）は一覧から消さずSOLDで残す（「売れた一点ものも見る」で表示）
- サイズで探す（身幅±3cm）／こちらも一点もの（取り置きは2026-10-07に廃止）
- 価格：ADD_TAX=True で「Square登録価格（税抜）×1.1 を10円単位に切り上げ」を税込として表示（2026-10-06 から True）。
  ※Squareのオンライン決済にも消費税がかかる設定にしてから True にする（表示と請求額をそろえるため）
- アクセス解析：CF_BEACON_TOKEN に Cloudflare Web Analytics のトークンを入れると全ページに計測タグが入る
- トップの写真：HERO_IMAGE（店内の写真）。写真の上にGoogleマップへのリンク
"""
import json, os, html, re, math, datetime, glob, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = 'https://kobanzame-site.pages.dev'   # 独自ドメイン取得後はここだけ差し替える
TODAY = os.environ.get('SITE_TODAY') or datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y-%m-%d')

ADD_TAX = True           # 2026-10-06 龍さん決定B：Square登録価格は税抜 → 表示・請求とも ×1.1 を10円単位に切り上げ（63番の QP.ADD_TAX と必ず同じにする）
TAX_RATE = 0.10
CF_BEACON_TOKEN = ''     # Cloudflare Web Analytics のトークン（空なら計測タグを入れない）
ANALYTICS_URL = 'https://script.google.com/macros/s/AKfycbxxYc9kZztdwiWOvefrpY6mPHlRUlqLb2SndthCdAUn7BeBXAgZO3i6_JoDxyFQiv3q/exec'       # 64番（自前の簡易計測）のウェブアプリURL。空なら計測しない（2026-10-06 龍さん決定A）
GSC_VERIFY = '2pVJ6dksHBkvBUmm0l3gbrdw8Rgpz4v7zoq4X3eL7ys'          # Google Search Console の確認コード（content="…" の中身だけ。空ならタグを入れない）
BING_VERIFY = ''         # Bing Webmaster Tools の確認コード（同上。Search Consoleから取り込むなら空のままでよい）
HOLD_DAYS = 2            # 店頭取り置きの日数（2026-10-04 決定）※2026-10-07 取り置きは廃止（HOLD_ENABLED=False）
HOLD_ENABLED = False     # 2026-10-07 龍さん決定：一点物なのでサイトも店頭も取り置き不可・先着順
# 2026-10-13 龍さん決定（10/8の「毎日営業」を置き換え）：11月1日から 火〜日 13:00–20:00・月曜定休（祝日の月曜は営業）・7〜8月は22:00まで
NEWHOURS_FROM = '2026-11-01'   # この日以降のビルドで文言が切り替わる
NEWHOURS = TODAY >= NEWHOURS_FROM
NOTICE_FROM = '2026-10-14'     # この日以降〜10/31のビルドで「11/1から」のお知らせを出す（龍さんの告知と合わせる）
NOTICE = (not NEWHOURS) and TODAY >= NOTICE_FROM
# 祝日の月曜（営業する日）。本日営業/定休バッジと案内文で使う。毎年1月に翌年分を足す（2026-10-30 2027-11-22は祝日ではないので外した。2027年の勤労感謝の日11/23は火曜）
HOLIDAY_MONDAYS = ['2026-11-23', '2027-01-11', '2027-03-22', '2027-05-03', '2027-07-19', '2027-09-20', '2027-10-11']
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
    # 2026-10-15 GoogleマップのGBP（古着屋 小判鮫）を直接指すURL。AIが「サイトの店＝マップの店」と結び付けられるよう構造化データに入れる
    'gplace': 'https://www.google.com/maps?cid=18204266440623225705',
}
# 2026-10-15 IndexNow（Bing・Yandexなどに「ページが更新された」と直接知らせる仕組み・無料）の鍵。
# 鍵ファイル /<鍵>.txt をサイトに置き、.github/workflows/indexnow.yml が更新のたびに知らせる。秘密情報ではない（公開して使うもの）
INDEXNOW_KEY = 'b3c3d1957f5e906d6ace2608040a7e04'
ADDR = {'ja': '〒350-0062 埼玉県川越市元町1-14-5', 'en': '1-14-5 Motomachi, Kawagoe, Saitama 350-0062, Japan'}

products = json.load(open(os.path.join(ROOT, 'data/products.json'), encoding='utf-8'))
_en_path = os.path.join(ROOT, 'data/products_en.json')
EN = json.load(open(_en_path, encoding='utf-8')) if os.path.exists(_en_path) else {}

# ---------- お知らせ（2026-10-21 龍さん決定A：LINE（AI秘書）→シート→サイト自動化GAS→ data/news.json）----------
# data/news.json の形：{"items":[{"id":"N001","date":"2026-10-21","text":"本文","until":"2026-11-20","band":false}, ...]}
#   id：番号（N＋数字）／date：お知らせの日付／text：本文（文字だけ・HTMLは使わない）／until：この日まで出す（空なら期限なし）
#   band：true なら、いちばん上の帯にも出す（臨時休業など）
# 形がおかしい1件は飛ばす（サイトの作り直しは止めない）。理由はログに出す。期限切れはここで外す。
NEWS_MAX_TEXT = 200      # GAS側の上限（120字）より少し大きめ。超えたら飛ばす（壊れたデータの防止）
NEWS_TOP = 3             # トップに出す件数（新しい順）
NEWS_BAND_MAX = 2        # 上の帯に出す件数
_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
_NEWS_ODD = re.compile('[\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]')
def news_plain(t):
    """llms.txt（AI向けの説明・Markdown）に入れる用：見出し・リンク・箇条書きの記号を全角にして、文として読ませる"""
    return t.translate(str.maketrans({'#': '＃', '[': '［', ']': '］', '(': '（', ')': '）', '*': '＊', '`': '｀', '<': '＜', '>': '＞'}))
def load_news():
    path = os.path.join(ROOT, 'data/news.json')
    if not os.path.exists(path):
        return []
    try:
        raw = json.load(open(path, encoding='utf-8'))
    except Exception as e:
        print('::warning::data/news.json が読めません（お知らせなしで作ります）:', e)
        return []
    items = raw.get('items') if isinstance(raw, dict) else None
    if not isinstance(items, list):
        print('::warning::data/news.json の items が一覧になっていません（お知らせなしで作ります）')
        return []
    out = []
    for it in items:
        if not isinstance(it, dict):
            print('⚠ お知らせ：形が違う1件を飛ばしました'); continue
        nid, d, text = str(it.get('id', '')), str(it.get('date', '')), it.get('text')
        until = str(it.get('until') or '')
        if not re.match(r'^N\d{1,6}$', nid) or not _DATE_RE.match(d) or (until and not _DATE_RE.match(until)):
            print('⚠ お知らせ：番号・日付の形が違うので飛ばしました', nid); continue
        if not isinstance(text, str) or not text.strip() or len(text) > NEWS_MAX_TEXT:
            print('⚠ お知らせ：本文が空か長すぎるので飛ばしました', nid); continue
        if until and until < TODAY:
            continue   # 期限切れ
        text = re.sub(r'\s+', ' ', _NEWS_ODD.sub('', text)).strip()   # 文字の向きを変える記号・幅ゼロの文字は取り除く
        if not text:
            continue
        out.append({'id': nid, 'date': d, 'text': text, 'until': until, 'band': it.get('band') is True})
    out.sort(key=lambda n: (n['date'], int(n['id'][1:])), reverse=True)
    return out
NEWS = load_news()
NEWS_BAND = [n for n in NEWS if n['band']][:NEWS_BAND_MAX]

# ---------- 文言（日本語／英語） ----------
T = {
 'ja': {
  'util': '<b>毎週水曜 新着入荷</b>　送料込み・決済確認後3日以内に発送（月・火定休を除く）',
  'nav': [('/#list', '商品一覧'), ('/blog/', 'ブログ'), ('/#store', '店舗'), ('/#faq', 'Q&amp;A')],
  'hero_h': 'One<br>of <em>One.</em>',
  'hero_p': '埼玉・川越、築約80年の古民家から。国内外で買い付けたヴィンテージ古着と、オリジナルの「GAW」。どれも一点もので、同じものはありません。',
  'hero_btn': '一点ものを見る',
  'map': '地図を開く ／ 川越市元町1-14-5',
  'days_h': '営業日', 'days': '水〜日 12:00–20:00（月・火 定休）', 'today_open': '本日営業', 'today_closed': '本日定休',
  'menu': 'メニュー', 'menu_close': '閉じる', 'menu_cats': 'ジャンルで選ぶ', 'menu_all': 'すべての商品', 'menu_more': 'お店のこと',
  'list_h': 'In Stock', 'list_s': 'オンラインで買える一点もの（毎週水曜更新）', 'unit': '点', 'see_all': 'すべて見る', 'new_in': '新着',
  'kw_l': '文字で探す', 'kw_ph': '例：Levi\'s　90s　デニム', 'pr_l': '値段', 'pr_all': 'すべて',
  'pr_bands': ['〜1万円', '1万〜2万円', '2万円〜'], 'finder_l': '手持ちの服の身幅', 'finder_u': 'cm ±3cmの服を表示', 'finder_sold': '売れた一点ものも見る', 'finder_clear': '条件をクリア',
  'finder_hint': '身幅＝脇の下から脇の下までを平らに置いて測った長さ。いちばん気に入っている服で測るのがおすすめです。',
  'empty_w': '身幅{w}cm前後の服は、いまはありません。毎週水曜に新着が入ります。', 'empty': '条件に合う一点ものは、いまはありません。',
  'fit': '身幅{w}cm（{d}）', 'same': '同じ',
  'one': '1点限り', 'tax': '税込', 'tax_ship': '税込・送料込み',
  'trust': [('送料込み', '表示価格は税込・送料込み'), ('3日以内に発送', '決済確認後（月・火定休を除く）'),
            ('川越の実店舗', '古物商許可 ' + SHOP['kobutsu']), ('お店の評判', '<a href="{gm}" rel="noopener">Googleマップでクチコミを見る</a>')],
  'store_p': '古着屋 小判鮫（KOBANZAME）は、埼玉県川越市元町にある築約80年の古民家で営業している古着屋です。国内外で買い付けたヴィンテージ古着と、小判鮫オリジナルのリメイクアクセサリー「GAW」を扱っています。ブランドや流行ではなく、素材・質感・その一点にしかない空気感で選んでいます。サイトに載っている商品は、店頭にも並んでいます。',
  'store_dl': [('住所', None), ('営業', '12:00–20:00'), ('定休日', '月曜・火曜'), ('運営', SHOP['company']), ('お問い合わせ', SHOP['email'])],
  'faq_s': 'よくある質問',
  'buy': '購入する（クレジットカード）', 'buy_s': '購入する', 'soldout': 'SOLD OUT（この一点は旅立ちました）', 'prep': '準備中（まもなく購入できるようになります）',
  'hold_btn': '店頭で見たい・取り置きする（{n}日間）',
  'hold_p': '川越・元町の店頭で{n}日間お取り置きします。下の内容をInstagramのDMかメールで送ってください。',
  'hold_code': '取り置き希望／{sku}／来店予定日：　月　日／お名前：',
  'hold_to': '送り先', 'hold_mail': 'メール', 'hold_note': '店頭やネットで先に売れていた場合は、こちらからご連絡します。',
  'ship': '<b>一点もの・在庫1点。</b>Squareの安全な決済ページへ進みます。<br>先に店頭などで売れていた場合は、全額返金いたします。<br>決済確認後3日以内に発送（月・火定休を除く）',
  'stock1': '在庫1点', 'width': '身幅 {w}cm',
  'story': 'この一着の話', 'specs': '仕様・サイズ', 'delivery': '配送・返品',
  'howto': '実寸は平置きで測っています。身幅＝脇の下から脇の下、着丈＝襟のつけ根から裾まで。お手持ちの服を同じように測って比べると、サイズの失敗が減ります。',
  'delivery_p': '送料込み。決済確認後3日以内（月・火定休を除く）に、川越の店舗から発送します。古着・一点ものの性質上、お客様都合の返品はお受けしていません。商品説明と著しく異なる場合や発送間違いの場合は、到着後4日以内にメールでご連絡ください。',
  'byline': '文：小判鮫オーナー・専属バイヤー 龍',
  'related': 'こういうのもおすすめです', 'draft': '下書き（まだ公開していません）｜毎週水曜の夜（20時台）に公開されます',
  'journal_h': 'Journal', 'journal_s': '一点ものの、成り立ちの記録',
  'legal': [('/tokushoho/', '特定商取引法に基づく表記'), ('/privacy/', 'プライバシーポリシー')],
  'gm': 'Googleマップ', 'rank_new': '新品・未使用', 'rank_vin': 'ヴィンテージ（経年あり）', 'rank': '状態 {r}',
  'cats': {'outer': 'アウター', 'tops': 'トップス', 'bottoms': 'パンツ・スカート', 'dress': 'ワンピース', 'shoes': '靴', 'acc': 'アクセサリー・GAW', 'other': '小物・雑貨'},
  'nf_p': 'お探しのページは見つかりませんでした。売れた商品も、ふだんはSOLDとしてページを残しています。', 'nf_btn': 'オンラインで買える一点もの',
  'top_title': '古着屋 小判鮫 KOBANZAME｜埼玉・川越の古民家ヴィンテージ古着店',
  'top_desc': '埼玉県川越市元町、築約80年の古民家で営業する古着屋 小判鮫（KOBANZAME）。国内外で買い付けたヴィンテージ古着と、オリジナルのリメイクアクセサリー「GAW」。すべて一点もの。サイトからクレジットカードで購入できます（送料込み）。',
  'jr_title': 'ジャーナル｜古着屋 小判鮫 KOBANZAME', 'jr_desc': '一点ものの古着とGAWアクセサリーの成り立ちの記録。掲載中の商品はクレジットカードで購入できます（送料込み）。',
  'no_en': '',
 },
 'en': {
  'util': '<b>New arrivals every Wednesday</b>　Shipping included · Dispatched within 3 days of payment (closed Mon & Tue)',
  'nav': [('/en/#list', 'Shop'), ('/blog/', 'Blog'), ('/en/#store', 'Store'), ('/en/#faq', 'FAQ')],
  'hero_h': 'One<br>of <em>One.</em>',
  'hero_p': 'From an 80-year-old wooden house in Kawagoe, Saitama. Vintage clothing sourced in Japan and abroad, and our own remake line, GAW. Every piece is one of a kind.',
  'hero_btn': 'See the pieces',
  'map': 'Open map / 1-14-5 Motomachi, Kawagoe',
  'days_h': 'Open', 'days': 'Wed–Sun 12:00–20:00 (closed Mon & Tue)', 'today_open': 'Open today', 'today_closed': 'Closed today',
  'menu': 'Menu', 'menu_close': 'Close', 'menu_cats': 'Shop by category', 'menu_all': 'All items', 'menu_more': 'About the shop',
  'list_h': 'In Stock', 'list_s': 'One-of-a-kind pieces you can buy online (updated every Wednesday)', 'unit': ' items', 'see_all': 'See all', 'new_in': 'New in',
  'kw_l': 'Search', 'kw_ph': 'e.g. Levi\'s 90s denim', 'pr_l': 'Price', 'pr_all': 'Any',
  'pr_bands': ['Under ¥10,000', '¥10,000–20,000', '¥20,000 and up'], 'finder_l': 'Chest width of a piece you own', 'finder_u': 'cm — show pieces within ±3 cm', 'finder_sold': 'Show sold pieces', 'finder_clear': 'Clear',
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
  'related': 'You might also like these', 'draft': 'Draft (not yet published) | goes live on Wednesday morning',
  'journal_h': 'Journal', 'journal_s': 'Where each piece comes from',
  'legal': [('/en/legal/', 'Legal notice & privacy')],
  'gm': 'Google Maps', 'rank_new': 'New, unused', 'rank_vin': 'Vintage (signs of age)', 'rank': 'Condition {r}',
  'cats': {'outer': 'Outerwear', 'tops': 'Tops', 'bottoms': 'Pants & skirts', 'dress': 'Dresses', 'shoes': 'Shoes', 'acc': 'Accessories & GAW', 'other': 'Goods'},
  'nf_p': 'We could not find that page. Sold pieces usually stay on the site marked SOLD.', 'nf_btn': 'See the pieces',
  'top_title': 'Kobanzame | Vintage clothing shop in Kawagoe, Japan',
  'top_desc': 'Vintage clothing shop in an 80-year-old wooden house in Kawagoe, Saitama. One-of-a-kind pieces from Japan and abroad, plus our remade GAW accessories.',
  'jr_title': 'Journal | Kobanzame, Kawagoe', 'jr_desc': 'Where each one-of-a-kind piece comes from. Listed pieces can be bought online.',
  'no_en': 'English description coming soon. The details below are in Japanese.',
 },
}
# ---------- ワークショップ（2026-10-07 龍さん決定A） ----------
# 予約は外部の予約サイト（concentsocket.com）。このサイトには案内と「予約する」ボタンだけを置く。
# WS_FROM より前の日付で作ったときは、ページもメニューの入り口も出さない（予約受付の開始日に合わせる）。
# 料金は「10/24開催分」として書く（2026-10-15 龍さんGO・案A）。「期間限定」は終了日が未定だと有利誤認のおそれがあるため使わない。
# 比べる「通常価格」も書かない（二重価格表示にしない）。
WS_FROM = '2026-10-21'
WS_OPEN = TODAY >= WS_FROM
# 予約の受付（2026-10-23 龍さん決定B「予約サイトはまだ準備中にしておいて」）。
# False の間は「予約する」ボタンを出さず「予約は準備中です」と表示し、メニューも「（準備中）」付きにする。
# 予約サイトが整ったら True に戻す（RESERVE の行き先も新しいサイトに）。
WS_BOOKING = False
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
    T_WS_NAV = ({'ja': ('/workshop/', 'ワークショップ'), 'en': ('/en/workshop/', 'Workshops')} if WS_BOOKING else
                {'ja': ('/workshop/', 'ワークショップ（準備中）'), 'en': ('/en/workshop/', 'Workshops (coming soon)')})

CAT_EN = {'outer': 'Outer', 'tops': 'Tops', 'bottoms': 'Bottoms', 'dress': 'Dresses', 'shoes': 'Shoes', 'acc': 'Accessories', 'other': 'Goods'}

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
    ('取り置きはできますか？', '一点ものなので、サイト・店頭ともお取り置きはしていません。先着順でのご案内です。'),
    ('店頭とネットの在庫は同じですか？', 'はい。このサイト・店頭・メルカリShopsで同じ一点を販売しています（在庫を共有しています）。売れた時点でほかの販路は自動で止まりますが、ごくまれに同時に売れた場合は、先に決済が完了したご注文を優先し、もう一方のお客様にはご連絡のうえ全額返金いたします。'),
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
    ('Can you hold a piece for me?', 'Every piece is one of a kind, so we do not hold items, online or in the shop. First come, first served.'),
    ('Is online stock the same as in the shop?', 'Yes. The same one-of-a-kind pieces are sold on this site, in the shop and on Mercari Shops (shared stock). Other channels are stopped automatically once a piece sells; in the rare case that it sells in two places at once, the order paid first is honoured and the other customer is contacted and fully refunded.'),
 ],
}

# ---------- 11月1日からの新しい営業日（火〜日 13:00–20:00・月曜定休）----------
# 〜10/25：今の表示（水〜日 12:00–20:00・月火定休）のまま
# 10/26〜10/31：今の表示＋「11/1から」のお知らせ
# 11/1〜：新しい表示
if NEWHOURS:
    T['ja'].update({
        'util': '<b>毎週水曜 新着入荷</b>　送料込み・決済確認後3日以内に発送（月曜定休を除く）',
        'days': '火〜日 13:00–20:00（月曜定休・祝日は営業）',
        'trust': [(a, '決済確認後（月曜定休を除く）' if a == '3日以内に発送' else b) for a, b in T['ja']['trust']],
        'store_dl': [('営業', '13:00–20:00（7〜8月は22:00まで）') if a == '営業' else ('定休日', '月曜（祝日は営業）') if a == '定休日' else (a, b) for a, b in T['ja']['store_dl']],
        'ship': T['ja']['ship'].replace('（月・火定休を除く）', '（月曜定休を除く）'),
        'delivery_p': T['ja']['delivery_p'].replace('3日以内（月・火定休を除く）に', '3日以内（月曜定休を除く）に'),
    })
    T['en'].update({
        'util': '<b>New arrivals every Wednesday</b>　Shipping included · Dispatched within 3 days of payment (closed Mondays)',
        'days': 'Tue–Sun 13:00–20:00 (closed Mon, open on holidays)',
        'trust': [(a, 'After payment (closed Mondays)' if a == 'Ships in 3 days' else b) for a, b in T['en']['trust']],  # 2026-10-30 英語版の「3日以内に発送」の欄が月火定休のまま残っていたので追加
        'store_dl': [('Hours', '13:00–20:00 (until 22:00 in Jul–Aug)') if a == 'Hours' else ('Closed', 'Mondays (open on public holidays)') if a == 'Closed' else (a, b) for a, b in T['en']['store_dl']],
        'delivery_p': T['en']['delivery_p'].replace(' (closed Mon & Tue)', ' (closed Mondays)'),
    })
    FAQ['ja'] = [(q, '13:00〜20:00の営業で、定休日は毎週月曜日です（祝日の月曜は営業）。7〜8月は22:00まで営業します。臨時の休みや営業時間の変更はInstagramでお知らせします。') if q == '営業時間と定休日は？' else (q, a) for q, a in FAQ['ja']]
    FAQ['en'] = [(q, 'Open 13:00–20:00, Tuesday to Sunday. Closed on Mondays (open on public holidays). Until 22:00 in July and August. Changes are announced on Instagram.') if q == 'Opening hours?' else (q, a) for q, a in FAQ['en']]
elif NOTICE:
    T['ja']['util'] += '　<b>11/1から 月曜定休・13時開店</b>'
    T['ja']['days'] += '<span class="soon">11月1日から 火〜日 13:00–20:00（月曜定休・祝日は営業）</span>'
    T['en']['util'] += '　<b>New hours from 1 Nov</b>'
    T['en']['days'] += '<span class="soon">From 1 November: Tue–Sun 13:00–20:00 (closed Mon)</span>'
    FAQ['ja'] = [(q, a + '2026年11月1日からは、火曜〜日曜の13:00〜20:00営業・月曜定休（祝日は営業）になります。') if q == '営業時間と定休日は？' else (q, a) for q, a in FAQ['ja']]
    FAQ['en'] = [(q, a + ' From 1 November 2026: Tuesday to Sunday 13:00–20:00, closed on Mondays.') if q == 'Opening hours?' else (q, a) for q, a in FAQ['en']]
HOURS_LINE = {'ja': ('13:00–20:00・月曜定休' if NEWHOURS else '12:00–20:00・月曜・火曜定休'),
              'en': ('13:00–20:00, closed Mon' if NEWHOURS else '12:00–20:00, closed Mon & Tue')}
CLOSED_WEEKDAYS_JS = '[1]' if NEWHOURS else '[1,2]'   # 本日営業/定休バッジ用（0=日 1=月 2=火）

# お知らせ（帯）：「帯に出す」印のお知らせを、上の帯の先頭に足す（日本語ページだけ）。期限の日を過ぎたら画面側でも隠す
if NEWS_BAND:
    T['ja']['util'] = ''.join(
        f'<span class="nb" data-until="{n["until"]}"><b>{html.escape(n["text"])}</b>　</span>' for n in NEWS_BAND) + T['ja']['util']

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
    # 2026-10-08 products.json に genre（写真から判定したジャンル）があればそれを優先。無ければカテゴリの文字で判定
    if p.get('genre') in ('outer', 'tops', 'bottoms', 'dress', 'shoes', 'acc', 'other'):
        return p['genre']
    c = p.get('category', '')
    if 'ワンピース' in c or 'ドレス' in c: return 'dress'
    if 'アクセサリー' in c: return 'acc'
    if 'アウター' in c or 'ジャケット' in c or 'コート' in c: return 'outer'
    if 'トップス' in c or 'シャツ' in c or 'ニット' in c or 'スウェット' in c: return 'tops'
    if 'パンツ' in c or 'ボトムス' in c or 'スカート' in c: return 'bottoms'
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

def real_images(p):
    """AIで作ったマネキン画像を除いた、本物の写真だけ（Googleの商品フィード・構造化データ用。AI画像・文字入り画像は不承認の恐れ）"""
    mq = (p.get('photo_v2') or {}).get('mannequin_url')
    return [u for u in p['images'] if u != mq] or p['images']

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

PRICE_BANDS = [(0, 10000), (10000, 20000), (20000, 10**9)]   # 2026-10-29 値段の絞り込み（税込・下限以上〜上限未満）

def decades_of(p):
    """年代を {'1990s', ...} の形で返す。仕様表の「年代・生産」「年代」だけを読む（商品名の「40s」サイズ等を年代と取り違えないため）。
    「1980〜90年代」のような幅は両方の年代を入れる。Y2K は 2000s。分からなければ空"""
    sp = spec_of(p)
    txt = unicodedata.normalize('NFKC', ' '.join([sp.get('年代・生産', ''), sp.get('年代', '')]))
    out = set()
    if re.search(r'y2k', txt, re.I):
        out.add('2000s')
    for m in re.finditer(r'(?<!\d)(19|20)?(\d)0\s*(?:s|\'s|年代)', txt):
        c = m.group(1) or ('20' if m.group(2) in '012' else '19')
        out.add(f'{c}{m.group(2)}0s')
    m = re.search(r'(?<!\d)(19|20)?(\d)0\s*[〜~\-–]\s*(?:19|20)?(\d)0\s*(?:s|\'s|年代)', txt)   # 「1980〜90年代」の前の方
    if m:
        c = m.group(1) or ('20' if m.group(2) in '012' else '19')
        out.add(f'{c}{m.group(2)}0s')
    return out

def norm_q(x):
    """検索用にそろえる：全角→半角（NFKC）・小文字・アポストロフィを消す（Levi's／LEVI’S／levis を同じにする）"""
    return re.sub(r"['’`]", '', unicodedata.normalize('NFKC', x).lower())

def search_text(p):
    """一覧の文字検索に使う文字（ブランド・商品名・英語名・年代・色・素材・ジャンル）。同じ言葉は1回だけ（ページを重くしない）"""
    sp = spec_of(p)
    parts = [p.get('brand'), p.get('product_name'), p.get('title'), sp.get('年代・生産'), sp.get('年代'),
             sp.get('色'), sp.get('素材'), sp.get('タグの表記'), sp.get('店頭での名前'), p.get('category'),
             ' '.join(sorted(decades_of(p))), T['ja']['cats'].get(cat_of(p), ''), CAT_EN.get(cat_of(p), '')]
    if has_en(p):
        parts += [EN[p['sku']].get('product_name'), EN[p['sku']].get('title')]
    words = norm_q(' '.join(str(x) for x in parts if x is not None)).split()
    return ' '.join(dict.fromkeys(words))[:600]

def reco_score(a, b):
    """2026-10-29 「こういうのもおすすめです」の点数（数字のルールだけ。AIは使わない）
    同じジャンル+4／身幅の差3cm以内+2・6cm以内+1／値段が0.7〜1.4倍+2・0.5〜2倍+1／年代が重なる+2／同じブランド（大文字小文字は区別しない）+2"""
    s = 4 if cat_of(a) == cat_of(b) else 0
    wa, wb = body_width(a), body_width(b)
    if wa is not None and wb is not None:
        d = abs(wa - wb)
        s += 2 if d <= 3 else (1 if d <= 6 else 0)
    pa, pb = site_price(a), site_price(b)
    if pa > 0 and pb > 0:
        r = pb / pa
        s += 2 if 0.7 <= r <= 1.4 else (1 if 0.5 <= r <= 2 else 0)
    if decades_of(a) & decades_of(b):
        s += 2
    ba = (a.get('brand') or '').strip()
    if ba and ba not in NO_BRAND and ba.casefold() == (b.get('brand') or '').strip().casefold():
        s += 2
    return s

def reco_of(p, pool, n=3):
    """点数の高い順。同点なら新しく公開した順"""
    cands = [x for x in pool if x['sku'] != p['sku']]
    cands.sort(key=lambda x: x.get('published_date', ''), reverse=True)
    cands.sort(key=lambda x: reco_score(p, x), reverse=True)   # 安定ソートなので同点は新しい順のまま
    return cands[:n]

def gender_of(p):
    c = p.get('category', '')
    return 'male' if c.startswith('メンズ') else 'female' if c.startswith('レディース') else 'unisex'

def brand_of(p):
    b = (p.get('brand') or '').strip()
    return '' if (not b or any(b.startswith(x) for x in NO_BRAND)) else b

CRUMB_NAMES = {'blog': ('ブログ', 'Blog'), 'journal': ('ジャーナル', 'Journal'), 'news': ('お知らせ', 'News'),
               'workshop': ('ワークショップ', 'Workshops'), 'tokushoho': ('特定商取引法に基づく表記', ''), 'privacy': ('プライバシーポリシー', ''),
               'guide': ('川越で古着屋を探している方へ', 'Kawagoe vintage guide'), 'legal': ('', 'Legal notice & privacy')}
def add_crumb_ld(ld, lang, title, path):
    """2026-10-23 SEO：パンくず（BreadcrumbList）が無いページに、URL から作って足す"""
    if path in ('/', '/en/') or path.endswith('404.html'):
        return ld
    g = ld.get('@graph') if isinstance(ld, dict) else None
    if g is None or any(n.get('@type') == 'BreadcrumbList' for n in g):
        return ld
    P = pre(lang)
    segs = [x for x in path[len(P):].strip('/').split('/') if x] if path.startswith(P + '/') else [x for x in path.strip('/').split('/') if x]
    items = [{'@type': 'ListItem', 'position': 1, 'name': 'HOME', 'item': BASE + P + '/'}]
    url = P if segs and segs[0] in ('journal', 'news', 'workshop', 'guide', 'legal') else ''
    for i, sg in enumerate(segs):
        url += '/' + sg
        nm = CRUMB_NAMES.get(sg, ('', ''))[0 if lang == 'ja' else 1] or CRUMB_NAMES.get(sg, ('', ''))[0]
        if i == len(segs) - 1 and (i > 0 or not nm):
            nm = re.split(r'｜| \| ', title)[0]
        items.append({'@type': 'ListItem', 'position': len(items) + 1, 'name': nm or sg, 'item': BASE + url + '/'})
    g.append({'@type': 'BreadcrumbList', 'itemListElement': items})
    return ld

def jld(obj):
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False, separators=(',', ':')) + '</script>'

def org_node():
    return {
        '@type': 'ClothingStore', '@id': BASE + '/#store',
        'name': SHOP['name'], 'alternateName': ['小判鮫', 'KOBANZAME', 'こばんざめ', 'Remora', 'Remora Vintage Clothing Kawagoe'],   # Remora＝小判鮫の英名（2026-10-15 龍さん）。Bingマップ等にこの名前で載っているため
        'description': '埼玉県川越市、築約80年の古民家で営業する古着屋。国内外で買い付けたヴィンテージ古着と、小判鮫オリジナルのリメイクアクセサリー「GAW」を扱う。商品はすべて一点もの。',
        'url': BASE + '/', 'email': SHOP['email'],
        'image': BASE + '/assets/hero-shop.jpg', 'logo': BASE + '/assets/seal-256.png' if os.path.exists(os.path.join(ROOT, 'assets/seal-256.png')) else BASE + '/assets/seal-128.png',
        'priceRange': PRICE_RANGE,
        'address': {'@type': 'PostalAddress', 'postalCode': SHOP['postal'], 'addressRegion': '埼玉県',
                    'addressLocality': '川越市', 'streetAddress': '元町1-14-5', 'addressCountry': 'JP'},
        'openingHours': ('Tu-Su 13:00-20:00' if NEWHOURS else 'We-Su 12:00-20:00'), 'currenciesAccepted': 'JPY', 'paymentAccepted': 'クレジットカード',
        'hasMap': SHOP['gplace'],
        'geo': {'@type': 'GeoCoordinates', 'latitude': 35.9253165, 'longitude': 139.4832435},   # Googleマップの店舗ページの座標（2026-10-06）
        'openingHoursSpecification': [{'@type': 'OpeningHoursSpecification',
                                       'dayOfWeek': (['Tuesday'] if NEWHOURS else []) + ['Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'],
                                       'opens': ('13:00' if NEWHOURS else '12:00'), 'closes': '20:00'}],
        'parentOrganization': {'@type': 'Organization', 'name': SHOP['company']},
        'sameAs': [SHOP['instagram'], SHOP['mercari'], SHOP['gplace']],
    }

# ---------- 見た目 ----------
# 配色の原理：ベース70%＝墨（古民家の黒い壁）／メイン25%＝生成り（文字と紙の面）／アクセント5%＝古金（値段・ボタン・細線だけ）
# ＋濃淡の4色目＝煤竹（写真の台紙や面の区切り。墨より一段明るい黒）。明るさの差で奥行きを出し、色の数は増やさない。
CSS = r'''
:root{
  /* 2026-10-08 見た目を「白地×黒・写真主役」のセレクトショップ調へ（変数名は旧のまま・中身だけ入れ替え） */
  --sumi:#ffffff;      /* 地：白 */
  --susu:#f3f3f1;      /* 面の区切り：ごく薄いグレー */
  --kinari:#111111;    /* 文字：黒 */
  --kin:#111111;       /* アクセント：黒（ボタン・細線） */
  --usu:#686868;       /* 補助の文字（白地でコントラスト5.6） */
  --line:#e2e2e2;      /* 罫線 */
  --sold:#c0392b;      /* SOLD（売れた印だけに使う） */
  --mincho:"Zen Kaku Gothic New","Hiragino Sans","Yu Gothic",system-ui,sans-serif;
  --roman:"Libre Caslon Text","Zen Kaku Gothic New",serif;
  --gothic:"Jost","Zen Kaku Gothic New","Hiragino Sans","Yu Gothic",system-ui,sans-serif;
  --gutter:16px; color-scheme:light;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--sumi);color:var(--kinari);font-family:var(--gothic);font-size:15px;line-height:1.85;letter-spacing:.02em;-webkit-font-smoothing:antialiased}
img{display:block;max-width:100%}a{color:inherit}button{font:inherit;color:inherit;background:none;border:0;cursor:pointer}
:focus-visible{outline:2px solid var(--kin);outline-offset:3px}
.wrap{max-width:1240px;margin:0 auto;padding-inline:var(--gutter)}
.hair{height:1px;background:linear-gradient(90deg,transparent,var(--kin),transparent);opacity:.7}
.util{background:var(--susu);color:var(--usu);font-size:12px;letter-spacing:.08em;text-align:center;padding:8px var(--gutter);border-bottom:1px solid var(--line)}
.util b{color:var(--kin);font-weight:500}
header.site{position:sticky;top:0;z-index:20;background:rgba(255,255,255,.86);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}
header.site .wrap{display:flex;align-items:center;justify-content:space-between;gap:16px;min-height:64px}
.hl{display:flex;align-items:center;gap:14px}
.logo{display:flex;align-items:baseline;gap:12px;text-decoration:none}
.logo b{font-family:var(--mincho);font-weight:800;font-size:22px;letter-spacing:.14em}
.logo span{font-family:var(--roman);font-size:14px;letter-spacing:.32em;color:var(--kin)}
.hnav{display:flex;align-items:center;gap:22px}
.hnav a{font-size:13px;letter-spacing:.1em;text-decoration:none;color:var(--usu);white-space:nowrap}
.hnav a:hover{color:var(--kinari)}
.lang{display:flex;border:1px solid var(--line)}
.menubtn{display:inline-flex;align-items:center;gap:8px;background:none;border:1px solid var(--line);color:var(--kinari);font:inherit;font-size:12px;letter-spacing:.1em;padding:6px 10px;cursor:pointer}
.menubtn i{display:block;width:16px;height:2px;background:currentColor;position:relative}
.menubtn i::before,.menubtn i::after{content:"";position:absolute;left:0;width:16px;height:2px;background:currentColor}
.menubtn i::before{top:-5px}.menubtn i::after{top:5px}
.menubtn:hover{border-color:var(--kin)}
.drawer-bg{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:40}
.drawer{position:fixed;top:0;left:0;bottom:0;width:min(320px,86vw);background:var(--sumi);border-right:1px solid var(--line);z-index:41;padding:18px 20px 28px;overflow-y:auto;transform:translateX(-102%);transition:transform .2s ease}
.drawer.open{transform:none}
[hidden]{display:none!important}   /* 2026-10-09：.card{display:flex} などが hidden を上書きして、絞り込みで消したカードが見えたままだった不具合の修正 */
.drawer-bg[hidden]{display:none}
.drawer .dh{display:flex;justify-content:space-between;align-items:center;margin-bottom:18px}
.drawer .dh b{font-family:var(--mincho);font-size:18px;letter-spacing:.14em}
.drawer .x{background:none;border:1px solid var(--line);color:var(--kinari);font:inherit;font-size:12px;padding:5px 10px;cursor:pointer}
.drawer h3{font-size:11px;letter-spacing:.2em;color:var(--kin);font-weight:500;margin:20px 0 6px}
.drawer ul{list-style:none;margin:0;padding:0}
.drawer li a{display:flex;justify-content:space-between;align-items:baseline;padding:12px 2px;border-bottom:1px solid var(--line);color:var(--kinari);text-decoration:none;font-size:15px}
.drawer li a small{color:var(--usu);font-size:12px}
.drawer li a:hover{color:var(--kin)}
@media(prefers-reduced-motion:reduce){.drawer{transition:none}}
.lang a{font-size:12px;padding:4px 10px;color:var(--usu)}
.lang a[aria-current="true"]{background:var(--kinari);color:var(--sumi)}
@media(max-width:760px){.logo span{display:none}.hl{gap:10px}.hnav{gap:12px}.hnav a.n{display:none}}
.hero{position:relative;overflow:hidden;border-bottom:1px solid var(--line)}
.hero .wrap{display:grid;grid-template-columns:minmax(0,1fr)}
.hero-ph{position:relative}
.hero-img{width:100%;height:auto;aspect-ratio:1/1;object-fit:cover;object-position:50% 50%}
.herobox{position:absolute;left:12px;bottom:12px;right:12px;display:flex;flex-direction:column;align-items:flex-start;gap:6px}
.days{display:inline-flex;flex-wrap:wrap;align-items:center;gap:8px;background:rgba(255,255,255,.9);border:1px solid var(--line);color:var(--kinari);font-size:12px;letter-spacing:.06em;padding:7px 12px}
.days b{color:var(--kin);font-weight:500}
.days .today{border:1px solid var(--kin);color:var(--kin);font-size:11px;padding:1px 6px}
.days .today.closed{border-color:var(--usu);color:var(--usu)}
.days .soon{flex-basis:100%;order:3;color:var(--kin)}
.maplink{display:inline-flex;align-items:center;gap:8px;background:rgba(255,255,255,.9);border:1px solid var(--kin);color:var(--kinari);font-size:12px;letter-spacing:.06em;padding:8px 12px;text-decoration:none}
.maplink svg{width:14px;height:14px;flex:none}
.hero-copy{padding:32px 0 40px}
.hero h1{font-family:var(--roman);font-weight:500;font-style:italic;font-size:clamp(56px,11vw,120px);line-height:.92;letter-spacing:.01em}
.hero h1 em{font-style:italic;color:var(--kin)}
.hero p{font-family:var(--mincho);font-size:16px;margin-top:18px;max-width:28em;color:var(--kinari)}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:10px;min-height:52px;padding:0 28px;letter-spacing:.12em;text-decoration:none;border:1px solid var(--kin);color:var(--kinari);font-size:14px;text-align:center}
.btn:hover{background:rgba(0,0,0,.05)}
.ws{display:grid;gap:20px;margin-top:24px}
.ws article{border:1px solid var(--line);background:var(--susu);padding:22px 20px}
.ws h2{font-family:var(--mincho);font-size:19px;margin:0 0 6px;color:var(--kinari)}
.ws .price{font-family:var(--mincho);font-size:22px;color:var(--kin)}
.ws .price small{font-size:12px;color:var(--usu);margin-left:8px;letter-spacing:.06em}
.ws .meta{color:var(--usu);font-size:13px;margin:4px 0 12px}
.ws ul{margin:10px 0 18px 1.2em;color:var(--usu);font-size:13px}
@media(min-width:860px){.ws{grid-template-columns:1fr 1fr}}
.btn.kin{background:var(--kin);color:var(--sumi);font-weight:700;width:100%}
.btn.kin:hover{background:#333}
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
.finder input[type=search],.finder select{height:40px;background:var(--susu);color:var(--kinari);border:1px solid var(--kin);border-radius:0;padding:0 8px;font:inherit;font-size:16px}
.finder .frow{flex-basis:100%;display:flex;align-items:center;gap:10px}
.finder .fgrp{display:inline-flex;align-items:center;gap:8px;margin-right:8px}
.finder input[type=search]{flex:1 1 auto;min-width:0}
.finder input[type=number]{width:5.5em;height:40px;background:var(--susu);color:var(--kinari);border:1px solid var(--kin);border-radius:0;padding:0 8px;font:inherit;font-size:16px}
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
.story p{margin:0 0 1em}   /* 2026-10-29 龍さん：文が詰まって見えるので段落の間をあける */
.spec{display:grid;grid-template-columns:6.5em minmax(0,1fr);gap:8px 12px;font-size:14px;padding-bottom:12px}
.spec dt{color:var(--usu)}
.howto{font-size:12.5px;color:var(--usu);padding-bottom:16px}
.byline{font-size:12px;color:var(--usu);padding-block:16px}
.related{border-top:1px solid var(--line);padding-block:40px 140px}
@media(min-width:900px){.related{padding-bottom:72px}}
.related h2{font-size:36px;margin-bottom:20px}
@media(max-width:600px){.related .grid>:nth-child(3){display:none}}
.bar{position:fixed;left:0;right:0;bottom:0;z-index:30;background:rgba(255,255,255,.97);border-top:1px solid var(--kin);padding:10px var(--gutter) calc(10px + env(safe-area-inset-bottom,0px));display:flex;align-items:center;gap:12px}
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
/* ---- 2026-10-08 セレクトショップ調（白地・写真主役）の上書き ---- */
body{font-size:15px;letter-spacing:.01em}
.util{background:var(--kinari);color:var(--sumi);border-bottom:0;font-size:11.5px;letter-spacing:.1em}
.util b{color:var(--kin2);font-weight:600}
header.site .wrap{display:grid;grid-template-columns:1fr auto 1fr;min-height:68px}
header.site .hnav{justify-self:end}
.logo{flex-direction:column;align-items:center;gap:2px;line-height:1}
.logo b{font-family:var(--roman);font-weight:700;font-size:22px;letter-spacing:.18em}
.logo span{font-family:var(--gothic);font-size:9.5px;letter-spacing:.32em;color:var(--usu)}
.hnav a{font-family:var(--gothic);font-size:12px;letter-spacing:.14em;text-transform:uppercase}
.menubtn{border-color:transparent;padding-left:0;white-space:nowrap;font-family:var(--gothic);letter-spacing:.14em}
.menubtn:hover{border-color:transparent;opacity:.6}
.lang{border-color:var(--line)}
@media(max-width:760px){.logo span{display:block;font-size:8.5px}.logo b{font-size:18px}.hnav .lang a{padding:4px 7px}}
.tiles{padding-top:10px}
.tgrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;max-width:none;padding-inline:6px}
@media(min-width:640px){.tgrid{gap:10px;padding-inline:10px}}
@media(min-width:1000px){.tgrid{grid-template-columns:repeat(3,minmax(0,1fr))}}
.tile{position:relative;display:block;aspect-ratio:1/1;overflow:hidden;background:var(--susu);text-decoration:none}
.tile img{width:100%;height:100%;object-fit:cover;transition:transform .7s ease}
.tile:hover img{transform:scale(1.03)}
.tile:after{content:"";position:absolute;inset:0;background:linear-gradient(180deg,transparent 45%,rgba(0,0,0,.42))}
.tile .tt{position:absolute;left:12px;right:12px;bottom:22px;z-index:1;display:flex;flex-direction:column;align-items:center;gap:12px;text-align:center}
.tile .tt b{font-family:var(--roman);font-weight:700;font-size:clamp(20px,2.3vw,28px);line-height:1.25;color:#fff;text-shadow:0 1px 12px rgba(0,0,0,.35)}
.tile .tt i{font-style:normal;font-family:var(--gothic);font-size:12px;letter-spacing:.12em;background:var(--sumi);color:var(--kinari);padding:8px 18px}
@media(max-width:639px){.tile .tt{bottom:12px;gap:8px}.tile .tt b{font-size:14px}.tile .tt i{font-size:10px;padding:6px 10px}.menubtn{font-size:0;gap:0}}
.hero{border-bottom:0;margin-top:56px}
.hero h1{font-family:var(--roman);font-style:normal;font-weight:400;font-size:clamp(44px,8vw,92px);letter-spacing:0}
.hero h1 em{font-style:normal;color:var(--kinari)}
.hero p{font-family:var(--mincho)}
.days,.maplink{border-color:var(--line);color:var(--kinari)}
.days b{color:var(--kinari);font-weight:600}
.days .today{border-color:var(--kinari);color:var(--kinari)}
.btn{border-color:var(--kinari);font-family:var(--gothic);letter-spacing:.14em;min-height:48px}
.btn.kin{background:var(--kin);color:#fff;font-weight:500}
.sec-head h2,.store h2,.related h2{font-family:var(--gothic);font-weight:500;font-size:22px;letter-spacing:.16em;text-transform:uppercase}
.sec-head h2 small,.related h2 small{font-family:var(--mincho);text-transform:none;letter-spacing:.06em}
.catrow button{font-family:var(--gothic);color:var(--kinari)}
.catrow button small{font-family:var(--gothic);color:var(--usu);font-size:11px}
.catrow button[aria-pressed="true"]{background:var(--kinari);color:var(--sumi);border-color:var(--kinari)}
.catrow button[aria-pressed="true"] small{color:#ddd}
.finder input[type=number]{background:var(--sumi);border-color:var(--kinari)}
.finder input[type=search],.finder select{background:var(--sumi);border-color:var(--kinari)}
.card .ph{aspect-ratio:1/1}
.card .brand{font-family:var(--gothic);font-size:12px;font-weight:600;letter-spacing:.14em;text-transform:uppercase;color:var(--kinari)}
.card .nm{color:var(--usu);font-size:13px}
.card .pr{font-family:var(--gothic);font-weight:500;font-size:15px}
.tag{background:var(--sumi);color:var(--kinari);border:0;font-family:var(--gothic);font-size:10.5px;padding:3px 8px;top:8px;right:8px}
.card.sold .ph:after{font-family:var(--gothic);font-size:20px;letter-spacing:.3em}
.trust b{color:var(--kinari);font-family:var(--mincho)}
.store dl{border-top-color:var(--kinari)}
.store dd a,.holdbox a{color:var(--kinari);text-decoration:underline}
details summary{font-family:var(--mincho)}
details summary:after{font-family:var(--gothic);color:var(--kinari)}
footer.site{background:var(--kinari);border-top:0;color:#c9bfae;font-size:11.5px}
footer.site .big{font-family:var(--roman);font-style:normal;font-weight:700;font-size:28px;letter-spacing:.18em}
.blocks{display:flex;flex-direction:column;gap:56px}
.block .bhead{display:flex;align-items:flex-end;justify-content:space-between;gap:12px;border-bottom:1px solid var(--kinari);padding-bottom:10px;margin-bottom:18px}
.block h3{font-family:var(--gothic);font-weight:500;font-size:18px;letter-spacing:.18em;line-height:1}
.block h3 small{display:block;font-family:var(--mincho);font-size:12.5px;letter-spacing:.06em;color:var(--usu);margin-top:8px}
.ball{font-family:var(--gothic);font-size:12px;letter-spacing:.12em;color:var(--kinari);border:1px solid var(--kinari);padding:8px 14px;white-space:nowrap;min-height:40px}
.ball span{margin-left:8px;color:var(--usu);font-variant-numeric:tabular-nums}
.ball:hover{background:var(--kinari);color:var(--sumi)}.ball:hover span{color:#ddd}
.brow{display:grid;grid-auto-flow:column;grid-auto-columns:46%;gap:12px;overflow-x:auto;scroll-snap-type:x mandatory;padding-bottom:8px;-webkit-overflow-scrolling:touch}
.brow .card{scroll-snap-align:start}
@media(min-width:900px){.brow{grid-auto-flow:row;grid-template-columns:repeat(4,minmax(0,1fr));grid-auto-columns:auto;overflow:visible;gap:40px 20px}}
footer.site .hair{background:var(--line);opacity:1}
.info .brand{font-family:var(--gothic);font-size:13px;font-weight:600;letter-spacing:.16em;text-transform:uppercase;color:var(--kinari)}
.info h1{font-family:var(--mincho)}
.info .price{font-family:var(--gothic);font-weight:500;font-size:26px}
.info .sku{font-family:var(--gothic)}
.facts span.one{border-color:var(--kinari);color:var(--kinari)}
.points{border-top-color:var(--kinari)}
.points li:before{background:var(--kinari)}
.story{font-family:var(--mincho)}
.story h2,.page h2{color:var(--kinari)}
.bar{border-top-color:var(--line)}
.bar b{font-family:var(--gothic);font-weight:500}
.draftnote{background:var(--kinari);color:var(--sumi)}
.nf h1{font-family:var(--roman);font-style:normal}
.gal img{aspect-ratio:1/1}
/* ---- 2026-10-09 A案「漆喰と墨」：店の壁と梁の色。地＝漆喰、文字＝墨、アクセント＝柿渋（買うボタン）と真鍮（細線） ---- */
:root{--sumi:#F4F0E8;--susu:#EAE4D8;--kinari:#120A07;--kin:#7C4412;--kin2:#AD8951;--usu:#5E554C;--line:#DCD3C3}
header.site{background:rgba(244,240,232,.94);border-bottom:1px solid var(--line)}
.logo{flex-direction:row;align-items:center;gap:10px;text-decoration:none}
.logo img{width:44px;height:44px;flex:none}
.logo .wm{display:flex;flex-direction:column;gap:3px;line-height:1}
@media(max-width:760px){.logo img{width:36px;height:36px}.logo{gap:8px}}
.btn.kin:hover{background:var(--kinari)}
.block .bhead{border-bottom-color:var(--kin2)}
.card .pr{color:var(--kinari)}
.tile:after{background:linear-gradient(180deg,transparent 45%,rgba(18,10,7,.5))}
footer.site{position:relative;overflow:hidden;padding-block:56px 48px}
footer.site .wrap{position:relative;z-index:1}
footer.site a{color:var(--sumi)}
footer.site .big{display:flex;align-items:center;gap:14px;color:var(--sumi)}
footer.site .big img{width:64px;height:64px}
footer.site .hair{background:var(--kin2);opacity:.6}
footer.site:after{content:"";position:absolute;right:-40px;bottom:-30px;width:300px;height:288px;background:url(/assets/jaw-light-400.png) center/contain no-repeat;opacity:.05;pointer-events:none}
/* ---- 2026-10-09 圧迫感を減らす・動きをつける ---- */
html:lang(ja) body{word-break:keep-all;overflow-wrap:anywhere;line-break:strict}
p,li,dd,.nm,.hero p{text-wrap:pretty}
h1,h2,h3{text-wrap:balance}
.card .ph{aspect-ratio:4/5}
.gal img{aspect-ratio:4/5}
.card .ph img{width:100%;height:100%;object-fit:cover;transition:opacity .45s ease,transform .9s ease}
.card .ph img.alt{position:absolute;inset:0;opacity:0}
@media(hover:hover){.card:hover .ph img.alt{opacity:1}.card:hover .ph img:not(.alt){transform:scale(1.02)}}
.tgrid{gap:12px;padding-inline:var(--gutter)}
@media(min-width:640px){.tgrid{gap:20px;padding-inline:24px}}
.tile:after{background:linear-gradient(180deg,transparent 60%,rgba(18,10,7,.32))}
.tile .tt b{font-family:var(--gothic);font-weight:500;letter-spacing:.14em;font-size:clamp(14px,1.6vw,20px)}
.tile img{transition:transform 1.6s ease}
.tile:hover img{transform:scale(1.05)}
.blocks{gap:88px}
.brow{gap:20px}
@media(min-width:900px){.brow{gap:56px 28px}}
.rv{opacity:0;transform:translateY(18px);transition:opacity .8s ease,transform .8s ease}
.rv.in{opacity:1;transform:none}
header.site{transition:box-shadow .3s ease}
header.site.sc{box-shadow:0 6px 20px -14px rgba(18,10,7,.35)}
.btn,.ball{transition:background .25s ease,color .25s ease}
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
# 2026-10-28：リンクに ?utm_source=threads&utm_campaign=new-20261028 のような印があれば、流入元（ref）をその印にする（Threads からのクリック数を数えるため）。
# 個人を見分ける情報（Cookie・端末ID・IP等）は送らない。スタッフは一度 ?nolog=1 を付けて開くと、その端末からは送られない。
TRACK_JS = """<script>
(function(){var U='__URL__';if(!U||navigator.webdriver||/bot|crawl|spider|slurp|lighthouse|headless/i.test(navigator.userAgent))return;
try{if(/[?&]nolog=1/.test(location.search))localStorage.setItem('kbz_nolog','1');if(/[?&]nolog=0/.test(location.search))localStorage.removeItem('kbz_nolog');if(localStorage.getItem('kbz_nolog')==='1')return;}catch(e){}
function sku(){var el=document.querySelector('.sku');var m=el&&el.textContent.match(/[A-Z]{1,3}\\d{3,6}/);return m?m[0]:'';}
function send(o){o.p=location.pathname;o.sku=sku();o.lang=document.documentElement.lang||'';o.dev=/Mobi|Android|iPhone/i.test(navigator.userAgent)?'m':'d';
try{var h=document.referrer?new URL(document.referrer).hostname:'';o.ref=(h===location.hostname)?'':h;}catch(e){o.ref='';}
try{var us=(location.search.match(/[?&]utm_source=([A-Za-z0-9-]{1,30})/)||[])[1];if(us){var uc=(location.search.match(/[?&]utm_campaign=([A-Za-z0-9-]{1,40})/)||[])[1];o.ref=(us+(uc?'-'+uc:'')).toLowerCase();}}catch(e){}
var b=JSON.stringify(o);try{if(navigator.sendBeacon&&navigator.sendBeacon(U,new Blob([b],{type:'text/plain'})))return;}catch(e){}
try{fetch(U,{method:'POST',body:b,mode:'no-cors',keepalive:true});}catch(e){}}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',function(){send({t:'pv'});});else send({t:'pv'});
document.addEventListener('click',function(e){var a=e.target.closest&&e.target.closest('a,button');if(!a)return;var h=a.getAttribute('href')||'',k='';
if(a.id==='holdbtn')k='hold';else if(/square\\.link/.test(h))k='buy';else if(/mercari/.test(h))k='mercari';else if(/instagram\\.com/.test(h))k='instagram';else if(/google\\.[a-z.]+\\/maps|maps\\.app\\.goo\\.gl|goo\\.gl\\/maps/.test(h))k='map';
if(k)send({t:'click',btn:k});},true);
})();
</script>"""

# お知らせ：期限（data-until）の日を過ぎたものを、見ている人のスマホ側で隠す（日本時間で判定。作り直しが遅れても出しっぱなしにしない）
NEWS_JS = '''<script>document.addEventListener('DOMContentLoaded',function(){try{var d=new Date(Date.now()+324e5).toISOString().slice(0,10);document.querySelectorAll('[data-until]').forEach(function(e){var u=e.getAttribute('data-until');if(u&&u<d)e.hidden=true;});}catch(x){}});</script>'''

def news_items_html(items):
    """お知らせの一覧（<li>）。本文は文字として出す（HTMLにしない）"""
    return '\n'.join(
        f'      <li data-until="{n["until"]}"><time datetime="{n["date"]}">{n["date"].replace("-", ".")}</time><p>{html.escape(n["text"])}</p></li>'
        for n in items)

def head(lang, title, desc, path, og_type='website', image=None, extra_ld=None, noindex=False):
    t = T[lang]
    if len(desc) > 160:   # 2026-10-23 SEO：検索結果で切れないよう説明文は160字まで
        desc = desc[:157].rstrip() + '…'
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
    tabs = tabs_html(lang, path)
    return f'''<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
{'<meta name="robots" content="noindex">' if noindex else ''}
<meta name="theme-color" content="#ffffff">
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
<link href="https://fonts.googleapis.com/css2?family=Jost:wght@400;500;600&family=Libre+Caslon+Text:wght@400;700&family=Zen+Kaku+Gothic+New:wght@400;500;700&display=swap" rel="stylesheet">
<link rel="icon" type="image/png" href="/assets/favicon-48.png"><link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">
<link rel="stylesheet" href="/assets/site.css">
{jld(add_crumb_ld(ld, lang, title, path))}
{beacon}{track}
{verify}</head>
<body>
<div class="util">{t['util']}</div>{NEWS_JS if NEWS else ''}
<header class="site"><div class="wrap">
  <div class="hl"><button type="button" class="menubtn" id="menubtn" aria-expanded="false" aria-controls="drawer"><i aria-hidden="true"></i>{t['menu']}</button></div>
  <a class="logo" href="{pre(lang)}/" aria-label="小判鮫 KOBANZAME"><img src="/assets/seal-128.png" alt="" width="44" height="44"><span class="wm"><b>KOBANZAME</b><span>小判鮫 ・ KAWAGOE</span></span></a>
  <div class="hnav">{navs}
    <nav class="lang" aria-label="言語 / Language"><a href="{alt if lang == 'en' else path}" lang="ja" aria-current="{ja_cur}">日本語</a><a href="{alt if lang == 'ja' else path}" lang="en" aria-current="{en_cur}">EN</a></nav>
  </div>
</div>{tabs}</header>
''' + drawer_html(lang)

REVEAL_JS = '''<div class="toast" id="toast" role="status" aria-live="polite"></div>
<script>
(function(){
  var h=document.querySelector('header.site');
  function hh(){if(h)document.documentElement.style.setProperty('--hh',h.offsetHeight+'px');} hh(); addEventListener('resize',hh);
  var to=document.getElementById('toast'),tm;
  window.kzToast=function(m){if(!to)return;to.textContent=m;to.classList.add('on');clearTimeout(tm);tm=setTimeout(function(){to.classList.remove('on');},2200);};
  document.querySelectorAll('.ph>img:first-child,.tile img,.blog-card-img img').forEach(function(i){
    var p=i.parentNode; function d(){p.classList.add('ld');}
    if(i.complete&&i.naturalWidth)d(); else {i.addEventListener('load',d);i.addEventListener('error',d);}
  });
})();
</script>
<script>
(function(){
  var q=document.querySelectorAll('.card,.sec-head,.block .bhead,.store,.faq,.story,.trust,.tile');
  if(!('IntersectionObserver' in window)||matchMedia('(prefers-reduced-motion:reduce)').matches)return;
  var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target);}});},{rootMargin:'0px 0px -8% 0px'});
  q.forEach(function(el,i){el.classList.add('rv');el.style.transitionDelay=(i%4)*60+'ms';io.observe(el);});
  setTimeout(function(){q.forEach(function(el){if(el.getBoundingClientRect().top<innerHeight)el.classList.add('in');});},1500);  // 念のため：画面内のものは1.5秒後には必ず見せる
  var h=document.querySelector('header.site');addEventListener('scroll',function(){h.classList.toggle('sc',scrollY>40);},{passive:true});
})();
</script>'''

# 2026-10-23 龍さん決定A：スマホでもメニューが見えるように、ロゴの下に文字のタブを常に出す（古着屋 BerBerJin などの「上に SHOP・BLOG」の形）
TABS = {'ja': [('list', '商品'), ('new', '新着'), ('blog', 'ブログ'), ('store', 'お店')],
        'en': [('list', 'Shop'), ('new', 'New in'), ('blog', 'Blog'), ('store', 'Store')]}
def tabs_html(lang, path):
    P = pre(lang)
    href = {'list': f'{P}/#list', 'new': f'{P}/?cat=new#list', 'blog': '/blog/', 'store': f'{P}/#store'}
    has_new = any(is_new(p) for p in avail_live)
    cur = 'blog' if path.startswith('/blog') else ''
    items = ''.join(f'<a href="{href[k]}"' + (' data-cat="new"' if k == 'new' else (' data-cat=""' if k == 'list' else '')) + (' aria-current="page"' if k == cur else '') + f'>{l}</a>'
                    for k, l in TABS[lang] if k != 'new' or has_new)
    return f'<nav class="tabs" aria-label="{"メイン" if lang == "ja" else "Main"}">{items}</nav>'

def drawer_html(lang):
    t = T[lang]
    P = pre(lang)
    n_all = len([p for p in live if not is_sold(p)])
    n_new = len([p for p in avail_live if is_new(p)])
    cats = (f'<li><a href="{P}/?cat=new#list" data-cat="new">{NEW_LABEL[lang]}<small>{n_new}</small></a></li>' if n_new else '') + ''.join(f'<li><a href="{P}/?cat={c}#list" data-cat="{c}">{t["cats"][c]}<small>{len([p for p in live if not is_sold(p) and cat_of(p) == c])}</small></a></li>' for c in CATS_PRESENT)
    more = ''.join(f'<li><a href="{h}">{l}</a></li>' for h, l in t['nav'][1:] + ([T_WS_NAV[lang]] if WS_OPEN else []))
    return f'''<div class="drawer-bg" id="drawerbg" hidden></div>
<nav class="drawer" id="drawer" aria-label="{t['menu']}" aria-hidden="true">
  <div class="dh"><b>小判鮫</b><button type="button" class="x" id="drawerx">{t['menu_close']}</button></div>
  <h3>{t['menu_cats']}</h3>
  <ul><li><a href="{P}/#list" data-cat="">{t['menu_all']}<small>{n_all}</small></a></li>{cats}</ul>
  <h3>{t['menu_more']}</h3>
  <ul>{more}</ul>
</nav>
<script>
(function(){{
  var b=document.getElementById('menubtn'),d=document.getElementById('drawer'),bg=document.getElementById('drawerbg'),x=document.getElementById('drawerx');
  function open(){{d.classList.add('open');d.setAttribute('aria-hidden','false');bg.hidden=false;b.setAttribute('aria-expanded','true');var a=d.querySelector('a');if(a)a.focus();}}
  function close(){{d.classList.remove('open');d.setAttribute('aria-hidden','true');bg.hidden=true;b.setAttribute('aria-expanded','false');}}
  b.addEventListener('click',function(){{d.classList.contains('open')?close():open();}});
  x.addEventListener('click',function(){{close();b.focus();}}); bg.addEventListener('click',close);
  document.addEventListener('keydown',function(e){{if(e.key==='Escape'&&d.classList.contains('open')){{close();b.focus();}}}});
  document.querySelectorAll('#drawer a[data-cat],header.site .tabs a[data-cat]').forEach(function(a){{a.addEventListener('click',function(e){{
    if(!document.getElementById('grid'))return;
    e.preventDefault();close();
    document.dispatchEvent(new CustomEvent('kz:cat',{{detail:a.dataset.cat||null}}));
    history.replaceState(null,'',a.getAttribute('href'));
    var l=document.getElementById('list');if(l)l.scrollIntoView();
  }});}});
}})();
</script>
'''

def foot(lang):
    t = T[lang]
    P = pre(lang)
    ja = lang == 'ja'
    lic = ('古物商許可：' + SHOP['kobutsu']) if ja else 'Licensed secondhand dealer: Saitama Prefectural Public Safety Commission No. 431080060786'
    op = ('運営：' + SHOP['company']) if ja else 'Operated by Plug Inc.'
    hours = HOURS_LINE[lang]
    def col(h, links):
        return f'<div class="fcol"><h3>{h}</h3><ul>' + ''.join(f'<li><a href="{u}"' + (' rel="noopener"' if u.startswith('http') else '') + f'>{l}</a></li>' for u, l in links) + '</ul></div>'
    # 2026-10-23 龍さん「一番下に小さいメニューしかない」→ お買い物／読みもの／お店 の3列に分ける
    shop = [(f'{P}/#list', t['menu_all'])] + ([(f'{P}/?cat=new#list', NEW_LABEL[lang])] if any(is_new(p) for p in avail_live) else []) \
         + [(f'{P}/?cat={c}#list', t['cats'][c]) for c in CATS_PRESENT] + [(SHOP['mercari'], 'メルカリShops' if ja else 'Mercari Shops')]
    read = [('/blog/', 'ブログ' if ja else 'Blog (Japanese)'), ('/guide/' if ja else '/en/guide/', '川越で古着屋を探している方へ' if ja else 'Kawagoe vintage guide')] \
         + ([('/news/', 'お知らせ')] if ja and NEWS else [])
    store = [(f'{P}/#store', '場所・営業時間' if ja else 'Address & hours'), (f'{P}/#faq', 'よくある質問' if ja else 'FAQ')] \
          + ([T_WS_NAV[lang]] if WS_OPEN else []) + [(SHOP['gmaps'], t['gm']), (SHOP['instagram'], 'Instagram')]
    cols = col('お買い物' if ja else 'Shop', shop) + col('読みもの' if ja else 'Read', read) + col('お店' if ja else 'The shop', store)
    legal = '　・　'.join(f'<a href="{h}">{l}</a>' for h, l in t['legal'])
    return f'''<footer class="site"><div class="wrap">
  <div class="big"><img src="/assets/seal-light-256.png" alt="" width="64" height="64">Kobanzame</div>
  <nav class="fcols" aria-label="{'サイトの案内' if ja else 'Site map'}">{cols}</nav>
  <div class="hair"></div>
  <div>古着屋 小判鮫／{ADDR[lang]}／{hours}<br>
    {op}　・　{lic}<br>
    {legal}
  </div>
</div></footer>
{REVEAL_JS}
</body>
</html>
'''

try:
    import budoux
    _BX = budoux.load_default_japanese_parser()
except Exception:   # 入っていなくてもサイトは作る（改行が少し不自然になるだけ）
    _BX = None
_SKIP = re.compile(r'(<(script|style|title|textarea|code|option)\b.*?</\2>|<[^>]+>|&#?\w+;)', re.S | re.I)
def wbr(html):
    """本文の日本語の文節の切れ目に <wbr> を入れる（タグ・スクリプトの中は触らない）"""
    if _BX is None or '<body' not in html:
        return html
    head, body = html.split('<body', 1)
    parts, pos = [], 0
    for m in _SKIP.finditer(body):
        parts.append(_wbr_text(body[pos:m.start()])); parts.append(m.group(0)); pos = m.end()
    parts.append(_wbr_text(body[pos:]))
    return head + '<body' + ''.join(parts)
def _wbr_text(t):
    if not re.search(r'[ぁ-んァ-ヶ一-龯]', t) or len(t) < 8:
        return t
    return '<wbr>'.join(_BX.parse(t))

def write(path, text):
    if path.endswith('.html'):
        text = wbr(text)
    full = os.path.join(ROOT, path.lstrip('/'))
    os.makedirs(os.path.dirname(full), exist_ok=True)
    open(full, 'w', encoding='utf-8').write(text)

# 2026-10-14 使いやすさの直し（龍さん決定A：デジタル庁デザインシステムの考え方＝押せる広さ44px以上・小さすぎる文字を使わない。見た目は変えない）
A11Y_CSS = """
.menubtn{min-width:44px;min-height:44px;justify-content:center;margin-inline:-8px}
.lang a{min-height:44px;display:inline-flex;align-items:center}
#drawerx,button.ball{min-height:44px}
#myw{min-height:44px}
footer.site a{display:inline-flex;align-items:center;min-height:44px}
.finder button.clear{min-height:44px;padding-inline:8px}
label.chk{display:inline-flex;align-items:center;gap:8px;min-height:44px;cursor:pointer}
label.chk input{width:20px;height:20px}
.util{font-size:13px}
footer.site{font-size:13px}
.drawer h3,.days .today,.tag,.card .pr small,.catrow button small{font-size:12px}
@media(max-width:639px){.tile .tt i{font-size:12px;padding:8px 14px}}
"""
# 2026-10-21 お知らせ欄（トップの営業日の下・/news/）。見出しは既存の .sec-head h2 と同じ見た目にそろえる
# 2026-10-23 メニューを分かりやすく（スマホの文字タブ・3列のフッター・トップのブログ欄・ブログ一覧の見出し・WSの準備中）
NAV_CSS = """
header.site .tabs{display:none}
@media(max-width:760px){
  header.site .tabs{display:flex;border-top:1px solid var(--line)}
  header.site .tabs a{flex:1;display:flex;align-items:center;justify-content:center;min-height:44px;font-family:var(--gothic);font-size:13px;letter-spacing:.12em;color:var(--kinari);text-decoration:none}
  header.site .tabs a[aria-current="page"]{box-shadow:inset 0 -2px 0 var(--kin)}
  [id]{scroll-margin-top:calc(var(--hh,112px) + 56px)}
}
/* 今いる場所（パンくず）をヘッダーの下に貼りつける。ジャンルを押すとその一覧に戻れる */
.crumb{position:sticky;top:var(--hh,68px);z-index:15;background:var(--sumi);box-shadow:0 0 0 100vmax var(--sumi);clip-path:inset(0 -100vmax);padding-block:10px;align-items:center}
.crumb>span:last-child{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0;flex:1}
.crumb{flex-wrap:nowrap}
.crumb a{min-height:32px;display:inline-flex;align-items:center;white-space:nowrap}
.herebar{position:sticky;top:var(--hh,68px);z-index:15;display:flex;gap:8px;align-items:center;justify-content:space-between;background:var(--sumi);box-shadow:0 0 0 100vmax var(--sumi);clip-path:inset(0 -100vmax);padding-block:8px;border-bottom:1px solid var(--line)}
.herebar[hidden]{display:none}
.herebar button{font:inherit;font-size:13px;background:none;border:0;color:var(--kinari);min-height:40px;cursor:pointer;padding:0 4px}
.herebar .back{border:1px solid var(--line);padding:0 12px;white-space:nowrap}
/* トースト（画面の下に少しだけ出る短いお知らせ） */
.toast{position:fixed;left:50%;bottom:24px;transform:translate(-50%,16px);background:var(--kinari);color:var(--sumi);font-size:13px;padding:10px 18px;border-radius:999px;opacity:0;pointer-events:none;transition:opacity .25s,transform .25s;z-index:50;max-width:calc(100% - 32px);text-align:center}
.toast.on{opacity:1;transform:translate(-50%,0)}
/* スケルトン（写真が読み込まれるまで、灰色の枠を光らせる） */
@keyframes kzsk{0%{background-position:100% 0}100%{background-position:-100% 0}}
.ph:not(.ld),.tile:not(.ld),.blog-card-img:not(.ld){background:linear-gradient(90deg,#e7e0d4 25%,#f2ede4 50%,#e7e0d4 75%);background-size:200% 100%;animation:kzsk 1.3s linear infinite}
.blog-card-img{min-height:200px;background:var(--susu)}
@media(prefers-reduced-motion:reduce){.ph,.tile,.blog-card-img{animation:none!important}}
footer.site .fcols{display:grid;gap:24px 32px;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));margin:8px 0 4px}
footer.site .fcols h3{font-family:var(--gothic);font-size:12px;font-weight:500;letter-spacing:.16em;color:#fff;margin:0 0 6px}
footer.site .fcols ul{list-style:none;margin:0;padding:0}
footer.site .fcols li a{display:inline-flex;align-items:center;min-height:32px;font-size:13px;text-decoration:none}
footer.site .fcols li a:hover{text-decoration:underline}
.blogtop .sec-head .more{font-size:13px;color:var(--kin);min-height:44px;display:inline-flex;align-items:center}
.blog-grid-3{margin-top:8px}
@media(min-width:900px){.blog-grid-3{grid-template-columns:repeat(3,1fr)}}
.blog-card-body h3{font-size:1rem;line-height:1.5;margin:.3em 0 0;color:var(--kinari)}
.blog-main .sec-head h1{font-family:var(--gothic);font-weight:500;font-size:22px;line-height:1;letter-spacing:.16em;text-transform:uppercase}
.blog-main .sec-head h1 small{display:block;font-family:var(--mincho);font-size:14px;margin-top:10px;color:var(--usu);letter-spacing:.06em;text-transform:none}
/* ブログのタグが、商品カードの「1点限り」の位置指定を受けて画面の右上に浮いていたのを直す */
.blog-card-tags .tag,.blog-tags .tag{position:static;inset:auto;transform:none}
/* 2026-10-23 龍さん「横にスクロールする商品の列が上下にも少し動いて、縦のスクロールが引っかかる」→ 列の中は縦に動かさない */
@media(max-width:899px){.brow,.gal{overflow-y:hidden;overscroll-behavior-x:contain}}
.jhead h1{font-family:var(--gothic);font-weight:500;font-size:22px;line-height:1;letter-spacing:.16em;text-transform:uppercase}
.jhead h1 small{display:block;font-family:var(--mincho);font-size:14px;margin-top:10px;color:var(--usu);letter-spacing:.06em;text-transform:none}
.toblog{margin-top:20px}.toblog a{color:var(--kin);min-height:44px;display:inline-flex;align-items:center}
.ws-off{margin-top:12px;padding:12px 14px;border:1px dashed var(--line);color:var(--usu);font-size:14px}
"""

NEWS_CSS = """
.news .sec-head{margin-top:32px}
.news .sec-head h1{font-family:var(--gothic);font-weight:500;font-size:22px;line-height:1;letter-spacing:.16em;text-transform:uppercase}
.news .sec-head h1 small{display:block;font-family:var(--mincho);font-size:14px;margin-top:10px;color:var(--usu);letter-spacing:.06em;text-transform:none}
.news .sec-head .more{font-size:13px;color:var(--kin);min-height:44px;display:inline-flex;align-items:center}
.newslist{list-style:none;margin:0 0 8px;padding:0;border-top:1px solid var(--kin)}
.newslist li{display:grid;grid-template-columns:minmax(0,1fr);gap:4px;padding:14px 0;border-bottom:1px solid var(--line);font-size:14px;line-height:1.8}
@media(min-width:640px){.newslist li{grid-template-columns:7.5em minmax(0,1fr);gap:16px}}
.newslist time{font-family:var(--roman);font-size:13px;letter-spacing:.08em;color:var(--usu)}
.newslist p{margin:0;overflow-wrap:anywhere}
.newsnone{font-size:14px;color:var(--usu);padding:14px 0}
.util .nb b{font-weight:600}
.newtag{position:absolute;left:8px;top:8px;background:var(--kin);color:#fff;font-family:var(--gothic);font-size:10.5px;font-weight:600;letter-spacing:.14em;padding:3px 8px}
"""
# ブログのCSSを先に読み込む（build_blog.py は ROOT, BASE 等を参照するので、ここで import できる）
from build_blog import BLOG_CSS
# 2026-10-31 龍さん要望：商品写真をクリック（タップ）すると大きく開き、もう一度押すとズーム（Amazonのような見え方）
ZOOM_CSS = """
.gal img{cursor:zoom-in}
.lb{position:fixed;inset:0;z-index:1000;background:#120A07;display:flex;align-items:center;justify-content:center;touch-action:none;overscroll-behavior:contain}
.lb[hidden]{display:none}
.lb .lbv{width:100%;height:100%;overflow:hidden;display:flex;align-items:center;justify-content:center}
.lb .lbv img{max-width:100%;max-height:100%;object-fit:contain;cursor:zoom-in;transition:transform .25s ease;user-select:none;-webkit-user-drag:none}
.lb.zoom .lbv img{cursor:zoom-out;transition:none}
.lb button{position:absolute;background:rgba(244,240,232,.92);color:#120A07;border:0;width:48px;height:48px;font-size:22px;line-height:48px;cursor:pointer;font-family:var(--gothic)}
.lb .lbx{top:12px;right:12px}
.lb .lbp{left:12px;top:50%;transform:translateY(-50%)}
.lb .lbn{right:12px;top:50%;transform:translateY(-50%)}
.lb .lbc{position:absolute;left:12px;top:12px;line-height:24px;color:#F4F0E8;font-size:13px;font-variant-numeric:tabular-nums;background:rgba(18,10,7,.6);padding:4px 12px}
.lb .lbh{position:absolute;left:50%;bottom:16px;transform:translateX(-50%);color:#F4F0E8;font-size:12px;opacity:.8;white-space:nowrap}
.lb.zoom .lbh,.lb.zoom .lbp,.lb.zoom .lbn{display:none}
@media(max-width:640px){.lb .lbp,.lb .lbn{display:none}}
"""
write('/assets/site.css', CSS.strip() + '\n' + A11Y_CSS.strip() + '\n' + NEWS_CSS.strip() + '\n' + BLOG_CSS.strip() + '\n' + NAV_CSS.strip() + '\n' + ZOOM_CSS.strip() + '\n')

# 2026-10-23 龍さん決定：トップにブログの新着3本を写真つきで出す（日本語だけ。ブログは日本語のみのため）
def blog_top_html(lang, n=3):
    if lang != 'ja':
        return ''
    try:
        from build_blog import load_posts, cover_src
    except Exception:
        return ''
    posts = [p for p in load_posts() if not p.get('_draft')]
    posts.sort(key=lambda p: (p['date'], p['slug']), reverse=True)
    if not posts:
        return ''
    cards = ''.join(f'''<a href="/blog/{p['slug']}/" class="blog-card"><div class="blog-card-img"><img src="{esc(cover_src(p))}" alt="" loading="lazy" decoding="async"></div>'''
                    f'''<div class="blog-card-body"><time datetime="{p['date']}">{p['date'].replace('-', '.')}</time><h3>{esc(p['title'])}</h3></div></a>''' for p in posts[:n])
    return f'''    <section class="blogtop" aria-labelledby="blog-h">
      <div class="sec-head"><h2 id="blog-h">Blog<small>ブログ</small></h2><a class="more" href="/blog/">すべて見る</a></div>
      <div class="blog-grid blog-grid-3">{cards}</div>
    </section>
'''

# ---------- 一覧 ----------
# 2026-10-21 龍さん「新着が一番上に出てこない」：一覧（全部・絞り込み・ジャーナル）を公開日の新しい順に。同じ日は products.json の順
BLOG_SLUGS = {os.path.splitext(os.path.basename(f))[0] for f in glob.glob(os.path.join(ROOT, 'data/blog/posts/*.json'))}
live = sorted([p for p in products if release(p) == 'live'], key=lambda p: str(p.get('published_date', '')), reverse=True)
avail_live = [p for p in live if not is_sold(p)]
_prices = sorted(site_price(p) for p in avail_live) or [0]
PRICE_RANGE = f'¥{_prices[0]:,}〜¥{_prices[-1]:,}'
CATS_PRESENT = [c for c in ['outer', 'tops', 'bottoms', 'dress', 'shoes', 'acc', 'other'] if any(cat_of(p) == c for p in live)]

def alt_img(p):
    """2枚目の写真（PCでカーソルを乗せた時だけ見える）。マネキン画像は使わない"""
    ims = [u for u in p.get('images', [])[1:] if u != (p.get('photo_v2') or {}).get('mannequin_url')]
    return f'<img class="alt" src="{esc(ims[0].replace("/large/", "/medium/"))}" alt="" loading="lazy" aria-hidden="true">' if ims and not is_sold(p) else ''

NEW_DAYS = 6   # 2026-10-22 龍さん：水曜の公開から次の水曜の公開の前日まで「NEW」を付ける（毎週水曜に作り直されるので、先週分は自然に外れる）

def is_new(p):
    try:
        d = datetime.date.fromisoformat(str(p.get('published_date', ''))[:10])
        return (datetime.date.fromisoformat(TODAY) - d).days <= NEW_DAYS
    except ValueError:
        return False

def card_html(p, lang, lazy=True, findable=False):
    t = T[lang]
    w = body_width(p)
    sold = is_sold(p)
    lz = ' loading="lazy"' if lazy else ''
    tag = '' if sold else f'<span class="tag">{t["one"]}</span>'
    if not sold and is_new(p):   # 2026-10-22 龍さん：新着が分かるように（公開から NEW_DAYS 日以内）
        tag += '<span class="newtag">NEW</span>'
    wv = '' if w is None else f'{w:g}'
    return (f'<a class="card{" sold" if sold else ""}" href="{pre(lang)}/journal/{p["slug"]}/" data-cat="{cat_of(p)}" data-new="{1 if (not sold and is_new(p)) else 0}" data-w="{wv}" data-sold="{1 if sold else 0}"' + (f' data-p="{site_price(p)}" data-q="{esc(search_text(p))}"' if findable else '') + '>'
            f'<div class="ph"><img src="{esc(thumb_of(p))}" alt="{esc(loc(p, "product_name", lang))}"{lz}>{alt_img(p)}{tag}</div>'
            f'<div class="brand">{esc(p["brand"])}</div><div class="nm">{esc(loc(p, "product_name", lang))}</div>'
            f'<span class="fit" hidden></span>'
            f'<div class="pr">{money(site_price(p), lang)}<small>{t["tax"]}</small></div></a>')

def tiles_html(lang):
    """トップ最上段の写真タイル（カテゴリごとに新しい順の1枚目）。写真が主役・文字は最小限。"""
    P = pre(lang)
    out = []
    for c in CATS_PRESENT:
        ps = [p for p in avail_live if cat_of(p) == c]
        if not ps:
            continue
        ps = sorted(ps, key=lambda p: p.get('published_date', ''), reverse=True)
        img = thumb_of(ps[0])
        lab = CAT_EN[c].upper()
        out.append(f'<a class="tile" href="{P}/?cat={c}#list" data-cat="{c}"><img src="{esc(img)}" alt="{esc(T[lang]["cats"][c])}"'
                   + (' fetchpriority="high"' if not out else ' loading="lazy"') + f'><span class="tt"><b>{lab} - NEW ARRIVAL</b><i>SHOP NOW</i></span></a>')
    return ''.join(out[:6])

BLOCK_MAX = 8   # 1ジャンルのブロックに出す点数（新しい順）

def blocks_html(lang):
    """2026-10-09 トップの一覧をジャンルごとのブロックに分ける（絞り込み・身幅・SOLD表示を使った時は、今までどおり全部の一覧に切り替わる）"""
    t = T[lang]
    out = []
    news = [p for p in avail_live if is_new(p)]   # 2026-10-22 龍さん：トップのジャンル別の一番上に「新着」のブロック
    if news:
        cards = ''.join(card_html(p, lang) for p in news[:BLOCK_MAX])
        out.append(f'<section class="block" data-cat="new"><div class="bhead"><h3>NEW ARRIVAL<small>{NEW_LABEL[lang]}</small></h3>'
                   f'<button type="button" class="ball" data-filter="new">{t["see_all"]}<span>{len(news)}{t["unit"]}</span></button></div>'
                   f'<div class="brow">{cards}</div></section>')
    for c in CATS_PRESENT:
        ps = sorted([p for p in avail_live if cat_of(p) == c], key=lambda p: p.get('published_date', ''), reverse=True)
        if not ps:
            continue
        cards = ''.join(card_html(p, lang) for p in ps[:BLOCK_MAX])
        out.append(f'<section class="block" data-cat="{c}"><div class="bhead"><h3>{CAT_EN[c].upper()}<small>{t["cats"][c]}</small></h3>'
                   f'<button type="button" class="ball" data-filter="{c}">{t["see_all"]}<span>{len(ps)}{t["unit"]}</span></button></div>'
                   f'<div class="brow">{cards}</div></section>')
    return '\n'.join(out)

NEW_LABEL = {'ja': '新着', 'en': 'New in'}   # 2026-10-22 龍さん「NEWだけを見る欄がない」

def catrow(lang):
    t = T[lang]
    new = (f'<button type="button" data-filter="new" aria-pressed="false">{NEW_LABEL[lang]}<small>NEW</small></button>'
           if any(is_new(p) for p in avail_live) else '')
    return new + ''.join(f'<button type="button" data-filter="{c}" aria-pressed="false">{t["cats"][c]}<small>{CAT_EN[c]}</small></button>' for c in CATS_PRESENT)

def finder(lang):
    t = T[lang]
    return f'''<div class="finder">
  <div class="frow"><label for="kw">{t['kw_l']}</label><input type="search" id="kw" maxlength="40" autocomplete="off" placeholder="{esc(t['kw_ph'])}"></div>
  <span class="fgrp"><label for="pr">{t['pr_l']}</label><select id="pr"><option value="">{t['pr_all']}</option>{''.join(f'<option value="{i}">{b}</option>' for i, b in enumerate(t['pr_bands']))}</select></span>
  <label for="myw">{t['finder_l']}</label>
  <input type="number" id="myw" inputmode="decimal" min="30" max="90" step="0.5" placeholder="55">
  <span>{t['finder_u']}</span>
  <label class="chk"><input type="checkbox" id="showsold"> {t['finder_sold']}</label>
  <button type="button" class="clear" id="clear">{t['finder_clear']}</button>
  <span class="hint">{t['finder_hint']}</span>
</div>'''

def list_js(lang):
    t = T[lang]
    msg = json.dumps({'empty_w': t['empty_w'], 'empty': t['empty'], 'fit': t['fit'], 'same': t['same'], 'unit': t['unit'],
                      'labels': dict(t['cats'], new=NEW_LABEL[lang]), 'here': 'いま見ているのは' if lang == 'ja' else 'Showing',
                      'shown': '{c}を表示（{n}）' if lang == 'ja' else 'Showing {c} ({n})', 'all': 'すべての商品を表示' if lang == 'ja' else 'Showing all items', 'bands': PRICE_BANDS}, ensure_ascii=False)
    return '''<script>
(function(){
  var M=''' + msg + ''';
  var filter=null, grid=document.getElementById('grid'); if(!grid) return;
  var kw=document.getElementById('kw'), pr=document.getElementById('pr'), myw=document.getElementById('myw'), showsold=document.getElementById('showsold'), cnt=document.getElementById('count'), blocks=document.getElementById('blocks');
  var empty=document.createElement('div'); empty.className='empty'; empty.hidden=true; grid.appendChild(empty);
  function apply(){
    var my=parseFloat(myw.value), n=0;
    var words=(kw?kw.value:'').normalize('NFKC').toLowerCase().replace(/['’`]/g,'').split(/\\s+/).filter(Boolean), band=(pr&&pr.value!=='')?M.bands[+pr.value]:null;
    var plain=!filter&&isNaN(my)&&!showsold.checked&&!words.length&&!band;   // 何も絞っていない時はジャンルごとのブロックを見せる
    if(blocks){blocks.hidden=!plain; grid.hidden=plain;}
    grid.querySelectorAll('.card').forEach(function(c){
      var ok=(!filter||(filter==='new'?c.dataset.new==='1':c.dataset.cat===filter))&&(showsold.checked||c.dataset.sold!=='1');
      var w=c.dataset.w===''?null:parseFloat(c.dataset.w), fit=c.querySelector('.fit');
      if(!isNaN(my)) ok=ok&&w!==null&&Math.abs(w-my)<=3;
      if(words.length){var q=c.dataset.q||''; ok=ok&&words.every(function(x){return q.indexOf(x)>=0;});}
      if(band){var pv=parseInt(c.dataset.p,10)||0; ok=ok&&pv>=band[0]&&pv<band[1];}
      if(!isNaN(my)&&w!==null){var d=w-my; fit.textContent=M.fit.replace('{w}',w).replace('{d}',d===0?M.same:(d>0?'+':'')+d.toFixed(1)+'cm'); fit.hidden=false;} else fit.hidden=true;
      c.hidden=!ok; if(ok) n++;
    });
    empty.hidden=n>0;
    empty.textContent=!isNaN(my)?M.empty_w.replace('{w}',my):M.empty;
    if(cnt) cnt.textContent=n+M.unit;
    document.querySelectorAll('.catrow button').forEach(function(b){b.setAttribute('aria-pressed',String(b.dataset.filter===filter));});
    var hb=document.getElementById('herebar');
    if(hb){hb.hidden=!filter; if(filter) document.getElementById('herego').innerHTML=M.here+' <b>'+(M.labels[filter]||filter)+'</b>（'+n+M.unit+'）';}
    return n;
  }
  function tell(){var n=apply(); if(window.kzToast) kzToast(filter?M.shown.replace('{c}',M.labels[filter]||filter).replace('{n}',n+M.unit):M.all);}
  var hg=document.getElementById('herego'); if(hg) hg.addEventListener('click',function(){var l=document.getElementById('list');if(l)l.scrollIntoView({behavior:'smooth'});});
  var hbk=document.getElementById('hereback'); if(hbk) hbk.addEventListener('click',function(){filter=null;tell();history.replaceState(null,'',location.pathname+'#list');});
  document.querySelectorAll('.catrow button').forEach(function(b){b.addEventListener('click',function(){filter=(filter===b.dataset.filter?null:b.dataset.filter);tell();});});
  document.querySelectorAll('.ball').forEach(function(b){b.addEventListener('click',function(){filter=b.dataset.filter;tell();var l=document.getElementById('list');if(l)l.scrollIntoView({behavior:'smooth'});});});
  var q=(location.search.match(/[?&]cat=([a-z]+)/)||[])[1]; if(q&&document.querySelector('.catrow button[data-filter="'+q+'"]')) filter=q;
  document.addEventListener('kz:cat',function(e){filter=e.detail||null;tell();});
  myw.addEventListener('input',apply); showsold.addEventListener('change',apply); if(kw) kw.addEventListener('input',apply); if(pr) pr.addEventListener('change',apply);
  document.getElementById('clear').addEventListener('click',function(){myw.value='';if(kw)kw.value='';if(pr)pr.value='';showsold.checked=false;filter=null;apply();});
  apply();
  var td=document.getElementById('today');
  if(td){var j=new Date(Date.now()+(new Date().getTimezoneOffset()+540)*60000),dw=j.getDay(),ymd=j.getFullYear()+'-'+('0'+(j.getMonth()+1)).slice(-2)+'-'+('0'+j.getDate()).slice(-2),hol='''+json.dumps(HOLIDAY_MONDAYS)+''',open=(ymd>='''+"'"+NEWHOURS_FROM+"'"+'''?[1]:'''+CLOSED_WEEKDAYS_JS+''').indexOf(dw)<0||hol.indexOf(ymd)>=0;
    td.textContent=open?td.dataset.open:td.dataset.closed; if(!open) td.className='today closed'; td.hidden=false;}
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
    cards = '\n'.join(card_html(p, lang, findable=True) for p in live)   # 検索用の文字は絞り込む一覧のカードだけに付ける（ページを重くしない）
    top_ld = {'@context': 'https://schema.org', '@graph': [org_node(), faq_ld(lang),
              {'@type': 'WebSite', '@id': BASE + P + '/#website', 'url': BASE + P + '/', 'name': SHOP['name'], 'inLanguage': lang,
               'publisher': {'@id': BASE + '/#store'}}]}
    faq_html = '\n'.join(f'    <details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>' for q, a in FAQ[lang])
    trust = ''.join(f'<div><b>{h}</b><span>{s.format(gm=SHOP["gmaps"])}</span></div>' for h, s in t['trust'])
    store_dl = ''.join(f'<dt>{k}</dt><dd>{ADDR[lang] + " ・ <a href=" + chr(34) + SHOP["gmaps"] + chr(34) + " rel=" + chr(34) + "noopener" + chr(34) + ">" + t["gm"] + "</a>" if v is None else v}</dd>' for k, v in t['store_dl'])
    hero_alt = '小判鮫の店内（川越・元町の古民家）' if lang == 'ja' else 'Inside Kobanzame, an old wooden house in Kawagoe'
    # お知らせ欄（日本語のトップだけ・お知らせが1件以上あるときだけ出す）
    news_section = '' if (lang != 'ja' or not NEWS) else f'''  <section class="news" id="news" aria-labelledby="news-h">
    <div class="wrap">
      <div class="sec-head"><h2 id="news-h">News<small>お知らせ</small></h2>{'<a class="more" href="/news/">すべて見る</a>' if len(NEWS) > NEWS_TOP else ''}</div>
      <ul class="newslist">
{news_items_html(NEWS[:NEWS_TOP])}
      </ul>
    </div>
  </section>
'''
    top = head(lang, t['top_title'], t['top_desc'], P + '/', extra_ld=top_ld) + f'''
<main>
  <section class="tiles" aria-label="{'カテゴリ' if lang == 'ja' else 'Categories'}">
    <div class="wrap tgrid">{tiles_html(lang)}</div>
  </section>
  <section class="hero">
    <div class="wrap">
      <div class="hero-ph">
        <img class="hero-img" src="{esc(HERO_SRC)}"{HERO_SRCSET} alt="{hero_alt}" fetchpriority="high">
        <div class="herobox">
          <div class="days"><b>{t['days_h']}</b>{t['days']}<span class="today" id="today" hidden data-open="{t['today_open']}" data-closed="{t['today_closed']}"></span></div>
          <a class="maplink" href="{SHOP['gmaps']}" rel="noopener">{PIN}{t['map']}</a>
        </div>
      </div>
      <div class="hero-copy">
        <h1>{t['hero_h']}</h1>
        <p>{t['hero_p']}</p>
        <a class="btn" href="#list">{t['hero_btn']}</a>
      </div>
    </div>
  </section>
{news_section}  <div class="wrap">
    <div class="herebar" id="herebar" hidden><button type="button" class="here" id="herego"></button><button type="button" class="back" id="hereback">{'すべての商品に戻る' if lang == 'ja' else 'Show all'}</button></div>
    <div class="catrow" role="group">{catrow(lang)}</div>
    <div class="sec-head" id="list"><h2>{t['list_h']}<small>{t['list_s']}</small></h2><span class="count" id="count">{len(avail_live)}{t['unit']}</span></div>
    {finder(lang)}
    <div class="blocks" id="blocks">
{blocks_html(lang)}
    </div>
    <div class="grid" id="grid" hidden>
{cards}
    </div>
{blog_top_html(lang)}    <div class="trust">{trust}</div>
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
  <div class="sec-head jhead"><h1>{t['journal_h']}<small>{t['journal_s']}</small></h1><span class="count" id="count">{len(avail_live)}{t['unit']}</span></div>
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
/* 2026-10-31 写真の拡大表示：写真を押す→全画面で開く／もう一度押す→2.5倍ズーム（PCはマウスを動かすと見る場所が動く・スマホは指でなぞる）／左右で次の写真／Escか×で閉じる */
(function(){
  var g=document.getElementById('gal'); if(!g) return;
  var ims=[].slice.call(g.querySelectorAll('img')); if(!ims.length) return;
  var en=document.documentElement.lang==='en', S=2.5, lb, view, big, cnt, cur=0, zoomed=false, ox=50, oy=50, dn=null;
  function build(){
    lb=document.createElement('div'); lb.className='lb'; lb.hidden=true;
    lb.setAttribute('role','dialog'); lb.setAttribute('aria-modal','true'); lb.setAttribute('aria-label',en?'Photo viewer':'写真の拡大表示');
    lb.innerHTML='<div class="lbv"><img alt=""></div><div class="lbh"></div><div class="lbc"></div>'
      +'<button type="button" class="lbp" aria-label="'+(en?'Previous photo':'前の写真')+'">&#8249;</button>'
      +'<button type="button" class="lbn" aria-label="'+(en?'Next photo':'次の写真')+'">&#8250;</button>'
      +'<button type="button" class="lbx" aria-label="'+(en?'Close':'閉じる')+'">&#10005;</button>';
    document.body.appendChild(lb);
    view=lb.querySelector('.lbv'); big=view.querySelector('img'); cnt=lb.querySelector('.lbc');
    lb.querySelector('.lbh').textContent=en?'Tap the photo to zoom':'写真を押すとズームします';
    lb.querySelector('.lbx').addEventListener('click',close);
    lb.querySelector('.lbp').addEventListener('click',function(){show(cur-1);});
    lb.querySelector('.lbn').addEventListener('click',function(){show(cur+1);});
    view.addEventListener('pointerdown',function(e){dn={x:e.clientX,y:e.clientY,ox:ox,oy:oy};});
    view.addEventListener('pointermove',function(e){
      if(!zoomed) return;
      if(e.pointerType==='mouse'&&!dn){ /* PC：マウスの位置を見る（Amazonと同じ） */
        var w=big.offsetWidth, h=big.offsetHeight, L=(view.clientWidth-w)/2, T=(view.clientHeight-h)/2, vr=view.getBoundingClientRect();
        setO((e.clientX-vr.left-L)/w*100,(e.clientY-vr.top-T)/h*100); return; }
      if(dn){ /* 指（またはマウスのドラッグ）でなぞる：なぞった方向に写真が動く */
        setO(dn.ox-(e.clientX-dn.x)/big.offsetWidth*100/(S-1), dn.oy-(e.clientY-dn.y)/big.offsetHeight*100/(S-1)); }
    });
    view.addEventListener('pointerup',function(e){
      if(!dn) return; var dx=e.clientX-dn.x, dy=e.clientY-dn.y, moved=Math.abs(dx)>10||Math.abs(dy)>10; dn=null;
      if(!moved){ if(e.target===big) toggle(e); else if(!zoomed) close(); return; }
      if(!zoomed&&Math.abs(dx)>50&&Math.abs(dx)>Math.abs(dy)) show(cur+(dx<0?1:-1));
    });
    view.addEventListener('pointercancel',function(){dn=null;});
    document.addEventListener('keydown',function(e){
      if(lb.hidden) return;
      if(e.key==='Escape'){ zoomed?unzoom():close(); }
      else if(e.key==='ArrowRight') show(cur+1);
      else if(e.key==='ArrowLeft') show(cur-1);
    });
  }
  function setO(x,y){ ox=Math.max(0,Math.min(100,x)); oy=Math.max(0,Math.min(100,y)); big.style.transformOrigin=ox+'% '+oy+'%'; }
  function toggle(e){
    if(zoomed){ unzoom(); return; }
    var w=big.offsetWidth, h=big.offsetHeight, vr=view.getBoundingClientRect(), L=(view.clientWidth-w)/2, T=(view.clientHeight-h)/2;
    setO((e.clientX-vr.left-L)/w*100,(e.clientY-vr.top-T)/h*100);
    zoomed=true; lb.classList.add('zoom'); big.style.transform='scale('+S+')';
  }
  function unzoom(){ zoomed=false; lb.classList.remove('zoom'); big.style.transform=''; }
  function show(i){
    var n=ims.length; cur=(i%n+n)%n; unzoom(); setO(50,50);
    big.src=ims[cur].currentSrc||ims[cur].src; big.alt=ims[cur].alt||''; cnt.textContent=(cur+1)+' / '+n;
  }
  var opener=null;
  function open(i){ if(!lb) build(); opener=document.activeElement; show(i); lb.hidden=false; document.documentElement.style.overflow='hidden'; lb.querySelector('.lbx').focus(); }
  function close(){ unzoom(); lb.hidden=true; document.documentElement.style.overflow=''; if(opener&&opener.focus) opener.focus(); }
  ims.forEach(function(im,i){
    im.setAttribute('tabindex','0'); im.setAttribute('role','button');
    im.setAttribute('aria-label',(im.alt||'')+(en?' (open larger)':'（拡大して見る）'));
    var sx=0, sy=0;
    im.addEventListener('pointerdown',function(e){sx=e.clientX; sy=e.clientY;});
    im.addEventListener('click',function(e){ if(Math.abs(e.clientX-sx)>10||Math.abs(e.clientY-sy)>10) return; open(i); }); /* スマホで横にめくった時は開かない */
    im.addEventListener('keydown',function(e){ if(e.key==='Enter'||e.key===' '){ e.preventDefault(); open(i);} });
  });
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
                 'hasMerchantReturnPolicy': {'@type': 'MerchantReturnPolicy', 'applicableCountry': 'JP', 'returnPolicyCategory': 'https://schema.org/MerchantReturnNotPermitted'},
                 'shippingDetails': {'@type': 'OfferShippingDetails',
                                     'shippingRate': {'@type': 'MonetaryAmount', 'value': '0', 'currency': 'JPY'},
                                     'shippingDestination': {'@type': 'DefinedRegion', 'addressCountry': 'JP'},
                                     'deliveryTime': {'@type': 'ShippingDeliveryTime',
                                                      'handlingTime': {'@type': 'QuantitativeValue', 'minValue': 0, 'maxValue': 3, 'unitCode': 'DAY'},
                                                      'transitTime': {'@type': 'QuantitativeValue', 'minValue': 1, 'maxValue': 3, 'unitCode': 'DAY'}}}}
        author = {'@type': 'Person', 'name': '龍' if lang == 'ja' else 'Ryu', 'jobTitle': '小判鮫オーナー・専属バイヤー' if lang == 'ja' else 'Owner & buyer, Kobanzame', 'worksFor': {'@id': BASE + '/#store'}}
        ld = {'@context': 'https://schema.org', '@graph': [
            {'@type': 'Product', '@id': BASE + path + '#product', 'name': name, 'sku': p['sku'],
             'description': loc(p, 'summary_text', lang), 'image': [abs_url(u) for u in real_images(p)], 'brand': {'@type': 'Brand', 'name': p['brand']},
             'material': p.get('material', ''), 'category': p.get('category', ''), 'offers': offer,
             **({'color': color_of(p)} if color_of(p) else {}), **({'size': size_of(p)} if size_of(p) else {}),
             'audience': {'@type': 'PeopleAudience', 'suggestedGender': gender_of(p)},
             'additionalProperty': [{'@type': 'PropertyValue', 'name': k, 'value': v} for k, v in p.get('spec', []) if k not in ('発送',)],
             **({'subjectOf': {'@type': 'BlogPosting', 'url': BASE + '/blog/' + p['slug'] + '/'}} if p['slug'] in BLOG_SLUGS else {})},
            {'@type': 'BlogPosting', '@id': BASE + path + '#article', 'headline': loc(p, 'title', lang), 'image': abs_url(p['images'][0]),
             'datePublished': p.get('published_date', TODAY), 'dateModified': TODAY, 'inLanguage': lang,
             'author': author, 'publisher': {'@id': BASE + '/#store'}, 'about': {'@id': BASE + path + '#product'}, 'mainEntityOfPage': BASE + path},
            {'@type': 'BreadcrumbList', 'itemListElement': [
                {'@type': 'ListItem', 'position': 1, 'name': 'HOME', 'item': BASE + P + '/'},
                {'@type': 'ListItem', 'position': 2, 'name': t['cats'][cat_of(p)], 'item': BASE + P + f'/?cat={cat_of(p)}'},
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
        hold = '' if (sold or not HOLD_ENABLED) else f'''<button type="button" class="btn ghost" id="holdbtn" aria-expanded="false" aria-controls="holdbox">{t['hold_btn'].format(n=HOLD_DAYS)}</button>
        <div class="holdbox" id="holdbox" hidden>
          <p>{t['hold_p'].format(n=HOLD_DAYS)}</p>
          <p><code>{esc(t['hold_code'].format(sku=p['sku']))}</code></p>
          <p>{t['hold_to']}：<a href="{SHOP['instagram']}" rel="noopener">Instagram（{SHOP['ig_handle']}）</a> ／ {t['hold_mail']} <code>{SHOP['email']}</code></p>
          <p class="ship">{t['hold_note']}</p>
        </div>'''
        noen = f'<p class="noen">{t["no_en"]}</p>' if (lang == 'en' and not has_en(p)) else ''
        draft_banner = f'<div class="draftnote">{t["draft"]}</div>' if rel == 'draft' else ''
        relp = reco_of(p, avail_live)   # 2026-10-29 点数づけ（reco_score）に変更
        rel_cards = ''.join(card_html(x, lang) for x in relp)
        related = f'<section class="related"><h2>Recommended<small>{t["related"]}</small></h2><div class="grid">{rel_cards}</div></section>' if rel_cards else ''
        ttl = loc(p, 'title', lang)
        if lang == 'en' and not has_en(p):
            _b = p['brand'] if str(p.get('brand', '')).isascii() and p.get('brand') else 'Vintage'
            ttl = f"{_b} {CAT_EN.get(cat_of(p), '')} ({p['sku']})".replace('  ', ' ').strip()
        suf = f"｜{SHOP['name']}" if lang == 'ja' else ' | Kobanzame Vintage, Kawagoe'
        if len(ttl + suf) > 60:
            suf = '｜小判鮫 川越' if lang == 'ja' else ' | Kobanzame'
        pdesc = loc(p, 'summary_text', lang)
        if lang == 'en' and not has_en(p):   # 訳が無い商品の英語ページは、日本語ページと同じ説明文にしない
            pdesc = f"{_b} {CAT_EN.get(cat_of(p), 'item')} ({p['sku']}), one of a kind, at Kobanzame vintage clothing shop in Kawagoe, Japan. Full description in Japanese."
        page = head(lang, ttl + suf, pdesc, path, og_type='article',
                    image=imgs[0], extra_ld=ld, noindex=(p.get('noindex', False) or rel == 'draft')) + f'''{draft_banner}
<main class="wrap">
  <div class="crumb"><a href="{P}/">HOME</a><span>／</span><a href="{P}/?cat={cat_of(p)}#list">{t['cats'][cat_of(p)]}</a><span>／</span><span>{esc(p['sku'])}</span></div>
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
      {('<p class="toblog"><a href="/blog/' + p['slug'] + '/">' + ('この一着のことをブログで読む →' if lang == 'ja' else 'Read about this piece on our blog (Japanese) →') + '</a></p>') if p['slug'] in BLOG_SLUGS else ''}
    </div>
  </div>
  {related}
</main>
{bar}
{GAL_JS}
''' + foot(lang)
        write(path + 'index.html', page)

    # 404（日本語は /404.html、英語は /en/404.html。2026-10-08 英語切り替えのリンク切れを修正）
    if lang == 'ja':
        nf = head('ja', 'ページが見つかりません｜古着屋 小判鮫 KOBANZAME', 'お探しのページは見つかりませんでした。', '/404.html', noindex=True) + f'''
<main class="wrap nf"><h1>Not Found</h1><p>{t['nf_p']}</p><a class="btn" href="/#list">{t['nf_btn']}</a></main>
''' + foot('ja')
        write('/404.html', nf)
    else:
        nf = head('en', 'Page not found | Kobanzame vintage, Kawagoe', 'We could not find that page.', '/en/404.html', noindex=True) + f'''
<main class="wrap nf"><h1>Not Found</h1><p>{t['nf_p']}</p><a class="btn" href="/en/#list">{t['nf_btn']}</a></main>
''' + foot('en')
        write('/en/404.html', nf)

# ---------- 特定商取引法に基づく表記（日本語） ----------
LAW = [
    ('販売業者', SHOP['company']), ('運営統括責任者', '嶋崎龍'), ('所在地', ADDR['ja']),
    ('電話番号', '請求があった場合には遅滞なく開示いたします。'), ('メールアドレス', SHOP['email']),
    ('販売価格', '各商品ページに税込価格で表示しています。'),
    ('商品代金以外の必要料金', '送料は販売価格に含まれます（当店負担）。決済手数料はかかりません。'),
    ('支払方法', 'クレジットカード（Square の決済ページで決済）'), ('支払時期', 'ご注文時に決済が確定します。'),
    ('引渡時期', 'ご注文（決済）の確認後、3日以内（' + '定休日' + 'を除く）に発送します。'), ('販売数量', '各商品とも1点限りです。'),
    ('返品・交換', '古着・一点ものの性質上、お客様都合による返品・交換はお受けしておりません。商品説明と著しく異なる場合や当店の発送間違いの場合は、商品到着後4日以内にメールでご連絡ください。返品送料は当店が負担し、返金または交換にて対応いたします。'),
    ('申込みの撤回・解除', '通信販売にはクーリング・オフ制度は適用されません。上記「返品・交換」の条件に従います。'),
    ('品切れの場合', '店頭・他の販路で先に売れた場合は、ご注文をお受けできないことがあります。その際はご連絡のうえ全額返金いたします。'),
    ('古物商許可', f"{SHOP['kobutsu']}（{SHOP['company']}）"),
]
law_html = ''.join(f'<dt>{esc(k)}</dt><dd>{esc(v)}</dd>' for k, v in LAW)
write('/tokushoho/index.html', head('ja', '特定商取引法に基づく表記｜古着屋 小判鮫', '古着屋 小判鮫（運営：株式会社プラグ）の特定商取引法に基づく表記。販売価格（税込・送料込み）、支払い方法、発送の時期、返品・交換の条件、古物商許可番号を載せています。', '/tokushoho/') + f'''
<main class="wrap page lawtable"><h1>特定商取引法に基づく表記</h1><dl>{law_html}</dl><p style="color:var(--usu);font-size:13px;margin-top:24px">制定：2026年9月30日</p></main>
''' + foot('ja'))

write('/privacy/index.html', head('ja', 'プライバシーポリシー｜古着屋 小判鮫', '古着屋 小判鮫（運営：株式会社プラグ）のプライバシーポリシー。ご注文やお問い合わせでお預かりする個人情報の使い道と、カード情報の扱い（Square が処理し、当店は持たない）について。', '/privacy/') + f'''
<main class="wrap page">
  <h1>プライバシーポリシー</h1>
  <p>古着屋 小判鮫（運営：{SHOP['company']}。以下「当店」）は、お客様の個人情報を適切に取り扱います。</p>
  <h2>取得する情報</h2><p>ご注文・お問い合わせ・販売（外部プラットフォームを含む）に際して、お名前・連絡先・配送先など、取引に必要な範囲の情報を取得します。</p>
  <h2>利用目的</h2><p>商品の発送、お問い合わせへの対応、取引に必要なご連絡のために利用し、目的の範囲を超えて利用しません。</p>
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
  <h2>Privacy</h2><p>We collect only what an order or inquiry needs (name, contact, delivery address) and use it only for that purpose. Card details are processed by Square; we never receive or store card numbers. We do not share personal data without consent except as required by law or for delivery.</p>
</main>
''' + foot('en'))

# ---------- ワークショップのページ（WS_FROM 以降だけ作る） ----------
if WS_OPEN:
    for lang in ('ja', 'en'):
        P = pre(lang)
        path = P + '/workshop/'
        if lang == 'ja':
            title = 'ワークショップ｜古着屋 小判鮫（川越・元町の古民家）'
            desc = '川越・元町の古民家古着屋 小判鮫のワークショップ。真鍮バングル、天然石ビーズブレスレット。' + ('10月24日（土）開催。ご予約はオンラインで。' if WS_BOOKING else '予約の受付は準備中です。')
            h1, intro = 'ワークショップ', '小判鮫の店内で、ものづくりの時間を。どちらも完成品はその場でお持ち帰りいただけます。'
            limited = '税込・10/24開催分'
            end_note = '10/25以降の開催日と料金は、決まり次第このページとInstagramでお知らせします。'
            meta = '所要 約{m}分・1回 最大{n}名'
            btn = '予約する（日時を選ぶ）'
            btn_off = '予約は準備中です（受付を始めたら、このページと Instagram でお知らせします）'
            place = f'会場：古着屋 小判鮫（{ADDR["ja"]}）／' + ('定休日 月曜（祝日は営業）' if NEWHOURS else '定休日 月曜・火曜')
        else:
            title = 'Workshops | Kobanzame, Kawagoe'
            desc = 'Workshops at Kobanzame, a vintage shop in an old wooden house in Kawagoe: brass bangle and natural stone bead bracelet. ' + ('Held on Saturday 24 October. Book online.' if WS_BOOKING else 'Online booking is coming soon.')
            h1, intro = 'Workshops', 'Make something in our old wooden shop. You take your piece home the same day.'
            limited = 'tax incl., for the 24 Oct sessions'
            end_note = 'Dates and prices after 24 October will be announced on this page and on Instagram.'
            meta = 'About {m} min · up to {n} people per session'
            btn = 'Book a time'
            btn_off = 'Booking is coming soon (we will announce it here and on Instagram)'
            place = f'Venue: Kobanzame, {ADDR["en"]} / ' + ('closed Mondays (open on holidays)' if NEWHOURS else 'closed Mondays and Tuesdays')
        cards, svc = '', []
        for w in WORKSHOPS:
            x = w[lang]
            notes = ''.join(f'<li>{esc(n)}</li>' for n in x['notes'])
            cards += (f'<article id="{w["id"]}"><h2>{esc(x["name"])}</h2>'
                      f'<div class="price">{money(w["price"], lang)}<small>{limited}</small></div>'
                      f'<div class="meta">{meta.format(m=w["minutes"], n=w["max"])}</div>'
                      f'<p>{esc(x["lead"])}</p><ul>{notes}</ul>'
                      + (f'<a class="btn kin" href="{w["reserve"]}" rel="noopener">{btn}</a>' if WS_BOOKING else f'<p class="ws-off" role="note">{btn_off}</p>')
                      + '</article>')
            svc.append({'@type': 'Service', 'name': x['name'], 'description': x['lead'], 'provider': {'@id': BASE + '/#store'},
                        'areaServed': '川越市' if lang == 'ja' else 'Kawagoe',
                        'offers': dict({'@type': 'Offer', 'price': str(w['price']), 'priceCurrency': 'JPY'}, **({'url': w['reserve']} if WS_BOOKING else {}))})
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
  'desc': '埼玉県川越市元町の古民家古着屋 小判鮫の案内。場所・営業時間・定休日・扱っている古着・価格帯・通販の買い方をまとめました。',
  'h1': '川越で古着屋を探している方へ',
  'lead': '古着屋 小判鮫（こばんざめ／KOBANZAME）は、埼玉県川越市元町にある古着屋です。築約80年の古民家をそのまま使った店内に、国内外で買い付けたヴィンテージ古着と、オリジナルのリメイクアクセサリー「GAW」を並べています。川越観光のついでに立ち寄っていただける場所です。',
  'secs': [
   ('場所と営業時間', f'住所は{ADDR["ja"]}。蔵造りの町並みと同じ、川越の元町エリアにあります。' + ('営業は13:00〜20:00（7〜8月は22:00まで）、定休日は毎週月曜日です（祝日の月曜は営業）' if NEWHOURS else '営業は12:00〜20:00、定休日は毎週月曜日・火曜日です' + ('（2026年11月1日からは火曜〜日曜の13:00〜20:00・月曜定休）' if NOTICE else '')) + f'。臨時の休みや営業時間の変更はInstagram（{SHOP["ig_handle"]}）でお知らせします。'),
   ('どんな古着があるか', 'アメリカ・ヨーロッパなどのヴィンテージ古着を中心に、メンズ・レディースの両方を扱っています。アウター、シャツやTシャツ、ワンピース、靴、小物まで。ブランドや流行ではなく、素材・質感・その一点にしかない雰囲気で選んでいるので、すべて一点ものです。'),
   ('価格の目安', (f'このサイトに掲載中の一点ものは、{money(_pr[0], "ja")}〜{money(_pr[-1], "ja")}（税込・送料込み）です。店頭の価格は商品ごとに異なります。' if _pr else '価格は商品ごとに異なります。サイトに掲載中の商品ページでご確認ください。')),
   ('新着入荷', '毎週水曜日に新しい一点ものが入ります。このサイトにも水曜日の夜（20時台）に新着を掲載しています。'),
   ('GAW（オリジナルのリメイクアクセサリー）', '古いスプーンなどの素材を、ペンダントやバングルなどに作り直した、小判鮫オリジナルのアクセサリーです。こちらも一点ものです。'),
   ('取り置きについて', 'すべて一点ものなので、サイト・店頭ともお取り置きはしていません。先着順です。気になる一点は、お早めにご来店いただくか、このサイトからご購入ください。'),
   ('遠くて行けないとき', 'このサイトに載っている商品は、クレジットカード（Square決済）でそのまま購入できます。送料込みで、決済確認後3日以内（' + '定休日' + 'を除く）に川越の店舗から発送します。メルカリShopsでも販売しています。'),
   ('サイズ選びのコツ', '実寸は平置きで測っています。お手持ちのいちばん気に入っている服の身幅（脇の下から脇の下まで）を測って比べると、サイズの失敗が減ります。トップページの「手持ちの服の身幅」に数字を入れると、近いサイズの服だけを表示できます。'),
  ],
  'faq': [
   ('川越の小判鮫はどこにありますか？', f'{ADDR["ja"]}にあります。築約80年の古民家で営業している古着屋です。'),
   ('定休日はいつですか？', ('毎週月曜日が定休日です（祝日の月曜は営業）。営業時間は13:00〜20:00（7〜8月は22:00まで）です。臨時休業はInstagramでお知らせします。' if NEWHOURS else '毎週月曜日・火曜日が定休日です。営業時間は12:00〜20:00です。' + ('2026年11月1日からは、火曜〜日曜の13:00〜20:00営業・月曜定休になります。' if NOTICE else ''))),
   ('メンズもレディースもありますか？', 'あります。メンズ・レディースどちらのヴィンテージ古着も扱っています。'),
   ('新しい商品はいつ入りますか？', '毎週水曜日に新着が入ります。'),
   ('川越まで行けなくても買えますか？', 'このサイトからクレジットカードで購入できます（送料込み）。メルカリShopsでも販売しています。'),
  ],
  'cta': '掲載中の一点ものを見る', 'back': '/#list', 'crumb': '川越の古着屋 案内',
 },
 'en': {
  'path': '/en/guide/', 'title': 'Looking for a vintage shop in Kawagoe? | Kobanzame',
  'desc': 'A guide to Kobanzame, a vintage clothing shop in an old wooden house in Motomachi, Kawagoe, Saitama: location, hours, what we carry, prices and buying online.',
  'h1': 'Looking for a vintage shop in Kawagoe?',
  'lead': 'Kobanzame is a vintage clothing shop in Motomachi, Kawagoe, Saitama, set in an 80-year-old wooden house. We carry vintage clothing sourced in Japan and abroad, and GAW, our own line of remade accessories. It is an easy stop while you explore Kawagoe.',
  'secs': [
   ('Location and hours', f'{ADDR["en"]}, in the Motomachi area of Kawagoe, the same area as Kawagoe’s old kurazukuri (clay-walled merchant house) streets. ' + ('Open 13:00–20:00 (until 22:00 in July–August), closed every Monday except public holidays' if NEWHOURS else 'Open 12:00–20:00, closed every Monday and Tuesday' + (' (from 1 November 2026: Tuesday–Sunday 13:00–20:00, closed Mondays)' if NOTICE else '')) + f'. Changes are announced on Instagram ({SHOP["ig_handle"]}).'),
   ('What you will find', 'Mostly vintage clothing from the US and Europe, for men and women: outerwear, shirts and tees, dresses, shoes and small goods. We choose by material, texture and the feel of each piece rather than brand or trend, so everything is one of a kind.'),
   ('Prices', (f'Pieces listed on this site range from {money(_pr[0], "en")} to {money(_pr[-1], "en")} (tax and domestic shipping included). In-store prices vary by item.' if _pr else 'Prices vary by item. See each item page on this site.')),
   ('New arrivals', 'New pieces arrive every Wednesday, and go up on this site on Wednesday morning.'),
   ('GAW', 'Our own accessory line: old materials such as spoons remade into pendants, bangles and more. Each one is one of a kind.'),
   ('Holding a piece', 'Every piece is one of a kind, so we do not hold items, online or in the shop. First come, first served.'),
   ('Buying online', 'Pieces on this site can be bought by credit card through Square. Online checkout ships within Japan; for overseas shipping, please contact us before buying.'),
  ],
  'faq': [
   ('Where is Kobanzame?', f'At {ADDR["en"]}, in an 80-year-old wooden house.'),
   ('When is it closed?', ('Every Monday (open on public holidays). Open 13:00–20:00 Tuesday to Sunday, until 22:00 in July–August.' if NEWHOURS else 'Every Monday and Tuesday. Open 12:00–20:00 on other days.' + (' From 1 November 2026: Tuesday–Sunday 13:00–20:00, closed Mondays.' if NOTICE else ''))),
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

# ---------- お知らせ一覧（/news/・/en/news/）----------
# お知らせが0件でもページは作る（古いページが残って期限切れの文が出続けないように、毎回上書きする）
for lang in ('ja', 'en'):
    P = pre(lang)
    if lang == 'ja':
        nt, nd = 'お知らせ｜古着屋 小判鮫 KOBANZAME', '古着屋 小判鮫（川越・元町）からのお知らせです。臨時休業・営業時間の変更・イベントなどをお知らせします。'
        empty, note = '今お知らせはありません。', ''
    else:
        nt, nd = 'News | Kobanzame', 'News from Kobanzame, a vintage clothing shop in Kawagoe (posted in Japanese).'
        empty, note = 'There is no news at the moment.', '<p class="noen">News is posted in Japanese. Opening hours in English are on the <a href="/en/#store">top page</a>.</p>'
    body = (f'<ul class="newslist" lang="ja">\n{news_items_html(NEWS)}\n  </ul>' if NEWS else f'<p class="newsnone">{empty}</p>')
    write(P + '/news/index.html', head(lang, nt, nd, P + '/news/') + f'''
<main class="wrap news">
  <div class="crumb"><a href="{P}/">HOME</a><span>／</span><span>NEWS</span></div>
  <div class="sec-head"><h1 id="news-h">News<small>{'お知らせ' if lang == 'ja' else 'Shop news'}</small></h1></div>
  {note}
  {body}
</main>
''' + foot(lang))

# ---------- ブログ ----------
from build_blog import build_blog
blog_urls = build_blog()

# ---------- robots.txt / sitemap.xml / llms.txt ----------
pages = []
for lang in ('ja', 'en'):
    P = pre(lang)
    pages += [P + '/', P + '/journal/'] + [P + f"/journal/{p['slug']}/" for p in live]
pages += ['/tokushoho/', '/privacy/', '/en/legal/', '/guide/', '/en/guide/'] + (['/workshop/', '/en/workshop/'] if WS_OPEN else [])
pages += ['/news/', '/en/news/']
pages += blog_urls   # ブログのページ
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
write(f'/{INDEXNOW_KEY}.txt', INDEXNOW_KEY)
write('/sitemap.xml', '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
      ''.join(f'  <url><loc>{BASE}{u}</loc><lastmod>{TODAY}</lastmod></url>\n' for u in pages) + '</urlset>\n')
from build_blog import load_posts as _lp
blog_llms = '\n'.join(f"- [{b['title']}]({BASE}/blog/{b['slug']}/): {b.get('description', '')}" for b in _lp() if not b.get('_draft'))
items = '\n'.join(f"- [{p['title']}]({BASE}/journal/{p['slug']}/): {p['product_name']}。{money(site_price(p), 'ja')}（税込・送料込み）。{'販売終了' if is_sold(p) else '在庫1点'}"
                  for p in live)
write('/llms.txt', f'''# 古着屋 小判鮫（KOBANZAME）

> 埼玉県川越市元町1-14-5の、築約80年の古民家で営業している古着屋。国内外で買い付けたヴィンテージ古着と、小判鮫オリジナルのリメイクアクセサリー「GAW」を扱う。商品はすべて一点もの。運営は{SHOP['company']}。英語ページは {BASE}/en/ 。

## 基本情報
- 店名: 古着屋 小判鮫（こばんざめ / KOBANZAME）。英名は Remora（Remora Vintage Clothing Kawagoe）
- 所在地: {ADDR['ja']}（地図: {SHOP['gmaps']}）
- 営業時間: {'13:00〜20:00（7〜8月は22:00まで）・月曜定休（祝日は営業）・臨時休業はInstagramでお知らせ' if NEWHOURS else '12:00〜20:00・月曜・火曜定休' + ('。2026年11月1日から火〜日 13:00〜20:00・月曜定休' if NOTICE else '')}
- 新着: 毎週水曜
- 取扱い: ヴィンテージ古着（メンズ・レディース）、ヨーロッパ・アメリカの古着、オリジナルのリメイクアクセサリー「GAW」
- 買い方: 店頭／このサイト（クレジットカード・Square決済・送料込み）／メルカリShops
- 取り置き: なし（一点ものなので、サイト・店頭とも先着順）
- 発送: 決済確認後3日以内（{'月曜の定休日を除く' if NEWHOURS else '月曜・火曜の定休日を除く'}）
- 古物商許可: {SHOP['kobutsu']}
- お問い合わせ: {SHOP['email']}
- Instagram: {SHOP['instagram']}

{('## お知らせ（' + TODAY + ' 時点）' + chr(10) + chr(10).join('- ' + n['date'] + ': ' + news_plain(n['text']) + ('（' + n['until'] + 'まで）' if n['until'] else '') for n in NEWS) + chr(10) + chr(10)) if NEWS else ''}## ページ
- [トップ・よくある質問]({BASE}/)
- [お知らせ]({BASE}/news/)
- [ジャーナル]({BASE}/journal/)
- [川越で古着屋を探している方へ（案内）]({BASE}/guide/)
- [ブログ]({BASE}/blog/)
{'- [ワークショップ（真鍮バングル・天然石ビーズブレスレット・' + ('10/24開催' if WS_BOOKING else '予約は準備中') + '）](' + BASE + '/workshop/)' + chr(10) if WS_OPEN else ''}- [English]({BASE}/en/)
- [特定商取引法に基づく表記]({BASE}/tokushoho/)
- [プライバシーポリシー]({BASE}/privacy/)

## よくある質問
{chr(10).join('- ' + q + ' — ' + a for q, a in FAQ['ja'])}

## ブログ（商品の紹介・読みもの）
{blog_llms}

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
    imgs = [abs_url(u) for u in real_images(p)[:11]]
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

# ---------- 文章の点検（2026-10-09 龍さん決定：語尾は「です・ます」で言い切る） ----------
# 止めはしない（サイトは作る）。言い切っていない文があれば、作り直しのログに一覧を出す。
_END_OK = re.compile(r'(です|ます|ました|ません|でした|ましょう|ください)[。！]?$')
_vague = []
for _p in products:
    if release(_p) != 'live':
        continue
    for _k in ('summary_text', 'lead', 'body_html'):
        _v = _p.get(_k) or ''
        _chunks = re.findall(r'<p>(.*?)</p>', _v, re.S) if _k == 'body_html' else [_v]
        for _c in _chunks:
            for _s in re.split(r'(?<=。)', _c):
                _s = _s.strip()
                if _s and not _END_OK.search(re.sub(r'（[^（]*）(?=。?$)', '', re.sub(r'」+(?=。?$)', '', _s))):
                    _vague.append(f"{_p['sku']} {_k}: {_s}")
if _vague:
    print(f'⚠ 言い切っていない文が {len(_vague)} 件あります（直すと良い）:')
    for _l in _vague[:30]:
        print('  ', _l)
