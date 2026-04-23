"""Utility functions for judicial-exam — 法警特考考古題系統."""

# 法警特考 6 大科目
SUBJECTS: list[str] = [
    "行政法概要",
    "刑法概要",
    "刑事訴訟法概要",
    "法院組織法",
    "法學知識與英文",
    "國文",
]

SUBJECT_ALIASES: dict[str, str] = {
    "行政法": "行政法概要",
    "行政法概要": "行政法概要",
    "刑法": "刑法概要",
    "刑法概要": "刑法概要",
    "刑事訴訟法": "刑事訴訟法概要",
    "刑事訴訟法概要": "刑事訴訟法概要",
    "刑訴": "刑事訴訟法概要",
    "法院組織法": "法院組織法",
    "法組": "法院組織法",
    "法學知識": "法學知識與英文",
    "法學知識與英文": "法學知識與英文",
    "英文": "法學知識與英文",
    "國文": "國文",
}

QUESTION_TYPE_DISPLAY: dict[str, str] = {
    "mcq": "選擇題",
    "essay": "申論題",
}

EXAM_CATEGORY_DISPLAY: dict[str, str] = {
    "法警": "司法特考四等（法警）",
}


def normalize_subject(subject: str | None) -> str | None:
    """Normalize subject name variants to canonical form."""
    if not subject:
        return subject
    return SUBJECT_ALIASES.get(subject, subject)


def display_subject(subject: str | None) -> str | None:
    """Return display-friendly subject name (currently identity)."""
    if not subject:
        return subject
    return subject


def get_subject_color(subject: str) -> str:
    """Return a CSS color class for each subject (for badges/chips)."""
    colors = {
        "行政法概要": "blue",
        "刑法概要": "red",
        "刑事訴訟法概要": "orange",
        "法院組織法": "purple",
        "法學知識與英文": "green",
        "國文": "yellow",
    }
    return colors.get(subject, "gray")
