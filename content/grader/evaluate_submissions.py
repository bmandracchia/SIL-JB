"""
evaluate_submissions.py

Create a single Excel workbook for grading CSV submissions exported by widgets.py.

The workbook contains:
    1) grades
    2) manual_grading
    3) code_tests          (only when code questions are present)
    4) summary

Main features
-------------
- Automatic grading from answer_key.csv
- Manual questions collected in one sheet
- Linked formulas from "grades" to "manual_grading"
- Editable cells highlighted automatically
- Formula cells locked and sheets protected
- Data validation so manual_score stays between 0 and max_points
- Detailed test-by-test report for code questions
- Choice between all-or-nothing and proportional code-test scoring
- Summary sheet with class statistics and grade distribution

WORKFLOW
========

1. The instructor answers the same notebook and exports:
       answer_key.csv

2. Students submit their CSV files into one directory:
       submissions/

3. Run:
       python evaluate_submissions.py submissions answer_key.csv

   This creates:
       grading_workbook.xlsx

4. Open the workbook, fill the "manual_score" cells in the "manual_grading"
   sheet, and save. The "grades" sheet will automatically show the manual
   question scores, final scores and percentages.

DEPENDENCIES
============
    pip install pandas numpy openpyxl
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Font, PatternFill, Protection
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation


# =============================================================================
# INSTRUCTOR CONFIGURATION
# =============================================================================

DEFAULT_POINTS = 1.0
DEFAULT_RTOL = 1e-5
DEFAULT_ATOL = 1e-8

# Configure only questions that differ from the defaults.
#
# Example:
#
# QUESTION_CONFIG = {
#     "q1": {
#         "points": 2,
#         "rtol": 1e-4,
#     },
#
#     "q3": {
#         "points": 3,
#         "partial_credit": True,
#     },
#
#     "q5": {
#         "points": 2,
#         "mode": "manual",
#     },
#
#     "q12": {
#         "points": 2,
#         "mode": "code",
#         "timeout": 3,
#         "test_scoring": "all",  # "all" or "proportional"
#         "tests": [
#             "assert np.isclose(H(0), 1.0)",
#             {
#                 "name": "Value at t=1",
#                 "code": "assert np.isclose(H(1), 0.5)",
#             },
#         ],
#     },
# }
#
# Available modes:
#   "auto"   -> compare with answer_key.csv
#   "manual" -> add the answer to the manual_grading sheet
#   "code"   -> execute submitted code and the tests listed here
#
# Code scoring:
#   "all"          -> full credit only if all tests pass
#   "proportional" -> score proportional to tests passed
#
QUESTION_CONFIG: dict[str, dict[str, Any]] = {}

DEFAULT_CODE_TEST_SCORING = "all"

DEFAULT_MANUAL_TYPES = {
    "manual_text",
}


# =============================================================================
# CSV FORMAT
# =============================================================================

STANDARD_COLUMNS = {
    "question_id",
    "question_type",
    "answered",
    "answer",
    "exported_at_utc",
}

REQUIRED_COLUMNS = {
    "question_id",
    "question_type",
    "answered",
    "answer",
}


# =============================================================================
# BASIC HELPERS
# =============================================================================

def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {
        "true", "1", "yes", "y", "si", "sí"
    }


def parse_answer(value: Any) -> Any:
    """Decode the JSON stored in the answer column."""
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def is_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float, complex, np.number))
        and not isinstance(value, (bool, np.bool_))
    )


def numbers_close(
    student: Any,
    expected: Any,
    *,
    rtol: float,
    atol: float,
) -> bool:
    try:
        return bool(
            np.isclose(
                complex(student),
                complex(expected),
                rtol=rtol,
                atol=atol,
                equal_nan=True,
            )
        )
    except (TypeError, ValueError, OverflowError):
        return False


# =============================================================================
# ANSWER COMPARISON
# =============================================================================

def compare_values(
    student: Any,
    expected: Any,
    *,
    rtol: float,
    atol: float,
) -> bool:
    """
    Recursive comparison for JSON-compatible values.

    - numbers: tolerance-based
    - strings and booleans: exact
    - lists: same order
    - dictionaries: same keys
    """
    if is_number(student) and is_number(expected):
        return numbers_close(
            student,
            expected,
            rtol=rtol,
            atol=atol,
        )

    if isinstance(student, dict) and isinstance(expected, dict):
        if set(student) != set(expected):
            return False
        return all(
            compare_values(
                student[key],
                expected[key],
                rtol=rtol,
                atol=atol,
            )
            for key in expected
        )

    if isinstance(student, list) and isinstance(expected, list):
        if len(student) != len(expected):
            return False
        return all(
            compare_values(s, e, rtol=rtol, atol=atol)
            for s, e in zip(student, expected)
        )

    return student == expected


def compare_multiple_choice(student: Any, expected: Any) -> bool:
    """
    Compare checkbox-group answers.

    The order of sub-questions matters, but the order inside each selected list
    does not matter.
    """
    if not isinstance(student, list) or not isinstance(expected, list):
        return False
    if len(student) != len(expected):
        return False

    for s, e in zip(student, expected):
        if not isinstance(s, list) or not isinstance(e, list):
            return False
        if set(s) != set(e):
            return False

    return True


def compare_question(
    student: Any,
    expected: Any,
    *,
    question_type: str,
    rtol: float,
    atol: float,
) -> bool:
    if question_type == "multiple_choice":
        return compare_multiple_choice(student, expected)
    return compare_values(
        student,
        expected,
        rtol=rtol,
        atol=atol,
    )


def partial_fraction(
    student: Any,
    expected: Any,
    *,
    question_type: str,
    rtol: float,
    atol: float,
) -> float:
    """
    Fraction of correct top-level components for partial credit.
    """
    if question_type == "multiple_choice":
        if not isinstance(student, list) or not isinstance(expected, list):
            return 0.0
        if len(student) != len(expected) or not expected:
            return 0.0

        correct = 0
        for s, e in zip(student, expected):
            if isinstance(s, list) and isinstance(e, list) and set(s) == set(e):
                correct += 1
        return correct / len(expected)

    if isinstance(expected, dict):
        if not expected or not isinstance(student, dict):
            return 0.0
        correct = sum(
            key in student
            and compare_values(
                student[key],
                expected[key],
                rtol=rtol,
                atol=atol,
            )
            for key in expected
        )
        return correct / len(expected)

    if isinstance(expected, list):
        if not expected or not isinstance(student, list):
            return 0.0
        if len(student) != len(expected):
            return 0.0
        correct = sum(
            compare_values(s, e, rtol=rtol, atol=atol)
            for s, e in zip(student, expected)
        )
        return correct / len(expected)

    return float(
        compare_question(
            student,
            expected,
            question_type=question_type,
            rtol=rtol,
            atol=atol,
        )
    )


def question_settings(question_id: str, question_type: str) -> dict[str, Any]:
    config = dict(QUESTION_CONFIG.get(question_id, {}))
    config.setdefault("points", DEFAULT_POINTS)
    config.setdefault("rtol", DEFAULT_RTOL)
    config.setdefault("atol", DEFAULT_ATOL)
    config.setdefault("partial_credit", False)

    if "mode" not in config:
        if question_type in DEFAULT_MANUAL_TYPES:
            config["mode"] = "manual"
        elif question_type == "code":
            config["mode"] = "code"
        else:
            config["mode"] = "auto"

    if config["mode"] == "code":
        config.setdefault("test_scoring", DEFAULT_CODE_TEST_SCORING)

    return config


# =============================================================================
# OPTIONAL CODE EVALUATION
# =============================================================================

def normalize_code_tests(
    settings: dict[str, Any],
) -> list[dict[str, str]]:
    """Normalize string or named-dictionary code tests."""
    normalized = []

    for index, test in enumerate(settings.get("tests", []), start=1):
        if isinstance(test, str):
            normalized.append({
                "name": f"Test {index}",
                "code": test,
            })
        elif isinstance(test, dict) and "code" in test:
            normalized.append({
                "name": str(test.get("name", f"Test {index}")),
                "code": str(test["code"]),
            })
        else:
            raise ValueError(
                "Each code test must be a string or a dictionary "
                "with at least a 'code' field."
            )

    return normalized


def run_one_code_test(
    student_code: str,
    test_code: str,
    *,
    timeout: float,
) -> tuple[bool, str, str]:
    """
    Run one code test in a fresh Python subprocess.

    Returns:
        passed, status, diagnostic

    Status is PASS, FAIL, ERROR or TIMEOUT.
    This protects the batch process from ordinary crashes/infinite loops,
    but it is not a security sandbox against deliberately malicious code.
    """
    program = (
        "import math\n"
        "import numpy as np\n\n"
        "# ===== STUDENT CODE =====\n"
        f"{student_code}\n\n"
        "# ===== INSTRUCTOR TEST =====\n"
        f"{test_code}\n"
    )

    try:
        with tempfile.TemporaryDirectory(prefix="sl_code_test_") as tmp:
            test_file = Path(tmp) / "test_submission.py"
            test_file.write_text(program, encoding="utf-8")

            result = subprocess.run(
                [sys.executable, "-I", str(test_file)],
                cwd=tmp,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

    except subprocess.TimeoutExpired:
        return False, "TIMEOUT", f"Exceeded {timeout} s"

    except Exception as exc:
        return False, "ERROR", f"{type(exc).__name__}: {exc}"

    if result.returncode == 0:
        return True, "PASS", ""

    message = (
        result.stderr
        or result.stdout
        or "Code test failed"
    ).strip()

    status = "FAIL" if "AssertionError" in message else "ERROR"
    return False, status, message[-1500:]


def grade_code(
    student_code: Any,
    settings: dict[str, Any],
) -> tuple[float, str, list[dict[str, Any]]]:
    """
    Grade a code answer and return test-level results.

    test_scoring="all":
        award full question credit only if every test passes.

    test_scoring="proportional":
        award a fraction equal to passed_tests / total_tests.
    """
    tests = normalize_code_tests(settings)
    timeout = float(settings.get("timeout", 3))
    scoring = str(
        settings.get("test_scoring", DEFAULT_CODE_TEST_SCORING)
    ).strip().lower()

    if scoring not in {"all", "proportional"}:
        raise ValueError(
            "test_scoring must be 'all' or 'proportional'."
        )

    if not tests:
        return 0.0, "No code tests configured", [{
            "test_index": "",
            "test_name": "",
            "test_code": "",
            "passed": False,
            "status": "NO_TESTS",
            "diagnostic": "No code tests configured",
        }]

    if not isinstance(student_code, str) or not student_code.strip():
        results = []
        for index, test in enumerate(tests, start=1):
            results.append({
                "test_index": index,
                "test_name": test["name"],
                "test_code": test["code"],
                "passed": False,
                "status": "NOT_RUN",
                "diagnostic": "No code submitted",
            })
        return 0.0, "No code submitted", results

    results = []
    passed_count = 0

    for index, test in enumerate(tests, start=1):
        passed, status, diagnostic = run_one_code_test(
            student_code,
            test["code"],
            timeout=timeout,
        )

        if passed:
            passed_count += 1

        results.append({
            "test_index": index,
            "test_name": test["name"],
            "test_code": test["code"],
            "passed": passed,
            "status": status,
            "diagnostic": diagnostic,
        })

    total_tests = len(tests)

    if scoring == "all":
        fraction = 1.0 if passed_count == total_tests else 0.0
    else:
        fraction = passed_count / total_tests

    diagnostic = (
        f"{passed_count}/{total_tests} tests passed; scoring={scoring}"
    )

    return fraction, diagnostic, results


# =============================================================================
# LOADING
# =============================================================================

def load_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(
        path,
        dtype=str,
        keep_default_na=False,
    )

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            "Missing required columns: " + ", ".join(sorted(missing))
        )

    if df["question_id"].duplicated().any():
        duplicates = sorted(
            df.loc[
                df["question_id"].duplicated(),
                "question_id",
            ].unique()
        )
        raise ValueError(
            "Duplicated question_id values: " + ", ".join(duplicates)
        )

    return df


def one_metadata_value(df: pd.DataFrame, column: str) -> str:
    if column not in df.columns:
        return ""

    values = [
        str(value).strip()
        for value in df[column].tolist()
        if str(value).strip()
    ]
    unique = list(dict.fromkeys(values))

    if not unique:
        return ""
    if len(unique) > 1:
        raise ValueError(
            f"Inconsistent metadata in column {column!r}: {unique}"
        )

    return unique[0]


def metadata_columns(df: pd.DataFrame) -> list[str]:
    return [
        column
        for column in df.columns
        if column not in STANDARD_COLUMNS
    ]


def build_answer_key(df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    key = {}

    for _, row in df.iterrows():
        question_id = str(row["question_id"])
        key[question_id] = {
            "question_type": str(row["question_type"]),
            "answer": parse_answer(row["answer"]),
        }

    return key


# =============================================================================
# ONE SUBMISSION
# =============================================================================

def grade_one_submission(
    submission_path: Path,
    *,
    answer_key: dict[str, dict[str, Any]],
    question_order: list[str],
    expected_assignment_id: str,
    expected_assignment_version: str,
    key_metadata_columns: list[str],
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    df = load_csv(submission_path)

    assignment_id = one_metadata_value(df, "assignment_id")
    assignment_version = one_metadata_value(df, "assignment_version")

    if expected_assignment_id and assignment_id != expected_assignment_id:
        raise ValueError(
            f"assignment_id={assignment_id!r}; expected {expected_assignment_id!r}"
        )

    if expected_assignment_version and assignment_version != expected_assignment_version:
        raise ValueError(
            "assignment_version="
            f"{assignment_version!r}; expected {expected_assignment_version!r}"
        )

    report: dict[str, Any] = {
        "submission_file": submission_path.name,
        "status": "GRADED",
    }

    all_metadata = list(dict.fromkeys(key_metadata_columns + metadata_columns(df)))
    for column in all_metadata:
        report[column] = one_metadata_value(df, column)

    submitted = {
        str(row["question_id"]): row
        for _, row in df.iterrows()
    }

    automatic_score = 0.0
    automatic_max = 0.0
    manual_max = 0.0
    manual_rows: list[dict[str, Any]] = []
    code_test_rows: list[dict[str, Any]] = []
    warnings = []

    extra = sorted(set(submitted) - set(answer_key))
    if extra:
        warnings.append("extra questions ignored: " + ", ".join(extra))

    for question_id in question_order:
        expected_info = answer_key[question_id]
        expected_type = expected_info["question_type"]
        expected_answer = expected_info["answer"]

        settings = question_settings(question_id, expected_type)
        points = float(settings["points"])
        mode = str(settings["mode"]).lower()

        student_row = submitted.get(question_id)

        if student_row is None:
            student_answer = None
            answered = False
            submitted_type = ""
        else:
            student_answer = parse_answer(student_row["answer"])
            answered = parse_bool(student_row["answered"])
            submitted_type = str(student_row["question_type"])

        if submitted_type and submitted_type != expected_type:
            warnings.append(
                f"{question_id}: type={submitted_type!r}; expected {expected_type!r}"
            )

        if mode == "manual":
            manual_max += points
            report[question_id] = ""

            manual_entry = {
                key: report.get(key, "")
                for key in all_metadata
            }
            manual_entry.update(
                {
                    "submission_file": submission_path.name,
                    "question_id": question_id,
                    "question_type": expected_type,
                    "answer": json.dumps(student_answer, ensure_ascii=False),
                    "answered": answered,
                    "max_points": points,
                    "manual_score": "",
                    "comment": "",
                }
            )
            manual_rows.append(manual_entry)
            continue

        automatic_max += points

        if mode == "code":
            fraction, diagnostic, test_results = grade_code(
                student_answer if answered else None,
                settings,
            )
            score = points * fraction

            valid_test_results = [
                result
                for result in test_results
                if result["status"] != "NO_TESTS"
            ]
            passed_tests = sum(
                bool(result["passed"])
                for result in valid_test_results
            )
            total_tests = len(valid_test_results)

            for result in test_results:
                code_entry = {
                    key: report.get(key, "")
                    for key in all_metadata
                }
                code_entry.update({
                    "submission_file": submission_path.name,
                    "question_id": question_id,
                    "question_type": expected_type,
                    "question_points": points,
                    "question_score": round(float(score), 6),
                    "test_scoring": str(
                        settings.get(
                            "test_scoring",
                            DEFAULT_CODE_TEST_SCORING,
                        )
                    ),
                    "passed_tests": passed_tests,
                    "total_tests": total_tests,
                    **result,
                })
                code_test_rows.append(code_entry)

        elif not answered:
            score = 0.0
            diagnostic = "UNANSWERED"

        elif mode == "auto":
            rtol = float(settings["rtol"])
            atol = float(settings["atol"])

            if settings["partial_credit"]:
                fraction = partial_fraction(
                    student_answer,
                    expected_answer,
                    question_type=expected_type,
                    rtol=rtol,
                    atol=atol,
                )
                score = points * fraction
            else:
                correct = compare_question(
                    student_answer,
                    expected_answer,
                    question_type=expected_type,
                    rtol=rtol,
                    atol=atol,
                )
                score = points if correct else 0.0

            diagnostic = ""

        else:
            raise ValueError(
                f"{question_id}: unknown grading mode {mode!r}"
            )

        score = round(float(score), 6)
        automatic_score += score
        report[question_id] = score

        if diagnostic:
            warnings.append(f"{question_id}: {diagnostic}")

    total_max = automatic_max + manual_max

    report["automatic_score"] = round(automatic_score, 6)
    report["automatic_max"] = round(automatic_max, 6)
    report["manual_pending_points"] = round(manual_max, 6)
    report["max_score"] = round(total_max, 6)
    report["final_score"] = ""
    report["percentage"] = ""
    report["warnings"] = " | ".join(warnings)

    return report, manual_rows, code_test_rows


# =============================================================================
# BATCH GRADING
# =============================================================================

def grade_directory(
    submissions_dir: Path,
    answer_key_path: Path,
    *,
    pattern: str = "*.csv",
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    list[str],
]:
    key_df = load_csv(answer_key_path)
    answer_key = build_answer_key(key_df)
    question_order = list(answer_key.keys())

    expected_assignment_id = one_metadata_value(key_df, "assignment_id")
    expected_assignment_version = one_metadata_value(
        key_df,
        "assignment_version",
    )
    key_meta = metadata_columns(key_df)

    files = sorted(
        path
        for path in submissions_dir.glob(pattern)
        if path.is_file() and path.resolve() != answer_key_path.resolve()
    )

    if not files:
        raise FileNotFoundError(
            f"No files matching {pattern!r} were found in {submissions_dir}"
        )

    grade_rows = []
    manual_rows = []
    code_test_rows = []

    for index, path in enumerate(files, start=1):
        print(f"[{index}/{len(files)}] {path.name} ... ", end="")

        try:
            report, pending, code_pending = grade_one_submission(
                path,
                answer_key=answer_key,
                question_order=question_order,
                expected_assignment_id=expected_assignment_id,
                expected_assignment_version=expected_assignment_version,
                key_metadata_columns=key_meta,
            )
            grade_rows.append(report)
            manual_rows.extend(pending)
            code_test_rows.extend(code_pending)

            print(
                f"{report['automatic_score']}/"
                f"{report['automatic_max']} automatic"
            )

        except Exception as exc:
            print("ERROR")
            grade_rows.append(
                {
                    "submission_file": path.name,
                    "status": "ERROR",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    grades_df = pd.DataFrame(grade_rows)
    manual_df = pd.DataFrame(manual_rows)
    code_tests_df = pd.DataFrame(code_test_rows)

    return grades_df, manual_df, code_tests_df, question_order


# =============================================================================
# EXCEL OUTPUT
# =============================================================================

HEADER_FILL = PatternFill(fill_type="solid", fgColor="D9EAF7")
EDITABLE_FILL = PatternFill(fill_type="solid", fgColor="FFF2CC")
LINKED_MANUAL_FILL = PatternFill(fill_type="solid", fgColor="E2F0D9")
FORMULA_FILL = PatternFill(fill_type="solid", fgColor="F2F2F2")
PASS_FILL = PatternFill(fill_type="solid", fgColor="E2F0D9")
FAIL_FILL = PatternFill(fill_type="solid", fgColor="FCE4D6")


def write_dataframe_sheet(ws, df: pd.DataFrame) -> None:
    headers = list(df.columns)
    ws.append(headers)

    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = HEADER_FILL

    for _, row in df.iterrows():
        values = []
        for column in headers:
            value = row[column]
            if pd.isna(value):
                value = ""
            values.append(value)
        ws.append(values)


def autosize_columns(ws, max_width: int = 40) -> None:
    widths = {}
    for row in ws.iter_rows():
        for cell in row:
            value = "" if cell.value is None else str(cell.value)
            widths[cell.column] = max(widths.get(cell.column, 0), len(value))

    for col_idx, width in widths.items():
        ws.column_dimensions[get_column_letter(col_idx)].width = min(width + 2, max_width)


def protect_sheet(ws, *, password: str = "") -> None:
    """
    Activate sheet protection.

    Empty password means the sheet is protected from accidental edits,
    but without a secret password.
    """
    ws.protection.sheet = True
    ws.protection.password = password
    ws.protection.formatCells = False
    ws.protection.formatColumns = False
    ws.protection.formatRows = False
    ws.protection.insertColumns = False
    ws.protection.insertRows = False
    ws.protection.insertHyperlinks = False
    ws.protection.deleteColumns = False
    ws.protection.deleteRows = False
    ws.protection.sort = False
    ws.protection.autoFilter = True
    ws.protection.pivotTables = False
    ws.protection.selectLockedCells = True
    ws.protection.selectUnlockedCells = True


def add_manual_score_validation(ws_manual) -> None:
    """
    Add row-by-row validation:
        0 <= manual_score <= max_points
    """
    headers = [cell.value for cell in ws_manual[1]]
    if "manual_score" not in headers or "max_points" not in headers:
        return

    manual_score_col = headers.index("manual_score") + 1
    max_points_col = headers.index("max_points") + 1

    for row_idx in range(2, ws_manual.max_row + 1):
        score_cell = ws_manual.cell(row=row_idx, column=manual_score_col)
        max_points_ref = f"${get_column_letter(max_points_col)}${row_idx}"

        dv = DataValidation(
            type="decimal",
            operator="between",
            formula1="0",
            formula2=max_points_ref,
            allow_blank=True,
        )
        dv.errorTitle = "Invalid score"
        dv.error = f"Enter a value between 0 and {max_points_ref}."
        dv.promptTitle = "Manual score"
        dv.prompt = "Type a score between 0 and max_points."
        ws_manual.add_data_validation(dv)
        dv.add(score_cell)


def build_summary_sheet(
    wb: Workbook,
    grades_headers: list[str],
    n_rows_grades: int,
    manual_rows_count: int,
) -> None:
    """
    Create a third sheet with class statistics and a grade-distribution chart.

    The statistics and distribution use Excel formulas, so they update
    automatically when manual scores are entered in the workbook.

    The distribution is shown on a normalized 0-10 scale, calculated from the
    percentage column, so it remains meaningful even if an activity does not
    have a maximum raw score of 10.
    """
    ws = wb.create_sheet("summary")

    # -------------------------------------------------------------------------
    # Section labels
    # -------------------------------------------------------------------------

    ws["A1"] = "General"
    ws["A15"] = "Pass statistics"
    ws["A20"] = "Grade distribution (0-10)"

    for cell in ["A1", "A15", "A20"]:
        ws[cell].font = Font(bold=True)
        ws[cell].fill = HEADER_FILL

    # -------------------------------------------------------------------------
    # General statistics
    # -------------------------------------------------------------------------

    ws["A2"] = "Students"
    ws["A3"] = "Graded"
    ws["A4"] = "Errors"
    ws["A5"] = "Manual responses"
    ws["A6"] = "Average automatic score"
    ws["A7"] = "Average final score"
    ws["A8"] = "Std. deviation final score"
    ws["A9"] = "Average percentage"
    ws["A10"] = "Std. deviation percentage"
    ws["A11"] = "Max final score"
    ws["A12"] = "Min final score"
    ws["A13"] = "Median final score"

    # -------------------------------------------------------------------------
    # Pass statistics
    # -------------------------------------------------------------------------

    ws["A16"] = "Passed (>= 50%)"
    ws["A17"] = "Failed (< 50%)"
    ws["A18"] = "Pass rate (%)"

    # -------------------------------------------------------------------------
    # Distribution table
    # -------------------------------------------------------------------------

    ws["A21"] = "Grade interval"
    ws["B21"] = "Students"

    for cell in ws["21:21"]:
        if cell.column <= 2:
            cell.font = Font(bold=True)
            cell.fill = HEADER_FILL

    grade_bins = [
        ("0-1", 0, 10),
        ("1-2", 10, 20),
        ("2-3", 20, 30),
        ("3-4", 30, 40),
        ("4-5", 40, 50),
        ("5-6", 50, 60),
        ("6-7", 60, 70),
        ("7-8", 70, 80),
        ("8-9", 80, 90),
        ("9-10", 90, 100),
    ]

    for row_idx, (label, _, _) in enumerate(grade_bins, start=22):
        ws.cell(row=row_idx, column=1, value=label)

    if n_rows_grades < 2:
        ws["B5"] = manual_rows_count
        autosize_columns(ws)
        return

    header_to_col = {
        header: index + 1
        for index, header in enumerate(grades_headers)
    }

    required_summary_columns = {
        "status",
        "automatic_score",
        "final_score",
        "percentage",
    }
    missing = required_summary_columns - set(header_to_col)
    if missing:
        raise ValueError(
            "Cannot build summary sheet. Missing columns in grades: "
            + ", ".join(sorted(missing))
        )

    first_data_row = 2
    last_data_row = n_rows_grades
    grades_name = "grades"

    def col_ref(name: str) -> str:
        return get_column_letter(header_to_col[name])

    status_rng = (
        f"'{grades_name}'!${col_ref('status')}${first_data_row}:"
        f"${col_ref('status')}${last_data_row}"
    )
    automatic_rng = (
        f"'{grades_name}'!${col_ref('automatic_score')}${first_data_row}:"
        f"${col_ref('automatic_score')}${last_data_row}"
    )
    final_rng = (
        f"'{grades_name}'!${col_ref('final_score')}${first_data_row}:"
        f"${col_ref('final_score')}${last_data_row}"
    )
    percentage_rng = (
        f"'{grades_name}'!${col_ref('percentage')}${first_data_row}:"
        f"${col_ref('percentage')}${last_data_row}"
    )

    # -------------------------------------------------------------------------
    # General statistics formulas
    # -------------------------------------------------------------------------

    ws["B2"] = f'=COUNTA({status_rng})'
    ws["B3"] = f'=COUNTIF({status_rng},"GRADED")'
    ws["B4"] = f'=COUNTIF({status_rng},"ERROR")'
    ws["B5"] = manual_rows_count
    ws["B6"] = (
        f'=IFERROR(AVERAGEIF({status_rng},"GRADED",{automatic_rng}),"")'
    )
    ws["B7"] = (
        f'=IFERROR(AVERAGEIF({status_rng},"GRADED",{final_rng}),"")'
    )

    # STDEV.P is used because the workbook normally contains the complete
    # population of submitted grades for the class, rather than a sample.
    ws["B8"] = (
        f'=IFERROR(STDEV.P(FILTER({final_rng},{status_rng}="GRADED")),"")'
    )

    ws["B9"] = (
        f'=IFERROR(AVERAGEIF({status_rng},"GRADED",{percentage_rng}),"")'
    )
    ws["B10"] = (
        f'=IFERROR(STDEV.P(FILTER({percentage_rng},{status_rng}="GRADED")),"")'
    )
    ws["B11"] = (
        f'=IFERROR(MAXIFS({final_rng},{status_rng},"GRADED"),"")'
    )
    ws["B12"] = (
        f'=IFERROR(MINIFS({final_rng},{status_rng},"GRADED"),"")'
    )
    ws["B13"] = (
        f'=IFERROR(MEDIAN(FILTER({final_rng},{status_rng}="GRADED")),"")'
    )

    # -------------------------------------------------------------------------
    # Pass statistics formulas
    # -------------------------------------------------------------------------

    ws["B16"] = (
        f'=COUNTIFS({status_rng},"GRADED",{percentage_rng},">=50")'
    )
    ws["B17"] = (
        f'=COUNTIFS({status_rng},"GRADED",{percentage_rng},"<50")'
    )
    ws["B18"] = '=IF(B3>0,100*B16/B3,"")'

    # -------------------------------------------------------------------------
    # Grade distribution formulas
    # -------------------------------------------------------------------------
    # The percentage is divided into 10-point intervals, corresponding to
    # normalized grades 0-1, 1-2, ..., 9-10.

    for row_idx, (_, lower, upper) in enumerate(grade_bins, start=22):
        if upper < 100:
            formula = (
                f'=COUNTIFS('
                f'{status_rng},"GRADED",'
                f'{percentage_rng},">={lower}",'
                f'{percentage_rng},"<{upper}")'
            )
        else:
            formula = (
                f'=COUNTIFS('
                f'{status_rng},"GRADED",'
                f'{percentage_rng},">={lower}",'
                f'{percentage_rng},"<=100")'
            )

        ws.cell(row=row_idx, column=2, value=formula)

    # -------------------------------------------------------------------------
    # Number formatting
    # -------------------------------------------------------------------------

    for cell in ["B9", "B10", "B18"]:
        ws[cell].number_format = "0.000"

    for cell in [
        "B6", "B7", "B8", "B11", "B12", "B13"
    ]:
        ws[cell].number_format = "0.000"

    # -------------------------------------------------------------------------
    # Chart
    # -------------------------------------------------------------------------

    chart = BarChart()
    chart.type = "col"
    chart.style = 10
    chart.title = "Grade distribution"
    chart.y_axis.title = "Number of students"
    chart.x_axis.title = "Grade (0-10)"
    chart.height = 8.5
    chart.width = 15.5
    chart.legend = None

    data = Reference(
        ws,
        min_col=2,
        min_row=21,
        max_row=31,
    )
    categories = Reference(
        ws,
        min_col=1,
        min_row=22,
        max_row=31,
    )

    chart.add_data(data, titles_from_data=True)
    chart.set_categories(categories)
    ws.add_chart(chart, "D2")

    ws.freeze_panes = "A2"
    autosize_columns(ws)


def build_workbook(
    grades_df: pd.DataFrame,
    manual_df: pd.DataFrame,
    code_tests_df: pd.DataFrame,
    question_order: list[str],
    output_path: Path,
) -> Path:
    """
    Create an Excel workbook with grades, manual_grading, summary and,
    when code questions are present, a code_tests audit sheet.

    Manual score cells in "grades" are formulas linked to "manual_grading".
    """
    wb = Workbook()
    ws_grades = wb.active
    ws_grades.title = "grades"
    ws_manual = wb.create_sheet("manual_grading")

    # -------------------------------------------------------------------------
    # manual_grading sheet
    # -------------------------------------------------------------------------
    if manual_df.empty:
        manual_headers = [
            "submission_file",
            "question_id",
            "question_type",
            "answer",
            "answered",
            "max_points",
            "manual_score",
            "comment",
        ]
        ws_manual.append(manual_headers)
        for cell in ws_manual[1]:
            cell.font = Font(bold=True)
            cell.fill = HEADER_FILL
    else:
        write_dataframe_sheet(ws_manual, manual_df)

    ws_manual.freeze_panes = "A2"

    manual_headers = [cell.value for cell in ws_manual[1]]
    manual_score_col = manual_headers.index("manual_score") + 1
    comment_col = manual_headers.index("comment") + 1

    # Default: all cells locked
    for row in ws_manual.iter_rows():
        for cell in row:
            cell.protection = Protection(locked=True)

    # Highlight + unlock manual_score and comment cells
    for row_idx in range(2, ws_manual.max_row + 1):
        score_cell = ws_manual.cell(row=row_idx, column=manual_score_col)
        score_cell.fill = EDITABLE_FILL
        score_cell.protection = Protection(locked=False)

        comment_cell = ws_manual.cell(row=row_idx, column=comment_col)
        comment_cell.fill = EDITABLE_FILL
        comment_cell.protection = Protection(locked=False)

    add_manual_score_validation(ws_manual)

    # Map (submission_file, question_id) -> manual_score cell reference
    manual_ref: dict[tuple[str, str], str] = {}
    submission_file_col_manual = manual_headers.index("submission_file") + 1
    question_id_col_manual = manual_headers.index("question_id") + 1

    for row_idx in range(2, ws_manual.max_row + 1):
        submission_file = str(
            ws_manual.cell(row=row_idx, column=submission_file_col_manual).value or ""
        )
        question_id = str(
            ws_manual.cell(row=row_idx, column=question_id_col_manual).value or ""
        )
        coord = ws_manual.cell(row=row_idx, column=manual_score_col).coordinate
        manual_ref[(submission_file, question_id)] = f"'manual_grading'!{coord}"

    # -------------------------------------------------------------------------
    # grades sheet
    # -------------------------------------------------------------------------
    headers = list(grades_df.columns)
    ws_grades.append(headers)

    for cell in ws_grades[1]:
        cell.font = Font(bold=True)
        cell.fill = HEADER_FILL

    header_to_col = {
        header: index + 1
        for index, header in enumerate(headers)
    }

    manual_questions = set()
    if not manual_df.empty and "question_id" in manual_df.columns:
        manual_questions = set(manual_df["question_id"].astype(str).tolist())

    # Default: all cells locked
    for row in ws_grades.iter_rows():
        for cell in row:
            cell.protection = Protection(locked=True)

    for _, row in grades_df.iterrows():
        excel_row = ws_grades.max_row + 1

        # first write the row values
        for col_idx, header in enumerate(headers, start=1):
            value = row.get(header, "")
            if pd.isna(value):
                value = ""
            ws_grades.cell(row=excel_row, column=col_idx, value=value)

        if str(row.get("status", "")) != "GRADED":
            continue

        submission_file = str(row.get("submission_file", ""))

        # replace manual question cells by references to the manual sheet
        for qid in question_order:
            if qid not in header_to_col or qid not in manual_questions:
                continue

            col_idx = header_to_col[qid]
            cell = ws_grades.cell(row=excel_row, column=col_idx)
            ref = manual_ref.get((submission_file, qid))

            if ref:
                cell.value = f"={ref}"
                cell.fill = LINKED_MANUAL_FILL
            else:
                cell.value = ""

        # final score formula = sum of all question columns
        q_formula_terms = []
        for qid in question_order:
            if qid in header_to_col:
                q_formula_terms.append(
                    f"{get_column_letter(header_to_col[qid])}{excel_row}"
                )

        if "final_score" in header_to_col and q_formula_terms:
            final_cell = ws_grades.cell(
                row=excel_row,
                column=header_to_col["final_score"],
            )
            final_cell.value = "=SUM(" + ",".join(q_formula_terms) + ")"
            final_cell.fill = FORMULA_FILL

        # percentage formula
        if (
            "percentage" in header_to_col
            and "max_score" in header_to_col
            and "final_score" in header_to_col
        ):
            percentage_cell = ws_grades.cell(
                row=excel_row,
                column=header_to_col["percentage"],
            )

            final_ref = f"{get_column_letter(header_to_col['final_score'])}{excel_row}"
            max_ref = f"{get_column_letter(header_to_col['max_score'])}{excel_row}"

            percentage_cell.value = f'=IF({max_ref}>0,100*{final_ref}/{max_ref},"")'
            percentage_cell.fill = FORMULA_FILL

    ws_grades.freeze_panes = "A2"

    # Additional grey fill for any formula cell not already coloured
    for row in ws_grades.iter_rows(min_row=2):
        for cell in row:
            if isinstance(cell.value, str) and cell.value.startswith("="):
                if cell.fill == PatternFill():
                    cell.fill = FORMULA_FILL

    for row in ws_manual.iter_rows(min_row=2):
        for cell in row:
            if isinstance(cell.value, str) and cell.value.startswith("="):
                cell.fill = FORMULA_FILL

    # Number formatting
    if "percentage" in header_to_col:
        percentage_col = header_to_col["percentage"]
        for row_idx in range(2, ws_grades.max_row + 1):
            ws_grades.cell(row=row_idx, column=percentage_col).number_format = "0.000"

    # Protect both sheets
    protect_sheet(ws_grades)
    protect_sheet(ws_manual)

    autosize_columns(ws_grades)
    autosize_columns(ws_manual)

    # -------------------------------------------------------------------------
    # code_tests sheet (only when code questions exist)
    # -------------------------------------------------------------------------
    if not code_tests_df.empty:
        ws_code = wb.create_sheet("code_tests")
        write_dataframe_sheet(ws_code, code_tests_df)
        ws_code.freeze_panes = "A2"

        code_headers = [cell.value for cell in ws_code[1]]

        if "status" in code_headers:
            status_col = code_headers.index("status") + 1
            for row_idx in range(2, ws_code.max_row + 1):
                status_cell = ws_code.cell(
                    row=row_idx,
                    column=status_col,
                )
                if status_cell.value == "PASS":
                    status_cell.fill = PASS_FILL
                elif status_cell.value in {
                    "FAIL", "ERROR", "TIMEOUT",
                    "NOT_RUN", "NO_TESTS",
                }:
                    status_cell.fill = FAIL_FILL

        for row in ws_code.iter_rows():
            for cell in row:
                cell.protection = Protection(locked=True)

        protect_sheet(ws_code)
        autosize_columns(ws_code, max_width=50)

        if "test_code" in code_headers:
            col = code_headers.index("test_code") + 1
            ws_code.column_dimensions[get_column_letter(col)].width = 55

        if "diagnostic" in code_headers:
            col = code_headers.index("diagnostic") + 1
            ws_code.column_dimensions[get_column_letter(col)].width = 70

    # -------------------------------------------------------------------------
    # summary sheet
    # -------------------------------------------------------------------------
    build_summary_sheet(
        wb,
        grades_headers=headers,
        n_rows_grades=ws_grades.max_row,
        manual_rows_count=max(ws_manual.max_row - 1, 0),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    return output_path


# =============================================================================
# COMMAND LINE
# =============================================================================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate CSV files exported by widgets.py and create a single "
            "Excel workbook with automatic and manual grading."
        )
    )

    parser.add_argument(
        "submissions",
        type=Path,
        help="Directory containing student CSV submissions.",
    )

    parser.add_argument(
        "answer_key",
        type=Path,
        help="Instructor CSV with the correct answers.",
    )

    parser.add_argument(
        "--pattern",
        default="*.csv",
        help="Submission filename pattern. Default: *.csv",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("grading_workbook.xlsx"),
        help="Output Excel workbook. Default: grading_workbook.xlsx",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    submissions_dir = args.submissions.resolve()
    answer_key_path = args.answer_key.resolve()
    output_path = args.output.resolve()

    if not submissions_dir.is_dir():
        print(
            f"ERROR: submissions directory does not exist: {submissions_dir}",
            file=sys.stderr,
        )
        return 1

    if not answer_key_path.is_file():
        print(
            f"ERROR: answer key does not exist: {answer_key_path}",
            file=sys.stderr,
        )
        return 1

    try:
        grades_df, manual_df, code_tests_df, question_order = grade_directory(
            submissions_dir,
            answer_key_path,
            pattern=args.pattern,
        )

        build_workbook(
            grades_df,
            manual_df,
            code_tests_df,
            question_order,
            output_path,
        )

    except Exception as exc:
        print(
            f"ERROR: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1

    graded = int((grades_df.get("status") == "GRADED").sum()) if "status" in grades_df.columns else 0
    errors = int((grades_df.get("status") == "ERROR").sum()) if "status" in grades_df.columns else 0

    print()
    print("=" * 64)
    print("EVALUATION COMPLETE")
    print("=" * 64)
    print(f"Submissions      : {len(grades_df)}")
    print(f"Graded           : {graded}")
    print(f"Errors           : {errors}")
    print(f"Manual responses : {len(manual_df)}")
    print(f"Code test rows   : {len(code_tests_df)}")
    print(f"Workbook         : {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
