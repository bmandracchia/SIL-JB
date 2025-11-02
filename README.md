# Sistemas Lineales - Jupyter Book

Este repositorio contiene un Jupyter Book construido con [MyST Markdown](https://mystmd.org/guide).

## Instalación

> Requiere Python 3.9+ y Conda (o Mamba).

```bash
# Crear y activar el entorno
conda create -n <env name> python=3.11 -y
conda activate <env name>

# Instalar jupyter-book (v2 alpha, según se solicita) y librerías de gráficos
pip install "jupyter-book>=2.0.0a0"
pip install bokeh plotly matplotlib

# (Opcional) Herramientas de conversión PDF/PNG/SVG usadas por el script de imágenes
# Ubuntu/Debian:
#   sudo apt-get install poppler-utils inkscape
```

### Inicializar el libro localmente

```bash
# Desde la raíz del repositorio (donde está myst.yml)
jupyter book init
# Sigue el enlace para abrir el sitio generado en tu navegador
```

### Construir el libro localmente

```bash
# Desde la raíz del repositorio (donde está myst.yml)
jupyter book start

# Sigue el enlace para abrir el sitio generado en tu navegador
```

Utilidades comunes:

```bash
# Limpiar compilaciones previas
jupyter book clean .
```

## Estructura del repositorio (sugerida)

```
.
├─ content/                 # capítulos/secciones
│  ├─ intro.md
│  ├─ 001-chapter1.ipynb    # el primer número representa el Tema/Parte
│  └─ figures/              # imágenes (png/svg/pdf)
├─ tools/
│  ├─ inkscape-pdf2svg.sh   # PDF → SVG (texto→trazados, más seguro)
│  └─ pdf2png-batch.sh      # PDF → PNG (ráster)
├─ myst.yml
├─ index.md
└─ README.md
```

## Cómo contribuir

¡Las contribuciones son bienvenidas! Por favor:

1. **Crea una rama**:
   `git checkout -b feature/tu-tema`
2. **Añade/modifica contenido** en `content/` y actualiza `myst.yml` para que las nuevas páginas aparezcan en el libro.
3. **Ejecuta el script de conversión de imágenes** si añadiste PDFs vectoriales (ver *Conversión de imágenes* más abajo).
4. **Compila localmente** para revisar enlaces, figuras y formato: `jupyter book start`
5. **Abre un Pull Request** con un resumen conciso de los cambios y, si puedes, capturas de pantalla de las páginas clave.

### Guías de estilo para el contenido

* Prefiere **Jupyter Notebooks** (`.ipynb`) frente a **MyST Markdown** (`.md`).
* Usa encabezados semánticos (`#`, `##`, `###`…).
* Nombra las figuras de forma descriptiva y colócalas en `content/figures/`.
* En cuadernos, limpia salidas innecesarias y procura tiempos de ejecución razonables.

## Añadir figuras

Usa la directiva `figure` de MyST (funciona con PNG/SVG/PDF):

````md
```{figure} figures/my_plot
 ---
 :name: fig-my-plot
 :width: 60%
 :alt: Una descripción concisa (alt text) de la figura.
 ---

**Figura:** Un pie de figura breve. Puedes referenciarla como {numref}`fig-my-plot`.
```
````

>Para facilitar la exportación en diferentes formatos, no especifiques la extensión de la figura. Así el script de exportación puede buscar el mejor formato.

## Ejercicios y soluciones

MyST permite escribir ejercicios así:

````md
```{exercise} gradient-descent-basic
:label: ex-gd-basic
:class: dropdown

Considera la función cuadrática \(f(x) = (x-3)^2\).
1) Calcula el gradiente.
2) Muestra una iteración de descenso de gradiente con paso \(\eta\).

```

```{solution} ex-gd-basic
:class: dropdown

- \(\nabla f(x)=2(x-3)\).  
- Un paso: \(x_{k+1} = x_k - \eta\,2(x_k-3)\).
```
````

* `:class: dropdown` hace el bloque colapsable.
* Enlaza a un ejercicio mediante `{ref}` o su etiqueta (p. ej., `{ref}`ex-gd-basic`).

## Avisos MyST (admonitions / callouts)

Usa admoniciones integradas para notas, consejos, advertencias, etc.

````md
```{note}
Esta es una nota concisa para lectores.
```

```{tip}
Truco: mantén las celdas de código pequeñas y enfocadas.
```

```{warning}
Cuidado con imágenes grandes: optimiza o conviértelas a SVG/PNG antes.
```

```{admonition} Idea clave
:class: dropdown
Resume la idea central y oculta detalles por defecto.
```
````

## Celdas de código ejecutables

Puedes incluir código ejecutable con `{code-cell}`:

````md
```{code-cell} ipython3
import numpy as np
np.sqrt(2)
```
````

(Configura la ejecución en `myst.yml` si quieres que el libro ejecute celdas al compilar).

## Conversión de imágenes

Si añades PDFs exportados desde herramientas de gráficos o LaTeX, conviértelos para la web:

* **PDF → SVG** (vectorial, más seguro visualmente convirtiendo texto a trazados):

  ```bash
  ./tools/pdf2svg-batch.sh content/figures content/figures
  # Por defecto, convierte el texto a trazados para evitar problemas de fuentes.
  # Mantén el texto seleccionable (si sabes que las fuentes están embebidas):
  TEXT_TO_PATH=false ./tools/inkscape-pdf2svg.sh content/figures/<carpeta de pdf>
  ```

* **PDF → PNG** (ráster, elige DPI):

  ```bash
  DPI=300 ./tools/pdf2png-batch.sh content/figures/<carpeta de pdf>
  ```

## Añadir tu página al Índice (Table of Contents)

Edita `myst.yml` e incluye tu nueva página:

```yaml
toc:
  - file: content/chapter1
  - file: content/your_new_page-1   # ← añade esta línea (sin .md)
    children:
      - file: your_new_page-2
```

## Más documentación

* Guía y sintaxis de MyST: [https://mystmd.org/guide](https://mystmd.org/guide)
* Documentación de Jupyter Book (estructura, config, ejecución, ejercicios, citas): [https://next.jupyterbook.org](https://next.jupyterbook.org)
