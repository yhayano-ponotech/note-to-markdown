# Note.com Article Downloader

このツールは、Note.comの記事をMarkdown形式でダウンロードし、画像付きで保存するPythonスクリプトです。

## 機能

- Note.comの記事をMarkdown形式に変換
- 記事内の画像を自動的にダウンロードして保存
- 記事のプレビュー画像の生成
- 選択的なダウンロード（特定の記事のみ or 全記事）
- 記事の更新検知と差分更新
- 記事のタイトル検索機能

## 必要条件

- Python 3.7以上
- 必要なパッケージ:
  ```
  feedparser
  requests
  html2text
  playwright
  PyYAML
  ```

## セットアップ

1. リポジトリをクローン:
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. 依存パッケージをインストール:
   ```bash
   pip install -r requirements.txt
   ```

3. Playwrightをセットアップ:
   ```bash
   playwright install
   ```

4. 設定ファイルを作成:
   `config.ini` ファイルを作成し、以下の内容を設定:
   ```ini
   [credentials]
   username = your-email@example.com
   password = your-password
   ```

## 使用方法

### 記事のダウンロード

```bash
python html_to_markdown.py <note-username>
```

- `<note-username>`: ダウンロードしたい記事の著者のNoteユーザー名

実行すると以下のオプションが表示されます：
- すべての記事をダウンロード
- 特定の記事を選択してダウンロード

### 記事の検索

```bash
python search_articles.py <search-word> [--dir <directory>]
```

- `<search-word>`: 検索したいキーワード
- `--dir`: 記事が保存されているディレクトリ（デフォルト: posts）

## ディレクトリ構造

```
.
├── posts/                  # 変換されたMarkdownファイル
├── assets/                 # 画像ファイル
│   └── YYYYMMDD_hash/     # 日付とハッシュでグループ化された画像
├── html_to_markdown.py     # メインスクリプト
├── search_articles.py      # 検索スクリプト
├── config.ini             # 設定ファイル
└── requirements.txt       # 依存パッケージリスト
```

## 出力ファイル形式

### Markdownファイル

各記事は以下のフロントマターを含むMarkdownファイルとして保存されます：

```markdown
---
title: "記事タイトル"
excerpt: "記事の冒頭200文字..."
coverImage: "/assets/YYYYMMDD_hash/YYYYMMDD_hash_1.png"
date: "公開日"
dateModified: "更新日"
author:
  name: "Note Author"
  picture: "/assets/blog/authors/note_author.jpeg"
ogImage:
  url: "/assets/YYYYMMDD_hash/YYYYMMDD_hash_1.png"
---
```

### 画像ファイル

- 記事内の画像は `assets/YYYYMMDD_hash/` ディレクトリに保存
- プレビュー画像は記事ごとに生成
- 画像ファイル名は日付とハッシュに基づいて自動生成

## エラーハンドリング

- ログファイルは `note_to_markdown.log` に出力
- 各処理ステップでエラーをキャッチし、ログに記録
- 一つの記事の処理に失敗しても他の記事の処理は継続

## 注意事項

- Note.comのログインが必要です
- APIのレート制限を考慮して適切な待機時間を設定しています
- 大量の記事をダウンロードする場合は、サーバーへの負荷を考慮してください

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。