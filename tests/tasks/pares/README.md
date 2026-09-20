# tests/tasks/pares

Integración bidireccional de las tareas gemelas (relación reversible), un archivo
por relación:

- `test_comprimir_descomprimir.py` — `Descomprimir(Comprimir(árbol)) == árbol`
  (normal, compacto, paralelo, reanudación; nombres + bytes + carpetas vacías).
- `test_combinar_descombinar.py` — `Descombinar(Combinar(fuentes)) == fuentes`.
- `test_aplanar_desaplanar.py` — `Desaplanar(Aplanar(árbol, modo=ruta)) == árbol`.

Regla: usan SOLO la API pública de cada motor (`ejecutar`, `Opciones`,
`rutas_validadas`), nunca funciones privadas ni imports cruzados entre tareas.
Las combinaciones NO reversibles (modo `final`, `reemplazar`, `crear_indice=False`,
separador dentro del nombre) se cubren como tests explícitos del comportamiento
documentado. Comparación completa: recuento + firma (tamaño, sha256), mtime ±2 s.
