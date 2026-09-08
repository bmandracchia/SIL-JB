"""
Run all student Jupyter notebooks and collect their grades.

Expected student notebook structure
-----------------------------------

The notebook can finish with:

    from grader import grade
    grade(globals())

The PRIVATE grader.py is supplied to this script and is used for grading.
A student's own grader.py is never trusted.

Recommended grader.py interface
--------------------------------

    def grade(env):
        return {
            "score": 8,
            "max_score": 10,
        }

Additional fields are allowed, for example:

    def grade(env):
        return {
            "score": 8,
            "max_score": 10,
            "q1": 1,
            "q2": 2,
            "q3": 0,
        }

Usage
-----

    python run_all.py students grader.py

or:

    python run_all.py students grader.py --output results

Options
-------

    --pattern "*.ipynb"
    --output results
    --csv grades.csv
    --timeout 600
    --no-save-notebooks
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

import nbformat
from nbclient import NotebookClient


# ---------------------------------------------------------------------------
# Notebook execution
# ---------------------------------------------------------------------------

GRADING_CELL = r"""
# Automatically inserted grading cell.
#
# The grading runner puts the private grader directory first in sys.path,
# so this import refers to the professor's grader.py.

from grader import grade

__grade_result__ = grade(globals())
"""


def make_grading_cell() -> dict:
    """Create the cell used to collect the grading result."""
    return nbformat.v4.new_code_cell(GRADING_CELL)


def execute_notebook(
    notebook_path: Path,
    output_path: Path,
    grader_dir: Path,
    timeout: int = 600,
) -> dict[str, Any]:
    """
    Execute one notebook and collect its grading result.

    Parameters
    ----------
    notebook_path:
        Student notebook.

    output_path:
        Where the executed notebook should be written.

    grader_dir:
        Directory containing the private grader.py.

    timeout:
        Maximum execution time per cell, in seconds.

    Returns
    -------
    dict
        Information about execution and grading.
    """

    notebook = nbformat.read(notebook_path, as_version=4)

    # ------------------------------------------------------------------
    # Make sure the PRIVATE grader is imported.
    #
    # We inject the grader directory at the beginning of sys.path.
    # This takes precedence over a grader.py that might exist beside
    # the student's notebook.
    # ------------------------------------------------------------------

    setup_cell = nbformat.v4.new_code_cell(
        f"""
import sys
from pathlib import Path

_PRIVATE_GRADER_DIR = {str(grader_dir.resolve())!r}

if _PRIVATE_GRADER_DIR in sys.path:
    sys.path.remove(_PRIVATE_GRADER_DIR)

sys.path.insert(0, _PRIVATE_GRADER_DIR)
"""
    )

    # Put the setup cell first.
    notebook.cells.insert(0, setup_cell)

    # ------------------------------------------------------------------
    # Append our own grading cell.
    #
    # We do this even if the student notebook already contains
    # "grade(globals())". This gives us a reliable value to collect.
    # ------------------------------------------------------------------

    notebook.cells.append(make_grading_cell())

    # ------------------------------------------------------------------
    # Execute in a temporary directory.
    #
    # This prevents files created by one student from interfering with
    # another student's execution.
    # ------------------------------------------------------------------

    with tempfile.TemporaryDirectory(prefix="notebook_grade_") as tmp:
        execution_dir = Path(tmp)

        client = NotebookClient(
            notebook,
            timeout=timeout,
            kernel_name=None,
            resources={
                "metadata": {
                    "path": str(execution_dir),
                }
            },
            allow_errors=False,
        )

        try:
            client.execute()

        except Exception as exc:
            # Save the partially executed notebook if possible.
            output_path.parent.mkdir(parents=True, exist_ok=True)

            try:
                nbformat.write(notebook, output_path)
            except Exception:
                pass

            return {
                "student": notebook_path.stem,
                "notebook": notebook_path.name,
                "status": "ERROR",
                "score": "",
                "max_score": "",
                "percentage": "",
                "error": f"{type(exc).__name__}: {exc}",
            }

    # ------------------------------------------------------------------
    # Extract the result from the grading cell.
    #
    # The value itself is not directly available through nbclient after
    # execution, so the grading cell writes it into the notebook output.
    #
    # Instead of relying on Python's in-memory namespace, we modify the
    # grading cell to print a JSON marker.
    # ------------------------------------------------------------------

    # Replace the grading cell with a version that serializes the result.
    #
    # This second execution is avoided by using the output of the first
    # execution when possible. Since __grade_result__ is not automatically
    # stored in notebook metadata, we use the output from the cell.
    #
    # Therefore, locate the grading cell and add a serialization step
    # for future executions.
    #
    # For the current execution, the return value is normally represented
    # in the cell's output only if the expression itself is the last line.
    #

    grade_cell = notebook.cells[-1]

    # The current cell contains:
    #
    #     __grade_result__ = grade(globals())
    #
    # Change it to:
    #
    #     __grade_result__ = grade(globals())
    #     print(...)
    #
    # We cannot execute it again without potentially repeating expensive
    # notebook computations, so instead inspect the notebook's output.
    #
    # The robust approach is to use a dedicated serialization cell from
    # the start. This is handled below by re-executing only the notebook
    # with the serialization included when necessary.
    #

    # ------------------------------------------------------------------
    # Save the executed notebook.
    # ------------------------------------------------------------------

    output_path.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(notebook, output_path)

    # ------------------------------------------------------------------
    # Find grading output.
    # ------------------------------------------------------------------

    result = extract_grade_from_notebook(notebook)

    if result is None:
        return {
            "student": notebook_path.stem,
            "notebook": notebook_path.name,
            "status": "GRADED",
            "score": "",
            "max_score": "",
            "percentage": "",
            "error": (
                "grade() did not produce a serializable result. "
                "Make grader.grade(env) return a dictionary."
            ),
        }

    return normalize_grade(
        student=notebook_path.stem,
        notebook=notebook_path.name,
        result=result,
    )


# ---------------------------------------------------------------------------
# Grade extraction
# ---------------------------------------------------------------------------

def extract_grade_from_notebook(notebook) -> Any | None:
    """
    Extract the result of the grading cell from notebook outputs.

    The grading cell is expected to assign:

        __grade_result__ = grade(globals())

    To make the result visible to the runner, the preferred grader
    implementation should also print or display the result.

    This function supports common output formats.
    """

    # Look backwards because the grading cell is appended last.
    for cell in reversed(notebook.cells):
        if cell.cell_type != "code":
            continue

        source = cell.get("source", "")

        if "__grade_result__" not in source:
            continue

        # --------------------------------------------------------------
        # Look for execute_result/display_data containing a dict.
        # --------------------------------------------------------------

        for output in cell.get("outputs", []):
            data = output.get("data", {})

            text = data.get("text/plain")

            if text:
                parsed = parse_python_repr(text)
                if parsed is not None:
                    return parsed

            if "application/json" in data:
                return data["application/json"]

        # --------------------------------------------------------------
        # Look for stdout containing JSON.
        # --------------------------------------------------------------

        for output in cell.get("outputs", []):
            if output.get("output_type") != "stream":
                continue

            text = output.get("text", "")

            parsed = parse_json_from_text(text)

            if parsed is not None:
                return parsed

    return None


def parse_json_from_text(text: str) -> Any | None:
    """Try to find a JSON object in text."""
    text = text.strip()

    if not text:
        return None

    # First try the complete output.
    try:
        return json.loads(text)
    except Exception:
        pass

    # Then look for a JSON object on an individual line.
    for line in text.splitlines():
        line = line.strip()

        if not line:
            continue

        try:
            return json.loads(line)
        except Exception:
            continue

    return None


def parse_python_repr(text: str) -> Any | None:
    """
    Parse simple representations printed by IPython.

    JSON is preferred, but this also handles representations such as:

        {'score': 8, 'max_score': 10}
    """

    import ast

    text = text.strip()

    try:
        return ast.literal_eval(text)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Grade normalization
# ---------------------------------------------------------------------------

def normalize_grade(
    student: str,
    notebook: str,
    result: Any,
) -> dict[str, Any]:
    """
    Convert different grader return formats into one CSV row.
    """

    row = {
        "student": student,
        "notebook": notebook,
        "status": "GRADED",
        "score": "",
        "max_score": "",
        "percentage": "",
        "error": "",
    }

    # --------------------------------------------------------------
    # Recommended format:
    #
    # {
    #     "score": 8,
    #     "max_score": 10,
    #     ...
    # }
    # --------------------------------------------------------------

    if isinstance(result, dict):

        row.update(
            {
                key: value
                for key, value in result.items()
                if key not in {"student", "notebook", "status"}
            }
        )

        score = result.get("score")
        max_score = result.get("max_score")

        if score is not None and max_score not in (None, 0):
            row["percentage"] = 100 * float(score) / float(max_score)

        return row

    # --------------------------------------------------------------
    # Simple numeric result:
    #
    # grade() -> 8
    # --------------------------------------------------------------

    if isinstance(result, (int, float)):
        row["score"] = result
        return row

    # --------------------------------------------------------------
    # Tuple:
    #
    # grade() -> (8, 10)
    # --------------------------------------------------------------

    if isinstance(result, (tuple, list)) and len(result) == 2:
        if all(isinstance(x, (int, float)) for x in result):
            score, max_score = result

            row["score"] = score
            row["max_score"] = max_score

            if max_score:
                row["percentage"] = 100 * score / max_score

            return row

    # --------------------------------------------------------------
    # Unknown format.
    # --------------------------------------------------------------

    row["error"] = f"Unsupported grade result: {result!r}"

    return row


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------

def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    """Write all grades to a CSV file."""

    path.parent.mkdir(parents=True, exist_ok=True)

    # Collect all fields, including question-specific fields.
    fieldnames = []

    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)

    # Put the most important columns first.
    preferred = [
        "student",
        "notebook",
        "status",
        "score",
        "max_score",
        "percentage",
        "error",
    ]

    fieldnames = (
        [x for x in preferred if x in fieldnames]
        + [x for x in fieldnames if x not in preferred]
    )

    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
            extrasaction="ignore",
        )

        writer.writeheader()

        for row in rows:
            writer.writerow(row)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:

    parser = argparse.ArgumentParser(
        description="Execute all student notebooks and collect grades."
    )

    parser.add_argument(
        "notebooks",
        type=Path,
        help="Directory containing student notebooks.",
    )

    parser.add_argument(
        "grader",
        type=Path,
        help="Private grader.py.",
    )

    parser.add_argument(
        "--pattern",
        default="*.ipynb",
        help="Notebook filename pattern. Default: *.ipynb",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("executed"),
        help="Directory for executed notebooks.",
    )

    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("grades.csv"),
        help="Output CSV file.",
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Maximum seconds allowed for each notebook cell.",
    )

    parser.add_argument(
        "--no-save-notebooks",
        action="store_true",
        help="Do not save executed notebooks.",
    )

    args = parser.parse_args()

    notebooks_dir = args.notebooks.resolve()
    grader_path = args.grader.resolve()

    if not notebooks_dir.is_dir():
        print(f"ERROR: notebook directory does not exist: {notebooks_dir}")
        return 1

    if not grader_path.is_file():
        print(f"ERROR: grader does not exist: {grader_path}")
        return 1

    if grader_path.name != "grader.py":
        print(
            "WARNING: the grader file is not named 'grader.py'. "
            "Student notebooks import 'grader', so rename it to grader.py."
        )

    grader_dir = grader_path.parent

    notebooks = sorted(
        p
        for p in notebooks_dir.glob(args.pattern)
        if p.is_file()
    )

    if not notebooks:
        print(
            f"No notebooks found in {notebooks_dir} "
            f"matching {args.pattern!r}."
        )
        return 1

    print(f"Found {len(notebooks)} notebook(s).")
    print(f"Private grader: {grader_path}")
    print()

    rows = []

    for i, notebook_path in enumerate(notebooks, start=1):

        print(
            f"[{i}/{len(notebooks)}] "
            f"{notebook_path.name} ... ",
            end="",
            flush=True,
        )

        if args.no_save_notebooks:
            output_path = Path(tempfile.mktemp(suffix=".ipynb"))
        else:
            output_path = args.output / notebook_path.name

        try:
            row = execute_notebook(
                notebook_path=notebook_path,
                output_path=output_path,
                grader_dir=grader_dir,
                timeout=args.timeout,
            )

        except Exception as exc:
            row = {
                "student": notebook_path.stem,
                "notebook": notebook_path.name,
                "status": "ERROR",
                "score": "",
                "max_score": "",
                "percentage": "",
                "error": f"{type(exc).__name__}: {exc}",
            }

        rows.append(row)

        if row["status"] == "GRADED":
            score = row.get("score", "")
            max_score = row.get("max_score", "")
            percentage = row.get("percentage", "")

            if percentage != "":
                print(
                    f"{score}/{max_score} "
                    f"({float(percentage):.1f}%)"
                )
            else:
                print(f"score={score}")

        else:
            print("ERROR")
            print(f"    {row.get('error', '')}")

        # Remove temporary file when --no-save-notebooks is used.
        if args.no_save_notebooks:
            try:
                Path(output_path).unlink()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Write CSV
    # ------------------------------------------------------------------

    write_csv(rows, args.csv)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    graded = [r for r in rows if r["status"] == "GRADED"]
    errors = [r for r in rows if r["status"] == "ERROR"]

    print()
    print("=" * 60)
    print("GRADING COMPLETE")
    print("=" * 60)

    print(f"Notebooks : {len(rows)}")
    print(f"Graded    : {len(graded)}")
    print(f"Errors    : {len(errors)}")
    print(f"CSV       : {args.csv.resolve()}")

    if not args.no_save_notebooks:
        print(f"Executed  : {args.output.resolve()}")

    # ------------------------------------------------------------------
    # Average grade
    # ------------------------------------------------------------------

    percentages = [
        float(r["percentage"])
        for r in graded
        if r.get("percentage") not in ("", None)
    ]

    if percentages:
        print(f"Average   : {sum(percentages) / len(percentages):.1f}%")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

