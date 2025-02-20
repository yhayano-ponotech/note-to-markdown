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

# ログ設定
logging.basicConfig(filename='error.log', level=logging.ERROR,
                    format='%(asctime)s - %(levelname)s - %(message)s')

def fetch_note_rss():
    rss_url = 'https://note.com/yas_bizdev/rss'
    if not rss_url:
        raise ValueError("RSS_URL environment variable is not set")
    if hasattr(ssl, '_create_unverified_context'):
        ssl._create_default_https_context = ssl._create_unverified_context
    feed = feedparser.parse(rss_url)
    print(f"Found {len(feed.entries)} entries in RSS feed")
    return feed.entries

def login_to_note(page, username, password):
    page.goto("https://note.com/login")
    page.wait_for_timeout(2000)  # ページ遷移後に少し待つ
    page.fill('#email', username)
    page.fill('#password', password)
    page.wait_for_timeout(1000)  # 入力後少し待つ
    # ログインボタンをクリック
    with page.expect_navigation():
        page.click('button:has-text("ログイン")')
    
    # ページの読み込みが完了するまで待つ
    page.wait_for_load_state('networkidle')
    
    page.wait_for_timeout(2000)
    
    # ログイン成功を確認
    if "login" in page.url:
        print("ログインに失敗しました。")
        return False
    else:
        print("ログインに成功しました。")
        return True

def download_html(page, url):
    page.goto(url)
    page.wait_for_load_state('networkidle', timeout=180000)
    return page.content()

def html_to_markdown(html):
    h = html2text.HTML2Text()
    h.ignore_links = False
    return h.handle(html)

def html_to_png(html, output_path):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html)
        page.screenshot(path=output_path, full_page=True)
        browser.close()

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

def save_images(markdown, hash_id):
    # 複数行に対応した正規表現
    image_pattern = r'!\[.*?\]\((.*?)\)'
    images = re.findall(image_pattern, markdown, re.DOTALL)

    print(f"Found {len(images)} images in markdown") # デバッグログ

    current_month = datetime.now().strftime("%Y-%m")
    assets_dir = f'assets/{current_month}'
    os.makedirs(assets_dir, exist_ok=True)

    for i, image_url in enumerate(images, start=1):
        # 改行文字を含むURLを、改行文字を削除したURLに置換
        markdown = markdown.replace(image_url, image_url.replace('\n', ''))

        # 改行文字を削除
        image_url = image_url.replace('\n', '')
        print(f"Downloading image from {image_url}") # デバッグログ

        if image_url.startswith("data:image"):
            # data URL は無視
            print(f"Ignoring data URL: {image_url}")
            continue

        # 通常の URL の場合
        try:
            response = requests.get(image_url)
            if response.status_code == 200:
                image_path = f'{assets_dir}/{hash_id}_{i}.png'
                with open(image_path, 'wb') as f:
                    f.write(response.content)
                # Markdown中のURLを相対パスに置換 (全ての出現箇所を置換)
                markdown = markdown.replace(image_url, f'/assets/{current_month}/{hash_id}_{i}.png')
                print(f"Saved image to {image_path}") # デバッグログ
            else:
                print(f"Failed to download image from {image_url}, status code: {response.status_code}") # デバッグログ
        except Exception as e:
            print(f"Error downloading image: {e}") # エラーログ

    return markdown

def save_content(title, markdown, png_path, url, publish_date):
    hash_id = get_hash_from_url(url)
    if not hash_id:
        raise ValueError(f"Could not extract hash from URL: {url}")
    
    posts_dir = '_posts'
    os.makedirs(posts_dir, exist_ok=True)
    
    md_path = os.path.join(posts_dir, f"{hash_id}.md")
    
    # Check if file already exists
    if os.path.exists(md_path):
        print(f"File {md_path} already exists. Skipping processing.")
        return None, None, hash_id
    
    # Process and save markdown
    markdown = remove_unwanted_lines(markdown)
    markdown = save_images(markdown, hash_id)
    
    # Prepare header
    header = f"""---
title: "{title}"
excerpt: "{markdown[:200]}..."
coverImage: "/assets/{datetime.now().strftime('%Y-%m')}/{hash_id}_1.png"
date: "{publish_date}"
author:
  name: "Note Author"
  picture: "/assets/blog/authors/note_author.jpeg"
ogImage:
  url: "/assets/{datetime.now().strftime('%Y-%m')}/{hash_id}_1.png"
---

"""
    
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(header + markdown)
    
    # Save preview image
    preview_png_path = f"assets/{datetime.now().strftime('%Y-%m')}/{hash_id}_preview.png"
    os.rename(png_path, preview_png_path)
    
    return md_path, preview_png_path, hash_id

def main():
    config = configparser.ConfigParser()
    config.read('config.ini')
    username = config['credentials']['username']
    password = config['credentials']['password']

    try:
        entries = fetch_note_rss()

        # ダウンロードモードの選択
        download_mode = input("すべての記事をダウンロードしますか？(y/n): ")
        if download_mode.lower() != 'y':
            # 特定の記事を選択
            print("ダウンロードする記事を選択してください:")
            for index, entry in enumerate(entries):
                print(f"{index + 1}. {entry.title}")

            selected_indices = input("ダウンロードする記事の番号をカンマ区切りで入力してください (例: 1,3,5): ")
            selected_indices = [int(x.strip()) for x in selected_indices.split(",")]
            selected_entries = [entries[i - 1] for i in selected_indices]
        else:
            selected_entries = entries

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # ログインを1回だけ行う
            login_to_note(page, username, password)

            for index, entry in enumerate(selected_entries, start=1):
                html = download_html(page, entry.link)
                markdown = html_to_markdown(html)

                temp_png_path = f"temp_{index}.png"
                page.screenshot(path=temp_png_path, full_page=True)

                md_path, png_path, hash_id = save_content(entry.title, markdown, temp_png_path, entry.link, entry.published)

                if md_path and png_path:
                    print(f"Processed #{index}: {entry.title} (Hash: {hash_id})")
                else:
                    print(f"Skipped #{index}: {entry.title} (Hash: {hash_id}) - Already exists")

            browser.close()

    except Exception as e:
        error_message = f"An error occurred: {str(e)}\n"
        error_message += traceback.format_exc()
        logging.error(error_message)
        print(error_message, file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
