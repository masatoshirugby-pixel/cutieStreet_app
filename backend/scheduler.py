import asyncio
import logging
from datetime import datetime, timezone

import db
import x_fetcher
import youtube_fetcher
import web_fetcher
import email_fetcher
import claude_judge
from event_utils import extract_event_date, extract_venue, is_duplicate, ACCOUNTS
from models import EventRecord, EmailRecord

logger = logging.getLogger(__name__)

FETCH_HOUR = 8  # 毎日 08:00 UTC に取得


# -----------------------------------------------------------------------
# X パイプライン
# -----------------------------------------------------------------------

def run_x_for_account(
    account: str,
    start_time: str | None = None,
    max_results: int = 10,
) -> int:
    since_id = db.get_latest_post_id(account) if not start_time else None
    tweets = x_fetcher.fetch_latest_tweets(
        username=account,
        since_id=since_id,
        start_time=start_time,
        max_results=max_results,
    )
    if not tweets:
        logger.info(f"[X:{account}] 新規ツイートなし。スキップ")
        return 0
    return _save_tweet_data(tweets, account, source="x")


# -----------------------------------------------------------------------
# YouTube パイプライン
# -----------------------------------------------------------------------

def run_youtube_for_account(account: str, published_after: str | None = None) -> int:
    videos = youtube_fetcher.fetch_latest_videos(account, published_after=published_after)
    if not videos:
        return 0
    return _save_tweet_data(videos, account, source="youtube")


# -----------------------------------------------------------------------
# Web スクレイピングパイプライン
# -----------------------------------------------------------------------

def run_web_for_account(account: str) -> int:
    pages = web_fetcher.fetch_web_events(account)
    if not pages:
        return 0
    return _save_tweet_data(pages, account, source="web")


# -----------------------------------------------------------------------
# 共通: TweetData → 判定 → DB保存
# -----------------------------------------------------------------------

def _save_tweet_data(tweets, account: str, source: str) -> int:
    existing_records = db.get_recent_events_for_dedup(account=account, limit=100)
    saved = 0

    for tweet in tweets:
        if db.is_post_exists(tweet.post_id):
            continue

        judgement = claude_judge.judge_tweet(tweet.post_text)
        if not judgement.is_event:
            logger.info(f"[{source}:{account}] 非イベント判定: {tweet.post_id}")
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
            logger.info(f"[{source}:{account}] 重複スキップ: {tweet.post_id}")
            continue

        post_url = (
            f"https://x.com/{account}/status/{tweet.post_id}"
            if source == "x"
            else tweet.post_id  # YouTube/Web は post_id に URL を格納
        )
        # YouTube の場合は正しい URL を組み立て
        if source == "youtube" and tweet.post_id.startswith("yt_"):
            video_id = tweet.post_id[3:]
            post_url = f"https://www.youtube.com/watch?v={video_id}"
        # Web の場合は post_text から元 URL を復元できないので post_id をキーとして使用
        if source == "web":
            post_url = ""

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
            image_url=tweet.image_url,
            source=source,
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
                f"[{source}:{account}] 保存: {tweet.post_id} "
                f"[{judgement.category}] event_date={event_date_str}"
            )

    return saved


# -----------------------------------------------------------------------
# メールパイプライン
# -----------------------------------------------------------------------

def run_email_pipeline() -> int:
    from event_utils import extract_event_date as _extract_date

    emails = email_fetcher.fetch_emails()
    saved = 0

    for mail in emails:
        if db.is_email_exists(mail["message_id"]):
            continue

        body_full = mail.get("body_full", "")
        deadline = _extract_date(f"{mail['subject']} {body_full}")
        deadline_str = deadline.isoformat() if deadline else None

        record = EmailRecord(
            message_id=mail["message_id"],
            account=mail["account"],
            subject=mail["subject"],
            sender=mail["sender"],
            received_at=mail["received_at"],
            body_preview=mail["body_preview"],
            deadline_date=deadline_str,
            created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )

        if db.save_email(record):
            saved += 1
            logger.info(
                f"[Email:{mail['account']}] 保存: {mail['subject'][:40]} "
                f"deadline={deadline_str}"
            )

            # 締め切り日付があればカレンダーにも追加
            if deadline_str:
                event_record = EventRecord(
                    post_id=f"email_{mail['message_id'][:40]}",
                    post_text=f"【メール】{mail['subject']}\n{mail['body_preview']}",
                    post_url="",
                    posted_at=mail["received_at"],
                    is_event=True,
                    account=mail["account"],
                    category="申込締切",
                    event_date=deadline_str,
                    venue=None,
                    image_url=None,
                    source="email",
                    created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                )
                db.save_event(event_record)

    return saved


# -----------------------------------------------------------------------
# 全体パイプライン
# -----------------------------------------------------------------------

def run_pipeline(
    start_time: str | None = None,
    max_results: int = 10,
) -> int:
    total = 0
    for account in ACCOUNTS:
        total += run_x_for_account(account, start_time=start_time, max_results=max_results)
        total += run_youtube_for_account(account)
        total += run_web_for_account(account)

    total += run_email_pipeline()

    deleted = db.delete_expired_events()
    if deleted:
        logger.info(f"期限切れイベント {deleted} 件を削除しました")

    logger.info(f"パイプライン完了: 合計 {total} 件保存")
    return total


async def run_loop() -> None:
    """起動時に即実行し、以降は毎日 FETCH_HOUR 時に run_pipeline を実行するループ"""
    # 起動時に即実行（差分取得）
    logger.info("起動時パイプライン実行開始")
    try:
        await asyncio.to_thread(run_pipeline)
    except Exception as e:
        logger.error(f"起動時パイプラインエラー: {e}")

    while True:
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        next_run = now.replace(hour=FETCH_HOUR, minute=0, second=0, microsecond=0)
        if now >= next_run:
            next_run += timedelta(days=1)

        wait_seconds = (next_run - now).total_seconds()
        logger.info(f"次回取得: {next_run.isoformat()} ({wait_seconds:.0f}秒後)")

        await asyncio.sleep(wait_seconds)

        try:
            await asyncio.to_thread(run_pipeline)
        except Exception as e:
            logger.error(f"スケジューラーエラー: {e}")
