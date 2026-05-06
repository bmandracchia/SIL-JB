# SIL-JB/utils/plot_helpers.py

import numpy as np
from bokeh.plotting import figure, show
from bokeh.layouts import column, row
from bokeh.models import Arrow, NormalHead, VeeHead, ColumnDataSource, CustomJS, Slider, RadioButtonGroup, Label
from bokeh.io import output_notebook

def style_math_axes(p, x_range, y_range, prolong_axes=[0.05, 0.05], margins=[0, 0, 0, 0.05], xlabel="t", ylabel=r"$$\tilde{x}(t)$$"):
    """
    Replica EXACTAMENTE el estilo 'setup_axes' de tu librería Matplotlib.
    
    Lógica portada:
    - prolong_axes: fracción de margen extra a añadir a los ejes.
    - margins: [left, right, bottom, top] en proporción al rango.
    - Flechas: Cruzan TODA la ventana visual (de límite a límite).
    - Grosor: 1.5 pt.
    """
    # 1. Limpieza total
    p.outline_line_color = None
    p.grid.visible = False
    p.axis.visible = False

    # 2. CALCULO DE MÁRGENES (Idéntico a tu código original)
    x0, x1 = x_range
    span_x = x1 - x0
    x_margin = prolong_axes[0] * span_x # 20% margen X
    
    y0, y1 = y_range
    span_y = y1 - y0
    y_margin = (prolong_axes[1] + 0.1) * span_y if span_y > 0 else 1.0 # 20% margen base Y
    # Calculamos los límites VISUALES finales (La "Caja" completa)
    vis_x0 = x0 - x_margin
    vis_x1 = x1 + x_margin
    
    vis_y0 = y0 - y_margin
    vis_y1 = y1 + y_margin 

    # Aplicamos estos límites a la cámara de Bokeh
    p.x_range.start = vis_x0 - margins[0] * (vis_x1 - vis_x0)
    p.x_range.end = vis_x1 + margins[1] * (vis_x1 - vis_x0)
    p.y_range.start = vis_y0 - margins[2] * (vis_y1 - vis_y0)
    p.y_range.end = vis_y1 + margins[3] * (vis_y1 - vis_y0)

    # 3. Estilo de Flechas
    LINE_WIDTH = 1.5
    ARROW_SIZE = 10
    
    # Usamos VeeHead para imitar el mutation_aspect=0.8 (flecha afilada)
    # fill_color=black y line_color=black la hacen sólida
    arrow_style = VeeHead(size=ARROW_SIZE, fill_color="black", line_color="black")
    
    # --- EJE X ---
    # Dibujamos la línea desde el borde izquierdo visual hasta el derecho
    p.segment(x0=vis_x0, y0=0, x1=vis_x1, y1=0, color="black", line_width=LINE_WIDTH)
    
    # Inicio desplazado un pelín (0.01) para asegurar la dirección
    p.add_layout(Arrow(end=arrow_style, 
                       x_start=vis_x1 - 0.01, y_start=0, 
                       x_end=vis_x1, y_end=0))
    
    # Etiqueta t: Debajo de la flecha
    p.add_layout(Label(x=vis_x1, y=0, text=xlabel, 
                       text_font_style="italic", text_font_size="12pt",
                       anchor="bottom_left",
                       x_offset=-10, y_offset=7)) # Ajustada para no chocar con la punta

    # --- EJE Y ---
    # Dibujamos la línea desde el borde inferior visual hasta el superior
    p.segment(x0=0, y0=vis_y0, x1=0, y1=vis_y1, color="black", line_width=LINE_WIDTH)
    
    # Punta de flecha en el extremo superior visual (vis_y1)
    # Usamos NormalHead para un aspecto más estándar en vertical
    p.add_layout(Arrow(end=arrow_style, 
                       x_start=0, y_start=vis_y1 - 0.01, 
                       x_end=0, y_end=vis_y1))

    # Etiqueta Y: A la izquierda de la punta (para no chocar con la gráfica si es alta)
    # O a la derecha, según tu preferencia. En tu código original suele quedar a la izquierda o encima.
    p.add_layout(Label(x=0, y=vis_y1, text=ylabel, 
                       text_font_size="11pt",
                       anchor="top_left",
                       x_offset=12, y_offset=-3)) # A la derecha de la flecha
    
    p.toolbar.logo = None

    return p

# ==========================================
# NUEVA VERSIÓN DE ADD_MATH_TICKS (PIXELS)
# ==========================================
def add_math_ticks(p, xticks=None, xtick_labels=None, yticks=None, ytick_labels=None, 
                   tick_len=10, font_size="10pt"):
    """
    Añade ticks usando 'Scatter' para que el tamaño sea en PIXELES (screen units),
    independiente de la escala de datos.
    
    Args:
        tick_len: Tamaño del tick en píxeles de pantalla (default 10).
    """
    # --- EJE X ---
    if xticks and xtick_labels:
        # Usamos marker="dash" rotado 90 grados (pi/2) para hacer líneas verticales
        p.scatter(x=xticks, y=0, marker="dash", angle=np.pi/2, size=tick_len, color="black")
        
        for x, label in zip(xticks, xtick_labels):
            lbl = Label(x=x, y=0, text=label, text_align='center', text_baseline='middle',
                        y_offset=-15, text_font_size=font_size, text_color="black")
            p.add_layout(lbl)

    # --- EJE Y ---
    if yticks and ytick_labels:
        # Marker "dash" horizontal
        p.scatter(x=0, y=yticks, marker="dash", angle=0, size=tick_len, color="black")
        
        for y, label in zip(yticks, ytick_labels):
            lbl = Label(x=0, y=y, text=label, text_align='right', text_baseline='middle',
                        x_offset=-10, text_font_size=font_size, text_color="black")
            p.add_layout(lbl)
    
    return p