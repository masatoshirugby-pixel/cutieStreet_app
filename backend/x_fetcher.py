import os
import logging
from typing import Optional

import tweepy

from models import TweetData

logger = logging.getLogger(__name__)

BEARER_TOKEN = os.getenv("X_BEARER_TOKEN", "")
TARGET_USERNAME = "CUTIE_STREET_"

_client: Optional[tweepy.Client] = None
_user_id_cache: Optional[str] = None


def _get_client() -> tweepy.Client:
    global _client
    if _client is None:
        _client = tweepy.Client(bearer_token=BEARER_TOKEN, wait_on_rate_limit=False)
    return _client


def get_user_id(username: str = TARGET_USERNAME) -> Optional[str]:
    global _user_id_cache
    if _user_id_cache:
        return _user_id_cache
    try:
        resp = _get_client().get_user(username=username)
        if resp.data:
            _user_id_cache = str(resp.data.id)
            return _user_id_cache
    except tweepy.errors.TweepyException as e:
        logger.error(f"ユーザーID取得失敗: {e}")
    return None


def fetch_latest_tweets(
    since_id: Optional[str] = None,
    max_results: int = 10,
) -> list[TweetData]:
    user_id = get_user_id()
    if not user_id:
        logger.error("ユーザーIDを取得できませんでした")
        return []

    try:
        resp = _get_client().get_users_tweets(
            id=user_id,
            max_results=max(5, min(max_results, 100)),
            since_id=since_id,
            tweet_fields=["created_at", "text"],
            exclude=["retweets", "replies"],
        )
    except tweepy.errors.TooManyRequests:
        logger.warning("X API レートリミット超過。次回まで待機します")
        return []
    except tweepy.errors.TweepyException as e:
        logger.error(f"ツイート取得失敗: {e}")
        return []

    if not resp.data:
        logger.info("新規ツイートなし")
        return []

    tweets = []
    for tweet in resp.data:
        posted_at = (
            tweet.created_at.isoformat().replace("+00:00", "Z")
            if tweet.created_at
            else ""
        )
        tweets.append(
            TweetData(
                post_id=str(tweet.id),
                post_text=tweet.text,
                posted_at=posted_at,
            )
        )

    logger.info(f"{len(tweets)} 件の新規ツイートを取得しました")
    return tweets
