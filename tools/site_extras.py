"""商品ページの追加機能（2026-10-31 龍さん決定：A・B・C 全部）

A. お気に入り＋比較：商品ページの「♡ お気に入り」→ /favorites/ に並ぶ。2〜3点を選ぶと実寸・価格・素材を横に並べて比べられる。
   覚える場所はお客さまのブラウザ（localStorage）。会員登録もサーバーも要らない。消えても困らない「便利機能」だけに使う。
B. 店頭で見たい：商品ページの「店頭でこの服を見る」→ 今日が営業日か・営業時間・住所・地図。取り置きはしない決まり（10/7）なので「確保」ではなく来店の案内。
C. 手持ちの服と比べる：トップス・アウター・ワンピースで、身幅と着丈が分かる商品だけ。手持ちの服の身幅・着丈を入れると、形を重ねた図と差（+3cm など）が出る。
   入れた数字はブラウザに覚えておき、他の商品ページでもそのまま使える。

build_site.py からは、この中の関数と文字列を呼ぶだけ（既存の行の変更は最小）。
ブラウザに覚えさせる読み書きは全部 try/catch で包む（プライベートブラウズ等で使えなくても、ページは普通に表示される）。
"""
import html, json, re

FAV_KEY = 'kz_fav_v1'     # お気に入りの slug の配列
MY_KEY = 'kz_my_v1'       # 手持ちの服の実寸 {w,l,s,sl}
FAV_MAX = 30
MEASURE_KEYS = [('s', '肩幅'), ('w', '身幅'), ('l', '着丈'), ('sl', '袖丈')]
FIT_GENRES = ('tops', 'outer', 'dress')

TX = {
    'ja': {
        'fav_add': '♡ お気に入りに入れる', 'fav_nostore': 'このブラウザでは保存できない設定になっています（プライベートブラウズなど）。', 'fav_on': '♥ お気に入りに入っています', 'fav_see': 'お気に入りを見る →',
        'visit_btn': '店頭でこの服を見る', 'visit_open': '今日は営業日です', 'visit_closed': '今日は定休日です',
        'visit_note': '一点ものなので、先に売れていたらごめんなさい（取り置きはしていません）。来店の前に在庫を知りたいときは、Instagram の DM で品番を送ってください。',
        'visit_map': '地図を開く', 'visit_item': '品番',
        'fit_h': '手持ちの服と比べる', 'fit_p': '手持ちの服を平らに置いて、脇の下から脇の下（身幅）と、えりの付け根から裾（着丈）を測って入れてください。数字はこの端末に覚えておき、ほかの商品でも使えます。',
        'fit_w': '身幅', 'fit_l': '着丈', 'fit_s': '肩幅（なくても可）', 'fit_sl': '袖丈（なくても可）',
        'fit_item': 'この服', 'fit_mine': '手持ちの服', 'fit_empty': '身幅と着丈を入れると、形を重ねた図が出ます。',
        'fit_bigger': '大きい', 'fit_smaller': '小さい', 'fit_same': 'ほぼ同じ', 'fit_clear': '数字を消す',
        'fav_title': 'お気に入り', 'fav_sub': 'Favorites', 'fav_none': 'まだお気に入りがありません。商品ページの「♡ お気に入りに入れる」で、ここに並びます。',
        'fav_local': 'お気に入りはこの端末のブラウザに覚えています。別のスマホやPCには引き継がれません。',
        'fav_remove': '外す', 'fav_cmp': '比べる', 'fav_cmp_hint': '比べたい服に「比べる」の印を付けてください（最大3点）。',
        'cmp_h': '並べて比べる', 'cmp_price': '価格', 'cmp_state': '在庫', 'cmp_mat': '素材', 'cmp_size': 'サイズ',
        'cmp_sold': '売り切れ', 'cmp_one': '在庫1点', 'cmp_mine': '手持ちの服との差',
        'list_link': '商品一覧へ', 'gone': 'この商品は掲載を終了しました',
    },
    'en': {
        'fav_add': '♡ Save to favorites', 'fav_nostore': 'This browser does not allow saving (private browsing, for example).', 'fav_on': '♥ Saved to favorites', 'fav_see': 'See favorites →',
        'visit_btn': 'See this piece in the shop', 'visit_open': 'We are open today', 'visit_closed': 'We are closed today',
        'visit_note': 'Every piece is one of a kind, so it may sell before you arrive (we do not hold items). To check before visiting, send the item number by Instagram DM.',
        'visit_map': 'Open map', 'visit_item': 'Item no.',
        'fit_h': 'Compare with a piece you own', 'fit_p': 'Lay a piece you own flat and measure armpit to armpit (chest) and collar base to hem (length). The numbers are kept on this device for other items too.',
        'fit_w': 'Chest', 'fit_l': 'Length', 'fit_s': 'Shoulder (optional)', 'fit_sl': 'Sleeve (optional)',
        'fit_item': 'This piece', 'fit_mine': 'Yours', 'fit_empty': 'Enter chest and length to see the two shapes overlaid.',
        'fit_bigger': 'larger', 'fit_smaller': 'smaller', 'fit_same': 'about the same', 'fit_clear': 'Clear',
        'fav_title': 'Favorites', 'fav_sub': 'Saved pieces', 'fav_none': 'No favorites yet. Use "♡ Save to favorites" on an item page to list it here.',
        'fav_local': 'Favorites are kept in this browser only and do not move to other devices.',
        'fav_remove': 'Remove', 'fav_cmp': 'Compare', 'fav_cmp_hint': 'Tick "Compare" on up to 3 pieces.',
        'cmp_h': 'Side by side', 'cmp_price': 'Price', 'cmp_state': 'Stock', 'cmp_mat': 'Material', 'cmp_size': 'Size',
        'cmp_sold': 'Sold', 'cmp_one': 'One in stock', 'cmp_mine': 'vs. yours',
        'list_link': 'Back to shop', 'gone': 'This item is no longer listed',
    },
}
MEASURE_LABEL = {'ja': {'s': '肩幅', 'w': '身幅', 'l': '着丈', 'sl': '袖丈'},
                 'en': {'s': 'Shoulder', 'w': 'Chest', 'l': 'Length', 'sl': 'Sleeve'}}

_NUM = r'(?:\([^)]*\)|（[^）]*）)?\s*[:：]?\s*約?\s*(\d+(?:\.\d+)?)'


def measures(p):
    """仕様表の「サイズ」から 肩幅・身幅・着丈・袖丈（cm）を読む。読めないものは入れない"""
    v = next((v for k, v in p.get('spec', []) if k == 'サイズ'), '')
    out = {}
    for key, ja in MEASURE_KEYS:
        m = re.search(ja + _NUM, v)
        if m and key == 'sl' and re.search(r'脇下|裄', v[m.start():m.end()]):
            continue   # 脇の下から測った袖丈（ラグラン袖など）は、肩から測る手持ちの服と比べられないので使わない
        if m:
            x = float(m.group(1))
            if 5 <= x <= 200:
                out[key] = x
    return out


def can_fit(p, genre):
    m = measures(p)
    return genre in FIT_GENRES and 'w' in m and 'l' in m


def _spec(spec, keys):
    return next((v for k, v in spec if k in keys), '')


def items_json(live, loc, site_price, is_sold, thumb_of):
    """お気に入りページが読む、掲載中の商品の小さな一覧（/assets/items.json）。英語の訳が無い商品は日本語のまま"""
    rows = []
    for p in live:
        ja, en = p.get('spec', []), loc(p, 'spec', 'en')
        mat_ja = p.get('material', '') or _spec(ja, ('素材',))
        rows.append({'s': p['slug'], 'b': p.get('brand', ''),
                     'n': {'ja': loc(p, 'product_name', 'ja'), 'en': loc(p, 'product_name', 'en')},
                     'p': site_price(p), 'sold': 1 if is_sold(p) else 0, 't': thumb_of(p), 'm': measures(p),
                     'mat': {'ja': mat_ja, 'en': _spec(en, ('Materials', 'Material')) or mat_ja},
                     'sz': {'ja': _spec(ja, ('サイズ',)), 'en': _spec(en, ('Size',)) or _spec(ja, ('サイズ',))}})
    return json.dumps({'items': rows}, ensure_ascii=False, separators=(',', ':'))


def product_buy_html(p, lang, sold, hours_line, addr, gmaps):
    """買うボタンの下：お気に入り（A）と店頭で見たい（B）"""
    t = TX[lang]
    P = '/en' if lang == 'en' else ''
    fav = (f'<div class="kxfav"><button type="button" class="btn ghost" id="favbtn" data-slug="{html.escape(p["slug"])}" '
           f'data-off="{t["fav_add"]}" data-on="{t["fav_on"]}" aria-pressed="false">{t["fav_add"]}</button>'
           f'<a class="kxsee" id="favsee" href="{P}/favorites/" hidden>{t["fav_see"]}</a>'
           f'<small class="kxmsg" id="favmsg" role="status" hidden>{t["fav_nostore"]}</small></div>')
    if sold:
        return fav
    visit = f'''<button type="button" class="btn ghost" id="visitbtn" aria-expanded="false" aria-controls="visitbox">{t['visit_btn']}</button>
        <div class="visitbox" id="visitbox" hidden>
          <p class="vtoday" id="vtoday" data-open="{t['visit_open']}" data-closed="{t['visit_closed']}" hidden></p>
          <p>{html.escape(hours_line)}<br>{html.escape(addr)}</p>
          <p><a class="maplink" href="{html.escape(gmaps)}" rel="noopener">{t['visit_map']}</a>　{t['visit_item']} <code>{html.escape(p['sku'])}</code></p>
          <p class="ship">{t['visit_note']}</p>
        </div>'''
    return fav + visit


def product_fit_html(p, lang, genre):
    """仕様表の下：手持ちの服と比べる（C）。身幅と着丈が分かるトップス・アウター・ワンピースだけ"""
    if not can_fit(p, genre):
        return ''
    t = TX[lang]
    m = measures(p)
    data = html.escape(json.dumps(m))
    def inp(k, label):
        return (f'<label class="kxin"><span>{label}</span><input type="number" inputmode="decimal" min="10" max="150" step="0.5" '
                f'data-k="{k}"><small>cm</small></label>')
    return f'''<details class="kxfit" id="fitbox" data-m="{data}"><summary>{t['fit_h']}</summary>
        <p class="howto">{t['fit_p']}</p>
        <div class="kxins">{inp('w', t['fit_w'])}{inp('l', t['fit_l'])}{inp('s', t['fit_s'])}{inp('sl', t['fit_sl'])}</div>
        <div class="kxfig"><svg id="fitsvg" viewBox="0 0 200 160" role="img" aria-label="{t['fit_h']}"></svg>
          <div class="kxleg"><span class="li"><i class="it"></i>{t['fit_item']}</span><span class="li"><i class="mi"></i>{t['fit_mine']}</span></div></div>
        <ul class="kxdiff" id="fitdiff"><li>{t['fit_empty']}</li></ul>
        <button type="button" class="kxbtn" id="fitclear">{t['fit_clear']}</button>
      </details>'''


def _shape_js():
    """服の形（cm）→ SVG の path。肩幅が無いときは身幅から目安を作り、袖丈が無いときは袖を描かない（図の形のためだけ・差の表には出さない）"""
    return r'''function kzShape(m,ox,oy,k){
  var w=m.w, l=m.l, s=m.s||w*0.92, sl=m.sl||0, nk=Math.min(18,s*0.36)/2, drop=3.5;
  var X=function(x){return (ox+x*k).toFixed(1)}, Y=function(y){return (oy+y*k).toFixed(1)};
  var hs=s/2, hw=w/2, pit=Math.max(18,l*0.3), d='M'+X(-nk)+' '+Y(0)+' Q'+X(0)+' '+Y(5)+' '+X(nk)+' '+Y(0)+' L'+X(hs)+' '+Y(drop);
  if(sl>0){var a=0.9, ex=Math.cos(a)*sl, ey=Math.sin(a)*sl, cw=Math.max(8,w*0.3);
    d+=' L'+X(hs+ex)+' '+Y(drop+ey)+' L'+X(hs+ex-Math.sin(a)*cw)+' '+Y(drop+ey+Math.cos(a)*cw)+' L'+X(hw)+' '+Y(pit);}
  else d+=' L'+X(hw)+' '+Y(pit);
  d+=' L'+X(hw)+' '+Y(l)+' L'+X(-hw)+' '+Y(l)+' L'+X(-hw)+' '+Y(pit);
  if(sl>0){d+=' L'+X(-hs-ex+Math.sin(a)*cw)+' '+Y(drop+ey+Math.cos(a)*cw)+' L'+X(-hs-ex)+' '+Y(drop+ey);}
  return d+' L'+X(-hs)+' '+Y(drop)+' Z';
}
function kzExtent(m){var w=m.w,s=m.s||w*0.92,sl=m.sl||0;return {hx:Math.max(w/2,s/2+(sl?Math.cos(0.9)*sl:0)),y:Math.max(m.l,3.5+(sl?Math.sin(0.9)*sl+Math.max(8,w*0.3):0))};}'''


EXTRAS_JS_TPL = r'''<script>
(function(){
  var L=__L__, FK='__FK__', MK='__MK__', MAX=__MAX__;
  function rd(k,d){try{var v=JSON.parse(localStorage.getItem(k)||'null');return v==null?d:v;}catch(e){return d;}}
  function wr(k,v){try{localStorage.setItem(k,JSON.stringify(v));return true;}catch(e){return false;}}
  /* A：お気に入り */
  var fb=document.getElementById('favbtn'), fs=document.getElementById('favsee');
  if(fb){
    var slug=fb.dataset.slug;
    function paint(){var on=rd(FK,[]).indexOf(slug)>=0; fb.textContent=on?fb.dataset.on:fb.dataset.off; fb.setAttribute('aria-pressed',String(on)); fb.classList.toggle('on',on); if(fs) fs.hidden=!on;}
    fb.addEventListener('click',function(){
      var a=rd(FK,[]), i=a.indexOf(slug);
      if(i>=0) a.splice(i,1); else { a.unshift(slug); if(a.length>MAX) a=a.slice(0,MAX); }
      if(!wr(FK,a)){ var mg=document.getElementById('favmsg'); if(mg) mg.hidden=false; return; }
      paint();
    });
    paint();
  }
  /* B：店頭で見たい */
  var vb=document.getElementById('visitbtn'), vx=document.getElementById('visitbox'), vt=document.getElementById('vtoday');
  if(vb&&vx){
    vb.addEventListener('click',function(){vx.hidden=!vx.hidden; vb.setAttribute('aria-expanded',String(!vx.hidden));});
    if(vt){var j=new Date(Date.now()+(new Date().getTimezoneOffset()+540)*60000),dw=j.getDay(),ymd=j.getFullYear()+'-'+('0'+(j.getMonth()+1)).slice(-2)+'-'+('0'+j.getDate()).slice(-2),hol=__HOL__,open=(ymd>='__NHF__'?[1]:__CW__).indexOf(dw)<0||hol.indexOf(ymd)>=0;
      vt.textContent=open?vt.dataset.open:vt.dataset.closed; if(!open) vt.className='vtoday closed'; vt.hidden=false;}
  }
  /* C：手持ちの服と比べる */
  __SHAPE__
  var fx=document.getElementById('fitbox');
  if(fx){
    var item=JSON.parse(fx.dataset.m), ins=fx.querySelectorAll('input[data-k]'), svg=document.getElementById('fitsvg'), df=document.getElementById('fitdiff'), lab=__LAB__;
    var my=rd(MK,{}); ins.forEach(function(i){ if(my[i.dataset.k]) i.value=my[i.dataset.k]; });
    function num(v){var x=parseFloat(String(v).replace(/[^0-9.]/g,''));return (x>=10&&x<=150)?x:0;}
    function draw(){
      var mine={}; ins.forEach(function(i){var x=num(i.value); if(x) mine[i.dataset.k]=x;});
      wr(MK,mine);
      var ok=mine.w&&mine.l, e1=kzExtent(item), e2=ok?kzExtent(mine):{hx:0,y:0};
      var hx=Math.max(e1.hx,e2.hx), hy=Math.max(e1.y,e2.y), k=Math.min(90/hx,148/hy), h='';
      h+='<path d="'+kzShape(item,100,6,k)+'" class="it"/>';
      if(ok) h+='<path d="'+kzShape(mine,100,6,k)+'" class="mi"/>';
      svg.innerHTML=h;
      if(!ok){df.innerHTML='<li>'+L.fit_empty+'</li>';return;}
      var out='';
      ['w','l','s','sl'].forEach(function(key){
        if(!(item[key]&&mine[key])) return;
        var d=Math.round((item[key]-mine[key])*2)/2, word=Math.abs(d)<1?L.fit_same:L.word.replace('{n}',Math.abs(d)).replace('{w}',d>0?L.fit_bigger:L.fit_smaller);
        var li=document.createElement('li'); li.textContent=lab[key]+L.sep+L.fit_item+' '+item[key]+'cm / '+L.fit_mine+' '+mine[key]+'cm → '+word; out+=li.outerHTML;
      });
      df.innerHTML=out;
    }
    ins.forEach(function(i){i.addEventListener('input',draw);});
    document.getElementById('fitclear').addEventListener('click',function(){ins.forEach(function(i){i.value='';}); draw();});
    draw();
  }
})();
</script>'''


def extras_js(lang, holiday_mondays, newhours_from, closed_weekdays_js):
    t = TX[lang]
    return (EXTRAS_JS_TPL.replace('__L__', json.dumps({'fit_empty': t['fit_empty'], 'fit_item': t['fit_item'], 'fit_mine': t['fit_mine'],
                                                       'fit_same': t['fit_same'], 'fit_bigger': t['fit_bigger'], 'fit_smaller': t['fit_smaller'], 'sep': '：' if lang == 'ja' else ': ', 'word': 'この服のほうが{n}cm{w}' if lang == 'ja' else 'this piece is {n}cm {w}'}, ensure_ascii=False))
            .replace('__FK__', FAV_KEY).replace('__MK__', MY_KEY).replace('__MAX__', str(FAV_MAX))
            .replace('__HOL__', json.dumps(holiday_mondays)).replace('__NHF__', newhours_from).replace('__CW__', closed_weekdays_js)
            .replace('__SHAPE__', _shape_js()).replace('__LAB__', json.dumps(MEASURE_LABEL[lang], ensure_ascii=False)))


FAV_JS_TPL = r'''<script>
(function(){
  var L=__L__, LAB=__LAB__, P='__P__', lang='__LANG__', FK='__FK__', MK='__MK__';
  function rd(k,d){try{var v=JSON.parse(localStorage.getItem(k)||'null');return v==null?d:v;}catch(e){return d;}}
  function wr(k,v){try{localStorage.setItem(k,JSON.stringify(v));}catch(e){}}
  var grid=document.getElementById('favgrid'), none=document.getElementById('favnone'), cmp=document.getElementById('cmpbox'), hint=document.getElementById('cmphint'), sel=[];
  function money(n){return lang==='ja'?n.toLocaleString('ja-JP')+'円':'¥'+n.toLocaleString('en-US');}
  function el(tag,cls,txt){var e=document.createElement(tag); if(cls) e.className=cls; if(txt!=null) e.textContent=txt; return e;}
  function render(items){
    var fav=rd(FK,[]), by={}; items.forEach(function(x){by[x.s]=x;});
    /* 一覧に無い商品（掲載終了・下書き・読み込みの途中）は勝手に消さず、「掲載を終了しました」と出して、外すかどうかはお客さまに任せる */
    var list=fav.filter(function(s){return by[s];}).map(function(s){return by[s];}), gone=fav.filter(function(s){return !by[s];});
    grid.innerHTML=''; sel=sel.filter(function(s){return by[s];});
    none.hidden=fav.length>0; hint.hidden=list.length<2;
    gone.forEach(function(s){
      var w=el('div','favcell gone'); w.appendChild(el('p','favgone',L.gone));
      var rm=el('button','kxbtn',L.fav_remove); rm.type='button';
      rm.addEventListener('click',function(){ wr(FK,rd(FK,[]).filter(function(x){return x!==s;})); render(items); });
      w.appendChild(rm); grid.appendChild(w);
    });
    list.forEach(function(x){
      var w=el('div','favcell'), a=el('a','card'+(x.sold?' sold':'')); a.href=P+'/journal/'+x.s+'/';
      var ph=el('div','ph'), im=el('img'); im.onload=im.onerror=function(){ph.classList.add('ld');}; im.src=x.t; im.alt=x.n[lang]||x.n.ja; im.loading='lazy'; ph.appendChild(im); a.appendChild(ph);
      a.appendChild(el('div','brand',x.b)); a.appendChild(el('div','nm',x.n[lang]||x.n.ja));
      a.appendChild(el('div','pr',money(x.p)));
      var ctl=el('div','favctl'), cb=el('label','chk'), ci=document.createElement('input'); ci.type='checkbox'; ci.checked=sel.indexOf(x.s)>=0;
      ci.addEventListener('change',function(){ var i=sel.indexOf(x.s); if(ci.checked){ if(sel.length>=3){ci.checked=false; hint.hidden=false; hint.classList.add('warn'); return;} sel.push(x.s);} else if(i>=0) sel.splice(i,1); hint.classList.remove('warn'); table(by); });
      cb.appendChild(ci); cb.appendChild(document.createTextNode(' '+L.fav_cmp));
      var rm=el('button','kxbtn',L.fav_remove); rm.type='button';
      rm.addEventListener('click',function(){ wr(FK,rd(FK,[]).filter(function(s){return s!==x.s;})); render(items); });
      ctl.appendChild(cb); ctl.appendChild(rm); w.appendChild(a); w.appendChild(ctl); grid.appendChild(w);
    });
    table(by);
  }
  function table(by){
    cmp.innerHTML=''; if(sel.length<2){cmp.hidden=true;return;} cmp.hidden=false;
    var xs=sel.map(function(s){return by[s];}), my=rd(MK,{}), t=el('table','cmp'), hd=el('tr');
    hd.appendChild(el('th','',''));
    xs.forEach(function(x){var th=el('th'), a=el('a'), im=el('img'); a.href=P+'/journal/'+x.s+'/'; im.src=x.t; im.alt=''; a.appendChild(im); a.appendChild(el('span','',x.b)); th.appendChild(a); hd.appendChild(th);});
    t.appendChild(hd);
    function row(label,f){var tr=el('tr'); tr.appendChild(el('th','',label)); xs.forEach(function(x){tr.appendChild(el('td','',f(x)));}); t.appendChild(tr);}
    row(L.cmp_price,function(x){return money(x.p);});
    row(L.cmp_state,function(x){return x.sold?L.cmp_sold:L.cmp_one;});
    ['w','l','s','sl'].forEach(function(k){
      if(!xs.some(function(x){return x.m[k];})) return;
      row(LAB[k],function(x){ if(!x.m[k]) return '—'; var s=x.m[k]+'cm'; if(my[k]){var d=Math.round((x.m[k]-my[k])*2)/2; s+=L.po+(d>0?'+':'')+d+L.pc;} return s; });
    });
    row(L.cmp_mat,function(x){return (x.mat&&(x.mat[lang]||x.mat.ja))||'—';});
    row(L.cmp_size,function(x){return (x.sz&&(x.sz[lang]||x.sz.ja))||'—';});
    var h=el('h2','',L.cmp_h); cmp.appendChild(h);
    if(my.w) cmp.appendChild(el('p','howto',L.po+' '+L.pc+' = '+L.cmp_mine));
    var wrap=el('div','cmpwrap'); wrap.appendChild(t); cmp.appendChild(wrap);
  }
  fetch('/assets/items.json',{cache:'no-cache'}).then(function(r){ if(!r.ok) throw new Error('HTTP '+r.status); return r.json(); })
    .then(function(d){render(d.items||[]);})
    .catch(function(e){ var er=document.getElementById('faverr'); er.hidden=false; er.textContent=L.load_err+' ('+e.message+')'; try{console.error('favorites:',e);}catch(x){} });
})();
</script>'''


def favorites_page_main(lang):
    t = TX[lang]
    P = '/en' if lang == 'en' else ''
    return f'''<main class="wrap">
  <div class="sec-head jhead"><h1>{t['fav_title']}<small>{t['fav_sub']}</small></h1></div>
  <p class="howto">{t['fav_local']}</p>
  <p class="howto" id="cmphint" hidden>{t['fav_cmp_hint']}</p>
  <section class="cmpbox" id="cmpbox" hidden></section>
  <p class="favnone" id="faverr" role="alert" hidden></p>
  <p class="favnone" id="favnone" hidden>{t['fav_none']}<br><a href="{P}/#list">{t['list_link']}</a></p>
  <div class="grid" id="favgrid"></div>
  <div style="height:72px"></div>
</main>'''


def favorites_js(lang):
    t = TX[lang]
    L = {k: t[k] for k in ('fav_remove', 'fav_cmp', 'cmp_h', 'cmp_price', 'cmp_state', 'cmp_mat', 'cmp_size', 'cmp_sold', 'cmp_one', 'cmp_mine')}
    L['load_err'] = 'お気に入りを読み込めませんでした。時間をおいて開き直してください' if lang == 'ja' else 'Could not load favorites. Please reload later'
    L['gone'] = t['gone']
    L['po'], L['pc'] = ('（', '）') if lang == 'ja' else (' (', ')')
    return (FAV_JS_TPL.replace('__L__', json.dumps(L, ensure_ascii=False)).replace('__LAB__', json.dumps(MEASURE_LABEL[lang], ensure_ascii=False))
            .replace('__P__', '/en' if lang == 'en' else '').replace('__LANG__', lang).replace('__FK__', FAV_KEY).replace('__MK__', MY_KEY))


EXTRAS_CSS = """
.kxfav{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-top:10px}
#favbtn.on{border-color:var(--kin);color:var(--kin)}
.kxsee{font-size:13px}
#visitbtn{margin-top:10px}
.visitbox{border:1px solid var(--line);padding:14px 16px;margin-top:10px;font-size:14px;line-height:1.8}
.visitbox p{margin:0 0 8px}
.vtoday{font-weight:600;color:var(--kin)}
.vtoday.closed{color:var(--usu)}
.kxfit summary{cursor:pointer}
.kxins{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:10px 0}
.kxin{display:flex;flex-direction:column;gap:4px;font-size:13px}
.kxin input{font-size:16px;padding:10px;border:1px solid var(--line);background:transparent;color:inherit;width:100%;min-height:44px;box-sizing:border-box}
.kxin small{color:var(--usu)}
.kxfig{display:flex;flex-direction:column;align-items:center;gap:6px;margin:8px 0}
#fitsvg{width:100%;max-width:340px;height:auto;background:var(--susu)}
#fitsvg .it{fill:rgba(124,68,18,.28);stroke:var(--kin);stroke-width:1.2}
#fitsvg .mi{fill:none;stroke:var(--kinari);stroke-width:1.4;stroke-dasharray:4 3}
.kxleg{display:flex;gap:16px;font-size:12px;color:var(--usu)}
.kxleg i{display:inline-block;width:18px;height:10px;margin-right:6px;vertical-align:middle}
.kxleg .it{background:rgba(124,68,18,.28);border:1px solid var(--kin)}
.kxleg .mi{border:1.5px dashed var(--kinari)}
.kxdiff{font-size:14px;line-height:1.8;padding-left:1.2em;margin:8px 0}
.favcell{display:flex;flex-direction:column}
.favctl{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-top:6px;font-size:13px}
.favctl .chk{display:flex;align-items:center;gap:6px;min-height:44px}
.favnone{font-size:14px;color:var(--usu);padding:24px 0;line-height:1.9}
.cmpbox{margin:12px 0 28px}
.cmpwrap{overflow-x:auto}
table.cmp{border-collapse:collapse;width:100%;min-width:480px;font-size:13px}
table.cmp th,table.cmp td{border-top:1px solid var(--line);padding:8px;text-align:left;vertical-align:top}
table.cmp tr:first-child th{border-top:0}
table.cmp tr:first-child img{width:96px;aspect-ratio:4/5;object-fit:cover;display:block;margin-bottom:4px}
table.cmp th:first-child{color:var(--usu);font-weight:500;white-space:nowrap;width:5em}
.kxbtn{background:none;border:1px solid var(--line);color:inherit;font:inherit;font-size:13px;padding:0 14px;min-height:44px;cursor:pointer}
.kxmsg{display:block;width:100%;font-size:12px;color:var(--usu)}
#cmphint.warn{color:var(--kin)}
.favgone{font-size:13px;color:var(--usu);margin:0 0 8px}
.favcell.gone{border:1px dashed var(--line);padding:12px;justify-content:space-between}
"""
