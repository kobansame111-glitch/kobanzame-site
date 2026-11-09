#!/usr/bin/env python3
"""tools/photo_v2.py の模擬テスト（2026-11-09・Gemini にはつながない。お金はかからない）
使い方：python3 tools/test_photo_v2.py（NG が1つでもあれば終了コード1）
見ること：新しい型と料金・Batch（まとめて頼む）の頼み方と受け取り方・見本の頼み・上限の計算・--check の数え方"""
import base64, csv, importlib.util, io, json, os, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('photo_v2', os.path.join(HERE, 'photo_v2.py'))
pv = importlib.util.module_from_spec(spec); spec.loader.exec_module(pv)

ok = ng = 0


def check(name, got, want):
    global ok, ng
    if got == want:
        ok += 1; print('  OK ' + name)
    else:
        ng += 1; print(f'  NG {name}：got {got!r} want {want!r}')


# ---- 型と料金 ----
check('新しい型＝Nano Banana 2 Lite', pv.IMAGE_MODEL, 'gemini-3.1-flash-lite-image')
check('古い型は見本・昔の台帳用に残す', pv.OLD_IMAGE_MODEL, 'gemini-2.5-flash-image')
old = round(pv.image_yen_estimate(pv.OLD_IMAGE_MODEL), 2)
new_std = round(pv.image_yen_estimate(pv.IMAGE_MODEL), 2)
new_batch = round(pv.image_yen_estimate(pv.IMAGE_MODEL, batch=True), 2)
check('直す前：古い型・その場で1枚＝約5.83円', old, 5.83)
check('新しい型・その場で1枚＝約5.06円', new_std, 5.06)
check('直した後：新しい型・まとめて1枚＝約2.53円（半額）', new_batch, 2.53)
check('台帳の実測（2026-11-08 K10562：入力614・出力1290）を古い型で計算すると 5.83円', round(pv.Budget.yen(pv.OLD_IMAGE_MODEL, {'promptTokenCount': 614, 'candidatesTokenCount': 1290})[2], 2), 5.83)
u = {'promptTokenCount': 1000, 'candidatesTokenCount': 1120, 'thoughtsTokenCount': 400,
     'candidatesTokensDetails': [{'modality': 'IMAGE', 'tokenCount': 1120}]}
check('内訳あり：画像1,120は画像の料金・考えた400は文字の料金（新しい型・その場）',
      round(pv.Budget.yen(pv.IMAGE_MODEL, u)[2], 4), round((1000 * 0.25 + 1120 * 30 + 400 * 1.5) / 1e6 * 150, 4))
check('内訳なし：今まで通り全部を画像の料金（高い方）', round(pv.Budget.yen(pv.IMAGE_MODEL, {'candidatesTokenCount': 1120, 'thoughtsTokenCount': 400})[2], 4),
      round(1520 * 30 / 1e6 * 150, 4))
check('知らない型は高い方（古い型）で数える', pv.Budget.yen('unknown', {'candidatesTokenCount': 1290})[2], pv.Budget.yen(pv.OLD_IMAGE_MODEL, {'candidatesTokenCount': 1290})[2])

# ---- 純粋関数 ----
check('状態：JOB_STATE_SUCCEEDED', pv.batch_state({'metadata': {'state': 'JOB_STATE_SUCCEEDED'}, 'done': True}), 'SUCCEEDED')
check('状態：BATCH_STATE_RUNNING（置き場所が上）', pv.batch_state({'state': 'BATCH_STATE_RUNNING'}), 'RUNNING')
check('状態：done=false だけ → RUNNING', pv.batch_state({'done': False}), 'RUNNING')
check('状態：期限切れ', pv.batch_state({'metadata': {'state': 'JOB_STATE_EXPIRED'}}), 'EXPIRED')
r1 = [{'metadata': {'key': 'a'}}]
check('返事の一覧：response.inlinedResponses.inlinedResponses', pv.inlined_responses({'response': {'inlinedResponses': {'inlinedResponses': r1}}}), r1)
check('返事の一覧：response.inlinedResponses がそのまま一覧', pv.inlined_responses({'response': {'inlinedResponses': r1}}), r1)
check('返事の一覧：dest.inlinedResponses', pv.inlined_responses({'dest': {'inlinedResponses': r1}}), r1)
check('返事の一覧：無い → 空', pv.inlined_responses({'response': {}}), [])
body = pv.batch_body([('K1-x', {'contents': []})], '20261109-1000')
check('頼む本文の形（公式の REST の例と同じ）', body, {'batch': {'display_name': 'kobanzame-mannequin-20261109-1000', 'input_config': {
    'requests': {'requests': [{'request': {'contents': []}, 'metadata': {'key': 'K1-x'}}]}}}})
check('見本の品番：K＋5桁・重なりなし・3つまで・小文字も', pv.sample_skus('k11450\nK10562 K11450\nK11452\nK11449\nx'), ['K11450', 'K10562', 'K11452'])

# ---- 流れ（作業用のフォルダで・Gemini は偽物） ----
tmp = tempfile.mkdtemp()
pv.ROOT = tmp
pv.COST_DIR = os.path.join(tmp, 'data', 'ai_cost'); os.makedirs(pv.COST_DIR)
pv.COST_CSV = os.path.join(pv.COST_DIR, 'photo_v2.csv')
pv.STOP_FILE = os.path.join(pv.COST_DIR, 'STOP')
pv.SAMPLE_FILE = os.path.join(pv.COST_DIR, 'SAMPLE_REQUEST')
pv.SAMPLE_DIR = os.path.join(pv.COST_DIR, 'samples')
pv.DATA = os.path.join(tmp, 'data', 'products.json')

from PIL import Image  # noqa: E402

png = io.BytesIO(); Image.new('RGB', (40, 60), (200, 10, 10)).save(png, 'PNG')
PNG64 = base64.b64encode(png.getvalue()).decode()
pv.load_image = lambda u: Image.new('RGB', (3000, 4000), (120, 120, 120))
pv.finish_mannequin = lambda raw, b: raw          # 切り抜きの道具（rembg）は使わない
calls = []
STATE = {'state': 'JOB_STATE_RUNNING', 'responses': []}


def fake_http(path, body=None, timeout=180):
    calls.append((path, body))
    if path.endswith(':batchGenerateContent'):
        return {'name': 'batches/abc123', 'metadata': {'state': 'JOB_STATE_PENDING'}}
    if path.endswith(':generateContent'):
        return {'candidates': [{'content': {'parts': [{'inlineData': {'mimeType': 'image/png', 'data': PNG64}}]}}],
                'usageMetadata': {'promptTokenCount': 600, 'candidatesTokenCount': pv.IMAGE_OUT_TOKENS.get(path.split('/')[1].split(':')[0], 1290)}}
    if path == 'batches/abc123':
        return {'name': path, 'done': STATE['state'] != 'JOB_STATE_RUNNING', 'metadata': {'state': STATE['state']},
                'response': {'inlinedResponses': {'inlinedResponses': STATE['responses']}}}
    raise RuntimeError('知らない呼び出し ' + path)


pv.gemini_http = fake_http


def prod(sku, mq=None, genre='outer'):
    v = {'front_i': 0, 'back_i': -1}
    if mq:
        v['mannequin'] = mq
    return {'sku': sku, 'status': 'available', 'genre': genre, 'images': ['/a.jpg'], 'images_orig': ['/a.jpg'],
            'spec': [['サイズ', '着丈70cm・身幅55cm']], 'photo_v2': v}


ps = [prod('K90001'), prod('K90002', 'retry'), prod('K90003', 'ok')]
ps[1]['photo_v2']['mannequin_url'] = '/assets/products/k90002/v2_mannequin.jpg'
budget = pv.Budget(ps)
check('上限の計算：受け取り待ちが無ければ見込み0円', budget.reserved, 0.0)
pv.mark_queued(ps[0]['photo_v2'], ps[0], pv.body_for(ps[0]), pv.parse_measures(ps[0]))
pv.remake_mannequin(ps[1], budget)
check('作り直し（retry）もその場では作らず queued・前の画像は使わない', (ps[1]['photo_v2']['mannequin'], 'mannequin_url' in ps[1]['photo_v2'], ps[1]['photo_v2']['mannequin_retries']), ('queued', False, 1))
check('--check：受け取り待ち・頼む予定も数える', len(pv.waiting_products(ps)), 2)
n = pv.submit_batch(ps, budget)
check('まとめて1回だけ頼む（2件）', (n, [c[0] for c in calls]), (2, [f'models/{pv.IMAGE_MODEL}:batchGenerateContent']))
reqs = calls[0][1]['batch']['input_config']['requests']['requests']
check('頼む中身：写真＋指示・画像で返す・品番つきの鍵', ([len(r['request']['contents'][0]['parts']) for r in reqs], reqs[0]['request']['generationConfig'],
                                       [r['metadata']['key'].split('-')[0] for r in reqs]), ([2, 2], {'responseModalities': ['IMAGE', 'TEXT']}, ['K90001', 'K90002']))
w, h = Image.open(io.BytesIO(base64.b64decode(reqs[0]['request']['contents'][0]['parts'][0]['inline_data']['data']))).size
check('送る写真は長い辺2048画素まで（20MBの上限に余裕）', max(w, h), 2048)
check('頼んだ品は batch・名前と鍵を残す', [(p['photo_v2']['mannequin'], p['photo_v2'].get('mannequin_batch')) for p in ps[:2]], [('batch', 'batches/abc123')] * 2)
check('OK 済みの品は頼まない', ps[2]['photo_v2']['mannequin'], 'ok')
check('頼んだだけでは台帳に料金は書かない（受け取った時に書く）', os.path.exists(pv.COST_CSV) and len(list(csv.reader(open(pv.COST_CSV)))), 1)

calls.clear()
check('まだ終わっていない → 何も変えない', (pv.collect_batches(ps, budget), ps[0]['photo_v2']['mannequin']), (0, 'batch'))
STATE['state'] = 'JOB_STATE_SUCCEEDED'
key0 = ps[0]['photo_v2']['mannequin_key']
STATE['responses'] = [{'metadata': {'key': key0}, 'response': {
    'candidates': [{'content': {'parts': [{'inlineData': {'mimeType': 'image/png', 'data': PNG64}}]}}],
    'usageMetadata': {'promptTokenCount': 600, 'candidatesTokenCount': 1120}}},
    {'metadata': {'key': ps[1]['photo_v2']['mannequin_key']}, 'error': {'code': 400, 'message': 'blocked'}}]
budget2 = pv.Budget(ps)
check('上限の計算：受け取り待ち2件ぶんを見込みで数える', round(budget2.reserved, 2), round(2 * new_batch, 2))
got = pv.collect_batches(ps, budget2)
v0, v1 = ps[0]['photo_v2'], ps[1]['photo_v2']
check('受け取れた品 → 確認待ち（pending）・画像の置き場所', (got, v0['mannequin'], v0['mannequin_url'], 'mannequin_batch' in v0),
      (2, 'pending', '/assets/products/k90001/v2_mannequin.jpg', False))
check('画像のファイルができた', os.path.exists(os.path.join(tmp, 'assets', 'products', 'k90001', 'v2_mannequin.jpg')), True)
check('エラーの品 → error（マネキンなしのまま）', (v1['mannequin'], 'blocked' in v1.get('mannequin_error', '')), ('error', True))
rows = list(csv.DictReader(open(pv.COST_CSV, encoding='utf-8')))
check('台帳に1行：まとめて・新しい型・半額の円・1枚', [(r['品番'], r['処理'], r['モデル'], r['概算円'], r['作った画像']) for r in rows],
      [('K90001', 'マネキン画像（まとめて）', pv.IMAGE_MODEL, f'{new_batch:.2f}', '1')])

ps3 = [prod('K90004')]
pv.mark_queued(ps3[0]['photo_v2'], ps3[0], pv.body_for(ps3[0]), {})
pv.submit_batch(ps3, pv.Budget(ps3))
STATE['state'] = 'JOB_STATE_EXPIRED'
pv.collect_batches(ps3, pv.Budget(ps3))
check('期限切れ（48時間）→ error・料金なし', (ps3[0]['photo_v2']['mannequin'], len(list(csv.reader(open(pv.COST_CSV))))), ('error', 2))

orig_http = pv.gemini_http
pv.gemini_http = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('Gemini HTTP 503'))
ps4 = [prod('K90005')]
pv.mark_queued(ps4[0]['photo_v2'], ps4[0], pv.body_for(ps4[0]), {})
check('頼むのに失敗 → 0件・error（サイトはマネキンなしのまま）', (pv.submit_batch(ps4, pv.Budget(ps4)), ps4[0]['photo_v2']['mannequin']), (0, 'error'))
pv.gemini_http = orig_http

# ---- 見本 ----
calls.clear()
open(pv.SAMPLE_FILE, 'w').write('K90001\n')
sp = [prod('K90001')]
before_json = json.dumps(sp, sort_keys=True)
pv.make_samples(sp, pv.Budget(sp))
d = os.path.join(pv.SAMPLE_DIR, sorted(os.listdir(pv.SAMPLE_DIR))[0])
check('見本：新旧2枚ずつ（4枚）と README', sorted(os.listdir(d)), ['K90001_new_1.jpg', 'K90001_new_2.jpg', 'K90001_old_1.jpg', 'K90001_old_2.jpg', 'README.txt'])
check('見本：その場で4回（古い型2・新しい型2）', [c[0] for c in calls], [f'models/{pv.OLD_IMAGE_MODEL}:generateContent'] * 2 + [f'models/{pv.IMAGE_MODEL}:generateContent'] * 2)
check('見本：商品データは変えない', json.dumps(sp, sort_keys=True), before_json)
check('見本：頼みのファイルは消す', os.path.exists(pv.SAMPLE_FILE), False)
import contextlib  # noqa: E402
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    pv.dump_b64(os.path.join(d, 'K90001_new_1.jpg'), width=100)
parts = [ln.split(' ', 3) for ln in buf.getvalue().splitlines() if ln.startswith('SAMPLE_B64 ')]
check('ログに書き出した画像を元に戻せる', base64.b64decode(''.join(p[3] for p in parts)), open(os.path.join(d, 'K90001_new_1.jpg'), 'rb').read())
srows = [r for r in csv.DictReader(open(pv.COST_CSV, encoding='utf-8')) if r['処理'].startswith('見本')]
check('見本の料金も台帳に4行（標準の料金）', [(r['モデル'], r['概算円']) for r in srows],
      [(pv.OLD_IMAGE_MODEL, f'{old:.2f}')] * 2 + [(pv.IMAGE_MODEL, f'{new_std:.2f}')] * 2)

# ---- 上限 ----
b5 = pv.Budget([])
b5.spent = pv.MONTH_CAP_YEN - 1
check('月の上限に近いと頼まない（can_spend が False）', b5.can_spend(new_batch), False)

print(f'NG {ng}件／{ok + ng}' if ng else f'photo_v2：全部 OK（{ok}件）')
sys.exit(1 if ng else 0)
