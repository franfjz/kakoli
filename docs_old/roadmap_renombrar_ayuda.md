# Roadmap: motor "Renombrar" + portada solo-tarjetas + pestaña "Ayuda"

Tres cambios pedidos por el usuario (este documento **solo diseña**, no toca código):

1. **Motor nuevo "Renombrar"** (antes de Eliminar): modificar nombres de archivos —en un
   solo directorio o en subdirectorios— añadiendo texto al **inicio**, reemplazando un
   **fragmento interno** y/o añadiendo texto al **final**, **sin tocar la extensión**.
2. **Portada solo con tarjetas**: en el nivel 1, **ocultar la barra de pestañas
   superior**; que solo se vean las **categorías**, cada una en un **recuadro con una
   breve descripción**.
3. **Pestaña "Ayuda"** al final: un README dentro de la app que describe, con detalle
   técnico, cada tarea y sus opciones, para ayudar a entender cada pestaña.

Se apoya en el código real (menú de dos niveles, motores declarativos A–H). Referencias:
`ARQUITECTURA.md`, `GUI.md`, `escalabilidad.md`, `roadmap_menu_pestanas.md`.

Fecha: 2026-09-07.

---

## PARTE A — Motor "Renombrar"

### A.1 Semántica

**Entrada**: un **directorio** (`origen`). **Ámbito**: solo ese directorio o también sus
**subdirectorios** (`recursivo`). Se renombran **archivos** (no carpetas, N3).

Para cada archivo, se separa **nombre base (stem)** de **extensión** y se transforma
**solo el stem** (N2: la extensión = último sufijo, p. ej. `.txt`; `.tar.gz` → solo
`.gz`, ver decisión):

```
nuevo_stem = prefijo + reemplazar(stem) + sufijo
nuevo_nombre = nuevo_stem + extension
```

- **Prefijo**: texto al inicio del nombre.
- **Reemplazar**: sustituye un fragmento interno del stem (`buscar` → `reemplazar`),
  todas las ocurrencias o solo la primera (N5), sensible o no a mayúsculas (N5).
- **Sufijo**: texto al final del nombre, **antes de la extensión**.
- Las tres son **combinables** en una sola pasada (N1). Si `nuevo_nombre == nombre`, no
  se hace nada (se cuenta como "sin cambios").

**Conflictos** (el nuevo nombre ya existe en esa carpeta) — política `conflicto` (N4):
**numerar** (`nombre_2.ext`, por defecto, no se pierde nada) u **omitir** (se deja como
está y se avisa).

**Vista previa** (N6): el usuario puede **simular** (mostrar `antes → después` sin
renombrar nada) antes de aplicar. Es la red de seguridad principal (N7: sin "deshacer"
en la v1; queda como posible extensión con un log de renombrado).

### A.2 Diseño del motor (`motor_renombrar.py`)

- `class Opciones(comun.OpcionesBase)`:
  - `prefijo: str = ""`, `sufijo: str = ""`.
  - `buscar: str = ""`, `reemplazar: str = ""`.
  - `sensible_mayusculas: bool = True`, `solo_primera: bool = False`.
  - `recursivo: bool = True`, `omitir_ocultos: bool = False`.
  - `conflicto: str = "numerar"` (`numerar` | `omitir`).
  - `simular: bool = False`.
  - (hereda `detallado` + `politica`.)
- `nuevo_nombre(nombre, opts) -> str`: la transformación pura (stem/ext), fácil de testear.
- `rutas_validadas(origen) -> Path`.
- `procesar(origen, opts, *, callbacks)`: recorre (`os.walk` si `recursivo`, o solo el
  nivel), calcula el nuevo nombre, resuelve conflicto y **renombra** (`os.rename`,
  atómico en el mismo volumen). En modo `simular`, solo registra `antes → después` en el
  `log` y no toca disco. Devuelve `comun.Resultado` (renombrados / sin cambios /
  omitidos / errores).
- `ejecutar(entradas={"origen": …}, opts, *, callbacks)` + `main()` con `comun.correr_cli`.
- **Rendimiento** (N8): secuencial (el `rename` es muy rápido); paralelizar es opcional a
  futuro (serializando por nombre destino, como Aplanar). No hace falta índice ni
  reanudación en la v1 (es rápido; ver N7).

### A.3 Diseño de la GUI (`PestanaRenombrar`)

- Categoría nueva **"Renombrado"**, colocada **antes de "Eliminar"** (orden final:
  Combinación / Compresión / Aplanado / **Renombrado** / Eliminar). Tarea única (como
  Eliminar).
- `nombre="Renombrar"`, `MOTOR=motor_renombrar`, `ENTRADAS=[Campo("origen","Carpeta:",
  "carpeta")]`.
- Opciones (secciones `LabelFrame`, helpers `_check`/`_combo` + `Entry`):
  - **"Añadir texto"** → `Entry` Prefijo, `Entry` Sufijo.
  - **"Reemplazar"** → `Entry` Buscar, `Entry` Reemplazar por, `Checkbutton` "Distinguir
    mayúsculas", `Checkbutton` "Solo la primera vez".
  - **"Ámbito"** → `Checkbutton` "Incluir subdirectorios" (recursivo), `Checkbutton`
    "Omitir ocultos".
  - **"Conflictos"** → `Combobox` (Numerar / Omitir).
- **Vista previa**: botón **"Vista previa"** que ejecuta el motor en modo `simular` y
  vuelca `antes → después` en la consola (sin renombrar). El botón *Renombrar* aplica.
- `_validar()`: origen + al menos una operación no vacía (si todo está vacío → `ValueError`
  "indica algún cambio"). Construye `Opciones`.
- `_confirmar(datos)`: aviso modal recordando que el renombrado es **en bloque** y
  recomendando la vista previa; (opcional) resumen de cuántos cambiarían.

---

## PARTE B — Portada solo con tarjetas (ocultar pestañas superiores)

### B.1 Situación actual

En el nivel 1, `App._pintar_barra` pinta un **botón por categoría** en `barra_nav`
(`[ Combinación ] [ Compresión ] …`) **y además** la portada muestra **tarjetas**
clicables (`_tarjeta_categoria`). Es redundante.

### B.2 Cambio

- `_pintar_barra`, en nivel 1 (`_categoria_actual is None`): **no pintar nada** (barra
  vacía). Las **tarjetas** de la portada pasan a ser la única navegación de nivel 1. En
  nivel 2 la barra sigue igual (`[ ← ]` + tareas).
- `_tarjeta_categoria`: añadir una **breve descripción** por categoría. Nuevo campo
  **`Categoria.descripcion: str`** (una línea). La tarjeta muestra **nombre** (grande) +
  **descripción** (gris) — el "recuadro" ya lo da `tema.estilo_tarjeta_menu`. (Se puede
  conservar la lista de tareas como tercera línea, o sustituirla por la descripción; ver
  P2.)
- Texto de la portada: "Ábrela en la barra de arriba o pulsa una tarjeta" → "Pulsa una
  categoría" (ya no hay barra en nivel 1).

### B.3 Descripciones propuestas (una línea por categoría)

- **Combinación**: "Fundir varios árboles de directorios en uno, y deshacer la fusión."
- **Compresión**: "Comprimir una carpeta en ZIPs anidados y volver a extraerla."
- **Aplanado**: "Llevar todos los archivos a una sola carpeta, y reconstruir el árbol."
- **Renombrado**: "Renombrar archivos en bloque (prefijo, reemplazo, sufijo)."
- **Eliminar**: "Borrado definitivo y recursivo (no pasa por la papelera)."
- **Ayuda**: "Guía detallada de todas las tareas y sus opciones." (ver Parte C.)

---

## PARTE C — Pestaña "Ayuda" (README dentro de la app)

### C.1 Naturaleza

"Ayuda" **no es un motor** (no tiene Origen / Iniciar / Pausar / progreso): es una
**vista de solo lectura** con el README. No encaja en `PestanaBase`. Se trata como un
**caso especial** de la navegación.

### C.2 Diseño

- Una **tarjeta "Ayuda"** al final de la portada (última, tras Eliminar), con su recuadro
  y descripción. Al pulsarla, en vez de `_entrar(categoria)`, se llama a un
  **`_entrar_ayuda()`** que muestra una **vista de ayuda** en `area_tarea` (como una
  tarea, pero sin motor) y pinta la barra con solo **`[ ← ]`** (volver a la portada).
- La vista de ayuda: un **`Canvas` + `Text`/etiquetas scrollables** (reutilizar el patrón
  de scroll de `PestanaBase`), con **secciones por tarea**. Contenido **estructurado en el
  código** (A2: una lista `AYUDA` de secciones, mantenida a mano; self-contained, sin
  leer `GUI.md` en runtime).
- Bloqueo: si hay una tarea en curso (`_bloqueado`), `[ ← ]` y el acceso se comportan como
  en el resto (la ayuda es de solo lectura, así que consultarla no interfiere; decisión
  menor: permitir abrir Ayuda incluso bloqueado, ya que no lanza nada).

### C.3 Contenido (guion del README)

Por cada tarea, con enfoque **técnico y de opciones** (lo que el usuario pidió):

- **Qué hace** y **entradas**.
- **Cada opción**: a qué equivale y su **consecuencia** (mapea a lo ya documentado en
  `GUI.md`).
- **Particularidades**: p. ej. la **ambigüedad** de Desaplanar (reconstruye por los
  nombres, un `-` literal crea carpetas), el carácter **in-situ** de Combinar y su
  índice, la **irreversibilidad** de "reemplazar"/Eliminar, la **reanudación tras cerrar**
  (qué tareas y cómo), el modo "solo nombre final" **no desaplanable**, etc.
- Nota general: rendimiento común (Hilos + Modo ligero), pausa/continuar, handoff entre
  tareas.

---

## Decisiones a resolver (antes de la Fase 0)

**Renombrar**
- **N1 — Operaciones combinables** (prefijo + reemplazo + sufijo en una pasada).
  Propuesta: **sí**, en ese orden (reemplazo sobre el stem, luego prefijo/sufijo).
- **N2 — Extensión**: solo la **última** (`Path.suffix`, `.gz` de `.tar.gz`) o
  **compuesta**. Propuesta: **última** (simple y predecible); documentar el caso compuesto.
- **N3 — ¿Renombrar solo archivos** o también carpetas? Propuesta: **solo archivos**.
- **N4 — Conflictos**: **numerar** (`_2`, por defecto) u **omitir**. Propuesta: ambas,
  numerar por defecto.
- **N5 — Reemplazo**: sensibilidad a mayúsculas y "todas / solo la primera". Propuesta:
  **sensible** y **todas** por defecto, ambas configurables.
- **N6 — Vista previa**: **botón "Vista previa"** (simula y muestra `antes → después`).
  Propuesta: sí (además del aviso de confirmación).
- **N7 — ¿Deshacer (undo)?** Propuesta: **no en la v1** (la vista previa es la red de
  seguridad); posible extensión futura con un log de renombrado.
- **N8 — ¿Paralelo/reanudable?** Propuesta: **secuencial**, sin índice (rename es rápido).

**Portada**
- **P1 — Ocultar del todo la barra en nivel 1** (solo tarjetas). Propuesta: **sí**.
- **P2 — Tarjeta**: ¿mostrar **descripción** en vez de / además de la lista de tareas?
  Propuesta: **nombre + descripción** (y, si cabe, las tareas en una tercera línea gris).

**Ayuda**
- **A1 — Ubicación**: **tarjeta "Ayuda"** al final de la portada (no una categoría de
  tareas), con vista dedicada. Propuesta: **sí**.
- **A2 — Contenido**: **estructurado en el código** (self-contained). Propuesta: sí.
- **A3 — Barra en la vista Ayuda**: solo **`[ ← ]`** para volver. ¿Permitir abrir Ayuda
  aunque haya una tarea en curso? Propuesta: **sí** (es de solo lectura).

---

## Fases

- **Fase 0 — Motor Renombrar (sin GUI).** `motor_renombrar.py`: `Opciones`,
  `nuevo_nombre` (transformación pura), `procesar` (recorrido + conflictos + `simular`),
  `ejecutar` + `main`. Tests: prefijo/sufijo/reemplazo (todas/primera, sensibilidad),
  **extensión intacta** (incl. `.tar.gz`), sin cambios, recursivo vs no, colisiones
  (numerar/omitir), unicode, `simular` no toca disco. Round-trip no aplica; se comprueba
  el resultado esperado en disco.
  **ESTADO: HECHA** (2026-09-07). `motor_renombrar.py`: `Opciones(OpcionesBase)` con
  prefijo/sufijo/buscar/reemplazar/sensible_mayusculas/solo_primera/recursivo/
  omitir_ocultos/conflicto(numerar|omitir)/simular. **N2 (compuestas)**: `dividir_ext`
  reconoce `EXT_COMPUESTAS` (`.tar.gz`, `.tar.bz2`, `.tar.xz`, `.tar.zst`, …) y preserva
  la extensión entera; dotfiles (`.gitignore`) sin extensión. `nuevo_nombre` =
  `prefijo + reemplazar(stem) + sufijo + ext` (reemplazo sensible con `str.replace` o
  insensible con regex + reemplazo LITERAL). `procesar`: recorrido (recursivo/plano,
  ordenado), `_resolver` (numerar preservando ext / omitir; `_ocupado` mira `reservados`
  + `dest.exists()` con `_mismo` para el caso case-only en Windows), `os.rename` o solo
  log en `simular`; `Resultado` (renombrados/sin_cambios/omitidos). `main` con
  `--simular`, `--prefijo/--sufijo/--buscar/--reemplazar`, `--ignorar-mayusculas`,
  `--solo-primera`, `--no-subdirectorios`, `--conflicto`. Verificado test_renombrar
  (26/26) + CLI (simular lista antes→después, real renombra, `.tar.gz` intacto). La app
  (kakoli) no se toca aún (Fase 1).
- **Fase 1 — Pestaña Renombrar + categoría "Renombrado".** `PestanaRenombrar`
  (declarativa: `ENTRADAS`, opciones, `_validar`, `_confirmar`, botón "Vista previa");
  `Categoria("Renombrado", [PestanaRenombrar])` **antes de Eliminar** en `App.MENU`. Test
  GUI (vista previa lista `antes→después` sin tocar disco; renombrado real; conflictos).
  **ESTADO: HECHA** (2026-09-07). kakoli importa `motor_renombrar as mrenom`.
  `PestanaRenombrar` (nombre="Renombrar", MOTOR=mrenom, origen carpeta; helper `_entry`
  Label+Entry; secciones "Añadir texto" [prefijo/sufijo], "Reemplazar un fragmento"
  [buscar/reemplazar + Distinguir mayúsculas + Solo la primera], "Ámbito" [Incluir
  subdirectorios/Omitir ocultos], "Conflictos" [Combobox `_CONFLICTOS_RENOM`
  numerar/omitir], "Vista previa" [botón]). Vista previa: `_previsualizar` pone
  `_simular_flag=True` y llama `_iniciar`; `_validar` lee el flag→`opts.simular` y lo
  resetea; exige alguna operación (si no, ValueError). `_confirmar` no pregunta en
  simular; en real, modal de aviso (renombrado en bloque sin deshacer). `App.MENU` =
  (Combinación, Compresión, Aplanado, **Renombrado**, Eliminar) → 6 categorías/7 tareas;
  nivel 2 de Renombrado: `[ ← ] [ Renombrar ]`. Verificado test_renombrar_gui (8/8: orden
  MENU, opts desde GUI, sin-operación→ValueError, vista previa NO toca disco + resetea el
  flag, renombrado real aplicado) + regresión (solo test_gui_fase5 ajustado al 4º corchete
  `[ Renombrado ]`; test_cd/menu/fase8 usan len(clases_tarea())/categoría por nombre, OK).
- **Fase 2 — Portada solo-tarjetas.** `_pintar_barra` no pinta en nivel 1;
  `Categoria.descripcion`; `_tarjeta_categoria` con recuadro + descripción; texto de la
  portada. **Ajustar tests de navegación** que asumen botones de categoría en
  `estado_barra` a nivel 1 (test_menu, test_gui_fase5): ahora ese nivel devuelve `[]` y la
  navegación de nivel 1 se prueba por las tarjetas / `_entrar`.
  **ESTADO: HECHA** (2026-09-07). `Categoria.descripcion: str = ""`; `App.MENU` con una
  descripción por categoría. `_pintar_barra` en nivel 1 hace `barra_nav.grid_remove()`
  (barra oculta) y en nivel 2 `barra_nav.grid()` (se muestra `[ ← ]` + tareas).
  `_tarjeta_categoria` muestra **nombre (head) + descripción (normal) + tareas (gris)**;
  todo clicable (hover resalta). Texto de la portada: "Pulsa una categoría para abrirla".
  Verificado captura (5 recuadros con descripción, sin barra superior). Tests ajustados:
  test_gui_fase5 (nivel 1 → `estado_barra()==[]`, corchetes solo en nivel 2), test_cd
  (categoría nueva se comprueba por `MENU`/`clases_tarea`, y `estado_barra()==[]` en nivel
  1). test_menu (entrar-desde-tarjeta, recuerdo, estilos de nivel 2) sigue verde.
- **Fase 3 — Vista "Ayuda".** Tarjeta "Ayuda" al final de la portada; `_entrar_ayuda()` +
  vista scrollable de solo lectura con secciones por tarea (contenido `AYUDA` en el
  código); barra con `[ ← ]`. Test: la tarjeta abre la vista; el `[ ← ]` vuelve; el
  contenido cubre todas las tareas.
  **ESTADO: HECHA** (2026-09-07). Constante módulo `AYUDA_SECCIONES` (lista de
  (título, [párrafos]); un párrafo con dos espacios iniciales se pinta en gris) con una
  sección por tarea (Combinar/Descombinar/Comprimir/Descomprimir/Aplanar/Desaplanar/
  Renombrar/Eliminar) + intro + rendimiento/reanudación, todo técnico y orientado a las
  opciones. Portada: helper genérico `_tarjeta(titulo, descripcion, sub, comando)`
  (refactor de `_tarjeta_categoria`) + `_tarjeta_ayuda()` (tarjeta final "Ayuda").
  `_entrar_ayuda()`: oculta la portada, muestra `_ayuda_frame` (Canvas + Scrollbar +
  interior con `_render_ayuda`, wraplength adaptado al ancho, rueda del ratón), barra
  reducida a `[ ← ]` (→ `_ir_menu`). `_ir_menu` también oculta la vista de Ayuda
  (`_en_ayuda`). No es `PestanaBase` (sin motor/Iniciar/Pausar). Verificado test_ayuda
  (20/20: AYUDA cubre las 8 tareas + rendimiento; entrar muestra la vista con barra solo
  `[ ← ]` y >10 párrafos; volver reactiva la portada; la vista se reutiliza) + regresión
  (test_menu ajustado: la portada tiene len(MENU)+1 tarjetas [+Ayuda]; barra vacía nivel 1).
- **Fase 4 — Verificación + docs.** Regresión completa (ajustar conteos por la nueva
  categoría, como con Combinación/Aplanado); capturas de portada (solo tarjetas + Ayuda) y
  de la pestaña Renombrar. Actualizar `ARQUITECTURA.md` (§2 `motor_renombrar`, §7 MENU +
  portada solo-tarjetas + vista Ayuda), `GUI.md` (nueva sección Renombrar + portada +
  Ayuda) y `escalabilidad.md` (Renombrado = otra validación del molde: motor + pestaña +
  una línea en `MENU`).
  **ESTADO: HECHA** (2026-09-08). Verificación cruzada: suite completa **31/31** (incluidos
  test_renombrar, test_renombrar_gui, test_ayuda) + los **4 modos de bench** (compresión/
  merge/flatten/reanudar) verdes. Ajustes de tests por la nueva categoría / portada
  solo-tarjetas: test_gui_fase5 y test_aplanar_gui (orden del MENU con "Renombrado"),
  test_cd (categoría por `MENU`/`clases_tarea` + `estado_barra()==[]` en nivel 1),
  test_menu (portada con `len(MENU)+1` tarjetas por la de Ayuda; barra vacía nivel 1).
  Docs: `ARQUITECTURA.md` (§2 `motor_renombrar` + fila `kakoli` con 8 tareas/Renombrado/
  Ayuda; §7 MENU con `descripcion`, portada solo-tarjetas y vista Ayuda), `GUI.md`
  (§1 portada solo-tarjetas + Ayuda; **§5d Renombrar** con todos los selectores + Vista
  previa), `escalabilidad.md` (validación "Renombrado": cero extensiones del framework).
  Capturas: renombrar.png, portada.png, ayuda.png.

---

## ROADMAP RENOMBRAR + PORTADA + AYUDA — COMPLETO (fases 0–4)

Tres cambios entregados: (A) **motor Renombrar** (categoría "Renombrado" antes de
Eliminar) — prefijo/reemplazo/sufijo sin tocar la extensión (compuestas incluidas),
conflictos numerar/omitir, vista previa (simular); (B) **portada solo con tarjetas**
(barra superior oculta en nivel 1) con recuadro + descripción por categoría; (C) **vista
Ayuda** (README dentro de la app, scrollable, una sección técnica por tarea). Todo con la
suite y los 4 bench en verde. Renombrar siguió el molde (motor + pestaña + una línea en
`MENU`); portada y Ayuda son presentación en `App`.

Orden recomendado: 0 → 1 (motor y su pestaña) → 2 (portada) → 3 (Ayuda) → 4 (docs).

---

## Riesgos y notas

- **Renombrar es in-place y masivo**: mitigado por la **vista previa** (simular) + aviso +
  política de conflictos (numerar no pierde nada). Sin "deshacer" en la v1 (N7).
- **Colisiones y orden**: al renombrar dentro de una carpeta, dos archivos pueden chocar;
  "numerar" resuelve de forma determinista; en secuencial no hay carreras.
- **Tests de navegación**: ocultar la barra de nivel 1 cambia `estado_barra()` en la
  portada (pasa a `[]`); hay que actualizar test_menu/test_gui_fase5. Añadir la categoría
  "Renombrado" cambia nº/orden de tareas → ajustar test_cd/fase8/etc. (como en las
  categorías anteriores).
- **Ayuda no es `PestanaBase`**: se integra como caso especial de la navegación (tarjeta +
  vista propia), sin motor, sin romper el bloqueo/handoff ni el monitor compartido.
- **Escalabilidad intacta**: Renombrar sigue el molde (motor + pestaña declarativa + una
  línea en `MENU`); portada y Ayuda son cambios de presentación en `App`, no del contrato
  de motores.
