from pydantic import BaseModel

from aimw.domain import ChannelReport, PostAssessment


class AnalyzeRequest(BaseModel):
    channels: list[str]


class PostAssessmentOut(BaseModel):
    tg_message_id: int
    categories: list[str]
    confidence: float
    evidence_quotes: list[str]
    explanation: str
    model_used: str

    @classmethod
    def from_domain(cls, pa: PostAssessment) -> "PostAssessmentOut":
        return cls(**pa.__dict__)


class ChannelReportOut(BaseModel):
    username: str
    title: str
    status: str
    risk_score: int
    categories: list[str]
    explanation: str
    error_reason: str | None
    post_assessments: list[PostAssessmentOut]

    @classmethod
    def from_domain(cls, report: ChannelReport) -> "ChannelReportOut":
        return cls(
            username=report.username,
            title=report.title,
            status=report.status,
            risk_score=report.risk_score,
            categories=report.categories,
            explanation=report.explanation,
            error_reason=report.error_reason,
            post_assessments=[
                PostAssessmentOut.from_domain(p) for p in report.post_assessments
            ],
        )
