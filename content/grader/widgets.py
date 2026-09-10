"""
Interactive answer widgets for Jupyter notebooks.

The notebook is the student-facing learning environment. Answers are stored in
an internal registry and can be exported to a CSV file for submission.

No answer key or grading logic is included in this module.
"""

from __future__ import annotations

import ast
import copy
import html
import json
import math
import operator as op
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import ipywidgets as widgets
import numpy as np
import pandas as pd
from IPython.display import FileLink, HTML, clear_output, display


# =============================================================================
# Internal registries
# =============================================================================

ANSWERS: dict[str, Any] = {}
QUESTION_TYPES: dict[str, str] = {}
ANSWERED: dict[str, bool] = {}

METADATA: dict[str, str] = {}
_REQUIRED_METADATA: set[str] = set()


def _copy(value: Any) -> Any:
    """Return a defensive copy when possible."""
    try:
        return copy.deepcopy(value)
    except Exception:
        return value


def _store_answer(
    question_id: str,
    value: Any,
    *,
    question_type: str,
    complete: bool,
) -> None:
    """Store one answer in the central registry."""
    ANSWERS[question_id] = _copy(value)
    QUESTION_TYPES[question_id] = question_type
    ANSWERED[question_id] = bool(complete)


def set_answer(
    question_id: str,
    value: Any,
    *,
    question_type: str = "custom",
    complete: bool = True,
) -> None:
    """
    Register an answer produced by a custom interactive activity.

    Useful for sliders, draggable points, fitted parameters, graphical
    exercises, or any activity not covered by the predefined widgets.

    Example
    -------
    set_answer(
        "q7",
        {"amplitude": 2.0, "frequency": np.pi},
        question_type="parameters",
    )
    """
    _store_answer(
        question_id,
        value,
        question_type=question_type,
        complete=complete,
    )


def get_answers() -> dict[str, Any]:
    """Return a copy of all currently registered answers."""
    return _copy(ANSWERS)


def get_metadata() -> dict[str, str]:
    """Return a copy of the current submission metadata."""
    return dict(METADATA)


def clear_answers() -> None:
    """Clear all registered answers and question metadata."""
    ANSWERS.clear()
    QUESTION_TYPES.clear()
    ANSWERED.clear()


def clear_metadata() -> None:
    """Clear all submission metadata."""
    METADATA.clear()
    _REQUIRED_METADATA.clear()


# =============================================================================
# Submission metadata widget
# =============================================================================


def metadata_widget(
    assignment_id: str,
    assignment_version: str = "1.0",
    *,
    fields=None,
    title: str = "Datos de entrega",
):
    """
    Display a metadata form to be placed near the beginning of the notebook.

    ``assignment_id`` and ``assignment_version`` are fixed by the notebook and
    shown to the student. Student-specific fields are entered interactively.

    Parameters
    ----------
    assignment_id:
        Stable identifier for the activity, e.g. ``"tema_1"``.

    assignment_version:
        Version of the activity, e.g. ``"1.0"``.

    fields:
        Iterable of ``(key, label)`` or ``(key, label, required)`` tuples.
        By default asks for student ID and full name.

    title:
        Heading displayed above the form.

    Returns
    -------
    dict
        Mapping from metadata keys to their Text widgets.

    Example
    -------
    metadata_widget(
        assignment_id="tema_1",
        assignment_version="1.0",
        fields=[
            ("student_id", "NIA", True),
            ("student_name", "Nombre y apellidos", True),
            ("group", "Grupo", False),
        ],
    )
    """
    if fields is None:
        fields = [
            ("student_id", "Identificador / NIA", True),
            ("student_name", "Nombre y apellidos", True),
        ]

    normalized_fields = []
    for field in fields:
        if len(field) == 2:
            key, label = field
            required = True
        elif len(field) == 3:
            key, label, required = field
        else:
            raise ValueError(
                "Cada campo debe ser (key, label) o (key, label, required)."
            )

        normalized_fields.append((str(key), str(label), bool(required)))

    METADATA["assignment_id"] = str(assignment_id)
    METADATA["assignment_version"] = str(assignment_version)

    # Rebuild the required set for this form.
    _REQUIRED_METADATA.clear()

    controls = {}
    rows = []

    header = widgets.HTML(
        value=(
            f"<h4 style='margin-bottom:6px'>{html.escape(title)}</h4>"
            f"<div><b>Actividad:</b> {html.escape(str(assignment_id))}<br>"
            f"<b>Versión:</b> {html.escape(str(assignment_version))}</div>"
        )
    )
    rows.append(header)

    status = widgets.HTML(
        value=(
            "<span style='color:#666'>"
            "Completa los datos antes de exportar las respuestas."
            "</span>"
        )
    )

    def update_status():
        missing = [
            key
            for key in _REQUIRED_METADATA
            if not str(METADATA.get(key, "")).strip()
        ]

        if missing:
            status.value = (
                "<span style='color:#666'>"
                "Faltan datos obligatorios."
                "</span>"
            )
        else:
            status.value = (
                "<span style='color:#2e7d32'>"
                "Datos de entrega completos."
                "</span>"
            )

    for key, label, required in normalized_fields:
        METADATA.setdefault(key, "")

        if required:
            _REQUIRED_METADATA.add(key)

        suffix = " *" if required else ""
        control = widgets.Text(
            value=str(METADATA.get(key, "")),
            description=label + suffix,
            placeholder="Escribe aquí",
            style={"description_width": "initial"},
            layout=widgets.Layout(width="520px"),
        )

        def handler(change, key=key):
            METADATA[key] = change["new"].strip()
            update_status()

        control.observe(handler, names="value")
        controls[key] = control
        rows.append(control)

    rows.append(status)
    update_status()

    display(widgets.VBox(rows))
    return controls


# =============================================================================
# Safe numeric input
# =============================================================================

_ALLOWED_BINOPS = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.Pow: op.pow,
}

_ALLOWED_UNARY = {
    ast.UAdd: op.pos,
    ast.USub: op.neg,
}

_ALLOWED_NAMES = {
    "pi": math.pi,
    "e": math.e,
}


def _safe_number(text: Any) -> float | None:
    """Convert a simple mathematical expression to a number."""
    if text is None:
        return None

    text = (
        str(text)
        .strip()
        .replace(",", ".")
        .replace("π", "pi")
        .replace("^", "**")
    )

    if not text:
        return None

    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)

        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)

        if isinstance(node, ast.Name) and node.id in _ALLOWED_NAMES:
            return float(_ALLOWED_NAMES[node.id])

        if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
            return _ALLOWED_BINOPS[type(node.op)](
                _eval(node.left),
                _eval(node.right),
            )

        if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARY:
            return _ALLOWED_UNARY[type(node.op)](_eval(node.operand))

        raise ValueError("Invalid expression")

    try:
        return float(_eval(ast.parse(text, mode="eval")))
    except Exception:
        return None


# =============================================================================
# Standard question widgets
# =============================================================================


def numeric_group(var_name, labels):
    """Create numeric answer boxes and register their values."""
    answers = [None] * len(labels)

    _store_answer(
        var_name,
        answers,
        question_type="numeric",
        complete=False,
    )

    controls = []
    status = widgets.HTML(
        value=(
            "<span style='color:#666'>"
            "Introduce las respuestas. Se registran automáticamente."
            "</span>"
        )
    )

    def make_handler(index):
        def _handler(change):
            answers[index] = _safe_number(change["new"])
            complete = all(value is not None for value in answers)

            _store_answer(
                var_name,
                answers,
                question_type="numeric",
                complete=complete,
            )

            if change["new"].strip() and answers[index] is None:
                status.value = (
                    "<span style='color:#b00020'>"
                    "Hay una expresión numérica no válida."
                    "</span>"
                )
            elif complete:
                status.value = (
                    "<span style='color:#2e7d32'>"
                    "Respuesta completa y registrada."
                    "</span>"
                )
            else:
                status.value = (
                    "<span style='color:#666'>"
                    "Respuesta registrada. Quedan apartados por completar."
                    "</span>"
                )

        return _handler

    for i, label in enumerate(labels):
        control = widgets.Text(
            value="",
            placeholder="Escribe un valor",
            description=label,
            style={"description_width": "initial"},
            layout=widgets.Layout(width="420px"),
        )
        control.observe(make_handler(i), names="value")
        controls.append(control)

    display(widgets.VBox(controls + [status]))
    return controls


def radio_group(var_name, items, options):
    """Create radio-button groups and register their values."""
    answers = [""] * len(items)

    _store_answer(
        var_name,
        answers,
        question_type="single_choice",
        complete=False,
    )

    boxes = []
    full_options = [("— Selecciona —", "")] + list(options)

    def make_handler(index):
        def _handler(change):
            answers[index] = change["new"]
            complete = all(value != "" for value in answers)

            _store_answer(
                var_name,
                answers,
                question_type="single_choice",
                complete=complete,
            )

        return _handler

    for i, item in enumerate(items):
        title = widgets.HTMLMath(value=f"<b>{item}</b>")
        control = widgets.RadioButtons(
            options=full_options,
            value="",
            layout=widgets.Layout(width="95%"),
        )
        control.observe(make_handler(i), names="value")
        boxes.append(widgets.VBox([title, control]))

    display(widgets.VBox(boxes))
    return boxes


def checkbox_group(
    var_name,
    items,
    options,
    *,
    require_selection=True,
):
    """
    Create checkbox groups and register their values.

    By default, every sub-question must contain at least one selected option to
    be marked complete. Set ``require_selection=False`` when selecting no option
    is itself a valid answer.
    """
    answers = [[] for _ in items]

    _store_answer(
        var_name,
        answers,
        question_type="multiple_choice",
        complete=(not require_selection),
    )

    groups = []

    def refresh(group_index, checkboxes):
        selected = [
            code
            for checkbox, (_, code) in zip(checkboxes, options)
            if checkbox.value
        ]

        answers[group_index] = selected

        if require_selection:
            complete = all(len(selection) > 0 for selection in answers)
        else:
            complete = True

        _store_answer(
            var_name,
            answers,
            question_type="multiple_choice",
            complete=complete,
        )

    for i, item in enumerate(items):
        title = widgets.HTMLMath(value=f"<b>{item}</b>")

        checks = [
            widgets.Checkbox(value=False, description=label)
            for label, _ in options
        ]

        for checkbox in checks:
            checkbox.observe(
                lambda change, i=i, checks=checks: refresh(i, checks),
                names="value",
            )

        groups.append(widgets.VBox([title] + checks))

    display(widgets.VBox(groups))
    return groups


def mixed_superposition_widget(var_name):
    """Create the mixed numeric/yes-no superposition widget."""
    answers = [None, None, None, ""]

    _store_answer(
        var_name,
        answers,
        question_type="mixed",
        complete=False,
    )

    texts = [
        widgets.Text(
            description="a)",
            placeholder="valor",
            style={"description_width": "initial"},
        ),
        widgets.Text(
            description="b)",
            placeholder="valor",
            style={"description_width": "initial"},
        ),
        widgets.Text(
            description="c)",
            placeholder="valor",
            style={"description_width": "initial"},
        ),
    ]

    yesno = widgets.RadioButtons(
        options=[
            ("— Selecciona —", ""),
            ("Sí", "SI"),
            ("No", "NO"),
        ],
        value="",
        description="d)",
        style={"description_width": "initial"},
    )

    def refresh():
        complete = (
            all(value is not None for value in answers[:3])
            and answers[3] != ""
        )

        _store_answer(
            var_name,
            answers,
            question_type="mixed",
            complete=complete,
        )

    for i, control in enumerate(texts):
        def handler(change, i=i):
            answers[i] = _safe_number(change["new"])
            refresh()

        control.observe(handler, names="value")

    def handler_yesno(change):
        answers[3] = change["new"]
        refresh()

    yesno.observe(handler_yesno, names="value")

    display(widgets.VBox(texts + [yesno]))
    return texts, yesno


def manual_text_widget(
    var_name,
    placeholder="Escribe aquí tu razonamiento...",
):
    """Create a free-text answer widget and register its content."""
    _store_answer(
        var_name,
        "",
        question_type="manual_text",
        complete=False,
    )

    text = widgets.Textarea(
        value="",
        placeholder=placeholder,
        layout=widgets.Layout(width="95%", height="180px"),
    )

    save = widgets.Button(
        description="Guardar respuesta",
        button_style="primary",
    )

    out = widgets.Output()

    def _update(change):
        value = change["new"]
        _store_answer(
            var_name,
            value,
            question_type="manual_text",
            complete=bool(value.strip()),
        )

    def _save(_):
        value = text.value
        _store_answer(
            var_name,
            value,
            question_type="manual_text",
            complete=bool(value.strip()),
        )

        with out:
            clear_output()
            rendered = html.escape(value).replace("\n", "<br>")
            display(
                HTML(
                    "<div style='border:1px solid #bbb;"
                    "padding:10px;border-radius:6px'>"
                    "<b>Respuesta guardada:</b><br>"
                    + rendered
                    + "</div>"
                )
            )

    text.observe(_update, names="value")
    save.on_click(_save)

    display(widgets.VBox([text, save, out]))
    return text


def code_text_widget(
    var_name,
    placeholder="Escribe aquí el código...",
    *,
    height="220px",
):
    """
    Create a text area for code and save the code itself as the answer.

    The code is not executed by this module. A private grading script can later
    inspect or execute it under controlled conditions.
    """
    _store_answer(
        var_name,
        "",
        question_type="code",
        complete=False,
    )

    text = widgets.Textarea(
        value="",
        placeholder=placeholder,
        layout=widgets.Layout(width="95%", height=height),
    )

    status = widgets.HTML(
        value=(
            "<span style='color:#666'>"
            "El código se registra automáticamente."
            "</span>"
        )
    )

    def _update(change):
        value = change["new"]
        _store_answer(
            var_name,
            value,
            question_type="code",
            complete=bool(value.strip()),
        )

        if value.strip():
            status.value = (
                "<span style='color:#2e7d32'>Código registrado.</span>"
            )
        else:
            status.value = (
                "<span style='color:#666'>"
                "El código se registra automáticamente."
                "</span>"
            )

    text.observe(_update, names="value")

    display(widgets.VBox([text, status]))
    return text


# =============================================================================
# Status and export
# =============================================================================


def _jsonable(value: Any) -> Any:
    """Convert common scientific Python objects to JSON-compatible values."""
    if value is None:
        return None

    if isinstance(value, np.generic):
        return _jsonable(value.item())

    if isinstance(value, np.ndarray):
        return [_jsonable(item) for item in value.tolist()]

    if isinstance(value, complex):
        return {
            "real": float(value.real),
            "imag": float(value.imag),
        }

    if isinstance(value, dict):
        return {
            str(key): _jsonable(val)
            for key, val in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]

    if isinstance(value, (str, int, float, bool)):
        return value

    # Fallback for objects such as SymPy expressions.
    return str(value)


def answer_status(display_result=True) -> pd.DataFrame:
    """Return a table showing which questions are currently complete."""
    rows = [
        {
            "question_id": question_id,
            "question_type": QUESTION_TYPES.get(question_id, "unknown"),
            "answered": bool(ANSWERED.get(question_id, False)),
        }
        for question_id in ANSWERS
    ]

    df = pd.DataFrame(
        rows,
        columns=["question_id", "question_type", "answered"],
    )

    if display_result:
        total = len(df)
        completed = int(df["answered"].sum()) if total else 0

        display(HTML(f"<b>Respuestas completas:</b> {completed}/{total}"))
        if total:
            display(df)

    return df


def _missing_metadata() -> list[str]:
    return sorted(
        key
        for key in _REQUIRED_METADATA
        if not str(METADATA.get(key, "")).strip()
    )


def answers_dataframe() -> pd.DataFrame:
    """
    Build the submission DataFrame from the current metadata and answers.

    One row is produced per registered question. The ``answer`` column contains
    JSON, so scalars, lists, matrices and parameter dictionaries can share one
    stable CSV format.
    """
    exported_at = datetime.now(timezone.utc).isoformat()
    rows = []

    for question_id, answer in ANSWERS.items():
        row = {
            **METADATA,
            "question_id": str(question_id),
            "question_type": QUESTION_TYPES.get(question_id, "unknown"),
            "answered": bool(ANSWERED.get(question_id, False)),
            "answer": json.dumps(
                _jsonable(answer),
                ensure_ascii=False,
            ),
            "exported_at_utc": exported_at,
        }
        rows.append(row)

    metadata_columns = list(METADATA.keys())
    standard_columns = [
        "question_id",
        "question_type",
        "answered",
        "answer",
        "exported_at_utc",
    ]

    return pd.DataFrame(
        rows,
        columns=metadata_columns + standard_columns,
    )


def _safe_filename_part(value: Any, fallback: str) -> str:
    text = str(value).strip()
    if not text:
        return fallback

    text = re.sub(r"[^\w.-]+", "_", text, flags=re.UNICODE)
    return text.strip("._") or fallback


def export_answers(
    filename=None,
    *,
    require_complete=False,
    require_metadata=True,
    show_summary=True,
    download=False,
):
    """
    Export all registered answers to a CSV file.

    Metadata are taken from ``metadata_widget``; they are not passed again to
    this function.

    Parameters
    ----------
    filename:
        Output filename. If omitted, it is generated from ``assignment_id`` and
        ``student_id`` when available.

    require_complete:
        If True, export is blocked while any registered question is incomplete.

    require_metadata:
        If True, export is blocked while required metadata fields are empty.

    show_summary:
        Display a confirmation and a clickable file link.

    download:
        If True and running in Google Colab, trigger the browser download.

    Returns
    -------
    pathlib.Path
        Path to the generated CSV file.
    """
    if not ANSWERS:
        raise ValueError(
            "No hay respuestas registradas. "
            "Ejecuta primero las celdas de las preguntas."
        )

    if require_metadata:
        missing_metadata = _missing_metadata()
        if missing_metadata:
            raise ValueError(
                "No se puede exportar: faltan metadatos obligatorios: "
                + ", ".join(missing_metadata)
            )

    incomplete = [
        question_id
        for question_id in ANSWERS
        if not ANSWERED.get(question_id, False)
    ]

    if require_complete and incomplete:
        raise ValueError(
            "No se puede exportar: faltan respuestas en "
            + ", ".join(incomplete)
        )

    df = answers_dataframe()

    if filename is None:
        assignment_part = _safe_filename_part(
            METADATA.get("assignment_id", ""),
            "actividad",
        )
        student_part = _safe_filename_part(
            METADATA.get("student_id", ""),
            "estudiante",
        )
        filename = f"{assignment_part}_{student_part}_respuestas.csv"

    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)

    df.to_csv(path, index=False, encoding="utf-8-sig")

    if show_summary:
        completed = sum(
            bool(ANSWERED.get(question_id, False))
            for question_id in ANSWERS
        )
        total = len(ANSWERS)

        warning = ""
        if incomplete:
            warning = (
                "<br><span style='color:#b26a00'>"
                "Aviso: quedan preguntas marcadas como incompletas: "
                + ", ".join(html.escape(item) for item in incomplete)
                + "</span>"
            )

        display(
            HTML(
                "<div style='border:1px solid #bbb;"
                "padding:10px;border-radius:6px'>"
                "<b>Respuestas exportadas correctamente.</b><br>"
                f"Preguntas completas: {completed}/{total}<br>"
                f"Archivo: {html.escape(str(path))}"
                f"{warning}"
                "</div>"
            )
        )

        try:
            display(FileLink(str(path)))
        except Exception:
            pass

    if download:
        try:
            from google.colab import files
            files.download(str(path))
        except ImportError:
            pass

    return path
