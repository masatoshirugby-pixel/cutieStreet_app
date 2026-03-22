"""
公式サイトのスクレイピングでイベント情報を取得する。

- スケジュール一覧: <a href="/live_information/detail/..."> を解析して直接抽出
- ニュース一覧: 一時停止中（コメントアウト）
"""

import hashlib
import logging
import re
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

# ニュース（一時停止中）
# NEWS_URLS: dict[str, list[str]] = {
#     "CUTIE_STREET_": [
#         "https://cutiestreet.asobisystem.com/news/1/",
#         "https://cutiestreet.asobisystem.com/news/1/?page=2",
#     ],
#     "CANDY_TUNE_": [
#         "https://candytune.asobisystem.com/news/1/",
#         "https://candytune.asobisystem.com/news/1/?page=2",
#     ],
#     "SWEET_STEADY": [
#         "https://sweetsteady.asobisystem.com/news/1/",
#         "https://sweetsteady.asobisystem.com/news/1/?page=2",
#     ],
# }

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

# スケジュールエントリが日付を持つと判断する正規表現（_DATE_VAL_RE と同等）
_DATE_VAL_RE = re.compile(
    r'20\d{2}[-/\.]\d{1,2}[-/\.]\d{1,2}'  # 2026-03-07 / 2026.03.07 / 2026/3/7
    r'|(?<!\d)\d{1,2}[/月]\d{1,2}(?:\(.\))?'  # 3/7(土) / 3月7日
    r'|\d{2}\s+\d{2}\s+\[[A-Z]{2,3}\]'  # 03 01 [SUN]
)


def _fetch_soup(url: str) -> BeautifulSoup | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        logger.warning(f"ページ取得失敗 {url}: {e}")
        return None


# -----------------------------------------------------------------------
# スケジュール一覧: <a href="/live_information/detail/..."> を直接解析
# -----------------------------------------------------------------------

def _find_next_month_url(soup: BeautifulSoup, base_url: str) -> str | None:
    """スケジュールページの翌月リンクを探して返す（存在しない場合は None）"""
    base_path = urlparse(base_url).path
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # 翌月リンクは /live_information/schedule/list/ + クエリパラメータの形式
        if "/live_information/schedule/list/" in href and "?" in href:
            return urljoin(base_url, href)
    return None


def _fetch_schedule_from_list(url: str) -> list[TweetData]:
    """
    スケジュール一覧ページの <a href="/live_information/detail/..."> を解析して
    イベント一覧を返す。詳細ページへのアクセスは行わない。
    """
    soup = _fetch_soup(url)
    if not soup:
        return []

    results: list[TweetData] = []
    seen_ids: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/live_information/detail/" not in href:
            continue

        post_text = a.get_text(separator=" ", strip=True)
        if not post_text or not _DATE_VAL_RE.search(post_text):
            continue

        # 詳細ページのパスをキーとして安定した post_id を生成
        post_id = f"sched_{hashlib.md5(href.encode()).hexdigest()[:12]}"
        if post_id in seen_ids:
            continue
        seen_ids.add(post_id)

        results.append(TweetData(
            post_id=post_id,
            post_text=post_text,
            posted_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            image_url=None,
        ))

    # 翌月があればそちらも取得
    next_url = _find_next_month_url(soup, url)
    if next_url:
        next_soup = _fetch_soup(next_url)
        if next_soup:
            for a in next_soup.find_all("a", href=True):
                href = a["href"]
                if "/live_information/detail/" not in href:
                    continue
                post_text = a.get_text(separator=" ", strip=True)
                if not post_text or not _DATE_VAL_RE.search(post_text):
                    continue
                post_id = f"sched_{hashlib.md5(href.encode()).hexdigest()[:12]}"
                if post_id in seen_ids:
                    continue
                seen_ids.add(post_id)
                results.append(TweetData(
                    post_id=post_id,
                    post_text=post_text,
                    posted_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    image_url=None,
                ))

    logger.info(f"[Web:schedule] {url}: {len(results)} 件")
    return results


# -----------------------------------------------------------------------
# ニュース一覧（一時停止中）
# -----------------------------------------------------------------------

# def _extract_news_links(soup: BeautifulSoup, base_url: str) -> list[str]:
#     ...
#
# def _soup_to_tweet(url: str, soup: BeautifulSoup) -> TweetData:
#     ...
#
# def _fetch_news_detail(link: str) -> TweetData | None:
#     ...
#
# def _fetch_news_events(news_urls: list[str]) -> list[TweetData]:
#     ...


# -----------------------------------------------------------------------
# メインエントリポイント
# -----------------------------------------------------------------------

def fetch_web_events(account: str) -> list[TweetData]:
    """公式サイトのイベント情報を取得する（現在はスケジュールのみ）"""
    results: list[TweetData] = []
    seen_ids: set[str] = set()

    # スケジュール一覧
    schedule_url = SCHEDULE_URLS.get(account)
    if schedule_url:
        for td in _fetch_schedule_from_list(schedule_url):
            if td.post_id not in seen_ids:
                results.append(td)
                seen_ids.add(td.post_id)

    # ニュース（一時停止中）
    # for td in _fetch_news_events(NEWS_URLS.get(account, [])):
    #     if td.post_id not in seen_ids:
    #         results.append(td)
    #         seen_ids.add(td.post_id)

    logger.info(f"[Web:{account}] {len(results)} 件取得")
    return results
