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


def source_info(job) -> dict:
    meta = job.source_meta or {}
    return {
        "platform": job.source_platform,
        "url": job.source_url,
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
        "description": (job.description or "")[:240],
        "method_confidences": method_confidences(job.findings),
    }
