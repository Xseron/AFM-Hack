from pathlib import Path

import scam_image_detector as sid


WRITE_CARD_NUMBER = "\u043f\u0438\u0448\u0438 \u043d\u043e\u043c\u0435\u0440 \u043a\u0430\u0440\u0442\u044b"
SENDING_TO_FOLLOWERS = (
    "\u043e\u0442\u043f\u0440\u0430\u0432\u043b\u044f\u044e "
    "\u0441\u0440\u0435\u0434\u0438 "
    "\u043f\u043e\u0434\u043f\u0438\u0441\u0447\u0438\u043a\u043e\u0432"
)


def test_ocr_confusable_text_recovers_card_number_phrase():
    text = "nnwn HoMep KAPTbI\nOTnPaBnAIO CpeAN nOAnNcUNKOB"

    normalized = sid.normalize_text(text)

    assert WRITE_CARD_NUMBER in normalized
    assert SENDING_TO_FOLLOWERS in normalized


def test_ocr_semantic_score_uses_recovered_terms(tmp_path):
    text = "nnwn HoMep KAPTbI\nOTnPaBnAIO CpeAN nOAnNcUNKOB"
    ocr = sid.OcrResult(
        source_path=Path("clip.mp4"),
        text_path=tmp_path / "ocr.txt",
        text=text,
        frame_count=1,
    )
    detector = sid.VisualScamEmbeddingDetector(
        backend="tfidf",
        embedding_model=sid.DEFAULT_EMBEDDING_MODEL,
        local_files_only=True,
        device="cpu",
        threshold=0.5,
        temperature=0.09,
        keyword_weight=0.04,
    )

    result = detector.classify(ocr)

    assert result.predicted_label == "scam"
    assert result.scam_probability >= 0.5
    assert any(hit.term == WRITE_CARD_NUMBER for hit in result.matched_terms)
