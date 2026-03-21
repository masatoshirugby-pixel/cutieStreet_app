"""
YouTube Data API v3 を使って各グループの最新動画を取得する。
playlistItems.list を使用（search.list より低コスト）。
"""

import logging
import os

import requests

from models import TweetData

logger = logging.getLogger(__name__)

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
BASE_URL = "https://www.googleapis.com/youtube/v3"

# アカウント → YouTube チャンネルハンドル
CHANNEL_HANDLES: dict[str, str] = {
    "CUTIE_STREET_": "CUTIE_STREET",
    "CANDY_TUNE_":   "candy_tune",
    "SWEET_STEADY":  "SWEET_STEADY",
}

_uploads_playlist_cache: dict[str, str] = {}


def _get_uploads_playlist_id(handle: str) -> str | None:
    if handle in _uploads_playlist_cache:
        return _uploads_playlist_cache[handle]

    resp = requests.get(
        f"{BASE_URL}/channels",
        params={"key": YOUTUBE_API_KEY, "forHandle": handle, "part": "contentDetails"},
        timeout=10,
    )
    if not resp.ok:
        logger.error(f"[YouTube] チャンネル取得失敗 handle={handle}: {resp.status_code}")
        return None

    items = resp.json().get("items", [])
    if not items:
        logger.warning(f"[YouTube] チャンネルが見つかりません handle={handle}")
        return None

    playlist_id = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    _uploads_playlist_cache[handle] = playlist_id
    return playlist_id


def fetch_latest_videos(
    account: str,
    published_after: str | None = None,
    max_results: int = 10,
) -> list[TweetData]:
    if not YOUTUBE_API_KEY:
        logger.warning("[YouTube] YOUTUBE_API_KEY が設定されていません")
        return []

    handle = CHANNEL_HANDLES.get(account)
    if not handle:
        return []

    playlist_id = _get_uploads_playlist_id(handle)
    if not playlist_id:
        return []

    resp = requests.get(
        f"{BASE_URL}/playlistItems",
        params={
            "key": YOUTUBE_API_KEY,
            "playlistId": playlist_id,
            "part": "snippet",
            "maxResults": max_results,
        },
        timeout=10,
    )
    if not resp.ok:
        logger.error(f"[YouTube:{account}] 動画一覧取得失敗: {resp.status_code}")
        return []

    results: list[TweetData] = []
    for item in resp.json().get("items", []):
        snippet = item.get("snippet", {})
        video_id = snippet.get("resourceId", {}).get("videoId")
        if not video_id:
            continue

        published_at = snippet.get("publishedAt", "")
        if published_after and published_at < published_after:
            continue

        title = snippet.get("title", "")
        description = snippet.get("description", "")
        thumbnail = (
            snippet.get("thumbnails", {}).get("high", {}).get("url")
            or snippet.get("thumbnails", {}).get("default", {}).get("url")
        )

        results.append(TweetData(
            post_id=f"yt_{video_id}",
            post_text=f"{title}\n{description}",
            posted_at=published_at,
            image_url=thumbnail,
        ))

    logger.info(f"[YouTube:{account}] {len(results)} 件取得")
    return results
