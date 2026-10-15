#!/usr/bin/env python3
"""Check that the ledger's declared total equals the sum of the participant rows.

Run it locally before you push:

    python scripts/verify_sum.py

GitHub Actions runs this exact script on every pull request, so what you see
here is what the check on your PR will say.

Exits 0 when the ledger adds up, 1 otherwise.
"""

from __future__ import annotations

import html as html_module
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TARGET = REPO_ROOT / "index.html"

TABLE_RE = re.compile(r"<table\b([^>]*)>(.*?)</table>", re.DOTALL | re.IGNORECASE)
TBODY_RE = re.compile(r"<tbody\b[^>]*>(.*?)</tbody>", re.DOTALL | re.IGNORECASE)
ROW_RE = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.DOTALL | re.IGNORECASE)
CELL_RE = re.compile(r"<t([dh])\b([^>]*)>(.*?)</t\1>", re.DOTALL | re.IGNORECASE)
TOTAL_CELL_RE = re.compile(
    r"""<t[dh]\b[^>]*\bid\s*=\s*["']total["'][^>]*>(.*?)</t[dh]>""",
    re.DOTALL | re.IGNORECASE,
)
ID_RE = re.compile(r"""\bid\s*=\s*["']([^"']*)["']""", re.IGNORECASE)
CLASS_RE = re.compile(r"""\bclass\s*=\s*["']([^"']*)["']""", re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]+>")
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
CONFLICT_MARKER_RE = re.compile(
    r"^(?:<{7}(?=[ \t]|$)|={7}$|>{7}(?=[ \t]|$))", re.MULTILINE
)
INTEGER_RE = re.compile(r"^[+-]?[0-9]+$")

PLACEHOLDER_NAME = "your name"


def line_of(text: str, offset: int) -> int:
    """1-based line number for a character offset in `text`."""
    return text.count("\n", 0, offset) + 1


def strip_comments(text: str) -> str:
    """Blank out HTML comments while keeping every offset and line number intact.

    Commented-out rows are instructions or leftovers, never ledger data - and a
    commented-out example of the total cell would otherwise look like a
    duplicated total.
    """
    return COMMENT_RE.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)


def plain(fragment: str) -> str:
    """Strip tags, unescape entities, collapse whitespace."""
    return re.sub(r"\s+", " ", html_module.unescape(TAG_RE.sub(" ", fragment))).strip()


def classes(attrs: str) -> list[str]:
    match = CLASS_RE.search(attrs)
    return match.group(1).split() if match else []


def parse_ledger(raw_text: str) -> dict:
    text = strip_comments(raw_text)

    result = {
        "rows": [],        # {"name", "number", "notes", "line"}
        "total": None,
        "total_line": None,
        "errors": [],      # fatal, fail the build
        "warnings": [],    # suspicious, do not fail the build
    }

    markers = list(CONFLICT_MARKER_RE.finditer(text))
    if markers:
        lines = ", ".join(str(line_of(text, m.start())) for m in markers[:8])
        more = "" if len(markers) <= 8 else f" (+{len(markers) - 8} more)"
        result["errors"].append(
            f"Line(s) {lines}{more}: this file still contains Git conflict "
            "markers (<<<<<<<, =======, >>>>>>>). The merge was never finished. "
            "Decide what the file should say, delete every marker line, keep the "
            "content you want, then commit again."
        )
        return result

    ledger = None
    for match in TABLE_RE.finditer(text):
        id_match = ID_RE.search(match.group(1))
        if id_match and id_match.group(1) == "ledger":
            ledger = match
            break

    if ledger is None:
        result["errors"].append(
            'Could not find <table id="ledger"> in this file. '
            "Was the table deleted or renamed while resolving a conflict?"
        )
        return result

    table_body = ledger.group(2)
    table_body_start = ledger.start(2)

    # Scope to <tbody> when present so headings, legends and the <pre> snippets
    # in the instructions below can never be mistaken for ledger data.
    body = TBODY_RE.search(table_body)
    body_text = body.group(1) if body else table_body
    body_offset = table_body_start + (body.start(1) if body else 0)

    totals = list(TOTAL_CELL_RE.finditer(text))
    if not totals:
        result["errors"].append(
            'Could not find <td id="total">...</td>. '
            "Every ledger needs exactly one total cell."
        )
    elif len(totals) > 1:
        lines = ", ".join(str(line_of(text, m.start())) for m in totals)
        result["errors"].append(
            f'Found {len(totals)} cells with id="total" (lines {lines}). '
            "An id must be unique. This is usually a merge conflict that was "
            "resolved by keeping both sides, which absorbs a participant row "
            "into a duplicated total row. There should be exactly one "
            '<tr class="total-row">, and every participant needs their own '
            'complete <tr class="entry-row"> with three cells.'
        )
    else:
        cell = totals[0]
        raw = plain(cell.group(1))
        result["total_line"] = line_of(text, cell.start())
        if INTEGER_RE.match(raw):
            result["total"] = int(raw)
        else:
            result["errors"].append(
                f'Line {result["total_line"]}: the total cell contains {raw!r}, '
                "which is not a plain integer. Write only digits there, "
                'e.g. <td id="total">42</td>.'
            )

    for row in ROW_RE.finditer(body_text):
        row_line = line_of(text, body_offset + row.start())
        inner = row.group(1)
        inner_offset = body_offset + row.start(1)

        if TOTAL_CELL_RE.search(inner):
            continue  # the total row is not a participant

        cells = [
            {
                "attrs": m.group(2),
                "text": plain(m.group(3)),
                "line": line_of(text, inner_offset + m.start()),
            }
            for m in CELL_RE.finditer(inner)
        ]

        if not cells:
            continue  # empty spacer row

        if len(cells) != 3:
            problem = "one is missing" if len(cells) < 3 else "one is extra"
            result["errors"].append(
                f"Line {row_line}: this row has {len(cells)} cell(s) but needs "
                f"exactly 3 (Participant, Number, Notes) - {problem}. "
                "A cell was probably added or half-deleted while resolving a "
                "merge conflict. Keep the Notes cell even if it stays empty."
            )
            continue

        name = cells[0]["text"]
        notes = cells[2]["text"]

        number_cell = next((c for c in cells if "num" in classes(c["attrs"])), cells[1])
        raw = number_cell["text"]

        if not raw:
            result["errors"].append(
                f"Line {number_cell['line']}: the Number cell for "
                f"{name or 'an unnamed row'} is empty. Put an integer in it."
            )
            continue

        if not INTEGER_RE.match(raw):
            result["errors"].append(
                f"Line {number_cell['line']}: {raw!r} is not a plain integer. "
                'Write it exactly like <td class="num">42</td> - no units, '
                "no spaces, no decimals, no thousands separators."
            )
            continue

        if name.strip().lower() == PLACEHOLDER_NAME:
            result["errors"].append(
                f"Line {row_line}: this row still says 'Your Name'. "
                "Replace it with your actual name."
            )
            continue

        result["rows"].append(
            {"name": name, "number": int(raw), "notes": notes, "line": row_line}
        )

    if not result["errors"]:
        seen: dict[tuple[str, int, str], int] = {}
        for row in result["rows"]:
            key = (row["name"].lower(), row["number"], row["notes"].lower())
            seen[key] = seen.get(key, 0) + 1
        exact_dups = set()
        for (name, number, _), count in seen.items():
            if count > 1:
                exact_dups.add(name)
                result["warnings"].append(
                    f"'{name}' appears {count} times with the number {number}. "
                    "If that is you twice, a merge duplicated your row - delete one."
                )

        names: dict[str, int] = {}
        for row in result["rows"]:
            key = row["name"].lower()
            names[key] = names.get(key, 0) + 1
        for name, count in names.items():
            if count > 1 and name not in exact_dups:
                result["warnings"].append(
                    f"The name '{name}' is used by {count} rows. Not an error, "
                    "but add something to Notes so we can tell you apart."
                )

    return result


def render(parsed: dict, target: Path) -> tuple[str, bool]:
    out: list[str] = []
    rows = parsed["rows"]
    errors = parsed["errors"]
    warnings = parsed["warnings"]
    total = parsed["total"]

    out.append(f"Ledger: {target}")
    out.append("")

    if rows:
        width = max(len(r["name"]) for r in rows)
        width = max(width, len("Participant"))
        out.append(f"  {'#':>3}  {'Participant':<{width}}  {'Number':>6}  Notes")
        for index, row in enumerate(rows, start=1):
            out.append(
                f"  {index:>3}  {row['name']:<{width}}  {row['number']:>6}  {row['notes']}"
            )
        out.append("")

    actual = sum(row["number"] for row in rows)
    out.append(f"  Rows:             {len(rows)}")
    out.append(f"  Sum of rows:      {actual}")
    if total is None:
        out.append("  Declared total:   (unreadable)")
    else:
        where = f" (line {parsed['total_line']})" if parsed["total_line"] else ""
        out.append(f"  Declared total:   {total}{where}")
        out.append(f"  Difference:       {total - actual:+d}")
    out.append("")

    for warning in warnings:
        out.append(f"warning: {warning}")
    if warnings:
        out.append("")

    ok = not errors and total is not None and total == actual and bool(rows)

    for error in errors:
        out.append(f"error: {error}")

    if errors:
        out.append("")
        out.append("FAILED - fix the errors above and run this script again.")
    elif total != actual:
        diff = total - actual
        direction = "higher" if diff > 0 else "lower"
        out.append(
            f"FAILED - the declared total is {abs(diff)} {direction} than the sum "
            "of the rows."
        )
        out.append("")
        out.append("  Most likely cause: two branches were merged and the total was")
        out.append("  never re-added. Git merged the text correctly - it just cannot")
        out.append("  know that the Total row means something.")
        out.append("")
        out.append("  Fix: add up the Number column yourself and put the result in")
        out.append(f'  <td id="total">{actual}</td>, then commit and push again.')
    elif not rows:
        out.append("FAILED - no participant rows found.")
        out.append("")
        out.append('  Expected rows shaped like <tr class="entry-row"> inside the')
        out.append('  <tbody> of <table id="ledger">.')
    else:
        out.append(
            f"PASSED - {len(rows)} row(s) sum to {actual} and the declared total "
            f"is {actual}."
        )

    return "\n".join(out), ok


def main(argv: list[str]) -> int:
    target = Path(argv[1]) if len(argv) > 1 else DEFAULT_TARGET

    if not target.is_file():
        print(f"error: {target} does not exist.")
        print("Run this from the repository root, or pass the path to index.html.")
        return 1

    parsed = parse_ledger(target.read_text(encoding="utf-8"))
    report, ok = render(parsed, target)
    print(report)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
