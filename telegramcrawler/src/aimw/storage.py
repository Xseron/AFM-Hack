import json

from sqlalchemy import (
    Column, Float, ForeignKey, Integer, String, Text, create_engine, select,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship

from aimw.domain import ChannelReport, PostAssessment


class Base(DeclarativeBase):
    pass


class ChannelRow(Base):
    __tablename__ = "channels"
    username = Column(String, primary_key=True)
    title = Column(String, default="")
    status = Column(String, default="ok")
    error_reason = Column(Text, nullable=True)
    risk_score = Column(Integer, default=0)
    explanation = Column(Text, default="")
    categories = Column(Text, default="[]")  # JSON
    assessments = relationship(
        "AssessmentRow", cascade="all, delete-orphan", backref="channel"
    )


class AssessmentRow(Base):
    __tablename__ = "post_assessments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_username = Column(String, ForeignKey("channels.username"))
    tg_message_id = Column(Integer)
    categories = Column(Text, default="[]")  # JSON
    confidence = Column(Float, default=0.0)
    evidence_quotes = Column(Text, default="[]")  # JSON
    explanation = Column(Text, default="")
    model_used = Column(String, default="")


class Repository:
    def __init__(self, database_url: str):
        self._engine = create_engine(database_url)
        Base.metadata.create_all(self._engine)

    def save_report(self, report: ChannelReport) -> None:
        with Session(self._engine) as session:
            existing = session.get(ChannelRow, report.username)
            if existing is not None:
                session.delete(existing)  # ORM delete cascades to assessments
                session.flush()
            row = ChannelRow(
                username=report.username,
                title=report.title,
                status=report.status,
                error_reason=report.error_reason,
                risk_score=report.risk_score,
                explanation=report.explanation,
                categories=json.dumps(report.categories, ensure_ascii=False),
            )
            for pa in report.post_assessments:
                row.assessments.append(AssessmentRow(
                    tg_message_id=pa.tg_message_id,
                    categories=json.dumps(pa.categories, ensure_ascii=False),
                    confidence=pa.confidence,
                    evidence_quotes=json.dumps(pa.evidence_quotes, ensure_ascii=False),
                    explanation=pa.explanation,
                    model_used=pa.model_used,
                ))
            session.add(row)
            session.commit()

    def get_report(self, username: str) -> ChannelReport | None:
        with Session(self._engine) as session:
            row = session.get(ChannelRow, username)
            if row is None:
                return None
            return self._to_report(row)

    def list_reports(self, sort_by_risk: bool = True) -> list[ChannelReport]:
        with Session(self._engine) as session:
            stmt = select(ChannelRow)
            if sort_by_risk:
                stmt = stmt.order_by(ChannelRow.risk_score.desc())
            return [self._to_report(r) for r in session.scalars(stmt).all()]

    def _to_report(self, row: ChannelRow) -> ChannelReport:
        assessments = [
            PostAssessment(
                tg_message_id=a.tg_message_id,
                categories=json.loads(a.categories),
                confidence=a.confidence,
                evidence_quotes=json.loads(a.evidence_quotes),
                explanation=a.explanation,
                model_used=a.model_used,
            )
            for a in row.assessments
        ]
        return ChannelReport(
            username=row.username,
            title=row.title,
            status=row.status,
            risk_score=row.risk_score,
            categories=json.loads(row.categories),
            explanation=row.explanation,
            post_assessments=assessments,
            error_reason=row.error_reason,
        )
