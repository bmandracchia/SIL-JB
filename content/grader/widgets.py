import ast
import html
import math
import operator as op

import numpy as np
import ipywidgets as widgets
from IPython.display import display, HTML, clear_output


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


def _safe_number(text):
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
            return _ALLOWED_UNARY[type(node.op)](
                _eval(node.operand),
            )

        raise ValueError("Invalid expression")

    try:
        return float(_eval(ast.parse(text, mode="eval")))
    except Exception:
        return None


def numeric_group(var_name, labels, env=None):
    """Create a numeric answer widget and store answers in ``env``."""

    if env is None:
        env = globals()

    answers = [None] * len(labels)
    env[var_name] = answers

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
            env[var_name] = list(answers)

            if change["new"].strip() and answers[index] is None:
                status.value = (
                    "<span style='color:#b00020'>"
                    "Hay una expresión numérica no válida."
                    "</span>"
                )
            else:
                status.value = (
                    "<span style='color:#2e7d32'>"
                    "Respuesta registrada."
                    "</span>"
                )

        return _handler

    for i, label in enumerate(labels):
        w = widgets.Text(
            value="",
            placeholder="Escribe un valor",
            description=label,
            style={"description_width": "initial"},
            layout=widgets.Layout(width="420px"),
        )

        w.observe(make_handler(i), names="value")
        controls.append(w)

    display(widgets.VBox(controls + [status]))

    return controls


def radio_group(var_name, items, options, env=None):
    """Create radio-button groups and store answers in ``env``."""

    if env is None:
        env = globals()

    answers = [""] * len(items)
    env[var_name] = answers

    boxes = []

    full_options = [
        ("— Selecciona —", "")
    ] + list(options)

    def make_handler(index):

        def _handler(change):
            answers[index] = change["new"]
            env[var_name] = list(answers)

        return _handler

    for i, item in enumerate(items):

        title = widgets.HTMLMath(
            value=f"<b>{item}</b>"
        )

        rb = widgets.RadioButtons(
            options=full_options,
            value="",
            layout=widgets.Layout(width="95%"),
        )

        rb.observe(
            make_handler(i),
            names="value",
        )

        boxes.append(
            widgets.VBox([title, rb])
        )

    display(widgets.VBox(boxes))

    return boxes


def checkbox_group(var_name, items, options, env=None):
    """Create checkbox groups and store answers in ``env``."""

    if env is None:
        env = globals()

    answers = [[] for _ in items]
    env[var_name] = answers

    groups = []

    def refresh(group_index, checkboxes):

        selected = [
            code
            for checkbox, (_, code)
            in zip(checkboxes, options)
            if checkbox.value
        ]

        answers[group_index] = selected
        env[var_name] = [list(x) for x in answers]

    for i, item in enumerate(items):

        title = widgets.HTMLMath(
            value=f"<b>{item}</b>"
        )

        checks = [
            widgets.Checkbox(
                value=False,
                description=label,
            )
            for label, _ in options
        ]

        for cb in checks:
            cb.observe(
                lambda change, i=i, checks=checks:
                    refresh(i, checks),
                names="value",
            )

        groups.append(
            widgets.VBox([title] + checks)
        )

    display(widgets.VBox(groups))

    return groups


def mixed_superposition_widget(var_name, env=None):
    """Create the superposition widget and store answers in ``env``."""

    if env is None:
        env = globals()

    answers = [None, None, None, ""]
    env[var_name] = answers

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

    for i, w in enumerate(texts):

        def handler(change, i=i):
            answers[i] = _safe_number(change["new"])
            env[var_name] = list(answers)

        w.observe(handler, names="value")

    def handler_yesno(change):
        answers[3] = change["new"]
        env[var_name] = list(answers)

    yesno.observe(
        handler_yesno,
        names="value",
    )

    display(
        widgets.VBox(
            texts + [yesno]
        )
    )

    return texts, yesno


def manual_text_widget(
    var_name,
    placeholder="Escribe aquí tu razonamiento...",
    env=None,
):
    """Create a text widget and store the answer in ``env``."""

    if env is None:
        env = globals()

    env[var_name] = ""

    text = widgets.Textarea(
        value="",
        placeholder=placeholder,
        layout=widgets.Layout(
            width="95%",
            height="180px",
        ),
    )

    save = widgets.Button(
        description="Guardar respuesta",
        button_style="primary",
    )

    out = widgets.Output()

    def _update(change):
        env[var_name] = change["new"]

    def _save(_):
        env[var_name] = text.value

        with out:
            clear_output()

            rendered = (
                html.escape(text.value)
                .replace("\n", "<br>")
            )

            display(
                HTML(
                    "<div style='border:1px solid #bbb;"
                    "padding:10px;border-radius:6px'>"
                    "<b>Respuesta guardada:</b><br>"
                    + rendered +
                    "</div>"
                )
            )

    text.observe(
        _update,
        names="value",
    )

    save.on_click(_save)

    display(
        widgets.VBox(
            [text, save, out]
        )
    )

    return text
