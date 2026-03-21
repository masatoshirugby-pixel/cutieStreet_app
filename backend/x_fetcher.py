"""
X投稿取得モジュール
RSSHub 経由で CUTIE_STREET_ の投稿を取得する（X API 不要）。
"""

import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser

from models import TweetData

logger = logging.getLogger(__name__)

TARGET_USERNAME = "CUTIE_STREET_"
RSSHUB_URL = f"https://rsshub.app/twitter/user/{TARGET_USERNAME}"

_POST_ID_RE = re.compile(r"/status/(\d+)")


def _parse_post_id(url: str) -> str | None:
    """ツイートURLから post_id を抽出する"""
    m = _POST_ID_RE.search(url)
    return m.group(1) if m else None


def _parse_date(entry) -> str:
    """RSS エントリから ISO8601 UTC 日時文字列を取得する"""
    # feedparser は published_parsed (time.struct_time UTC) を持つことが多い
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")
    # fallback: published 文字列をパース
    if hasattr(entry, "published") and entry.published:
        try:
            dt = parsedate_to_datetime(entry.published).astimezone(timezone.utc)
            return dt.isoformat().replace("+00:00", "Z")
        except Exception:
            pass
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch_latest_tweets(
    since_id: str | None = None,
    max_results: int = 20,
) -> list[TweetData]:
    """
    RSSHub から最新ツイートを取得して TweetData リストで返す。
    since_id より古い（または同じ）ものはスキップする。
    """
    try:
        feed = feedparser.parse(RSSHUB_URL)
    except Exception as e:
        logger.error(f"RSS 取得失敗: {e}")
        return []

    if feed.bozo and not feed.entries:
        logger.error(f"RSS パース失敗: {feed.bozo_exception}")
        return []

    tweets: list[TweetData] = []
    for entry in feed.entries[:max_results]:
        url = entry.get("link", "")
        post_id = _parse_post_id(url)
        if not post_id:
            continue

        # since_id より古いものはスキップ
        if since_id and int(post_id) <= int(since_id):
            continue

        # 本文: summary または title を使用（HTMLタグを除去）
        raw_text = entry.get("summary") or entry.get("title", "")
        text = re.sub(r"<[^>]+>", "", raw_text).strip()

        tweets.append(
            TweetData(
                post_id=post_id,
                post_text=text,
                posted_at=_parse_date(entry),
            )
        )

    logger.info(f"{len(tweets)} 件の新規ツイートを取得しました")
    return tweets
