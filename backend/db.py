import os
from contextlib import contextmanager
from typing import Generator, Optional
from datetime import datetime, timezone, timedelta

import psycopg2
import psycopg2.extras

from models import EventRecord, EventResponse

DATABASE_URL = os.getenv("DATABASE_URL", "")
EVENT_EXPIRY_DAYS = 14  # イベント終了から2週間でDB削除


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
                    created_at TEXT    NOT NULL
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_posted_at  ON events(posted_at DESC)")
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_post_id ON events(post_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_event_date ON events(event_date)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_account    ON events(account)")


def is_post_exists(post_id: str) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT EXISTS(SELECT 1 FROM events WHERE post_id = %s)", (post_id,)
            )
            return cur.fetchone()[0]


def get_recent_events_for_dedup(account: str, limit: int = 100) -> list[dict]:
    """重複検出用: アカウント別直近 limit 件"""
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
    """保存成功で True、重複スキップで False を返す"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO events
                  (post_id, post_text, post_url, posted_at, is_event, account,
                   category, event_date, venue, image_url, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                    event.created_at,
                ),
            )
            return cur.rowcount > 0


def get_events(account: Optional[str] = None, limit: int = 200) -> list[EventResponse]:
    """
    イベント一覧を返す。
    event_date があるイベントを優先し、イベント日順でソート。
    """
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


def get_latest_post_id(account: str) -> Optional[str]:
    """差分取得用: アカウント別の最新 post_id を返す"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT post_id FROM events WHERE account = %s ORDER BY posted_at DESC LIMIT 1",
                (account,),
            )
            row = cur.fetchone()
            return row[0] if row else None


def delete_expired_events() -> int:
    """終了から2週間が経過したイベントを削除。削除件数を返す。"""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=EVENT_EXPIRY_DAYS)).date().isoformat()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM events
                WHERE (
                    (event_date IS NOT NULL AND event_date < %s)
                    OR
                    (event_date IS NULL AND posted_at::date < %s::date)
                )
                """,
                (cutoff, cutoff),
            )
            return cur.rowcount
