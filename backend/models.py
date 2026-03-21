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
    image_url: Optional[str] = None   # 投稿に添付された画像URL
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
    created_at: str
