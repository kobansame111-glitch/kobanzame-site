"""火曜の「明日、公式サイトに新着」告知画像（2026-10-12 v1.0・デザイン課／19 レイアウト担当）

決定（龍さん 2026-10-12）：毎週火曜に、水曜夜（20時台）に公開される商品の告知画像を作り、メールで送る（①A）。デザインは見本のまま（②A）。
規定：Project「嶋崎龍3」 claude/claude_デザイン課_レイアウト規定_v1_2026-10-12.md の「型1」

いつ動くか：GitHub Actions announce（毎週火曜 21:05 JST ごろ。手動でも可）
対象：data/products.json で published が true・release が "draft"・status が "available"（＝水曜夜（20時台）に61番が公開する予定）
作るもの：assets/announce/<公開日>.jpg と assets/announce/latest.jpg、data/announce.json（日付・点数・品番・画像の場所）
       対象が0点なら画像は作らず、data/announce.json に count:0 だけ書く（メール側が「今週の新着はありません」と送る）
使わないもの：AIのマネキン画像（実物の写真だけ）。在庫0・SOLD の商品
メールは送らない（送るのはサイト自動化GASの68番。このファイルは画像を作るだけ）
"""
import datetime, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data', 'products.json')
OUT_DIR = os.path.join(ROOT, 'assets', 'announce')
META = os.path.join(ROOT, 'data', 'announce.json')
JST = datetime.timezone(datetime.timedelta(hours=9))
ADD_TAX = True     # build_site.py の ADD_TAX と同じ（Square価格は税抜 → ×1.1 を10円単位に切り上げて税込）

W, H = 1080, 1350
BG, INK, KIN, USU, RULE = (244, 240, 232), (18, 10, 7), (124, 68, 18), (104, 104, 104), (200, 192, 178)
MARGIN, GAP = 72, 18
FONT_DIRS = ['/usr/share/fonts/opentype/noto', '/usr/share/fonts/truetype/noto']
SERIF = ['NotoSerifCJK-Bold.ttc', 'NotoSerifCJK-Black.ttc', 'NotoSerifCJK-Regular.ttc', 'NotoSansCJK-Bold.ttc']
SANS = ['NotoSansCJK-Medium.ttc', 'NotoSansCJK-Regular.ttc', 'NotoSansCJK-DemiLight.ttc']
WEEK = '月火水木金土日'


def font(cands, size):
    from PIL import ImageFont
    for d in FONT_DIRS:
        for c in cands:
            p = os.path.join(d, c)
            if os.path.exists(p):
                return ImageFont.truetype(p, size, index=0)   # .ttc の0番＝日本語（JP）
    raise RuntimeError('日本語フォントが見つかりません（fonts-noto-cjk を入れてください）')


def tax_price(p):
    base = int((p.get('prices') or {}).get('site') or 0)
    return (-(-base * 11 // 100)) * 10 if ADD_TAX else base


def targets(products):
    """水曜に公開される予定の商品（純粋関数・テスト対象）"""
    return [p for p in products
            if p.get('published') is True and p.get('release') == 'draft' and p.get('status') == 'available'
            and tax_price(p) > 0 and (p.get('images') or p.get('thumb'))]


def photo_path(p):
    """実物の写真（背景をそろえた正面 → サムネ → 1枚目）。マネキン画像は使わない"""
    v = p.get('photo_v2') or {}
    for u in [v.get('front_url'), p.get('thumb')] + list(p.get('images') or []):
        if not u or not str(u).startswith('/') or 'mannequin' in str(u):
            continue
        path = os.path.join(ROOT, str(u).lstrip('/'))
        if os.path.exists(path):
            return path
    return None


def short(text, n):
    t = str(text or '').strip()
    return t if len(t) <= n else t[:n - 1] + '…'


def grid(n):
    """点数 → 列数（1点＝1列／2〜4点＝2列／5点以上＝3列）"""
    return 1 if n == 1 else 2 if n <= 4 else 3


def draw(items, total, date_label, out):
    from PIL import Image, ImageDraw, ImageOps
    im = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(im)
    d.text((MARGIN, 70), '小判鮫', font=font(SERIF, 54), fill=INK)
    d.text((MARGIN + 170, 92), 'KOBANZAME', font=font(SANS, 24), fill=KIN)
    d.text((MARGIN, 170), '明日、公式サイトに新着', font=font(SERIF, 64), fill=INK)
    d.text((MARGIN, 262), date_label, font=font(SANS, 34), fill=KIN)
    shown = items[:9]
    cols = grid(len(shown))
    rows = (len(shown) + cols - 1) // cols
    top, bottom = 340, H - 190
    cw = (W - 2 * MARGIN - GAP * (cols - 1)) // cols
    ch = min((bottom - top - GAP * (rows - 1)) // rows, int(cw * 1.25))
    fs = 22 if cols == 3 else 25 if cols == 2 else 30
    cap_h = 52 if cols == 1 else 70
    maxc = 10 if cols == 3 else 15 if cols == 2 else 30
    f = font(SANS, fs)
    for i, it in enumerate(shown):
        r, c = divmod(i, cols)
        x, y = MARGIN + c * (cw + GAP), top + r * (ch + GAP)
        ph = ImageOps.fit(Image.open(it['path']).convert('RGB'), (cw, ch - cap_h), centering=(0.5, 0.45))
        im.paste(ph, (x, y))
        ty = y + ph.height + 6
        d.text((x, ty), short(it['name'], maxc), font=f, fill=INK)
        pt = f"¥{it['price']:,}（税込）"
        if cols == 1:
            d.text((x + cw - d.textlength(pt, font=f), ty), pt, font=f, fill=KIN)
        else:
            d.text((x, ty + fs + 6), pt, font=f, fill=KIN)
    d.line((MARGIN, H - 160, W - MARGIN, H - 160), fill=RULE, width=2)
    more = f'　ほか {total - len(shown)} 点' if total > len(shown) else ''
    d.text((MARGIN, H - 140), f'全 {total} 点・すべて一点ものです{more}', font=font(SANS, 30), fill=INK)
    d.text((MARGIN, H - 92), 'kobanzame-kawagoe.com ／ 川越の古民家の古着屋', font=font(SANS, 26), fill=USU)
    im.save(out, quality=90, optimize=True)


def main():
    now = datetime.datetime.now(JST)
    pub = (now + datetime.timedelta(days=1)).date()        # 火曜に動いて「明日（水曜）」の告知を作る
    if os.environ.get('ANNOUNCE_DATE'):                    # 試験用：公開日を指定
        pub = datetime.date.fromisoformat(os.environ['ANNOUNCE_DATE'])
    label = f'{pub.month}/{pub.day}（{WEEK[pub.weekday()]}）20時台 公開'
    products = json.load(open(DATA, encoding='utf-8'))
    items, skipped = [], []
    for p in targets(products):
        path = photo_path(p)
        if not path:
            skipped.append(p.get('sku'))
            continue
        items.append({'sku': p.get('sku'), 'name': p.get('title') or p.get('product_name') or p.get('sku'),
                      'price': tax_price(p), 'path': path, 'slug': p.get('slug')})
    meta = {'publish_date': pub.isoformat(), 'made_at': now.strftime('%Y-%m-%d %H:%M'), 'count': len(items),
            'skus': [i['sku'] for i in items], 'skipped_no_photo': skipped, 'image': ''}
    if items:
        os.makedirs(OUT_DIR, exist_ok=True)
        dated = os.path.join(OUT_DIR, f'{pub.isoformat()}.jpg')
        draw(items, len(items), label, dated)
        draw(items, len(items), label, os.path.join(OUT_DIR, 'latest.jpg'))
        meta['image'] = f'/assets/announce/{pub.isoformat()}.jpg'
    with open(META, 'w', encoding='utf-8') as fp:
        fp.write(json.dumps(meta, ensure_ascii=False, indent=1) + '\n')
    print(json.dumps(meta, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
