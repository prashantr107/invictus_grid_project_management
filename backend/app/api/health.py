from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health", summary="Check API health")
def health_check() -> dict[str, str]:
    """Return a basic liveness response without exposing infrastructure details."""
    return {"status": "ok"}
