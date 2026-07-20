from IPython.display import HTML, display
import uuid


def create_answer_selector(num_options, solution, mode="alphabetic"):
    """
    Create an interactive multiple-choice exercise.

    Parameters
    ----------
    num_options : int
        Number of possible answers.

    solution : int
        Correct option number (starting at 1).

    mode : str
        "numeric"    -> 1,2,3,...
        "alphabetic" -> A,B,C,...

    Example usage:
    create_answer_selector(
        num_options=4,          
        solution=2,
        mode="alphabetic"
    )
    """

    uid = str(uuid.uuid4()).replace("-", "")

    select_id = f"select_{uid}"
    feedback_id = f"feedback_{uid}"
    button_id = f"button_{uid}"

    options_html = '<option value="">-- Elige una opción --</option>'

    for i in range(1, num_options + 1):

        if mode == "alphabetic":
            label = chr(64 + i)   # A,B,C,...
        else:
            label = str(i)

        options_html += f'<option value="{i}">{label}</option>'

    html = f"""
    <div style="
        border:1px solid #ccc;
        border-radius:10px;
        padding:15px;
        margin:10px 0;
        background:#f8f9fa;
    ">

        <select id="{select_id}" style="
            padding:6px;
            border-radius:6px;
        ">
            {options_html}
        </select>

        <button id="{button_id}" style="
            margin-left:10px;
            padding:6px 12px;
            border-radius:6px;
            cursor:pointer;
        ">
            Evaluar
        </button>

        <p id="{feedback_id}" style="
            margin-top:10px;
            font-weight:bold;
        "></p>

    </div>

    <script>
    document.getElementById("{button_id}").onclick = function() {{

        const selected =
            Number(document.getElementById("{select_id}").value);

        const feedback =
            document.getElementById("{feedback_id}");

        if (!selected) {{
            feedback.innerHTML = "Selecciona una opción.";
            feedback.style.color = "orange";
            return;
        }}

        if (selected === {solution}) {{
            feedback.innerHTML = "¡Correcto!";
            feedback.style.color = "green";
        }} else {{
            feedback.innerHTML = "¡Incorrecto! Inténtalo de nuevo.";
            feedback.style.color = "red";
        }}
    }};
    </script>
    """

    display(HTML(html))



def create_numeric_input_exercise(solution, tolerance=0):
    """
    Create an interactive exercise with a numeric input field.

    Parameters
    ----------
    solution : float
        Correct numerical answer.

    tolerance : float
        Accepted absolute error tolerance.

    Example usage:
    create_numeric_input_exercise(
        solution=14,
        tolerance=0
    )

    """

    uid = str(uuid.uuid4()).replace("-", "")

    input_id = f"input_{uid}"
    button_id = f"button_{uid}"
    feedback_id = f"feedback_{uid}"

    html = f"""
    <div style="
        border:1px solid #ccc;
        border-radius:10px;
        padding:15px;
        margin:10px 0;
        background:#f8f9fa;
    ">

        <p><strong>Ingresa tu respuesta:</strong></p>

        <input
            type="number"
            id="{input_id}"
            step="any"
            placeholder="Tu respuesta aquí"
            style="
                padding:6px;
                border-radius:6px;
                width:150px;
            "
        >

        <button id="{button_id}" style="
            margin-left:10px;
            padding:6px 12px;
            border-radius:6px;
            cursor:pointer;
        ">
            Evaluar
        </button>

        <p id="{feedback_id}" style="
            margin-top:10px;
            font-weight:bold;
        "></p>

    </div>

    <script>
    document.getElementById("{button_id}").onclick = function() {{

        const value =
            parseFloat(document.getElementById("{input_id}").value);

        const feedback =
            document.getElementById("{feedback_id}");

        if (isNaN(value)) {{
            feedback.innerHTML = "Por favor, ingresa un número.";
            feedback.style.color = "orange";
            return;
        }}

        if (Math.abs(value - ({solution})) <= {tolerance}) {{
            feedback.innerHTML = "¡Correcto!";
            feedback.style.color = "green";
        }} else {{
            feedback.innerHTML = "¡Incorrecto! Inténtalo de nuevo.";
            feedback.style.color = "red";
        }}
    }};
    </script>
    """

    display(HTML(html))




def create_true_false_exercise(statement, solution=True):
    """
    True/False exercise displayed with the statement on top 
    and options on the line below.
    
    Parameters
    ----------
    statement : str
        The statement to evaluate.  
    solution : bool
        True if the statement is correct, False otherwise.

    Example usage:
    create_true_false_exercise(
        statement="The Earth is flat.",
        solution=False
    )

    """

    uid = str(uuid.uuid4()).replace("-", "")

    radio_name = f"radio_{uid}"
    button_id = f"button_{uid}"
    feedback_id = f"feedback_{uid}"

    solution_str = "true" if solution else "false"

    html = f"""
    <div style="
        border:1px solid #ccc;
        border-radius:10px;
        padding:15px;
        margin:10px 0;
        background:#f8f9fa;
        color:black;
    ">

        <div style="margin-bottom: 15px;">
            <span><strong>{statement}</strong></span>
        </div>

        <div style="
            display:flex;
            align-items:center;
            gap:15px;
            flex-wrap:wrap;
        ">
            <label style="cursor:pointer;">
                <input type="radio" name="{radio_name}" value="true">
                Verdadero
            </label>

            <label style="cursor:pointer;">
                <input type="radio" name="{radio_name}" value="false">
                Falso
            </label>

            <button id="{button_id}" style="
                padding:4px 6px;
                border:1px solid #6c757d;
                border-radius:6px;
                background:#f8f9fa;
                color:#212529;
                cursor:pointer;
            ">
                Evaluar
            </button>

            <span id="{feedback_id}" style="
                font-weight:bold;
            "></span>
        </div>

    </div>

    <script>
    document.getElementById("{button_id}").onclick = function() {{

        const radios =
            document.getElementsByName("{radio_name}");

        let selected = null;

        for (const radio of radios) {{
            if (radio.checked) {{
                selected = radio.value;
            }}
        }}

        const feedback =
            document.getElementById("{feedback_id}");

        if (selected === null) {{
            feedback.innerHTML = "Selecciona una opción.";
            feedback.style.color = "orange";
            return;
        }}

        if (selected === "{solution_str}") {{
            feedback.innerHTML = "¡Correcto!";
            feedback.style.color = "green";
        }} else {{
            feedback.innerHTML = "¡Incorrecto! Inténtalo de nuevo.";
            feedback.style.color = "red";
        }}
    }};
    </script>
    """

    display(HTML(html))