# -*- coding: utf-8 -*-
"""小判鮫 ブログ生成スクリプト v1.0（2026-10-22 新規）
data/blog/posts/<slug>.json → /blog/ 一覧ページ ＋ /blog/<slug>/ 記事ページ

build_site.py の main() の末尾で呼ばれる。
build_site.py が先に head(), foot(), write() などを定義しているので、ここではそれらを使う。

記事JSONの形：
{
  "slug": "af-kempshall",
  "title": "...",
  "date": "2026-10-22",
  "author": "小判鮫",
  "description": "...",
  "cover": "01.jpg",
  "access": "free",          // "free" | "members"（将来の有料化に備えた設計）
  "paid_from": "",            // access を members に切り替える予定日（空なら未定）
  "teaser": "...",            // 無料で読める導入文（HTML）
  "body": "...",              // 本文（HTML）── access="free" ならそのまま出す
  "photos": [                 // 記事に使う写真の一覧
    {"file": "01.jpg", "alt": "正面・全体（フードあり）"},
    ...
  ],
  "tags": ["ダウンジャケット", "Abercrombie & Fitch"]
}
"""
import json, os, re, html as _html, glob, datetime

# build_site.py から import されるとき、build_site のグローバルは見えない。
# 必要な変数・関数は build_site から明示的に取得する。
import importlib, sys

def _get_site():
    """build_site.py のモジュールを返す（すでに読み込み済みならそれを使う）"""
    mod = sys.modules.get('build_site') or sys.modules.get('__main__')
    return mod

def _site_var(name, default=None):
    mod = _get_site()
    return getattr(mod, name, default)

ROOT = _site_var('ROOT') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = _site_var('BASE') or 'https://kobanzame-site.pages.dev'
TODAY = _site_var('TODAY') or os.environ.get('SITE_TODAY') or datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y-%m-%d')

BLOG_DIR = os.path.join(ROOT, 'data/blog/posts')
BLOG_ASSETS = '/assets/blog'   # URL上のパス

# ---------- 記事を読み込む ----------
def load_posts():
    """data/blog/posts/*.json を読んで、新しい順に並べて返す"""
    posts = []
    pat = os.path.join(BLOG_DIR, '*.json')
    for path in glob.glob(pat):
        try:
            p = json.load(open(path, encoding='utf-8'))
        except Exception as e:
            print(f'⚠ ブログ記事を読めませんでした {path}: {e}')
            continue
        # 必須フィールドの確認
        if not p.get('slug') or not p.get('title') or not p.get('date'):
            print(f'⚠ ブログ記事：slug/title/date が足りません {path}')
            continue
        # 未来の日付の記事は下書き扱い（ビルドするが一覧に出さない）
        p['_draft'] = p['date'] > TODAY
        posts.append(p)
    posts.sort(key=lambda p: p['date'], reverse=True)
    return posts


def _esc(s):
    """html.escape のショートカット（build_site.py の esc が無いとき用）"""
    fn = _site_var('esc')
    if fn:
        return fn(s)
    return _html.escape(str(s), quote=True)


# ---------- 表紙の写真の場所（2026-10-22：cover が photos の file と同じなら、その src を使う。一覧の表紙が出ない不具合の直し） ----------
def cover_src(p):
    cover = p.get('cover', '')
    if not cover:
        return ''
    for ph in p.get('photos', []):
        if ph.get('file') == cover and ph.get('src'):
            return ph['src']
    return f"{BLOG_ASSETS}/{p['slug']}/{cover}"


# ---------- 記事の写真を <figure> に ----------
def photo_html(photo, slug):
    """1枚の写真を <figure> で返す"""
    # photos[] に src があればそれを使う（外部URL や /journal/... など）
    # 無ければ既存の BLOG_ASSETS/{slug}/{file} で組み立てる
    if 'src' in photo and photo['src']:
        src = photo['src']
    else:
        src = f'{BLOG_ASSETS}/{slug}/{photo["file"]}'
    alt = _esc(photo.get('alt', ''))
    caption = photo.get('caption', photo.get('alt', ''))
    fig = f'<figure class="blog-photo"><img src="{src}" alt="{alt}" loading="lazy" decoding="async">'
    if caption:
        fig += f'<figcaption>{_esc(caption)}</figcaption>'
    fig += '</figure>'
    return fig


# ---------- 本文の中に写真を差し込む（2026-10-22 龍さん「文章の間に写真」） ----------
# 本文（teaser・body）に <!--photo:05.jpg--> と書くと、その場所に写真1枚。
# <!--photo:05.jpg,09.jpg--> と2枚書くと横並び。ファイル名は photos[] の file と同じ。
# 差し込んだ写真は、最後のギャラリーには出さない。
_PHOTO_MARK = re.compile(r'<!--\s*photo:\s*([^>]+?)\s*-->')


def inline_photos(html, photos, slug, used):
    by_file = {ph['file']: ph for ph in photos}

    def rep(m):
        files = [f.strip() for f in m.group(1).split(',') if f.strip()]
        figs = []
        for f in files:
            ph = by_file.get(f)
            if not ph:
                print(f'  [blog] {slug}: 本文の写真 {f} が photos に無い（飛ばした）')
                continue
            used.add(f)
            figs.append(photo_html(ph, slug))
        if not figs:
            return ''
        cls = 'blog-inline blog-inline-2' if len(figs) > 1 else 'blog-inline'
        return f'<div class="{cls}">' + ''.join(figs) + '</div>'

    return _PHOTO_MARK.sub(rep, html or '')


# ---------- 公開前の点検（ブログの書き方ルール v0 §2-6：数えてログに出すだけ・止めない） ----------
_NG_WORDS = ['レア', '希少', '激レア', '最強', '世界に一つ', '気配', '前世', '転生', '取り置き', '予約', '俺',
             'と思われます', 'ではないでしょうか', 'よく見られる']


_PRODUCTS = None


def _products():
    global _PRODUCTS
    if _PRODUCTS is None:
        try:
            _PRODUCTS = {x.get('slug'): x for x in json.load(open(os.path.join(ROOT, 'data/products.json'), encoding='utf-8'))}
        except Exception:
            _PRODUCTS = {}
    return _PRODUCTS


def lint_post(p):
    text = re.sub(r'<[^>]+>', '', (p.get('teaser', '') or '') + (p.get('body', '') or ''))
    # 2026-10-22：商品の記事は、記事の slug＝商品の slug（違うと週1の自動作成が「記事が無い」と思い二重に書く・URL も変わる）
    slug = p.get('slug', '')
    prods = _products()
    if re.match(r'^k\d', slug) and prods and slug not in prods:
        print(f'  [blog] {slug}: ⚠ 記事の slug が商品の slug と違う（商品の slug に合わせる）')
    # 2026-10-22：価格が商品ページと違えばログに出す（税抜×1.1 を10円単位に切り上げ・整数だけで計算）
    pr = prods.get(slug)
    try:
        site = int(pr['prices']['site'])
        exp = ((site * 11 + 99) // 100) * 10
        got = [int(x.replace(',', '')) for x in re.findall(r'¥([\d,]+)', text)]
        if got and exp not in got:
            print(f'  [blog] {slug}: ⚠ 価格が商品ページと違う（記事 {got}・商品ページ ¥{exp:,}）')
    except Exception:
        pass
    hits = [(w, text.count(w)) for w in _NG_WORDS if w in text]
    if hits:
        print(f'  [blog] {p["slug"]}: 点検で見つかった言葉 ' + '・'.join(f'{w}×{n}' for w, n in hits))


def gallery_html(photos, slug):
    """写真の一覧をギャラリー風に並べる"""
    if not photos:
        return ''
    figs = '\n'.join(photo_html(ph, slug) for ph in photos)
    return f'<div class="blog-gallery">\n{figs}\n</div>'


# ---------- 記事ページ ----------
def build_post(p):
    """1つの記事ページを生成する"""
    slug = p['slug']
    title = p['title']
    date = p['date']
    desc = p.get('description', title)
    cover = p.get('cover', '')
    access = p.get('access', 'free')
    teaser = p.get('teaser', '')
    body = p.get('body', '')
    photos = p.get('photos', [])
    tags = p.get('tags', [])
    author = p.get('author', '小判鮫')

    # OG画像
    og_image = cover_src(p) or None

    # 構造化データ（BlogPosting）
    ld = {
        '@context': 'https://schema.org',
        '@graph': [
            try_org_node(),
            {
                '@type': 'BlogPosting',
                'headline': title,
                'datePublished': date,
                '@id': f'{BASE}/blog/{slug}/#article',
                'author': {'@type': 'Organization', '@id': f'{BASE}/#store', 'name': _site_var('SHOP', {}).get('name', '古着屋 小判鮫 KOBANZAME')},
                'publisher': {'@id': f'{BASE}/#store'},
                'dateModified': date, 'inLanguage': 'ja',
                'isPartOf': {'@type': 'Blog', '@id': f'{BASE}/blog/#blog'},
                **({'about': {'@id': f'{BASE}/journal/{slug}/#product'}} if slug in _products() else {}),
                'description': desc,
                'mainEntityOfPage': {'@type': 'WebPage', '@id': f'{BASE}/blog/{slug}/'},
            }
        ]
    }
    if og_image:
        ld['@graph'][1]['image'] = og_image if og_image.startswith('http') else f'{BASE}{og_image}'

    # 日付の表示
    try:
        dt = datetime.datetime.strptime(date, '%Y-%m-%d')
        date_display = dt.strftime('%Y.%m.%d')
    except ValueError:
        date_display = date

    # 本文の組み立て（本文中の <!--photo:…--> を写真に差し替える）
    used = set()
    teaser = inline_photos(teaser, photos, slug, used)
    body = inline_photos(body, photos, slug, used) if access == 'free' else body
    lint_post(p)
    content_parts = []
    if teaser:
        content_parts.append(f'<div class="blog-teaser">{teaser}</div>')

    if access == 'free':
        # 無料記事：本文をそのまま出す
        if body:
            content_parts.append(f'<div class="blog-body">{body}</div>')
    else:
        # 有料記事（将来用）：teaser だけ出して、残りはプレースホルダー
        content_parts.append('<div class="blog-paywall"><p>続きは会員向けの記事です。</p></div>')

    # 写真ギャラリー（本文の後）：本文に差し込まなかった写真だけ
    rest = [ph for ph in photos if ph['file'] not in used]
    if rest:
        head = '<h2 class="blog-gallery-head">そのほかの写真</h2>' if used else ''
        content_parts.append(head + gallery_html(rest, slug))

    # タグ
    tags_html = ''
    if tags:
        tags_html = '<div class="blog-tags">' + ''.join(f'<span class="tag">{_esc(t)}</span>' for t in tags) + '</div>'

    page_html = try_head('ja', f'{title} | 小判鮫ブログ', desc, f'/blog/{slug}/',
                         og_type='article', image=og_image, extra_ld=ld, noindex=p.get('_draft', False))

    page_html += f'''<main class="blog-main">
  <div class="crumb"><a href="/">HOME</a><span>／</span><a href="/blog/">ブログ</a><span>／</span><span>{_esc(title)}</span></div>
  <article class="blog-article">
    <div class="blog-header">
      <time datetime="{date}">{date_display}</time>
      <h1>{_esc(title)}</h1>
      <p class="blog-author">{_esc(author)}</p>
    </div>
    {''.join(content_parts)}
    {tags_html}
  </article>
</main>
'''
    page_html += try_foot('ja')
    try_write(f'/blog/{slug}/index.html', page_html)
    return f'/blog/{slug}/'


# ---------- 一覧ページ ----------
def build_index(posts):
    """ブログの一覧ページ /blog/ を生成する"""
    visible = [p for p in posts if not p.get('_draft')]

    cards = []
    for p in visible:
        slug = p['slug']
        title = p['title']
        date = p['date']
        desc = p.get('description', '')
        cover = p.get('cover', '')
        tags = p.get('tags', [])
        try:
            dt = datetime.datetime.strptime(date, '%Y-%m-%d')
            date_display = dt.strftime('%Y.%m.%d')
        except ValueError:
            date_display = date

        img_html = ''
        if cover:
            img_html = f'<div class="blog-card-img"><img src="{cover_src(p)}" alt="" loading="lazy" decoding="async"></div>'

        tags_html = ''
        if tags:
            tags_html = '<div class="blog-card-tags">' + ''.join(f'<span class="tag">{_esc(t)}</span>' for t in tags) + '</div>'

        cards.append(f'''<a href="/blog/{slug}/" class="blog-card">
  {img_html}
  <div class="blog-card-body">
    <time datetime="{date}">{date_display}</time>
    <h2>{_esc(title)}</h2>
    <p>{_esc(desc[:120])}</p>
    {tags_html}
  </div>
</a>''')

    if not cards:
        body_html = '<p class="blog-empty">記事はまだありません。</p>'
    else:
        body_html = '<div class="blog-grid">\n' + '\n'.join(cards) + '\n</div>'

    blog_ld = {'@context': 'https://schema.org', '@graph': [try_org_node(), {
        '@type': 'Blog', '@id': f'{BASE}/blog/#blog', 'name': '小判鮫ブログ', 'url': f'{BASE}/blog/', 'inLanguage': 'ja', 'publisher': {'@id': f'{BASE}/#store'},
        'blogPost': [{'@type': 'BlogPosting', '@id': f'{BASE}/blog/{p["slug"]}/#article', 'headline': p['title'], 'url': f'{BASE}/blog/{p["slug"]}/', 'datePublished': p['date']} for p in visible]}]}
    page_html = try_head('ja', 'ブログ｜古着屋 小判鮫（川越の古着・ヴィンテージ）',
                         '川越・元町の古民家古着屋「小判鮫」のブログ。店頭とサイトに並ぶヴィンテージ古着や一点ものを、写真と一緒に1点ずつ紹介しています。', '/blog/', extra_ld=blog_ld)
    page_html += f'''<main class="blog-main">
  <div class="crumb"><a href="/">HOME</a><span>／</span><span>ブログ</span></div>
  <div class="sec-head"><h1>Blog<small>ブログ</small></h1></div>
  {body_html}
</main>
'''
    page_html += try_foot('ja')
    try_write('/blog/index.html', page_html)
    return [f'/blog/{p["slug"]}/' for p in visible]


# ---------- build_site.py の関数を安全に呼ぶラッパー ----------
def try_head(*a, **kw):
    fn = _site_var('head')
    if fn:
        return fn(*a, **kw)
    return f'<!doctype html><html lang="ja"><head><title>{a[1] if len(a) > 1 else ""}</title></head><body>'

def try_foot(*a, **kw):
    fn = _site_var('foot')
    if fn:
        return fn(*a, **kw)
    return '</body></html>'

def try_write(path, text):
    fn = _site_var('write')
    if fn:
        fn(path, text)
    else:
        full = os.path.join(ROOT, path.lstrip('/'))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        open(full, 'w', encoding='utf-8').write(text)

def try_org_node():
    fn = _site_var('org_node')
    if fn:
        return fn()
    return {'@type': 'Organization', 'name': '古着屋 小判鮫 KOBANZAME'}


# ---------- CSS（build_site.py に追記用） ----------
BLOG_CSS = """
/* ---------- ブログ ---------- */
.blog-main{max-width:760px;margin:0 auto;padding:32px 16px 64px}
.blog-article{margin-top:24px}
.blog-header{margin-bottom:32px}
.blog-header time{font-family:'Jost',sans-serif;font-size:.85rem;color:var(--usu);letter-spacing:.04em}
.blog-header h1{font-family:'Libre Caslon Text','Zen Kaku Gothic New',serif;font-size:1.6rem;line-height:1.5;margin:.4em 0 .3em;color:var(--kinari)}
.blog-header .blog-author{font-size:.85rem;color:var(--usu)}
.blog-teaser,.blog-body{font-size:1rem;line-height:1.85;color:var(--kinari)}
.blog-teaser p,.blog-body p{margin:1.2em 0}
.blog-teaser h2,.blog-body h2{font-family:'Libre Caslon Text','Zen Kaku Gothic New',serif;font-size:1.25rem;margin:2em 0 .6em;border-bottom:1px solid var(--line);padding-bottom:.3em}
.blog-teaser h3,.blog-body h3{font-size:1.1rem;margin:1.6em 0 .4em}
.blog-paywall{background:var(--susu);border-radius:8px;padding:24px;margin:2em 0;text-align:center;color:var(--usu)}
.blog-photo{margin:1.5em 0}
.blog-photo img{width:100%;height:auto;border-radius:6px;display:block}
.blog-photo figcaption{font-size:.82rem;color:var(--usu);margin-top:.4em;line-height:1.5}
.blog-inline{margin:1.6em 0}
.blog-inline .blog-photo{margin:0}
.blog-inline-2{display:grid;gap:12px}
@media(min-width:560px){.blog-inline-2{grid-template-columns:1fr 1fr}}
.blog-gallery-head{font-size:1.1rem;margin:2.4em 0 .4em}
.blog-spec{width:100%;border-collapse:collapse;font-size:.92rem;margin:1em 0}
.blog-spec th,.blog-spec td{border-bottom:1px solid var(--line);padding:.55em .4em;text-align:left;vertical-align:top}
.blog-spec th{width:7.5em;color:var(--usu);font-weight:normal;white-space:nowrap}
.blog-gallery{display:grid;gap:16px;margin:2em 0}
@media(min-width:560px){.blog-gallery{grid-template-columns:1fr 1fr}}
.blog-tags{margin:2em 0 0;display:flex;flex-wrap:wrap;gap:8px}
.blog-tags .tag{font-size:.78rem;background:var(--susu);color:var(--usu);padding:4px 12px;border-radius:20px}
.blog-card{display:block;text-decoration:none;color:inherit;border:1px solid var(--line);border-radius:8px;overflow:hidden;transition:box-shadow .2s}
.blog-card:hover{box-shadow:0 4px 16px rgba(0,0,0,.06)}
.blog-card-img img{width:100%;height:200px;object-fit:cover;display:block}
.blog-card-body{padding:16px}
.blog-card-body time{font-family:'Jost',sans-serif;font-size:.78rem;color:var(--usu)}
.blog-card-body h2{font-size:1.05rem;line-height:1.4;margin:.3em 0;color:var(--kinari)}
.blog-card-body p{font-size:.85rem;color:var(--usu);line-height:1.5;margin:.3em 0 0}
.blog-card-tags{margin-top:8px;display:flex;flex-wrap:wrap;gap:4px}
.blog-card-tags .tag{font-size:.72rem;background:var(--susu);color:var(--usu);padding:2px 8px;border-radius:12px}
.blog-grid{display:grid;gap:24px;margin-top:24px}
@media(min-width:640px){.blog-grid{grid-template-columns:1fr 1fr}}
.blog-empty{color:var(--usu);text-align:center;padding:48px 0}
"""

# ---------- エントリーポイント ----------
def build_blog():
    """ブログの全ページを生成し、サイトマップ用のURLリストを返す"""
    posts = load_posts()
    if not posts:
        print('ブログ記事なし（スキップ）')
        return []
    urls = []
    for p in posts:
        url = build_post(p)
        urls.append(url)
    visible_urls = build_index(posts)
    # 一覧ページ自体も返す
    urls = ['/blog/'] + urls
    print(f'ブログ: {len(posts)} 記事を生成')
    return urls


if __name__ == '__main__':
    build_blog()
