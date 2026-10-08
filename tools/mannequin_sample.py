"""マネキン着用イメージの「見本づくり」（2026-10-08・オンライン課A6・お試し）

いつ動くか：GitHub Actions の mannequin-sample（ブランチ mannequin-sample に push した時だけ）。
何をするか：指定した商品の1枚目の写真を Gemini の画像モデルに見せ、
  型A＝首なしトルソー／型B＝全身の白いマネキン に着せた画像を作り、out/mannequin/ に保存する。
やらないこと：products.json・サイトの変更（見本を作るだけ。サイトには載せない）。
鍵：GitHub Secrets の GEMINI_API_KEY（値はログに出さない）。
失敗：HTTP ステータスと本文の先頭をログに出し、その1枚だけ飛ばす（握り潰さない）。
"""
import base64, json, os, sys, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data', 'products.json')
OUT = os.path.join(ROOT, 'out', 'mannequin')
SITE = 'https://kobanzame-site.pages.dev'
MODEL = os.environ.get('IMAGE_MODEL', 'gemini-2.5-flash-image')
SKUS = os.environ.get('SAMPLE_SKUS', 'K10888,K10743,K11190').split(',')

COMMON = ('This photo shows a vintage garment for sale. Create a new product photo of EXACTLY this same garment '
          'worn by a mannequin. Keep the garment identical: same color, pattern, print, logos, tags, buttons, '
          'stitching, fabric texture, fading, length and proportions. Do not add, remove or redesign anything on it. '
          'Do not add accessories, people, text or watermarks. Plain off-white seamless studio background, '
          'soft even lighting, front view, the whole garment visible, square 1:1 composition.')
STYLES = {
    'A_torso': COMMON + ' Mannequin: a plain matte white headless dress form (torso) on a simple wooden stand.',
    'B_full': COMMON + ' Mannequin: a plain matte white full-body mannequin without facial features, standing straight.',
}


def log(m):
    print(m, flush=True)


def fetch(url):
    if url.startswith('/'):
        url = SITE + url
    req = urllib.request.Request(url, headers={'User-Agent': 'kobanzame-site-bot'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read(), r.headers.get('Content-Type', 'image/jpeg').split(';')[0]


def generate(key, img, ctype, prompt):
    body = {'contents': [{'parts': [
        {'inline_data': {'mime_type': ctype, 'data': base64.b64encode(img).decode()}},
        {'text': prompt}]}],
        'generationConfig': {'responseModalities': ['IMAGE', 'TEXT']}}
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent'
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method='POST',
                                 headers={'Content-Type': 'application/json', 'x-goog-api-key': key})
    with urllib.request.urlopen(req, timeout=120) as r:
        res = json.loads(r.read().decode())
    cand = (res.get('candidates') or [{}])[0]
    for part in (cand.get('content') or {}).get('parts', []):
        d = part.get('inlineData') or part.get('inline_data')
        if d and d.get('data'):
            return base64.b64decode(d['data']), d.get('mimeType') or d.get('mime_type') or 'image/png', res.get('usageMetadata')
    raise RuntimeError('画像が返ってきません finish=%s %s' % (cand.get('finishReason'), json.dumps(res.get('promptFeedback', {}))[:300]))


def main():
    key = os.environ.get('GEMINI_API_KEY')
    if not key:
        log('GEMINI_API_KEY がありません。何もしません'); return 1
    os.makedirs(OUT, exist_ok=True)
    items = {p['sku']: p for p in json.load(open(DATA, encoding='utf-8'))}
    ok = ng = 0
    report = []
    for sku in SKUS:
        p = items.get(sku.strip())
        if not p or not p.get('images'):
            log(f'{sku}: 商品または写真が見つかりません'); ng += 1; continue
        src, ctype = fetch(p['images'][0])
        ext0 = 'png' if 'png' in ctype else 'jpg'
        open(os.path.join(OUT, f'{sku}_0_original.{ext0}'), 'wb').write(src)
        for name, prompt in STYLES.items():
            try:
                img, mime, usage = generate(key, src, ctype, prompt)
                ext = 'png' if 'png' in mime else 'jpg'
                fn = f'{sku}_{name}.{ext}'
                open(os.path.join(OUT, fn), 'wb').write(img)
                log(f'{sku} {name}: OK {len(img)//1024}KB usage={json.dumps(usage)}')
                report.append({'sku': sku, 'style': name, 'file': fn, 'usage': usage}); ok += 1
            except urllib.error.HTTPError as e:
                log(f'{sku} {name}: HTTP {e.code} {e.read().decode(errors="replace")[:400]}'); ng += 1
            except Exception as e:
                log(f'{sku} {name}: エラー {e}'); ng += 1
    json.dump(report, open(os.path.join(OUT, 'report.json'), 'w'), ensure_ascii=False, indent=1)
    log(f'終了：成功 {ok}枚・失敗 {ng}件（モデル {MODEL}）')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
