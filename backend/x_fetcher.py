"""
X投稿取得モジュール
Tweepy (X API v2) で投稿を取得する。画像・ページネーション対応。
"""

import logging
import os
from typing import Optional

import tweepy

from models import TweetData

logger = logging.getLogger(__name__)

BEARER_TOKEN = os.getenv("X_BEARER_TOKEN", "")
MAX_PAGES = 10  # ページネーション上限（1ページ最大100件）

_client: Optional[tweepy.Client] = None
_user_id_cache: dict[str, str] = {}


def _get_client() -> tweepy.Client:
    global _client
    if _client is None:
        _client = tweepy.Client(bearer_token=BEARER_TOKEN, wait_on_rate_limit=False)
    return _client


def get_user_id(username: str) -> Optional[str]:
    if username in _user_id_cache:
        return _user_id_cache[username]
    try:
        resp = _get_client().get_user(username=username)
        if resp.data:
            _user_id_cache[username] = str(resp.data.id)
            return _user_id_cache[username]
    except tweepy.errors.TweepyException as e:
        logger.error(f"ユーザーID取得失敗: {e}")
    return None


def _extract_image_url(resp, tweet) -> Optional[str]:
    """レスポンスからツイートの最初の画像URLを取得する"""
    try:
        if not hasattr(tweet, "attachments") or not tweet.attachments:
            return None
        media_keys = tweet.attachments.get("media_keys", [])
        if not media_keys or not resp.includes or "media" not in resp.includes:
            return None
        media_map = {m.media_key: m for m in resp.includes["media"]}
        media = media_map.get(media_keys[0])
        if not media:
            return None
        return getattr(media, "url", None) or getattr(media, "preview_image_url", None)
    except Exception:
        return None


def fetch_latest_tweets(
    username: str,
    since_id: Optional[str] = None,
    start_time: Optional[str] = None,
    max_results: int = 10,
) -> list[TweetData]:
    """
    ツイートを取得して TweetData リストで返す。
    start_time 指定時はページネーションで全件取得（最大 MAX_PAGES ページ）。
    """
    user_id = get_user_id(username)
    if not user_id:
        logger.error(f"[{username}] ユーザーIDを取得できませんでした")
        return []

    tweets: list[TweetData] = []
    next_token: Optional[str] = None
    page = 0

    while page < MAX_PAGES:
        try:
            resp = _get_client().get_users_tweets(
                id=user_id,
                max_results=max(5, min(max_results, 100)),
                since_id=since_id,
                start_time=start_time,
                pagination_token=next_token,
                tweet_fields=["created_at", "text", "attachments"],
                media_fields=["url", "preview_image_url"],
                expansions=["attachments.media_keys"],
                exclude=["retweets", "replies"],
            )
        except tweepy.errors.TooManyRequests:
            logger.warning(f"[{username}] レートリミット超過")
            break
        except tweepy.errors.TweepyException as e:
            logger.error(f"[{username}] ツイート取得失敗: {e}")
            break

        if not resp.data:
            break

        for tweet in resp.data:
            posted_at = (
                tweet.created_at.isoformat().replace("+00:00", "Z")
                if tweet.created_at else ""
            )
            image_url = _extract_image_url(resp, tweet)
            tweets.append(TweetData(
                post_id=str(tweet.id),
                post_text=tweet.text,
                posted_at=posted_at,
                image_url=image_url,
            ))

        page += 1
        meta = getattr(resp, "meta", None)
        next_token = meta.get("next_token") if meta else None

        if not next_token:
            break

    logger.info(f"[{username}] {len(tweets)} 件取得（{page}ページ）")
    return tweets
