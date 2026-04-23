"""Sources registry admin/debug endpoints."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db_session

router = APIRouter(prefix="/sources", tags=["sources"])


class SourceStatsOut(BaseModel):
    source_name: str
    tier: int
    weight: float
    active: bool
    source_type: str
    articles_24h: int
    signals_contributed_7d: int


@router.get("", response_model=list[SourceStatsOut])
async def list_sources(db: AsyncSession = Depends(get_db_session)):
    rows = (await db.execute(text(
        """
        SELECT
          sr.source_name, sr.tier, sr.weight, sr.active, sr.source_type,
          COALESCE(
            (SELECT COUNT(*) FROM news n
             WHERE n.source_id = sr.id AND n.publish_date >= NOW() - INTERVAL '24 hours'),
            0
          ) AS articles_24h,
          COALESCE(
            (SELECT COUNT(DISTINCT s.id) FROM signals s
             JOIN event_news_links el ON el.event_id = s.event_id
             JOIN news_clean nc ON nc.id = el.clean_id
             JOIN news n ON n.id = nc.news_id
             WHERE n.source_id = sr.id AND s.created_at >= NOW() - INTERVAL '7 days'),
            0
          ) AS signals_contributed_7d
        FROM sources_registry sr
        WHERE sr.active = true
        ORDER BY sr.tier ASC, sr.source_name ASC
        """
    ))).mappings().all()
    return [SourceStatsOut(**r) for r in rows]
