import feedparser
import requests
import html2text
import json
import os
import sys
import traceback
import ssl
from datetime import datetime
from playwright.sync_api import sync_playwright
import logging
import re
from pathlib import Path
import configparser
import argparse

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('note_to_markdown.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def fetch_note_rss():
    rss_url = 'https://note.com/yas_bizdev/rss'
    if not rss_url:
        raise ValueError("RSS_URL environment variable is not set")
    if hasattr(ssl, '_create_unverified_context'):
        ssl._create_default_https_context = ssl._create_unverified_context
    feed = feedparser.parse(rss_url)
    logger.info(f"Found {len(feed.entries)} entries in RSS feed")
    return feed.entries

def fetch_all_note_articles(page, username):
    """ユーザーの全記事を取得する"""
    logger.info(f"開始: ユーザー '{username}' の記事を取得")
    articles = []
    page_num = 1
    
    # APIリクエスト用のヘッダーを設定
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest'
    }
    
    while True:
        url = f"https://note.com/api/v2/creators/{username}/contents?kind=note&page={page_num}"
        logger.info(f"APIリクエスト: ページ {page_num} を取得中")
        
        try:
            # APIリクエストを送信
            js_function = """
            async (params) => {
                const response = await fetch(params.url, {
                    method: 'GET',
                    headers: params.headers
                });
                const json = await response.json();
                return json;
            }
            """
            response = page.evaluate(js_function, {"url": url, "headers": headers})
            logger.debug(f"APIレスポンス: {json.dumps(response, ensure_ascii=False)[:200]}...")
            
            if not response or not response.get('data'):
                logger.info("データが取得できませんでした。取得を終了します。")
                break
                
            notes = response['data']['contents']
            if not notes:
                logger.info("これ以上記事がありません。取得を終了します。")
                break
                
            logger.info(f"ページ {page_num} から {len(notes)} 件の記事を取得しました")
            
            for note in notes:
                article = {
                    'title': note['name'],
                    'link': f"https://note.com/{username}/n/{note['key']}",
                    'published': note['publishAt'],
                    'dateModified': note.get('dateModified', note['publishAt']),
                    'key': note['key']
                }
                articles.append(article)
                logger.debug(f"記事を追加: {article['title']}")
            
            page_num += 1
            logger.info("APIレート制限を避けるため1秒待機します")
            page.wait_for_timeout(1000)
            
        except Exception as e:
            logger.error(f"APIリクエスト中にエラーが発生しました: {str(e)}")
            logger.error(traceback.format_exc())
            break

    logger.info(f"完了: 合計 {len(articles)} 件の記事を取得しました")
    return articles

def login_to_note(page, username, password):
    logger.info("noteへのログインを開始")
    page.goto("https://note.com/login")
    logger.info("ログインページを読み込み中...")
    page.wait_for_timeout(2000)
    
    logger.info("ログイン情報を入力中...")
    page.fill('#email', username)
    page.fill('#password', password)
    page.wait_for_timeout(1000)
    
    logger.info("ログインボタンをクリック")
    with page.expect_navigation():
        page.click('button:has-text("ログイン")')
    
    logger.info("ページの読み込みを待機中...")
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)
    
    if "login" in page.url:
        logger.error("ログインに失敗しました")
        return False
    else:
        logger.info("ログインに成功しました")
        return True

def download_html(page, url):
    logger.info(f"HTMLを取得中: {url}")
    page.goto(url)
    logger.info("ページの読み込みを待機中...")
    page.wait_for_load_state('networkidle', timeout=180000)
    logger.info("HTMLの取得が完了しました")
    return page.content()

def html_to_markdown(html):
    h = html2text.HTML2Text()
    h.ignore_links = False
    return h.handle(html)

def html_to_png(browser, html, output_path):
    """HTMLをPNGとして保存する"""
    logger.info(f"HTMLをPNGとして保存: {output_path}")
    try:
        # 新しいコンテキストとページを作成
        context = browser.new_context()
        temp_page = context.new_page()
        
        # HTMLを設定してスクリーンショットを撮影
        temp_page.set_content(html)
        temp_page.screenshot(path=output_path, full_page=True)
        
        # リソースを解放
        temp_page.close()
        context.close()
        logger.info("スクリーンショットの保存が完了しました")
    except Exception as e:
        logger.error(f"スクリーンショットの保存中にエラー: {str(e)}")
        raise

def get_hash_from_url(url):
    match = re.search(r'/n/([a-zA-Z0-9]+)$', url)
    return match.group(1) if match else None

def remove_unwanted_lines(markdown):
    unwanted_keywords = ['ログイン', '会員登録', '返金可', '割引']
    lines = markdown.split('\n')
    filtered_lines = [line for line in lines if not any(keyword in line for keyword in unwanted_keywords)]
    filtered_markdown = '\n'.join(filtered_lines)
    
    # Remove lines after "* [ noteプレミアム ](https://premium.lp-note.com)"
    premium_index = filtered_markdown.find("* [ noteプレミアム ](https://premium.lp-note.com)")
    if premium_index != -1:
        filtered_markdown = filtered_markdown[:premium_index]
    
    return filtered_markdown

def save_images(markdown, date_str, hash_id):
    """画像を保存してマークダウンのリンクを更新する"""
    logger.info(f"記事 {hash_id} の画像の保存を開始")
    
    image_pattern = r'!\[.*?\]\((.*?)\)'
    images = re.findall(image_pattern, markdown, re.DOTALL)
    logger.info(f"マークダウン内で {len(images)} 個の画像を検出")

    assets_dir = f'assets/{date_str}_{hash_id}'
    logger.info(f"アセットディレクトリを作成: {assets_dir}")
    os.makedirs(assets_dir, exist_ok=True)

    for i, image_url in enumerate(images, start=1):
        markdown = markdown.replace(image_url, image_url.replace('\n', ''))
        image_url = image_url.replace('\n', '')
        logger.info(f"画像 {i}/{len(images)} をダウンロード中: {image_url}")

        if image_url.startswith("data:image"):
            logger.info(f"data URLをスキップ: {image_url[:50]}...")
            continue

        try:
            response = requests.get(image_url)
            if response.status_code == 200:
                image_filename = f'{date_str}_{hash_id}_{i}.png'
                image_path = os.path.join(assets_dir, image_filename)
                with open(image_path, 'wb') as f:
                    f.write(response.content)
                markdown = markdown.replace(image_url, f'/assets/{date_str}_{hash_id}/{image_filename}')
                logger.info(f"画像を保存しました: {image_path}")
            else:
                logger.error(f"画像のダウンロードに失敗: {image_url}, ステータスコード: {response.status_code}")
        except Exception as e:
            logger.error(f"画像のダウンロード中にエラー: {str(e)}")

    logger.info(f"記事 {hash_id} の画像の保存が完了")
    return markdown

def should_update_article(existing_path, new_date_modified):
    """既存の記事を更新すべきかどうかを判断する"""
    logger.debug(f"記事の更新チェック: {existing_path}")
    
    if not os.path.exists(existing_path):
        logger.debug("既存の記事が存在しません")
        return True
        
    with open(existing_path, 'r', encoding='utf-8') as f:
        content = f.read()
        date_modified_match = re.search(r'dateModified: "(.*?)"', content)
        if not date_modified_match:
            logger.debug("既存の記事に最終更新日が見つかりません")
            return True
            
        try:
            existing_date = parse_date(date_modified_match.group(1))
            new_date = parse_date(new_date_modified)
            
            should_update = new_date > existing_date
            logger.debug(f"更新判定: 既存={existing_date}, 新規={new_date}, 更新必要={should_update}")
            return should_update
            
        except ValueError as e:
            logger.error(f"日付の比較中にエラー: {e}")
            return True

def cleanup_old_assets(date_str, hash_id):
    """古いアセットを削除する"""
    assets_dir = f'assets/{date_str}_{hash_id}'
    if os.path.exists(assets_dir):
        for file in os.listdir(assets_dir):
            file_path = os.path.join(assets_dir, file)
            try:
                os.remove(file_path)
            except Exception as e:
                logger.error(f"Error removing file {file_path}: {e}")
        try:
            os.rmdir(assets_dir)
        except Exception as e:
            logger.error(f"Error removing directory {assets_dir}: {e}")

def parse_date(date_str):
    """様々な日付フォーマットをパースしてYYYYMMDD形式の文字列を返す"""
    logger.debug(f"日付文字列をパース: {date_str}")
    
    formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",      # 2024-12-17T17:43:03.000Z
        "%Y-%m-%dT%H:%M:%S%z",        # 2024-12-17T17:43:03+09:00
        "%Y-%m-%dT%H:%M:%SZ",         # 2024-12-17T17:43:03Z
        "%Y-%m-%dT%H:%M:%S.%f%z",     # 2024-12-17T17:43:03.000+09:00
    ]
    
    for fmt in formats:
        try:
            date_obj = datetime.strptime(date_str, fmt)
            result = date_obj.strftime("%Y%m%d")
            logger.debug(f"パース成功: {result}")
            return result
        except ValueError:
            continue
    
    raise ValueError(f"Unsupported date format: {date_str}")

def save_content(title, markdown, png_path, url, publish_date, date_modified):
    logger.info(f"記事の保存を開始: {title}")
    
    hash_id = get_hash_from_url(url)
    if not hash_id:
        logger.error(f"URLからハッシュを抽出できません: {url}")
        raise ValueError(f"Could not extract hash from URL: {url}")
    
    try:
        date_str = parse_date(publish_date)
        logger.info(f"記事ID: {hash_id}, 公開日: {date_str}")
    except ValueError as e:
        logger.error(f"日付のパースに失敗: {e}")
        raise
    
    posts_dir = 'posts'
    os.makedirs(posts_dir, exist_ok=True)
    
    md_filename = f"{date_str}_{hash_id}.md"
    md_path = os.path.join(posts_dir, md_filename)
    logger.info(f"マークダウンファイルのパス: {md_path}")
    
    if not should_update_article(md_path, date_modified):
        logger.info(f"記事は最新の状態です。スキップします: {md_path}")
        return None, None, hash_id
    
    logger.info("古いアセットを削除中...")
    cleanup_old_assets(date_str, hash_id)
    
    logger.info("マークダウンの処理を開始")
    markdown = remove_unwanted_lines(markdown)
    markdown = save_images(markdown, date_str, hash_id)
    
    logger.info("マークダウンファイルを保存中...")
    header = f"""---
title: "{title}"
excerpt: "{markdown[:200]}..."
coverImage: "/assets/{date_str}_{hash_id}/{date_str}_{hash_id}_1.png"
date: "{publish_date}"
dateModified: "{date_modified}"
author:
  name: "Note Author"
  picture: "/assets/blog/authors/note_author.jpeg"
ogImage:
  url: "/assets/{date_str}_{hash_id}/{date_str}_{hash_id}_1.png"
---

"""
    
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(header + markdown)
    
    logger.info("プレビュー画像を保存中...")
    preview_filename = f"{date_str}_{hash_id}_preview.png"
    preview_dir = f"assets/{date_str}_{hash_id}"
    os.makedirs(preview_dir, exist_ok=True)
    preview_png_path = os.path.join(preview_dir, preview_filename)
    os.rename(png_path, preview_png_path)
    
    logger.info(f"記事の保存が完了: {md_path}")
    return md_path, preview_png_path, hash_id

def main():
    parser = argparse.ArgumentParser(description='Download note articles and convert to markdown')
    parser.add_argument('username', help='note username')
    args = parser.parse_args()

    config = configparser.ConfigParser()
    config.read('config.ini')
    login_username = config['credentials']['username']
    password = config['credentials']['password']

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            # ログインを行う
            login_to_note(page, login_username, password)
            
            # 全記事を取得
            articles = fetch_all_note_articles(page, args.username)
            logger.info(f"Found {len(articles)} articles")

            # ダウンロードモードの選択
            download_mode = input("すべての記事をダウンロードしますか？(y/n): ")
            if download_mode.lower() != 'y':
                # 特定の記事を選択
                logger.info("ダウンロードする記事を選択してください:")
                for index, article in enumerate(articles):
                    logger.info(f"{index + 1}. {article['title']}")

                selected_indices = input("ダウンロードする記事の番号をカンマ区切りで入力してください (例: 1,3,5): ")
                selected_indices = [int(x.strip()) for x in selected_indices.split(",")]
                selected_articles = [articles[i - 1] for i in selected_indices]
            else:
                selected_articles = articles

            for article in selected_articles:
                try:
                    logger.info(f"Processing article: {article['title']}")
                    
                    # 記事のHTMLを取得
                    html_content = download_html(page, article['link'])
                    
                    # HTMLをマークダウンに変換
                    markdown_content = html_to_markdown(html_content)
                    
                    # スクリーンショットを保存
                    temp_png = "temp_preview.png"
                    html_to_png(browser, html_content, temp_png)
                    
                    # コンテンツを保存
                    md_path, preview_path, hash_id = save_content(
                        article['title'],
                        markdown_content,
                        temp_png,
                        article['link'],
                        article['published'],
                        article['dateModified']
                    )
                    
                    if md_path:
                        logger.info(f"Successfully saved article to {md_path}")
                    
                except Exception as e:
                    logger.error(f"Error processing article {article['title']}: {e}")
                    logger.error(traceback.format_exc())
                    continue

            context.close()
            browser.close()

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    main()
