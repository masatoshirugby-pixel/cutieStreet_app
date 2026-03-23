import os
from contextlib import contextmanager
from typing import Generator, Optional
from datetime import datetime, timezone, timedelta

import psycopg2
import psycopg2.extras

from models import EventRecord, EventResponse, EmailRecord, EmailResponse

DATABASE_URL = os.getenv("DATABASE_URL", "")
EVENT_EXPIRY_DAYS = 14


@contextmanager
def get_conn() -> Generator[psycopg2.extensions.connection, None, None]:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id         SERIAL PRIMARY KEY,
                    post_id    TEXT    NOT NULL UNIQUE,
                    post_text  TEXT    NOT NULL,
                    post_url   TEXT    NOT NULL,
                    posted_at  TEXT    NOT NULL,
                    is_event   BOOLEAN NOT NULL DEFAULT FALSE,
                    account    TEXT    NOT NULL DEFAULT '',
                    category   TEXT    DEFAULT NULL,
                    event_date TEXT    DEFAULT NULL,
                    venue      TEXT    DEFAULT NULL,
                    image_url  TEXT    DEFAULT NULL,
                    source     TEXT    NOT NULL DEFAULT 'x',
                    created_at TEXT    NOT NULL
                )
            """)
            cur.execute("ALTER TABLE events ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'x'")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_posted_at  ON events(posted_at DESC)")
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_post_id ON events(post_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_event_date ON events(event_date)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_account    ON events(account)")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS emails (
                    id            SERIAL PRIMARY KEY,
                    message_id    TEXT NOT NULL UNIQUE,
                    account       TEXT NOT NULL,
                    subject       TEXT,
                    sender        TEXT,
                    received_at   TEXT NOT NULL,
                    body_preview  TEXT,
                    deadline_date TEXT DEFAULT NULL,
                    created_at    TEXT NOT NULL
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_email_account ON emails(account)")


def is_post_exists(post_id: str) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT EXISTS(SELECT 1 FROM events WHERE post_id = %s)", (post_id,)
            )
            return cur.fetchone()[0]


def get_recent_events_for_dedup(account: str, limit: int = 100) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT post_text, category, event_date
                FROM events
                WHERE is_event = TRUE AND account = %s
                ORDER BY posted_at DESC
                LIMIT %s
                """,
                (account, limit),
            )
            return [dict(row) for row in cur.fetchall()]


def save_event(event: EventRecord) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO events
                  (post_id, post_text, post_url, posted_at, is_event, account,
                   category, event_date, venue, image_url, source, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (post_id) DO NOTHING
                """,
                (
                    event.post_id,
                    event.post_text,
                    event.post_url,
                    event.posted_at,
                    event.is_event,
                    event.account,
                    event.category,
                    event.event_date,
                    event.venue,
                    event.image_url,
                    event.source,
                    event.created_at,
                ),
            )
            return cur.rowcount > 0


def get_events(account: Optional[str] = None, limit: int = 1000) -> list[EventResponse]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if account:
                cur.execute(
                    """
                    SELECT * FROM events
                    WHERE is_event = TRUE AND account = %s
                    ORDER BY COALESCE(event_date, posted_at::date::text) DESC
                    LIMIT %s
                    """,
                    (account, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT * FROM events
                    WHERE is_event = TRUE
                    ORDER BY COALESCE(event_date, posted_at::date::text) DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
            return [EventResponse(**dict(row)) for row in cur.fetchall()]


def get_news_without_deadlines() -> list[EventResponse]:
    """締切レコードが未作成の news/x/web イベントを全件返す（バックフィル用）"""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT e.* FROM events e
                WHERE e.source IN ('news', 'x', 'web')
                  AND e.is_event = TRUE
                  AND e.category != '申込締切'
                  AND NOT EXISTS (
                      SELECT 1 FROM events d
                      WHERE d.post_id LIKE e.post_id || '_deadline%'
                  )
                ORDER BY e.event_date DESC NULLS LAST
                """
            )
            return [EventResponse(**dict(row)) for row in cur.fetchall()]


def get_latest_post_id(account: str) -> Optional[str]:
    """差分取得用: X投稿の最新 post_id を返す（YouTube/Web/Email は除外）"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT post_id FROM events WHERE account = %s AND source = 'x' ORDER BY posted_at DESC LIMIT 1",
                (account,),
            )
            row = cur.fetchone()
            return row[0] if row else None


def delete_web_events(account: str) -> int:
    """スケジュールページ由来の web イベントを全削除（毎回再取得するため）。申込締切レコードは保持。"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM events WHERE account = %s AND source = 'web' AND category != '申込締切'",
                (account,),
            )
            return cur.rowcount


def delete_expired_events() -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=EVENT_EXPIRY_DAYS)).date().isoformat()
    with get_conn() as conn:
        with conn.cursor() as cur:
            # 通常イベント（申込締切以外）を期限切れ削除
            cur.execute(
                """
                DELETE FROM events
                WHERE category != '申込締切'
                AND (
                    (event_date IS NOT NULL AND event_date < %s)
                    OR
                    (event_date IS NULL AND posted_at::date < %s::date)
                )
                """,
                (cutoff, cutoff),
            )
            deleted_normal = cur.rowcount

            # 申込締切レコードは親イベントが存在しない場合のみ削除
            # （親イベントが未来にある間は締切日が過去でも残す）
            cur.execute(
                """
                DELETE FROM events dl
                WHERE dl.category = '申込締切'
                AND dl.event_date IS NOT NULL
                AND dl.event_date < %s
                AND NOT EXISTS (
                    SELECT 1 FROM events parent
                    WHERE dl.post_id LIKE parent.post_id || '_deadline%%'
                )
                """,
                (cutoff,),
            )
            deleted_deadlines = cur.rowcount

            return deleted_normal + deleted_deadlines


# -----------------------------------------------------------------------
# メール関連
# -----------------------------------------------------------------------

def is_email_exists(message_id: str) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT EXISTS(SELECT 1 FROM emails WHERE message_id = %s)", (message_id,)
            )
            return cur.fetchone()[0]


def save_email(record: EmailRecord) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO emails
                  (message_id, account, subject, sender, received_at,
                   body_preview, deadline_date, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (message_id) DO NOTHING
                """,
                (
                    record.message_id,
                    record.account,
                    record.subject,
                    record.sender,
                    record.received_at,
                    record.body_preview,
                    record.deadline_date,
                    record.created_at,
                ),
            )
            return cur.rowcount > 0


_EXCLUDE_SUBJECT_FRAGMENTS = (
    "ご注文内容のご確認",
    "ご注文の確認",
    "注文確認",
    "ご注文ありがとう",
    "購入完了",
    "お買い上げありがとう",
    "order confirmation",
)


def get_emails(account: Optional[str] = None) -> list[EmailResponse]:
    exclude_conditions = " AND ".join(
        f"subject NOT ILIKE %s" for _ in _EXCLUDE_SUBJECT_FRAGMENTS
    )
    exclude_params = tuple(f"%{s}%" for s in _EXCLUDE_SUBJECT_FRAGMENTS)

    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if account:
                cur.execute(
                    f"""
                    SELECT * FROM emails
                    WHERE account = %s AND ({exclude_conditions})
                    ORDER BY received_at DESC
                    LIMIT 50
                    """,
                    (account,) + exclude_params,
                )
            else:
                cur.execute(
                    f"""
                    SELECT * FROM emails
                    WHERE {exclude_conditions}
                    ORDER BY received_at DESC
                    LIMIT 50
                    """,
                    exclude_params,
                )
            return [EmailResponse(**dict(row)) for row in cur.fetchall()]
