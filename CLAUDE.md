# Claude 向けの案内（kobanzame-site）

> このリポジトリは公開で、ここに置いたファイルはそのままサイトでも見えます。**この説明書にも、ID・鍵・アカウント名・人の名前・電話番号・お客さまの名前を書かないでください。**

川越の古着屋「小判鮫」の公式サイト（https://kobanzame-kawagoe.com）。
龍さん（オーナー）はプログラミング初心者。返事は日本語で、手順を省かず、選択肢は A／B／C に根拠と推奨を添える。

## 最初に読むもの
詳しい決まり（安全手順・本番への入れ方・自動化の地図）は、非公開リポジトリ **kobanzame-brain** にあります。触る前に、そちらの `CLAUDE.md` → `docs/仕組みの地図.md`（§5 公式サイト）→ `skills/safe-prod-change/SKILL.md` を読んでください。読めないときは、作業を始める前に龍さんに伝えてください。

## 仕組み（ざっくり）
- 商品データは `data/products.json`。ページは `tools/build_site.py` と `tools/build_blog.py` が作る（HTML を手で直さない）。
- main に `data/products.json`・`data/news.json`・`data/blog/**`・`tools/build_*.py` などが入ると、GitHub Actions（build-site）がサイトを作り直してコミットする。
- このリポジトリの直下がそのまま公開される（Cloudflare Pages）。

## 変更の進め方
- 変更はブランチ → プルリクエスト（差分の確認画面）→ **龍さんが Merge**。main に直接 push しない。Merge もしない。
- `.github/workflows/` は龍さんが明示したときだけ触る。
- 商品説明・ブログの文章のルールは Project「嶋崎龍3」の `preferences` と記録に従う（言い切る・「気配」でなく「空気感」・年代は「2000年代頃」など）。
- お客さまの名前が入ったファイルは絶対に載せない（履歴からも消す）。
- コミットの1行目は「YYYY-MM-DD 何をしたか」（日本語でよい）。
