# Roadmap: reanudar tareas tras cerrar el programa

Objetivo: poder **reanudar una tarea pausada aunque se haya cerrado la aplicación**,
comprobando el progreso guardado en disco. Al iniciar una tarea con **el mismo origen
y destino** que un proyecto anterior a medias, la app detecta el registro y ofrece
**continuar por donde se pausó** en vez de empezar de cero.

Dos metas:
1. **Unificar y hacer visible** la reanudación que YA existe (hoy es silenciosa y
   dispar entre motores).
2. **Añadir un registro persistente** a las dos tareas que aún no lo tienen: **Aplanar
   y Desaplanar**.

Este documento **solo diseña**: no toca código. Se apoya en los mecanismos reales.
Referencias: `ARQUITECTURA.md`, `GUI.md`, `roadmap_aplanar.md`, `roadmap_combinar.md`.

Fecha: 2026-09-07.

---

## 1. Estado actual (verificado en el código)

La reanudación **ya funciona tras cerrar el programa en 5 de las 7 tareas**, pero por
**dos mecanismos distintos**. La lógica vive en los **motores** (leen el estado del
disco en la siguiente llamada a `procesar`), no en la GUI: al relanzar la app y pulsar
*Iniciar* con el mismo origen/destino, el motor continúa. La GUI **no** recuerda entre
sesiones qué tarea estaba pausada (el rótulo *Continuar* es solo en memoria).

| Tarea | ¿Reanuda tras cerrar? | Mecanismo | Clave | Salvedades |
|---|---|---|---|---|
| **Comprimir** | ✅ | **JSON** `_estado_zip.jsonl` en la **salida** (append-only, se vuelca cada `PASO_REGISTRO`) | valida `raiz` | `opts.reiniciar` empieza de cero |
| **Combinar** | ✅ (si hay índice) | **JSON** `.kakoli_combinacion.json` en el **principal**; `_procesados()` salta lo hecho | el principal | solo con `crear_indice=True` (D9) |
| **Descomprimir** | ✅ | **Sistema de archivos** (temporal + salto de carpetas ya completas) | destino | salvo `sobrescribir` |
| **Descombinar** | ✅ | **Sistema de archivos** (salta `dest.exists()`); mapeo del índice de Combinar | destino | salvo `sobrescribir` |
| **Eliminar** | ✅ (trivial) | **Sistema de archivos** (borrado idempotente: relanzar borra lo que quede) | carpeta | nada que "reanudar" |
| **Aplanar** | ⚠️ **No fiable** | sin registro | — | ver §2 |
| **Desaplanar** | ⚠️ **No fiable** | sin registro | — | ver §2 |

**Conclusión**: la visión del usuario ("un JSON en el destino, al iniciar con el mismo
origen/destino se comprueba para reanudar") es **exactamente lo que ya hacen Comprimir
y Combinar**. El molde está probado; falta (a) hacerlo **visible y uniforme** y (b)
llevarlo a **Aplanar/Desaplanar**.

---

## 2. El hueco: Aplanar / Desaplanar

No generan **ningún registro de progreso**. Al relanzar la misma tarea, el resultado
depende de la **política de conflicto**, y el **caso por defecto es el peligroso**:

- **`renombrar` (por defecto)**: cada archivo ya copiado **existe** en el destino →
  se trata como colisión → se **duplica** con sufijo (`a_n2.txt`, luego `a_n2_2.txt`…).
  ❌ Reanudar corrompe el resultado.
- **`mantener`**: los ya copiados se saltan, los que faltaban se copian → **de hecho
  reanuda bien** (por FS), pero sin informar el progreso previo.
- **`reemplazar`**: recopia lo ya hecho (trabajo desperdiciado), sin duplicar.

Para reanudar **con cualquier política** (incluida la de por defecto) hace falta un
**registro persistente** que recuerde qué unidades de origen ya se procesaron y **con
qué nombre de destino** (para no re-renombrar).

---

## 3. Diseño del registro de progreso (compartido)

Se propone un helper **compartido en `comun`** (`comun.RegistroReanudable`, nombre a
decidir) para no repetir un tercer formato ad-hoc, y para poder unificar la detección
en la GUI. Un motor que mapea unidades de origen a salidas lo usa así:

**Formato** (JSON en el **destino**, escritura atómica `.part`+`os.replace`):
```
{ "formato": "kakoli-reanudable/1",
  "tarea": "aplanar",                       // qué motor lo escribió
  "creado": "<ISO>", "actualizado": "<ISO>",
  "origen": "<ruta absoluta del origen>",   // valida el proyecto
  "firma": { "modo_nombre": "ruta", "separador": "-", "conflicto": "renombrar",
             "criterio_reemplazo": "..." }, // opciones que afectan al RESULTADO
  "hechos": { "<rel_origen>": "<nombre/rel_destino asignado>" },
  "descartados": [ ... ] }                   // informativo (mantener/reemplazar)
```

**Contrato del helper**:
- `cargar(destino, origen, firma) -> Registro|None`: lee el JSON; **valida** que
  `origen` y `firma` coinciden (si no, devuelve None → empezar de cero con aviso).
- `procesados() -> set[str]`: claves de `hechos` (para saltar, como `_procesados` de
  Combinar).
- `anota(unidad, salida)` / `descarta(unidad, motivo)`: bajo cerrojo (`ilock`), como
  Combinar; vuelca a disco cada `PASO_REGISTRO`.
- `completar()`: vuelca y (según R4) **borra** el JSON al terminar bien.

**Reutiliza el patrón ya probado en Combinar** (`_procesados`, `ilock`, volcado
periódico, escritura atómica). No inventa nada nuevo de concurrencia.

---

## 4. Detección y visibilidad en la GUI (meta 1)

Se añade al **contrato de motor** una función opcional:
`info_reanudable(entradas, opts) -> dict|None` → si hay un registro pendiente para ese
origen/destino/firma, devuelve `{"fecha":…, "hechas":N, "total":M}`; si no, None. Los
motores sin reanudación no la definen.

En `PestanaBase._iniciar` (antes de lanzar el hilo, tras `_validar`): si
`self.MOTOR.info_reanudable(...)` devuelve algo, se muestra un **modal uniforme**:

> "Se encontró una tarea a medias del *<fecha>* (*N* de *M* hechas).
> ¿**Continuar** donde se quedó o **empezar de cero**?"

Según la respuesta se fija un flag `reiniciar` en `opts`. Así **toda** tarea con
registro (Comprimir, Combinar, Aplanar, Desaplanar) reanuda de forma **visible y
uniforme**, en vez de en silencio. (Descomprimir/Descombinar/Eliminar siguen con su
salto por FS; ver R7.)

Es una ampliación **aditiva** del contrato (como `produce`/`produce_hacia`): la base la
usa si existe, y no rompe a los motores que no la implementan.

---

## 5. Decisiones a resolver (antes de la Fase 0)

- **R1 — ¿Automático o preguntar?** Propuesta: **preguntar** (modal Continuar / Empezar
  de cero). Es lo que pide el enunciado ("comprueba el json para poder reanudar") y
  evita reanudaciones sorpresa. (Hoy Comprimir reanuda en silencio.)
- **R2 — ¿Registro compartido en `comun` o bespoke por motor?** Propuesta: **compartido**
  (`comun.RegistroReanudable`), para no crear un tercer formato y unificar la detección.
- **R3 — ¿Migrar Comprimir/Combinar al helper compartido?** Propuesta: **no** (funcionan;
  no arriesgar). Solo se les añade `info_reanudable` leyendo su JSON actual. El helper
  nuevo lo usan Aplanar/Desaplanar.
- **R4 — ¿Borrar el JSON al completar?** Propuesta: **sí** en Aplanar/Desaplanar (es
  solo para reanudar; deja la salida limpia). Combinar **conserva** su índice porque
  Descombinar lo necesita — son cosas distintas.
- **R5 — Firma que invalida un registro:** origen distinto, o cambio de `modo_nombre` /
  `separador` / `conflicto` / `criterio_reemplazo` (todo lo que altera el nombre de
  salida) → se descarta el registro y se empieza de cero **con aviso**.
- **R6 — Dónde vive el JSON:** en el **destino**. Debe **excluirse** del recorrido y del
  resultado: Desaplanar ya recorre el destino como origen, así que hay que saltar
  `.kakoli_aplanado.json`/`.kakoli_desaplanado.json` en `_walk_archivos` (como Combinar
  excluye su índice en `_walk_rel`).
- **R7 — Alcance del prompt:** solo tareas con **registro JSON** (Comprimir, Combinar,
  Aplanar, Desaplanar), donde saber "cuánto falta" es barato. Descomprimir/Descombinar/
  Eliminar mantienen su salto por FS sin prompt (informar su progreso exigiría escanear
  el destino). *(¿de acuerdo, o se quiere prompt también ahí?)*
- **R8 — ¿Registro opcional en Aplanar (tipo D9)?** El registro es pequeño; propuesta:
  **siempre activo**, con posible casilla "no registrar progreso" para quien priorice
  velocidad/limpieza y no vaya a reanudar (avisando que entonces no será reanudable).

---

## 6. Fases

- **Fase 0 — Registro compartido en `comun`.** `comun.RegistroReanudable`: formato
  (§3), `cargar`+validación (origen+firma), `procesados()`, `anota`/`descarta` con
  `ilock` y volcado cada `PASO_REGISTRO`, `completar()` (con borrado según R4),
  escritura atómica. Tests unitarios (crear/volcar/cargar/validar/compactar). No toca
  ningún motor todavía.
  **ESTADO: HECHA** (2026-09-07). Clase `comun.RegistroReanudable` (+ constante
  `REANUDABLE_FORMATO="kakoli-reanudable/1"`; comun importa `json`/`os`/`threading`):
  `cargar(ruta, tarea, origen, firma, *, reiniciar=False, log)` (empieza de cero si
  reiniciar, o si no coincide formato/tarea/origen/firma → aviso); `inspeccionar(...)
  ->{"fecha","hechas"}|None` (peek sin construir, base de `info_reanudable`);
  `procesados()->set`; `anota(unidad,salida)`/`descarta(unidad,motivo)` bajo cerrojo
  interno con volcado automático cada `PASO_REGISTRO`; `guardar()`; `completar(*,
  borrar=True)` (borra el JSON al terminar bien, R4); `_volcar` atómico (`.part`+
  `os.replace`). Verificado test_reanudable (20/20): vacío/recarga preserva hechos+
  salidas+descartados; inspeccionar con progreso válido; firma/origen/tarea distintos →
  de cero; reiniciar borra; volcado automático a los `PASO_REGISTRO`; `completar`
  borra/conserva; **concurrencia** 8 hilos × 50 = 400 sin pérdidas; JSON corrupto →
  de cero. Regresión (comun re-exportado): imports + test_combinar/aplanar/cd/menu OK.
  Ningún motor tocado.
- **Fase 1 — Detección uniforme + prompt (visibilidad, meta 1).** Añadir
  `info_reanudable(entradas, opts) -> dict|None` al contrato; implementarla para
  **Comprimir** (lee `_estado_zip.jsonl`) y **Combinar** (lee `.kakoli_combinacion.json`).
  `PestanaBase._iniciar` muestra el modal Continuar/Empezar de cero y fija `reiniciar`.
  Verificar que Comprimir/Combinar ahora **preguntan** en vez de reanudar en silencio,
  sin romper el round-trip.
  **ESTADO: HECHA** (2026-09-07). Contrato + modal genérico implementados:
  `PestanaBase._preguntar_reanudar(datos)` llama a `self.MOTOR.info_reanudable(...)` (si
  existe) y, si hay progreso, muestra `messagebox.askyesnocancel` (**Sí=Continuar /
  No=Empezar de cero / Cancelar**); `_iniciar` lo consulta y fija `datos["opts"].reiniciar`.
  `motor_comprimir.info_reanudable`: señal **barata y correcta** — existe el estado con
  carpetas hechas Y el **ZIP final (`salida/<raiz>.zip`, que se crea al terminar) NO
  existe** (si existe → completado → None); valida `raiz` en la cabecera; fecha = mtime
  del estado. **Ajuste de UX/integración**: `PestanaBase._reanudando_en_sesion` (True
  cuando `_fin` recibe "pausado") hace que **"Continuar" en la MISMA sesión NO muestre
  el modal** (el usuario acaba de pausar); el modal es solo para reanudar **tras cerrar
  la app**. Verificado test_reanudar_gui (10/10) + regresión completa (incluido
  test_func_pausa, que pausa+continúa comprimir sin colgarse). **DESVIACIÓN — Combinar
  NO recibe el modal** (queda reanudando en silencio como antes): su fusión es **in
  situ**, su índice **debe conservarse** (lo necesita Descombinar) y no tiene flag
  `reiniciar`, así que "empezar de cero" **re-duplicaría** los archivos ya fundidos
  (inseguro). Se dejó igual (correcto: re-lanzar es idempotente por `_procesados`).
  **DECIDIDO por el usuario (2026-09-07): opción (a) — Combinar se queda como está**
  (reanudación silenciosa, sin modal ni reiniciar). No se añade prompt.
- **Fase 2 — Aplanar reanudable (meta 2).** `motor_aplanar` adopta el registro
  compartido (`.kakoli_aplanado.json` en el destino): registra `rel_origen →
  nombre_destino`, salta procesados, valida firma, serializa la escritura (ya hay
  `ilock`/`_lock_nombre`), borra el JSON al completar. `info_reanudable`. Tests: pausar
  a mitad → "cerrar" (descartar el motor) → relanzar con mismos paths → completa **sin
  duplicados ni pérdidas** con renombrar/mantener/reemplazar; cambiar `separador`/`modo`
  invalida el registro (empieza de cero con aviso).
  **ESTADO: HECHA** (2026-09-07). `motor_aplanar`: `Opciones.reiniciar`; `_firma(opts)`
  (modo/separador/conflicto/criterio/ocultos/enlaces); `info_reanudable(entradas,opts)`
  vía `RegistroReanudable.inspeccionar(destino/.kakoli_aplanado.json, "aplanar", origen,
  firma)`. `procesar`: crea el registro (`REGISTRO_NOMBRE=".kakoli_aplanado.json"`,
  `TAREA="aplanar"`), `items = [rel not in procesados]`, cada worker **anota** lo que
  ESCRIBIÓ (copiado/renombrado/reemplazar-gana → nombre real) o **descarta** lo no
  escrito (mantener/reemplazar-perdedor); errores NO se marcan (se reintentan). Al
  **pausar** o con errores → `guardar()`; al **completar sin errores** → `completar(
  borrar=True)` (registro borrado, salida limpia, R4). **`reiniciar`**: antes de empezar,
  borra del destino los ficheros que el registro dice que escribimos (undo preciso) y
  arranca de cero — evita duplicar. CLI: `--reiniciar`. La GUI **no** cambió: el modal
  genérico (Fase 1) ya llama a `info_reanudable`. Verificado test_aplanar_reanudar
  (18/18): pausa→reanuda byte a byte (modo ruta), colisiones modo final renombrar SIN
  duplicados (multiset idéntico a un aplanado de una vez), `reiniciar` deja resultado
  limpio, firma distinta → None; test_reanudar_gui (13/13, el modal se activa para
  Aplanar con registro a medias). bench `--flatten` y toda la suite de aplanado siguen
  verdes (el registro se borra al completar → no ensucia el round-trip).
- **Fase 3 — Desaplanar reanudable.** Igual (`.kakoli_desaplanado.json`), registrando
  `nombre_plano → rel_reconstruido`. **Excluir** los JSON de reanudación del recorrido
  de `_walk_archivos` (R6) para no reconstruirlos. Tests análogos.
  **ESTADO: HECHA** (2026-09-07). `motor_desaplanar`: `Opciones.reiniciar`; `_firma(opts)`
  (separador/conflicto/omitir_ocultos); `info_reanudable`; `REGISTRO_NOMBRE=
  ".kakoli_desaplanado.json"`, `TAREA="desaplanar"`. **Exclusión (R6)**: `_walk_archivos`
  salta `_EXCLUIR = {".kakoli_desaplanado.json", ".kakoli_aplanado.json"}` (importa el
  nombre de aplanar) — así un registro de aplanar que quedara en la carpeta aplanada (por
  un aplanado pausado) NO se reconstruye. `procesar`: crea el registro en el destino,
  `items = [src no procesado]` (unidad = ruta relativa del fichero plano), cada worker
  **anota** lo reconstruido/reemplazado (→ ruta escrita) o **descarta** los mantenidos;
  pausa/errores → `guardar()`, completa sin errores → `completar(borrar=True)`. `reiniciar`
  borra del destino lo que el registro dice que escribimos + arranca de cero. CLI
  `--reiniciar`. GUI sin cambios (modal genérico). Verificado test_desaplanar_reanudar
  (17/17): pausa→reanuda byte a byte, **exclusión** (un `.kakoli_aplanado.json` +
  `.kakoli_desaplanado.json` en la carpeta aplanada no se reconstruyen; solo los reales),
  `reiniciar` limpio, firma distinta → None. bench `--flatten` (seq y `--hilos 4`) y toda
  la suite de aplanado verdes.
- **Fase 4 — Verificación + docs + bench.** Round-trip con corte a mitad y reanudación
  (secuencial y paralelo) para Aplanar/Desaplanar y para Combinar/Comprimir vía el
  prompt. `bench`: escenario `--reanudar` (procesar la mitad, simular cierre, reanudar,
  comparar byte a byte). Actualizar `ARQUITECTURA.md` (registro en `comun` + contrato
  `info_reanudable`), `GUI.md` (modal de reanudación) y `escalabilidad.md`.
  **ESTADO: HECHA** (2026-09-07). `bench.py`: nuevo modo **`--reanudar`** (`correr_reanudar`):
  aplana la mitad (pausa determinista secuencial) → "cierra" (motor descartado) → reanuda
  con los hilos pedidos → ídem desaplanar → round-trip byte a byte por archivo
  (`_firma_archivos`); `bench --reanudar --todos` = **5/5** secuencial y con `--hilos 4`
  (pausa a la mitad, reanuda y completa en los 5 escenarios). Docs: `ARQUITECTURA.md` §2
  (`RegistroReanudable` en `comun`) y §6 (invariante "Reanudable incluso tras cerrar":
  los tres mecanismos JSON/FS + el contrato `info_reanudable` + el modal); `GUI.md` §7.1
  (modal de reanudación). Verificación cruzada: los 4 modos de bench (compresión/merge/
  flatten/reanudar) y toda la suite (28 tests) verdes.

- **Fase 5 — Unificar el helper de análisis del JSON de reanudación (AMPLIACIÓN).**
  **Objetivo**: que TODAS las tareas compatibles con reanudar a partir del JSON usen el
  MISMO helper para analizar el JSON y detectar el progreso pendiente (fecha + nº hechas
  + "¿queda algo?"), en vez de código a medida por motor. Nota de rutas: tras la
  reorganización, el helper vive en `nucleo.comun.RegistroReanudable` y los motores en
  `motores/`.
  - **Estado actual (por qué la fase):**
    - `nucleo.comun.RegistroReanudable.inspeccionar(ruta, tarea, origen, firma) ->
      {"fecha","hechas"}|None` es el analizador canónico. Lo usan **Aplanar/Desaplanar**
      (su `info_reanudable` es un wrapper de una línea).
    - **Comprimir NO lo usa**: su `info_reanudable` lee a mano el `_estado_zip.jsonl`
      (cabecera + cuenta de carpetas + comprobación de que el ZIP final aún no existe).
      Formato propio (JSONL con cabecera y una línea por carpeta).
    - **Combinar** tiene índice JSON pero no expone `info_reanudable` (opción a: reanuda
      en silencio); quedaría cubierta si algún día se activa su prompt.
    - Las tareas por **sistema de archivos** (Descomprimir/Descombinar/Eliminar) NO tienen
      JSON → fuera de alcance.
  - **Qué NO cambia**: el contrato `info_reanudable(entradas, opts) -> dict|None` y el
    modal de la GUI (`_preguntar_reanudar`) ya son comunes. La unificación es **interna**:
    que cada `info_reanudable` **delegue en el helper común** en vez de construir el dict
    a mano; y no se tocan los **formatos en disco** (R3: no migrar el `Estado` de Comprimir
    ni el índice de Combinar).
  - **Decisiones a resolver (al implementar):**
    - **U1 — ¿Migrar Comprimir al formato de `RegistroReanudable`, o generalizar el
      helper?** Propuesta: **generalizar el helper** (no migrar formatos, R3). P. ej.
      `RegistroReanudable.inspeccionar` acepta un **parser opcional** (un callable que,
      dada la ruta, devuelve `(fecha, nº_hechas)` o None) y una **condición de completado**
      opcional; así Comprimir reutiliza `inspeccionar` pasándole su lector del
      `_estado_zip.jsonl` + la señal del ZIP final. Alternativa: un helper aparte
      `nucleo.comun.resumen_reanudable(fecha, hechas, *, pendiente) -> dict|None` que
      estandariza SOLO la salida y la regla "no None si hay pendiente", y cada motor le da
      los datos crudos de su formato.
    - **U2 — Formato de la firma/validación**: hoy `inspeccionar` valida `origen`+`firma`
      (RegistroReanudable). Comprimir valida `raiz` en su cabecera. Decidir si el helper
      generalizado unifica esa validación (origen) o la delega al parser por formato.
    - **U3 — Alcance**: Comprimir + Aplanar + Desaplanar (y Combinar si se activa). Confirmar.
  - **Verificación**: los `info_reanudable` de Comprimir/Aplanar/Desaplanar producen el
    mismo tipo de resultado por el **mismo camino** (un solo punto que analiza el JSON);
    el modal se comporta igual; suite verde; **sin cambiar los formatos en disco**.
  - **Riesgo**: no romper la detección de Comprimir (su señal de "completado" = el ZIP
    final ya existe es específica); el helper generalizado debe permitir esa condición.
  - **ESTADO: HECHA** (2026-09-11). **U1 resuelta: generalizar el helper** (no migrar
    formatos, R3). `nucleo.comun.RegistroReanudable.inspeccionar(ruta, tarea=None,
    origen=None, firma=None, *, leer=None)` es ahora el **punto ÚNICO de análisis**: sin
    `leer` lee el formato RegistroReanudable (valida formato/tarea/origen/firma, camino de
    Aplanar/Desaplanar, sin cambios); con `leer` (callable `Path -> (fecha, hechas)|None`)
    se adapta a otros formatos, aplicando la MISMA regla común (`hechas>0` → `{"fecha",
    "hechas"}`, si no None). `motor_comprimir.info_reanudable` pasa a **enrutar por
    `inspeccionar`**: comprueba aparte su señal de completado (el ZIP final existe → None,
    U2: validación de origen delegada al lector, que valida `raiz` en la cabecera del
    `_estado_zip.jsonl`) y le pasa un `leer` que cuenta las carpetas hechas. **U3**:
    alcance Comprimir + Aplanar + Desaplanar (Combinar sigue silencioso, opción a). NO se
    tocaron los formatos en disco. Verificado: test_reanudable (helper, camino por
    defecto intacto), test_reanudar_gui (Comprimir por el modal: sin estado→None, a
    medias→hechas, ZIP final→None, otra raíz→None), test_aplanar/desaplanar_reanudar +
    suite completa + 4 bench.

---

## ROADMAP DE REANUDACIÓN — COMPLETO (fases 0–5)

Reanudar tras cerrar el programa, comprobando el JSON de progreso. Infra compartida
`comun.RegistroReanudable` (Fase 0); contrato `info_reanudable` + modal Continuar/
Empezar-de-cero en `PestanaBase._iniciar`, con Comprimir vía su `_estado_zip.jsonl`
(Fase 1); **Aplanar** y **Desaplanar** reanudables con `.kakoli_aplanado.json` /
`.kakoli_desaplanado.json` (Fases 2–3, con exclusión de los registros del recorrido);
`bench --reanudar` + docs (Fase 4). **Combinar** queda reanudando en silencio (decisión
del usuario, opción a: su fusión in-situ hace inseguro "empezar de cero").

**Fase 5 (PENDIENTE, ampliación)**: unificar el helper de análisis del JSON de
reanudación para que TODAS las tareas con registro JSON (Comprimir, Aplanar, Desaplanar,
y Combinar si se activa) detecten el progreso pendiente por el MISMO camino, en vez de
código a medida por motor — sin cambiar los formatos en disco (R3).

Orden recomendado: 0 → 1 → 2 → 3 → 4 (infra y visibilidad de lo existente antes de
extender a las tareas nuevas); la Fase 5 es una ampliación posterior.

---

## 7. Riesgos y notas

- **El JSON contamina el destino** (sobre todo en Aplanar, cuya salida "debe ser
  limpia"): mitigado por **borrado al completar** (R4) + **exclusión** del recorrido/
  resultado (R6). Un destino ya completado no tiene JSON; solo lo tiene uno a medias.
- **Cambiar opciones a mitad** produce resultados inconsistentes: la **firma** (R5) lo
  detecta y fuerza empezar de cero con aviso.
- **Concurrencia**: la escritura del registro va bajo `ilock` y se vuelca cada
  `PASO_REGISTRO`, exactamente como en Combinar (ya validado en paralelo). El bug de
  `_destino_seguro` (resuelto en `roadmap_aplanar.md` Fase 5) recuerda: **validar la
  reanudación comparando recuentos + firma completa, no solo contenido**.
- **Descomprimir/Descombinar/Eliminar** reanudan por FS pero no informan progreso
  barato: quedan fuera del prompt (R7); su comportamiento actual no cambia.
- **Cambio de comportamiento en Comprimir** (hoy reanuda en silencio → pasaría a
  preguntar): es intencionado (meta 1, visibilidad), pero conviene confirmarlo (R1).
- **No romper lo que funciona**: R3 deja Comprimir/Combinar con su formato actual; el
  helper compartido es nuevo y solo lo estrenan Aplanar/Desaplanar. Cero cambios en
  `recursos`/`paralelo` ni en el modelo hilo+cola+bomba de la GUI.
