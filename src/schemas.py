from pydantic import BaseModel
from typing import Optional, List, Literal


class TriageClassification(BaseModel):
    product_area: str
    issue_category: str
    urgency: Literal["P1", "P2", "P3", "P4"]
    reasoning: str


class KBMatch(BaseModel):
    doc_id: str
    title: str
    category: str
    score: float


class RiskFlag(BaseModel):
    ticket_id: str
    risk_type: str
    quote: str
    explanation: str


class AccountBrief(BaseModel):
    account_id: str
    executive_summary: str
    open_risks: List[RiskFlag]
    talking_points: List[str]
