#!/usr/bin/env python3
"""
ブログの写真をサイトに保存する（2026-10-22 龍さん「サイト側に写真を残す」）

data/blog/posts/*.json の photos[] で src が http(s) のもの（メルカリShops の画像など）を
ダウンロードして assets/blog/<slug>/<file> に保存し、src をサイト内のパス（/assets/blog/<slug>/<file>）に書き換える。
- メルカリ側で出品を消しても、ブログの写真が消えないようにするため
- 長い辺 1000px・JPEG 品質 80 に縮める（Pillow が無ければそのまま保存）
- 失敗した写真は src を変えない（元の URL のまま表示される）。止めずに次へ
- build-site の Action の中で、build_site.py の前に動く（Actions はインターネットにつながる）
使い方：python3 tools/blog_photos.py
"""
import glob, io, json, os, re, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_SIDE = 1000
QUALITY = 80

try:
    from PIL import Image
except Exception:
    Image = None


def shrink(data):
    if Image is None:
        return data
    try:
        im = Image.open(io.BytesIO(data))
        im = im.convert('RGB')
        w, h = im.size
        r = MAX_SIDE / max(w, h)
        if r < 1:
            im = im.resize((int(w * r), int(h * r)), Image.LANCZOS)
        out = io.BytesIO()
        im.save(out, 'JPEG', quality=QUALITY, optimize=True)
        return out.getvalue()
    except Exception as e:
        print(f'  縮小に失敗（元のまま保存）：{e}')
        return data


def main():
    saved = failed = 0
    for path in sorted(glob.glob(os.path.join(ROOT, 'data/blog/posts/*.json'))):
        raw = open(path, encoding='utf-8').read()
        d = json.loads(raw)
        slug = d['slug']
        changed = False
        for i, ph in enumerate(d.get('photos', [])):
            src = ph.get('src', '')
            if not src.startswith('http'):
                continue
            name = ph.get('file') or f'{i + 1:02d}.jpg'
            name = re.sub(r'[^A-Za-z0-9._-]', '_', os.path.splitext(name)[0]) + '.jpg'
            dest_dir = os.path.join(ROOT, 'assets/blog', slug)
            dest = os.path.join(dest_dir, name)
            try:
                if not os.path.exists(dest):
                    req = urllib.request.Request(src, headers={'User-Agent': 'kobanzame-site-bot'})
                    with urllib.request.urlopen(req, timeout=30) as r:
                        data = r.read()
                    if len(data) < 1000:
                        raise ValueError(f'小さすぎる（{len(data)} バイト）')
                    os.makedirs(dest_dir, exist_ok=True)
                    open(dest, 'wb').write(shrink(data))
                ph['src'] = f'/assets/blog/{slug}/{name}'
                if 'file' in ph:
                    ph['file'] = name
                changed = True
                saved += 1
            except Exception as e:
                failed += 1
                print(f'  [blog_photos] {slug} {src[:60]}… 失敗：{e}')
        if changed:
            open(path, 'w', encoding='utf-8').write(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
    print(f'[blog_photos] 保存 {saved} 枚・失敗 {failed} 枚')
    return 0


if __name__ == '__main__':
    sys.exit(main())
