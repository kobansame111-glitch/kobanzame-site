"""商品の1枚目の写真からジャンルを判定して data/products.json の genre 欄に書く（2026-10-08）

いつ動くか：GitHub Actions（build-site）で、サイトを作り直す直前に毎回動く。
何をするか：genre 欄が空の商品だけ、1枚目の写真を Gemini に見せてジャンルを1つ選ばせる。
  - 自信（0〜1）が 0.7 以上 → genre に書く（genre_by="ai-photo"）。サイトはこのジャンルを使う
  - 0.7 未満 → genre は書かず genre_review=true と候補を残す。サイトはカテゴリの文字で分ける（今までどおり）
  - すでに genre がある商品・非公開（hidden）・テスト用は触らない＝2回目以降はAPIを呼ばない
鍵：GitHub の Secrets に GEMINI_API_KEY がある時だけ動く。無ければ何もせず終了（サイトは今までどおり作られる）。
失敗：通信やAPIのエラーは HTTP ステータスと本文をログに出し、その商品だけ飛ばす（握り潰さない・サイトの作り直しは止めない）。
"""
import base64, json, os, sys, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data', 'products.json')
SITE = 'https://kobanzame-site.pages.dev'
MODEL = os.environ.get('GENRE_MODEL', 'gemini-2.5-flash')
MIN_CONF = 0.7
GENRES = {
    'outer': 'アウター（ジャケット・コート・ブルゾン・ベスト）',
    'tops': 'トップス（Tシャツ・シャツ・スウェット・ニット・パーカー）',
    'bottoms': 'パンツ・スカート',
    'dress': 'ワンピース・ドレス・オールインワン',
    'shoes': '靴（ブーツ・スニーカー・ローファー・サンダル）',
    'acc': 'アクセサリー（ネックレス・ブレスレット・指輪・ベルト・帽子・バッグ・ウォレットチェーン）',
    'other': '小物・雑貨（食器・インテリア・その他の服以外）',
}
PROMPT = ('古着屋の商品写真です。写っている「売り物」を1つ選び、次のジャンルのどれか1つに分類してください。\n'
          + '\n'.join(f'- {k}: {v}' for k, v in GENRES.items())
          + '\nマネキンやハンガー、背景の別の服は無視して、中央の主役の商品で判断してください。'
          + '\n参考情報（出品時のカテゴリと商品名。写真と食い違う時は写真を優先）：{hint}'
          + '\n答えはJSONだけ：{{"genre":"<上のキー>","confidence":<0〜1の数>,"reason":"<日本語で20字以内>"}}')


def log(msg):
    print(msg, flush=True)


def fetch_image(url):
    if url.startswith('/'):
        url = SITE + url
    req = urllib.request.Request(url, headers={'User-Agent': 'kobanzame-site-bot'})
    with urllib.request.urlopen(req, timeout=30) as r:
        ctype = r.headers.get('Content-Type', 'image/jpeg').split(';')[0]
        return r.read(), ctype


def ask_gemini(key, img, ctype, hint):
    body = {
        'contents': [{'parts': [
            {'inline_data': {'mime_type': ctype, 'data': base64.b64encode(img).decode()}},
            {'text': PROMPT.format(hint=hint)},
        ]}],
        'generationConfig': {'temperature': 0, 'responseMimeType': 'application/json'},
    }
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent'
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method='POST',
                                 headers={'Content-Type': 'application/json', 'x-goog-api-key': key})
    with urllib.request.urlopen(req, timeout=60) as r:
        res = json.loads(r.read().decode())
    text = res['candidates'][0]['content']['parts'][0]['text']
    out = json.loads(text)
    g = out.get('genre')
    if g not in GENRES:
        raise ValueError(f'想定外のジャンル: {text[:200]}')
    return g, float(out.get('confidence', 0)), str(out.get('reason', ''))[:40]


def main():
    key = os.environ.get('GEMINI_API_KEY', '').strip()
    raw = open(DATA, encoding='utf-8').read()
    products = json.loads(raw)
    todo = [p for p in products
            if not p.get('genre') and not p.get('genre_review')
            and p.get('release') != 'hidden' and p.get('category') != 'テスト' and p.get('images')]
    log(f'[genre] 判定待ち {len(todo)} 件')
    if not todo:
        return
    if not key:
        log('::warning::[genre] GEMINI_API_KEY が未設定のため写真判定をスキップ（カテゴリの文字で分けます）')
        return
    changed = 0
    for p in todo:
        sku = p.get('sku')
        try:
            img, ctype = fetch_image(p['images'][0])
            g, conf, why = ask_gemini(key, img, ctype, f"{p.get('category', '')}／{p.get('product_name', '')}")
        except urllib.error.HTTPError as e:
            log(f'::warning::[genre] {sku} HTTP {e.code} {e.read().decode(errors="replace")[:300]}')
            continue
        except Exception as e:  # 1件の失敗で全体を止めない。理由は必ずログに残す
            log(f'::warning::[genre] {sku} 失敗: {type(e).__name__}: {e}')
            continue
        if conf >= MIN_CONF:
            p['genre'], p['genre_by'], p['genre_conf'] = g, 'ai-photo', round(conf, 2)
            log(f'[genre] {sku} → {g}（自信 {conf:.2f}・{why}）')
        else:
            p['genre_review'], p['genre_guess'], p['genre_conf'] = True, g, round(conf, 2)
            log(f'::warning::[genre] {sku} 要確認：候補 {g}（自信 {conf:.2f}・{why}）→ カテゴリの文字で分けます')
        changed += 1
    if changed:
        # 既存と同じ書式（インデント1・日本語そのまま）で書き戻す＝差分を最小にする
        open(DATA, 'w', encoding='utf-8').write(json.dumps(products, ensure_ascii=False, indent=1) + '\n')
    log(f'[genre] 書き込み {changed} 件')


if __name__ == '__main__':
    main()
