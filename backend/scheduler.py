import asyncio
import logging
from datetime import datetime, timezone

import db
import x_fetcher
import claude_judge
from event_utils import extract_event_date, extract_venue, is_duplicate, ACCOUNTS
from models import EventRecord

logger = logging.getLogger(__name__)

FETCH_HOUR = 8  # 毎日 08:00 UTC に取得


def run_pipeline_for_account(
    account: str,
    start_time: str | None = None,
    max_results: int = 10,
) -> int:
    """指定アカウントの取得→判定→保存パイプライン。保存件数を返す"""
    since_id = db.get_latest_post_id(account) if not start_time else None
    tweets = x_fetcher.fetch_latest_tweets(
        username=account,
        since_id=since_id,
        start_time=start_time,
        max_results=max_results,
    )

    if not tweets:
        logger.info(f"[{account}] 新規ツイートなし。スキップ")
        return 0

    existing_records = db.get_recent_events_for_dedup(account=account, limit=100)

    saved = 0
    for tweet in tweets:
        if db.is_post_exists(tweet.post_id):
            continue

        judgement = claude_judge.judge_tweet(tweet.post_text)
        if not judgement.is_event:
            logger.info(f"[{account}] 非イベント判定: {tweet.post_id}")
            continue

        event_date = extract_event_date(tweet.post_text)
        event_date_str = event_date.isoformat() if event_date else None
        venue = extract_venue(tweet.post_text)

        if is_duplicate(
            new_text=tweet.post_text,
            new_category=judgement.category,
            new_event_date=event_date,
            existing_records=existing_records,
        ):
            logger.info(f"[{account}] 同一イベントのためスキップ: {tweet.post_id}")
            continue

        post_url = f"https://x.com/{account}/status/{tweet.post_id}"
        record = EventRecord(
            post_id=tweet.post_id,
            post_text=tweet.post_text,
            post_url=post_url,
            posted_at=tweet.posted_at,
            is_event=True,
            account=account,
            category=judgement.category,
            event_date=event_date_str,
            venue=venue,
            created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )

        if db.save_event(record):
            saved += 1
            existing_records.append({
                "post_text": tweet.post_text,
                "category": judgement.category,
                "event_date": event_date_str,
            })
            logger.info(
                f"[{account}] 保存: {tweet.post_id} "
                f"[{judgement.category}] event_date={event_date_str} venue={venue}"
            )

    return saved


def run_pipeline(
    start_time: str | None = None,
    max_results: int = 10,
) -> int:
    """全アカウントのパイプラインを実行。合計保存件数を返す"""
    total = 0
    for account in ACCOUNTS:
        total += run_pipeline_for_account(account, start_time=start_time, max_results=max_results)

    deleted = db.delete_expired_events()
    if deleted:
        logger.info(f"期限切れイベント {deleted} 件を削除しました")

    logger.info(f"パイプライン完了: 合計 {total} 件保存")
    return total


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
