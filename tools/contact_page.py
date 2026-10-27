# -*- coding: utf-8 -*-
"""お問い合わせページ /contact/（衣装提供・撮影・取材など）
2026-10-27 龍さん決定：A 自前フォーム＋専用GAS／通知は Gmail だけ／ご用件は5つ

しくみ
- このページはフォームの見た目だけ。送信先は専用の GAS（69番「問い合わせ受付」・単独のプロジェクト）。
- CONTACT_URL（build_site.py の上のほう）が空のあいだは、フォームの代わりに「メールで問い合わせる」ボタンを出す。
  → GAS の設置前にこのページを公開しても壊れない。
- 送信内容（お客さまの名前・メール）は GitHub には一切入らない（GAS→スプレッドシート＋Gmail にだけ届く）。
"""
import json
from urllib.parse import quote

KINDS = ['衣装提供・リース', '撮影・ロケ地のご相談', '取材・メディア掲載', '法人・コラボのご相談', 'その他']

CONTACT_CSS = '''
.cform{margin-top:20px;display:grid;gap:18px}
.cform label{display:block;font-size:13px;letter-spacing:.06em;margin-bottom:6px}
.cform .req{font-size:11px;margin-left:6px;padding:1px 6px;border:1px solid var(--kin)}
.cform .opt{font-size:11px;margin-left:6px;color:var(--usu)}
.cform input[type=text],.cform input[type=email],.cform input[type=tel],.cform select,.cform textarea{width:100%;min-height:48px;background:var(--sumi);color:var(--kinari);border:1px solid var(--kin);border-radius:0;padding:10px 12px;font:inherit;font-size:16px}
.cform textarea{min-height:180px;resize:vertical;line-height:1.7}
.cform .hint{font-size:12px;color:var(--usu);margin-top:4px}
.cform .agree{display:flex;gap:10px;align-items:flex-start;font-size:14px}
.cform .agree input{width:20px;height:20px;margin-top:3px;flex:none}
.cform .hp{position:absolute;left:-9999px;width:1px;height:1px;overflow:hidden}
.cform button[disabled]{opacity:.5;cursor:wait}
.cmsg{margin-top:16px;padding:14px 16px;border:1px solid var(--kin);font-size:14px}
.cmsg.err{border-color:var(--sold);color:var(--sold)}
.cdone h2{margin-top:0}
'''

# 送る前に画面側で確かめる（本当の確認は GAS 側でもう一度やる）
CONTACT_JS = r'''
(function(){
var U=__URL__,f=document.getElementById('cform'),m=document.getElementById('cmsg'),b=document.getElementById('csend'),t0=Date.now();
if(!f)return;
function show(txt,err){m.hidden=false;m.className='cmsg'+(err?' err':'');m.textContent=txt;m.scrollIntoView({block:'center'});}
f.addEventListener('submit',function(e){
  e.preventDefault();
  if(!f.reportValidity())return;
  var d={};new FormData(f).forEach(function(v,k){d[k]=String(v).trim();});
  d.t=Date.now()-t0;d.page=location.pathname;
  b.disabled=true;b.textContent='送信しています…';
  fetch(U,{method:'POST',body:JSON.stringify(d)}).then(function(r){return r.json();}).then(function(j){
    if(j&&j.ok){f.hidden=true;m.hidden=true;var dn=document.getElementById('cdone');dn.hidden=false;if(j.ack===false){var a=document.getElementById('cack');if(a)a.textContent='受付の控えメールは、いまはお送りできませんでした。お問い合わせは届いていますので、担当からのご返信をお待ちください。';}dn.scrollIntoView();return;}
    show((j&&j.message)||'送信できませんでした。時間をおいてもう一度お試しください。',true);
    b.disabled=false;b.textContent='送信する';
  }).catch(function(){
    show('送信できたか確認できませんでした。お手数ですが、'+__MAIL__+' まで同じ内容をメールでお送りください。',true);
    b.disabled=false;b.textContent='送信する';
  });
});
})();
'''


def build_contact(write, head, foot, esc, SHOP, CONTACT_URL):
    mail = SHOP['email']
    subject = '【お問い合わせ】衣装提供・撮影・取材のご相談'
    mailto = f'mailto:{mail}?subject=' + quote(subject)
    title = 'お問い合わせ（衣装提供・撮影・取材）｜古着屋 小判鮫'
    desc = '川越・元町の古着屋 小判鮫へのお問い合わせ。ドラマ・映画・MV・広告・雑誌への衣装提供（リース）、店内での撮影、取材、法人・コラボのご相談をこのページから受け付けています。'
    opts = '<option value="">選んでください</option>' + ''.join(f'<option>{esc(k)}</option>' for k in KINDS)

    intro = f'''<h1>お問い合わせ</h1>
  <p>ドラマ・映画・MV・広告・雑誌などへの衣装提供（リース）、店内での撮影、取材、法人・コラボのご相談を受け付けています。内容を確認して、メールでご返信します。</p>
  <p class="hint" style="color:var(--usu);font-size:13px;margin-top:8px">小判鮫の商品はすべて一点物です。ご希望の商品が、ご連絡のあいだに売れてしまう場合があります。商品のご質問は <a href="{SHOP['instagram']}" rel="noopener">Instagram</a> の DM でも受け付けています。</p>'''

    if CONTACT_URL:
        body = f'''<form id="cform" class="cform" novalidate>
    <div><label for="c-kind">ご用件<span class="req">必須</span></label><select id="c-kind" name="kind" required>{opts}</select></div>
    <div><label for="c-name">お名前<span class="req">必須</span></label><input id="c-name" name="name" type="text" required maxlength="60" autocomplete="name"></div>
    <div><label for="c-org">会社・団体・媒体名<span class="opt">任意</span></label><input id="c-org" name="org" type="text" maxlength="100" autocomplete="organization"></div>
    <div><label for="c-email">メールアドレス<span class="req">必須</span></label><input id="c-email" name="email" type="email" required maxlength="120" autocomplete="email" inputmode="email"></div>
    <div><label for="c-tel">電話番号<span class="opt">任意</span></label><input id="c-tel" name="tel" type="tel" maxlength="20" autocomplete="tel" inputmode="tel"></div>
    <div><label for="c-work">作品名・企画名<span class="opt">任意</span></label><input id="c-work" name="work" type="text" maxlength="100"><p class="hint">衣装提供・撮影・取材のときにお書きください。</p></div>
    <div><label for="c-date">ご希望の日程<span class="opt">任意</span></label><input id="c-date" name="date" type="text" maxlength="100"><p class="hint">例：11月10日 撮影、11月12日 返却</p></div>
    <div><label for="c-msg">ご相談の内容<span class="req">必須</span></label><textarea id="c-msg" name="message" required maxlength="2000"></textarea><p class="hint">イメージしている服・点数・使い方などをお書きください（2,000字まで）。</p></div>
    <div class="hp" aria-hidden="true"><label for="c-web">ウェブサイト</label><input id="c-web" name="website" type="text" tabindex="-1" autocomplete="off"></div>
    <div><label class="agree"><input type="checkbox" name="agree" value="yes" required><span><a href="/privacy/">プライバシーポリシー</a>に同意します</span></label></div>
    <div><button id="csend" class="btn kin" type="submit">送信する</button></div>
  </form>
  <div id="cmsg" class="cmsg" hidden role="alert"></div>
  <div id="cdone" class="cdone" hidden><h2>送信しました</h2><p>お問い合わせありがとうございます。内容を確認して、担当からご返信します。</p><p id="cack">入力いただいたメールアドレスに、受付の控えをお送りしました。</p><p class="hint" style="color:var(--usu);font-size:13px">控えのメールが届かないときは、迷惑メールのフォルダをご確認ください。</p></div>
<script>{CONTACT_JS.replace('__URL__', json.dumps(CONTACT_URL)).replace('__MAIL__', json.dumps(mail))}</script>'''
    else:
        # GAS の設置前：メールで受け付ける
        body = f'''<p style="margin-top:20px">下のボタンからメールでお問い合わせください。ご用件・お名前・作品名や企画名・ご希望の日程・ご相談の内容をお書きいただくと、ご返信が早くなります。</p>
  <p style="margin-top:16px"><a class="btn kin" href="{mailto}">メールで問い合わせる</a></p>
  <p class="hint" style="color:var(--usu);font-size:13px;margin-top:8px">宛先：{esc(mail)}</p>'''

    write('/contact/index.html', head('ja', title, desc, '/contact/') + f'''
<style>{CONTACT_CSS.strip()}</style>
<main class="wrap page">
  {intro}
  {body}
</main>
''' + foot('ja'))
