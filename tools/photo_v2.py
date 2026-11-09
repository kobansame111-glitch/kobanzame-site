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
止める：data/ai_cost/STOP というファイルがあれば、AIを一切呼ばない。次の2つの時に自動で作る（作られるとワークフローの最後の段が
      失敗になり、GitHubから龍さんにメールが届く）：①マネキン画像1枚が STOP_PER_IMAGE_YEN を超えた ②この月の合計が MONTH_CAP_YEN に届いた。
      再開は、中身を確認してから data/ai_cost/STOP を消す。
鍵：GEMINI_API_KEY（GitHub Secrets・値はログに出さない）。無ければ何もしない。
失敗：その商品は元の写真のまま。HTTP ステータスと本文の先頭をログに出す（握り潰さない）。

2026-11-09 龍さん「なるべくお金をかけずに」（v1.1）
  ①マネキン画像の型を gemini-2.5-flash-image（2027-03-15 に終わる予定）から Nano Banana 2 Lite
    （gemini-3.1-flash-lite-image・画像の型で一番安い・1K だけ）に替える。
  ②マネキン画像は Batch（まとめて頼むと半額）で頼む。その回の実行では頼むだけ（mannequin=queued→batch）、
    結果は次の回の実行で受け取って確認待ち（pending）にする。水曜の公開に間に合わない品は、今と同じくマネキンなしで出る
    （マネキンは確認で OK が出た品だけ2枚目に入るため）。
  ③見本：data/ai_cost/SAMPLE_REQUEST に品番（1行に1つ・3つまで）を書いて置くと、その回は見本だけを作る
    （新旧の型で2枚ずつ・data/ai_cost/samples/YYYYMMDD/。商品データ・サイトは変えない）。作り終えたらファイルを消す。
"""
import base64, csv, datetime, io, json, os, re, sys, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data', 'products.json')
COST_DIR = os.path.join(ROOT, 'data', 'ai_cost')
COST_CSV = os.path.join(COST_DIR, 'photo_v2.csv')
STOP_FILE = os.path.join(COST_DIR, 'STOP')
SAMPLE_FILE = os.path.join(COST_DIR, 'SAMPLE_REQUEST')   # 見本を作る頼み（品番を1行に1つ）
SAMPLE_DIR = os.path.join(COST_DIR, 'samples')
SITE = 'https://kobanzame-kawagoe.com'
JST = datetime.timezone(datetime.timedelta(hours=9))

PHOTO_V2_FROM = os.environ.get('PHOTO_V2_FROM', '2026-10-09')   # この日以降に公開された商品だけ
MAX_PER_RUN = int(os.environ.get('PHOTO_V2_MAX', '5'))           # 1回に処理する商品の上限（時間・費用の暴走防止）
TEXT_MODEL = 'gemini-2.5-flash'
IMAGE_MODEL = 'gemini-3.1-flash-lite-image'   # 2026-11-09 Nano Banana 2 Lite（画像の型で一番安い・1K だけ）
OLD_IMAGE_MODEL = 'gemini-2.5-flash-image'    # 2027-03-15 に終わる予定の型。見本の比べ用と、昔の台帳の行の料金用に残す

# ---- お金のルール（円・推定）。料金が変わったらここを直す ----
USD_JPY = 150.0                       # 為替（推定・固定）
PRICE = {                             # 100万トークンあたりのドル（Google公表の料金。2026-11-09 に公式の料金ページで確かめた値）
    TEXT_MODEL: {'in': 0.30, 'out': 2.50, 'text_out': 2.50},
    OLD_IMAGE_MODEL: {'in': 0.30, 'out': 30.0, 'text_out': 2.50},   # 画像1枚の出力＝約1,290トークン＝0.039ドル＝約5.8円
    IMAGE_MODEL: {'in': 0.25, 'out': 30.0, 'text_out': 1.50},       # 1K の画像1枚＝1,120トークン＝0.0336ドル＝約5.0円。文字と考えた分は 1.50
}
IMAGE_OUT_TOKENS = {OLD_IMAGE_MODEL: 1290, IMAGE_MODEL: 1120}   # 画像1枚の出力トークン（見込みの計算用）
BATCH_RATE = 0.5                      # Batch（まとめて頼む）は入力も出力も半額（公式の料金ページの Batch の表）
STOP_PER_IMAGE_YEN = 15.0             # 画像1枚を作るのにこれを超えたら止める（ふだんは約2.5円・見本だけ約5〜6円）
MONTH_CAP_YEN = 1000.0                # この処理の1か月の上限（Googleの上限1,500円の内側。21番・ジャンル判定の分を残す）

BG = (243, 241, 236)                  # サイト共通の背景色（オフホワイト）
BG_LIGHT_ITEM = (226, 222, 214)       # 2026-10-22 龍さんA：白・生成りの服は、この少し濃いグレージュの背景にする（服のふちが溶けないように）
WHITE_ITEM_L = 185                    # 服の明るさ（0〜255・中央値）がこれ以上なら「白い服」とみなす（10/22 実測：白Tシャツ K10153 が197〜199・ストライプ K10990 が166 → 185）
MAX_BRIGHTEN = 5.0                    # 背景が透けて服が明るくなった量（平均・0〜255）がこれ以上なら白飛びとみなし、元の写真のまま使う
CANVAS = (1200, 1500)                 # 4:5
FIT_H, FIT_W = 0.64, 0.62             # 本物の写真：服が占める高さ・幅の上限（2026-10-14 龍さん決定A：寄りすぎなので 0.80/0.78 から下げて余白を広く）
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

    def __init__(self, products=None):
        os.makedirs(COST_DIR, exist_ok=True)
        if not os.path.exists(COST_CSV):
            with open(COST_CSV, 'w', newline='', encoding='utf-8') as f:
                csv.writer(f).writerow(self.HEADER)
        self.month = now_jst().strftime('%Y-%m')
        self.spent = 0.0
        # まとめて頼んで、まだ受け取っていない分（料金は受け取った時に台帳へ）は、上限の計算では使ったものとして数える
        self.reserved = image_yen_estimate(IMAGE_MODEL, batch=True) * len(waiting_products(products or []))
        with open(COST_CSV, encoding='utf-8') as f:
            for r in csv.DictReader(f):
                if str(r.get('日時', '')).startswith(self.month):
                    try:
                        self.spent += float(r.get('概算円') or 0)
                    except ValueError:
                        log(f'台帳の読めない行を飛ばしました：{r}')

    @staticmethod
    def yen(model, usage, batch=False):
        p = PRICE.get(model, PRICE[OLD_IMAGE_MODEL])   # 知らないモデルは高い方で数える
        i = usage.get('promptTokenCount', 0) or 0
        cand = usage.get('candidatesTokenCount', 0) or 0
        think = usage.get('thoughtsTokenCount', 0) or 0
        o = cand + think
        # 2026-11-09：出力の内訳（画像／文字）が返ってくる時は、画像の分だけ画像の料金、文字と考えた分は文字の料金で数える
        # （1回目の見本で、新しい型の考えた分を画像の料金で数えて1枚 約6.6〜7.0円と高く出たため）。内訳が無い時は今まで通り高い方で
        img = sum((d.get('tokenCount') or 0) for d in (usage.get('candidatesTokensDetails') or []) if d.get('modality') == 'IMAGE')
        cost = (i * p['in'] + img * p['out'] + (o - img) * p['text_out']) if img else (i * p['in'] + o * p['out'])
        return i, o, cost / 1e6 * USD_JPY * (BATCH_RATE if batch else 1.0)

    def record(self, sku, kind, model, res, images=0, batch=False):
        i, o, y = self.yen(model, (res or {}).get('usageMetadata') or {}, batch)
        self.spent += y
        with open(COST_CSV, 'a', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow([now_jst().strftime('%Y-%m-%d %H:%M'), sku, kind, model, i, o, f'{y:.2f}', images])
        return y

    def can_spend(self, est):
        return self.spent + self.reserved + est <= MONTH_CAP_YEN

    @staticmethod
    def stop(reason):
        os.makedirs(COST_DIR, exist_ok=True)
        with open(STOP_FILE, 'w', encoding='utf-8') as f:
            f.write(f'{now_jst():%Y-%m-%d %H:%M} 停止：{reason}\n確認して問題なければ、このファイルを消すと再開します。\n')
        log(f'⛔ 停止：{reason}（data/ai_cost/STOP を作りました）')


# ===== Gemini =====================================================================

def gemini_logged(budget, sku, kind, model, parts, gen, images=0):
    """Gemini を呼び、成功も失敗も台帳に1行残す（時間切れは料金が分からないので、画像なら1枚分を見込みで数える）"""
    try:
        res = gemini(model, parts, gen)
    except Exception as e:
        est = 0.0 if model == TEXT_MODEL else image_yen_estimate(model)
        budget.spent += est
        with open(COST_CSV, 'a', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow([now_jst().strftime('%Y-%m-%d %H:%M'), sku, kind + '（失敗・料金不明）', model, '', '', f'{est:.2f}', 0])
        raise
    y = budget.record(sku, kind, model, res, images)
    if kind.startswith('見本'):   # 見本の時は、料金の内訳（トークン）もログに残す（PR に実測を書くため）
        log(f'  {sku} {kind} 使ったトークン：{json.dumps(res.get("usageMetadata") or {}, ensure_ascii=False)[:400]}')
    return res, y


def image_yen_estimate(model, batch=False):
    """画像1枚の見込みの円（入力は写真1枚＋指示で約600トークン・2026-11-08 の実測 614 から）"""
    return Budget.yen(model, {'promptTokenCount': 600, 'candidatesTokenCount': IMAGE_OUT_TOKENS.get(model, 1290)}, batch)[2]


API = 'https://generativelanguage.googleapis.com/v1beta'


def gemini_http(path, body=None, timeout=180):
    """Gemini の REST を呼ぶ（body が無ければ GET）。HTTP の失敗は本文の先頭つきで RuntimeError にする"""
    req = urllib.request.Request(f'{API}/{path}', data=json.dumps(body).encode() if body is not None else None,
                                 method='POST' if body is not None else 'GET',
                                 headers={'Content-Type': 'application/json', 'x-goog-api-key': os.environ['GEMINI_API_KEY']})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'Gemini HTTP {e.code}：{e.read().decode(errors="replace")[:400]}')


def gemini(model, parts, gen):
    return gemini_http(f'models/{model}:generateContent', {'contents': [{'parts': parts}], 'generationConfig': gen})


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
    res, _ = gemini_logged(budget, sku, '写真選び', TEXT_MODEL, parts,
                           {'temperature': 0, 'responseMimeType': 'application/json', 'maxOutputTokens': 100,
                            'thinkingConfig': {'thinkingBudget': 0}})
    try:
        j = json_of(res)
        if isinstance(j, list):
            j = j[0] if j else {}
        return check_picks(j.get('front', -1), j.get('back', -1), len(images[:16]))
    except Exception as e:
        raise RuntimeError(f'写真選びの返事が読めない：{text_of(res)[:200]}') from e


def check_picks(front, back, n):
    """AIが選んだ番号が写真の枚数の範囲内か確かめる。正面と背面が同じなら背面は無し（純粋関数・テスト対象）"""
    def ok(v):
        try:
            v = int(v)
        except (TypeError, ValueError):
            return -1
        return v if 0 <= v < n else -1
    f, b = ok(front), ok(back)
    if b == f:
        b = -1
    return f, b


def find_box(j):
    """返事のどこかにある [y0,x0,y1,x1]（0〜1000の数4つ）を探す（純粋関数・テスト対象）"""
    if isinstance(j, dict):
        for k in ('box_2d', 'box', 'bbox', 'bounding_box'):
            if k in j:
                r = find_box(j[k])
                if r:
                    return r
        for v in j.values():
            r = find_box(v)
            if r:
                return r
    elif isinstance(j, list):
        if len(j) == 4 and all(isinstance(v, (int, float)) for v in j):
            y0, x0, y1, x1 = j
            if 0 <= y0 < y1 <= 1000 and 0 <= x0 < x1 <= 1000:
                return [float(v) for v in j]
            return None
        for v in j:
            r = find_box(v)
            if r:
                return r
    return None


def garment_box(im, sku, budget, pad=0.015):
    """Gemini に「売り物の服だけ」を囲む箱を出してもらう（輪郭マスクは返事が壊れやすいので使わない・2026-10-08 試験）"""
    import numpy as np
    small = im.copy(); small.thumbnail((1024, 1024))
    prompt = ('Detect the single garment for sale in this photo (the clothing item only). '
              'The box must cover the whole garment from its top edge (shoulders/collar/waistband) to its hem and both sides, '
              'but exclude hangers, hooks, wall decorations, horns, shelves and mannequin stands as much as possible. '
              'Answer JSON only: {"box_2d":[y0,x0,y1,x1]} normalized to 0-1000.')
    box4 = None
    for attempt in range(2):   # 返事の形が崩れることがある（2026-10-09：box_2d 以外の名前で返ってきた）ので1回だけやり直す
        res, _ = gemini_logged(budget, sku, '服の箱', TEXT_MODEL, [img_part(small), {'text': prompt}],
                               {'temperature': 0, 'responseMimeType': 'application/json', 'maxOutputTokens': 200,
                                'thinkingConfig': {'thinkingBudget': 0}})
        try:
            box4 = find_box(json_of(res))
        except Exception:
            box4 = None
        if box4:
            break
        log(f'  服の箱の返事が読めない（{attempt + 1}回目）：{text_of(res)[:120]}')
    if not box4:
        raise RuntimeError('服の箱が返ってきません')
    y0, x0, y1, x1 = [v / 1000 for v in box4]
    W, H = im.size
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


def cutout(im, sku, budget, pad=0.015):
    """箱（Gemini）∩ 服の形（cloth_seg）× 輪郭（isnet）＝ 服だけの透明度"""
    import numpy as np
    from PIL import Image, ImageFilter
    from scipy import ndimage as ndi
    box = garment_box(im, sku, budget, pad)
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
    # 2026-10-21 龍さん「白くなりすぎ」：輪郭のモデルが服の内側を半透明と判定すると、背景のオフホワイトが透けて服が白っぽくなる。
    # 服の内側（輪郭から12画素以上内側）は透明度をなくす（元の写真の色のまま）。
    core = ndi.binary_erosion(reg, iterations=12)
    # 2026-10-21 22:1x：服と背景が同じような灰色だと、内側に完全な透明（穴）が残った（K11314）。内側は全部不透明にする
    a = np.where(core, 1.0, a)
    if a.sum() < 0.05 * a.size:
        raise RuntimeError('切り抜いた服が小さすぎます（失敗の可能性）')
    rgba = im.convert('RGBA'); rgba.putalpha(Image.fromarray((a * 255).astype('uint8')))
    return rgba


def tone_check(rgba):
    """2026-10-22 龍さんA：AIを使わない数字の検査（無料・毎回同じ答え）。
    ①服の内側で、背景が透けて元の写真より明るくなった量（平均）＝ brighten
    ②服の明るさ（中央値）＝ garment_l（白い服かどうか）
    服の画素は元の写真のまま使うので、明るさが変わるのは「透けた分」だけ。だからこの差＝白飛びの量になる"""
    import numpy as np
    from scipy import ndimage as ndi
    arr = np.asarray(rgba).astype(float)
    a = arr[..., 3] / 255
    lum = arr[..., 0] * 0.299 + arr[..., 1] * 0.587 + arr[..., 2] * 0.114
    region = ndi.binary_fill_holes(a > 0.05)            # 服の範囲（半透明の所も含む）
    inner = ndi.binary_erosion(region, iterations=6)    # ふち（もともと半透明でよい所）を除いた内側
    if inner.sum() < 1000:
        inner = region
    bg_l = BG[0] * 0.299 + BG[1] * 0.587 + BG[2] * 0.114
    brighten = float(np.mean((1 - a[inner]) * np.clip(bg_l - lum[inner], 0, None))) if inner.any() else 0.0
    garment_l = float(np.median(lum[inner])) if inner.any() else 0.0
    return round(brighten, 1), round(garment_l, 1)


def make_v2(im, sku, budget, rejected_path=None):
    """切り抜き → 数字の検査 → 置く → AIの仕上がり確認。だめなら RuntimeError（元の写真のまま使う）。
    2026-10-22：「裾・袖が切れる」で不合格なら、服の箱を広げて（余白1.5%→6%）1回だけやり直す。
    不合格の画像は rejected_path に残す（サイトには使わない・あとで目で確かめる用）
    戻り値：(画像, 検査の記録)"""
    try:
        return _make_v2(im, sku, budget, 0.015, rejected_path)
    except RuntimeError as e:
        if '切' not in str(e) and '欠' not in str(e):
            raise
        log(f'  {sku}: 「{e}」→ 服の箱を広げてもう1回')
        out, info = _make_v2(im, sku, budget, 0.06, rejected_path)
        info['pad'] = 0.06
        return out, info


def _make_v2(im, sku, budget, pad, rejected_path):
    rgba = cutout(im, sku, budget, pad)
    brighten, garment_l = tone_check(rgba)
    info = {'brighten': brighten, 'garment_l': garment_l}
    if brighten >= MAX_BRIGHTEN:
        raise RuntimeError(f'数字の検査で不合格：背景が透けて明るくなった量 {brighten}（{MAX_BRIGHTEN}以上）＝白飛び')
    white = garment_l >= WHITE_ITEM_L
    info['bg'] = 'light_item' if white else 'normal'
    out = place(rgba, FIT_H, FIT_W, bg=BG_LIGHT_ITEM if white else None)
    ok, why = quality_ok(out, sku, budget)
    if not ok:
        if rejected_path:
            try:
                out.save(rejected_path, quality=80, optimize=True)
            except Exception as e2:
                log(f'  不合格の画像を残せない：{e2!r}')
        raise RuntimeError(f'仕上がり確認で不合格：{why}')
    return out, info


def quality_ok(img, sku, budget):
    """できた画像をAIに見せて、服以外の物（壁の飾り・角・棚・切れ端）が残っていないか、服が欠けていないかを確かめる。
    ダメなら元の写真のまま使う（本物の写真は確認なしで自動公開するので、その安全装置）。ハンガーは残っていてよい"""
    small = img.copy(); small.thumbnail((768, 768))
    prompt = ('This is an automatically cut-out product photo of a garment on a plain off-white background. '
              'Check two things: (1) Is any leftover object other than the garment visible, such as wall decorations, horns, '
              'plaques, shelves, wall pieces, floor, or blotches of the old background? A clothes hanger is acceptable. '
              '(2) Is any part of the garment visibly cut off or missing (holes, chopped hem or sleeve)? '
              'Answer JSON only: {"clean": true or false, "problem": "short reason in Japanese or empty"}')
    res, _ = gemini_logged(budget, sku, '仕上がり確認', TEXT_MODEL, [img_part(small), {'text': prompt}],
                           {'temperature': 0, 'responseMimeType': 'application/json', 'maxOutputTokens': 120,
                            'thinkingConfig': {'thinkingBudget': 0}})
    try:
        j = json_of(res)
    except Exception:
        return False, f'確認の返事が読めない：{text_of(res)[:80]}'
    if isinstance(j, list):
        j = j[0] if j else {}
    return bool(j.get('clean')), str(j.get('problem', ''))[:100]


def place(rgba, fit_h, fit_w, shadow=True, bg=None):
    """切り抜いた物を、同じ大きさ・同じ余白でキャンバスの真ん中に置く"""
    from PIL import Image, ImageFilter
    obj = rgba.crop(rgba.getbbox())
    s = min(CANVAS[1] * fit_h / obj.height, CANVAS[0] * fit_w / obj.width)
    obj = obj.resize((max(1, int(obj.width * s)), max(1, int(obj.height * s))), Image.LANCZOS)
    canvas = Image.new('RGBA', CANVAS, (bg or BG) + (255,))
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


def mannequin_prompt(p, b, m):
    return ('This photo shows a vintage garment for sale. Create a new product photo of EXACTLY this same garment worn by '
              'a plain matte white full-body mannequin without facial features, standing straight, front view. '
              'Show the whole mannequin from head to feet. Keep the garment identical: same color, pattern, print, logos, tags, '
              'buttons (same number), stitching, fabric texture, fading, wear and proportions. Do not add, remove or redesign '
              'anything on it. Do not add other clothes except plain white simple trousers if the item is a top, no accessories, '
              'no people, no text. Plain flat off-white background (#F3F1EC), soft even studio light. '
              # 2026-10-14 追加：K11265 で汚れが消え・値札が描かれ・脚が短くなったため
              'Keep every stain, paint mark, scratch, crack and other damage exactly where it is on the original; never clean or repair it. '
              'Do not draw price tags, paper tags, labels hanging from the garment, or hangers. '
              'The mannequin must have realistic adult proportions: legs are about half of the total height, crotch at about 47% of the height from the floor. '
              + fit_text(p, b, m))


MANNEQUIN_GEN = {'responseModalities': ['IMAGE', 'TEXT']}   # 新しい型は 1K だけなので大きさの指定はしない（既定が 1K）


def front_part(front):
    """元の写真（長い辺を2048画素まで・まとめて頼む時の大きさの上限20MBに余裕を持たせる）"""
    small = front.copy(); small.thumbnail((2048, 2048))
    return img_part(small)


def image_from_response(res):
    """Gemini の返事から画像を1枚取り出す。無ければ理由つきで RuntimeError（純粋関数に近い・テスト対象）"""
    from PIL import Image
    for part in ((res.get('candidates') or [{}])[0].get('content') or {}).get('parts', []):
        d = part.get('inlineData') or part.get('inline_data')
        if d and d.get('data'):
            return Image.open(io.BytesIO(base64.b64decode(d['data']))).convert('RGB')
    c = (res.get('candidates') or [{}])[0]
    raise RuntimeError(f'マネキン画像が返ってきません finish={c.get("finishReason")} {json.dumps(res.get("promptFeedback", {}))[:200]} {text_of(res)[:120]}')


def mannequin_image(p, front, b, m, budget, model=IMAGE_MODEL, kind='マネキン画像'):
    """その場で1枚作る（見本づくり用。ふだんのマネキン画像は Batch で頼む）"""
    res, y = gemini_logged(budget, p['sku'], kind, model, [front_part(front), {'text': mannequin_prompt(p, b, m)}],
                           MANNEQUIN_GEN, images=1)
    if y > STOP_PER_IMAGE_YEN:
        Budget.stop(f'{p["sku"]} のマネキン画像1枚が {y:.1f}円（上限 {STOP_PER_IMAGE_YEN:.0f}円）')
    return image_from_response(res)


def finish_mannequin(raw, b):
    """AIの画像 → 背景をそろえて置き、下に「AI作成」の一文を入れる"""
    from PIL import Image
    rgba = raw.convert('RGBA'); rgba.putalpha(Image.fromarray((edge_alpha(raw) * 255).astype('uint8')))
    return caption(place(rgba, MANNEQUIN_H, 0.9, shadow=False),
                   f'{b["label"]}のマネキン着用イメージ（AI作成／サイズ感は実寸からの推定）')


# ===== マネキン画像を Batch（まとめて・半額）で頼む／受け取る（2026-11-09） ==================

BATCH_MAX = 20                         # 1回にまとめて頼む上限（1件 約0.5MB なので 20MB に余裕あり）
BATCH_WAIT_STATES = ('PENDING', 'RUNNING', 'UNSPECIFIED', '')


def waiting_products(products):
    """頼む前（queued）と、頼んで受け取る前（batch）の商品"""
    return [p for p in products if (p.get('photo_v2') or {}).get('mannequin') in ('queued', 'batch')]


def batch_state(st):
    """Batch の状態を短い言葉に（JOB_STATE_SUCCEEDED / BATCH_STATE_SUCCEEDED → SUCCEEDED）。done=false なら RUNNING（純粋関数・テスト対象）"""
    s = str((st.get('metadata') or {}).get('state') or st.get('state') or '')
    s = s.split('_STATE_')[-1] if '_STATE_' in s else s
    if not s and st.get('done') is False:
        return 'RUNNING'
    return s


def inlined_responses(st):
    """終わった Batch から、1件ずつの返事の一覧を取り出す（置き場所が2通りあるので両方見る・純粋関数・テスト対象）"""
    for holder in (st.get('response') or {}, (st.get('metadata') or {}).get('output') or {}, st.get('dest') or {}, st.get('output') or {}):
        ir = holder.get('inlinedResponses')
        if isinstance(ir, dict):
            ir = ir.get('inlinedResponses')
        if isinstance(ir, list):
            return ir
    return []


def batch_body(items, stamp):
    """items＝[(key, request)] → batchGenerateContent に送る本文（純粋関数・テスト対象）"""
    return {'batch': {'display_name': f'kobanzame-mannequin-{stamp}',
                      'input_config': {'requests': {'requests': [{'request': r, 'metadata': {'key': k}} for k, r in items]}}}}


def mark_queued(v, p, b, m):
    """マネキン画像を「頼む予定」にする（この回の最後にまとめて頼む）"""
    v.update({'mannequin': 'queued', 'mannequin_body': b['label'], 'measures': m})
    v.pop('mannequin_url', None)      # 前の画像（NG になった物など）は使わない
    v.pop('mannequin_error', None)


def submit_batch(products, budget):
    """queued の商品をまとめて1つの Batch で頼む。成功→ batch（名前と鍵を残す）、失敗→ error。頼んだ数を返す"""
    queued = [p for p in products if (p.get('photo_v2') or {}).get('mannequin') == 'queued'][:BATCH_MAX]
    if not queued:
        return 0
    stamp = now_jst().strftime('%Y%m%d-%H%M')
    items, ok = [], []
    for p in queued:
        v = p['photo_v2']
        try:
            src = p.get('images_orig') or p['images']
            fi = v.get('front_i', 0)
            front = load_image(src[fi] if isinstance(fi, int) and 0 <= fi < len(src) else src[0])
            b, m = body_for(p), parse_measures(p)
            items.append((f'{p["sku"]}-{stamp}', {'contents': [{'parts': [front_part(front), {'text': mannequin_prompt(p, b, m)}]}],
                                                   'generationConfig': MANNEQUIN_GEN}))
            ok.append(p)
        except Exception as e:
            v.update({'mannequin': 'error', 'mannequin_error': f'頼む前の準備で失敗：{e!r}'[:300]})
            log(f'{p["sku"]}: マネキン画像を頼めません：{e!r}')
    if not items:
        return 0
    try:
        res = gemini_http(f'models/{IMAGE_MODEL}:batchGenerateContent', batch_body(items, stamp), timeout=300)
        name = res.get('name') or (res.get('metadata') or {}).get('name')
        if not name:
            raise RuntimeError(f'Batch の名前が返ってきません：{json.dumps(res)[:200]}')
    except Exception as e:
        for p in ok:
            p['photo_v2'].update({'mannequin': 'error', 'mannequin_error': f'まとめて頼めませんでした：{e!r}'[:300]})
        log(f'マネキン画像をまとめて頼めませんでした（{len(ok)}件・マネキンなしのまま）：{e!r}')
        return 0
    for (key, _), p in zip(items, ok):
        p['photo_v2'].update({'mannequin': 'batch', 'mannequin_batch': name, 'mannequin_key': key,
                              'mannequin_model': IMAGE_MODEL, 'mannequin_asked': now_jst().strftime('%Y-%m-%d %H:%M')})
    log(f'マネキン画像を {len(ok)}件 まとめて頼みました（{name}・結果は次の回の実行で受け取る）')
    return len(ok)


def collect_batches(products, budget):
    """頼んであった Batch の結果を受け取る。終わった分は画像にして確認待ち（pending）へ。料金は1枚ずつ台帳へ。変えた数を返す"""
    groups = {}
    for p in products:
        v = p.get('photo_v2') or {}
        if v.get('mannequin') == 'batch' and v.get('mannequin_batch'):
            groups.setdefault(v['mannequin_batch'], []).append(p)
    changed = 0
    for name, ps in groups.items():
        try:
            st = gemini_http(name, timeout=120)
        except Exception as e:
            log(f'Batch {name} の様子が読めません（次の回にもう一度）：{e!r}')
            continue
        state = batch_state(st)
        if state in BATCH_WAIT_STATES:
            log(f'Batch {name}：まだ終わっていません（{state or "不明"}・{len(ps)}件）')
            continue
        if state != 'SUCCEEDED':
            for p in ps:
                p['photo_v2'].update({'mannequin': 'error', 'mannequin_error': f'まとめて頼んだ分が {state} で終わりました'})
            log(f'Batch {name}：{state}（{len(ps)}件はマネキンなしのまま）')
            changed += len(ps)
            continue
        by_key = {str((r.get('metadata') or {}).get('key')): r for r in inlined_responses(st)}
        for p in ps:
            v = p['photo_v2']
            r = by_key.get(str(v.get('mannequin_key')))
            changed += 1
            try:
                if not r:
                    raise RuntimeError('結果の一覧にこの品がありません')
                if r.get('error'):
                    raise RuntimeError(f'エラー：{json.dumps(r["error"], ensure_ascii=False)[:200]}')
                res = r.get('response') or {}
                y = budget.record(p['sku'], 'マネキン画像（まとめて）', v.get('mannequin_model') or IMAGE_MODEL, res, images=1, batch=True)
                budget.reserved = max(0.0, budget.reserved - image_yen_estimate(IMAGE_MODEL, batch=True))
                if y > STOP_PER_IMAGE_YEN:
                    Budget.stop(f'{p["sku"]} のマネキン画像1枚が {y:.1f}円（上限 {STOP_PER_IMAGE_YEN:.0f}円）')
                b = body_for(p)
                rel = f'/assets/products/{p["sku"].lower()}'
                od = os.path.join(ROOT, rel.lstrip('/')); os.makedirs(od, exist_ok=True)
                finish_mannequin(image_from_response(res), b).save(os.path.join(od, 'v2_mannequin.jpg'), quality=88, optimize=True)
                for k in ('mannequin_batch', 'mannequin_key', 'mannequin_error'):
                    v.pop(k, None)
                v.update({'mannequin': 'pending', 'mannequin_url': f'{rel}/v2_mannequin.jpg', 'mannequin_body': b['label'],
                          'mannequin_date': now_jst().strftime('%Y-%m-%d')})
                log(f'{p["sku"]}: マネキン画像を受け取りました（確認待ち）')
            except Exception as e:
                v.update({'mannequin': 'error', 'mannequin_error': repr(e)[:300]})
                for k in ('mannequin_batch', 'mannequin_key'):
                    v.pop(k, None)
                log(f'{p["sku"]}: マネキン画像の受け取りで失敗（マネキンなしのまま）：{e!r}')
    return changed


# ===== 見本（新旧の型で2枚ずつ・2026-11-09） ==========================================

def sample_skus(text):
    """SAMPLE_REQUEST の中身から品番を取り出す（K＋5桁・重なりなし・3つまで。純粋関数・テスト対象）"""
    out = []
    for s in re.findall(r'\bK\d{5}\b', text.upper()):
        if s not in out:
            out.append(s)
    return out[:3]


def dump_b64(path, width=8000):
    """ファイルを base64 にして、印つきの行に分けてログに出す（LOG_LINES には入れない）"""
    data = base64.b64encode(open(path, 'rb').read()).decode()
    name = os.path.basename(path)
    chunks = [data[k:k + width] for k in range(0, len(data), width)]
    for n, c in enumerate(chunks):
        print(f'SAMPLE_B64 {name} {n + 1}/{len(chunks)} {c}', flush=True)


def make_samples(products, budget):
    """見本だけを作る（商品データ・サイトの写真は変えない）。新旧の型で2枚ずつ、その場で作る（Batch を待たないので標準の料金）"""
    skus = sample_skus(open(SAMPLE_FILE, encoding='utf-8').read())
    od = os.path.join(SAMPLE_DIR, now_jst().strftime('%Y%m%d')); os.makedirs(od, exist_ok=True)
    lines = [f'マネキン画像の見本（{now_jst():%Y-%m-%d %H:%M}・旧＝{OLD_IMAGE_MODEL}／新＝{IMAGE_MODEL}）']
    for sku in skus:
        p = next((x for x in products if x.get('sku') == sku), None)
        if not p:
            lines.append(f'{sku}：商品データに無い'); continue
        v = p.get('photo_v2') or {}
        src = p.get('images_orig') or p.get('images') or []
        fi = v.get('front_i', 0)
        if not src:
            lines.append(f'{sku}：写真が無い'); continue
        front = load_image(src[fi] if isinstance(fi, int) and 0 <= fi < len(src) else src[0])
        b, m = body_for(p), parse_measures(p)
        for model, tag in ((OLD_IMAGE_MODEL, 'old'), (IMAGE_MODEL, 'new')):
            for n in (1, 2):
                if os.path.exists(STOP_FILE) or not budget.can_spend(STOP_PER_IMAGE_YEN):
                    lines.append(f'{sku} {tag}{n}：お金の上限で作らず'); continue
                before = budget.spent
                try:
                    finish_mannequin(mannequin_image(p, front, b, m, budget, model, f'見本（{"旧" if tag == "old" else "新"}の型）'), b).save(
                        os.path.join(od, f'{sku}_{tag}_{n}.jpg'), quality=88, optimize=True)
                    lines.append(f'{sku}_{tag}_{n}.jpg：{budget.spent - before:.2f}円')
                except Exception as e:
                    lines.append(f'{sku} {tag}{n}：失敗 {e!r}'[:300])
                log(lines[-1])
    with open(os.path.join(od, 'README.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    # main 以外のブランチで動かすと、最後のコミットの段が止まって画像が残らない（2026-11-09 1回目）。
    # 取り出せるように、画像をログにも文字で書き出す（公開リポジトリなのでログは誰でも見られる＝商品写真と同じ扱い）
    for name in sorted(os.listdir(od)):
        if name.endswith('.jpg'):
            dump_b64(os.path.join(od, name))
    os.remove(SAMPLE_FILE)
    log(f'見本を {od} に作りました（SAMPLE_REQUEST は消しました）')


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
    d = str(p.get('published_date', ''))
    if not re.match(r'^\d{4}-\d{2}-\d{2}', d):   # 「2026/10/01」などの形は比べられないので対象にしない
        return False
    return (p.get('status') == 'available' and p.get('published') is not False and not p.get('noindex')
            and d >= start and bool(p.get('images'))
            and (not p.get('photo_v2') or (p['photo_v2'].get('error') and p['photo_v2'].get('tries', 0) < 2)))   # 失敗は2回まで


def new_image_list(images, front_i, back_i, front_url, back_url, mannequin_url=None):
    """並び：1 正面（背景を揃えた）／2 マネキン（OKの時だけ）／3 背面（背景を揃えた）／4〜 残りの本物の写真（元のまま）"""
    rest = [u for k, u in enumerate(images) if k not in (front_i, back_i)]
    if not front_url and back_url:
        # 2026-10-22 龍さん「1枚目は背景をそろえて統一したい」：正面が失敗して背面ができた時は、背面を1枚目にし、元の正面は2枚目に
        head = [back_url] + ([mannequin_url] if mannequin_url else []) + ([images[front_i]] if front_i >= 0 else [])
        return head + rest
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
            out, info = make_v2(images[idx], sku, budget, os.path.join(od, f'v2_{key}_rejected.jpg'))
            out.save(os.path.join(od, f'v2_{key}.jpg'), quality=88, optimize=True)
            urls[key] = f'{rel}/v2_{key}.jpg'
            urls[key + '_check'] = info
            if key == 'front':   # 一覧用の小さい画像（スマホで重くならないように）
                small = out.copy(); small.thumbnail((600, 750)); small.save(os.path.join(od, 'v2_thumb.jpg'), quality=82, optimize=True)
            log(f'{sku} {key}: 背景を揃えました')
        except Exception as e:
            urls[key + '_error'] = repr(e)[:300]
            log(f'{sku} {key}: 失敗 → 元の写真のまま：{e!r}')
    v = {'date': now_jst().strftime('%Y-%m-%d'), 'front_i': front_i, 'back_i': back_i,
         **{(k if k.endswith(('_error', '_check')) else k + '_url'): u for k, u in urls.items()}}
    # マネキン（服のジャンルだけ）。2026-11-09：この回は「頼む予定」にするだけ。回の最後に Batch でまとめて頼み、次の回で受け取る
    if p.get('genre') in CLOTHES and front_i >= 0 and not os.path.exists(STOP_FILE) and os.environ.get('PHOTO_V2_NO_MANNEQUIN') != '1':
        if not budget.can_spend(image_yen_estimate(IMAGE_MODEL, batch=True)):
            v['mannequin'] = 'skipped-budget'
            Budget.stop(f'この月の写真v2のAI代が上限 {MONTH_CAP_YEN:.0f}円 に届きました（使用 {budget.spent:.0f}円）')
        else:
            b, m = body_for(p), parse_measures(p)
            mark_queued(v, p, b, m)
            budget.reserved += image_yen_estimate(IMAGE_MODEL, batch=True)
            log(f'{sku}: マネキン画像はまとめて頼みます（受け取りは次の回）実寸 {m}')
    p['images_orig'] = list(p['images'])
    p['images'] = new_image_list(p['images'], front_i, back_i, urls.get('front'), urls.get('back'))   # *_error は並びに使わない
    if urls.get('front') or urls.get('back'):
        if not urls.get('front'):   # 正面が失敗→背面で一覧の小さい画像を作る（1枚目と同じ写真にする）
            from PIL import Image
            small = Image.open(os.path.join(od, 'v2_back.jpg')); small.thumbnail((600, 750)); small.save(os.path.join(od, 'v2_thumb.jpg'), quality=82, optimize=True)
        p['thumb'] = f'{rel}/v2_thumb.jpg'
    p['photo_v2'] = v


def is_mannequin_retry(p):
    """photo_v2.mannequin が "retry" の商品は、マネキン画像だけを1回作り直す（2026-10-14 追加・人がNGにした時用）"""
    v = p.get('photo_v2') or {}
    return (p.get('status') == 'available' and v.get('mannequin') == 'retry' and v.get('mannequin_retries', 0) < 1
            and p.get('genre') in CLOTHES and bool(p.get('images_orig') or p.get('images')))


def is_cutout_redo(p):
    """photo_v2.redo_cutout が true の商品は、背景を揃えた正面・背面の写真だけを作り直す（2026-10-21 追加・切り抜きの直し用）。
    マネキン画像と、その確認の状態（pending/ok/ng）は変えない。1回だけ（終わったら redo_cutout を消す）"""
    v = p.get('photo_v2') or {}
    return (p.get('status') == 'available' and v.get('redo_cutout') is True and bool(p.get('images_orig')))


def targets(products):
    only = [x.strip() for x in os.environ.get('PHOTO_V2_ONLY', '').split(',') if x.strip()]   # 試験用：品番を絞る
    return [p for p in products if (is_target(p) or is_mannequin_retry(p) or is_cutout_redo(p)) and (not only or p['sku'] in only)]


def redo_cutout(p, budget):
    """背景を揃えた写真（正面・背面）だけを、元の写真から作り直す。並びは「正面／（OKならマネキン）／背面／残り」に組み直す"""
    v = p['photo_v2']
    v.pop('redo_cutout', None)
    sku = p['sku']
    rel = f'/assets/products/{sku.lower()}'
    od = os.path.join(ROOT, rel.lstrip('/')); os.makedirs(od, exist_ok=True)
    src = p['images_orig']
    urls = {}
    for key in ('front', 'back'):
        idx = v.get(key + '_i', -1)
        if not (isinstance(idx, int) and 0 <= idx < len(src)):
            continue
        try:
            out, info = make_v2(load_image(src[idx]), sku, budget, os.path.join(od, f'v2_{key}_rejected.jpg'))
            v[key + '_check'] = info
            out.save(os.path.join(od, f'v2_{key}.jpg'), quality=88, optimize=True)
            urls[key] = f'{rel}/v2_{key}.jpg'
            if key == 'front':
                small = out.copy(); small.thumbnail((600, 750)); small.save(os.path.join(od, 'v2_thumb.jpg'), quality=82, optimize=True)
            v.pop(key + '_error', None); v[key + '_url'] = urls[key]
            log(f'{sku} {key}: 作り直しました')
        except Exception as e:
            v.pop(key + '_url', None); v[key + '_error'] = repr(e)[:300]
            log(f'{sku} {key}: 作り直し失敗 → 元の写真のまま：{e!r}')
    mq = v.get('mannequin_url') if v.get('mannequin') == 'ok' else None
    p['images'] = new_image_list(src, v.get('front_i', -1), v.get('back_i', -1), urls.get('front'), urls.get('back'), mq)
    if not urls.get('front') and urls.get('back'):   # 正面が失敗→背面で一覧の小さい画像（1枚目と同じ写真）
        from PIL import Image
        small = Image.open(os.path.join(od, 'v2_back.jpg')); small.thumbnail((600, 750)); small.save(os.path.join(od, 'v2_thumb.jpg'), quality=82, optimize=True)
    p['thumb'] = f'{rel}/v2_thumb.jpg' if (urls.get('front') or urls.get('back')) else (f'{rel}/thumb.jpg' if os.path.exists(os.path.join(od, 'thumb.jpg')) else p.get('thumb'))
    v['redone'] = now_jst().strftime('%Y-%m-%d')


def remake_mannequin(p, budget):
    """マネキン画像だけ作り直す。背景をそろえた写真・並びは変えない。
    2026-11-09：その場では作らず「頼む予定（queued）」にし、回の最後に Batch で頼む。受け取ったら確認待ち（pending）"""
    v = p['photo_v2']
    v['mannequin_retries'] = v.get('mannequin_retries', 0) + 1
    if not budget.can_spend(image_yen_estimate(IMAGE_MODEL, batch=True)):
        Budget.stop(f'この月の写真v2のAI代が上限 {MONTH_CAP_YEN:.0f}円 に届きました（使用 {budget.spent:.0f}円）')
        return
    mark_queued(v, p, body_for(p), parse_measures(p))   # 2026-11-09：作り直しも Batch でまとめて頼む
    budget.reserved += image_yen_estimate(IMAGE_MODEL, batch=True)
    log(f'{p["sku"]}: マネキン画像の作り直しをまとめて頼みます（受け取りは次の回）')


def save_products(products):
    """一時ファイルに書いてから置き換える（書きかけで止まっても products.json が壊れない）"""
    tmp = DATA + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(json.dumps(products, ensure_ascii=False, indent=1) + '\n')
    os.replace(tmp, DATA)


def main():
    try:
        return _main()
    except Exception as e:   # 写真の処理が失敗しても、サイトの作り直し（SOLDの反映）は止めない
        import traceback
        log(f'写真v2 全体のエラー（サイトの作り直しは続ける）：{e!r}')
        log(traceback.format_exc()[-1500:])
        return 0


def _main():
    products = json.load(open(DATA, encoding='utf-8'))
    if '--check' in sys.argv:          # 対象の件数だけ出す（ワークフローが重い道具を入れるか決める）
        # 2026-11-09：まとめて頼んで受け取る前の品（画像にする時に切り抜きの道具が要る）と、見本の頼みも数える
        n = (len(targets(products)) + len(waiting_products(products)) + (1 if os.path.exists(SAMPLE_FILE) else 0)
             if os.environ.get('GEMINI_API_KEY') and not os.path.exists(STOP_FILE) else 0)
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
    elif os.path.exists(SAMPLE_FILE):
        # 見本の頼みがある回は、見本だけを作る（商品データ・サイトの写真は変えない）
        budget = Budget(products)
        make_samples(products, budget)
        log(f'今月のこの処理のAI代（概算）：{budget.spent:.1f}円／上限 {MONTH_CAP_YEN:.0f}円')
        changed = changed or 1
    else:
        budget = Budget(products)
        got = collect_batches(products, budget)   # 前の回にまとめて頼んだマネキン画像を受け取る
        if got:
            changed += got
            save_products(products)
        for p in targets(products)[:MAX_PER_RUN]:
            if os.path.exists(STOP_FILE):
                break
            before = json.dumps(p, ensure_ascii=False, sort_keys=True)
            try:
                if is_cutout_redo(p):
                    redo_cutout(p, budget)
                elif is_mannequin_retry(p):
                    remake_mannequin(p, budget)
                else:
                    process(p, budget)
                changed += 1
                save_products(products)   # 1商品ごとに保存
            except Exception as e:
                p.clear(); p.update(json.loads(before))   # 途中まで書き換えた商品は元に戻す
                tries = (p.get('photo_v2') or {}).get('tries', 0) + 1
                p['photo_v2'] = {'error': repr(e)[:300], 'tries': tries, 'date': now_jst().strftime('%Y-%m-%d')}
                save_products(products)
                changed += 1
                log(f'{p["sku"]}: エラー（元の写真のまま。{"次回もう一度試す" if tries < 2 else "2回失敗したのでやめる"}）：{e!r}')
        if not os.path.exists(STOP_FILE) and submit_batch(products, budget):   # この回の分をまとめて頼む（半額）
            changed += 1
            save_products(products)
        log(f'今月のこの処理のAI代（概算）：{budget.spent:.1f}円・受け取り待ちの見込み {budget.reserved:.1f}円／上限 {MONTH_CAP_YEN:.0f}円')
    if changed and LOG_LINES:
        os.makedirs(COST_DIR, exist_ok=True)
        with open(os.path.join(COST_DIR, 'photo_v2_last_run.txt'), 'w', encoding='utf-8') as f:   # 直近の実行の記録（何をして何が失敗したか）
            f.write(now_jst().strftime('%Y-%m-%d %H:%M') + '\n' + '\n'.join(LOG_LINES) + '\n')
    if changed:
        save_products(products)
    return 0   # 止まった時の知らせは、ワークフローの最後の段（STOP があれば失敗＝GitHubからメール）で出す


if __name__ == '__main__':
    sys.exit(main())
