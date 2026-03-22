"""
公式サイトのスクレイピングでイベント情報を取得する。

- スケジュール一覧: 一覧ページから直接日付・イベント情報を抽出（詳細ページ不要）
- ニュース一覧: 各記事の詳細ページへアクセスして情報を取得
"""

import hashlib
import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from models import TweetData

logger = logging.getLogger(__name__)

SCHEDULE_URLS: dict[str, str] = {
    "CUTIE_STREET_": "https://cutiestreet.asobisystem.com/live_information/schedule/list/",
    "CANDY_TUNE_":   "https://candytune.asobisystem.com/live_information/schedule/list/",
    "SWEET_STEADY":  "https://sweetsteady.asobisystem.com/live_information/schedule/list/",
}

NEWS_URLS: dict[str, list[str]] = {
    "CUTIE_STREET_": [
        "https://cutiestreet.asobisystem.com/news/1/",
        "https://cutiestreet.asobisystem.com/news/2/",
    ],
    "CANDY_TUNE_": [
        "https://candytune.asobisystem.com/news/1/",
        "https://candytune.asobisystem.com/news/2/",
    ],
    "SWEET_STEADY": [
        "https://sweetsteady.asobisystem.com/news/1/",
        "https://sweetsteady.asobisystem.com/news/2/",
    ],
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

MAX_NEWS_PAGES = 50  # ニュース詳細ページの最大取得数


def _fetch_soup(url: str) -> BeautifulSoup | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        logger.warning(f"ページ取得失敗 {url}: {e}")
        return None


def _load_next_data(soup: BeautifulSoup) -> dict:
    """__NEXT_DATA__ JSON を dict として返す"""
    script = soup.find("script", {"id": "__NEXT_DATA__"})
    if not script or not script.string:
        return {}
    try:
        return json.loads(script.string)
    except Exception:
        return {}


def _next_data_text(soup: BeautifulSoup) -> str:
    """__NEXT_DATA__ JSON をテキスト化して返す（日付抽出補完用）"""
    data = _load_next_data(soup)
    return json.dumps(data, ensure_ascii=False)[:4000] if data else ""


# -----------------------------------------------------------------------
# スケジュール一覧: __NEXT_DATA__ から直接抽出
# -----------------------------------------------------------------------

# 日付値を持つと判断する正規表現
_DATE_VAL_RE = re.compile(
    r'20\d{2}[-/\.]\d{1,2}[-/\.]\d{1,2}'  # 2026-03-07 / 2026.03.07 / 2026/3/7
    r'|(?<!\d)\d{1,2}[/月]\d{1,2}(?:\(.\))?'  # 3/7(土) / 3月7日
    r'|\d{2}\s+\d{2}\s+\[[A-Z]{2,3}\]'  # 03 01 [SUN]
)


def _find_schedule_items(obj, depth: int = 0) -> list[dict]:
    """
    JSON を再帰的に探索し、日付値を持つ dict のリストを返す。
    スケジュール一覧データがここに格納されていることが多い。
    """
    if depth > 8:
        return []

    if isinstance(obj, list) and obj:
        candidates = [
            item for item in obj
            if isinstance(item, dict) and any(
                isinstance(v, str) and _DATE_VAL_RE.search(v)
                for v in item.values()
            )
        ]
        if candidates:
            return candidates
        for item in obj:
            found = _find_schedule_items(item, depth + 1)
            if found:
                return found

    elif isinstance(obj, dict):
        best: list[dict] = []
        for v in obj.values():
            found = _find_schedule_items(v, depth + 1)
            if len(found) > len(best):
                best = found
        return best

    return []


def _fetch_schedule_from_list(url: str) -> list[TweetData]:
    """
    スケジュール一覧ページから各イベントを直接抽出する。
    詳細ページへのアクセスは行わない。
    """
    soup = _fetch_soup(url)
    if not soup:
        return []

    next_data = _load_next_data(soup)
    schedule_items = _find_schedule_items(next_data)
    results: list[TweetData] = []

    if schedule_items:
        for item in schedule_items:
            item_text = json.dumps(item, ensure_ascii=False)
            post_id = f"web_{hashlib.md5(item_text.encode()).hexdigest()[:12]}"
            results.append(TweetData(
                post_id=post_id,
                post_text=item_text,
                posted_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                image_url=None,
            ))
        logger.info(f"[Web:schedule] {url}: {len(results)} 件（__NEXT_DATA__）")
        return results

    # フォールバック: ページテキストから日付コンテキストを抽出
    nd_text = json.dumps(next_data, ensure_ascii=False) if next_data else ""
    page_text = soup.get_text(separator=" ", strip=True)
    combined = nd_text + " " + page_text

    seen: set[str] = set()
    for m in _DATE_VAL_RE.finditer(combined):
        date_str = m.group().strip()
        if date_str in seen or len(date_str) < 3:
            continue
        seen.add(date_str)
        ctx = combined[max(0, m.start() - 50): min(len(combined), m.end() + 250)].strip()
        post_id = f"web_{hashlib.md5((url + date_str).encode()).hexdigest()[:12]}"
        results.append(TweetData(
            post_id=post_id,
            post_text=ctx,
            posted_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            image_url=None,
        ))

    logger.info(f"[Web:schedule] {url}: {len(results)} 件（テキストフォールバック）")
    return results


# -----------------------------------------------------------------------
# ニュース一覧: 詳細ページへアクセスして情報を取得
# -----------------------------------------------------------------------

def _extract_news_links(soup: BeautifulSoup, base_url: str) -> list[str]:
    """ニュース一覧ページから詳細ページリンクを抽出する"""
    base_domain = urlparse(base_url).netloc
    links: list[str] = []

    # __NEXT_DATA__ から /news/.../detail/... パスを抽出
    next_data = _load_next_data(soup)
    if next_data:
        text = json.dumps(next_data)
        paths = re.findall(r'"(/news/(?:[^"]*?/)?detail/[^"]{1,60})"', text)
        seen: set[str] = set()
        for path in paths:
            if "#" in path or "?" in path:
                continue
            full = f"https://{base_domain}{path}"
            if full not in seen:
                seen.add(full)
                links.append(full)
        if links:
            return links[:MAX_NEWS_PAGES]

    # フォールバック: <a> タグから /news/ かつ /detail/ を含むリンクを抽出
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/news/" in href and "/detail/" in href:
            full = urljoin(base_url, href)
            if urlparse(full).netloc == base_domain and full not in seen:
                seen.add(full)
                links.append(full)

    return links[:MAX_NEWS_PAGES]


def _soup_to_tweet(url: str, soup: BeautifulSoup) -> TweetData:
    page_title = soup.title.get_text(strip=True) if soup.title else ""
    headings = " ".join(
        tag.get_text(separator="", strip=True)
        for tag in soup.find_all(["h1", "h2", "h3"])
    )
    body = soup.get_text(separator=" ", strip=True)[:2000]
    nd = _next_data_text(soup)
    post_id = f"web_{hashlib.md5(url.encode()).hexdigest()[:12]}"
    return TweetData(
        post_id=post_id,
        post_text=f"{page_title} {headings} {body} {nd}",
        posted_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        image_url=None,
    )


def _fetch_news_detail(link: str) -> TweetData | None:
    time.sleep(0.2)
    detail_soup = _fetch_soup(link)
    if not detail_soup:
        return None
    return _soup_to_tweet(link, detail_soup)


def _fetch_news_events(news_urls: list[str]) -> list[TweetData]:
    """ニュース一覧から記事詳細ページへアクセスしてイベント情報を取得する"""
    all_links: list[str] = []
    seen_links: set[str] = set()

    for url in news_urls:
        soup = _fetch_soup(url)
        if not soup:
            continue
        for link in _extract_news_links(soup, url):
            if link not in seen_links:
                seen_links.add(link)
                all_links.append(link)

    results: list[TweetData] = []
    seen_ids: set[str] = set()

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(_fetch_news_detail, link): link for link in all_links}
        for future in as_completed(futures):
            td = future.result()
            if td and td.post_id not in seen_ids:
                results.append(td)
                seen_ids.add(td.post_id)

    logger.info(f"[Web:news] {len(all_links)} 件リンク → {len(results)} 件取得")
    return results


# -----------------------------------------------------------------------
# メインエントリポイント
# -----------------------------------------------------------------------

def fetch_web_events(account: str) -> list[TweetData]:
    """公式サイトのイベント情報を取得する"""
    results: list[TweetData] = []
    seen_ids: set[str] = set()

    # スケジュール一覧: 詳細ページへのアクセスなし
    schedule_url = SCHEDULE_URLS.get(account)
    if schedule_url:
        for td in _fetch_schedule_from_list(schedule_url):
            if td.post_id not in seen_ids:
                results.append(td)
                seen_ids.add(td.post_id)

    # ニュース: 詳細ページへアクセス
    for td in _fetch_news_events(NEWS_URLS.get(account, [])):
        if td.post_id not in seen_ids:
            results.append(td)
            seen_ids.add(td.post_id)

    logger.info(f"[Web:{account}] {len(results)} 件取得")
    return results
