#!/usr/bin/env python3
"""Tests for verify_sum.py. Run with: python scripts/test_verify_sum.py

Covers the states a workshop ledger actually ends up in: a stale total after a
merge, malformed cells, duplicated total rows, commented-out leftovers and the
escaped example markup in the instructions.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

import verify_sum  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent


def row(name: str, number: str, notes: str = "") -> str:
    return (
        '    <tr class="entry-row">\n'
        f'      <td class="name">{name}</td>\n'
        f'      <td class="num">{number}</td>\n'
        f'      <td class="notes">{notes}</td>\n'
        "    </tr>\n"
    )


def build(rows: str, total: str = "10", table_id: str = "ledger") -> str:
    return (
        "<!DOCTYPE html>\n<html><body>\n"
        f'<table id="{table_id}">\n'
        "  <thead><tr><th>Participant</th><th>Number</th><th>Notes</th></tr></thead>\n"
        "  <tbody>\n"
        f"{rows}"
        '    <tr class="total-row">\n'
        "      <td>Total</td>\n"
        f'      <td id="total">{total}</td>\n'
        '      <td class="notes">manual</td>\n'
        "    </tr>\n"
        "  </tbody>\n</table>\n</body></html>\n"
    )


def run(text: str) -> tuple[bool, str]:
    parsed = verify_sum.parse_ledger(text)
    report, ok = verify_sum.render(parsed, Path("index.html"))
    return ok, report


CASES: list[tuple[str, str, bool, str]] = [
    (
        "seed ledger passes",
        build(row("Instructor", "10", "Initial seed"), total="10"),
        True,
        "PASSED",
    ),
    (
        "two rows, correct total",
        build(row("Instructor", "10") + row("Ana", "7"), total="17"),
        True,
        "Sum of rows:      17",
    ),
    (
        "stale total after someone else merged",
        build(row("Instructor", "10") + row("Ana", "7") + row("Mihai", "5"), total="17"),
        False,
        "5 lower than the sum",
    ),
    (
        "total too high",
        build(row("Instructor", "10"), total="25"),
        False,
        "15 higher than the sum",
    ),
    (
        "number with units is rejected",
        build(row("Ana", "7 points"), total="7"),
        False,
        "not a plain integer",
    ),
    (
        "decimal is rejected",
        build(row("Ana", "3.5"), total="3"),
        False,
        "not a plain integer",
    ),
    (
        "thousands separator is rejected",
        build(row("Ana", "1 000"), total="1000"),
        False,
        "not a plain integer",
    ),
    (
        "empty number cell is rejected",
        build(row("Ana", ""), total="0"),
        False,
        "is empty",
    ),
    (
        "negative numbers are allowed",
        build(row("Ana", "-4") + row("Mihai", "10"), total="6"),
        True,
        "PASSED",
    ),
    (
        "whitespace around the number is tolerated",
        build('    <tr class="entry-row">\n'
              '      <td>Ana</td>\n'
              '      <td class="num">  7  </td>\n'
              '      <td>hi</td>\n'
              "    </tr>\n", total="7"),
        True,
        "PASSED",
    ),
    (
        "single-quoted attributes are tolerated",
        build("    <tr class='entry-row'>\n"
              "      <td>Ana</td>\n"
              "      <td class='num'>7</td>\n"
              "      <td>hi</td>\n"
              "    </tr>\n", total="7"),
        True,
        "PASSED",
    ),
    (
        "number cell without class=num still found by position",
        build("    <tr>\n"
              "      <td>Ana</td>\n"
              "      <td>7</td>\n"
              "      <td>hi</td>\n"
              "    </tr>\n", total="7"),
        True,
        "PASSED",
    ),
    (
        "row missing its notes cell is rejected",
        build('    <tr class="entry-row">\n'
              '      <td>Ana</td>\n'
              '      <td class="num">7</td>\n'
              "    </tr>\n", total="7"),
        False,
        "needs exactly 3",
    ),
    (
        "row with an extra cell is rejected",
        build('    <tr class="entry-row">\n'
              '      <td>Ana</td>\n'
              '      <td class="num">7</td>\n'
              '      <td>hi</td>\n'
              '      <td>leftover</td>\n'
              "    </tr>\n", total="7"),
        False,
        "one is extra",
    ),
    (
        "leftover conflict markers are rejected",
        build(row("Instructor", "10"), total="10").replace(
            "  </tbody>",
            "<<<<<<< HEAD\n" + row("Ana", "7") + "=======\n" + row("Mihai", "5")
            + ">>>>>>> main\n  </tbody>",
        ),
        False,
        "still contains Git conflict markers",
    ),
    (
        "a long line of equals is not a conflict marker",
        build(row("Ana", "7"), total="7").replace(
            "<tbody>", "<tbody>\n=============================="
        ),
        True,
        "PASSED",
    ),
    (
        "empty notes cell is fine",
        build(row("Ana", "7", ""), total="7"),
        True,
        "PASSED",
    ),
    (
        "naive resolution absorbs a row into a duplicate total",
        build(
            row("Ana", "7", "first try")
            + '    <tr class="total-row">\n'
            "      <td>Total</td>\n"
            '      <td id="total">17</td>\n'
            '      <td class="name">Mihai</td>\n'
            '      <td class="num">5</td>\n'
            '      <td class="notes">hello</td>\n'
            "    </tr>\n",
            total="15",
        ),
        False,
        'Found 2 cells with id="total"',
    ),
    (
        "duplicated total row is rejected",
        build(row("Ana", "7"), total="7").replace(
            "</tbody>",
            '    <tr class="total-row">\n'
            "      <td>Total</td>\n"
            '      <td id="total">7</td>\n'
            "    </tr>\n  </tbody>",
        ),
        False,
        'Found 2 cells with id="total"',
    ),
    (
        "unedited template row is rejected",
        build(row("Your Name", "0"), total="0"),
        False,
        "still says 'Your Name'",
    ),
    (
        "missing total cell is rejected",
        build(row("Ana", "7"), total="7").replace('<td id="total">7</td>', "<td>7</td>"),
        False,
        "Could not find",
    ),
    (
        "ledger table without its id is rejected",
        build(row("Ana", "7"), total="7", table_id="totals"),
        False,
        'Could not find <table id="ledger">',
    ),
    (
        "commented-out row is ignored",
        build("    <!-- " + row("Ghost", "99").replace("\n", " ") + " -->\n"
              + row("Ana", "7"), total="7"),
        True,
        "PASSED",
    ),
    (
        "commented-out total cell does not look duplicated",
        build(row("Ana", "7"), total="7").replace(
            "<tbody>", '<tbody>\n    <!-- <td id="total">999</td> -->'
        ),
        True,
        "PASSED",
    ),
    (
        "escaped example markup is ignored",
        build(row("Ana", "7"), total="7").replace(
            "</body>",
            "<pre><code>&lt;tr class=\"entry-row\"&gt;\n"
            '  &lt;td class="num"&gt;999&lt;/td&gt;\n'
            "&lt;/tr&gt;\n"
            '&lt;td id="total"&gt;999&lt;/td&gt;</code></pre>\n</body>',
        ),
        True,
        "PASSED",
    ),
    (
        "duplicate row warns but still passes",
        build(row("Ana", "7", "hi") + row("Ana", "7", "hi"), total="14"),
        True,
        "appears 2 times",
    ),
    (
        "no participant rows is a failure",
        build("", total="0"),
        False,
        "no participant rows found",
    ),
]


def main() -> int:
    failures: list[str] = []

    for name, text, expect_ok, expect_snippet in CASES:
        ok, report = run(text)
        problems = []
        if ok is not expect_ok:
            problems.append(f"expected ok={expect_ok}, got ok={ok}")
        if expect_snippet not in report:
            problems.append(f"expected report to contain {expect_snippet!r}")
        if problems:
            failures.append(name)
            print(f"FAIL  {name}")
            for problem in problems:
                print(f"        {problem}")
            print("        --- report ---")
            for line in report.splitlines():
                print(f"        {line}")
            print("        --------------")
        else:
            print(f"ok    {name}")

    # The real page must ship green.
    real = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
    ok, report = run(real)
    if not ok:
        failures.append("index.html")
        print("FAIL  index.html does not pass its own check")
        print(report)
    else:
        print(f"ok    index.html ({report.splitlines()[-1]})")

    print()
    if failures:
        print(f"{len(failures)} failure(s): {', '.join(failures)}")
        return 1
    print(f"All {len(CASES) + 1} checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
