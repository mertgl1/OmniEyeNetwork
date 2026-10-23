from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from app.core.config import settings
from app.core.database import get_db
from app.schemas.health import HealthResponse

router = APIRouter()


@router.get("", response_model=HealthResponse)
async def check_health(db: AsyncSession = Depends(get_db)):
    """Checks the health of FastAPI, MariaDB, and Redis."""
    # Check Database
    try:
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    # Check Redis
    try:
        r = aioredis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0")
        await r.ping()
        await r.aclose()
        redis_status = "connected"
    except Exception as e:
        redis_status = f"unhealthy: {str(e)}"

    overall_status = "healthy" if db_status == "connected" and redis_status == "connected" else "degraded"

    return HealthResponse(
        status=overall_status,
        version="0.1.0",
        database=db_status,
        redis=redis_status,
    )
