from pydantic import BaseModel, ConfigDict
from typing import Optional


class TweetData(BaseModel):
    """X API から取得した生ツイートデータ"""
    post_id: str
    post_text: str
    posted_at: str  # ISO8601 UTC
    image_url: Optional[str] = None


class JudgementResult(BaseModel):
    """Claude によるイベント判定結果"""
    is_event: bool
    category: Optional[str] = None


class EventRecord(BaseModel):
    """DB に保存するレコード"""
    post_id: str
    post_text: str
    post_url: str
    posted_at: str
    is_event: bool
    account: str
    category: Optional[str] = None
    event_date: Optional[str] = None
    venue: Optional[str] = None
    image_url: Optional[str] = None
    source: str = "x"  # x / youtube / web / email
    created_at: str


class EventResponse(BaseModel):
    """GET /events エンドポイントのレスポンス"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    post_id: str
    post_text: str
    post_url: str
    posted_at: str
    is_event: bool
    account: str
    category: Optional[str] = None
    event_date: Optional[str] = None
    venue: Optional[str] = None
    image_url: Optional[str] = None
    source: Optional[str] = "x"
    created_at: str


class EmailRecord(BaseModel):
    """メールDB保存レコード"""
    message_id: str
    account: str
    subject: Optional[str] = None
    sender: Optional[str] = None
    received_at: str
    body_preview: Optional[str] = None
    deadline_date: Optional[str] = None
    created_at: str


class EmailResponse(BaseModel):
    """GET /emails エンドポイントのレスポンス"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    message_id: str
    account: str
    subject: Optional[str] = None
    sender: Optional[str] = None
    received_at: str
    body_preview: Optional[str] = None
    deadline_date: Optional[str] = None
    created_at: str
