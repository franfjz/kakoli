# tests/tasks

Tests de cada tarea por su motor (contrato `ejecutar`), sin Tkinter:

- `tests/tasks/<tarea>/` — un directorio por tarea (comprimir, descomprimir,
  combinar, descombinar, aplanar, desaplanar, renombrar, eliminar): caso normal,
  errores de `rutas_validadas`, pausa + reanudación, equivalencia 1 vs N hilos,
  seguridad (anti path-traversal) y compatibilidad de formatos en disco.
- `tests/tasks/pares/` — integración BIDIRECCIONAL de las gemelas
  (`Descomprimir(Comprimir(x)) == x`, etc.), usando solo la API pública de cada
  motor para no crear dependencia entre tareas.

Se llenan en las Fases 1 y 8-12 (ver `docs/REESTRUCTURACION.md`).
