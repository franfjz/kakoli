# tests/gui

Tests de la interfaz (`gui/`, hoy repartido entre `nucleo/tema.py` y `clases/`):
arranque, navegación de dos niveles, bloqueo «una tarea a la vez», handoff,
mapeo `_tag_log`, y el mapeo por pestaña `_validar()` -> `Opciones`.

**Requieren Tkinter** (marcador `gui`): se saltan si no hay display. Usan
`withdraw()` y bombean `procesar_cola` a mano, sin `mainloop`. Se llenan en la
Fase 2 (ver `docs/REESTRUCTURACION.md`).
