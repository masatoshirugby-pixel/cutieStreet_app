import asyncio
import logging
import re
from datetime import datetime, timezone

import db
import x_fetcher
import web_fetcher
import email_fetcher
import claude_judge
from event_utils import extract_event_date, extract_deadline_date, extract_deadline_dates, extract_venue, is_duplicate, ACCOUNTS
from models import EventRecord, EmailRecord, JudgementResult

logger = logging.getLogger(__name__)

FETCH_HOUR = 8  # 毎日 08:00 UTC に取得

# -----------------------------------------------------------------------
# スケジュールページ用カテゴリ判定（claude_judge を使わず TYPE から直接決定）
# -----------------------------------------------------------------------

_SCHED_TYPE_RE = re.compile(r'\[[A-Z]{2,3}\]\s+(LIVE|EVENT|TV|RADIO|VIDEO)', re.IGNORECASE)


def _judge_schedule(post_text: str) -> JudgementResult | None:
    """
    スケジュールページのテキスト ("04 05 [SUN] LIVE ...") からカテゴリを決定する。
    VIDEO など不要なタイプは None を返す（保存スキップ）。
    """
    m = _SCHED_TYPE_RE.search(post_text)
    type_str = m.group(1).upper() if m else "EVENT"

    if type_str == "VIDEO":
        return None  # ビデオはスキップ

    if type_str == "LIVE":
        if any(kw in post_text for kw in ["ワンマン", "単独公演", "単独ライブ"]):
            return JudgementResult(is_event=True, category="単独ライブ")
        if any(kw in post_text for kw in ["フェス", "フェスティバル", "festival"]):
            return JudgementResult(is_event=True, category="フェス出演")
        if any(kw in post_text for kw in ["対バン", "合同ライブ", "合同公演", "合同イベント"]):
            return JudgementResult(is_event=True, category="合同ライブ")
        return JudgementResult(is_event=True, category="ライブ")

    if type_str in ("TV", "RADIO"):
        return JudgementResult(is_event=True, category="メディア出演")

    # EVENT: タイトルのキーワードでさらに分類（オンラインサイン会は特典会より先にチェック）
    if "大特典会" in post_text:
        return JudgementResult(is_event=True, category="大特典会")
    if any(kw in post_text for kw in ["オンラインサイン会", "オンラインサイン"]):
        return JudgementResult(is_event=True, category="オンラインサイン会")
    if any(kw in post_text for kw in ["特典会", "チェキ", "お渡し", "ハイタッチ", "サイン会"]):
        return JudgementResult(is_event=True, category="特典会")
    if any(kw in post_text for kw in ["リリースイベント", "リリイベ", "発売記念", "インストア"]):
        return JudgementResult(is_event=True, category="リリースイベント")

    return JudgementResult(is_event=True, category="その他イベント")


# -----------------------------------------------------------------------
# 締切レコード補完（本体記事が既存の場合に呼ぶ）
# -----------------------------------------------------------------------

def _ensure_deadline_record(tweet, account: str, source: str) -> None:
    """本体記事が既にDBに存在するとき、締切レコードが未作成なら保存する（複数対応）。"""
    entries = extract_deadline_dates(tweet.post_text)
    if not entries:
        return
    event_date = extract_event_date(tweet.post_text)
    if source == "x":
        post_url = f"https://x.com/{account}/status/{tweet.post_id}"
    elif tweet.post_id.startswith("https://"):
        post_url = tweet.post_id
    else:
        post_url = ""
    for idx, (label, deadline_date) in enumerate(entries):
        # 締切日はイベント日より前でなければならない
        if event_date and deadline_date >= event_date:
            continue
        if deadline_date == event_date:
            continue
        suffix = "_deadline" if idx == 0 else f"_deadline_{idx}"
        deadline_id = f"{tweet.post_id}{suffix}"
        if db.is_post_exists(deadline_id):
            continue
        deadline_record = EventRecord(
            post_id=deadline_id,
            post_text=tweet.post_text,
            post_url=post_url,
            posted_at=tweet.posted_at,
            is_event=True,
            account=account,
            category="申込締切",
            event_date=deadline_date.isoformat(),
            venue=label,
            image_url=None,
            source=source,
            created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )
        if db.save_event(deadline_record):
            logger.info(
                f"[{source}:{account}] 申込締切補完: {deadline_id} label={label} deadline={deadline_date}"
            )


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
# Web スクレイピングパイプライン
# -----------------------------------------------------------------------

def run_web_for_account(account: str) -> int:
    # スケジュールページは毎回全削除→再取得して最新状態を反映
    deleted = db.delete_web_events(account)
    if deleted:
        logger.info(f"[web:{account}] 旧スケジュールイベント {deleted} 件を削除")
    pages = web_fetcher.fetch_web_events(account)
    schedule_saved = _save_tweet_data(pages, account, source="web") if pages else 0

    # ニュースページは差分取得（is_post_exists でスキップ）
    news = web_fetcher.fetch_news_events(account)
    news_saved = _save_tweet_data(news, account, source="news") if news else 0

    return schedule_saved + news_saved


# -----------------------------------------------------------------------
# 共通: TweetData → 判定 → DB保存
# -----------------------------------------------------------------------

def _save_tweet_data(tweets, account: str, source: str) -> int:
    existing_records = db.get_recent_events_for_dedup(account=account, limit=100)
    saved = 0

    for tweet in tweets:
        if db.is_post_exists(tweet.post_id):
            # 本体記事が既存でも、締切レコードが未作成なら生成する
            if source != "web":
                _ensure_deadline_record(tweet, account, source)
            continue

        if source == "web":
            # スケジュールページは TYPE（LIVE/EVENT/TV/RADIO）から直接カテゴリを決定
            judgement = _judge_schedule(tweet.post_text)
            if judgement is None:
                continue  # VIDEO など不要なタイプはスキップ
        else:
            # X・ニュースはキーワードマッチング＋形態素解析で判定
            judgement = claude_judge.judge_tweet(tweet.post_text)
            if not judgement.is_event:
                logger.info(f"[{source}:{account}] 非イベント判定: {tweet.post_id}")
                continue

        event_date = extract_event_date(tweet.post_text)
        event_date_str = event_date.isoformat() if event_date else None
        venue = extract_venue(tweet.post_text)

        # web（スケジュールページ）は公式情報なので重複チェックなし
        if source != "web" and is_duplicate(
            new_text=tweet.post_text,
            new_category=judgement.category,
            new_event_date=event_date,
            existing_records=existing_records,
        ):
            logger.info(f"[{source}:{account}] 重複スキップ: {tweet.post_id}")
            continue

        if source == "x":
            post_url = f"https://x.com/{account}/status/{tweet.post_id}"
        elif source in ("web", "news") and tweet.post_id.startswith("https://"):
            post_url = tweet.post_id  # post_id が詳細ページの完全URL
        else:
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

            # 投稿本文から申込締切日を抽出して別レコードとして保存（複数対応）
            # webスケジュールページは締切情報を含まないためスキップ
            if source != "web":
                for idx, (label, deadline_date) in enumerate(extract_deadline_dates(tweet.post_text)):
                    if deadline_date == event_date:
                        continue
                    # 締切日はイベント日より前でなければならない
                    if event_date and deadline_date >= event_date:
                        continue
                    suffix = "_deadline" if idx == 0 else f"_deadline_{idx}"
                    deadline_id = f"{tweet.post_id}{suffix}"
                    if not db.is_post_exists(deadline_id):
                        deadline_record = EventRecord(
                            post_id=deadline_id,
                            post_text=tweet.post_text,
                            post_url=post_url,
                            posted_at=tweet.posted_at,
                            is_event=True,
                            account=account,
                            category="申込締切",
                            event_date=deadline_date.isoformat(),
                            venue=label,
                            image_url=None,
                            source=source,
                            created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                        )
                        if db.save_event(deadline_record):
                            logger.info(
                                f"[{source}:{account}] 申込締切保存: {deadline_id} "
                                f"label={label} deadline={deadline_date}"
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

def run_deadline_backfill() -> int:
    """DB内の news/X 記事で締切レコードが未作成のものを全件補完する。"""
    from datetime import date as _date
    import requests
    from bs4 import BeautifulSoup

    events = db.get_news_without_deadlines()
    count = 0
    for event in events:
        entries = extract_deadline_dates(event.post_text)
        # stored post_text が切り詰められている可能性があるため、news記事は詳細ページを再取得して全文チェック
        if not entries and event.source in ("news", "web") and event.post_id.startswith("https://"):
            try:
                resp = requests.get(
                    event.post_id,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                    timeout=15,
                )
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")
                h1 = soup.find("h1")
                title = h1.get_text(strip=True) if h1 else ""
                section = soup.find(class_="section--detail")
                body_text = section.get_text(separator=" ", strip=True) if section else soup.get_text(separator=" ", strip=True)
                full_text = f"{title}\n{body_text}" if title else body_text
                entries = extract_deadline_dates(full_text)
                if entries:
                    logger.info(f"[backfill] 再取得で締切発見: {event.post_id}")
            except Exception as e:
                logger.warning(f"[backfill] 再取得失敗 {event.post_id}: {e}")
        if not entries:
            continue
        event_date_obj = _date.fromisoformat(event.event_date) if event.event_date else None
        post_url = event.post_url or ""
        for idx, (label, deadline_date) in enumerate(entries):
            if event_date_obj and deadline_date >= event_date_obj:
                continue
            suffix = "_deadline" if idx == 0 else f"_deadline_{idx}"
            deadline_id = f"{event.post_id}{suffix}"
            if db.is_post_exists(deadline_id):
                continue
            deadline_record = EventRecord(
                post_id=deadline_id,
                post_text=event.post_text,
                post_url=post_url,
                posted_at=event.posted_at,
                is_event=True,
                account=event.account,
                category="申込締切",
                event_date=deadline_date.isoformat(),
                venue=label,
                image_url=None,
                source=event.source,
                created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            )
            if db.save_event(deadline_record):
                count += 1
                logger.info(
                    f"[backfill] 申込締切補完: {deadline_id} label={label} deadline={deadline_date}"
                )
    logger.info(f"[backfill] 申込締切補完 合計 {count} 件")
    return count


def run_web_pipeline() -> int:
    """Web スクレイピング（スケジュールページ）のみ実行。X API は呼ばない。"""
    total = 0
    for account in ACCOUNTS:
        total += run_web_for_account(account)
    run_deadline_backfill()
    deleted = db.delete_expired_events()
    if deleted:
        logger.info(f"期限切れイベント {deleted} 件を削除しました")
    logger.info(f"[web pipeline] 合計 {total} 件保存")
    return total


def run_pipeline(
    start_time: str | None = None,
    max_results: int = 10,
) -> int:
    total = 0
    for account in ACCOUNTS:
        # スケジュールを先に保存し、X の重複チェックに活用する
        total += run_web_for_account(account)
        total += run_x_for_account(account, start_time=start_time, max_results=max_results)

    total += run_email_pipeline()

    deleted = db.delete_expired_events()
    if deleted:
        logger.info(f"期限切れイベント {deleted} 件を削除しました")

    logger.info(f"パイプライン完了: 合計 {total} 件保存")
    return total


async def run_loop() -> None:
    """起動時はWebのみ実行し、以降は毎日 FETCH_HOUR 時に run_pipeline（Web+X+メール）を実行するループ"""
    # 起動時はWebスクレイピングのみ（X APIは毎日FETCH_HOURのみ呼び出す）
    logger.info("起動時Webパイプライン実行開始")
    try:
        await asyncio.to_thread(run_web_pipeline)
    except Exception as e:
        logger.error(f"起動時Webパイプラインエラー: {e}")

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
