from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.db.models import Explanation, Finding, Job
from app.pipelines.base import Finding as DomainFinding
from app.pipelines.explain import Explanation as DomainExplanation


class JobRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def create_job(
        self,
        description: str,
        source_platform: str | None,
        source_url: str | None,
        source_meta: dict,
        buffer_path: str | None = None,
        content_hash: str | None = None,
    ) -> str:
        job_id = uuid.uuid4().hex
        async with self._sf() as s:
            s.add(Job(
                id=job_id,
                description=description,
                source_platform=source_platform,
                source_url=source_url,
                source_meta=source_meta,
                buffer_path=buffer_path,
                content_hash=content_hash,
            ))
            await s.commit()
        return job_id

    async def get_job(self, job_id: str) -> Job | None:
        async with self._sf() as s:
            stmt = (
                select(Job)
                .where(Job.id == job_id)
                .options(selectinload(Job.findings), selectinload(Job.explanations))
            )
            return (await s.execute(stmt)).scalar_one_or_none()

    async def get_job_by_hash(self, content_hash: str) -> Job | None:
        async with self._sf() as s:
            stmt = select(Job).where(Job.content_hash == content_hash)
            return (await s.execute(stmt)).scalar_one_or_none()

    async def clear_content_hashes(self) -> int:
        async with self._sf() as s:
            stmt = update(Job).where(Job.content_hash.is_not(None)).values(content_hash=None)
            result = await s.execute(stmt)
            await s.commit()
            return int(result.rowcount or 0)

    async def _update(self, job_id: str, **values) -> None:
        async with self._sf() as s:
            job = await s.get(Job, job_id)
            if job is None:
                return
            for key, val in values.items():
                setattr(job, key, val)
            await s.commit()

    async def set_status(self, job_id: str, status: str, error: str | None = None) -> None:
        await self._update(job_id, status=status, error=error)

    async def set_priority(self, job_id: str, priority: float) -> None:
        await self._update(job_id, priority=priority)

    async def set_risk(self, job_id: str, risk_score: float, category: str) -> None:
        await self._update(job_id, risk_score=risk_score, category=category)

    async def add_findings(self, job_id: str, findings: list[DomainFinding]) -> None:
        async with self._sf() as s:
            for f in findings:
                s.add(Finding(
                    job_id=job_id,
                    modality=f.modality,
                    signal_type=f.signal_type,
                    confidence=f.confidence,
                    evidence=f.evidence,
                    ts_in_video=f.ts_in_video,
                ))
            await s.commit()

    async def add_explanations(self, job_id: str, explanations: list[DomainExplanation]) -> None:
        async with self._sf() as s:
            for e in explanations:
                s.add(Explanation(
                    job_id=job_id,
                    scope=e.scope,
                    method=e.method,
                    summary=e.summary,
                    payload={"attributions": [
                        {"feature": a.feature, "value": a.value, "weight": a.weight}
                        for a in e.attributions
                    ]},
                ))
            await s.commit()

    async def get_findings(self, job_id: str) -> list[Finding]:
        async with self._sf() as s:
            stmt = select(Finding).where(Finding.job_id == job_id).order_by(Finding.id)
            return list((await s.execute(stmt)).scalars().all())

    async def get_explanations(self, job_id: str) -> list[Explanation]:
        async with self._sf() as s:
            stmt = select(Explanation).where(Explanation.job_id == job_id).order_by(Explanation.id)
            return list((await s.execute(stmt)).scalars().all())

    async def review_queue(self, limit: int = 50) -> list[Job]:
        async with self._sf() as s:
            stmt = (
                select(Job)
                .order_by(Job.risk_score.is_(None), Job.risk_score.desc(), Job.priority.desc())
                .options(selectinload(Job.findings))
                .limit(limit)
            )
            return list((await s.execute(stmt)).scalars().all())

    async def priority_queue(self, limit: int = 50) -> list[Job]:
        async with self._sf() as s:
            stmt = (
                select(Job)
                .order_by(Job.priority.desc(), Job.created_at.desc())
                .options(selectinload(Job.findings))
                .limit(limit)
            )
            return list((await s.execute(stmt)).scalars().all())

    async def recent_jobs(self, limit: int = 50) -> list[Job]:
        async with self._sf() as s:
            stmt = (
                select(Job)
                .order_by(Job.created_at.desc())
                .options(selectinload(Job.findings))
                .limit(limit)
            )
            return list((await s.execute(stmt)).scalars().all())
