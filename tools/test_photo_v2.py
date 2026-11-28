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
check('新しい型・その場で1枚＝約5.20円（11/9 見本の実測と同じ）', new_std, 5.2)
check('直した後：新しい型・まとめて1枚＝約2.60円（半額）', new_batch, 2.6)
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
pv.MANNEQUIN_OFF_FILE = os.path.join(pv.COST_DIR, 'MANNEQUIN_OFF')   # 作業用フォルダに向ける（実リポジトリの OFF ファイルを見ない）。下のマネキンの流れのテストは「マネキンON」で動かす
pv.DATA = os.path.join(tmp, 'data', 'products.json')
for _k in ('PHOTO_V2_MANNEQUIN', 'PHOTO_V2_NO_MANNEQUIN'):   # 環境変数のスイッチが付いていてもテストは素の状態で
    os.environ.pop(_k, None)

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
                'usageMetadata': pv.TYPICAL_USAGE[path.split('/')[1].split(':')[0]]}
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
    'usageMetadata': pv.TYPICAL_USAGE[pv.IMAGE_MODEL]}},
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

# ---- マネキンOFF スイッチ（2026-11-12 龍さん：成功 約29%で止める・機能は残す）----
check('OFF：既定（ファイルも環境変数も無い）は作る（False）', pv.mannequin_off(), False)
open(pv.MANNEQUIN_OFF_FILE, 'w').write('off')
check('OFF：MANNEQUIN_OFF ファイルがあれば止める（True）', pv.mannequin_off(), True)
offr = prod('K90010', 'retry'); offr['photo_v2']['mannequin_url'] = '/x.jpg'
check('OFF：retry はマネキンの対象にしない', pv.is_mannequin_retry(offr), False)
pv.remake_mannequin(offr, pv.Budget([offr]))
check('OFF：作り直しは何もしない（retry のまま・回数も増えない）',
      (offr['photo_v2']['mannequin'], offr['photo_v2'].get('mannequin_retries', 0)), ('retry', 0))
offq = [prod('K90011', 'queued')]
check('OFF：submit_batch は Batch で頼まない（0件・queued のまま）',
      (pv.submit_batch(offq, pv.Budget(offq)), offq[0]['photo_v2']['mannequin']), (0, 'queued'))
offb = [prod('K90012', 'batch')]; offb[0]['photo_v2']['mannequin_batch'] = 'batches/zzz'
check('OFF：collect_batches も受け取らない（0件・batch のまま）',
      (pv.collect_batches(offb, pv.Budget(offb)), offb[0]['photo_v2']['mannequin']), (0, 'batch'))
check('OFF：背景を揃える処理（make_v2）は止めない＝関数はそのまま使える', callable(getattr(pv, 'make_v2', None)), True)
os.remove(pv.MANNEQUIN_OFF_FILE)
os.environ['PHOTO_V2_MANNEQUIN'] = '0'
check('OFF：環境変数 PHOTO_V2_MANNEQUIN=0 でも止める', pv.mannequin_off(), True)
os.environ.pop('PHOTO_V2_MANNEQUIN')
os.environ['PHOTO_V2_NO_MANNEQUIN'] = '1'
check('OFF：前からのスイッチ PHOTO_V2_NO_MANNEQUIN=1 でも止める', pv.mannequin_off(), True)
os.environ.pop('PHOTO_V2_NO_MANNEQUIN')
check('OFF：スイッチを戻す（ファイルを消す・環境変数を外す）と ON（作る）に戻る', pv.mannequin_off(), False)

# ---- 固定モデル（2026-11-27） ----
check('固定モデル：all で8人', pv.model_ids('all'), ['M01', 'M02', 'F01', 'F02', 'M03', 'M04', 'F03', 'F04'])
check('固定モデル：足した4人だけ', pv.model_ids('M03 M04\nF03 F04'), ['M03', 'M04', 'F03', 'F04'])
check('固定モデル：名前を拾う・重なりなし・小文字も', pv.model_ids('m01\nF02 M01\nX99'), ['M01', 'F02'])
check('固定モデル：何も無ければ0人', pv.model_ids('hello'), [])
mp = pv.model_prompt('F01')
check('固定モデルの頼み文：架空の人・ロゴなし・背景の色', all(w in mp for w in ('fictional person', 'No logos', 'off-white')), True)
check('固定モデル：上位の型・1枚の見込みは上限の内（40円）', pv.image_yen_estimate(pv.PRO_IMAGE_MODEL) < pv.MODEL_PER_IMAGE_YEN, True)
check('固定モデル：ふだんの1枚の上限15円は変えない', pv.STOP_PER_IMAGE_YEN, 15.0)

# ---- 着せる試し（2026-11-27） ----
check('着せる試し：品番とモデルの組・重なりなし・小文字も', pv.tryon_requests('k10153 m02\nK10153 M02\nK11459 F01 メモ\nx'), [('K10153', 'M02'), ('K11459', 'F01')])
check('着せる試し：上限で切る', len(pv.tryon_requests('\n'.join(f'K1{i:04d} M01' for i in range(20)))), pv.TRYON_MAX)
tp = {'spec': {'サイズ': '実寸 身幅57cm・着丈73cm・肩幅53cm・袖丈20cm'}}
check('着せる試し：寸法を拾う', (pv.spec_cm(tp, '身幅'), pv.spec_cm(tp, '着丈'), pv.spec_cm(tp, '股下')), (57.0, 73.0, None))
tq = pv.tryon_prompt(tp)
check('着せる試し：頼み文に寸法と「描き直さない」', all(w in tq for w in ('chest width (flat) 57 cm', 'Do not add, remove, redraw')), True)

# ---- 着せた写真の検品（2026-11-28） ----
allsame = {'items': {k: 'same' for k in pv.CHECK_ITEMS}, 'problem': ''}
check('検品：全部 same なら載せる', pv.tryon_verdict(allsame), (True, ''))
one = {'items': dict(allsame['items'], text_logo='different'), 'problem': 'ロゴの文字が違う'}
check('検品：1つ different なら載せない', pv.tryon_verdict(one)[0], False)
check('検品：unsure も載せない', pv.tryon_verdict({'items': dict(allsame['items'], sleeve_length='unsure')})[0], False)
check('検品：項目が抜けていたら載せない', pv.tryon_verdict({'items': {'color': 'same'}})[0], False)
check('検品：返事が配列でも読む', pv.tryon_verdict([allsame])[0], True)

# 検品 v2（1枚ずつ書き出して Python で比べる）
A = {'garment_type': 't_shirt', 'sleeve_length': 'short', 'collar_type': 'crew_neck', 'front_closure': 'none',
     'pattern_type': 'graphic_print', 'primary_color': 'black', 'graphic_presence': 'present', 'text_presence': 'present',
     'button_count': 0, 'button_count_status': 'not_applicable', 'pocket_count': 0, 'pocket_status': 'exact', 'sleeve_to_body_ratio': 0.3}
T = {'text_presence': 'present', 'text_transcription': 'HARLEY-DAVIDSON', 'letters_legible': 'yes', 'text_fully_visible': 'yes'}
check('v2：全部同じなら載せる', pv.compare_attrs(A, dict(A), T, dict(T)), (True, []))
check('v2：袖が短→長はダメ', pv.compare_attrs(A, dict(A, sleeve_length='long'), T, T)[0], False)
check('v2：文字が崩れたらダメ', pv.compare_attrs(A, A, T, dict(T, text_transcription='HARLEY-DAVIDSOM'))[0], False)
check('v2：文字の読みが同じでも崩れの印があればダメ', pv.compare_attrs(A, A, T, dict(T, letters_legible='no'))[0], False)
check('v2：文字が隠れていたらダメ', pv.compare_attrs(A, A, T, dict(T, text_fully_visible='no'))[0], False)
check('v2：文字の大小・記号の違いは同じ', pv.compare_attrs(A, A, T, dict(T, text_transcription='harley davidson'))[0], True)
N = {'text_presence': 'absent', 'text_transcription': '', 'letters_legible': 'not_applicable', 'text_fully_visible': 'not_applicable'}
A0 = dict(A, text_presence='absent', pattern_type='solid', graphic_presence='absent')
check('v2：両方とも文字が無いなら同じ', pv.compare_attrs(A0, dict(A0), N, dict(N))[0], True)
check('v2：文字が増えたらダメ', pv.compare_attrs(A0, dict(A0, text_presence='present'), N, T)[0], False)
check('v2：同じ写真の2回の読みが食い違えばダメ', pv.compare_attrs(A0, A0, N, dict(N, text_presence='present'))[0], False)
check('v2：分からない（unclear）はダメ', pv.compare_attrs(A, dict(A, collar_type='unclear'), T, T)[0], False)
check('v2：隠れている（hidden）はダメ', pv.compare_attrs(A, dict(A, sleeve_length='hidden'), T, T)[0], False)
check('v2：項目が抜けていたらダメ', pv.compare_attrs(A, {k: v for k, v in A.items() if k != 'pattern_type'}, T, T)[0], False)
check('v2：ポケットが増えたらダメ', pv.compare_attrs(A, dict(A, pocket_count=1), T, T)[0], False)
check('v2：ポケットが数えられないならダメ', pv.compare_attrs(A, dict(A, pocket_status='hidden'), T, T)[0], False)
S = dict(A0, garment_type='shirt', front_closure='buttons', button_count=6, button_count_status='exact', collar_type='shirt_collar')
check('v2：ボタンの数が同じなら通す', pv.compare_attrs(S, dict(S), N, N)[0], True)
check('v3：ボタンの数は比べない（平置きと着用でぶれる）', pv.compare_attrs(S, dict(S, button_count=5), N, N)[0], True)
check('v3：袖の割合が0.25以上違えばダメ（短い袖→長い袖）', pv.compare_attrs(A, dict(A, sleeve_to_body_ratio=0.9), T, T)[0], False)
check('v3：袖の割合の小さな差は通す', pv.compare_attrs(A, dict(A, sleeve_to_body_ratio=0.4), T, T)[0], True)
check('v3：袖の割合が無ければダメ', pv.compare_attrs(A, {k: v for k, v in A.items() if k != 'sleeve_to_body_ratio'}, T, T)[0], False)
check('v3：シャツと「その他」の上着は同じ組', pv.compare_attrs(dict(A, garment_type='shirt'), dict(A, garment_type='other'), T, T)[0], True)
check('v3：上着とズボンは違う', pv.compare_attrs(A, dict(A, garment_type='pants'), T, T)[0], False)
check('v3：柄の other は比べない', pv.compare_attrs(dict(A, pattern_type='other'), dict(A, pattern_type='solid'), T, T)[0], True)
check('v3：無地と縞は違う', pv.compare_attrs(dict(A, pattern_type='solid'), dict(A, pattern_type='stripe'), T, T)[0], False)
check('v3：多色が出たら色は比べない', pv.compare_attrs(dict(A, primary_color='purple'), dict(A, primary_color='multicolor'), T, T)[0], True)
check('v2：黒と紺は違う', pv.compare_attrs(A, dict(A, primary_color='navy'), T, T)[0], False)
check('v2：紺と青は同じ色とみなす（青どうし）', pv.compare_attrs(dict(A, primary_color='blue'), dict(A, primary_color='navy'), T, T)[0], True)
check('v2：黒と赤は違う', pv.compare_attrs(A, dict(A, primary_color='red'), T, T)[0], False)
check('v2：文字の正規化', pv.norm_text(' Harley-Davidson® 1903 '), 'HARLEYDAVIDSON1903')
check('v2：型の必須項目', sorted(pv.GARMENT_SCHEMA['required']), sorted(list(pv.GARMENT_ENUMS) + ['button_count', 'pocket_count']))
check('v2：返事が空でもダメで止まる', pv.compare_attrs({}, {}, {}, {})[0], False)

# 検品 v4（袖は点の位置から Python で測る・状態を分ける）
def P(**kw):
    base = {'neck_center': (500, 100), 'hem_center': (500, 900), 'left_shoulder': (300, 150), 'right_shoulder': (700, 150),
            'left_cuff': (150, 300), 'right_cuff': (850, 300)}
    base.update(kw)
    return {k: {'x': v[0], 'y': v[1], 'visible': True} for k, v in base.items()}
short = pv.sleeve_from_points(P(), 1000, 1000)
check('v4：袖の短い点は short', short[0], 'short')
long_ = pv.sleeve_from_points(P(left_cuff=(250, 750), right_cuff=(750, 750)), 1000, 1000)
check('v4.1：割合0.46（着用の半袖Tくらい）は short', pv.sleeve_from_points(P(left_cuff=(180, 500), right_cuff=(820, 500)), 1000, 1000)[:2], ('short', 0.46))
check('v4：袖の長い点は long', long_[0], 'long')
check('v4：見えない点があれば決めない', pv.sleeve_from_points(dict(P(), left_cuff={'x': 1, 'y': 1, 'visible': False}), 1000, 1000)[0], None)
check('v4：左右が違いすぎたら決めない', pv.sleeve_from_points(P(left_cuff=(250, 750)), 1000, 1000)[0], None)
check('v4：点が無ければ決めない', pv.sleeve_from_points({}, 1000, 1000)[0], None)
check('v4：画像の縦横を使って測る', pv.sleeve_from_points(P(), 500, 1000)[0], 'short')
B = dict(A, collar_type='turtleneck', pattern_type='knit_texture', primary_color='brown', text_presence='absent', graphic_presence='absent')
check('v4：全部同じ・袖も同じなら合格', pv.compare_v4(B, dict(B), N, N, short, short), ('合格', []))
check('v4：半袖→長袖は袖だけで不一致', pv.compare_v4(B, dict(B), N, N, short, long_)[0], '不一致')
check('v4：袖の理由が書かれる', '袖の長さが違う' in pv.compare_v4(B, dict(B), N, N, short, long_)[1][0], True)
check('v4：モックネックとタートルは同じ組', pv.compare_v4(B, dict(B, collar_type='mock_neck'), N, N, short, short)[0], '合格')
check('v4：丸首と襟付きは不一致', pv.compare_v4(B, dict(B, collar_type='shirt_collar'), N, N, short, short)[0], '不一致')
check('v4：袖が測れないなら判定不能', pv.compare_v4(B, dict(B), N, N, short, (None, None, 'x'))[0], '判定不能')
check('v4：中くらいどうしは判定不能', pv.compare_v4(B, dict(B), N, N, ('mid', 0.5, ''), ('mid', 0.5, ''))[0], '判定不能')
check('v4：ポケット hidden は判定不能（不一致ではない）', pv.compare_v4(B, dict(B, pocket_status='hidden'), N, N, short, short)[0], '判定不能')
check('v4：文字の書き換えは不一致', pv.compare_v4(A, dict(A), T, dict(T, text_transcription="CATCH'EM LOUISIANA"), short, short)[0], '不一致')
check('v4：着用の文字崩れは不一致', pv.compare_v4(A, dict(A), T, dict(T, letters_legible='no'), short, short)[0], '不一致')
check('v4：文字が増えたら不一致', pv.compare_v4(B, dict(B), N, T, short, short)[0], '不一致')
check('v4：文字が定まらないなら判定不能', pv.compare_v4(B, dict(B), N, dict(N, text_presence='unclear'), short, short)[0], '判定不能')
check('v4：違いと分からないが両方なら不一致', pv.compare_v4(B, dict(B, pocket_status='hidden'), N, N, short, long_)[0], '不一致')
check('v4：返事が空なら合格にしない', pv.compare_v4({}, {}, {}, {}, None, None)[0] != '合格', True)
# 文字の読みの食い違いの決め方
calls = []
def again(v):
    def f():
        calls.append(1); return {'text_presence': v}
    return f
check('v4：2回の読みが同じなら読み直さない', (pv.settle_text({'text_presence': 'absent'}, N, again('present'))[0]['text_presence'], len(calls)), ('absent', 0))
check('v4：読み直しが文字の読みと同じなら採る', pv.settle_text({'text_presence': 'present'}, N, again('absent'))[0]['text_presence'], 'absent')
check('v4：読み直しが特徴の方と同じならそれを採る', pv.settle_text({'text_presence': 'absent'}, T, again('absent'))[0]['text_presence'], 'absent')
check('v4：読み直しが分からないなら定まらない', pv.settle_text({'text_presence': 'absent'}, T, again('unclear'))[0]['text_presence'], 'unclear')
check('v4：状態は4つ', pv.V4_STATUS, ('合格', '不一致', '判定不能', 'システム障害'))
check('検品：選んだモデル8人', sorted(pv.MODEL_PICK), ['F01', 'F02', 'F03', 'F04', 'M01', 'M02', 'M03', 'M04'])

print(f'NG {ng}件／{ok + ng}' if ng else f'photo_v2：全部 OK（{ok}件）')
sys.exit(1 if ng else 0)
