"""
Gmail IMAP でメールを取得し、グループ関連メールを抽出する。
締め切り日付が含まれるメールはカレンダーにも反映する。
"""

import email
import imaplib
import logging
import os
from datetime import datetime, timezone
from email.header import decode_header
from email.utils import parsedate_to_datetime

logger = logging.getLogger(__name__)

GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")

# グループ名の検索キーワード
GROUP_KEYWORDS: dict[str, list[str]] = {
    "CUTIE_STREET_": [
        "CUTIE STREET", "cutie street", "CUTIE_STREET", "キューティーストリート", "CS_",
    ],
    "CANDY_TUNE_": [
        "CANDY TUNE", "candy tune", "CANDY_TUNE", "キャンディチューン",
    ],
    "SWEET_STEADY": [
        "SWEET STEADY", "sweet steady", "SWEET_STEADY", "スウィートステディ",
    ],
}

FETCH_LIMIT = 200  # 直近の確認件数

# 除外する件名パターン（注文確認など）
EXCLUDE_SUBJECT_KEYWORDS = [
    "ご注文内容のご確認",
    "ご注文の確認",
    "注文確認",
    "ご注文ありがとう",
    "購入完了",
    "お買い上げありがとう",
    "order confirmation",
    "Order Confirmation",
]


def _decode_str(value: str) -> str:
    parts = decode_header(value)
    result = []
    for part, charset in parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(part)
    return "".join(result)


def _get_body(msg: email.message.Message) -> str:
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    body += payload.decode(charset, errors="replace")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            body = payload.decode(charset, errors="replace")
    return body[:3000]


def _detect_account(text: str) -> str | None:
    lower = text.lower()
    for account, keywords in GROUP_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in lower:
                return account
    return None


def _parse_received_at(date_str: str) -> str:
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except Exception:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch_emails() -> list[dict]:
    """
    Gmail から最新メールを取得してグループ関連を返す。
    Returns: list of dicts（message_id, account, subject, sender,
                            received_at, body_preview, body_full）
    """
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        logger.warning("[Email] Gmail 認証情報が設定されていません")
        return []

    results: list[dict] = []
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        mail.select("inbox")

        _, data = mail.search(None, "ALL")
        all_ids = data[0].split()
        target_ids = all_ids[-FETCH_LIMIT:] if len(all_ids) > FETCH_LIMIT else all_ids

        for msg_id in reversed(target_ids):
            _, msg_data = mail.fetch(msg_id, "(RFC822)")
            if not msg_data or not msg_data[0]:
                continue
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)

            subject = _decode_str(msg.get("Subject", ""))
            sender = _decode_str(msg.get("From", ""))
            date_str = msg.get("Date", "")
            message_id = msg.get("Message-ID", f"email_{msg_id.decode()}")
            body = _get_body(msg)

            # 注文確認メールを除外
            if any(kw in subject for kw in EXCLUDE_SUBJECT_KEYWORDS):
                continue

            account = _detect_account(f"{subject} {body}")
            if not account:
                continue

            results.append({
                "message_id": message_id,
                "account": account,
                "subject": subject,
                "sender": sender,
                "received_at": _parse_received_at(date_str),
                "body_preview": body[:300],
                "body_full": body,
            })

        mail.logout()
    except Exception as e:
        logger.error(f"[Email] メール取得エラー: {e}")

    logger.info(f"[Email] {len(results)} 件取得（グループ関連）")
    return results
