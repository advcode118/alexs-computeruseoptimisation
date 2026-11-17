"""Post-run row fields shared by all probe arms."""

WALL_CLOCK_VERSION = 2
GRADE_TEXT_CAP = 50_000


def measurement_fields(*, browser_launch_ms: float = 0.0, grade_read_ms: float = 0.0) -> dict:
    return {
        "wall_clock_version": WALL_CLOCK_VERSION,
        "browser_launch_ms": browser_launch_ms,
        "grade_read_ms": grade_read_ms,
    }


def grade_fields(url: str = "", text: str = "", selector_text: str = "", answer: str = "") -> dict:
    return {
        "grade_url": url,
        "grade_page_text": text[:GRADE_TEXT_CAP],
        "grade_page_text_truncated": len(text) > GRADE_TEXT_CAP,
        "grade_selector_text": selector_text,
        "claimed_answer": answer,
    }
