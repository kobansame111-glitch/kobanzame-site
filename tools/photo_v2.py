"""新しい商品写真の「見た目を揃える」処理 photo_v2（2026-10-09 v1.0・オンライン課A6）

決定（龍さん）
  2026-10-08 ①A：着用イメージはサイズを決めた全身マネキン（男物 身長175cm・胸囲90cm／女物 身長165cm・バスト83cm）。
               実寸（spec「サイズ」）からマネキンのどこまで来るかを計算してAIに伝え、画像の下に「○○のマネキン着用イメージ
               （AI作成／サイズ感は実寸からの推定）」と入れる。
             ②B：本物の写真は背景だけ同じオフホワイトに差し替える。服の画素は元の写真のまま（描き直さない）。
               寄りで撮った写真でも、服が同じ大きさ・同じ余白で真ん中に来るように置き直す。
  2026-10-09 A：背景を揃えた本物の写真は自動でサイトに入れる。マネキン画像は「確認待ち」にし、OKが出たら2枚目に入れる。
             過去の商品は今のまま。PHOTO_V2_FROM 以降に公開された商品だけ。
             画像のAI代は1回ごとに台帳（data/ai_cost/photo_v2.csv）に記録し、上限を超えたら止める。

いつ動くか：GitHub Actions build-site の中（products.json が変わった時）。対象が0件ならすぐ終わる（AIも呼ばない）。
変えるもの：products.json の対象商品の images／thumb と、新しい欄 photo_v2・images_orig。画像は assets/products/<sku>/v2_*.jpg。
やらないこと：元の写真の削除・上書き／過去の商品／マネキン画像の自動公開。
止める：data/ai_cost/STOP というファイルがあれば、AIを一切呼ばない（上限超えの時はこのファイルを自動で作る。再開は中身を確認してから人が消す）。
鍵：GEMINI_API_KEY（GitHub Secrets・値はログに出さない）。無ければ何もしない。
失敗：その商品は元の写真のまま。HTTP ステータスと本文の先頭をログに出す（握り潰さない）。
"""
import base64, csv, datetime, io, json, os, re, sys, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data', 'products.json')
COST_DIR = os.path.join(ROOT, 'data', 'ai_cost')
COST_CSV = os.path.join(COST_DIR, 'photo_v2.csv')
STOP_FILE = os.path.join(COST_DIR, 'STOP')
SITE = 'https://kobanzame-site.pages.dev'
JST = datetime.timezone(datetime.timedelta(hours=9))

PHOTO_V2_FROM = os.environ.get('PHOTO_V2_FROM', '2026-10-09')   # この日以降に公開された商品だけ
MAX_PER_RUN = int(os.environ.get('PHOTO_V2_MAX', '5'))           # 1回に処理する商品の上限（時間・費用の暴走防止）
TEXT_MODEL = 'gemini-2.5-flash'
IMAGE_MODEL = 'gemini-2.5-flash-image'

# ---- お金のルール（円・推定）。料金が変わったらここを直す ----
USD_JPY = 150.0                       # 為替（推定・固定）
PRICE = {                             # 100万トークンあたりのドル（Google公表の料金。2026-10 時点の値を手で入れたもの）
    TEXT_MODEL: {'in': 0.30, 'out': 2.50},
    IMAGE_MODEL: {'in': 0.30, 'out': 30.0},   # 画像1枚の出力＝約1,290トークン＝約0.039ドル＝約6円
}
STOP_PER_IMAGE_YEN = 15.0             # 画像1枚を作るのにこれを超えたら止める（ふだんは約6円）
MONTH_CAP_YEN = 1000.0                # この処理の1か月の上限（Googleの上限1,500円の内側。21番・ジャンル判定の分を残す）

BG = (243, 241, 236)                  # サイト共通の背景色（オフホワイト）
CANVAS = (1200, 1500)                 # 4:5
FIT_H, FIT_W = 0.80, 0.78             # 本物の写真：服が占める高さ・幅の上限
MANNEQUIN_H = 0.86                    # マネキン：頭から足までをキャンバスの高さの86%に固定（＝商品どうしで縮尺が揃う）
FONT = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'

BODY = {  # マネキンの寸法（床からの高さ cm）
    'men': dict(label='身長175cm・胸囲90cm', height=175, chest=90, shoulder=42, hps=144, waist=106, crotch=82, knee=48),
    'women': dict(label='身長165cm・バスト83cm', height=165, chest=83, shoulder=38, hps=135, waist=102, crotch=76, knee=45),
}
CLOTHES = ('outer', 'tops', 'bottoms', 'dress')   # マネキンに着せるジャンル（靴・アクセ・小物は着せない）

LOG_LINES = []


def log(m):
    print(m, flush=True)
    LOG_LINES.append(str(m))


def now_jst():
    return datetime.datetime.now(JST)


# ===== お金の台帳 ===================================================================

class Budget:
    HEADER = ['日時', '品番', '処理', 'モデル', '入力トークン', '出力トークン', '概算円', '作った画像']

    def __init__(self):
        os.makedirs(COST_DIR, exist_ok=True)
        if not os.path.exists(COST_CSV):
            with open(COST_CSV, 'w', newline='', encoding='utf-8') as f:
                csv.writer(f).writerow(self.HEADER)
        self.month = now_jst().strftime('%Y-%m')
        self.spent = 0.0
        with open(COST_CSV, encoding='utf-8') as f:
            for r in csv.DictReader(f):
                if r['日時'].startswith(self.month):
                    self.spent += float(r['概算円'] or 0)

    @staticmethod
    def yen(model, usage):
        p = PRICE.get(model, PRICE[IMAGE_MODEL])   # 知らないモデルは高い方で数える
        i = usage.get('promptTokenCount', 0) or 0
        o = (usage.get('candidatesTokenCount', 0) or 0) + (usage.get('thoughtsTokenCount', 0) or 0)
        return i, o, (i * p['in'] + o * p['out']) / 1e6 * USD_JPY

    def record(self, sku, kind, model, res, images=0):
        i, o, y = self.yen(model, (res or {}).get('usageMetadata') or {})
        self.spent += y
        with open(COST_CSV, 'a', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow([now_jst().strftime('%Y-%m-%d %H:%M'), sku, kind, model, i, o, f'{y:.2f}', images])
        return y

    def can_spend(self, est):
        return self.spent + est <= MONTH_CAP_YEN

    @staticmethod
    def stop(reason):
        os.makedirs(COST_DIR, exist_ok=True)
        with open(STOP_FILE, 'w', encoding='utf-8') as f:
            f.write(f'{now_jst():%Y-%m-%d %H:%M} 停止：{reason}\n確認して問題なければ、このファイルを消すと再開します。\n')
        log(f'⛔ 停止：{reason}（data/ai_cost/STOP を作りました）')


# ===== Gemini =====================================================================

def gemini(model, parts, gen):
    body = {'contents': [{'parts': parts}], 'generationConfig': gen}
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method='POST',
                                 headers={'Content-Type': 'application/json', 'x-goog-api-key': os.environ['GEMINI_API_KEY']})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'Gemini HTTP {e.code}：{e.read().decode(errors="replace")[:400]}')


def img_part(im, q=88):
    b = io.BytesIO(); im.convert('RGB').save(b, 'JPEG', quality=q)
    return {'inline_data': {'mime_type': 'image/jpeg', 'data': base64.b64encode(b.getvalue()).decode()}}


def text_of(res):
    c = (res.get('candidates') or [{}])[0]
    return ''.join(p.get('text', '') for p in (c.get('content') or {}).get('parts', []))


def json_of(res):
    raw = re.sub(r'^```(?:json)?|```$', '', text_of(res).strip(), flags=re.M).strip()
    return json.loads(raw)


def pick_full_shots(images, sku, budget):
    """写真の中から「服の全体が写った正面・背面」を選ぶ"""
    parts = []
    for i, im in enumerate(images[:16]):
        small = im.copy(); small.thumbnail((512, 512))
        parts += [{'text': f'写真{i}番'}, img_part(small, 80)]
    parts.append({'text': '古着の商品写真です。服の「全体」が写っている正面の写真と背面の写真を1枚ずつ選んでください。'
                          '寄りの細部・タグ・ダメージのアップは選ばない。無ければ -1。'
                          'JSONだけ：{"front":番号,"back":番号}'})
    res = gemini(TEXT_MODEL, parts, {'temperature': 0, 'responseMimeType': 'application/json', 'maxOutputTokens': 100,
                                     'thinkingConfig': {'thinkingBudget': 0}})
    budget.record(sku, '写真選び', TEXT_MODEL, res)
    j = json_of(res)
    return int(j.get('front', -1)), int(j.get('back', -1))


def garment_box(im, sku, budget):
    """Gemini に「売り物の服だけ」を囲む箱を出してもらう（輪郭マスクは返事が壊れやすいので使わない・2026-10-08 試験）"""
    import numpy as np
    small = im.copy(); small.thumbnail((1024, 1024))
    prompt = ('Detect the single garment for sale in this photo (the clothing item only). '
              'The box must cover the whole garment from its top edge (shoulders/collar/waistband) to its hem and both sides, '
              'but exclude hangers, hooks, wall decorations, horns, shelves and mannequin stands as much as possible. '
              'Answer JSON only: {"box_2d":[y0,x0,y1,x1]} normalized to 0-1000.')
    res = gemini(TEXT_MODEL, [img_part(small), {'text': prompt}],
                 {'temperature': 0, 'responseMimeType': 'application/json', 'maxOutputTokens': 200,
                  'thinkingConfig': {'thinkingBudget': 0}})
    budget.record(sku, '服の箱', TEXT_MODEL, res)
    j = json_of(res)
    if isinstance(j, list):
        j = j[0]
    y0, x0, y1, x1 = [v / 1000 for v in j['box_2d']]
    W, H = im.size
    pad = 0.015
    box = np.zeros((H, W), dtype=bool)
    box[max(0, int((y0 - pad) * H)):min(H, int((y1 + pad) * H)), max(0, int((x0 - pad) * W)):min(W, int((x1 + pad) * W))] = True
    return box


# ===== 切り抜き（服の画素は元のまま。透明度だけを決める） =====================

_S = {}


def _session(name):
    from rembg import new_session
    if name not in _S:
        _S[name] = new_session(name)
    return _S[name]


def edge_alpha(im):
    import numpy as np
    from rembg import remove
    return np.array(remove(im, session=_session('isnet-general-use')).split()[-1]).astype(float) / 255


def cloth_mask(im):
    """服だけを見分けるモデル（ハンガー・壁の飾りは服と見なさない）。上下・全身の3枚を重ねる"""
    import numpy as np
    from PIL import ImageChops
    from rembg import remove
    m = remove(im, session=_session('u2net_cloth_seg'), only_mask=True).convert('L')
    h = im.height
    parts = [m.crop((0, k * h, m.width, (k + 1) * h)) for k in range(max(1, m.height // h))]
    out = parts[0]
    for p in parts[1:]:
        out = ImageChops.lighter(out, p)
    return np.array(out.resize(im.size)) > 100


def cutout(im, sku, budget):
    """箱（Gemini）∩ 服の形（cloth_seg）× 輪郭（isnet）＝ 服だけの透明度"""
    import numpy as np
    from PIL import Image, ImageFilter
    from scipy import ndimage as ndi
    box = garment_box(im, sku, budget)
    reg = ndi.binary_closing(cloth_mask(im) & box, iterations=6)
    if reg.sum() < 0.03 * box.sum():          # 服の形が取れない時は箱だけで（ハンガーが少し残ることがある）
        reg = box
    reg = ndi.binary_fill_holes(reg)
    lab, k = ndi.label(reg)
    if k == 0:
        raise RuntimeError('服の範囲が空です')
    reg = lab == (np.argmax(ndi.sum(reg, lab, range(1, k + 1))) + 1)
    reg = ndi.binary_dilation(ndi.binary_fill_holes(reg), iterations=4)
    soft = np.array(Image.fromarray((reg * 255).astype('uint8')).filter(ImageFilter.GaussianBlur(2))) / 255
    a = np.clip(edge_alpha(im) * soft, 0, 1)
    if a.sum() < 0.05 * a.size:
        raise RuntimeError('切り抜いた服が小さすぎます（失敗の可能性）')
    rgba = im.convert('RGBA'); rgba.putalpha(Image.fromarray((a * 255).astype('uint8')))
    return rgba


def place(rgba, fit_h, fit_w, shadow=True):
    """切り抜いた物を、同じ大きさ・同じ余白でキャンバスの真ん中に置く"""
    from PIL import Image, ImageFilter
    obj = rgba.crop(rgba.getbbox())
    s = min(CANVAS[1] * fit_h / obj.height, CANVAS[0] * fit_w / obj.width)
    obj = obj.resize((max(1, int(obj.width * s)), max(1, int(obj.height * s))), Image.LANCZOS)
    canvas = Image.new('RGBA', CANVAS, BG + (255,))
    x, y = (CANVAS[0] - obj.width) // 2, (CANVAS[1] - obj.height) // 2
    if shadow:
        sh = Image.new('RGBA', obj.size, (60, 50, 40, 0)); sh.putalpha(obj.split()[-1].point(lambda v: int(v * 0.16)))
        canvas.alpha_composite(sh.filter(ImageFilter.GaussianBlur(14)), (x + 10, y + 16))
    canvas.alpha_composite(obj, (x, y))
    return canvas.convert('RGB')


# ===== マネキン着用イメージ ==========================================================

def parse_measures(p):
    size = ''
    for row in p.get('spec', []):
        if len(row) >= 2 and row[0] == 'サイズ':
            size = row[1]
    # 書き方がいろいろ（「身幅50cm・着丈57cm」「肩幅37／身幅49.5／着丈125cm」「平置き：ウエスト36／総丈78cm」）なので、cm は無くてもよい
    return {k: float(v) for k, v in re.findall(r'(肩幅|身幅|着丈|袖丈|裄丈|ウエスト|股下|総丈|ヒップ|わたり|裾幅|すそ幅)\s*[:：]?\s*([\d]+(?:\.\d+)?)', size)}


def body_for(p):
    return BODY['women'] if p.get('genre') == 'dress' or 'レディース' in p.get('category', '') else BODY['men']


def fit_text(p, b, m):
    """実寸 → 「マネキンのどこまで来るか」の文章（AIへの指示）"""
    lines = [f'Mannequin size: height {b["height"]} cm, chest circumference {b["chest"]} cm, shoulder width {b["shoulder"]} cm. '
             f'Landmarks measured from the floor: shoulder/neck point {b["hps"]} cm, waist {b["waist"]} cm, crotch {b["crotch"]} cm, knee {b["knee"]} cm.']
    g = p.get('genre')
    length = m.get('着丈') or m.get('総丈')
    if g in ('outer', 'tops', 'dress') and length:
        hem = b['hps'] - length
        where = ('above the waist' if hem > b['waist'] else 'between waist and crotch' if hem > b['crotch']
                 else 'between crotch and knee' if hem > b['knee'] else 'below the knee')
        lines.append(f'The garment length is {length:.0f} cm, so its hem must end about {hem:.0f} cm above the floor ({where}).')
    if '身幅' in m:
        ease = m['身幅'] * 2 - b['chest']
        fit = 'tight' if ease < 4 else 'regular' if ease < 14 else 'loose' if ease < 26 else 'very oversized'
        lines.append(f'Chest width laid flat is {m["身幅"]:.0f} cm (circumference about {m["身幅"]*2:.0f} cm vs mannequin {b["chest"]} cm): a {fit} fit.')
    if '肩幅' in m:
        d = m['肩幅'] - b['shoulder']
        lines.append(f'Shoulder width is {m["肩幅"]:.0f} cm vs mannequin {b["shoulder"]} cm: shoulder seams sit '
                     + ('inside the mannequin shoulder line.' if d < -2 else 'on the shoulder line.' if d <= 3 else 'dropped below the shoulder.'))
    if '袖丈' in m:
        lines.append(f'Sleeve length is {m["袖丈"]:.0f} cm from the shoulder seam.')
    if g == 'bottoms' and '総丈' in m and '股下' not in m:
        lines.append(f'Total length is {m["総丈"]:.0f} cm from the waistband, so the hem ends about {b["waist"]-m["総丈"]:.0f} cm above the floor.')
    if g == 'bottoms' and '股下' in m:
        lines.append(f'Inseam is {m["股下"]:.0f} cm, so the hem ends about {b["crotch"]-m["股下"]:.0f} cm above the floor.')
    return ' '.join(lines)


def mannequin_image(p, front, b, m, budget):
    from PIL import Image
    prompt = ('This photo shows a vintage garment for sale. Create a new product photo of EXACTLY this same garment worn by '
              'a plain matte white full-body mannequin without facial features, standing straight, front view. '
              'Show the whole mannequin from head to feet. Keep the garment identical: same color, pattern, print, logos, tags, '
              'buttons (same number), stitching, fabric texture, fading, wear and proportions. Do not add, remove or redesign '
              'anything on it. Do not add other clothes except plain white simple trousers if the item is a top, no accessories, '
              'no people, no text. Plain flat off-white background (#F3F1EC), soft even studio light. ' + fit_text(p, b, m))
    res = gemini(IMAGE_MODEL, [img_part(front), {'text': prompt}], {'responseModalities': ['IMAGE', 'TEXT']})
    y = budget.record(p['sku'], 'マネキン画像', IMAGE_MODEL, res, images=1)
    if y > STOP_PER_IMAGE_YEN:
        Budget.stop(f'{p["sku"]} のマネキン画像1枚が {y:.1f}円（上限 {STOP_PER_IMAGE_YEN:.0f}円）')
    for part in ((res.get('candidates') or [{}])[0].get('content') or {}).get('parts', []):
        d = part.get('inlineData') or part.get('inline_data')
        if d and d.get('data'):
            return Image.open(io.BytesIO(base64.b64decode(d['data']))).convert('RGB')
    raise RuntimeError('マネキン画像が返ってきません')


def caption(im, text):
    from PIL import Image, ImageDraw, ImageFont
    W, H = im.size
    bar = 92
    out = Image.new('RGB', (W, H), BG)
    out.paste(im.crop((0, 0, W, H - bar)), (0, 0))
    d = ImageDraw.Draw(out)
    f = ImageFont.truetype(FONT, 30)
    d.text(((W - d.textlength(text, font=f)) / 2, H - bar + 28), text, fill=(90, 90, 90), font=f)
    return out


# ===== 対象の判定（純粋関数・テスト対象） ===========================================

def is_target(p, start=None):
    start = start or PHOTO_V2_FROM
    return (p.get('status') == 'available' and p.get('published') is not False and not p.get('noindex')
            and str(p.get('published_date', '')) >= start and not p.get('photo_v2') and bool(p.get('images')))


def new_image_list(images, front_i, back_i, front_url, back_url, mannequin_url=None):
    """並び：1 正面（背景を揃えた）／2 マネキン（OKの時だけ）／3 背面（背景を揃えた）／4〜 残りの本物の写真（元のまま）"""
    rest = [u for k, u in enumerate(images) if k not in (front_i, back_i)]
    head = [front_url] if front_url else ([images[front_i]] if front_i >= 0 else [])
    if mannequin_url:
        head.append(mannequin_url)
    if back_url:
        head.append(back_url)
    elif back_i >= 0:
        head.append(images[back_i])
    return head + rest


def apply_approvals(products):
    """photo_v2.mannequin が "ok" になった商品は、マネキン画像を2枚目に入れる（人の確認が済んだもの）"""
    n = 0
    for p in products:
        v = p.get('photo_v2') or {}
        if v.get('mannequin') == 'ok' and v.get('mannequin_url') and v['mannequin_url'] not in p['images']:
            p['images'] = p['images'][:1] + [v['mannequin_url']] + p['images'][1:]
            n += 1
    return n


# ===== 本体 =========================================================================

def load_image(u):
    from PIL import Image
    if u.startswith('/'):
        path = os.path.join(ROOT, u.lstrip('/'))
        if os.path.exists(path):
            return Image.open(path).convert('RGB')
        u = SITE + u
    req = urllib.request.Request(u, headers={'User-Agent': 'kobanzame-site-bot'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return Image.open(io.BytesIO(r.read())).convert('RGB')


def process(p, budget):
    sku = p['sku']
    rel = f'/assets/products/{sku.lower()}'
    od = os.path.join(ROOT, rel.lstrip('/')); os.makedirs(od, exist_ok=True)
    images = [load_image(u) for u in p['images'][:16]]
    front_i, back_i = pick_full_shots(images, sku, budget)
    log(f'{sku}: 全体の写真 正面={front_i} 背面={back_i}（0から数える）')
    urls = {}
    for key, idx in (('front', front_i), ('back', back_i)):
        if idx < 0:
            continue
        try:
            import traceback
            place(cutout(images[idx], sku, budget), FIT_H, FIT_W).save(os.path.join(od, f'v2_{key}.jpg'), quality=88, optimize=True)
            urls[key] = f'{rel}/v2_{key}.jpg'
            log(f'{sku} {key}: 背景を揃えました')
        except Exception as e:
            urls[key + '_error'] = repr(e)[:300]
            log(f'{sku} {key}: 失敗 → 元の写真のまま：{e!r}')
    v = {'date': now_jst().strftime('%Y-%m-%d'), 'front_i': front_i, 'back_i': back_i,
         **{(k if k.endswith('_error') else k + '_url'): u for k, u in urls.items()}}
    # マネキン（服のジャンルだけ・確認待ちで作る）
    if p.get('genre') in CLOTHES and front_i >= 0 and not os.path.exists(STOP_FILE) and os.environ.get('PHOTO_V2_NO_MANNEQUIN') != '1':
        if not budget.can_spend(STOP_PER_IMAGE_YEN):
            log(f'{sku}: 今月のマネキン代が上限（{MONTH_CAP_YEN:.0f}円）に近いので作りません（使用 {budget.spent:.0f}円）')
            v['mannequin'] = 'skipped-budget'
        else:
            b, m = body_for(p), parse_measures(p)
            try:
                raw = mannequin_image(p, images[front_i], b, m, budget)
                from PIL import Image
                rgba = raw.convert('RGBA'); rgba.putalpha(Image.fromarray((edge_alpha(raw) * 255).astype('uint8')))
                caption(place(rgba, MANNEQUIN_H, 0.9, shadow=False),
                        f'{b["label"]}のマネキン着用イメージ（AI作成／サイズ感は実寸からの推定）').save(
                    os.path.join(od, 'v2_mannequin.jpg'), quality=88, optimize=True)
                v.update({'mannequin': 'pending', 'mannequin_url': f'{rel}/v2_mannequin.jpg', 'mannequin_body': b['label'],
                          'measures': m})
                log(f'{sku}: マネキン画像を作りました（確認待ち）実寸 {m}')
            except Exception as e:
                v['mannequin'] = 'error'
                log(f'{sku}: マネキン画像 失敗：{e!r}')
    p['images_orig'] = list(p['images'])
    p['images'] = new_image_list(p['images'], front_i, back_i, urls.get('front'), urls.get('back'))   # *_error は並びに使わない
    if urls.get('front'):
        p['thumb'] = urls['front']
    p['photo_v2'] = v


def targets(products):
    only = [x.strip() for x in os.environ.get('PHOTO_V2_ONLY', '').split(',') if x.strip()]   # 試験用：品番を絞る
    return [p for p in products if is_target(p) and (not only or p['sku'] in only)]


def main():
    products = json.load(open(DATA, encoding='utf-8'))
    if '--check' in sys.argv:          # 対象の件数だけ出す（ワークフローが重い道具を入れるか決める）
        n = len(targets(products)) if os.environ.get('GEMINI_API_KEY') and not os.path.exists(STOP_FILE) else 0
        print(n)
        out = os.environ.get('GITHUB_OUTPUT')
        if out:
            open(out, 'a').write(f'count={n}\n')
        return 0
    changed = apply_approvals(products)
    if changed:
        log(f'マネキン画像のOKを {changed}件 反映しました')
    if os.path.exists(STOP_FILE):
        log('⛔ data/ai_cost/STOP があるので、AIは呼びません：' + open(STOP_FILE, encoding='utf-8').read().strip())
    elif not os.environ.get('GEMINI_API_KEY'):
        log('GEMINI_API_KEY が無いので何もしません')
    else:
        budget = Budget()
        for p in targets(products)[:MAX_PER_RUN]:
            if os.path.exists(STOP_FILE):
                break
            try:
                process(p, budget)
                changed += 1
            except Exception as e:
                log(f'{p["sku"]}: エラー（元の写真のまま。次回また試す）：{e!r}')
        log(f'今月のこの処理のAI代（概算）：{budget.spent:.1f}円／上限 {MONTH_CAP_YEN:.0f}円')
    if changed and LOG_LINES:
        os.makedirs(COST_DIR, exist_ok=True)
        with open(os.path.join(COST_DIR, 'photo_v2_last_run.txt'), 'w', encoding='utf-8') as f:   # 直近の実行の記録（何をして何が失敗したか）
            f.write(now_jst().strftime('%Y-%m-%d %H:%M') + '\n' + '\n'.join(LOG_LINES) + '\n')
    if changed:
        with open(DATA, 'w', encoding='utf-8') as f:
            f.write(json.dumps(products, ensure_ascii=False, indent=1) + '\n')
    return 0   # 止まった時の知らせは、ワークフローの最後の段（STOP があれば失敗＝GitHubからメール）で出す


if __name__ == '__main__':
    sys.exit(main())
