/**
 * 66_mercari_csv.gs  v1.0（2026-10-10 作成・未設置）  小判鮫 金曜のメルカリShops用CSVを作る
 *
 * 置き場：新規ファイル（既存ファイルは1文字も変えない）。どのApps Scriptプロジェクトに置いても動くよう、
 *         他ファイルの関数は使わない（自己完結）。推奨は「小判鮫_写真受付（21番）」と同じく単独のプロジェクト。
 *
 * やること（毎週金曜の朝・手動でも可）
 *   1. サイトの商品データ（公開URLの products.json）を読む
 *   2. 対象＝ published=true・status=available・links.mercari が空・KMS（新）INVENTORY の在庫が1以上
 *        かつ「メルカリの最新の商品データCSV」（Driveの 小判鮫_メルカリCSV/出品データ に置く）に同じ品番が無い
 *        かつ 過去4週間にこのCSVへ入れていない（スクリプトプロパティ MQ_SENT に記録）
 *   3. メルカリShops「商品一括登録」テンプレート（2026-10-10 取得・98列）どおりのCSVを作る
 *        価格＝KMS INVENTORY D列（税抜・Square価格が正）×1.1 を10円単位に切り上げ（龍さん決定 2026-10-10「A」）
 *        商品ステータス＝1（非公開）で登録 → 龍さんが確認してから公開（二重出品・内容の取り違え対策）
 *        カテゴリID＝既存の出品から作った対応表。表に無いカテゴリは空欄（＝メルカリ側で下書き保存になる）
 *        商品の状態＝products.json の item_condition。無ければ 4（やや傷や汚れあり）にして「要確認」に出す
 *   4. Drive の「小判鮫_メルカリCSV」フォルダに保存し、品番の一覧と要確認をメールで知らせる
 *
 * やらないこと：メルカリへの送信・アップロード（龍さんの手）／台帳・Square・サイトへの書き込み
 * 設置時の注意：appsscript.json に "timeZone": "Asia/Tokyo" と、oauthScopes で spreadsheets.readonly（KMSに書けない権限）を指定する
 * 停止：スクリプトプロパティ MQ_KILL=true で何もしない
 * 必要なスクリプトプロパティ：なし（KMSは読むだけ。メールは実行者のGmailから自分宛て）
 */

var MQ = {
  PRODUCTS_URL: 'https://kobanzame-site.pages.dev/data/products.json',
  SITE_BASE: 'https://kobanzame-site.pages.dev',
  KMS_ID: '1S1LtKrEaY8jECWTuCXyiWrVds4wUop_Yw8Seh-vhGvY',   // 新KMS「小判鮫_KMS本体」（読むだけ）
  KMS_SHEET: 'INVENTORY',
  COL_SKU: 1, COL_PRICE: 4, COL_STOCK: 6,                   // A=品番 D=販売価格（税抜） F=在庫数
  FOLDER_NAME: '小判鮫_メルカリCSV',
  EXPORT_SUBFOLDER: '出品データ',   // ここに メルカリShops「商品データのダウンロード」のCSV（product_data_*.csv）を置く。一番新しい1つを読む
  EXPORT_MAX_AGE_DAYS: 14,          // それより古いと「最新でない」と要確認に出す
  SENT_DAYS: 28,                    // CSVに入れた品番は、この日数は再び入れない
  PRICE_MAX: 9999999,
  NOTIFY_TO: 'kobansame111@gmail.com',
  TZ: 'Asia/Tokyo',
  WEEKDAY: 5,               // 金曜（トリガーが他の曜日に動いたら何もしない）
  MAX_ROWS: 50,             // 1回のCSVの上限（暴走防止。メルカリ側の上限よりずっと小さく）
  TITLE_MAX: 130, DESC_MAX: 3000, IMG_MAX: 20,
  PRICE_MIN: 300,
  FIXED: {                  // 既存の出品（K11263 ほか）と同じ値。2026-10-10 の商品データCSVで実測
    '配送方法': '1',          // 未定（出品者が手配）
    '発送元の地域': 'jp11',    // 埼玉県
    '発送までの日数': '1',     // 1〜2日で発送
    '商品ステータス': '1',     // 非公開（既存は2＝公開だが、ここだけ意図して変えている。龍さんが確認してから公開）
    '配送料の負担': '1',       // 出品者負担（送料込み）
    'SKU1_在庫数': '1',
    'SKU1_同時購入可能数': '1'
  },
  DEFAULT_CONDITION: '4'
};

// サイトの category 文字 → メルカリのカテゴリID（2026-10-10 既存出品と品番で突き合わせて作成。1対1のものだけ）
var MQ_CATEGORY = {
  'アクセサリー／ウォレットチェーン': '8mtuQojemZGE3HV2u4Adh6',
  'アクセサリー／ベルト': 'uUj69RNLzFSns9GwU5Fcme',
  'アクセサリー／帽子': 'CXwWQtpPSDGa7h7HZh9379',
  'メンズ／パンツ／デニム': 'ZEeJB2CDroEoJU4FABRttJ',
  'メンズ／アウター／ベスト': '6LFLTCdgsYf5NTpxkrW5TM',
  'メンズ／ジャケット・アウター／テーラードジャケット': 'HaLMJwJoH4XtpFgMEqYjTF',
  'レディース／アウター／デニムジャケット': 'e8K2zh2JDxS2NYfzusDLe3',
  'レディース／ジャケット・アウター／ロングコート': 'gvZjsVfxSzcChLYrMvojMH',
  'レディース／靴／サンダル': 'QrfeUZniSkEYevQwkhcjZA',
  'メンズ／トップス／Tシャツ': 'hNG2HERAh5ZhG65ZGDpLgi',
  'メンズ／トップス／スウェット': '7UsTYoS2vU9qVuXZjySMo6'
  // 2つ以上のIDに分かれていたもの（ネックレス・ワンピース・雑貨・ブーツ）は入れない＝空欄→下書き→管理画面で選ぶ
};

// products.json の item_condition（schema.org）→ メルカリの状態コード
var MQ_CONDITION = { 'NewCondition': '1' };   // UsedCondition は状態の幅が広いので既定(4)＋要確認

// メルカリShops「商品一括登録」テンプレートの列（2026-10-10 龍さんがダウンロードした product_import_template.csv と同じ順・98列）
var MQ_HEADER = (function () {
  var h = [];
  for (var i = 1; i <= 20; i++) h.push('商品画像名_' + i);
  h.push('商品名', '商品説明');
  for (var s = 1; s <= 10; s++) h.push('SKU' + s + '_種類', 'SKU' + s + '_在庫数', 'SKU' + s + '_商品管理コード', 'SKU' + s + '_JANコード', 'SKU' + s + '_catalog_id', 'SKU' + s + '_同時購入可能数');
  h.push('ブランドID', '販売価格', 'カテゴリID', '商品の状態', '配送方法', '発送元の地域', '発送までの日数', '商品ステータス', '配送料の負担', '送料ID', '発売日', '予約受付開始日', '予約受付終了日', 'キャンセル期限', 'お届け予定', 'メルカリBiz配送_クール区分');
  return h;
})();

// ===== 入口 =====================================================================

/** 金曜のトリガーから呼ぶ本体（金曜以外は何もしない） */
function mq_weekly() {
  var day = Number(Utilities.formatDate(new Date(), MQ.TZ, 'u')) % 7;
  if (day !== MQ.WEEKDAY) { Logger.log('金曜ではないので何もしません'); return; }
  return mq_run_(false);
}
/** 今すぐ1回作る（曜日を問わない） */
function mq_buildNow() { return mq_run_(false); }
/** 書き込みもメールもしないで、対象と中身をログに出す（GO前の確認用） */
function mq_dryRun() { return mq_run_(true); }

/** 毎週金曜 8時台のトリガーを1本にする（何回実行しても1本だけ） */
function mq_installTrigger() {
  ScriptApp.getProjectTriggers().forEach(function (t) { if (t.getHandlerFunction() === 'mq_weekly') ScriptApp.deleteTrigger(t); });
  ScriptApp.newTrigger('mq_weekly').timeBased().onWeekDay(ScriptApp.WeekDay.FRIDAY).atHour(8).create();
  Logger.log('毎週金曜 8時台のトリガーを1本作りました');
}

function mq_run_(dryRun) {
  if (PropertiesService.getScriptProperties().getProperty('MQ_KILL') === 'true') { Logger.log('MQ_KILL=true のため停止中'); return; }
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(10000)) {
    Logger.log('前回の実行が動いているためスキップ');
    if (!dryRun) mq_notify_('小判鮫 金曜のメルカリCSV：今回は作りませんでした', '前回の実行がまだ動いていたため、今回は飛ばしました。続くようならClaudeへ。');
    return;
  }
  try {
    var products = mq_fetchProducts_();
    var inv = mq_loadInventory_();
    var exp = mq_loadMercariExport_();
    var sent = mq_loadSent_();
    var built = mq_build_(products, inv, { onMercari: exp.skus, mercariTitles: exp.titles, exportNote: exp.note, sent: sent, now: Date.now() });
    var lines = mq_report_(built, dryRun);
    Logger.log(lines.join('\n'));
    if (dryRun) {
      if (built.rows.length) Logger.log('1行目の中身：' + JSON.stringify(mq_rowToObject_(built.rows[0])).slice(0, 3000));
      return built;
    }
    if (!built.rows.length) {
      mq_notify_('小判鮫 金曜のメルカリCSV：今週は0件', lines.join('\n'));
      return built;
    }
    var file = mq_saveCsv_(built.rows);
    mq_saveSent_(sent, built.skuList);
    lines.push('', '保存先：' + file.getUrl(), '', 'アップロード手順：メルカリShops → 商品 → CSV一括機能 → 一括登録 → ファイルを選択 → このCSV。',
               '登録は「非公開」です。中身を確認してから、商品ごとに公開してください。',
               'CSVはExcelで開いて保存し直さないでください（文字コードと改行が壊れます）。中身を見るならGoogleスプレッドシートで「表示だけ」。');
    mq_notify_('小判鮫 金曜のメルカリCSV：' + built.rows.length + '件', lines.join('\n'));
    return built;
  } catch (e) {
    var msg = String(e && e.stack || e).slice(0, 1500);
    Logger.log('失敗：' + msg);
    if (!dryRun) mq_notify_('小判鮫 金曜のメルカリCSV：失敗しました', '作れませんでした。内容：\n' + msg + '\n\n続くようならClaudeへ。');
    throw e;
  } finally { lock.releaseLock(); }
}

// ===== 読む =====================================================================

function mq_fetchProducts_() {
  var r = UrlFetchApp.fetch(MQ.PRODUCTS_URL + '?t=' + Date.now(), { muteHttpExceptions: true });
  if (r.getResponseCode() !== 200) throw new Error('products.json が読めません HTTP ' + r.getResponseCode() + ' ' + r.getContentText().slice(0, 200));
  var ps = JSON.parse(r.getContentText());
  if (!Array.isArray(ps)) throw new Error('products.json の形が配列ではありません');
  return ps;
}

/** INVENTORY → { 品番: {price, stock} }（読むだけ） */
function mq_loadInventory_() {
  var sh = SpreadsheetApp.openById(MQ.KMS_ID).getSheetByName(MQ.KMS_SHEET);
  if (!sh) throw new Error('KMSに ' + MQ.KMS_SHEET + ' タブがありません');
  var n = sh.getLastRow() - 1;
  if (n < 1) throw new Error('KMSの ' + MQ.KMS_SHEET + ' が空です（読み取りの異常の可能性）');
  var map = {};
  var vals = sh.getRange(2, 1, n, MQ.COL_STOCK).getValues();
  vals.forEach(function (r) {
    var sku = String(r[MQ.COL_SKU - 1] || '').trim().toUpperCase();
    if (!/^K\d{5}$/.test(sku)) return;
    if (map[sku]) { map[sku].dup = true; return; }               // 同じ品番が2行＝どちらが正か分からないので使わない
    map[sku] = { price: Number(r[MQ.COL_PRICE - 1]) || 0, stock: Number(r[MQ.COL_STOCK - 1]) || 0 };
  });
  return map;
}

/** Drive「小判鮫_メルカリCSV/出品データ」の一番新しい商品データCSV → {skus:{品番:true}, titles:[商品名], note} */
function mq_loadMercariExport_() {
  var none = { skus: {}, titles: [], note: '出品データ（メルカリの商品データCSV）が無いので、メルカリとの重複は確認できていません' };
  var top = DriveApp.getFoldersByName(MQ.FOLDER_NAME);
  if (!top.hasNext()) return none;
  var sub = top.next().getFoldersByName(MQ.EXPORT_SUBFOLDER);
  if (!sub.hasNext()) return none;
  var files = sub.next().getFiles(), newest = null;
  while (files.hasNext()) {
    var f = files.next();
    if (!/\.csv$/i.test(f.getName())) continue;
    if (!newest || f.getLastUpdated() > newest.getLastUpdated()) newest = f;
  }
  if (!newest) return none;
  var res = mq_parseMercariExport_(newest.getBlob().getDataAsString('UTF-8'));
  var ageDays = (Date.now() - newest.getLastUpdated().getTime()) / 86400000;
  res.note = '出品データ：' + newest.getName() + '（' + res.count + '件）' + (ageDays > MQ.EXPORT_MAX_AGE_DAYS ? '※' + Math.floor(ageDays) + '日前の古いデータです。最新をダウンロードして置き換えてください' : '');
  return res;
}

// ===== 作る（純粋関数：テストできるようにGASの機能を使わない） =================

function mq_build_(products, inv, opt) {
  opt = opt || {};
  var onMercari = opt.onMercari || {}, sent = opt.sent || {}, now = opt.now || 0, titles = opt.mercariTitles || [];
  var out = { rows: [], skus: [], skuList: [], warn: [], skipped: [], over: 0, note: opt.exportNote || '' };
  products.forEach(function (p) {
    var sku = String(p.sku || '').toUpperCase();
    if (!p.published || p.status !== 'available') return;
    if (p.links && p.links.mercari) return;                       // メルカリに出品済み
    if (!/^K\d{5}$/.test(sku)) { out.skipped.push((p.sku || '品番なし') + '：品番の形が K＋5桁ではない'); return; }
    if (onMercari[sku]) { out.skipped.push(sku + '：メルカリに同じ品番の出品がある（サイトのデータにメルカリURLが未登録＝サイト側の登録漏れ）'); return; }
    if (sent[sku] && now - sent[sku] < MQ.SENT_DAYS * 86400000) { out.skipped.push(sku + '：' + MQ.SENT_DAYS + '日以内に一度CSVへ入れた（アップロード済みならサイトにメルカリURLを登録）'); return; }
    var k = inv[sku];
    if (!k) { out.skipped.push(sku + '：KMSのINVENTORYに無い'); return; }
    if (k.dup) { out.skipped.push(sku + '：KMSのINVENTORYに同じ品番が2行ある'); return; }
    if (!(k.stock >= 1)) { out.skipped.push(sku + '：KMSの在庫が0'); return; }
    var price = mq_price_(k.price);
    if (!(price >= MQ.PRICE_MIN) || price > MQ.PRICE_MAX) { out.skipped.push(sku + '：KMSの価格が空か範囲外（' + k.price + '）'); return; }
    var imgs = mq_images_(p);
    if (!imgs.length) { out.skipped.push(sku + '：写真のURLが無い'); return; }
    if (out.rows.length >= MQ.MAX_ROWS) { out.over++; return; }

    var notes = [];
    var cat = MQ_CATEGORY[String(p.category || '')] || '';
    if (!cat) notes.push('カテゴリの対応が無い（' + (p.category || '空') + '）→下書きになるので管理画面で選ぶ');
    var cond = MQ_CONDITION[p.item_condition] || MQ.DEFAULT_CONDITION;
    if (!MQ_CONDITION[p.item_condition]) notes.push('状態は仮に「やや傷や汚れあり」→実物と合っているか確認');
    if (p.prices && p.prices.site && Number(p.prices.site) !== k.price) notes.push('サイトの価格(' + p.prices.site + ')とKMS(' + k.price + ')が違う→KMSで作成');
    var similar = mq_similarTitle_(p, titles);
    if (similar) notes.push('メルカリに似た商品名の出品あり（品番なし）：「' + similar + '」→同じ商品なら入れない');

    var o = {};
    imgs.forEach(function (u, i) { o['商品画像名_' + (i + 1)] = u; });
    o['商品名'] = mq_title_(p, sku);
    o['商品説明'] = mq_description_(p, sku, cond);
    if (mq_hasFormulaHead_(p)) notes.push('商品名か説明の先頭が = + - @ だったので全角に置き換えた');
    o['SKU1_商品管理コード'] = sku;
    o['販売価格'] = String(price);
    o['カテゴリID'] = cat;
    o['商品の状態'] = cond;
    Object.keys(MQ.FIXED).forEach(function (h) { o[h] = MQ.FIXED[h]; });
    out.rows.push(MQ_HEADER.map(function (h) { return o[h] === undefined ? '' : String(o[h]); }));
    out.skus.push(sku + ' ' + price + '円');
    out.skuList.push(sku);
    if (notes.length) out.warn.push(sku + '：' + notes.join('／'));
  });
  return out;
}

/** 値札の税込額＝税抜×1.1 を10円単位に切り上げ（サイトの税込表示と同じ規則） */
function mq_price_(taxExcluded) {
  var v = Number(taxExcluded);
  if (!(v > 0)) return 0;
  return Math.ceil(v * 110 / 100 / 10) * 10;
}

function mq_images_(p) {
  return (p.images || []).map(function (u) {
    u = String(u || '').trim();
    if (!u) return '';
    if (/^https:\/\//.test(u)) return u;
    if (u.charAt(0) === '/') return MQ.SITE_BASE + u;
    return '';
  }).filter(function (u) { return u; }).slice(0, MQ.IMG_MAX);
}

function mq_title_(p, sku) {
  var t = mq_safeHead_(mq_oneLine_(p.product_name || p.title || '').replace(sku, '').trim());
  return mq_cut_(t, MQ.TITLE_MAX - sku.length - 1) + ' ' + sku;   // 既存の出品と同じく末尾に品番（切っても品番は残す）
}

/** 説明文：10/5の K11263 の出品と同じ見出しの並び。products.json にある事実だけで組み立てる（無い項目は書かない）。
 *  長すぎるときは前半（紹介文）を削り、詳細・管理番号・状態は必ず残す */
function mq_description_(p, sku, cond) {
  var head = ['川越古民家古着屋、小判鮫です。'];
  var summary = mq_plain_(p.summary_text || '');
  if (summary) head.push(summary);
  var pts = (p.summary_points || []).map(mq_plain_).filter(String);
  if (pts.length) head.push(pts.map(function (s) { return '・' + s; }).join('\n'));
  var spec = (p.spec || []).filter(function (r) { return Array.isArray(r) && r.length >= 2 && String(r[1]).trim(); })
                           .map(function (r) { return mq_plain_(r[0]) + '：' + mq_plain_(r[1]); });
  var condText = cond === '1' ? '新品・未使用品です。' : 'ヴィンテージ・ユーズド品です。写真で状態をご確認のうえお求めください。';
  var tail = ['【Detail - 詳細】\n' + spec.concat(['管理番号：' + sku]).join('\n'),
              '【Condition - 状態】\n' + condText,
              '【Kobanzame\'s Promise - 安心ポイント】\nInspection：店主が一点ずつ丁寧に検品しています。\nShipping：丁寧に梱包し、発送いたします。'].join('\n\n');
  var room = MQ.DESC_MAX - Array.from(tail).length - 2;
  return mq_safeHead_(mq_cut_(head.join('\n\n'), Math.max(0, room)) + '\n\n' + tail);
}

/** 表計算ソフトで数式として動く先頭文字（= + - @）を全角にする（メルカリにはそのまま全角で載る） */
function mq_safeHead_(s) {
  var map = { '=': '＝', '+': '＋', '-': '－', '@': '＠' };
  s = String(s);
  return map[s.charAt(0)] ? map[s.charAt(0)] + s.slice(1) : s;
}
function mq_hasFormulaHead_(p) {
  return [p.product_name || p.title || '', p.summary_text || ''].some(function (s) { return /^[=+\-@]/.test(mq_oneLine_(s)); });
}

/** メルカリの商品名（品番なし出品の分）に、サイトの商品名の先頭の言葉（ブランド名など）が入っていれば、その名前を返す */
function mq_similarTitle_(p, titles) {
  var key = String(p.brand || '').trim();
  if (!key || key.length < 3 || /^GAW$/i.test(key)) return '';    // GAWは同じ名前の商品が多いので照合しない
  var k = key.toLowerCase();
  for (var i = 0; i < titles.length; i++) if (String(titles[i]).toLowerCase().indexOf(k) >= 0) return String(titles[i]).slice(0, 40);
  return '';
}

/** メルカリの商品データCSV（ダウンロードしたもの）→ 品番の一覧と、品番が空の出品の商品名 */
function mq_parseMercariExport_(text) {
  var rows = mq_parseCsv_(String(text).replace(/^\uFEFF/, ''));
  var h = rows[0] || [], skus = {}, titles = [], count = 0;
  var codeCols = [], iName = h.indexOf('商品名'), iStatus = h.indexOf('商品ステータス');
  h.forEach(function (c, i) { if (/^SKU\d+_商品管理コード$/.test(c)) codeCols.push(i); });
  if (iName < 0 || !codeCols.length) throw new Error('出品データCSVの列が想定と違います（商品名・SKU1_商品管理コード が無い）');
  rows.slice(1).forEach(function (r) {
    if (r.length < 2) return;
    count++;
    var any = false;
    codeCols.forEach(function (i) { var c = String(r[i] || '').trim().toUpperCase(); if (c) { skus[c] = true; any = true; } });
    if (!any && r[iName]) titles.push(r[iName]);
  });
  return { skus: skus, titles: titles, count: count };
}

/** RFC4180 のCSV（"" 囲み・改行入り）を読む */
function mq_parseCsv_(t) {
  var rows = [], row = [], f = '', q = false;
  for (var i = 0; i < t.length; i++) {
    var c = t.charAt(i);
    if (q) { if (c === '"') { if (t.charAt(i + 1) === '"') { f += '"'; i++; } else q = false; } else f += c; }
    else if (c === '"') q = true;
    else if (c === ',') { row.push(f); f = ''; }
    else if (c === '\n' || c === '\r') { if (c === '\r' && t.charAt(i + 1) === '\n') i++; row.push(f); rows.push(row); row = []; f = ''; }
    else f += c;
  }
  if (f !== '' || row.length) { row.push(f); rows.push(row); }
  return rows;
}

function mq_plain_(s) {
  return String(s == null ? '' : s).replace(/<br\s*\/?>/gi, '\n').replace(/<[^>]+>/g, '')
    .replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'")
    .replace(/[ \t]+\n/g, '\n').trim();
}
function mq_oneLine_(s) { return mq_plain_(s).replace(/\s+/g, ' ').trim(); }
function mq_cut_(s, max) { var a = Array.from(String(s)); return a.length <= max ? String(s) : a.slice(0, max).join(''); }

/** CSV（UTF-8・BOMつき・全項目を "" で囲む・改行はそのまま） */
function mq_toCsv_(rows) {
  var esc = function (v) { return '"' + String(v).replace(/"/g, '""') + '"'; };
  return '﻿' + [MQ_HEADER].concat(rows).map(function (r) { return r.map(esc).join(','); }).join('\r\n') + '\r\n';
}

function mq_rowToObject_(row) { var o = {}; MQ_HEADER.forEach(function (h, i) { if (row[i] !== '') o[h] = row[i]; }); return o; }

function mq_report_(built, dryRun) {
  var lines = [(dryRun ? '【試し実行・保存もメールもしていません】' : '') + 'メルカリ用CSV：' + built.rows.length + '件'];
  if (built.note) lines.push(built.note);
  if (built.skus.length) lines.push('対象：' + built.skus.join('・'));
  if (built.over) lines.push('上限' + MQ.MAX_ROWS + '件を超えた ' + built.over + '件は来週に回します');
  if (built.warn.length) lines.push('', '要確認：', '- ' + built.warn.join('\n- '));
  if (built.skipped.length) lines.push('', '入れなかった商品：', '- ' + built.skipped.join('\n- '));
  lines.push('', '※ メルカリに同じ商品が品番なしで出ていないか、公開の前に確認してください（サイトのデータにメルカリURLが無い商品だけを入れています）');
  return lines;
}

// ===== 保存・通知 =================================================================

function mq_saveCsv_(rows) {
  var it = DriveApp.getFoldersByName(MQ.FOLDER_NAME);
  var folder = it.hasNext() ? it.next() : DriveApp.createFolder(MQ.FOLDER_NAME);
  var name = 'mercari_' + Utilities.formatDate(new Date(), MQ.TZ, 'yyyy-MM-dd_HHmm') + '.csv';
  return folder.createFile(Utilities.newBlob(mq_toCsv_(rows), 'text/csv', name));
}

function mq_loadSent_() {
  try { return JSON.parse(PropertiesService.getScriptProperties().getProperty('MQ_SENT') || '{}'); }
  catch (e) { Logger.log('MQ_SENT が読めないので空として扱います：' + e.message); return {}; }
}
function mq_saveSent_(sent, skus) {
  var now = Date.now(), keep = {};
  Object.keys(sent).forEach(function (k) { if (now - sent[k] < MQ.SENT_DAYS * 86400000) keep[k] = sent[k]; });
  skus.forEach(function (k) { keep[k] = now; });
  PropertiesService.getScriptProperties().setProperty('MQ_SENT', JSON.stringify(keep));
}

function mq_notify_(subject, body) {
  MailApp.sendEmail(MQ.NOTIFY_TO, subject, body);
}
