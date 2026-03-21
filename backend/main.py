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
def get_events(limit: int = Query(default=30, ge=1, le=100)):
    return db.get_events(limit=limit)


@app.post("/fetch")
async def manual_fetch():
    """手動トリガー: X取得 → Claude判定 → DB保存"""
    try:
        count = await asyncio.to_thread(scheduler.run_pipeline)
        return {"message": f"{count} 件のイベントを保存しました"}
    except Exception as e:
        logger.error(f"/fetch エラー: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    return {"status": "ok"}
