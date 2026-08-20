from pydantic import BaseModel


class StatsOut(BaseModel):
    sent: int
    failed: int
    queued: int
    duplicates_blocked: int
