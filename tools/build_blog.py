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
import json, os, html as _html, glob, datetime

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


# ---------- 記事の写真を <figure> に ----------
def photo_html(photo, slug):
    """1枚の写真を <figure> で返す"""
    src = f'{BLOG_ASSETS}/{slug}/{photo["file"]}'
    alt = _esc(photo.get('alt', ''))
    caption = photo.get('caption', photo.get('alt', ''))
    fig = f'<figure class="blog-photo"><img src="{src}" alt="{alt}" loading="lazy" decoding="async">'
    if caption:
        fig += f'<figcaption>{_esc(caption)}</figcaption>'
    fig += '</figure>'
    return fig


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
    og_image = f'{BLOG_ASSETS}/{slug}/{cover}' if cover else None

    # 構造化データ（BlogPosting）
    ld = {
        '@context': 'https://schema.org',
        '@graph': [
            try_org_node(),
            {
                '@type': 'BlogPosting',
                'headline': title,
                'datePublished': date,
                'author': {'@type': 'Organization', 'name': _site_var('SHOP', {}).get('name', '古着屋 小判鮫 KOBANZAME')},
                'publisher': {'@type': 'Organization', 'name': _site_var('SHOP', {}).get('name', '古着屋 小判鮫 KOBANZAME')},
                'description': desc,
                'mainEntityOfPage': {'@type': 'WebPage', '@id': f'{BASE}/blog/{slug}/'},
            }
        ]
    }
    if og_image:
        ld['@graph'][1]['image'] = f'{BASE}{og_image}'

    # 日付の表示
    try:
        dt = datetime.datetime.strptime(date, '%Y-%m-%d')
        date_display = dt.strftime('%Y.%m.%d')
    except ValueError:
        date_display = date

    # 本文の組み立て
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

    # 写真ギャラリー（本文の後）
    if photos:
        content_parts.append(gallery_html(photos, slug))

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
            img_html = f'<div class="blog-card-img"><img src="{BLOG_ASSETS}/{slug}/{cover}" alt="" loading="lazy" decoding="async"></div>'

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

    page_html = try_head('ja', 'ブログ | 古着屋 小判鮫', '小判鮫の商品紹介・コラム。', '/blog/')
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
