# Sistemas Lineales — Jupyter Book

Este repositorio contiene un Jupyter Book construido con MyST Markdown para la docencia de Sistemas Lineales. Incluye contenido teórico, ejemplos y visualizaciones interactivas.

---

## Instalación

Requiere Python 3.9+ y Conda (o Mamba).

```bash
# Crear y activar entorno
conda create -n <env-name> python=3.11 -y
conda activate <env-name>

# Instalar Jupyter Book (v2 alpha) y librerías de gráficos
pip install "jupyter-book>=2.0.0a0"
pip install bokeh plotly matplotlib
```

Opcional (conversión de imágenes en Ubuntu/Debian):

```bash
sudo apt-get install poppler-utils inkscape
```

---

## Uso rápido

```bash
# Inicializar (solo la primera vez)
jupyter book init

# Lanzar servidor local
jupyter book start

# Limpiar compilaciones
jupyter book clean .
```

---

## Estructura del repositorio

```
.
├─ content/                # capítulos y secciones
│  ├─ intro.md
│  ├─ 001-chapter1.ipynb
│  └─ figures/             # imágenes
├─ tools/                  # utilidades de conversión
├─ utils/                  # Métodos python útiles
├─ myst.yml                # configuración del libro
├─ index.md
└─ README.md
```

---

## Cómo añadir un nuevo capítulo

1. Crear un nuevo notebook en `content/`, por ejemplo:

   ```
   content/002-transformadas.ipynb
   ```

2. Seguir esta estructura mínima:

```markdown
# Título del capítulo

Breve introducción.

## Sección 1

Contenido...

## Sección 2

Contenido...
```

3. Añadir el archivo al índice (`myst.yml`):

```yaml
toc:
  - file: content/001-chapter1
  - file: content/002-transformadas
```

4. Compilar y revisar:

```bash
jupyter book start
```

---

## Ejemplo mínimo de notebook

```python
import numpy as np
import matplotlib.pyplot as plt

x = np.linspace(0, 2*np.pi, 100)
y = np.sin(x)

plt.plot(x, y)
plt.title("Señal seno")
plt.show()
```

---

## Figuras

````md
```{figure} figures/my_plot

---
:name: fig-my-plot
:width: 60%
---

**Figura:** Descripción breve. Referencia: {numref}`fig-my-plot`
```

````
---
## Definiciones

````md
```{important .simple icon=false} Titulo
Texto de la definición
```
````
---

## Ejercicios y soluciones

Se utiliza un enfoque simple basado en admonitions.

Ejercicio:

````md
```{warning .simple icon=false} Ejercicio 1
:class: ejercicio

Resuelve:
$$
x' + x = 0
$$
```

````

Solución:

````md
```{tip .simple icon=false} Solución 1
:class: solucion dropdown

$$
x(t) = Ce^{-t}
$$

````

Notas:

- `dropdown` permite ocultar/mostrar la solución
- Numeración manual (1, 2, ...)

---

## Código ejecutable

````md
```{code-cell} ipython3
import numpy as np
np.sqrt(2)
```

````

---

## Conversión de imágenes

PDF a SVG:

```bash
./tools/pdf2svg-batch.sh content/figures content/figures
````

PDF a PNG:

```bash
DPI=300 ./tools/pdf2png-batch.sh content/figures/<dir>
```

---

## Guía de estilo

### Títulos y encabezados

* Usar un único encabezado de nivel 1 (`#`) por capítulo.
* Usar `##` para secciones principales.
* Usar `###` solo para subsecciones dentro de una sección.
* Evitar títulos demasiado largos.
* Preferir títulos descriptivos frente a genéricos.


### Notación matemática

* Usar siempre LaTeX para variables, ecuaciones y operadores.
* Escribir las variables en cursiva matemática: `$x(t)$`, `$h(t)$`, `$y(t)$`.
* Usar ecuaciones centradas para resultados importantes:

```markdown
$$
y(t) = x(t) * h(t)
$$
```

* Mantener una notación consistente en todo el libro:

  * entrada: `$x(t)$`
  * salida: `$y(t)$`
  * respuesta impulsional: `$h(t)$`
  * tiempo continuo: `$t$`
  * tiempo discreto: `$n$`

### Texto docente

* Introducir cada bloque matemático con una frase breve.
* Explicar qué representa cada ecuación importante.
* Evitar párrafos excesivamente largos.
* Separar claramente teoría, ejemplo y conclusión.
* Usar listas solo cuando ayuden a resumir conceptos.


### Ejercicios y soluciones

Los ejercicios se escriben con admonitions:

````md
```{warning .simple icon=false} Ejercicio 1.1
:class: ejercicio

Enunciado del ejercicio.
```

````

Las soluciones se escriben como bloques desplegables:

````md
```{tip .simple icon=false} Solución 1.1
:class: solucion dropdown

Desarrollo de la solución.
```

````

Convenciones:

- Numerar manualmente como `Ejercicio número`, por ejemplo `Ejercicio 3`.
- Usar la misma numeración para la solución correspondiente.
- Colocar la solución justo después del ejercicio o al final de la sección, pero mantener el criterio dentro de cada capítulo.
- No mezclar varios ejercicios dentro de un mismo bloque.

### Figuras

- Guardar las figuras en `content/figures/` o en subcarpetas temáticas.
- Usar nombres descriptivos, sin espacios ni caracteres especiales.
- No incluir la extensión en la directiva `figure`.
- Añadir siempre pie de figura.
- Usar `:name:` cuando la figura se vaya a referenciar.

Ejemplo:

````md
```{figure} figures/T1/sistema_rc
---
:name: fig-sistema-rc
:width: 60%
---

**Figura:** Circuito RC considerado como sistema entrada-salida.
```

````

### Código

- Añadir a las celdas de código el tag **remove-input** para que no se visualize.
- No colocar celdas de código antes del titulo al comienzo del notebook.
- No dejar código de depuración (`print` innecesarios, variables temporales, pruebas antiguas).
- Si una celda tarda mucho en ejecutarse, indicarlo en el texto.

### Visualizaciones

- Preferir Bokeh para gráficas interactivas.
- Usar Matplotlib solo para figuras estáticas sencillas.
- Mantener títulos, etiquetas y unidades en los ejes.
- Usar rangos de ejes coherentes entre figuras comparables.
- Evitar gráficas sobrecargadas.

### Nombres de archivos

Usar nombres consistentes y ordenables:

```text
001-introduccion.ipynb
002-sistemas-lti.ipynb
003-convolucion.ipynb
004-transformada-fourier.ipynb
````

Para figuras:

```text
sistema_rc.svg
respuesta_impulsional.png
convolucion_grafica.svg
```

Evitar:

```text
figura nueva final buena.png
plot1.png
Captura de pantalla.png
```

### Buenas prácticas generales

* Mantener notebooks limpios, sin outputs innecesarios.
* Usar nombres de archivos consistentes.
* Evitar figuras demasiado pesadas.
* Revisar siempre el resultado final en el navegador.
* Comprobar enlaces internos y referencias a figuras.
* Mantener un estilo visual y narrativo uniforme entre capítulos.

---

## Documentación

* [https://mystmd.org/guide](https://mystmd.org/guide)
* [https://next.jupyterbook.org](https://next.jupyterbook.org)

