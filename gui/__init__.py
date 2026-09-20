# -*- coding: utf-8 -*-
"""gui — estructura general de la aplicación Tkinter (no conoce las tareas
concretas). Base común de la interfaz:

    tema         tema visual (paleta, fuentes, estilos ttk/tk, icono).
    app          la ventana principal (App): navegación de dos niveles, portada,
                 monitor compartido, bloqueo, bomba de colas, Ayuda.
    pestana_base PestanaBase (esqueleto común de una pestaña de tarea).
    componentes  piezas reutilizables (MarcoDesplazable, fila_texto).
    contexto     ContextoApp (Protocol): lo que App ofrece a una pestaña.
    campo        dataclass Campo (un campo de entrada declarativo).
    constantes   versión/marca, enlaces, ajustes de la GUI, politica_desde.
    ayuda        texto general de la vista de Ayuda (intro + cierre).

La GUI específica de cada tarea vive en su carpeta `tasks/<tarea>/pestana.py`.
"""
