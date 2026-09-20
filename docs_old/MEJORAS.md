# Mejoras de kakoli — catálogo y roadmap por fases

Documento de especificación para ejecutar mejoras sobre el `core/` y las `tasks/`
**ya reestructuradas** (ver `REESTRUCTURACION.md`, fases 0–14 completas). No es una
reestructuración: la arquitectura `core ← gui ← tasks ← kakoli.py` se mantiene; aquí
se pulen deuda técnica, duplicación y barandillas.

Fecha del análisis: 2026-09-17. Origen: lectura del código real + `pyflakes` sobre
`core gui tasks kakoli.py`.

**Leyenda de etiquetas:**
- **[H]** hecho observado (con evidencia en el código).
- **[R]** recomendación.
- **[D]** decisión que requiere confirmación del usuario.

**Reglas de ejecución (heredadas de la reestructuración):**
- Intérprete `./.venv/Scripts/python.exe`; código compatible con Python 3.11.
- Nunca editar `.py` UTF-8 con `Get/Set-Content` de PowerShell (usar Edit/Write/sed o scripts Python).
- Un commit al cierre de cada fase, directamente en `main`.
- No mezclar limpieza mecánica con cambios de lógica en la misma fase.
- Cada fase deja la suite verde (`pytest`) y no aumenta la deuda de `pyflakes`.

---

## 0. Estado de ejecución

| Fase | Nombre | Estado |
|---|---|---|
| 0 | Limpieza mecánica y trinquete de imports | **HECHA** (2026-09-17) |
| 1 | Contrato explícito y test de conformidad | **HECHA** (2026-09-17) |
| 2 | Estado reanudable unificado en el core (JSON de pausa/reanudación) | **HECHA** (2026-09-17) |
| 3 | Cancelar: contrato, ejecución y limpieza (núcleo + motores) | **HECHA** (2026-09-17) |
| 4 | Cancelar: botón y modal en la GUI | **HECHA** (2026-09-17) |
| 5 | Deduplicar la orquestación del bucle de proceso | **HECHA** (2026-09-17) |
| 6 | Reorganizar `core.comun` y `OpcionesBase` | **HECHA** (2026-09-17) |
| 7 | Reorganizar `recursos` y encapsular `paralelo`/`registro` | **HECHA** (2026-09-17) |
| 8 | Partir `comprimir` y retirar andamiaje | **HECHA** (2026-09-17) |

**MEJORAS COMPLETAS (fases 0–8).** Deuda técnica saldada, contrato con red de tests,
función de Cancelar de núcleo a interfaz, y núcleo reorganizado (resultado/opciones/
formato/cli/reanudable/control/recursos·sondas+politica). Suite: 314 passed.

Orden pensado para que cada fase se apoye en la anterior: primero limpiar y poner
barandillas (0–1); luego la **función de Pausar/Cancelar y su recuperación**, que el
usuario ha priorizado (2–4): el estado reanudable centralizado en el core (2) es la
base sobre la que se implementa Cancelar en el núcleo/motores (3) y en la GUI (4);
después el gran deduplicado del bucle de proceso (5) y por último las reorganizaciones
estructurales (6–8), que son las de más superficie.

> **Cambio de alcance (2026-09-17):** el usuario resolvió D-M1 y D-M2 (§3). D-M1 añade
> una función nueva —**Cancelar** junto a Pausar, con limpieza del fragmento a medias y
> recuperación desde el último punto completado— que antes no estaba en el roadmap;
> D-M2 exige **centralizar el JSON de pausa/reanudación en el core** y permite romper la
> compatibilidad. Por eso el roadmap pasó de 6 a 8 fases y las antiguas 3–6 se
> renumeran a 5–8.

---

## 1. Catálogo de mejoras

Cada ítem tiene un id estable (`C#` core, `T#` tareas) que las fases referencian.

### Core

**C1 — `Resultado.estado` es un string libre.** [core/comun.py:76]. Los estados
(`completado | pausado | nada | cancelado | error`) se comparan como literales
dispersos por los 8 motores y por `correr_cli`. Un typo no lo detecta nadie.
→ Enum o constantes; usarlas en todas las comparaciones. **[R]**

**C2 — Dos mecanismos de estado reanudable que hacen lo mismo.**
`RegistroReanudable` (JSON, aplanar/desaplanar) [core/comun.py:131] y la clase
`Estado` JSONL de comprimir [tasks/comprimir/motor.py:329] reimplementan por separado:
escritura atómica `.part`+`os.replace`, volcado por bloques (`PASO_REGISTRO`),
validación de cabecera y compactación. → **Un ÚNICO mecanismo en el core** (D-M2),
que use la escritura del JSON de pausa/reanudación de todas las tareas y sea trivial
de adoptar en tareas futuras. Se rompe la compatibilidad con formatos previos
(D-M2). Base de la función Cancelar (C12/C13). **[H]**

**C3 — `core.comun` es un cajón de sastre.** Reúne formato/tiempo, `Resultado`,
`Interrupcion`, `OpcionesBase`, `RegistroReanudable` y `correr_cli`: cinco
responsabilidades. El docstring aún cita `motor_comprimir` y el "plan de
escalabilidad" (obsoleto tras la Fase 13). → Separar en `resultado.py`, `cli.py`,
`reanudable.py`, `formato.py`. **[H]**

**C4 — `OpcionesBase` deja fuera opciones comunes.** `seguir_enlaces` y
`omitir_ocultos` se redeclaran en cada motor que recorre el árbol, en vez de
heredarse de `OpcionesBase` [core/comun.py:114]. → Subir las opciones de recorrido
de FS a la base compartida. **[H]**

**C5 — `carga_sistema()` es código muerto.** [core/recursos.py:203]. No la llama
nadie (la sustituyó `muestra_carga`). → Eliminar. **[H]**

**C6 — `recursos.py` (855 líneas) mezcla sondas y política.** Sondas de plataforma
(CPU/RAM/disco/energía, `ctypes` Windows + `/proc` Linux) conviven con la política
de hilos y el throttling. → Subpaquete `recursos/` (`sondas.py` vs `politica.py`);
testear la política sin tocar hardware. **[R]**

**C7 — `_Regulador` mete mano en los privados de `Ejecutor`.** Accede a
`self._ejec._cond` y `_activos_max` [core/paralelo.py:219]. → Exponer
`ejec.ajustar_limite(n)` y encapsular. **[H]**

**C8 — `Registro.consumidor_de` reconstruye la lista plana en cada llamada** y
devuelve el primer consumidor sin validar unicidad del artefacto
[core/registro.py:85]. → Precomputar `_por_artefacto` en `__init__` y validar que
ningún artefacto lo consuman dos tareas en silencio. **[H]**

**C9 — El contrato de `DescriptorTarea.clase` es implícito.** Tipada como `object`
[core/registro.py:19]; nada verifica que la fábrica de pestaña acepte lo que la GUI
le pasa. → `Protocol` para la fábrica de UI. **[R]**

**C10 — `Ejecucion` solo pausa, no cancela.** Sin `cancelar()` ni reinicio para
reusar el objeto (`self.hilo` queda colgando) [core/ejecucion.py:27]. → Resuelto por
la función Cancelar: **C12** (núcleo/motores). **[H]**

**C11 — Log sin niveles.** Convención de prefijo `"[!]"` para avisos; clasificar por
prefijo es frágil. → Nivel opcional (info/warn) en el callback. **[R]** *(Evaluado en
la Fase 5 y APLAZADO: cambiaría la firma de `log` en todo el proyecto —motores, GUI,
tests— por poco valor; queda como mejora independiente pendiente.)*

**C12 — Cancelar (núcleo + motores): abortar la unidad en curso, limpiar su fragmento
y dejar el JSON en el último punto completado.** Función NUEVA pedida por el usuario
(D-M1). Semántica: *Pausar* espera a terminar la unidad en curso e incluye esa unidad
en el JSON; *Cancelar* aborta la unidad en curso, borra su fragmento a medias (el
`.part`) y deja el JSON de recuperación en la ÚLTIMA unidad completada (ej.:
cancelando la 2.ª carpeta → 1.ª intacta, 2.ª rehecha al reanudar). En multihilo,
cancelar/pausar debe afectar a TODAS las unidades en TODOS los hilos. Toca
`core.ejecucion` (`pedir_cancelar()` + Event), el contrato de motor (`ejecutar(...,
cancelar=None)`), los 8 motores (chequeo dentro de la unidad) y `core.paralelo`
(abortar en vuelo en todos los workers). **[D→resuelta]**

**C13 — Cancelar (GUI): botón "Cancelar" junto a "Pausar" + modal de aviso.** Antes
de cancelar, un modal advierte de que se descarta la parte en curso y que se podrá
reanudar desde el último punto guardado. Al confirmar, `Ejecucion.pedir_cancelar()`;
el `Resultado("cancelado")` se trata como reanudable (botón "Continuar"). **[D→resuelta]**

### Tareas

**T1 — Imports muertos en 7 de 8 motores.** `pyflakes` sobre el proyecto da ~25
avisos: `signal`, `core.comun`, `leer_marca`, `Interrupcion`, `preguntar_consola`,
`datetime`, `timezone` en comprimir; `Interrupcion`/`preguntar_consola` sin usar en
combinar, descombinar, descomprimir, eliminar; `dataclasses.field` en descomprimir y
eliminar; `ttk`/`gui.tema` en 3 pestañas; `ahora` en [gui/app.py:18]. El trinquete
de la Fase 3 solo cubría nombres indefinidos (F821), no imports sin usar (F401).
→ Limpiar y ampliar el trinquete a F401. **[H]**

**T2 — `perf` calculado y nunca usado en `renombrar`.** [tasks/renombrar/motor.py:188]
mide la máquina (coste real) y descarta el resultado. → Usarlo para decidir hilos o
quitar la medición. **[H]**

**T3 — Orquestación del bucle de proceso duplicada en los 8 motores.** Cada uno
reimplementa el sentinela de archivo `PAUSA` + `pausa_ruta.exists()`, `max_dirs`
("límite de N"), `preguntar_cada` ("preguntar cada N") y la pausa del usuario. Es
lógica genérica, no de dominio. → Helper en `core` (o ampliar el `Ejecutor`) que
reciba plan + estas políticas. Es la mayor copia-pega entre tareas. **[H]**

**T4 — `info_reanudable` casi idéntico en cada tarea reanudable.** Abrir estado,
validar cabecera, contar hechas, devolver `{fecha, hechas}`; el de comprimir son
~50 líneas [tasks/comprimir/motor.py:150]. → Helper parametrizado por "lector de
estado" (ya existe `RegistroReanudable.inspeccionar`; falta que comprimir/
descomprimir lo aprovechen del todo). **[H]**

**T5 — `comprimir/motor.py` son 1071 líneas** — el módulo más grande; mezcla
exploración, agrupado (mejora 5), estado JSONL, planificador, compresor, motor y
CLI. → Partir dentro del paquete vertical (`explorar.py`, `estado.py`,
`planificador.py`, `cli.py`). **[R]**

**T6 — Comentarios/marcadores históricos que hoy mienten.**
[tasks/comprimir/motor.py:300]: el docstring de `seleccionar_agrupados` dice "lo que
falta es el empaquetado en sí (Comprimidor.crear_agrupado)", pero `crear_agrupado`
está implementado (línea 638). Además marcadores "Mejora 5 (preparado)", "Fase 4",
"roadmap_reanudar.md", "plan de escalabilidad" y el bloque 74–76 sobre re-export de
`motor_comprimir` (eliminado en Fase 13). → Auditar qué está realmente activo
(¿modo compacto alcanzable y testeado?) y limpiar la narrativa de fases. **[H]**

**T7 — Falta un test de conformidad del contrato sobre el REGISTRO.** Un test
parametrizado sobre `tasks.REGISTRO` que verifique, por descriptor: `ejecutar` con la
firma correcta, `Opciones` subclase de `OpcionesBase`, `main` vía `correr_cli` y (si
aplica) `info_reanudable`. Hoy una tarea nueva que rompa el contrato no se detecta
hasta la GUI. **[R]**

**T8 — Claves de `entradas` sin estandarizar.** El dict varía por tarea:
`origen`/`destino`, `principal`/`fuentes`, solo `origen`… La GUI debe conocer cada
convención. → Documentar/validar las claves esperadas contra el descriptor. **[H]**

**T9 — La indirección de tests `tests/soporte/modulos.py` ya cumplió su función.**
Existía para sobrevivir a los `git mv`. Estable la estructura, los tests pueden
importar `tasks.*` directamente y quitar la capa. **[R]**

**T10 — Migración de formato antiguo `_estado_zip.json` → `.jsonl`.**
[tasks/comprimir/motor.py:394]: compatibilidad que quizá ya no tenga usuarios.
Candidata a retirar. **[R]**

**T11 — `except Exception → Resultado("error", str(e))` pierde el traceback**
(p. ej. [tasks/comprimir/motor.py:964]). → Registrar el traceback a nivel debug sin
cambiar el comportamiento visible. **[R]**

---

## 2. Roadmap por fases

Formato de cada fase: **objetivo**, **incluye** (ids), **criterio de hecho**,
**riesgo** y **commit** sugerido.

### Fase 0 — Limpieza mecánica y trinquete de imports
- **Objetivo:** borrar deuda medible sin tocar comportamiento.
- **Incluye:** T1 (imports muertos), C5 (`carga_sistema` muerta), T2 (`perf` sin usar
  en renombrar — solo la línea muerta, sin rediseñar hilos), T6 (comentarios
  obsoletos), y ampliar el trinquete de `pyflakes` a F401 (imports sin usar) en la
  suite/CI.
- **Criterio de hecho:** `pyflakes core gui tasks kakoli.py` sin avisos; el test de
  trinquete falla si se reintroduce un import muerto; suite verde.
- **Riesgo:** mínimo (borrados y comentarios). Verificar que ningún import "muerto"
  fuera re-exportado y usado desde fuera (grep antes de borrar).
- **Commit:** `chore: Fase 0 mejoras — limpieza de imports muertos y trinquete F401`.

> **ESTADO: HECHA (2026-09-17).**
> - **T1** — retirados los imports muertos de 7 motores + `gui/app.py` (`signal`,
>   `datetime`/`timezone`, `field`, `Interrupcion`, `preguntar_consola`, `humano`,
>   `leer_marca`, `from core import comun`, `ahora`, `ttk`, `gui.tema`).
> - **C5** — eliminado el clúster muerto `carga_sistema` + `_uso_cpu_total` de
>   `core/recursos.py` (solo se usaban entre sí; `_tiempos_cpu` se conserva).
> - **T2** — `tasks/renombrar/motor.py`: se conserva la llamada a `recursos.preparar`
>   (efecto: log del perfil + modo ligero) pero sin asignar el retorno inútil `perf`.
> - **T6** — corregido el docstring que mentía en `seleccionar_agrupados`
>   ("falta el empaquetado" → ya implementado), retirado el comentario obsoleto sobre
>   re-export de `motor_comprimir`, y quitado el marcador "(preparado)" de la mejora 5.
> - **Trinquete** — `tests/test_pyflakes_baseline.py` reescrito: corregido su propio
>   fallo (escaneaba `motores`/`clases`, eliminadas, y no cubría `tasks/`) y ampliado a
>   estricto (F401/F811/F841 además de nombres indefinidos): pyflakes debe dar salida
>   vacía sobre `core gui tasks kakoli.py`.
> - **Verificación:** `pyflakes` limpio; **241 passed**; los 8 motores, sus pestañas, el
>   manifiesto y `gui.app` importan; CLIs y `kakoli --version` OK.

### Fase 1 — Contrato explícito y test de conformidad
- **Objetivo:** poner barandillas antes de refactorizar; que el contrato de tarea sea
  verificable.
- **Incluye:** C1 (Enum/constantes de `estado`), T7 (test de conformidad sobre
  `REGISTRO`), C9 (`Protocol` de la fábrica de UI), T8 (documentar/validar claves de
  `entradas`).
- **Criterio de hecho:** el test de conformidad recorre `REGISTRO` y pasa para las 8
  tareas; introducir una tarea que viole el contrato lo hace fallar; las
  comparaciones de estado usan la constante, no el literal.
- **Riesgo:** bajo. C1 toca muchos sitios pero es mecánico (buscar literales).
- **Commit:** `feat: Fase 1 mejoras — estado tipado y test de conformidad del contrato`.

> **ESTADO: HECHA (2026-09-17).**
> - **C1** — `core/comun.py`: `EstadoResultado(str, Enum)` con las 5 constantes +
>   `ESTADOS_VALIDOS`; `Resultado.__post_init__` valida el estado (un typo lanza
>   `ValueError` en el acto). Al heredar de `str`, `Resultado("error")` y las
>   comparaciones antiguas siguen valiendo. Migrados a la constante los sitios de
>   comparación: `correr_cli`, `gui/pestana_base._fin` + handoff, y las 3 pestañas de
>   tarea (comprimir/descomprimir/eliminar).
> - **C9** — `core/registro.py`: `FabricaPestana(Protocol, runtime_checkable)` que
>   documenta el contrato mínimo de la clase de pestaña (`nombre`, `procesar_cola`,
>   `ocupada`, `pedir_cierre`, `establecer_origen`); `DescriptorTarea.clase` pasa a
>   anotarse `type`. Estructural: el núcleo sigue sin importar Tkinter.
> - **T7** — nuevo `tests/test_conformidad_tareas.py`: parametrizado sobre
>   `REGISTRO`, Tk-free (solo inspección de clases). Verifica por tarea: firma de
>   `ejecutar` (`entradas`, `opts`, callbacks keyword-only), `Opciones` subclase de
>   `OpcionesBase` e instanciable, `main` presente, firma de `info_reanudable` si
>   existe, la pestaña cumple `FabricaPestana`, ids únicos y handoff coherente
>   (`consume` con su `produce`). **34 casos.**
> - **T8** — comprobado que los 8 motores ya documentan sus claves de `entradas` en el
>   docstring de `ejecutar`; fijada la convención en `ARQUITECTURA.md` (claves
>   definidas por tarea; el docstring del motor es la fuente de verdad y debe casar con
>   el `_validar()` de la pestaña). La parte uniforme (callbacks) la impone ahora el
>   test de conformidad.
> - **Docs** — `ARQUITECTURA.md`: contrato de motor actualizado (claves de `entradas`,
>   `EstadoResultado`, `FabricaPestana`).
> - **Verificación:** pyflakes limpio; **274 passed, 1 skipped** (skip = 2.º-root de Tk,
>   intermitente); la validación de estado caza un typo y mantiene la equivalencia
>   str/enum.

### Fase 2 — Estado reanudable unificado en el core (JSON de pausa/reanudación)
- **Objetivo:** un ÚNICO mecanismo de estado reanudable, en el core, que usen todas
  las tareas y sea trivial de adoptar en tareas futuras (D-M2). Es la BASE sobre la
  que se implementa Cancelar (Fases 3–4).
- **Incluye:** C2 (primitiva única en `core` —p. ej. `core/reanudable.py`—: escritor
  atómico `.part`+`os.replace`, cabecera con validación origen/firma, volcado por
  bloques `PASO_REGISTRO`, compactación, `inspeccionar()` para el modal; reemplaza
  `RegistroReanudable` y el `Estado` JSONL de comprimir), T4 (`info_reanudable` sobre
  el helper común). **Se rompe la compatibilidad** con formatos previos (D-M2): se
  adelanta **T10** (fuera la migración `_estado_zip.json`) y cualquier lectura legacy.
- **Punto de escritura común:** una API que centralice "marca unidad hecha / vuelca /
  cierra"; Pausar y Cancelar (Fase 3) escriben el JSON de recuperación por aquí.
- **Criterio de hecho:** las 4 tareas reanudables (comprimir/descomprimir/aplanar/
  desaplanar) usan la MISMA primitiva; pares round-trip (`bench.py` + tests) byte-a-
  byte OK; reanudación probada (cortar y relanzar) en comprimir y aplanar; sin restos
  de formato antiguo; suite verde.
- **Riesgo:** medio-alto (toca persistencia de 4 tareas). Mitiga: break-compat
  permitido (menos casos) y tests de reanudación por tarea.
- **Commit:** `refactor: Fase 2 mejoras — estado reanudable unificado en core`.

> **ESTADO: HECHA (2026-09-17).**
> - **C2** — nuevo `core/reanudable.py` con `RegistroReanudable` ÚNICO: JSONL
>   append-only (O(1) por unidad), cabecera validada (formato/tarea/origen/firma),
>   volcado por bloques (`PASO_REGISTRO`), compactación atómica (`.part`+`os.replace`),
>   `inspeccionar()` para el modal, y API `marca/anota/descarta/error/guardar/cerrar/
>   completar`. Seguro entre hilos. 10 tests nuevos (`tests/core/test_reanudable.py`).
> - **Migración** — Aplanar y Desaplanar pasan del antiguo `comun.RegistroReanudable`
>   (instantánea JSON, O(n) por volcado) al nuevo (import + `.hechos` ahora dict).
>   Comprimir: su clase `Estado` pasa a ser **subclase** de `RegistroReanudable`,
>   conservando la lógica de dominio (`completado` por ancestros + recomprobación en
>   disco); reanudación probada a mano (pausa por límite → estado → reanudar → ZIP
>   final; `info_reanudable` detecta y luego None).
> - **Break-compat (D-M2)** — retirado `comun.RegistroReanudable` (formato instantánea
>   `kakoli-reanudable/1`), la migración `_estado_zip.json` → `.jsonl` y el formato
>   `zip-anidado-estado/2`. Formato único nuevo: `kakoli-reanudable/2`. **Adelanta T10.**
> - **T4** — los tres `info_reanudable` (comprimir/aplanar/desaplanar) delegan ya en el
>   `RegistroReanudable.inspeccionar` común; se eliminó el lector a medida de comprimir.
> - **Verificación:** `pyflakes` limpio; **281 passed, 1 skipped**; `bench.py` round-trip
>   byte-a-byte OK; reanudación de comprimir y pares aplanado/comprimido en verde.
>
> *(T10 queda hecho aquí; en la Fase 8 ya no hay que retirar la migración.)*

### Fase 3 — Cancelar: contrato, ejecución y limpieza (núcleo + motores)
- **Objetivo:** implementar la CANCELACIÓN (D-M1) en el núcleo y los 8 motores, aún
  sin GUI.
- **Semántica (D-M1):** *Cancelar* aborta la unidad EN CURSO (no espera a que
  termine), borra su fragmento a medias (el `.part` de esa unidad) y deja el JSON de
  recuperación en la ÚLTIMA unidad completada. *Pausar* (actual) espera a terminar la
  unidad en curso e incluye esa unidad en el JSON. En multihilo, cancelar/pausar
  afecta a TODAS las unidades en TODOS los hilos.
- **Incluye:** C10 + C12 —
  - `core.ejecucion.Ejecucion`: `pedir_cancelar()` + `cancelar` (Event) expuesto al
    trabajo; limpiar `self.hilo` colgante y permitir reusar el objeto.
  - Contrato de motor: `ejecutar(..., cancelar=None)` (callback keyword-only, como
    `pausar`); los 8 motores lo enhebran a `procesar`. **Actualizar el test de
    conformidad (T7)** para exigir `cancelar`.
  - `procesar` de cada motor: comprobar `cancelar()` DENTRO de la unidad (p. ej. entre
    archivos de una carpeta) y abortarla; el `.part` ya se borra en el `except`, así
    que el fragmento desaparece y la unidad NO se marca → el JSON queda en la anterior.
    Devuelve `Resultado("cancelado")` conservando el estado (reanudable).
  - `core.paralelo.Ejecutor`: ruta de cancelación que (a) deja de repartir y (b) hace
    abortar la unidad en vuelo de TODOS los workers (señal compartida), con parada
    limpia del regulador.
- **Criterio de hecho:** en secuencial y en paralelo, cancelar a mitad de una unidad
  deja el fragmento borrado y el resto intacto; relanzar continúa desde la última
  unidad completada; **test nuevo** que lo verifica (cancelar comprimiendo la 2.ª
  carpeta → 1.ª intacta, 2.ª rehecha). Pausar se comporta igual que hoy. Suite verde.
- **Riesgo:** alto — corazón de la ejecución + los 8 motores. Mitiga: T7 (contrato) y
  tests de pausa/reanudación existentes + nuevos de cancelación por motor.
- **Commit:** `feat: Fase 3 mejoras — cancelación con limpieza y recuperación (núcleo + motores)`.

> **ESTADO: HECHA (2026-09-17).**
> - **Núcleo** — `core.comun.Cancelado` (excepción de parada limpia); `Ejecucion`:
>   `cancela` (Event) + `pedir_cancelar()`, el trabajo recibe `cancelar` y el objeto se
>   reinicia entre runs (C10). `paralelo.Ejecutor.ejecutar(..., cancelar=)`: los workers
>   dejan de tomar unidades y un `Cancelado` de cualquier worker es parada LIMPIA (no
>   error) que para a TODOS los hilos; devuelve `"cancelado"`.
> - **Contrato (C12)** — `ejecutar(..., cancelar=None)` keyword-only en los 8 motores;
>   `pestana_base` pasa `cancelar=self._ejec.cancela.is_set`; **T7 exige `cancelar`**.
> - **Motores** — cancelación en la frontera de unidad en los 8 (retornan `"cancelado"`,
>   reanudable). Comprimir además aborta la carpeta EN CURSO **intra-unidad**
>   (`Comprimidor.crear`/`crear_agrupado` comprueban `cancelar()` y lanzan `Cancelado`;
>   el `.part` se descarta en el `except`), dejando el progreso en la carpeta anterior.
> - **Semántica cumplida (D-M1)** — Pausar espera a terminar la unidad; Cancelar la
>   aborta y descarta su fragmento; el JSON de recuperación queda en la última unidad
>   completada; en paralelo afecta a todos los hilos.
> - **Tests** — `test_ejecucion` (cancelación cooperativa), `test_paralelo` (cancelar
>   desde el inicio + `Cancelado` como parada limpia), `tests/tasks/comprimir/
>   test_cancelar.py` (crear borra el fragmento; procesar cancelado es reanudable).
>   Smoke en paralelo: cancelar 8 carpetas a la vez deja 0 `.part` y reanuda a completo.
> - **Verificación:** pyflakes limpio; **287 passed**.
>
> *(La GUI —botón Cancelar + modal— es la Fase 4; aquí solo el núcleo/motores.)*

### Fase 4 — Cancelar: botón y modal en la GUI
- **Objetivo:** exponer Cancelar en la interfaz con confirmación.
- **Incluye:** C13 —
  - `PestanaBase`: botón "Cancelar" junto a "Pausar"; `_cancelar()` muestra un modal
    de aviso ("Se descartará la parte en curso; podrás reanudar desde el último punto
    guardado. ¿Cancelar?") y, al confirmar, llama a `Ejecucion.pedir_cancelar()`.
  - Estado/botones: tratar `Resultado("cancelado")` como reanudable (botón "Continuar",
    "Cancelado: quedan N"); habilitación/bloqueo coherentes con Pausar.
- **Criterio de hecho:** en la app real, Cancelar pide confirmación, corta la tarea
  (todos los hilos) y "Continuar" reanuda desde el punto guardado; test GUI del
  botón/estado. Suite verde.
- **Riesgo:** bajo-medio (GUI + un test GUI); el grueso está en la Fase 3.
- **Commit:** `feat: Fase 4 mejoras — botón Cancelar + modal en la GUI`.

> **ESTADO: HECHA (2026-09-17).**
> - **C13** — `PestanaBase`: botón "Cancelar" junto a "Pausar" (deshabilitado en
>   reposo; se habilita al arrancar). `_cancelar()` muestra un modal de aviso y, al
>   confirmar, llama a `Ejecucion.pedir_cancelar()` y deshabilita Cancelar/Pausar.
> - **Estado reanudable** — `_fin` trata `Resultado("cancelado")` como reanudable:
>   botón "Continuar", estado "Cancelado: quedan N", y `_reanudando_en_sesion=True`
>   (el próximo "Continuar" reanuda sin el modal). `procesar_cola` no pisa el texto
>   "Cancelando…" con el progreso (ni durante pausa ni durante cancelación).
> - **Tests** — `tests/gui/test_cancelar.py`: botón desactivado al inicio; `_cancelar`
>   activa la señal y deshabilita los botones; `_fin('cancelado')` deja "Continuar" +
>   "Cancelado: quedan N" + reanudable. (El comportamiento de aborto/limpieza está
>   cubierto por los tests de núcleo/motores de la Fase 3.)
> - **Verificación:** pyflakes limpio; **289 passed, 1 skipped** (2.º-root de Tk).
>
> **La función Cancelar (D-M1) queda COMPLETA de núcleo a interfaz (Fases 2–4).**

### Fase 5 — Deduplicar la orquestación del bucle de proceso
- **Objetivo:** sacar de los motores la lógica genérica de pausa/cancelar/límite/pregunta.
- **Incluye:** T3 (helper de bucle en `core` o ampliación del `Ejecutor`: `PAUSA`,
  `max_dirs`, `preguntar_cada`, pausa Y cancelación del usuario), C11 (aprovechar para
  introducir nivel de log si encaja). Llega DESPUÉS de Cancelar para deduplicar ya con
  ambas señales (pausar/cancelar) en su forma final.
- **Criterio de hecho:** los 8 motores usan el helper; pausa/cancelación (archivo
  `PAUSA`, Ctrl+C, límite, preguntar cada N, cancelar) idénticas al comportamiento de
  las Fases 3–4, cubiertas por tests; paralelo y secuencial respetan las mismas señales.
- **Riesgo:** medio-alto — corazón de la ejecución. Apoyarse en T7 y en los tests de
  pausa/cancelación/reanudación por motor.
- **Commit:** `refactor: Fase 5 mejoras — bucle de proceso común (pausa/cancelar/límite/pregunta)`.

> **ESTADO: HECHA (2026-09-17).**
> - **T3** — nuevo `core/control.py` con `Control`: centraliza las causas de parada
>   comunes en la frontera de unidad —cancelación, pausa del usuario, archivo `PAUSA`
>   y límite de unidades— con la precedencia (cancelar > pausar) y los mensajes en un
>   solo sitio. API: `debe_parar()` (secuencial), `debe_pausar()` (callback del
>   `Ejecutor`, sin cancelación), `desde_ejecutor(estado)` (traduce el retorno del
>   paralelo) y `estado`/`motivo`. 10 tests (`tests/core/test_control.py`).
> - **Motores** — los 8 sustituyen su bloque inline de comprobaciones + construcción de
>   `motivo`/`cancelado` por un `Control`: secuencial `if ctrl.debe_parar(): break`;
>   paralelo `ctrl.desde_ejecutor(ejec.ejecutar(..., ctrl.debe_pausar, cancelar=))`.
>   Los límites por dominio se conservan (`max_dirs`→"carpetas", `max_entradas`→
>   "elementos", `max_zips`→"ZIP") vía `contador`/`nombre_unidad`. Lo específico
>   (comprimir: `preguntar_cada` y el aborto intra-unidad `Cancelado`) queda inline.
> - **C11 (niveles de log) — NO hecho:** evaluado y descartado en esta fase; no encaja
>   en la extracción del `Control` y cambiaría la firma de `log` en todo el proyecto
>   (motores + GUI + tests). Queda pendiente como mejora independiente de bajo valor.
> - **Verificación:** pyflakes limpio; **301 passed**; smoke de los límites
>   (`max_dirs`/`max_entradas`) y de cancelación por `Control` en verde.

### Fase 6 — Reorganizar `core.comun` y `OpcionesBase`
- **Objetivo:** deshacer el cajón de sastre y compartir opciones comunes.
- **Incluye:** C3 (`comun` → `resultado.py`/`cli.py`/`formato.py`… coherente con el ya
  extraído `core/reanudable.py` de la Fase 2; actualizar docstrings obsoletos), C4
  (subir `seguir_enlaces`/`omitir_ocultos` a `OpcionesBase`).
- **Criterio de hecho:** imports actualizados en todo el árbol; el guardián de
  fronteras sigue en verde; ningún motor redeclara las opciones de recorrido; suite
  verde. Preservar historia con `git mv` al dividir.
- **Riesgo:** medio — mucha superficie de imports, pero mecánico. `git mv` + cambios de
  import en el mismo commit, sin lógica nueva.
- **Commit:** `refactor: Fase 6 mejoras — core.comun dividido y OpcionesBase ampliada`.

> **ESTADO: HECHA (2026-09-17).**
> - **C3** — `core/comun.py` (el cajón de sastre) se dividió y se ELIMINÓ, repartido en
>   cuatro módulos con una responsabilidad cada uno: `core/resultado.py`
>   (`Resultado`, `EstadoResultado`, `ESTADOS_VALIDOS`, `Cancelado`), `core/opciones.py`
>   (`OpcionesBase`), `core/formato.py` (`humano`/`duracion`/`ahora` + `PASO_REGISTRO`)
>   y `core/cli.py` (`correr_cli`, `Interrupcion`, `preguntar_consola`).
> - **Imports** — actualizados en todo el árbol: `core` (reanudable/ejecucion/paralelo/
>   __init__), `gui/pestana_base`, los 8 motores, las 3 pestañas, `bench.py` y los tests.
>   Sin re-exports de compatibilidad: `core.comun` ya no existe.
> - **C4** — `seguir_enlaces`/`omitir_ocultos` (opciones de recorrido de FS) suben a
>   `OpcionesBase`; retiradas las redeclaraciones de comprimir/aplanar/combinar/
>   desaplanar/renombrar (las heredan; los motores que no recorren las ignoran).
> - **Tests** — `test_comun.py` se dividió en `test_formato.py`, `test_resultado.py`
>   (con validación de estado inválido y equivalencia enum/str) y `test_cli.py`.
> - **Docs** — `ARQUITECTURA.md`/`README.md`/`tests/core/README.md` reflejan la nueva
>   estructura; contrato de motor con `cancelar`.
> - **Verificación:** pyflakes limpio; **306 passed, 1 skipped**; `bench.py` round-trip
>   byte-a-byte OK; sin ninguna referencia residual a `core.comun`.

### Fase 7 — Reorganizar `recursos` y encapsular `paralelo`/`registro`
- **Objetivo:** aislar lo dependiente de plataforma y limpiar fugas de encapsulación.
- **Incluye:** C6 (`recursos/` = `sondas.py` + `politica.py`), C7 (`ajustar_limite`
  en `Ejecutor`, sin tocar privados desde `_Regulador`), C8 (`_por_artefacto`
  precomputado + validación de unicidad). (C10 ya se resolvió en la Fase 3.)
- **Criterio de hecho:** la política de hilos se testea sin sondear hardware real
  (sondas mockeables); `_Regulador` no accede a privados; `Registro` valida artefacto
  duplicado; suite verde.
- **Riesgo:** medio. `recursos` es delicado por el código `ctypes`/`/proc`; no cambiar
  la lógica de las sondas, solo moverlas.
- **Commit:** `refactor: Fase 7 mejoras — recursos en subpaquete y encapsulación`.

> **ESTADO: HECHA (2026-09-17).**
> - **C6** — `core/recursos.py` (819 líneas) pasa a subpaquete `core/recursos/`:
>   `sondas.py` (medición pura: CPU/RAM/disco/energía + `PerfilSistema`/`perfil`/
>   `resumen`/`bajar_prioridad` + `main`) y `politica.py` (`PoliticaHilos`,
>   `calcular_hilos`, `techo_hilos`, `objetivo_activos`, `regulador_carga`, `preparar`;
>   importa lo que necesita de `sondas`). `__init__.py` es una fachada que reexporta la
>   API pública (con `__all__`), así los llamadores no cambian; `__main__.py` conserva
>   `python -m core.recursos`. Sin cambios de lógica, solo movimiento.
> - **C7** — `Ejecutor.ajustar_limite(n)` encapsula el throttling (acota a [1, hilos],
>   toma el cerrojo, notifica); `_Regulador` y el límite inicial lo usan en vez de tocar
>   `_cond`/`_activos_max` directamente.
> - **C8** — `Registro` precomputa `_por_artefacto` (consultas O(1)) y **valida** en el
>   constructor que ningún artefacto lo consuman dos tareas (handoff ambiguo).
> - **Tests** — nuevos: `ajustar_limite` (acotado a [1, hilos]) y validación de
>   artefacto duplicado. **309 passed.**
> - **Verificación:** pyflakes limpio; `python -m core.recursos` y el perfil siguen OK.

### Fase 8 — Partir `comprimir` y retirar andamiaje
- **Objetivo:** cerrar la deuda de tamaño y el andamiaje ya innecesario.
- **Incluye:** T5 (partir `comprimir/motor.py` en submódulos del paquete), T9 (quitar
  la indirección `tests/soporte/modulos.py`), T11 (traceback a debug en los `except`
  de motor). (T10 —migración `_estado_zip.json`— ya se retiró en la Fase 2.)
- **Criterio de hecho:** ningún módulo de tarea supera un tamaño razonable; los tests
  importan `tasks.*` directamente; `bench.py` round-trip OK; suite verde.
- **Riesgo:** bajo-medio. Al partir `comprimir`, usar `git mv` por bloques y no
  reescribir lógica. El modo compacto es función soportada y testeada (ver D-M3):
  `crear_agrupado`/marca `agrupado` viajan con el compresor, no son código muerto.
- **Commit:** `refactor: Fase 8 mejoras — comprimir modularizado y andamiaje retirado`.

> **ESTADO: HECHA (2026-09-17).**
> - **T5** — `tasks/comprimir/motor.py` (902 líneas) se parte en el paquete: `explorar.py`
>   (`InfoDir`/`explorar`/`seleccionar_agrupados`/`RAIZ`), `comprimidor.py` (`Comprimidor`
>   + `PRECOMPRIMIDAS`/`PARTS_NAME`, con la cancelación intra-unidad). `motor.py` queda en
>   ~580 líneas como fachada (reexporta la API pública que usan pestaña y tests) con
>   `Opciones`/`ejecutar`/`procesar`/`Estado`/`Planificador`/`info_reanudable`/`main`.
> - **T9** — retirada la indirección `tests/soporte/modulos.py`: los 22 tests que la
>   usaban importan los módulos reales directamente (`import tasks.X.motor as ...`);
>   `test_importa_todo` recorre los paquetes reales con `pkgutil`. El **guardián de
>   fronteras** se amplía: los submódulos de una misma tarea pueden importarse entre sí
>   (paquete vertical), sin permitir imports entre tareas distintas.
> - **T11** — el `except Exception` de `comprimir.procesar` registra el traceback a
>   `logging.getLogger(__name__).debug(exc_info=True)` (silencioso por defecto; sin
>   cambio visible), además del mensaje del `Resultado`.
> - **Extra** — limpiados 3 imports muertos preexistentes en tests (el trinquete solo
>   cubría producción).
> - **Verificación:** pyflakes limpio (producción y tests); **314 passed, 1 skipped**;
>   `bench.py` round-trip byte-a-byte OK; guardián de fronteras estricto en verde.

---

## 3. Decisiones (resueltas)

Estas decisiones cambian el alcance de alguna fase. **Las tres están resueltas**
(D-M1 y D-M2 por el usuario el 2026-09-17; D-M3 al verificar el código). Se conservan
como registro de por qué el roadmap tiene la forma que tiene.

### D-M1 — Cancelar: SÍ, junto a Pausar, con limpieza y recuperación → RESUELTA (2026-09-17)

**Decisión del usuario.** Se añade un botón **"Cancelar"** junto a "Pausar" con esta
semántica exacta:

- **Cancela la tarea que se está realizando en ese momento.**
- Si está trabajando en un **archivo a medias** (un fragmento que podría dar errores),
  **se elimina el archivo correspondiente a esa parte**, de forma que la tarea quede
  **recuperable desde el punto recuperable ANTERIOR**. Ejemplo: si está comprimiendo
  la segunda carpeta, se elimina el fragmento de la segunda carpeta a medias y **se
  mantiene la primera**.
- **Modal de aviso antes de cancelar.**
- **Genera un JSON** para poder continuar desde el punto recuperable anterior.
- **Única diferencia con Pausar:** *Pausar* espera a terminar la fase/unidad en curso
  y genera el JSON de recuperación incluyéndola; *Cancelar* termina la fase actual (la
  aborta) y genera el JSON en la **fase anterior completada**.
- **Multihilo:** al pausar o cancelar hay que asegurar que se **pausan/cancelan todas
  las unidades en todos los hilos**.

**Cómo se implementa.** Ítems **C12** (núcleo + motores) y **C13** (GUI); **Fases 3 y
4** del roadmap. Nota técnica que lo hace viable: los motores ya escriben cada unidad
en un `.part` y hacen `os.replace` al terminar, y borran el `.part` ante cualquier
excepción; y el JSON de estado solo registra unidades COMPLETADAS. Así, "abortar la
unidad en curso" = que el trabajo de la unidad compruebe la señal de cancelación y
lance/pare → el `.part` se borra solo y la unidad no se marca → el JSON queda en la
anterior, tal y como pide la decisión.

### D-M2 — Romper compatibilidad: SÍ; y centralizar el JSON de pausa/reanudación en el core → RESUELTA (2026-09-17)

**Decisión del usuario.** Se puede **romper la compatibilidad**: es un programa en
fase de desarrollo, todo es mejorable sin considerar comportamientos legacy. Además,
**la generación del archivo JSON para pausar y reanudar se incluye dentro del `core`**,
asegurando que sea **compatible con todas las tareas actuales y fácil de implementar en
tareas futuras**.

**Cómo se implementa.** Ítem **C2** ampliado; **Fase 2** del roadmap (un único
mecanismo de estado reanudable en `core`, base de Cancelar). Se adelanta **T10**
(retirar la migración `_estado_zip.json`) y se elimina cualquier lectura de formatos
previos. El JSON de recuperación queda centralizado y es el que escriben Pausar y
Cancelar.

### D-M3 — El "modo compacto" (mejora 5): solo hay que arreglar el comentario que miente (afecta a Fase 0/6)

**Contexto (verificado).** Comprimir tiene un **modo compacto** (`--compacto` /
`Opciones.agrupar_*`): en vez de un `.zip` por subcarpeta, agrupa subárboles pequeños
en un solo ZIP para pagar menos coste por archivo. Comprobado en el código: **es una
función soportada, no un experimento a medias**:
- Implementada: `seleccionar_agrupados` [tasks/comprimir/motor.py:295] y
  `Comprimidor.crear_agrupado` [tasks/comprimir/motor.py:638].
- **Testeada:** `test_round_trip_compacto` [tests/tasks/pares/test_comprimir_descomprimir.py:40]
  hace comprimir agrupado → descomprimir y comprueba el round-trip.
- **Expuesta en la GUI:** checkbox "Modo compacto (juntar carpetas pequeñas)"
  [tasks/comprimir/pestana.py:39], cableado a `aplicar_modo_compacto`.
- **Documentada** en la ayuda de la tarea [tasks/comprimir/ayuda.py:11].

**Conclusión.** La decisión "soportar vs retirar" que planteaba antes **no existe**:
el modo compacto se queda. Lo único real es que su docstring **miente** (dice "lo que
falta es el empaquetado en sí" cuando ya está implementado, testeado y en la GUI):
eso es **T6** y se arregla en la **Fase 0** (corregir el comentario), sin más
decisión que tomar.

**Lo que sí hay que recordar en las fases posteriores** (no es una decisión, es una
nota de alcance):
- **Fase 2 (estado reanudable):** el modo compacto también persiste estado; al
  unificar hay que cubrirlo, y su test de round-trip debe seguir en verde.
- **Fase 8 (partir `comprimir`):** `crear_agrupado` y la marca `agrupado=True` viajan
  con el compresor; no partir esa lógica como si fuera código muerto.

*(Esta decisión se "cerró" verificando el código el 2026-09-17; se conserva aquí para
dejar constancia de por qué el modo compacto no se toca.)*
