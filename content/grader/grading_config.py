"""
PRIVATE grading configuration.

Do NOT distribute this file to students.
"""

from grader import close_scalar, all_close, all_equal


ANSWER_KEY = {
    "q1": [3.14159, 6.28318, 1.57080],
    "q2": ["B"],
}


CHECKS = {

    "q1": lambda answer: all_close(
        answer,
        ANSWER_KEY["q1"],
        rtol=1e-4,
    ),

    "q2": lambda answer: all_equal(
        answer,
        ANSWER_KEY["q2"],
    ),

}


POINTS = {
    "q1": 2,
    "q2": 1,
}
