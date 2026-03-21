import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

import db
import scheduler
from models import EventResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    logger.info("DB 初期化完了")
    task = asyncio.create_task(scheduler.run_loop())
    logger.info("スケジューラー起動")
    yield
    task.cancel()


app = FastAPI(title="CUTIE_STREET イベント API", lifespan=lifespan)

ALLOWED_ORIGINS = os.getenv(
    "CORS_ORIGINS", "http://localhost:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/events", response_model=list[EventResponse])
def get_events(
    limit: int = Query(default=200, ge=1, le=500),
    account: str = Query(default=None),
):
    return db.get_events(account=account, limit=limit)


@app.post("/fetch")
async def manual_fetch(
    start_time: str = Query(default=None, description="取得開始日時 (RFC3339例: 2026-03-15T00:00:00Z)"),
    max_results: int = Query(default=10, ge=5, le=100, description="1アカウントあたりの最大取得件数"),
):
    """
    手動トリガー: X取得 → イベント判定 → DB保存

    - start_time: 過去分を取得する場合に指定 (例: 2026-03-15T00:00:00Z)
    - max_results: テスト時は5にすると API コストを最小化できる
    """
    try:
        count = await asyncio.to_thread(scheduler.run_pipeline, start_time, max_results)
        return {"message": f"{count} 件のイベントを保存しました"}
    except Exception as e:
        logger.error(f"/fetch エラー: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    return {"status": "ok"}
