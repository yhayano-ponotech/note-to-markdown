# note-to-markdown

## プロジェクトの概要
このプロジェクトは、note.comの記事をMarkdown形式に変換するためのツールです。Playwrightを使用して記事のHTMLを取得し、html2textを使用してMarkdownに変換します。

## インストール方法
```bash
git clone https://github.com/ponotech/note-to-markdown.git
cd note-to-markdown
pip install -r requirements.txt
playwright install
```

## 使用方法
1. `config.ini`ファイルにnote.comのログイン情報を設定します。
2. 以下のコマンドを実行して記事をダウンロードします：
```bash
python html_to_markdown.py
```

## 設定
`config.ini`ファイルに以下の形式でログイン情報を設定してください：
```ini
[credentials]
username = your_note_email
password = your_note_password
```

## 依存関係
- feedparser
- requests
- html2text
- playwright

## 貢献方法
貢献を歓迎します！プルリクエストを送る前に、[CONTRIBUTING.md](CONTRIBUTING.md)をお読みください。

## ライセンス
このプロジェクトはMITライセンスのもとで公開されています。詳細は[LICENSE](LICENSE)ファイルをご覧ください。