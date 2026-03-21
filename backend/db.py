import sqlite3
import os
from contextlib import contextmanager
from typing import Generator, Optional
from datetime import datetime, timezone, timedelta

from models import EventRecord, EventResponse

DB_PATH = os.getenv("DB_PATH", "./events.db")
EVENT_EXPIRY_DAYS = 14  # イベント終了から2週間でDB削除


@contextmanager
def get_conn() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
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
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS events (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id    TEXT    NOT NULL UNIQUE,
                post_text  TEXT    NOT NULL,
                post_url   TEXT    NOT NULL,
                posted_at  TEXT    NOT NULL,
                is_event   INTEGER NOT NULL DEFAULT 0,
                account    TEXT    NOT NULL DEFAULT '',
                category   TEXT    DEFAULT NULL,
                event_date TEXT    DEFAULT NULL,
                venue      TEXT    DEFAULT NULL,
                image_url  TEXT    DEFAULT NULL,
                created_at TEXT    NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_posted_at  ON events(posted_at DESC);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_post_id ON events(post_id);
            CREATE INDEX IF NOT EXISTS idx_event_date ON events(event_date);
            CREATE INDEX IF NOT EXISTS idx_account    ON events(account);
        """)


def is_post_exists(post_id: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT EXISTS(SELECT 1 FROM events WHERE post_id = ?)", (post_id,)
        ).fetchone()
        return bool(row[0])


def get_recent_events_for_dedup(account: str, limit: int = 100) -> list[dict]:
    """重複検出用: アカウント別直近 limit 件"""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT post_text, category, event_date
            FROM events
            WHERE is_event = 1 AND account = ?
            ORDER BY posted_at DESC
            LIMIT ?
            """,
            (account, limit),
        ).fetchall()
        return [dict(row) for row in rows]


def save_event(event: EventRecord) -> bool:
    """保存成功で True、重複スキップで False を返す"""
    with get_conn() as conn:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO events
              (post_id, post_text, post_url, posted_at, is_event, account,
               category, event_date, venue, image_url, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.post_id,
                event.post_text,
                event.post_url,
                event.posted_at,
                1 if event.is_event else 0,
                event.account,
                event.category,
                event.event_date,
                event.venue,
                event.image_url,
                event.created_at,
            ),
        )
        return cursor.rowcount > 0


def get_events(account: Optional[str] = None, limit: int = 30) -> list[EventResponse]:
    """
    イベント一覧を返す。
    event_date がある場合はイベント日順、ない場合は投稿日順でソート。
    """
    with get_conn() as conn:
        if account:
            rows = conn.execute(
                """
                SELECT * FROM events
                WHERE is_event = 1 AND account = ?
                ORDER BY COALESCE(event_date, date(posted_at)) DESC
                LIMIT ?
                """,
                (account, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM events
                WHERE is_event = 1
                ORDER BY COALESCE(event_date, date(posted_at)) DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [EventResponse(**dict(row)) for row in rows]


def get_latest_post_id(account: str) -> Optional[str]:
    """差分取得用: アカウント別の最新 post_id を返す"""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT post_id FROM events WHERE account = ? ORDER BY posted_at DESC LIMIT 1",
            (account,),
        ).fetchone()
        return row["post_id"] if row else None


def delete_expired_events() -> int:
    """終了から2週間が経過したイベントを削除。削除件数を返す。"""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=EVENT_EXPIRY_DAYS)).date().isoformat()
    with get_conn() as conn:
        cursor = conn.execute(
            """
            DELETE FROM events
            WHERE (
                (event_date IS NOT NULL AND event_date < ?)
                OR
                (event_date IS NULL AND date(posted_at) < ?)
            )
            """,
            (cutoff, cutoff),
        )
        return cursor.rowcount
