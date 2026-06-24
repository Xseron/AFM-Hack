from dataclasses import dataclass, field
from datetime import datetime

RISK_CATEGORIES = [
    "illegal_gambling",
    "financial_pyramid",
    "guaranteed_income",
    "aggressive_investment",
    "referral_scheme",
    "hidden_engagement",
]


@dataclass
class Post:
    tg_message_id: int
    date: datetime
    text: str
    media_paths: list[str] = field(default_factory=list)


@dataclass
class PostAssessment:
    tg_message_id: int
    categories: list[str]
    confidence: float
    evidence_quotes: list[str]
    explanation: str
    model_used: str


@dataclass
class ChannelReport:
    username: str
    title: str
    status: str
    risk_score: int
    categories: list[str]
    explanation: str
    post_assessments: list[PostAssessment]
    error_reason: str | None = None
