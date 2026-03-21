import asyncio
import logging
from datetime import datetime, timezone

import db
import x_fetcher
import claude_judge
from event_utils import extract_event_date, is_duplicate
from models import EventRecord

logger = logging.getLogger(__name__)

FETCH_HOUR = 8  # 毎日 08:00 UTC に取得


def run_pipeline() -> int:
    """X取得 → イベント判定 → 重複検出 → DB保存のパイプライン。保存件数を返す"""
    since_id = db.get_latest_post_id()
    tweets = x_fetcher.fetch_latest_tweets(since_id=since_id)

    if not tweets:
        logger.info("新規ツイートなし。スキップ")
        return 0

    # 重複検出用に既存イベントを取得（パイプライン実行前に一度だけ取得）
    existing_records = db.get_recent_events_for_dedup(limit=100)

    saved = 0
    for tweet in tweets:
        if db.is_post_exists(tweet.post_id):
            continue

        # イベント判定
        judgement = claude_judge.judge_tweet(tweet.post_text)
        if not judgement.is_event:
            logger.info(f"非イベント判定: {tweet.post_id}")
            continue

        # イベント日付を抽出
        event_date = extract_event_date(tweet.post_text)
        event_date_str = event_date.isoformat() if event_date else None

        # 同一イベント重複検出
        if is_duplicate(
            new_text=tweet.post_text,
            new_category=judgement.category,
            new_event_date=event_date,
            existing_records=existing_records,
        ):
            logger.info(f"同一イベントのためスキップ: {tweet.post_id}")
            continue

        post_url = f"https://x.com/{x_fetcher.TARGET_USERNAME}/status/{tweet.post_id}"
        record = EventRecord(
            post_id=tweet.post_id,
            post_text=tweet.post_text,
            post_url=post_url,
            posted_at=tweet.posted_at,
            is_event=True,
            category=judgement.category,
            event_date=event_date_str,
            created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )

        if db.save_event(record):
            saved += 1
            # 次の重複検出のために existing_records に追加
            existing_records.append({
                "post_text": tweet.post_text,
                "category": judgement.category,
                "event_date": event_date_str,
            })
            logger.info(f"保存: {tweet.post_id} [{judgement.category}] event_date={event_date_str}")

    # 期限切れイベントを削除（2週間経過）
    deleted = db.delete_expired_events()
    if deleted:
        logger.info(f"期限切れイベント {deleted} 件を削除しました")

    logger.info(f"パイプライン完了: {saved} 件保存")
    return saved


async def run_loop() -> None:
    """毎日 FETCH_HOUR 時に run_pipeline を実行するループ"""
    while True:
        now = datetime.now(timezone.utc)
        next_run = now.replace(hour=FETCH_HOUR, minute=0, second=0, microsecond=0)
        if now >= next_run:
            from datetime import timedelta
            next_run += timedelta(days=1)

        wait_seconds = (next_run - now).total_seconds()
        logger.info(f"次回取得: {next_run.isoformat()} ({wait_seconds:.0f}秒後)")

        await asyncio.sleep(wait_seconds)

        try:
            await asyncio.to_thread(run_pipeline)
        except Exception as e:
            logger.error(f"スケジューラーエラー: {e}")
