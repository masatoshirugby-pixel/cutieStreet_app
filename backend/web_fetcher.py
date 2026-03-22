"""
公式サイトのニュース・スケジュールページをスクレイピングして
イベント情報を取得する。リンク先の詳細ページも追跡する。
"""

import hashlib
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from models import TweetData

logger = logging.getLogger(__name__)

SITE_URLS: dict[str, list[str]] = {
    "CUTIE_STREET_": [
        "https://cutiestreet.asobisystem.com/news/1/",
        "https://cutiestreet.asobisystem.com/live_information/schedule/list/",
    ],
    "CANDY_TUNE_": [
        "https://candytune.asobisystem.com/news/1/",
        "https://candytune.asobisystem.com/live_information/schedule/list/",
    ],
    "SWEET_STEADY": [
        "https://sweetsteady.asobisystem.com/live_information/schedule/list/",
        "https://sweetsteady.asobisystem.com/news/1/",
    ],
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

MAX_DETAIL_PAGES = 50  # 1つの一覧ページから追跡する詳細ページの上限


def _fetch_soup(url: str) -> BeautifulSoup | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        logger.warning(f"ページ取得失敗 {url}: {e}")
        return None


def _extract_links_from_next_data(soup: BeautifulSoup, base_url: str) -> list[str]:
    """
    Next.js の __NEXT_DATA__ JSON からリンクを抽出する。
    asobisystem.com は Next.js 製のため通常の <a> タグでは取得できない。
    """
    import json
    base_domain = urlparse(base_url).netloc
    links: list[str] = []

    script = soup.find("script", {"id": "__NEXT_DATA__"})
    if not script:
        return links

    try:
        data = json.loads(script.string)
        # JSON を文字列化して URL パターンを正規表現で抽出
        import re
        text = json.dumps(data)
        # /news/detail/XXXXX や /live_information/schedule/detail/XXXXX 等のパス
        paths = re.findall(r'"(/(?:news|live_information)/(?:[^"]*?/)?detail/[^"]{1,60})"', text)
        seen: set[str] = set()
        for path in paths:
            if "#" in path or "?" in path:
                continue
            full = f"https://{base_domain}{path}"
            if full not in seen and full != base_url:
                seen.add(full)
                links.append(full)
    except Exception as e:
        logger.warning(f"__NEXT_DATA__ パース失敗 {base_url}: {e}")

    return links[:MAX_DETAIL_PAGES]


def _get_article_links(soup: BeautifulSoup, base_url: str) -> list[str]:
    """一覧ページから詳細ページリンクを抽出する（Next.js対応）"""
    # まず __NEXT_DATA__ から試みる
    links = _extract_links_from_next_data(soup, base_url)
    if links:
        return links

    # フォールバック: 通常の <a> タグ
    base_domain = urlparse(base_url).netloc
    seen: set[str] = set()
    result: list[str] = []
    for a in soup.find_all("a", href=True):
        full = urljoin(base_url, a["href"])
        if (
            urlparse(full).netloc == base_domain
            and full not in seen
            and full != base_url
            and "#" not in full
        ):
            seen.add(full)
            result.append(full)
    return result[:MAX_DETAIL_PAGES]


def _soup_to_tweet(url: str, soup: BeautifulSoup) -> TweetData:
    # <title> タグ
    page_title = soup.title.get_text(strip=True) if soup.title else ""
    # 記事タイトル: separator="" で「3\n/29」のような分断を防ぐ
    headings = " ".join(
        tag.get_text(separator="", strip=True)
        for tag in soup.find_all(["h1", "h2", "h3"])
    )
    body = soup.get_text(separator=" ", strip=True)[:2000]
    post_id = f"web_{hashlib.md5(url.encode()).hexdigest()[:12]}"
    # headings を先頭に置くことで日付抽出の精度を上げる
    post_text = f"{page_title} {headings} {body}"
    return TweetData(
        post_id=post_id,
        post_text=post_text,
        posted_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        image_url=None,
    )


def _fetch_detail(link: str) -> TweetData | None:
    """詳細ページ1件を取得して TweetData に変換する（並列実行用）"""
    time.sleep(0.2)  # サーバー負荷軽減
    detail_soup = _fetch_soup(link)
    if not detail_soup:
        return None
    return _soup_to_tweet(link, detail_soup)


def fetch_web_events(account: str) -> list[TweetData]:
    """公式サイトのイベント情報を取得する（詳細ページを並列取得）"""
    base_urls = SITE_URLS.get(account, [])
    all_links: list[str] = []
    seen_links: set[str] = set()

    for base_url in base_urls:
        soup = _fetch_soup(base_url)
        if not soup:
            continue
        for link in _get_article_links(soup, base_url):
            if link not in seen_links:
                seen_links.add(link)
                all_links.append(link)

    results: list[TweetData] = []
    seen_ids: set[str] = set()

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(_fetch_detail, link): link for link in all_links}
        for future in as_completed(futures):
            td = future.result()
            if td and td.post_id not in seen_ids:
                results.append(td)
                seen_ids.add(td.post_id)

    logger.info(f"[Web:{account}] {len(results)} 件取得")
    return results
