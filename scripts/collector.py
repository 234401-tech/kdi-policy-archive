import argparse
import json
import os
import hashlib
from datetime import datetime, timezone, timedelta
import urllib.request
import xml.etree.ElementTree as ET
from classifier import load_categories, classify_item
import sys
import requests # type: ignore
import feedparser # type: ignore
from bs4 import BeautifulSoup # type: ignore

RSS_URL = "https://eiec.kdi.re.kr/policy/rss.do?rss_type=material"
ARCHIVE_PATH = "docs/data/archive.json"
CATEGORIES_PATH = "docs/data/categories.json"
KST = timezone(timedelta(hours=9))

FETCH_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Accept': 'application/rss+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.5',
    'Referer': 'https://eiec.kdi.re.kr/policy/materialList.do',
}

def fetch_rss(url, retries=3):
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=FETCH_HEADERS, timeout=10, verify=False)
            response.raise_for_status()
            return response.content
        except requests.exceptions.RequestException as e:
            print(f"Fetch attempt {attempt + 1} failed: {e}")
    raise Exception("Failed to fetch RSS after 3 attempts")

def parse_rss(xml_content):
    feed = feedparser.parse(xml_content)
    items = []
    for entry in feed.entries:
        link = entry.link
        item_id = hashlib.md5(link.encode('utf-8')).hexdigest()
        
        # Clean description HTML tags
        description = entry.description if 'description' in entry else ""
        if description:
            soup = BeautifulSoup(description, "html.parser")
            description = soup.get_text(separator=" ", strip=True)
            
        pub_date = entry.published if 'published' in entry else ""
        category = entry.category if 'category' in entry else ""
        
        item = {
            "id": item_id,
            "title": entry.title,
            "link": link,
            "description": description,
            "pub_date": pub_date,
            "author": entry.author if 'author' in entry else "",
            "original_category": category,
            "collected_at": datetime.now(KST).isoformat()
        }
        items.append(item)
    return items

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reclassify", action="store_true", help="Reclassify all items")
    args = parser.parse_args()

    # Load categories
    if not os.path.exists(CATEGORIES_PATH):
        print(f"Error: {CATEGORIES_PATH} not found.")
        sys.exit(1)
    categories_config = load_categories(CATEGORIES_PATH)

    # Load existing archive
    archive = {"items": []}
    if os.path.exists(ARCHIVE_PATH):
        try:
            with open(ARCHIVE_PATH, 'r', encoding='utf-8') as f:
                archive = json.load(f)
        except json.JSONDecodeError:
            pass

    existing_items = {item['id']: item for item in archive.get('items', [])}
    
    if args.reclassify:
        print("Reclassifying all existing items...")
        for item_id, item in existing_items.items():
            item['matched_categories'] = classify_item(item, categories_config)
        new_count = 0
    else:
        # Fetch and parse RSS
        print("Fetching RSS...")
        try:
            xml_content = fetch_rss(RSS_URL)
            new_items = parse_rss(xml_content)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

        # 차단 페이지가 HTTP 200으로 오면 파싱 결과가 빈 목록이 되어
        # '신규 0건 성공'으로 위장됨 — 빈 피드는 실패로 처리해 드러낸다.
        if not new_items:
            head = xml_content[:300].decode("utf-8", "replace")
            print("RSS returned no items - likely blocked or format changed.")
            print(f"Response head: {head}")
            sys.exit(1)

        new_count = 0
        for item in new_items:
            if item['id'] not in existing_items:
                item['matched_categories'] = classify_item(item, categories_config)
                existing_items[item['id']] = item
                new_count += 1
                
    # Save back to archive
    all_items = list(existing_items.values())
    # Sort by pub_date descending, if parsing pub_date fails, use collected_at
    all_items.sort(key=lambda x: x.get('pub_date', x.get('collected_at', '')), reverse=True)
    
    archive['items'] = all_items
    archive['total_count'] = len(all_items)
    archive['last_updated'] = datetime.now(KST).isoformat()
    archive['source'] = RSS_URL

    os.makedirs(os.path.dirname(ARCHIVE_PATH), exist_ok=True)
    with open(ARCHIVE_PATH, 'w', encoding='utf-8') as f:
        json.dump(archive, f, ensure_ascii=False, indent=2)

    print(f"Total items: {len(all_items)}")
    print(f"New items added: {new_count}")

if __name__ == "__main__":
    main()
