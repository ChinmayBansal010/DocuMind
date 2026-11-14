import difflib
import re

from app.engines.analysis import CLAUSE_PATTERNS


def split_sections(text: str) -> dict[str, str]:
    sections = {}
    lines = text.splitlines()
    current_name = "Preamble"
    current_lines = []
    for line in lines:
        stripped = line.strip()
        is_heading = bool(
            re.match(r"^(?:\d+(?:\.\d+)*\.?\s+|[A-Z][A-Z\s]{3,}$)", stripped)
            and len(stripped) < 180
        )
        if is_heading and current_lines:
            sections[current_name] = "\n".join(current_lines).strip()
            current_name, current_lines = stripped, []
        current_lines.append(line)
    if current_lines:
        sections[current_name] = "\n".join(current_lines).strip()
    if len(sections) == 1 and "Preamble" in sections:
        return {name: sections["Preamble"] for name in CLAUSE_PATTERNS if any(
            re.search(pattern, text, re.IGNORECASE) for pattern in CLAUSE_PATTERNS[name]
        )} or sections
    return sections


def compare_texts(first: str, second: str) -> dict:
    old, new = split_sections(first), split_sections(second)
    changes = []
    for section in sorted(old.keys() | new.keys()):
        before, after = old.get(section), new.get(section)
        if before is None:
            status = "added"
        elif after is None:
            status = "removed"
        elif before == after:
            continue
        else:
            status = "modified"
        changes.append(
            {
                "section": section,
                "status": status,
                "before": before,
                "after": after,
                "diff": list(
                    difflib.unified_diff(
                        (before or "").splitlines(),
                        (after or "").splitlines(),
                        fromfile="Earlier version",
                        tofile="Later version",
                        lineterm="",
                    )
                ),
            }
        )
    return {"changes": changes, "added": sum(c["status"] == "added" for c in changes),
            "removed": sum(c["status"] == "removed" for c in changes),
            "modified": sum(c["status"] == "modified" for c in changes)}


def compare_obligations(first: list[dict], second: list[dict]) -> list[dict]:
    remaining = list(second)
    changes = []
    for old in first:
        identity = (
            str(old.get("responsible_party", "")).casefold().strip(),
            str(old.get("obligation", "")).casefold().strip(),
        )
        exact_index = next(
            (
                index
                for index, item in enumerate(remaining)
                if (
                    str(item.get("responsible_party", "")).casefold().strip(),
                    str(item.get("obligation", "")).casefold().strip(),
                )
                == identity
            ),
            None,
        )
        if exact_index is not None:
            new = remaining.pop(exact_index)
            old_deadline = str(old.get("deadline", "")).casefold().strip()
            new_deadline = str(new.get("deadline", "")).casefold().strip()
            if old_deadline != new_deadline:
                changes.append({"status": "modified", "before": old, "after": new})
            continue
        candidates = [
            (
                index,
                difflib.SequenceMatcher(
                    None,
                    identity[1],
                    str(item.get("obligation", "")).casefold().strip(),
                ).ratio(),
            )
            for index, item in enumerate(remaining)
            if str(item.get("responsible_party", "")).casefold().strip() == identity[0]
        ]
        best = max(candidates, key=lambda candidate: candidate[1], default=None)
        if best and best[1] >= 0.55:
            new = remaining.pop(best[0])
            changes.append({"status": "modified", "before": old, "after": new})
        else:
            changes.append({"status": "removed", "before": old, "after": None})
    changes.extend({"status": "added", "before": None, "after": item} for item in remaining)
    return changes
