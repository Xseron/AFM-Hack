from __future__ import annotations


def method_confidences(findings) -> dict[str, float]:
    values = {
        "semantic": 0.0,
        "ocr": 0.0,
        "clip": 0.0,
        "audio": 0.0,
    }
    for finding in findings:
        confidence = float(finding.confidence or 0.0)
        if finding.modality == "triage" and finding.signal_type == "semantic_scam_alignment":
            values["semantic"] = max(values["semantic"], confidence)
        elif finding.modality == "ocr":
            values["ocr"] = max(values["ocr"], confidence)
        elif finding.modality == "visual":
            values["clip"] = max(values["clip"], confidence)
        elif finding.modality == "audio":
            values["audio"] = max(values["audio"], confidence)
    return values


def scanner_confidences(findings) -> dict[str, float]:
    """Max confidence per concrete pipeline id.

    ``method_confidences`` keeps the old dashboard buckets. This exposes the
    actual live scanner nodes, including plugins, so the UI can render the same
    scanners the architecture page has enabled.
    """
    values: dict[str, float] = {}
    for finding in findings:
        pipeline = (finding.evidence or {}).get("_pipeline")
        if not pipeline:
            continue
        confidence = float(finding.confidence or 0.0)
        values[pipeline] = max(values.get(pipeline, 0.0), confidence)
    return values


def source_info(job) -> dict:
    meta = job.source_meta or {}
    top_bar_url = meta.get("top_bar_url") or meta.get("page_url") or job.source_url
    return {
        "platform": job.source_platform,
        "url": job.source_url,
        "top_bar_url": top_bar_url,
        "permalink": meta.get("permalink") or meta.get("source_url"),
        "shortcode": meta.get("shortcode"),
        "meta": meta,
    }


def job_list_item(job) -> dict:
    return {
        "job_id": job.id,
        "status": job.status,
        "priority": job.priority,
        "risk_score": job.risk_score,
        "category": job.category,
        "source": source_info(job),
        "description": job.description or "",
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "method_confidences": method_confidences(job.findings),
        "scanner_confidences": scanner_confidences(job.findings),
    }
