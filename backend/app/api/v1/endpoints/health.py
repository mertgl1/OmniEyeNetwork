from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis
import logging

from app.core.config import settings
from app.core.database import get_db
from app.schemas.health import HealthResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("", response_model=HealthResponse)
async def check_health(db: AsyncSession = Depends(get_db)):
    """Checks the health of FastAPI, MariaDB, and Redis."""
    # Check Database
    try:
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        logger.exception("Database health check failed.")
        db_status = "unhealthy"

    # Check Redis
    try:
        redis_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0"
        if settings.REDIS_PASSWORD:
            redis_url = f"redis://:{settings.REDIS_PASSWORD}@{settings.REDIS_HOST}:{settings.REDIS_PORT}/0"
        r = aioredis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
        await r.ping()
        await r.aclose()
        redis_status = "connected"
    except Exception:
        logger.exception("Redis health check failed.")
        redis_status = "unhealthy"

    overall_status = "healthy" if db_status == "connected" and redis_status == "connected" else "degraded"

    return HealthResponse(
        status=overall_status,
        version="0.5.0",
        database=db_status,
        redis=redis_status,
    )
