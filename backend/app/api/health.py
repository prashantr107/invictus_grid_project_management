from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.session import get_db

router = APIRouter(tags=["health"])
logger = get_logger("app.health")


@router.get("/health/live", summary="Liveness probe")
def liveness() -> dict[str, str]:
    """Process liveness only. Does not touch dependencies."""
    return {"status": "ok"}


@router.get("/health", summary="Readiness probe (checks database)")
def readiness(db: Session = Depends(get_db)) -> JSONResponse:
    """Report readiness, including live database connectivity, without leaking
    connection details or secrets."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.warning("database_unavailable", extra={"event": "health.database_unavailable"})
        return JSONResponse(status_code=503, content={"status": "degraded", "database": "unavailable"})
    return JSONResponse(status_code=200, content={"status": "ok", "database": "ok"})
