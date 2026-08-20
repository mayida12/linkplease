from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.database.session import get_db
from app.models.dm_job import DmJob, DELIVERED, FAILED, PENDING, SENT_PENDING_CONFIRMATION
from app.models.duplicate_block import DuplicateBlock
from app.schemas.stats import StatsOut

router = APIRouter()

# Statuses that mean "still in flight, not resolved yet" -> counts as "queued".
QUEUED_STATUSES = (PENDING, SENT_PENDING_CONFIRMATION)


@router.get("/stats", response_model=StatsOut)
def get_stats(db: Session = Depends(get_db)):
    """
    Every number here is a live COUNT() against current row state - not a
    separately-maintained counter. That means /stats can never drift out of
    sync with reality (e.g. because an increment was missed or double
    counted somewhere); it always reflects exactly what's in the database
    right now.
    """
    def count_where(*conditions) -> int:
        stmt = select(func.count(DmJob.id)).where(*conditions)
        return db.execute(stmt).scalar_one()

    sent = count_where(DmJob.status == DELIVERED)
    failed = count_where(DmJob.status == FAILED)
    queued = count_where(DmJob.status.in_(QUEUED_STATUSES))
    duplicates_blocked = db.execute(select(func.count(DuplicateBlock.id))).scalar_one()

    return StatsOut(sent=sent, failed=failed, queued=queued, duplicates_blocked=duplicates_blocked)
