# Entorno de actividades y evaluación en Jupyter

Este entorno permite crear actividades interactivas en notebooks de Jupyter sin que el alumnado tenga que trabajar directamente con un sistema de corrección. La arquitectura se divide en dos componentes:

- `widgets.py`: módulo que se distribuye con los notebooks y se encarga de mostrar widgets, registrar las respuestas y exportarlas a un CSV.
- `evaluate_submissions.py`: script privado del profesorado que corrige los CSV entregados y genera un único libro Excel con resultados automáticos, revisión manual, tests de código y estadísticas.

El flujo general es:

```text
Notebook del estudiante
        │
        │  widgets.py
        ▼
CSV de respuestas
        │
        │  entrega
        ▼
evaluate_submissions.py + answer_key.csv
        │
        ▼
grading_workbook.xlsx
```

---

# Índice

- [Entorno de actividades y evaluación en Jupyter](#entorno-de-actividades-y-evaluación-en-jupyter)
- [Índice](#índice)
- [1. Archivos del entorno](#1-archivos-del-entorno)
- [2. Instalación](#2-instalación)
  - [Opción recomendada: Conda / Miniconda](#opción-recomendada-conda--miniconda)
  - [Registrar el kernel en Jupyter](#registrar-el-kernel-en-jupyter)
- [3. Uso de `widgets.py`](#3-uso-de-widgetspy)
  - [3.1. Metadatos de la entrega](#31-metadatos-de-la-entrega)
  - [3.2. Preguntas numéricas](#32-preguntas-numéricas)
  - [3.3. Selección simple](#33-selección-simple)
  - [3.4. Selección múltiple](#34-selección-múltiple)
  - [3.5. Respuesta abierta](#35-respuesta-abierta)
  - [3.6. Respuesta de código](#36-respuesta-de-código)
  - [3.7. Actividades gráficas o widgets personalizados](#37-actividades-gráficas-o-widgets-personalizados)
  - [3.8. Ejemplo completo: ajustar la amplitud de un seno](#38-ejemplo-completo-ajustar-la-amplitud-de-un-seno)
- [4. Comprobar y exportar las respuestas](#4-comprobar-y-exportar-las-respuestas)
- [5. Crear la plantilla privada de respuestas](#5-crear-la-plantilla-privada-de-respuestas)
- [6. Configuración de `evaluate_submissions.py`](#6-configuración-de-evaluate_submissionspy)
  - [6.1. Tolerancia numérica](#61-tolerancia-numérica)
  - [6.2. Crédito parcial](#62-crédito-parcial)
- [7. Corrección de preguntas de código](#7-corrección-de-preguntas-de-código)
  - [7.1. Todos los tests obligatorios](#71-todos-los-tests-obligatorios)
  - [7.2. Nota proporcional](#72-nota-proporcional)
  - [7.3. Timeout](#73-timeout)
    - [Advertencia sobre seguridad](#advertencia-sobre-seguridad)
- [8. Ejecutar la evaluación](#8-ejecutar-la-evaluación)
- [9. Libro Excel generado](#9-libro-excel-generado)
  - [`grades`](#grades)
  - [`manual_grading`](#manual_grading)
  - [`code_tests`](#code_tests)
  - [`summary`](#summary)
- [10. Flujo completo recomendado](#10-flujo-completo-recomendado)
  - [Preparación por el profesor](#preparación-por-el-profesor)
  - [Trabajo del estudiante](#trabajo-del-estudiante)
  - [Corrección](#corrección)
- [11. Google Colab](#11-google-colab)
- [12. Dependencias principales](#12-dependencias-principales)
- [13. Compatibilidad](#13-compatibilidad)
- [14. Resumen de la arquitectura](#14-resumen-de-la-arquitectura)

---

# 1. Archivos del entorno

Una organización sencilla del proyecto es:

```text
proyecto/
│
├── widgets.py
├── evaluate_submissions.py
├── autograder-env.yml
├── README.md
│
├── notebooks/
│   ├── tema_1.ipynb
│   ├── tema_2.ipynb
│   └── ...
│
├── answer_keys/                 # PRIVADO
│   ├── answer_key_tema_1.csv
│   └── ...
│
├── submissions/                 # PRIVADO
│   ├── tema_1_123456_respuestas.csv
│   ├── tema_1_123457_respuestas.csv
│   └── ...
│
└── results/                     # PRIVADO
    └── grading_workbook.xlsx
```

`widgets.py` puede distribuirse al alumnado. `evaluate_submissions.py`, los `answer_key` y los resultados de evaluación deben mantenerse privados.

---

# 2. Instalación

## Opción recomendada: Conda / Miniconda

Desde la carpeta que contiene `autograder-env.yml`:

```bash
conda env create -f autograder-env.yml
```

Después:

```bash
conda activate autograder
```

Para abrir JupyterLab:

```bash
jupyter lab
```

Si se modifica posteriormente `autograder-env.yml`, el entorno puede actualizarse con:

```bash
conda env update -f autograder-env.yml --prune
```

También puede utilizarse `mamba`:

```bash
mamba env create -f autograder-env.yml
```

## Registrar el kernel en Jupyter

Normalmente no es imprescindible si Jupyter se ejecuta desde el entorno activado, pero puede resultar útil:

```bash
python -m ipykernel install --user \
    --name autograder \
    --display-name "Python (Autograder)"
```

---

# 3. Uso de `widgets.py`

El notebook del estudiante importa únicamente las funciones necesarias.

Por ejemplo:

```python
from widgets import (
    metadata_widget,
    numeric_group,
    radio_group,
    checkbox_group,
    manual_text_widget,
    code_text_widget,
    set_answer,
    answer_status,
    export_answers,
)
```

Todos los widgets escriben sus respuestas en un registro interno de `widgets.py`. No es necesario utilizar `globals()` ni mantener variables de respuesta manualmente.

---

## 3.1. Metadatos de la entrega

Es recomendable colocar un widget de metadatos al principio del notebook:

```python
metadata_widget(
    assignment_id="tema_1",
    assignment_version="1.0",
    fields=[
        ("student_id", "NIA", True),
        ("student_name", "Nombre y apellidos", True),
        ("group", "Grupo", False),
    ],
)
```

Los elementos de `fields` tienen la forma:

```python
("clave", "Etiqueta visible", obligatorio)
```

`assignment_id` identifica la actividad y `assignment_version` permite comprobar durante la evaluación que el CSV pertenece a la versión correcta del notebook.

---

## 3.2. Preguntas numéricas

```python
numeric_group(
    "q1",
    ["a) E1 =", "b) E2 =", "c) E3 ="],
)
```

El alumnado puede introducir números o expresiones numéricas sencillas, por ejemplo:

```text
3.5
1/2
2*pi
pi/4
2^3
```

---

## 3.3. Selección simple

```python
radio_group(
    "q2",
    ["Selecciona la propiedad correcta:"],
    [
        ("Lineal", "LINEAR"),
        ("No lineal", "NONLINEAR"),
    ],
)
```

El primer elemento de cada opción es el texto visible y el segundo es el valor que se guarda.

---

## 3.4. Selección múltiple

```python
checkbox_group(
    "q3",
    ["Selecciona todas las propiedades que se cumplen:"],
    [
        ("Lineal", "LINEAR"),
        ("Causal", "CAUSAL"),
        ("Estable", "STABLE"),
        ("Invariante en el tiempo", "TI"),
    ],
)
```

Por defecto, cada grupo debe tener al menos una opción seleccionada para considerarse completo.

Si una respuesta vacía es válida:

```python
checkbox_group(
    "q3",
    items,
    options,
    require_selection=False,
)
```

---

## 3.5. Respuesta abierta

```python
manual_text_widget(
    "q4",
    placeholder="Justifica brevemente tu respuesta...",
)
```

Las preguntas de tipo `manual_text` se envían automáticamente a la hoja de corrección manual del fichero Excel.

---

## 3.6. Respuesta de código

```python
code_text_widget(
    "q5",
    placeholder="Escribe aquí tu función...",
)
```

El código **no se ejecuta en el notebook mediante `widgets.py`**. Se guarda como texto en el CSV y, si se configuran tests privados, se evalúa posteriormente con `evaluate_submissions.py`.

---

## 3.7. Actividades gráficas o widgets personalizados

Para una actividad construida con sliders, botones, gráficos o cualquier otro widget, puede registrarse directamente el estado que constituya la respuesta:

```python
set_answer(
    "q6",
    {
        "amplitude": A,
        "frequency": omega,
        "phase": phi,
    },
    question_type="parameters",
)
```

Normalmente `set_answer()` se llama desde la función que actualiza el gráfico o desde un botón de confirmación.

También puede indicarse que la respuesta todavía no está completa:

```python
set_answer(
    "q6",
    current_values,
    question_type="parameters",
    complete=False,
)
```

---

## 3.8. Ejemplo completo: ajustar la amplitud de un seno

El siguiente ejemplo muestra una señal de referencia y permite al estudiante modificar la amplitud de otra senoide mediante un slider. La respuesta se registra solo cuando el estudiante pulsa `Save answer`.

```python
import numpy as np
import matplotlib.pyplot as plt
import ipywidgets as widgets

from IPython.display import display
from widgets import set_answer
```

```python
# Time axis
t = np.linspace(0, 2, 500)

# Reference signal
A_ref = 2.3
x_ref = A_ref * np.sin(2*np.pi*t)

# Student control
amplitude = widgets.FloatSlider(
    value=1.0,
    min=0.0,
    max=4.0,
    step=0.1,
    description="Amplitude:",
    continuous_update=True,
)

save_button = widgets.Button(
    description="Save answer",
    button_style="primary",
)

message = widgets.HTML()
output = widgets.Output()
```

```python
def update_plot(change=None):
    A = amplitude.value
    x = A * np.sin(2*np.pi*t)

    with output:
        output.clear_output(wait=True)

        plt.figure(figsize=(8, 4))
        plt.plot(
            t,
            x_ref,
            "--",
            label="Reference signal",
        )
        plt.plot(
            t,
            x,
            label="Your signal",
        )

        plt.xlabel("Time $t$")
        plt.ylabel("$x(t)$")
        plt.grid(True)
        plt.legend()
        plt.show()
```

```python
def save_answer(button):
    set_answer(
        "q6",
        {
            "amplitude": amplitude.value
        },
        question_type="parameters",
        complete=True,
    )

    message.value = (
        "<span style='color:green'>"
        f"Answer saved: A = {amplitude.value:.2f}"
        "</span>"
    )
```

```python
amplitude.observe(update_plot, names="value")
save_button.on_click(save_answer)

update_plot()

display(
    widgets.VBox([
        amplitude,
        output,
        save_button,
        message,
    ])
)
```

Cuando el estudiante pulsa `Save answer`, se almacena una respuesta equivalente a:

```python
{
    "q6": {
        "amplitude": 2.3
    }
}
```

y `export_answers()` la serializa en el CSV como:

```json
{"amplitude": 2.3}
```

El profesor puede corregir esta actividad mediante tolerancia numérica:

```python
QUESTION_CONFIG = {
    "q6": {
        "points": 1,
        "atol": 0.1,
    }
}
```

El mismo patrón puede ampliarse fácilmente a varios parámetros:

```python
set_answer(
    "q7",
    {
        "amplitude": amplitude.value,
        "frequency": frequency.value,
        "phase": phase.value,
    },
    question_type="parameters",
)
```

por ejemplo para reconstruir visualmente una señal

$$
x(t)=A\sin(\omega t+\phi).
$$

---

# 4. Comprobar y exportar las respuestas

Antes de exportar puede mostrarse el estado de las preguntas:

```python
answer_status()
```

Al final del notebook:

```python
export_answers(
    require_complete=True,
    download=True,
)
```

`require_complete=True` impide exportar si queda alguna pregunta incompleta.

`download=True` inicia la descarga automáticamente cuando el notebook se ejecuta en Google Colab.

Si no se indica un nombre, se genera automáticamente uno similar a:

```text
tema_1_123456_respuestas.csv
```

También puede especificarse:

```python
export_answers(
    "mis_respuestas.csv",
    require_complete=True,
)
```

---

# 5. Crear la plantilla privada de respuestas

El profesorado utiliza **el mismo notebook** que el alumnado.

Se rellenan correctamente todas las preguntas y al final se ejecuta:

```python
export_answers(
    "answer_key_tema_1.csv",
    require_complete=True,
)
```

Este archivo se mantiene privado y se utiliza como plantilla de corrección.

---

# 6. Configuración de `evaluate_submissions.py`

La configuración se realiza en `QUESTION_CONFIG`, al principio de `evaluate_submissions.py`.

Si una pregunta no aparece en `QUESTION_CONFIG`:

- vale `1` punto;
- las respuestas convencionales se corrigen automáticamente contra el `answer_key`;
- las preguntas `manual_text` se envían a corrección manual;
- las preguntas `code` se tratan como preguntas de código.

Ejemplo:

```python
QUESTION_CONFIG = {
    "q1": {
        "points": 2,
        "rtol": 1e-4,
        "atol": 1e-8,
    },

    "q3": {
        "points": 3,
        "partial_credit": True,
    },

    "q4": {
        "points": 2,
        "mode": "manual",
    },
}
```

## 6.1. Tolerancia numérica

Las respuestas numéricas se comparan utilizando `numpy.isclose`.

Los valores por defecto son:

```python
DEFAULT_RTOL = 1e-5
DEFAULT_ATOL = 1e-8
```

Pueden modificarse por pregunta.

## 6.2. Crédito parcial

Para listas, diccionarios o preguntas con varios apartados:

```python
"q3": {
    "points": 3,
    "partial_credit": True,
}
```

La puntuación se calcula a partir de los componentes de nivel superior correctos.

---

# 7. Corrección de preguntas de código

Los tests se escriben de forma privada dentro de `QUESTION_CONFIG`.

```python
"q12": {
    "points": 3,
    "mode": "code",
    "timeout": 3,
    "test_scoring": "all",

    "tests": [
        {
            "name": "DC gain",
            "code": "assert np.isclose(H(0), 1.0)",
        },
        {
            "name": "Value at t=1",
            "code": "assert np.isclose(H(1), 0.5)",
        },
        {
            "name": "Value at t=2",
            "code": "assert np.isclose(H(2), 1/3)",
        },
    ],
}
```

También pueden usarse tests sin nombre:

```python
"tests": [
    "assert np.isclose(H(0), 1.0)",
    "assert np.isclose(H(1), 0.5)",
]
```

## 7.1. Todos los tests obligatorios

```python
"test_scoring": "all"
```

Si la pregunta vale 3 puntos:

| Tests superados | Nota |
|---|---:|
| 3/3 | 3 |
| 2/3 | 0 |
| 1/3 | 0 |
| 0/3 | 0 |

## 7.2. Nota proporcional

```python
"test_scoring": "proportional"
```

| Tests superados | Nota |
|---|---:|
| 3/3 | 3 |
| 2/3 | 2 |
| 1/3 | 1 |
| 0/3 | 0 |

Cada test tiene actualmente el mismo peso.

## 7.3. Timeout

```python
"timeout": 3
```

Los estados posibles son:

```text
PASS
FAIL
ERROR
TIMEOUT
NOT_RUN
NO_TESTS
```

### Advertencia sobre seguridad

La ejecución en un subproceso y el timeout evitan que errores ordinarios o bucles infinitos bloqueen el corrector, pero **no constituyen un sandbox de seguridad**.

---

# 8. Ejecutar la evaluación

Ejemplo:

```text
answer_keys/answer_key_tema_1.csv
submissions/
    tema_1_123456_respuestas.csv
    tema_1_123457_respuestas.csv
```

Ejecutar:

```bash
python evaluate_submissions.py \
    submissions \
    answer_keys/answer_key_tema_1.csv
```

En Windows PowerShell:

```powershell
python evaluate_submissions.py submissions answer_keys/answer_key_tema_1.csv
```

Por defecto se genera:

```text
grading_workbook.xlsx
```

Para elegir otra ruta:

```bash
python evaluate_submissions.py \
    submissions \
    answer_keys/answer_key_tema_1.csv \
    --output results/tema_1_grades.xlsx
```

---

# 9. Libro Excel generado

## `grades`

Una fila por estudiante, con metadatos, puntuación por pregunta, resultados automáticos, nota final, porcentaje y avisos.

Las preguntas manuales están enlazadas mediante fórmulas con `manual_grading`.

## `manual_grading`

Contiene únicamente las respuestas que requieren revisión manual.

Solo es necesario rellenar:

- `manual_score`
- `comment` (opcional)

`manual_score` tiene validación:

```text
0 <= manual_score <= max_points
```

## `code_tests`

Aparece **solo si existen preguntas de código**.

Contiene una fila por:

```text
estudiante × pregunta × test
```

e incluye nombre del test, código, resultado, número de tests superados, estrategia de puntuación y diagnóstico.

## `summary`

Incluye:

- número de estudiantes;
- entregas corregidas;
- errores;
- respuestas manuales;
- media;
- desviación estándar;
- mediana;
- máximo;
- mínimo;
- porcentaje de aprobados;
- distribución de notas.

También contiene un gráfico de barras de la distribución de notas normalizadas en escala 0–10.

---

# 10. Flujo completo recomendado

## Preparación por el profesor

1. Crear el notebook.
2. Añadir `metadata_widget`.
3. Añadir las preguntas y actividades.
4. Completar el notebook con las respuestas correctas.
5. Exportar `answer_key.csv`.
6. Configurar puntuaciones, tolerancias, preguntas manuales y tests privados.

## Trabajo del estudiante

1. Abrir el notebook.
2. Ejecutar las celdas.
3. Rellenar sus datos.
4. Resolver las actividades.
5. Comprobar `answer_status()`.
6. Ejecutar `export_answers(...)`.
7. Entregar el CSV.

## Corrección

1. Colocar todos los CSV en `submissions/`.
2. Ejecutar `evaluate_submissions.py`.
3. Abrir `grading_workbook.xlsx`.
4. Revisar `code_tests` si existe.
5. Introducir las puntuaciones manuales.
6. Consultar las notas finales en `grades`.
7. Consultar las estadísticas en `summary`.

---

# 11. Google Colab

`widgets.py` puede utilizarse en Google Colab.

El archivo debe estar disponible en el directorio de trabajo del notebook:

```python
from widgets import metadata_widget, numeric_group, export_answers
```

Al finalizar:

```python
export_answers(
    require_complete=True,
    download=True,
)
```

`evaluate_submissions.py` está pensado principalmente para ejecutarse en el entorno privado del profesor.

---

# 12. Dependencias principales

`widgets.py` utiliza:

- Python
- NumPy
- pandas
- ipywidgets
- IPython / Jupyter

`evaluate_submissions.py` utiliza:

- Python
- NumPy
- pandas
- openpyxl

`autograder-env.yml` incluye además:

- Matplotlib
- SciPy
- SymPy
- JupyterLab
- Notebook
- ipykernel

---

# 13. Compatibilidad

Se recomienda utilizar una versión reciente de Excel o LibreOffice para abrir `grading_workbook.xlsx`.

Las hojas contienen fórmulas enlazadas y fórmulas estadísticas que se recalculan al abrir el libro. Para obtener todas las estadísticas dinámicas de `summary`, se recomienda especialmente una versión moderna de Excel con soporte para funciones como `FILTER`.

---

# 14. Resumen de la arquitectura

```text
                 MATERIAL PÚBLICO
┌─────────────────────────────────────────────┐
│ Notebook                                   │
│   + widgets.py                             │
│                                             │
│ metadata → actividades → respuestas → CSV  │
└──────────────────────┬──────────────────────┘
                       │
                       │ entrega
                       ▼
                 MATERIAL PRIVADO
┌─────────────────────────────────────────────┐
│ answer_key.csv                             │
│ evaluate_submissions.py                    │
│ QUESTION_CONFIG + tests privados           │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
             grading_workbook.xlsx
       ┌───────────────┼───────────────┐
       ▼               ▼               ▼
    grades      manual_grading     code_tests
       │
       ▼
     summary
```

La separación entre el notebook y la lógica de corrección permite utilizar una única versión pública de cada actividad y mantener privadas tanto las soluciones como los criterios de evaluación.
