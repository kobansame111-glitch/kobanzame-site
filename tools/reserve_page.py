# -*- coding: utf-8 -*-
"""小判鮫 予約ページ v1.0（2026-11-13 新規）
※ 外枠のクラスは rsv（サイト共通の .rv は「ふわっと出る」動きで、最初は見えないため使わない）
/reserve/（予約画面）と /reserve/thanks/（支払いのあとに戻ってくる画面）を作る。

中身（コース・料金・日時・残り人数・営業時間・キャンセルの決まり）は、ページを開いたときに
サイト自動化GASのウェブアプリ（CART_ENDPOINT・65番）から読む＝店がシートを直せば、サイトを作り直さなくてもすぐ変わる。
旧予約サイト（concentsocket）の反省：休業日はそもそも選べない／営業時間は文章で出す／枠はコースの開始時刻から／
支払いは小判鮫の Square／店が自分で直せる。
予約の受付が止まっている（RV_ENABLE が true ではない）ときは「準備中」を出す。
お客さまの名前・電話・メールはこのページから GAS へ送るだけ（サイトには残さない）。
"""
import json


def _css():
    return """<style>
.rsv{max-width:720px;margin:0 auto}
.rsv h2{font-size:17px;margin:28px 0 10px;letter-spacing:.06em}
.rsv .rv-note{color:var(--usu);font-size:13px;line-height:1.7}
.rv-courses{display:grid;gap:10px}
.rv-course{display:block;border:1px solid var(--line,#ddd);padding:14px 16px;cursor:pointer;text-align:left;background:var(--sumi);color:var(--kinari);font:inherit}
.rv-course[aria-pressed="true"]{border:2px solid var(--kin);padding:13px 15px}
.rv-course b{display:block;font-size:15px}
.rv-course span{display:block;font-size:13px;color:var(--usu);margin-top:4px;line-height:1.6}
.rv-cal{border:1px solid var(--line,#ddd)}
.rv-cal-head{display:flex;justify-content:space-between;align-items:center;padding:8px 10px;border-bottom:1px solid var(--line,#ddd)}
.rv-cal-head button{min-width:44px;min-height:40px;background:none;border:1px solid var(--line,#ddd);color:var(--kinari);font:inherit;cursor:pointer}
.rv-cal-head button:disabled{opacity:.3;cursor:default}
.rv-grid{display:grid;grid-template-columns:repeat(7,1fr)}
.rv-grid div,.rv-grid button{aspect-ratio:1/1;display:flex;align-items:center;justify-content:center;font-size:14px;border:0;background:none;color:var(--usu);font-family:inherit}
.rv-grid .wd{aspect-ratio:auto;padding:6px 0;font-size:12px}
.rv-grid button{color:var(--kinari);font-weight:700;cursor:pointer;position:relative}
.rv-grid button::after{content:"";position:absolute;bottom:18%;width:5px;height:5px;border-radius:50%;background:var(--kin)}
.rv-grid button[aria-pressed="true"]{background:var(--kin);color:var(--sumi)}
.rv-grid button[aria-pressed="true"]::after{background:var(--sumi)}
.rv-grid .off{text-decoration:line-through;opacity:.45}
.rv-times{display:flex;flex-wrap:wrap;gap:8px}
.rv-times button{min-height:44px;padding:0 16px;border:1px solid var(--line,#ddd);background:var(--sumi);color:var(--kinari);font:inherit;cursor:pointer}
.rv-times button small{display:block;font-size:11px;color:var(--usu)}
.rv-times button[aria-pressed="true"]{border:2px solid var(--kin)}
.rv-form label{display:block;margin:12px 0 4px;font-size:14px}
.rv-form input,.rv-form select{width:100%;min-height:44px;padding:8px 10px;border:1px solid var(--line,#ccc);font:inherit;background:var(--sumi);color:var(--kinari);box-sizing:border-box}
.rv-form .chk{display:flex;gap:8px;align-items:flex-start;font-size:14px;margin:16px 0}
.rv-form .chk input{width:auto;min-height:0;margin-top:4px}
.rv-sum{border-top:1px solid var(--line,#ddd);border-bottom:1px solid var(--line,#ddd);padding:12px 0;margin:18px 0;font-size:15px;line-height:1.8}
.rv-msg{padding:12px 14px;border:1px solid var(--kin);margin:14px 0;font-size:14px;line-height:1.7}
.rv-empty{color:var(--usu);font-size:14px;padding:10px 0}
/* 2026-11-13 龍さん「なぜ進めないのか分からない」：入っていない欄をその場で赤く・すぐ下に理由 */
.rv-form input[aria-invalid=true],.rv-form .chk.bad{outline:2px solid #d9534f;outline-offset:1px}
.rv-err{color:#e8786f;font-size:13px;margin:6px 0 0;line-height:1.6}
.rv-msg.bad{border-color:#d9534f;color:#e8786f}
/* 2026-11-13 龍さん「読み込み中はくるくる回るのにしよう（待っている感じが少ない）」 */
.rv-spin{display:flex;flex-direction:column;align-items:center;gap:12px;padding:48px 0;color:var(--usu);font-size:13px}
.rv-spin::before{content:'';width:34px;height:34px;border:3px solid currentColor;border-right-color:transparent;border-radius:50%;opacity:.7;animation:rvspin .8s linear infinite}
#rv-submit:disabled::before{content:'';display:inline-block;width:12px;height:12px;margin-right:8px;vertical-align:-1px;border:2px solid currentColor;border-right-color:transparent;border-radius:50%;animation:rvspin .8s linear infinite}
@keyframes rvspin{to{transform:rotate(360deg)}}
@media (prefers-reduced-motion:reduce){.rv-spin::before,#rv-submit:disabled::before{animation-duration:2.4s}}
</style>"""


def _js(endpoint):
    return '<script>(function(){var EP=' + json.dumps(endpoint) + r''';
var $=function(id){return document.getElementById(id)};
function stopSpin(){var l=$('rv-loading');if(l)l.className='rv-empty'}
var st={cfg:null,course:null,date:null,time:null,month:null};
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
function yen(n){return Number(n).toLocaleString('ja-JP')+'円'}
var WD=['日','月','火','水','木','金','土'];
function dJa(d){var p=d.split('-');var w=new Date(Date.UTC(+p[0],+p[1]-1,+p[2])).getUTCDay();return (+p[1])+'月'+(+p[2])+'日（'+WD[w]+'）'}
function show(id,on){$(id).hidden=!on}
function msg(t,bad){var m=$('rv-msg');m.textContent=t;m.hidden=!t;m.className='rv-msg'+(bad?' bad':'')}
/* 欄ごとのエラー：欄を赤くして、すぐ下に理由を出す */
var FIELDS=['rv-name','rv-tel','rv-email','rv-agree'];
function ferr(id,t){var el=$(id),box=id==='rv-agree'?el.parentNode:el,e=$(id+'-err');
  if(!e){e=document.createElement('p');e.className='rv-err';e.id=id+'-err';box.parentNode.insertBefore(e,box.nextSibling)}
  e.textContent=t||'';e.hidden=!t;
  if(id==='rv-agree'){box.classList.toggle('bad',!!t)}else{if(t){el.setAttribute('aria-invalid','true');el.setAttribute('aria-describedby',e.id)}else el.removeAttribute('aria-invalid')}}
function clearErr(){FIELDS.forEach(function(id){ferr(id,'')})}
function digits(v){return String(v||'').replace(/[０-９]/g,function(c){return String.fromCharCode(c.charCodeAt(0)-65248)}).replace(/[^0-9]/g,'')}
function check(){var bad=[],first=null;function add(id,t,label){ferr(id,t);bad.push(label);if(!first)first=id}
  var nm=$('rv-name').value.trim(),tl=digits($('rv-tel').value),em=$('rv-email').value.trim();
  if(!nm)add('rv-name','お名前が入っていません。','お名前');
  if(!tl)add('rv-tel','電話番号が入っていません。','電話番号');else if(tl.length<10||tl.length>11)add('rv-tel','電話番号は数字10〜11けたで入れてください（ハイフンはあってもなくても大丈夫です）。','電話番号');
  if(!em)add('rv-email','メールアドレスが入っていません。','メールアドレス');else if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(em))add('rv-email','メールアドレスの形をご確認ください（例：name@example.com）。','メールアドレス');
  if(!$('rv-agree').checked)add('rv-agree','キャンセルの決まりと、ご連絡先の使い方をご確認のうえ、チェックを入れてください。','確認のチェック');
  if(first){msg('まだ進めません。'+bad.join('・')+' をご確認ください（赤い所）。',true);var el=$(first);el.scrollIntoView({behavior:'smooth',block:'center'});try{el.focus({preventScroll:true})}catch(x){}}
  return !first}
function load(){
  if(!EP){stopSpin();$('rv-loading').textContent='予約の受付は準備中です。';return}
  fetch(EP+'?r=reserve',{cache:'no-store'}).then(function(r){return r.json()}).then(function(c){
    if(!c||!c.ok){stopSpin();$('rv-loading').textContent='予約の受付は準備中です。始めたら、このページと Instagram でお知らせします。';return}
    st.cfg=c;show('rv-loading',false);show('rv-app',true);
    $('rv-hours').textContent='営業時間：'+c.hours;
    if(c.note){$('rv-top').textContent=c.note;show('rv-top',true)}
    $('rv-cancel').textContent=c.cancelPolicy||'';
    var box=$('rv-courses');box.innerHTML='';
    if(!c.courses.length){box.innerHTML='<p class="rv-empty">いま予約できるコースはありません。</p>';return}
    c.courses.forEach(function(co){
      var b=document.createElement('button');b.type='button';b.className='rv-course';b.setAttribute('aria-pressed','false');b.dataset.id=co.id;
      b.innerHTML='<b>'+esc(co.name)+'　'+yen(co.price)+'<small>（1人・税込）</small></b><span>'+esc(co.desc)+(co.minutes?'<br>所要 約'+co.minutes+'分・1回 最大'+co.maxPeople+'名':'')+'</span>';
      b.onclick=function(){pickCourse(co.id)};box.appendChild(b);
    });
    var q=new URLSearchParams(location.search).get('c');
    if(q&&c.courses.some(function(x){return x.id===q}))pickCourse(q);else if(c.courses.length===1)pickCourse(c.courses[0].id);
  }).catch(function(){stopSpin();$('rv-loading').textContent='読み込めませんでした。少し時間をおいて、もう一度開いてください。'});
}
function course(){return st.cfg.courses.filter(function(x){return x.id===st.course})[0]}
function pickCourse(id){
  st.course=id;st.date=null;st.time=null;msg('');
  Array.prototype.forEach.call(document.querySelectorAll('.rv-course'),function(b){b.setAttribute('aria-pressed',String(b.dataset.id===id))});
  var co=course();show('rv-step2',true);show('rv-step3',false);show('rv-step4',false);
  if(!co.slots.length){$('rv-cal').innerHTML='<p class="rv-empty">いま選べる日時がありません（満席か、受付前です）。</p>';return}
  var f=co.slots[0].date.split('-');st.month=[+f[0],+f[1]];cal();
}
function cal(){
  var co=course(),y=st.month[0],m=st.month[1];
  var days={};co.slots.forEach(function(s){days[s.date]=1});
  var first=co.slots[0].date.slice(0,7),last=co.slots[co.slots.length-1].date.slice(0,7);
  var key=y+'-'+('0'+m).slice(-2);
  var h='<div class="rv-cal-head"><button type="button" id="rv-prev" aria-label="前の月"'+(key<=first?' disabled':'')+'>‹</button><b>'+y+'年'+m+'月</b><button type="button" id="rv-next" aria-label="次の月"'+(key>=last?' disabled':'')+'>›</button></div><div class="rv-grid">';
  WD.forEach(function(w){h+='<div class="wd">'+w+'</div>'});
  var start=new Date(Date.UTC(y,m-1,1)).getUTCDay(),n=new Date(Date.UTC(y,m,0)).getUTCDate();
  for(var i=0;i<start;i++)h+='<div></div>';
  for(var d=1;d<=n;d++){var ds=key+'-'+('0'+d).slice(-2);
    h+=days[ds]?'<button type="button" data-d="'+ds+'" aria-pressed="'+(ds===st.date)+'" aria-label="'+dJa(ds)+' 予約できます">'+d+'</button>':'<div class="off" aria-hidden="true">'+d+'</div>'}
  h+='</div>';$('rv-cal').innerHTML=h;
  $('rv-prev').onclick=function(){st.month=m===1?[y-1,12]:[y,m-1];cal()};
  $('rv-next').onclick=function(){st.month=m===12?[y+1,1]:[y,m+1];cal()};
  Array.prototype.forEach.call(document.querySelectorAll('.rv-grid button'),function(b){b.onclick=function(){pickDate(b.dataset.d)}});
}
function pickDate(d){
  st.date=d;st.time=null;cal();msg('');
  var t=$('rv-times');t.innerHTML='';
  course().slots.filter(function(s){return s.date===d}).forEach(function(s){
    var b=document.createElement('button');b.type='button';b.setAttribute('aria-pressed','false');
    b.innerHTML=s.time+'<small>残り'+s.left+'名</small>';b.onclick=function(){pickTime(s,b)};t.appendChild(b)});
  $('rv-date-label').textContent=dJa(d);show('rv-step3',true);show('rv-step4',false);
}
function pickTime(s,b){
  st.time=s.time;Array.prototype.forEach.call(document.querySelectorAll('.rv-times button'),function(x){x.setAttribute('aria-pressed',String(x===b))});
  var sel=$('rv-people');sel.innerHTML='';for(var i=1;i<=s.left;i++){var o=document.createElement('option');o.value=i;o.textContent=i+'名';sel.appendChild(o)}
  show('rv-step4',true);sum();$('rv-step4').scrollIntoView({behavior:'smooth',block:'start'});
}
function sum(){var co=course(),p=Number($('rv-people').value||1);
  $('rv-sum').innerHTML=esc(co.name)+'<br>'+dJa(st.date)+' '+st.time+'・'+p+'名<br><b>お支払い '+yen(co.price*p)+'（税込）</b>'}
function submit(e){
  e.preventDefault();msg('');clearErr();
  if(!check())return;
  var body={action:'reserve',course:st.course,date:st.date,time:st.time,people:Number($('rv-people').value),
    name:$('rv-name').value,tel:$('rv-tel').value,email:$('rv-email').value,agree:true};
  var btn=$('rv-submit');btn.disabled=true;btn.textContent='受付中…';
  fetch(EP,{method:'POST',headers:{'Content-Type':'text/plain;charset=utf-8'},body:JSON.stringify(body)}).then(function(r){return r.json()}).then(function(r){
    if(r&&r.ok&&r.url){btn.textContent='お支払いの画面へ移ります…';location.href=r.url;return}
    if(r&&r.ok&&r.done){$('rv-app').innerHTML='<div class="rv-msg">ご予約を承りました。確認のメールをお送りしました。</div>';return}
    btn.disabled=false;btn.textContent='お支払いへ進む';
    var c=r&&r.code,f=r&&r.field;
    var FMAP={name:['rv-name','お名前をご確認ください。'],tel:['rv-tel','電話番号は数字10〜11けたで入れてください。'],email:['rv-email','メールアドレスをご確認ください。'],agree:['rv-agree','確認のチェックを入れてください。']};
    if(c==='full'||c==='unavailable'){msg('ごめんなさい。この日時はちょうど埋まってしまいました。別の日時をお選びください。',true);load()}
    else if(c==='bad'&&FMAP[f]){ferr(FMAP[f][0],FMAP[f][1]);msg('まだ進めません。赤い所をご確認ください。',true);$(FMAP[f][0]).scrollIntoView({behavior:'smooth',block:'center'})}
    else if(c==='bad')msg('日時か人数の選び方がうまく受け付けられませんでした。日にちと時間を選び直してください。',true);
    else if(c==='busy')msg('いま混み合っています。少し時間をおいて、もう一度「お支払いへ進む」を押してください。',true);
    else if(c==='closed')msg('いま予約の受付を止めています。少し時間をおいてお試しください。',true);
    else msg('うまく受け付けられませんでした。少し時間をおいて、もう一度お試しください。',true);
  }).catch(function(){btn.disabled=false;btn.textContent='お支払いへ進む';msg('通信がうまくいきませんでした。電波の良い所で、もう一度お試しください。',true)});
}
document.addEventListener('DOMContentLoaded',function(){$('rv-people').onchange=sum;$('rv-form').onsubmit=submit;
  FIELDS.forEach(function(id){$(id).addEventListener(id==='rv-agree'?'change':'input',function(){ferr(id,'');if(!document.querySelector('.rv-err:not([hidden])'))msg('')})});load()});
})();</script>'''


def build(write, head, foot, endpoint, shop_name):
    """予約画面とお礼の画面を書き出す。返すのは作ったパスの一覧（サイトマップには入れない）"""
    path = '/reserve/'
    main = _css() + '''
<main class="wrap page rsv">
  <h1>ご予約</h1>
  <p class="rv-note" id="rv-hours"></p>
  <p class="rv-msg" id="rv-top" hidden></p>
  <p class="rv-spin" id="rv-loading" role="status" aria-live="polite">読み込んでいます</p>
  <div id="rv-app" hidden>
    <h2>1. コースを選ぶ</h2>
    <div class="rv-courses" id="rv-courses"></div>
    <section id="rv-step2" hidden>
      <h2>2. 日にちを選ぶ</h2>
      <p class="rv-note">● のついた日が予約できます。定休日・休業日・満席の日は選べません。</p>
      <div class="rv-cal" id="rv-cal"></div>
    </section>
    <section id="rv-step3" hidden>
      <h2>3. 時間を選ぶ（<span id="rv-date-label"></span>）</h2>
      <div class="rv-times" id="rv-times"></div>
    </section>
    <section id="rv-step4" hidden>
      <h2>4. 人数とご連絡先</h2>
      <form class="rv-form" id="rv-form" novalidate>
        <label for="rv-people">人数</label>
        <select id="rv-people"></select>
        <label for="rv-name">お名前</label>
        <input id="rv-name" autocomplete="name" maxlength="40" required>
        <label for="rv-tel">電話番号</label>
        <input id="rv-tel" type="tel" autocomplete="tel" inputmode="tel" maxlength="16" required>
        <label for="rv-email">メールアドレス（予約の確認と前日のお知らせを送ります）</label>
        <input id="rv-email" type="email" autocomplete="email" maxlength="120" required>
        <div class="rv-sum" id="rv-sum"></div>
        <p class="rv-note"><b>キャンセルについて</b><br><span id="rv-cancel"></span></p>
        <p class="rv-note"><b>ご連絡先の使い方</b><br>お名前・電話番号・メールアドレスは、このご予約の確認とご連絡だけに使います。お支払いは Square の画面で行い、カードの番号は当店には届きません。</p>
        <label class="chk"><input type="checkbox" id="rv-agree"> キャンセルの決まりと、ご連絡先の使い方を確認しました</label>
        <p class="rv-msg" id="rv-msg" hidden></p>
        <button class="btn kin" type="submit" id="rv-submit">お支払いへ進む</button>
        <p class="rv-note">お支払いが済むと、ご予約が確定します。30分以内にお支払いがない場合は、ご予約は取り消しになります。</p>
      </form>
    </section>
  </div>
</main>
''' + _js(endpoint)
    write(path + 'index.html', head('ja', 'ご予約｜' + shop_name, 'ワークショップのご予約。空いている日時を選んで、そのままお支払いまでできます。', path, noindex=True) + main + foot('ja'))

    tpath = '/reserve/thanks/'
    tmain = '''
<main class="wrap page rsv">
  <h1>お支払いありがとうございます</h1>
  <p>ご予約の確定まで、15分ほどかかることがあります。確定すると、ご入力のメールアドレスに確認のメールが届きます。</p>
  <p class="rv-note">30分たってもメールが届かないときは、迷惑メールのフォルダもご確認のうえ、Instagram の DM でお知らせください。</p>
  <p><a class="btn" href="/">トップへ戻る</a></p>
</main>
'''
    write(tpath + 'index.html', head('ja', 'お支払いありがとうございます｜' + shop_name, 'ご予約のお支払いが済みました。', tpath, noindex=True) + tmain + foot('ja'))
    return [path, tpath]
