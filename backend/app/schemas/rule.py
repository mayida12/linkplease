from pydantic import BaseModel, Field


class RuleCreate(BaseModel):
    keyword: str = Field(..., min_length=1)
    dm_message: str = Field(..., min_length=1)


class RuleOut(BaseModel):
    rule_id: str
    keyword: str
    dm_message: str

    model_config = {"from_attributes": True}
