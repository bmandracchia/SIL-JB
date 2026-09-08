"""
Generic notebook grader.

Students can receive this file without receiving the answers.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np


# ============================================================================
# Optional private configuration
# ============================================================================

try:
    from grading_config import ANSWER_KEY, CHECKS, POINTS

except ImportError:
    # No private grading configuration available.
    #
    # This is the version students receive.
    ANSWER_KEY = {}
    CHECKS = {}
    POINTS = {}


# ============================================================================
# Checking helpers
# ============================================================================

def equal(answer: Any, expected: Any) -> bool:
    """Exact equality."""
    return answer == expected


def all_equal(answer: Any, expected: Any) -> bool:
    """Exact element-by-element comparison."""
    try:
        return bool(np.array_equal(answer, expected))
    except (TypeError, ValueError):
        return False


def close_scalar(
    answer: Any,
    expected: Any,
    *,
    rtol: float = 1e-5,
    atol: float = 1e-8,
) -> bool:
    """Compare scalar numerical values."""
    try:
        return math.isclose(
            float(answer),
            float(expected),
            rel_tol=rtol,
            abs_tol=atol,
        )
    except (TypeError, ValueError):
        return False


def all_close(
    answer: Any,
    expected: Any,
    *,
    rtol: float = 1e-5,
    atol: float = 1e-8,
) -> bool:
    """Numerical element-by-element comparison."""
    try:
        return bool(
            np.allclose(
                answer,
                expected,
                rtol=rtol,
                atol=atol,
                equal_nan=True,
            )
        )
    except (TypeError, ValueError):
        return False


def contains(answer: Any, expected: Any) -> bool:
    """Check whether expected is contained in answer."""
    try:
        return expected in answer
    except (TypeError, ValueError):
        return False


# ============================================================================
# Grading
# ============================================================================

def grade(env: dict[str, Any]) -> dict[str, Any]:
    """
    Grade the executed notebook.

    Parameters
    ----------
    env:
        Notebook namespace, normally supplied as:

            grade(globals())

    Returns
    -------
    dict
        JSON-serializable grading result.
    """

    results = {}

    total_score = 0
    max_score = 0

    # ------------------------------------------------------------------------
    # No private configuration
    # ------------------------------------------------------------------------

    if not CHECKS:
        return {
            "score": 0,
            "max_score": 0,
            "percentage": 0.0,
        }

    # ------------------------------------------------------------------------
    # Grade each question
    # ------------------------------------------------------------------------

    for question, check in CHECKS.items():

        points = POINTS.get(question, 1)

        max_score += points

        # ------------------------------------------------------------
        # Missing answer
        # ------------------------------------------------------------

        if question not in env:
            results[question] = 0
            continue

        answer = env[question]

        # ------------------------------------------------------------
        # Run check
        # ------------------------------------------------------------

        try:
            passed = bool(check(answer))
        except Exception:
            passed = False

        # ------------------------------------------------------------
        # Award points
        # ------------------------------------------------------------

        awarded = points if passed else 0

        results[question] = awarded
        total_score += awarded

    # ------------------------------------------------------------------------
    # Final result
    # ------------------------------------------------------------------------

    percentage = (
        100.0 * total_score / max_score
        if max_score
        else 0.0
    )

    return {
        "score": total_score,
        "max_score": max_score,
        "percentage": percentage,
        **results,
    }
