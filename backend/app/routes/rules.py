from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.rule import Rule
from app.schemas.rule import RuleCreate, RuleOut

router = APIRouter()


@router.post("/rules", response_model=RuleOut, status_code=201)
def create_rule(payload: RuleCreate, db: Session = Depends(get_db)):
    rule = Rule(keyword=payload.keyword, dm_message=payload.dm_message)
    db.add(rule)
    db.commit()
    db.refresh(rule)

    return RuleOut(rule_id=rule.id, keyword=rule.keyword, dm_message=rule.dm_message)


@router.get("/rules", response_model=list[RuleOut])
def list_rules(db: Session = Depends(get_db)):
    """Not required by the spec, but handy for the frontend dashboard."""
    rules = db.query(Rule).order_by(Rule.created_at.desc()).all()
    return [RuleOut(rule_id=r.id, keyword=r.keyword, dm_message=r.dm_message) for r in rules]
