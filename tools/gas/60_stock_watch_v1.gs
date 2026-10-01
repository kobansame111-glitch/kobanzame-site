/**
 * 60_stock_watch_v1.gs  小判鮫 在庫見張り（Square × メルカリ × 公式サイト）  v1.4  2026-10-01
 * ---------------------------------------------------------------------------------
 * 何をするか（Claudeは使わない・GASだけで回る）：
 *   【15分おき】sw_watch
 *     A. Squareで在庫が0になった商品（店頭レジ・サイトの決済リンク）を見つける
 *        → サイト掲載品なら サイトを SOLD 表示に（data/products.json を書き換え→GitHub Actionsが作り直し）
 *        → 通知「K○○ Squareで売れました。メルカリに出していたら止めてください」
 *        ※サイト掲載品は毎回「在庫数そのもの」も直接確認する（取りこぼし防止）
 *     B. メルカリの購入メール（no-reply@mercari-shops.com「発送をお願いします」・送信元の署名が本物のものだけ）
 *        → 商品名（または商品管理コード）でSKUを特定
 *        → Squareの在庫を0に（※スイッチ SW_ENABLE_SQUARE_WRITE=true の時だけ。初期はfalse＝通知で促すだけ）
 *        → サイト掲載品なら SOLD 表示に
 *        → 通知
 *   【毎朝9:30】sw_dailyHealth（読み取りと通知だけ。何も書き換えない）
 *     サイトの全商品ページが開くか／購入ボタンのリンク先が正しいか／Squareの在庫とサイト表示の食い違い／
 *     見張り自体が止まっていないか → 異常がある時だけ通知
 *
 * 龍さんの操作（手順書：Project claude/claude_在庫見張り_v1_確認手順_2026-10-01.md）：
 *   1) スクリプトプロパティに SQUARE_ACCESS_TOKEN を追加（値はClaudeは見ない）。GITHUB_TOKEN は設定済み。
 *      LINEで受けたい場合は LINE_CHANNEL_ACCESS_TOKEN と LINE_TO_USER_ID も（無ければ自分宛てメール）
 *   2) 関数 sw_setup を実行 → Googleの「許可」を押す（権限承認は龍さん本人）
 *   3) 関数 sw_dryRun と sw_dryRunHealth を実行（書き込み・通知なし。判定結果が見張りシートの「ログ」に出る）
 *   4) 関数 sw_testNotify（通知が届くか）→ sw_testSiteSold（テスト用ダミーでSOLD化→元に戻す）
 *   5) 関数 sw_installTriggers を実行（15分おき＋毎朝9:30 の2本がONになる。過去のメールは通知しない）
 *   止める時：sw_removeTriggers を実行、またはスクリプトプロパティ SW_KILL に true
 *
 * 安全設計：
 *   - 既存ファイル（コード.gs＝50番）とは名前が衝突しないよう、全て sw_ / SW_ で始まる名前にしている
 *     ※50番の publishSiteShell / publishSpoonTest / publishStyleCss は旧方式（HTML直書き）なので今後は実行しない
 *   - 失敗は握り潰さない：HTTPステータスと本文を「ログ」シートに残し、通知も出す（同じ種類のエラーは1時間に1回まで）
 *     見張りシート自体が壊れた時も、シートを使わずに直接通知する
 *   - 同じ出来事で二度通知しない（「処理済み」シート）。処理済みの印は「通知が届いた後」に付ける
 *   - サイトのSOLD化に失敗したSKUは「保留」として次回も再試行する
 *   - Squareへの書き込みはスイッチで初期OFF。サイトの書き換えは data/products.json の status だけ
 *   - トークン類は全てスクリプトプロパティ（コードに書かない・ログに出さない）
 */

// ===== 設定 =====================================================================
var SW = {
  GH_OWNER: 'kobansame111-glitch',
  GH_REPO: 'kobanzame-site',
  GH_BRANCH: 'main',
  PRODUCTS_PATH: 'data/products.json',
  SITE_BASE: 'https://kobanzame-site.pages.dev',
  SQ_API: 'https://connect.squareup.com/v2',
  SQ_VERSION: '2025-01-23',
  SQ_LOCATION_ID: 'LCAGPZCFQEFFD',          // （株）プラグ の店舗ID（Squareの発送設定画面のURLで確認。sw_setup で実在を点検）
  MERCARI_FROM: 'no-reply@mercari-shops.com',
  MERCARI_DOMAIN: 'mercari-shops.com',
  MERCARI_SUBJECT: '"発送をお願いします"',
  MAIL_NEWER_THAN: '7d',                     // メール検索の範囲（処理済みで重複は防ぐ。長めにして取りこぼしを防ぐ）
  SHEET_NAME: '小判鮫_在庫見張り（60番）',
  TZ: 'Asia/Tokyo',
  WATCH_STALE_MIN: 90,                       // 見張りが90分動いていなければ、毎朝チェックで異常扱い
  FIRST_LOOKBACK_MIN: 30,                    // 初回実行で遡る時間
  MAX_LOOKBACK_MIN: 24 * 60                  // 止まっていた後に再開しても、遡るのは最大24時間まで
};
var SW_SQ_MISSING = 'SQUARE_ACCESS_TOKEN 未設定のため Square の見張りは停止中';

// 見張り対象の初期データ（sw_setup が「見張り対象」シートに書き込む。以後はシートが正）
// メルカリ商品名は購入メールとの照合用（メルカリで商品名を変えたらシートも直す）
var SW_SEED = [
  { sku: 'K11272', memo: 'GAW スプーンペンダント（サイト掲載）', mercariId: '2JX8ZeDHkG6rE72TdZiWWe', mercariTitle: '【GAWリメイク】洋白製スプーンネックレス／ホワイトハーツビーズ', onMercari: 'FALSE' },
  { sku: 'K11273', memo: 'GAW スプーンペンダント（もう1本・Square未登録・メルカリ公開中）', mercariId: '2JX8ZYUyxDEagbA29urio2', mercariTitle: '【GAWリメイク】洋白製スプーンネックレス／ホワイトハーツビーズ', onMercari: 'TRUE' },
  { sku: 'K11274', memo: 'GAW ウォレットチェーン（サイト掲載）', mercariId: '2JVTFRvTVuHd46RXqVcwvM', mercariTitle: 'GAW ウォレットチェーン 真鍮 ブラス 喜平チェーン 49cm ヴィンテージスプーン フック ハンドメイド 一点物 小判鮫オリジナル Brass Wallet Chain', onMercari: 'FALSE' },
  { sku: 'K10015', memo: "Wild's Palace of Poison T（サイト掲載）", mercariId: '2JREXvcVtpP3fd4NCWd6Zb', mercariTitle: "90s USA製 1994 Wild's Palace of Poison カーイベント スカルプリント Tシャツ XXL ヴィンテージ Fruit of the Loom アド系 ホットロッド ロカビリー 古着", onMercari: 'FALSE' },
  { sku: 'K10888', memo: 'Cacharel リネンジャケット（サイト掲載）', mercariId: '2JREPDZcpzPKyifQJHy4Br', mercariTitle: '90s Cacharel カシャレル リネン100% テーラードジャケット 3ボタン シングル マスタードイエロー Yellow Linen ヴィンテージ', onMercari: 'FALSE' },
  { sku: 'K10889', memo: 'Bon Vivant ジャケット（サイト掲載）', mercariId: '2JRMiH7DuMxRnQC2f373sk', mercariTitle: '【デッドストック】Bon Vivant ボンヴィヴァン リネン混 ヴィンテージ テーラードジャケット ブレザー ベージュ ナチュラル アメリカ 70s 80s しつけ糸付き 未使用 古着', onMercari: 'FALSE' },
  { sku: 'K10715', memo: 'MISTY WEATHER トレンチ（サイト掲載）', mercariId: '2JNC3SPNFCFzfgWL4KPU6F', mercariTitle: '80s MISTY WEATHER 漆黒ナイロン ロングトレンチコート | レインコート/ラグランスリーブ/ヴィンテージ/ブラック', onMercari: 'FALSE' }
];

var SW_TARGET_HEADER = ['SKU', 'メモ', 'メルカリ商品名（購入メール照合用・前後の空白は無視）', 'メルカリ商品ID', 'メルカリ出品中（TRUE/FALSE）', '最終更新'];
var SW_LOG_HEADER = ['日時', '実行', '種類', 'SKU', '内容', '結果', '詳細（HTTP・エラー本文）'];
var SW_DONE_HEADER = ['キー', '日時', 'メモ'];

// 1回の実行の中だけ使う覚え書き（シートを何度も開かない）
var SW_MEMO = { ss: null, done: null };

// ===== 入口（トリガー・手動実行） ==================================================

/** 15分おきトリガー本体 */
function sw_watch() { sw_guard_('見張り', function () { sw_run_({ dryRun: false, label: 'watch' }); }); }

/** 書き込み・通知なしで判定だけ（Square 24時間・メール7日分を見る） */
function sw_dryRun() {
  var r = sw_run_({ dryRun: true, label: 'dryRun', sqLookbackMin: 24 * 60 });
  Logger.log(JSON.stringify(r, null, 1));
  return r;
}

/** 毎朝9:30トリガー本体 */
function sw_dailyHealth() { sw_guard_('毎朝チェック', function () { sw_health_({ dryRun: false }); }); }

/** 健康チェックを通知なしで */
function sw_dryRunHealth() { var r = sw_health_({ dryRun: true }); Logger.log(JSON.stringify(r, null, 1)); return r; }

/** トリガー実行の一番外側：想定外の例外も、シートを使わずに直接通知してから投げ直す */
function sw_guard_(what, fn) {
  try { fn(); }
  catch (e) {
    var cache = CacheService.getScriptCache(), key = 'sw_fatal_' + what;
    if (!cache.get(key)) {
      try { sw_notifyDirect_('小判鮫 在庫見張り：' + what + 'が止まりました', String(e && e.stack || e)); cache.put(key, '1', 3600); }
      catch (e2) { Logger.log('通知も失敗: ' + e2); }
    }
    throw e;
  }
}

// ===== 許可の取り直し ============================================================

/** 足りない許可（Gmailなど）を求め直す。実行すると許可画面が出る →「すべて選択」にチェックして許可 */
function sw_authorize() {
  ScriptApp.requireAllScopes(ScriptApp.AuthMode.FULL);
  Logger.log('すべての許可がそろっています。次は sw_setup をもう一度実行してください。');
}

// ===== 初期設定 ==================================================================

/** 見張りシートを作り、見張り対象を書き込み、接続を点検する（何度実行しても安全） */
function sw_setup() {
  ScriptApp.requireAllScopes(ScriptApp.AuthMode.FULL);   // 許可が1つでも足りなければ、ここで許可画面を出し直す
  var props = PropertiesService.getScriptProperties();
  var ss = sw_sheet_(true);   // setup だけは無ければ作る
  var tgt = ss.getSheetByName('見張り対象');
  if (tgt.getLastRow() < 2) {
    var now = sw_now_();
    var rows = SW_SEED.map(function (s) { return [s.sku, s.memo, s.mercariTitle, s.mercariId, s.onMercari, now]; });
    tgt.getRange(2, 1, rows.length, SW_TARGET_HEADER.length).setValues(rows);
  }
  if (!props.getProperty('SW_ENABLE_SQUARE_WRITE')) props.setProperty('SW_ENABLE_SQUARE_WRITE', 'false');
  if (!props.getProperty('SW_NOTIFY_UNKNOWN_STORE_SALES')) props.setProperty('SW_NOTIFY_UNKNOWN_STORE_SALES', 'true');
  if (!props.getProperty('SW_KILL')) props.setProperty('SW_KILL', 'false');

  var check = sw_selfCheck_();
  sw_log_('setup', '点検', '', '接続チェック', check.ok ? 'OK' : '要対応', JSON.stringify(check));
  Logger.log('見張りシート: ' + ss.getUrl());
  Logger.log(JSON.stringify(check, null, 1));
  return check;
}

/** 各接続の点検（読み取りのみ） */
function sw_selfCheck_() {
  var props = PropertiesService.getScriptProperties();
  var out = { ok: true, items: [] };
  function add(name, ok, detail) { out.items.push({ name: name, ok: ok, detail: detail }); if (!ok) out.ok = false; }

  try { var p = sw_ghGetProducts_(); add('GitHub 商品データ読み取り', true, p.products.length + '件'); }
  catch (e) { add('GitHub 商品データ読み取り', false, String(e)); }

  if (!props.getProperty('SQUARE_ACCESS_TOKEN')) add('Square トークン', false, 'スクリプトプロパティ SQUARE_ACCESS_TOKEN が未設定');
  else {
    try { var loc = sw_sq_('get', '/locations/' + SW.SQ_LOCATION_ID); add('Square 店舗', true, (loc.location && loc.location.name) || 'OK'); }
    catch (e) { add('Square 店舗', false, String(e)); }
  }

  try {
    var ms = sw_readMercariMails_('365d');
    add('Gmail メルカリ購入メール', true, '過去1年で' + ms.mails.length + '件（署名が本物' + ms.mails.filter(function (m) { return m.verified; }).length + '件・読み取れないメール' + ms.unparsed.length + '件）');
  } catch (e) { add('Gmail メルカリ購入メール', false, String(e)); }

  var line = props.getProperty('LINE_CHANNEL_ACCESS_TOKEN') && props.getProperty('LINE_TO_USER_ID');
  add('通知の経路', true, line ? 'LINE（失敗時はメール）' : 'メール（' + Session.getEffectiveUser().getEmail() + ' 宛て。LINEにする場合は LINE_CHANNEL_ACCESS_TOKEN と LINE_TO_USER_ID を追加）');
  add('Squareへの自動書き込み', true, props.getProperty('SW_ENABLE_SQUARE_WRITE') === 'true' ? 'ON' : 'OFF（通知で促すだけ）');
  return out;
}

// ===== 見張り本体 ================================================================

function sw_run_(opt) {
  SW_MEMO = { ss: null, done: null };
  var props = PropertiesService.getScriptProperties();
  if (props.getProperty('SW_KILL') === 'true') { Logger.log('SW_KILL=true のため停止中'); return { stopped: true }; }
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(20000)) { sw_log_(opt.label, '見張り', '', '前回の実行がまだ動いているためスキップ', 'SKIP', ''); return { skipped: true }; }

  var startedAt = new Date();
  var result = { dryRun: opt.dryRun, squareSold: [], mercariSold: [], siteSold: [], notices: [], errors: [] };
  var pendingDone = [];   // [key, memo]：通知が届いたら処理済みにする
  var pendingSheet = [];  // [sku, 値]：通知が届いたら見張り対象の「メルカリ出品中」を書き換える
  var mercariSkus = {};   // この回にメルカリで売れたSKU（Square側の「売れました」通知を抑止）
  var sqScanOk = false;
  try {
    var targets = sw_readTargets_();
    var prod = null;
    try { prod = sw_ghGetProducts_(); } catch (e) { result.errors.push({ kind: 'github', text: 'GitHub読み取り: ' + e }); }
    var siteLive = {};
    var siteSkus = {};
    if (prod) prod.products.forEach(function (p) { if (p.sku && p.published) siteSkus[p.sku] = true; if (p.sku && p.published && p.status !== 'sold') siteLive[p.sku] = p; });

    // SOLD化待ち（前回失敗した分も含む）
    var toSold = {};
    sw_pendingSold_().forEach(function (s) { toSold[s] = '前回の再試行'; });
    var hasSq = !!props.getProperty('SQUARE_ACCESS_TOKEN');
    var seenVar = {};

    // ---- B. メルカリ：購入メール ----
    try {
      var ms = sw_readMercariMails_(SW.MAIL_NEWER_THAN);
      ms.unparsed.forEach(function (u) {
        var key = 'mailbad:' + u.messageId;
        if (sw_isDone_(key)) return;
        result.errors.push({ kind: 'mail-parse', text: 'メルカリのメールから商品名を読み取れませんでした（書式が変わった可能性）件名: ' + u.subject + ' / id=' + u.messageId });
        result.notices.push('【要確認】メルカリの購入メールを読み取れませんでした。何が売れたか確認してください。\n件名: ' + u.subject);
        pendingDone.push([key, u.subject]);
      });
      ms.mails.forEach(function (m) {
        m.items.forEach(function (title, idx) {
          try {
            var key = 'mail:' + m.messageId + ':' + idx;
            if (sw_isDone_(key)) return;
            if (!m.verified) {
              result.notices.push('【要確認】メルカリを名乗るメールですが送信元の署名を確認できません（自動処理はしていません）\n商品名: ' + title);
              sw_log_(opt.label, 'メルカリ購入（署名未確認）', '', title, opt.dryRun ? 'DRYRUN' : '通知のみ', 'msg=' + m.messageId);
              pendingDone.push([key, title]);
              return;
            }
            var match = sw_matchSku_({ title: title, code: idx === 0 ? m.code : '' }, targets);
            result.mercariSold.push({ title: title, sku: match.sku, how: match.how, orderId: m.orderId });
            var lines = ['【メルカリで売れました】' + (match.sku ? match.sku + ' ' : '') + title, '注文 ' + (m.orderId || '-')];
            if (match.sku) {
              if (prod && prod.products.some(function (p) { return p.sku === match.sku && p.published; }) || siteLive[match.sku]) lines.push('・公式サイトは自動でSOLD表示にします');
              toSold[match.sku] = 'メルカリ';   // サイトに無いSKUは sw_applySold_ で何も起きない
              var zr = sw_sqZeroForMercari_(match.sku, m.messageId + ':' + idx, opt);
              lines.push(zr.line);
              mercariSkus[match.sku] = zr.zeroed ? 'zeroed' : 'wait';
              if (!opt.dryRun) { pendingSheet.push([match.sku, 'FALSE']); pendingDone.push([(zr.zeroed ? 'mzero:' : 'mwait:') + match.sku, 'メルカリで売約']); }
            } else if (match.how === 'ambiguous') {
              lines.push('▶ 同じ商品名が複数あり、どれか特定できません（候補: ' + match.candidates.join(', ') + '）。Squareの在庫とサイトを手で確認してください');
            } else {
              lines.push('▶ 見張り対象に無い商品です。Squareに同じ商品があれば在庫を0にしてください');
            }
            result.notices.push(lines.join('\n'));
            sw_log_(opt.label, 'メルカリ購入', match.sku || '', title, opt.dryRun ? 'DRYRUN' : '通知', 'how=' + match.how + ' order=' + m.orderId + ' msg=' + m.messageId);
            pendingDone.push([key, match.sku || title]);
          } catch (e) { result.errors.push({ kind: 'mail', text: 'メルカリ購入メール処理（' + title + '）: ' + e }); }
        });
      });
    } catch (e) { result.errors.push({ kind: 'mail', text: 'メルカリメール読み取り: ' + e }); }

    // ---- A1. サイト掲載品は在庫数そのものを直接確認 ----
    if (hasSq) {
      // 販売中の掲載品＋「SOLDにしたが売れた通知がまだ届いていない」掲載品（通知失敗の再送のため）
      var siteCheck = {};
      Object.keys(siteLive).forEach(function (sku) { siteCheck[sku] = siteLive[sku]; });
      if (prod) prod.products.forEach(function (p) { if (p.sku && p.published && p.status === 'sold' && sw_isDone_('wsold:' + p.sku) && !sw_isDone_('site0:' + p.sku)) siteCheck[p.sku] = p; });
      Object.keys(siteCheck).forEach(function (sku) {
        try {
          var live = !!siteLive[sku];
          var v = sw_sqFindVariation_(sku);
          if (!v) { if (live) result.errors.push({ kind: 'sq-missing-' + sku, text: sku + ' がSquareに見つかりません（サイトは販売中）' }); return; }
          var qty = sw_sqQty_(v.id);
          if (qty === null) { if (live) result.errors.push({ kind: 'sq-norecord-' + sku, text: sku + ' はSquareで在庫数が未登録です（在庫の追跡をONにしてください）' }); return; }
          if (qty > 0) return;
          seenVar[v.id] = true;
          var key = 'site0:' + sku;
          if (sw_isDone_(key)) return;   // 通知済み（SOLD化の失敗分は「保留」から再試行される）
          toSold[sku] = 'Square在庫0';
          var t = targets[sku];
          var viaMercari = mercariSkus[sku] === 'zeroed' || sw_isDone_('mzero:' + sku);
          var afterMercari = !viaMercari && (mercariSkus[sku] === 'wait' || sw_isDone_('mwait:' + sku));
          var text = viaMercari ? null : afterMercari ? sw_afterMercariText_(sku, siteCheck[sku].product_name) : '【Squareで売れました】' + sku + ' ' + (siteCheck[sku].product_name || '') + '\n' + sw_mercariAdvice_(t) + '\n・公式サイトは' + (live ? '自動でSOLD表示にします' : 'SOLD表示にしてあります');
          if (text) result.notices.push(text);
          result.squareSold.push({ sku: sku, name: siteCheck[sku].product_name, how: 'サイト掲載品の直接確認' });
          sw_log_(opt.label, 'Square在庫0（サイト掲載品）', sku, siteCheck[sku].product_name, opt.dryRun ? 'DRYRUN' : (text ? '通知' : 'メルカリ経由で処理済み'), 'variation=' + v.id);
          pendingDone.push([key, sku]);
        } catch (e) { result.errors.push({ kind: 'sq', text: sku + ' の在庫確認: ' + e }); }
      });
    }

    // ---- A2. その他：前回以降に在庫0になった商品 ----
    if (hasSq && !prod) {
      result.errors.push({ kind: 'sq-skip', text: 'GitHubが読めないため、Squareの更新分の検索は次回に回しました（取りこぼしはしません）' });
    } else if (hasSq) {
      try {
        var last = props.getProperty('SW_LAST_SQ_CHECK');
        var since = opt.sqLookbackMin ? new Date(startedAt.getTime() - opt.sqLookbackMin * 60000)
          : new Date(Math.max(last ? new Date(last).getTime() : startedAt.getTime() - SW.FIRST_LOOKBACK_MIN * 60000,
                              startedAt.getTime() - SW.MAX_LOOKBACK_MIN * 60000));
        sw_sqZeroSince_(since).forEach(function (z) {
          if (seenVar[z.variationId]) return;           // A1で扱った
          if (z.sku && siteSkus[z.sku]) return;          // サイト掲載品（販売中・SOLD問わず）はA1が担当
          var key = 'sq0:' + z.variationId + ':' + z.calculatedAt;
          if (sw_isDone_(key)) return;
          var viaMercari = z.sku && (mercariSkus[z.sku] === 'zeroed' || sw_isDone_('mzero:' + z.sku));
          var afterMercari = z.sku && !viaMercari && (mercariSkus[z.sku] === 'wait' || sw_isDone_('mwait:' + z.sku));
          var t = z.sku ? targets[z.sku] : null;
          var notify = !viaMercari && (afterMercari || (t && t.onMercari !== 'FALSE') || (!t && props.getProperty('SW_NOTIFY_UNKNOWN_STORE_SALES') !== 'false'));
          if (notify) result.notices.push(afterMercari ? sw_afterMercariText_(z.sku, z.name) : '【Squareで売れました】' + (z.sku || '(SKUなし)') + ' ' + (z.name || '') + '\n' + sw_mercariAdvice_(t));
          result.squareSold.push({ sku: z.sku, name: z.name, how: '更新分の検索' });
          sw_log_(opt.label, 'Square在庫0', z.sku, z.name, opt.dryRun ? 'DRYRUN' : (viaMercari ? 'メルカリ経由で処理済み' : (notify ? '通知' : '記録のみ')), 'variation=' + z.variationId + ' calculated_at=' + z.calculatedAt);
          pendingDone.push([key, z.sku]);
        });
        sqScanOk = true;
      } catch (e) { result.errors.push({ kind: 'sq', text: 'Square読み取り: ' + e }); }
    } else {
      result.errors.push({ kind: 'sq-token', text: SW_SQ_MISSING });
    }

    // ---- サイトの SOLD 化 ----
    var soldSkus = Object.keys(toSold).filter(function (s) { return !!s; });
    if (soldSkus.length) {
      result.siteSold = soldSkus;
      if (!opt.dryRun) {
        try {
          var r = sw_ghMarkSold_(soldSkus);
          sw_setPendingSold_([]);
          soldSkus.forEach(function (k) { sw_markDone_('wsold:' + k, '見張りがSOLDにした'); });
          sw_log_(opt.label, 'サイトSOLD化', soldSkus.join(','), 'data/products.json を更新', 'OK', 'commit=' + r);
        } catch (e) {
          sw_setPendingSold_(soldSkus);   // 次回もう一度
          result.errors.push({ kind: 'github-sold', text: 'サイトSOLD化（' + soldSkus.join(', ') + '）: ' + e });
          result.notices.push('【要対応】サイトのSOLD化に失敗しました（' + soldSkus.join(', ') + '）。15分後に自動で再試行します。続く場合はClaudeに「サイトを' + soldSkus.join('・') + 'でSOLDに」と頼んでください');
        }
      } else {
        sw_log_(opt.label, 'サイトSOLD化', soldSkus.join(','), '（dryRunのため書き込みなし）', 'DRYRUN', '');
      }
    }

    // ---- エラー・通知・処理済み ----
    result.errors.forEach(function (e) { sw_log_(opt.label, 'エラー', '', e.kind, 'ERROR', e.text); });
    if (!opt.dryRun) {
      var sent = true;
      if (result.notices.length) {
        try { sw_notify_('小判鮫 在庫見張り', result.notices.join('\n\n')); }
        catch (e) { sent = false; sw_log_(opt.label, '通知', '', '通知に失敗（次回もう一度送ります）', 'ERROR', String(e)); }
      }
      if (sent) {   // 通知が届いてから処理済み・シート更新・検索開始時刻の更新
        pendingDone.forEach(function (d) { sw_markDone_(d[0], d[1]); });
        pendingSheet.forEach(function (d) { sw_setOnMercari_(d[0], d[1]); });
        if (sqScanOk) props.setProperty('SW_LAST_SQ_CHECK', new Date(startedAt.getTime() - 5 * 60000).toISOString()); // 5分重ねて取りこぼし防止（重複は処理済みで防ぐ）
      }
      var realErrors = result.errors.filter(function (e) { return e.kind !== 'sq-token' && e.kind !== 'mail-parse'; });   // mail-parse は上の通知で知らせ済み
      realErrors.forEach(function (e) { sw_notifyErrorThrottled_(e.kind, e.text); });
      if (sent) props.setProperty('SW_LAST_WATCH_OK', startedAt.toISOString());
    }
  } finally {
    lock.releaseLock();
  }
  result.errors = result.errors.map(function (e) { return e.text; });
  return result;
}

/** メルカリで売れた後に Square 在庫が0になった時の文（手で0にしたのか、店頭でも売れたのかを確認してもらう） */
function sw_afterMercariText_(sku, name) {
  return '【確認】' + sku + ' ' + (name || '') + ' のSquare在庫が0になりました（この商品はメルカリで売約済み）\n' +
    '・龍さんが手で0にしたのなら、このメッセージは無視してOK\n▶ 店頭でも売れた場合は二重販売です。メルカリ側のお客さまへの対応が必要です';
}

/** メルカリ側の案内文 */
function sw_mercariAdvice_(t) {
  if (t && t.onMercari === 'TRUE') return '▶ メルカリに出品中です。止めてください' + (t.mercariId ? '（商品ID ' + t.mercariId + '）' : '') + '。止めたら見張り対象の「メルカリ出品中」をFALSEに';
  if (t && t.onMercari === 'FALSE') return '（メルカリには出していない登録です）';
  return '▶ メルカリに出していたら止めてください（見張り対象に未登録）';
}

// ===== 毎朝の健康チェック（書き換えはしない） ======================================

function sw_health_(opt) {
  SW_MEMO = { ss: null, done: null };
  var props = PropertiesService.getScriptProperties();
  if (props.getProperty('SW_KILL') === 'true') {
    if (!opt.dryRun) sw_notifyDirect_('小判鮫 在庫見張り：停止中', 'SW_KILL=true のため見張りと毎朝チェックは止まっています。再開する時は SW_KILL を false に。');
    return { stopped: true };
  }
  var issues = [], checked = [];
  var prod;
  try { prod = sw_ghGetProducts_(); } catch (e) { issues.push('GitHubの商品データが読めません: ' + e); }
  var targets = sw_readTargets_();

  if (prod) {
    prod.products.filter(function (p) { return p.published; }).forEach(function (p) {
      var url = SW.SITE_BASE + '/journal/' + p.slug + '/';
      try {
        var res = UrlFetchApp.fetch(url + '?t=' + Date.now(), { muteHttpExceptions: true, followRedirects: true });
        var code = res.getResponseCode(), html = res.getContentText('UTF-8');
        if (code !== 200) { issues.push(p.sku + ' のページが開きません（HTTP ' + code + '）'); return; }
        if (p.status === 'sold') {
          if (html.indexOf('SOLD OUT') < 0) issues.push(p.sku + ' はデータ上SOLDなのに、ページがSOLD表示になっていません（自動生成の遅れ・失敗の可能性）');
        } else {
          var sq = p.links && p.links.square;
          if (!sq) issues.push(p.sku + ' に購入リンクがありません');
          else if (html.indexOf('href="' + sq + '"') < 0) issues.push(p.sku + ' の購入ボタンのリンク先がデータ（' + sq + '）と一致しません');
        }
        checked.push(p.sku);
      } catch (e) { issues.push(p.sku + ' のページ確認でエラー: ' + e); }
    });
  }

  if (props.getProperty('SQUARE_ACCESS_TOKEN')) {
    var skus = {};
    if (prod) prod.products.forEach(function (p) { if (p.sku && p.published) skus[p.sku] = true; });
    Object.keys(targets).forEach(function (s) { skus[s] = true; });
    Object.keys(skus).forEach(function (sku) {
      try {
        var v = sw_sqFindVariation_(sku);
        var p = prod && prod.products.filter(function (x) { return x.sku === sku; })[0];
        var t = targets[sku];
        if (!v) { if (p && p.published && p.status !== 'sold') issues.push(sku + ' はサイト販売中なのにSquareに見つかりません'); return; }
        var qty = sw_sqQty_(v.id);
        if (qty === null) { issues.push(sku + ' はSquareで在庫数が未登録です（在庫の追跡をONに）'); return; }
        if (p && p.published && p.status !== 'sold' && qty <= 0) issues.push(sku + ' はSquare在庫0なのにサイトは販売中です（15分おきの見張りがSOLDにするはず。続くならClaudeへ）');
        if (p && p.published && p.status === 'sold' && qty > 0) issues.push(sku + ' はサイトではSOLDなのにSquare在庫が' + qty + '（再入荷？手で確認してください）');
        if (t && t.onMercari === 'TRUE' && qty <= 0) issues.push(sku + ' はSquare在庫0なのにメルカリ出品中の登録 → メルカリを止めて、見張り対象の「メルカリ出品中」をFALSEに');
      } catch (e) { issues.push(sku + ' のSquare在庫確認でエラー: ' + e); }
    });
  } else {
    issues.push('SQUARE_ACCESS_TOKEN が未設定のため、Squareとの照合ができません');
  }

  var pend = sw_pendingSold_();
  if (pend.length) issues.push('サイトのSOLD化が保留のままです: ' + pend.join(', '));
  var last = props.getProperty('SW_LAST_WATCH_OK');
  var hasTrigger = ScriptApp.getProjectTriggers().some(function (t) { return t.getHandlerFunction() === 'sw_watch'; });
  if (!hasTrigger) issues.push('15分おきの見張り（sw_watch）のトリガーがありません');
  else if (!last || (Date.now() - new Date(last).getTime()) > SW.WATCH_STALE_MIN * 60000) {
    issues.push('15分おきの見張りが ' + (last ? Math.round((Date.now() - new Date(last).getTime()) / 60000) + '分' : '一度も') + ' 正常終了していません');
  }
  var note = 'メルカリの公開状態はGASから読めないため、この点検には含めていません（見張り対象シートの登録で判断）';
  sw_log_('health', '毎朝チェック', '', checked.length + 'ページ確認・異常' + issues.length + '件', issues.length ? '異常あり' : '異常なし', issues.join(' / ') + ' ※' + note);
  if (!opt.dryRun && issues.length) sw_notify_('小判鮫 サイト毎朝チェック：要確認', issues.map(function (s) { return '・' + s; }).join('\n'));
  return { checked: checked, issues: issues, note: note };
}

// ===== Square ====================================================================

function sw_sq_(method, path, body) {
  var token = PropertiesService.getScriptProperties().getProperty('SQUARE_ACCESS_TOKEN');
  if (!token) throw new Error('SQUARE_ACCESS_TOKEN 未設定');
  var opt = { method: method, muteHttpExceptions: true, contentType: 'application/json',
    headers: { Authorization: 'Bearer ' + token, 'Square-Version': SW.SQ_VERSION } };
  if (body) opt.payload = JSON.stringify(body);
  var res = UrlFetchApp.fetch(SW.SQ_API + path, opt);
  var code = res.getResponseCode(), text = res.getContentText();
  if (code >= 300) throw new Error('Square ' + method.toUpperCase() + ' ' + path + ' → HTTP ' + code + ' ' + text.slice(0, 300));
  return text ? JSON.parse(text) : {};
}

/** since 以降に更新され、在庫数が0以下になったバリエーション一覧 */
function sw_sqZeroSince_(since) {
  var counts = [], cursor = null, guard = 0;
  do {
    var body = { location_ids: [SW.SQ_LOCATION_ID], states: ['IN_STOCK'], updated_after: since.toISOString(), limit: 1000 };
    if (cursor) body.cursor = cursor;
    var r = sw_sq_('post', '/inventory/counts/batch-retrieve', body);
    (r.counts || []).forEach(function (c) { if (c.catalog_object_type === 'ITEM_VARIATION' || !c.catalog_object_type) counts.push(c); });
    cursor = r.cursor; guard++;
  } while (cursor && guard < 20);
  var zero = counts.filter(function (c) { return Number(c.quantity) <= 0; });
  if (!zero.length) return [];
  var info = sw_sqVariationInfo_(zero.map(function (c) { return c.catalog_object_id; }));
  return zero.map(function (c) {
    var i = info[c.catalog_object_id] || {};
    return { variationId: c.catalog_object_id, calculatedAt: c.calculated_at, sku: i.sku || '', name: i.name || '' };
  });
}

/** variationId → {sku, name} */
function sw_sqVariationInfo_(ids) {
  var out = {};
  for (var i = 0; i < ids.length; i += 500) {
    var r = sw_sq_('post', '/catalog/batch-retrieve', { object_ids: ids.slice(i, i + 500), include_related_objects: true });
    var itemNames = {};
    (r.related_objects || []).forEach(function (o) { if (o.type === 'ITEM' && o.item_data) itemNames[o.id] = o.item_data.name; });
    (r.objects || []).forEach(function (o) {
      if (o.type !== 'ITEM_VARIATION' || !o.item_variation_data) return;
      var d = o.item_variation_data;
      out[o.id] = { sku: d.sku || '', name: itemNames[d.item_id] || d.name || '' };
    });
  }
  return out;
}

/** SKU → {id}（見つからなければ null）。見つかった時は6時間、見つからない時は30分キャッシュ */
function sw_sqFindVariation_(sku) {
  var cache = CacheService.getScriptCache(), ck = 'sw_var_' + sku;
  var hit = cache.get(ck);
  if (hit) return hit === 'NONE' ? null : JSON.parse(hit);
  var r = sw_sq_('post', '/catalog/search', { object_types: ['ITEM_VARIATION'], query: { exact_query: { attribute_name: 'sku', attribute_value: sku } }, limit: 10 });
  var objs = (r.objects || []).filter(function (o) { return !o.is_deleted; });
  if (objs.length > 1) throw new Error('SKU ' + sku + ' がSquareに' + objs.length + '件あり特定できません');
  var v = objs.length === 1 ? { id: objs[0].id } : null;
  cache.put(ck, v ? JSON.stringify(v) : 'NONE', v ? 6 * 3600 : 1800);
  return v;
}

/** 在庫数（この店舗・IN_STOCK）。在庫の記録そのものが無い時は null（＝0とは区別する） */
function sw_sqQty_(variationId) {
  var r = sw_sq_('post', '/inventory/counts/batch-retrieve', { catalog_object_ids: [variationId], location_ids: [SW.SQ_LOCATION_ID], states: ['IN_STOCK'] });
  var c = (r.counts || [])[0];
  return c ? Number(c.quantity) : null;
}

/** メルカリで売れた商品の Square 在庫を0にする（スイッチONの時だけ）。{zeroed: Square在庫が0だと確認できたか, line: 通知用の1行} */
function sw_sqZeroForMercari_(sku, idemKey, opt) {
  var props = PropertiesService.getScriptProperties();
  if (!props.getProperty('SQUARE_ACCESS_TOKEN')) return { zeroed: false, line: '▶ Squareの在庫を0にしてください（Squareトークン未設定）' };
  try {
    var v = sw_sqFindVariation_(sku);
    if (!v) return { zeroed: true, line: '・Squareには未登録の商品です（店頭・サイトでは売っていない）' };
    var qty = sw_sqQty_(v.id);
    if (qty === null) return { zeroed: false, line: '▶ Squareで在庫数が未登録の商品です。店頭で売らないよう注意してください' };
    if (qty <= 0) return { zeroed: true, line: '・Squareの在庫はすでに0です' };
    if (props.getProperty('SW_ENABLE_SQUARE_WRITE') !== 'true') return { zeroed: false, line: '▶ Squareの在庫を0にしてください（現在' + qty + '。自動書き込みはOFF）' };
    if (opt.dryRun) return { zeroed: false, line: '・（dryRun）ONならSquareの在庫を' + qty + '→0にします' };
    sw_sq_('post', '/inventory/changes/batch-create', {
      idempotency_key: 'sw-mercari-' + idemKey + '-' + Date.now(),   // 在庫を0にする操作は繰り返しても無害
      changes: [{ type: 'PHYSICAL_COUNT', physical_count: { catalog_object_id: v.id, state: 'IN_STOCK', location_id: SW.SQ_LOCATION_ID, quantity: '0', occurred_at: new Date().toISOString() } }]
    });
    var after = sw_sqQty_(v.id);
    sw_log_(opt.label, 'Square在庫0に変更', sku, 'メルカリ売約のため', after !== null && after <= 0 ? 'OK' : 'NG', 'before=' + qty + ' after=' + after);
    var done0 = after !== null && after <= 0;
    return { zeroed: done0, line: done0 ? '・Squareの在庫を自動で0にしました（店頭・サイトの決済は止まりました）' : '▶ Squareの在庫を0にできませんでした（' + after + '）。手で0にしてください' };
  } catch (e) {
    sw_log_(opt.label, 'Square照合エラー', sku, 'メルカリ売約の処理中', 'ERROR', String(e));
    return { zeroed: false, line: '▶ Squareの在庫を手で0にしてください（自動処理でエラー: ' + String(e).slice(0, 150) + '）' };
  }
}


// ===== メルカリ（Gmail） =========================================================

function sw_mailQuery_(newerThan) {
  return 'from:' + SW.MERCARI_FROM + ' subject:' + SW.MERCARI_SUBJECT + ' newer_than:' + newerThan;
}

/** 購入メールを読む。{mails:[{messageId, items:[商品名...], code, orderId, verified}], unparsed:[{messageId, subject}]} */
function sw_readMercariMails_(newerThan) {
  var out = { mails: [], unparsed: [] };
  var days = Number(String(newerThan).replace(/\D/g, '')) || 7;
  var minTime = Date.now() - days * 86400000;
  GmailApp.search(sw_mailQuery_(newerThan), 0, 100).forEach(function (th) {
    th.getMessages().forEach(function (msg) {
      if (msg.getDate().getTime() < minTime) return;                 // スレッド内の古いメールは対象外
      if (sw_fromAddress_(msg.getFrom()) !== SW.MERCARI_FROM) return;
      var subject = msg.getSubject();
      if (subject.indexOf('発送をお願いします') < 0) return;
      var p = sw_parseMercariMail_(msg.getPlainBody(), subject);
      if (!p.items.length) { out.unparsed.push({ messageId: msg.getId(), subject: subject }); return; }
      p.messageId = msg.getId();
      p.verified = sw_isMercariSigned_(sw_firstHeader_(msg.getRawContent(), 'Authentication-Results'));
      out.mails.push(p);
    });
  });
  return out;
}

/** 送信元の署名が本物か（純粋関数）。実物のメールは dkim=pass header.i=@mercari-shops.com と dmarc=pass header.from=mercari-shops.com */
function sw_isMercariSigned_(authResults) {
  var a = String(authResults || '').toLowerCase().replace(/\s+/g, ' ').trim();
  if (a.indexOf('mx.google.com;') !== 0) return false;                        // Gmail自身が付けた判定だけを信じる
  return /dmarc=pass[^;]*header\.from=mercari-shops\.com(?![\w.-])/.test(a) &&
         /dkim=pass[^;]*header\.i=@mercari-shops\.com(?![\w.-])/.test(a);
}

/** メールの生データから、指定ヘッダーの「一番上」（＝最後に受け取ったGmail自身が付けたもの）を取り出す（純粋関数） */
function sw_firstHeader_(raw, name) {
  var head = String(raw || '').split(/\r?\n\r?\n/)[0].replace(/\r?\n[ \t]+/g, ' ');   // 折り返しを戻す
  var lines = head.split(/\r?\n/), key = name.toLowerCase() + ':';
  for (var i = 0; i < lines.length; i++) if (lines[i].toLowerCase().indexOf(key) === 0) return lines[i].slice(key.length).trim();
  return '';
}

/** 差出人のアドレス部分（純粋関数） */
function sw_fromAddress_(from) {
  var m = String(from || '').match(/<([^>]+)>/);
  return (m ? m[1] : String(from || '')).trim().toLowerCase();
}

/** 購入メール本文から 商品名（複数可）・商品管理コード・注文番号 を取り出す（純粋関数） */
function sw_parseMercariMail_(body, subject) {
  body = String(body || '').replace(/\r/g, '');
  var items = [];
  var re = /商品名\s*[:：]\s*(.+)/g, m;
  while ((m = re.exec(body)) !== null) { var t = m[1].trim(); if (t) items.push(t); }
  if (!items.length) {
    var s = (String(subject || '').match(/「(.+)」の発送をお願いします/) || [])[1];
    if (s) items.push(s.trim());
  }
  var code = (body.match(/商品管理コード\s*[:：]\s*([A-Za-z0-9\-_]+)/) || [])[1];
  var orderId = (body.match(/注文番号\s*[:：]\s*(\S+)/) || [])[1];
  return { items: items, title: items[0] || '', code: code || '', orderId: orderId || '' };
}

/** メールの商品 → SKU（純粋関数）。targets = {sku: {mercariTitle, onMercari}} */
function sw_matchSku_(mail, targets) {
  if (mail.code && targets[mail.code]) return { sku: mail.code, how: 'code' };
  if (mail.code && /^K\d+$/.test(mail.code)) return { sku: mail.code, how: 'code(未登録)' };
  var norm = function (s) { return String(s || '').replace(/\s+/g, ' ').trim(); };
  var hits = Object.keys(targets).filter(function (k) { return norm(targets[k].mercariTitle) === norm(mail.title); });
  if (hits.length === 1) return { sku: hits[0], how: 'title' };
  if (hits.length > 1) {
    var listed = hits.filter(function (k) { return targets[k].onMercari === 'TRUE'; });   // メルカリに出しているのが1つだけならそれ
    if (listed.length === 1) return { sku: listed[0], how: 'title+出品中' };
    return { sku: '', how: 'ambiguous', candidates: hits };
  }
  return { sku: '', how: 'unknown' };
}

// ===== GitHub（公式サイトの商品データ） ==========================================

function sw_gh_(method, path, body) {
  var token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  if (!token) throw new Error('GITHUB_TOKEN 未設定');
  var opt = { method: method, muteHttpExceptions: true, contentType: 'application/json',
    headers: { Authorization: 'Bearer ' + token, Accept: 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28' } };
  if (body) opt.payload = JSON.stringify(body);
  var res = UrlFetchApp.fetch('https://api.github.com/repos/' + SW.GH_OWNER + '/' + SW.GH_REPO + path, opt);
  var code = res.getResponseCode(), text = res.getContentText();
  if (code >= 300) { var err = new Error('GitHub ' + method.toUpperCase() + ' ' + path + ' → HTTP ' + code + ' ' + text.slice(0, 300)); err.httpCode = code; throw err; }
  return JSON.parse(text);
}

function sw_ghGetProducts_() {
  var r = sw_gh_('get', '/contents/' + SW.PRODUCTS_PATH + '?ref=' + SW.GH_BRANCH);
  var json = Utilities.newBlob(Utilities.base64Decode(String(r.content).replace(/\n/g, ''))).getDataAsString('UTF-8');
  return { sha: r.sha, products: JSON.parse(json) };
}

/** products.json を書き換えてコミット（競合時は読み直して再試行）。mutate(products) は変更したSKU配列を返す */
function sw_ghUpdateProducts_(mutate, message) {
  for (var attempt = 0; attempt < 3; attempt++) {
    var cur = sw_ghGetProducts_();
    var changed = mutate(cur.products);
    if (!changed.length) return '(変更なし)';
    try {
      var r = sw_gh_('put', '/contents/' + SW.PRODUCTS_PATH, {
        message: message(changed),
        content: Utilities.base64Encode(Utilities.newBlob(JSON.stringify(cur.products, null, 1) + '\n').getBytes()),
        sha: cur.sha, branch: SW.GH_BRANCH
      });
      return r.commit && r.commit.sha;
    } catch (e) {
      if ((e.httpCode === 409 || e.httpCode === 422) && attempt < 2) { Utilities.sleep(2000); continue; }
      throw e;
    }
  }
}

function sw_ghMarkSold_(skus) {
  return sw_ghUpdateProducts_(function (ps) { return sw_applySold_(ps, skus); },
    function (ch) { return '在庫見張り：' + ch.join('・') + ' をSOLDに（60_stock_watch_v1）'; });
}

/** products配列の該当SKUを sold にする（純粋関数）。変更したSKUの配列を返す */
function sw_applySold_(products, skus) {
  var changed = [];
  products.forEach(function (p) {
    if (p.sku && skus.indexOf(p.sku) >= 0 && p.status !== 'sold') { p.status = 'sold'; changed.push(p.sku); }
  });
  return changed;
}

function sw_pendingSold_() {
  var v = PropertiesService.getScriptProperties().getProperty('SW_PENDING_SOLD');
  return v ? v.split(',').filter(function (s) { return !!s; }) : [];
}
function sw_setPendingSold_(skus) { PropertiesService.getScriptProperties().setProperty('SW_PENDING_SOLD', skus.join(',')); }

// ===== 通知 ======================================================================

/** LINE（設定があれば）→ ダメならメール。どちらも失敗したら例外を投げる */
function sw_notify_(title, text) {
  var r = sw_notifyDirect_(title, text);
  sw_log_('notify', r.channel, '', title, 'OK', r.detail);
}

/** シートを使わない通知（見張りシートが壊れている時にも使う） */
function sw_notifyDirect_(title, text) {
  var props = PropertiesService.getScriptProperties();
  var tok = props.getProperty('LINE_CHANNEL_ACCESS_TOKEN'), to = props.getProperty('LINE_TO_USER_ID');
  var body = title + '\n' + text, lineFail = '';
  if (tok && to) {
    try {
      var res = UrlFetchApp.fetch('https://api.line.me/v2/bot/message/push', {
        method: 'post', muteHttpExceptions: true, contentType: 'application/json',
        headers: { Authorization: 'Bearer ' + tok },
        payload: JSON.stringify({ to: to, messages: sw_chunks_(body, 4900, 5).map(function (t) { return { type: 'text', text: t }; }) })
      });
      var code = res.getResponseCode();
      if (code === 200) return { channel: 'LINE', detail: 'HTTP 200' };
      lineFail = 'LINE送信失敗 HTTP ' + code + ' ' + res.getContentText().slice(0, 200);
    } catch (e) { lineFail = 'LINE送信で例外: ' + e; }
  }
  var me = Session.getEffectiveUser().getEmail();
  MailApp.sendEmail(me, '【' + title + '】', (lineFail ? '（' + lineFail + '。代わりにメールで送ります）\n\n' : '') + body);   // 失敗時は例外が上に伝わる
  return { channel: 'メール', detail: me + (lineFail ? ' / ' + lineFail : '') };
}

/** 長文を分割（LINEは1通5000字・1回5通まで）。入りきらない分は最後に「続きは見張りシート」（純粋関数） */
function sw_chunks_(text, size, max) {
  var out = [];
  for (var i = 0; i < text.length && out.length < max; i += size) out.push(text.slice(i, i + size));
  if (text.length > size * max) out[max - 1] = out[max - 1].slice(0, size - 40) + '\n…（続きは見張りシートの「ログ」）';
  return out;
}

/** エラー通知：同じ種類のエラーは1時間に1回まで（送れた時だけ印を付ける） */
function sw_notifyErrorThrottled_(kind, text) {
  var cache = CacheService.getScriptCache(), key = 'sw_err_' + kind;
  if (cache.get(key)) return;
  try {
    sw_notify_('小判鮫 在庫見張り：エラー', text + '\n（同じ種類のエラー通知は1時間に1回まで。詳細は見張りシートの「ログ」）');
    cache.put(key, '1', 3600);
  } catch (e) { sw_log_('notify', 'エラー通知', '', kind, 'ERROR', '通知自体に失敗: ' + e); }
}

// ===== シート（ログ・見張り対象・処理済み） ========================================

/** 見張りシート。create=true（sw_setupだけ）の時は無ければ作る。それ以外で開けなければ例外（黙って作り直さない） */
function sw_sheet_(create) {
  if (SW_MEMO.ss) return SW_MEMO.ss;
  var props = PropertiesService.getScriptProperties();
  var id = props.getProperty('SW_SHEET_ID');
  var ss = null;
  if (id) {
    try { ss = SpreadsheetApp.openById(id); }
    catch (e) { throw new Error('見張りシート（SW_SHEET_ID=' + id + '）を開けません: ' + e); }
  } else if (create) {
    ss = SpreadsheetApp.create(SW.SHEET_NAME);
    props.setProperty('SW_SHEET_ID', ss.getId());
  } else {
    throw new Error('見張りシートがまだありません。先に sw_setup を実行してください');
  }
  [['見張り対象', SW_TARGET_HEADER], ['ログ', SW_LOG_HEADER], ['処理済み', SW_DONE_HEADER]].forEach(function (d) {
    var sh = ss.getSheetByName(d[0]) || ss.insertSheet(d[0]);
    if (sh.getLastRow() === 0) { sh.appendRow(d[1]); sh.setFrozenRows(1); }
  });
  var def = ss.getSheetByName('シート1') || ss.getSheetByName('Sheet1');
  if (def && ss.getSheets().length > 1) ss.deleteSheet(def);
  SW_MEMO.ss = ss;
  return ss;
}

function sw_readTargets_() {
  var sh = sw_sheet_().getSheetByName('見張り対象');
  var out = {};
  if (sh.getLastRow() < 2) return out;
  sh.getRange(2, 1, sh.getLastRow() - 1, SW_TARGET_HEADER.length).getValues().forEach(function (r) {
    var sku = String(r[0]).trim();
    if (!sku) return;
    out[sku] = { memo: r[1], mercariTitle: String(r[2]), mercariId: String(r[3]), onMercari: String(r[4]).toUpperCase() };
  });
  return out;
}

function sw_setOnMercari_(sku, val) {
  var sh = sw_sheet_().getSheetByName('見張り対象');
  if (sh.getLastRow() < 2) return;
  var col = sh.getRange(2, 1, sh.getLastRow() - 1, 1).getValues();
  for (var i = 0; i < col.length; i++) {
    if (String(col[i][0]).trim() === sku) { sh.getRange(i + 2, 5, 1, 2).setValues([[val, sw_now_()]]); return; }
  }
}

function sw_log_(run, kind, sku, content, result, detail) {
  try {
    sw_sheet_().getSheetByName('ログ').appendRow([sw_now_(), run, kind, sw_safe_(sku), sw_safe_(content), result, sw_safe_(detail)]);
  } catch (e) { Logger.log('ログ書き込み失敗: ' + e + ' / ' + [run, kind, sku, content, result, detail].join(' | ')); }
}

function sw_isDone_(key) {
  if (!SW_MEMO.done) {
    var sh = sw_sheet_().getSheetByName('処理済み');
    SW_MEMO.done = {};
    if (sh.getLastRow() >= 2) sh.getRange(2, 1, sh.getLastRow() - 1, 1).getValues().forEach(function (r) { SW_MEMO.done[r[0]] = true; });
  }
  return !!SW_MEMO.done[key];
}

function sw_markDone_(key, memo) {
  if (sw_isDone_(key)) return;
  sw_sheet_().getSheetByName('処理済み').appendRow([key, sw_now_(), sw_safe_(memo)]);
  SW_MEMO.done[key] = true;
}

/** シートに書く文字列が数式として解釈されないようにする（外部由来の商品名など） */
function sw_safe_(v) {
  var s = String(v === undefined || v === null ? '' : v);
  return /^[=+\-@]/.test(s) ? "'" + s : s;
}

function sw_now_() { return Utilities.formatDate(new Date(), SW.TZ, 'yyyy-MM-dd HH:mm:ss'); }

// ===== テスト用（龍さんが確認時に1回ずつ実行） =====================================

/** 通知が届くかのテスト（1通だけ送る） */
function sw_testNotify() {
  SW_MEMO = { ss: null, done: null };
  sw_notify_('小判鮫 在庫見張り：テスト', 'これは在庫見張り（60番）のテスト通知です。届いていれば通知の経路はOKです。');
}

/** テスト用ダミー WATCHTEST を SOLD にして、ページがSOLD表示になるのを確認 → 必ず元に戻す（全体で約5分以内） */
function sw_testSiteSold() {
  SW_MEMO = { ss: null, done: null };
  var t0 = Date.now(), url = SW.SITE_BASE + '/journal/watch-test-0000/';
  var page = function () { return UrlFetchApp.fetch(url + '?t=' + Date.now(), { muteHttpExceptions: true }).getContentText('UTF-8'); };
  var cur = sw_ghGetProducts_();
  var t = cur.products.filter(function (p) { return p.sku === 'WATCHTEST'; })[0];
  if (!t) throw new Error('テスト用ダミー WATCHTEST が data/products.json にありません（Claudeに追加を依頼）');
  if (t.status === 'sold') sw_setWatchTest_('available');   // 前回の失敗で sold のまま残っていたら戻す
  var log = [];
  // 開始前に「SOLD表示でない」ことを確認（前回の残りで誤って合格にしない）。最大90秒待つ
  while (page().indexOf('SOLD OUT') >= 0) {
    if (Date.now() - t0 > 90000) {
      log.push('開始前のページがSOLD表示のまま（前回のテストの反映待ち）。数分後にやり直してください');
      sw_log_('test', 'サイトSOLDテスト', 'WATCHTEST', log.join(' → '), 'NG', url); Logger.log(log.join('\n')); return false;
    }
    Utilities.sleep(10000);
  }
  var ok = false, waited = 0;
  try {
    sw_setWatchTest_('sold'); log.push('WATCHTEST を sold にコミット');
    var t1 = Date.now();
    while (!ok && Date.now() - t0 < 4 * 60000) {   // 実行上限（6分）に掛からないよう、全体で4分まで
      Utilities.sleep(10000);
      ok = page().indexOf('SOLD OUT') >= 0;
    }
    waited = Math.round((Date.now() - t1) / 1000);
    log.push(ok ? 'ページがSOLD表示になった（自動生成→公開までOK・約' + waited + '秒）' : '時間内にSOLD表示にならない（GitHub Actions か Cloudflare を確認。数分後に sw_testSiteSold をもう一度）');
  } finally {
    try { sw_setWatchTest_('available'); log.push('WATCHTEST を available に戻した'); }
    catch (e) {
      log.push('WATCHTEST を元に戻せなかった: ' + e);
      try { sw_notifyDirect_('小判鮫 在庫見張り：テストの後片付けに失敗', 'WATCHTEST（非公開のテスト用ダミー）が sold のままです。sw_testSiteSold をもう一度実行すると戻ります。\n' + e); } catch (e2) { Logger.log(e2); }
    }
    sw_log_('test', 'サイトSOLDテスト', 'WATCHTEST', log.join(' → '), ok ? 'OK' : 'NG', url);
    Logger.log(log.join('\n'));
  }
  return ok;
}

function sw_setWatchTest_(status) {
  return sw_ghUpdateProducts_(function (ps) {
    var ch = [];
    ps.forEach(function (p) { if (p.sku === 'WATCHTEST' && p.status !== status) { p.status = status; ch.push(p.sku); } });
    return ch;
  }, function () { return '在庫見張りテスト：WATCHTEST を ' + status + ' に'; });
}

// ===== トリガー（龍さんが最後に実行） ============================================

/** トリガー2本を設定。同時に「今あるメルカリ購入メール」と「現在時刻」を起点にして、過去分を一斉通知しない */
function sw_installTriggers() {
  SW_MEMO = { ss: null, done: null };
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(30000)) throw new Error('見張りが実行中です。1分後にもう一度 sw_installTriggers を実行してください');
  try {
  var first = !PropertiesService.getScriptProperties().getProperty('SW_LAST_WATCH_OK');
  var n = 0, names = [];
  if (first) {   // 初回だけ：設置前のメール・SOLD済み商品は通知しない。再開時は止まっていた間の出来事を拾うので印を付けない
  var ms = sw_readMercariMails_(SW.MAIL_NEWER_THAN);
  ms.mails.forEach(function (m) { m.items.forEach(function (title, idx) { sw_markDone_('mail:' + m.messageId + ':' + idx, '設置前のメール（通知しない）: ' + title); names.push(title); n++; }); });
  ms.unparsed.forEach(function (u) { sw_markDone_('mailbad:' + u.messageId, '設置前のメール（通知しない）'); });
  try { sw_ghGetProducts_().products.forEach(function (p) { if (p.sku && p.status === 'sold') sw_markDone_('site0:' + p.sku, '設置前にSOLD済み（通知しない）'); }); }
  catch (e) { throw new Error('GitHubの商品データが読めないため設置を中止しました: ' + e); }
  PropertiesService.getScriptProperties().setProperty('SW_LAST_SQ_CHECK', new Date().toISOString());
  }
  sw_removeTriggers();
  ScriptApp.newTrigger('sw_watch').timeBased().everyMinutes(15).create();
  ScriptApp.newTrigger('sw_dailyHealth').timeBased().atHour(9).nearMinute(30).everyDays(1).inTimezone(SW.TZ).create();
  sw_log_('setup', 'トリガー', '', '15分おき＋毎朝9:30 を設定（' + (first ? '初回：設置前のメール' + n + '件は通知対象外' : '再開：止まっていた間の出来事は次の見張りで拾う') + '）', 'OK', names.join(' / '));
  Logger.log('トリガーを設定しました：sw_watch（15分おき）／sw_dailyHealth（毎朝9:30頃）。設置前のメール' + n + '件: ' + names.join(' / '));
  } finally { lock.releaseLock(); }
}

function sw_removeTriggers() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    var f = t.getHandlerFunction();
    if (f === 'sw_watch' || f === 'sw_dailyHealth') ScriptApp.deleteTrigger(t);
  });
}
