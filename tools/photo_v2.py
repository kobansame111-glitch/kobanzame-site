"""新しい商品写真の「見た目を揃える」処理 v2（2026-10-08・お試し：オンライン課A6）

方針（2026-10-08 龍さん決定 ①A・②B）
  ① 着用イメージ：サイズを決めた全身マネキン（男物 身長175cm・胸囲90cm／女物 身長165cm・バスト83cm）。
     実寸（products.json の spec「サイズ」）からマネキンのどこまで来るかを計算してAIに伝える。
     画像の下に「身長○cm・胸囲○cmのマネキン着用イメージ（AI作成／サイズ感は実寸からの推定）」を入れる。
  ② 本物の写真：背景だけ同じオフホワイトに差し替える。服の部分のピクセルは元の写真のまま（描き直さない）。
     寄りで撮った写真もあるので、服の大きさが揃うように同じ余白で真ん中に置き直す。
やらないこと：products.json・サイトの変更（見本を out/photo_v2/<SKU>/ に作るだけ）。
鍵：GEMINI_API_KEY（GitHub Secrets・値はログに出さない）。
失敗：HTTP ステータスと本文の先頭をログに出し、その1枚は「元の写真のまま」にする（握り潰さない）。
"""
import base64, io, json, os, re, sys, urllib.request, urllib.error
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy import ndimage as ndi

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data', 'products.json')
OUT = os.path.join(ROOT, 'out', 'photo_v2')
TEXT_MODEL = 'gemini-2.5-flash'
IMAGE_MODEL = 'gemini-2.5-flash-image'
BG = (243, 241, 236)               # サイト共通の背景色（オフホワイト）
CANVAS = (1200, 1500)              # 4:5
FIT_H, FIT_W = 0.80, 0.78          # 本物の写真：服が占める高さ・幅の上限
MANNEQUIN_H = 0.86                 # マネキン画像：頭から足までをキャンバスの高さの86%に固定（＝商品どうしで縮尺が揃う）
FONT = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'

BODY = {  # マネキンの寸法（床からの高さ cm）。175cmの男性マネキン・165cmの女性マネキンの一般的な比率
    'men': dict(label='身長175cm・胸囲90cm', height=175, chest=90, shoulder=42, hps=144, waist=106, crotch=82, knee=48),
    'women': dict(label='身長165cm・バスト83cm', height=165, chest=83, shoulder=38, hps=135, waist=102, crotch=76, knee=45),
}


LOG_LINES = []


def log(m):
    print(m, flush=True)
    LOG_LINES.append(str(m))


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


def pick_full_shots(images):
    """写真の中から「服の全体が写った正面・背面」を選ぶ"""
    parts = []
    for i, im in enumerate(images):
        small = im.copy(); small.thumbnail((512, 512))
        parts += [{'text': f'写真{i}番'}, img_part(small, 80)]
    parts.append({'text': '古着の商品写真です。服の「全体」が写っている正面の写真と背面の写真を1枚ずつ選んでください。'
                          '寄りの細部・タグ・ダメージのアップは選ばない。無ければ -1。'
                          'JSONだけ：{"front":番号,"back":番号}'})
    res = gemini(TEXT_MODEL, parts, {'temperature': 0, 'responseMimeType': 'application/json',
                                     'thinkingConfig': {'thinkingBudget': 0}})
    j = json.loads(text_of(res))
    return int(j.get('front', -1)), int(j.get('back', -1))


def garment_region(im):
    """Gemini に「売り物の服だけ」の範囲（マスク）を出してもらう。ハンガー・壁の飾り・什器は含めない"""
    small = im.copy(); small.thumbnail((1024, 1024))
    prompt = ('Give the segmentation mask for the single garment for sale in this photo (the clothing item only). '
              'Exclude hangers, hooks, wall decorations, horns, shelves, mannequin stands and the background. '
              'Output a JSON list where each entry has "box_2d" [y0,x0,y1,x1] normalized to 0-1000, '
              '"mask" (base64 PNG of the probability map inside the box) and "label".')
    res = gemini(TEXT_MODEL, [img_part(small), {'text': prompt}],
                 {'temperature': 0, 'responseMimeType': 'application/json', 'thinkingConfig': {'thinkingBudget': 0}})
    raw = text_of(res)
    items = json.loads(re.sub(r'^```(?:json)?|```$', '', raw.strip(), flags=re.M).strip() or '[]')
    if isinstance(items, dict):
        items = items.get('masks') or items.get('items') or [items]
    if not items:
        raise RuntimeError('服の範囲が返ってきません')
    W, H = im.size
    full = np.zeros((H, W), dtype=float)
    for it in items:
        y0, x0, y1, x1 = [v / 1000 for v in it['box_2d']]
        bx0, by0, bx1, by1 = int(x0 * W), int(y0 * H), int(x1 * W), int(y1 * H)
        if bx1 - bx0 < 4 or by1 - by0 < 4:
            continue
        b64 = re.sub(r'^data:image/\w+;base64,', '', str(it.get('mask', '')))
        if not b64:
            full[by0:by1, bx0:bx1] = 1.0   # マスクが無ければ箱の中を服とみなす（輪郭は rembg が決める）
            continue
        m = Image.open(io.BytesIO(base64.b64decode(b64))).convert('L').resize((bx1 - bx0, by1 - by0), Image.BILINEAR)
        full[by0:by1, bx0:bx1] = np.maximum(full[by0:by1, bx0:bx1], np.array(m) / 255)
    return full


# ===== 切り抜き（服のピクセルは元のまま。透明度だけを決める） =====================

_SESSION = None


def edge_alpha(im):
    global _SESSION
    from rembg import remove, new_session
    if _SESSION is None:
        _SESSION = new_session('isnet-general-use')
    return np.array(remove(im, session=_SESSION).split()[-1]).astype(float) / 255


def cutout(im):
    """領域（Gemini）× 輪郭（rembg）＝ 服だけの透明度。服の画素は1つも描き換えない"""
    region = garment_region(im) > 0.5
    region = ndi.binary_closing(region, iterations=8)
    lab, k = ndi.label(region)
    if k == 0:
        raise RuntimeError('服の範囲が空です')
    region = lab == (np.argmax(ndi.sum(region, lab, range(1, k + 1))) + 1)
    region = ndi.binary_fill_holes(region)
    region = ndi.binary_dilation(region, iterations=10)
    soft = np.array(Image.fromarray((region * 255).astype('uint8')).filter(ImageFilter.GaussianBlur(3))) / 255
    a = np.clip(edge_alpha(im) * soft, 0, 1)
    rgba = im.convert('RGBA'); rgba.putalpha(Image.fromarray((a * 255).astype('uint8')))
    return rgba


def place(rgba, fit_h, fit_w, shadow=True):
    """切り抜いた物を、同じ大きさ・同じ余白でキャンバスの真ん中に置く（寄りで撮っても大きさが揃う）"""
    bbox = rgba.getbbox()
    obj = rgba.crop(bbox)
    s = min(CANVAS[1] * fit_h / obj.height, CANVAS[0] * fit_w / obj.width)
    obj = obj.resize((max(1, int(obj.width * s)), max(1, int(obj.height * s))), Image.LANCZOS)
    canvas = Image.new('RGBA', CANVAS, BG + (255,))
    x, y = (CANVAS[0] - obj.width) // 2, (CANVAS[1] - obj.height) // 2
    if shadow:   # うっすら影（浮いて見えないように）
        sh = Image.new('RGBA', obj.size, (60, 50, 40, 0)); sh.putalpha(obj.split()[-1].point(lambda v: int(v * 0.16)))
        sh = sh.filter(ImageFilter.GaussianBlur(14))
        canvas.alpha_composite(sh, (x + 10, y + 16))
    canvas.alpha_composite(obj, (x, y))
    return canvas.convert('RGB')


# ===== マネキン着用イメージ ==========================================================

def parse_measures(p):
    size = ''
    for k, v in p.get('spec', []):
        if k == 'サイズ':
            size = v
    m = {}
    for name, num in re.findall(r'(肩幅|身幅|着丈|袖丈|裄丈|ウエスト|股下|総丈|ヒップ|わたり|裾幅)\s*([\d.]+)\s*cm', size):
        m[name] = float(num)
    return m


def body_for(p):
    g = p.get('genre', '')
    c = p.get('category', '')
    return BODY['women'] if g == 'dress' or 'レディース' in c else BODY['men']


def fit_text(p, b, m):
    """実寸 → 「マネキンのどこまで来るか」の文章（AIへの指示）"""
    lines = [f'Mannequin size: height {b["height"]} cm, chest circumference {b["chest"]} cm, shoulder width {b["shoulder"]} cm. '
             f'Landmarks measured from the floor: shoulder/neck point {b["hps"]} cm, waist {b["waist"]} cm, crotch {b["crotch"]} cm, knee {b["knee"]} cm.']
    g = p.get('genre')
    if g in ('outer', 'tops', 'dress') and '着丈' in m:
        hem = b['hps'] - m['着丈']
        where = ('above the waist' if hem > b['waist'] else 'between waist and crotch' if hem > b['crotch']
                 else 'between crotch and knee' if hem > b['knee'] else 'below the knee')
        lines.append(f'The garment length is {m["着丈"]:.0f} cm, so its hem must end about {hem:.0f} cm above the floor ({where}).')
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
    if g == 'bottoms' and '股下' in m:
        lines.append(f'Inseam is {m["股下"]:.0f} cm, so the hem ends about {b["crotch"]-m["股下"]:.0f} cm above the floor.')
    return ' '.join(lines)


def mannequin_image(p, front, b, m):
    prompt = ('This photo shows a vintage garment for sale. Create a new product photo of EXACTLY this same garment worn by '
              'a plain matte white full-body mannequin without facial features, standing straight, front view. '
              'Show the whole mannequin from head to feet. Keep the garment identical: same color, pattern, print, logos, tags, '
              'buttons (same number), stitching, fabric texture, fading, wear and proportions. Do not add, remove or redesign '
              'anything on it. Do not add other clothes except plain white simple trousers if the item is a top, no accessories, '
              'no people, no text. Plain flat off-white background (#F3F1EC), soft even studio light. ' + fit_text(p, b, m))
    res = gemini(IMAGE_MODEL, [img_part(front), {'text': prompt}], {'responseModalities': ['IMAGE', 'TEXT']})
    for part in ((res.get('candidates') or [{}])[0].get('content') or {}).get('parts', []):
        d = part.get('inlineData') or part.get('inline_data')
        if d and d.get('data'):
            return Image.open(io.BytesIO(base64.b64decode(d['data']))).convert('RGB'), prompt
    raise RuntimeError('マネキン画像が返ってきません')


def caption(im, text):
    W, H = im.size
    bar = 92
    out = Image.new('RGB', (W, H), BG)
    out.paste(im.crop((0, 0, W, H - bar)), (0, 0))
    d = ImageDraw.Draw(out)
    f = ImageFont.truetype(FONT, 30)
    tw = d.textlength(text, font=f)
    d.text(((W - tw) / 2, H - bar + 28), text, fill=(90, 90, 90), font=f)
    return out


# ===== 本体 =========================================================================

def run(sku):
    items = {p['sku']: p for p in json.load(open(DATA, encoding='utf-8'))}
    p = items[sku]
    paths = [os.path.join(ROOT, u.lstrip('/')) for u in p['images']]
    images = [Image.open(x).convert('RGB') for x in paths]
    od = os.path.join(OUT, sku); os.makedirs(od, exist_ok=True)
    front, back = pick_full_shots(images)
    log(f'{sku}: 全体の写真 正面={front} 背面={back}（0から数える）')
    made = {}
    for name, idx in (('1_front', front), ('3_back', back)):
        if idx < 0:
            continue
        try:
            made[name] = place(cutout(images[idx]), FIT_H, FIT_W)
            made[name].save(os.path.join(od, f'{name}.jpg'), quality=90)
            log(f'{sku} {name}: 背景を揃えました（元 {os.path.basename(paths[idx])}）')
        except Exception as e:
            import traceback
            log(f'{sku} {name}: 失敗 → 元の写真のまま使う：{e!r}')
            log(traceback.format_exc()[-1500:])
    b, m = body_for(p), parse_measures(p)
    log(f'{sku}: 実寸 {m} ／ マネキン {b["label"]}')
    if front >= 0 and os.environ.get('SKIP_MANNEQUIN') != '1':
        try:
            raw, prompt = mannequin_image(p, images[front], b, m)
            raw.save(os.path.join(od, '2_mannequin_raw.png'))
            rgba = raw.convert('RGBA'); rgba.putalpha(Image.fromarray((edge_alpha(raw) * 255).astype('uint8')))
            placed = place(rgba, MANNEQUIN_H, 0.9, shadow=False)
            cap = caption(placed, f'{b["label"]}のマネキン着用イメージ（AI作成／サイズ感は実寸からの推定）')
            cap.save(os.path.join(od, '2_mannequin.jpg'), quality=90)
            open(os.path.join(od, 'mannequin_prompt.txt'), 'w').write(prompt)
            made['2_mannequin'] = cap
            log(f'{sku} 2_mannequin: 作りました')
        except Exception as e:
            log(f'{sku} 2_mannequin: 失敗：{e}')
    return made


def main():
    if not os.environ.get('GEMINI_API_KEY'):
        log('GEMINI_API_KEY がありません。何もしません'); return 1
    skus = os.environ.get('SAMPLE_SKUS', 'K11263').split(',')
    ok = 0
    for s in skus:
        try:
            ok += len(run(s.strip()))
        except Exception as e:
            log(f'{s}: エラー {e}')
    log(f'終了：{ok}枚')
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, 'run_log.txt'), 'w', encoding='utf-8').write('\n'.join(LOG_LINES))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
