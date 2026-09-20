# Escalabilidad horizontal de kakoli — análisis y plan

> ⚠️ **DOCUMENTO HISTÓRICO.** Análisis (A–H) que preparó la escalabilidad sobre la
> estructura antigua `nucleo/motores/clases`. La reestructuración posterior (ver
> `REESTRUCTURACION.md`) llevó la app a `core/gui/tasks`; la receta actual para añadir
> una tarea está en `ARQUITECTURA.md §8`.

Objetivo del encargo: que **añadir un motor nuevo y su pestaña** (nuevas tareas,
todas ellas *transformaciones de directorios y subdirectorios*) sea sencillo,
reutilizando el máximo de código y evitando duplicidades. Este documento **solo
analiza**: no cambia código. Complementa a `ARQUITECTURA.md` (estado actual) y
`GUI.md` (selectores).

Fecha: 2026-09-06.

---

## 1. Qué cuesta hoy añadir una tarea (línea base)

Para una tarea nueva (p. ej. "Aplanar", "Renombrar en lote", "Deduplicar") hay que
tocar **tres sitios**:

1. **Nuevo `motor_X.py`**: `Opciones` (dataclass con `politica`), `rutas_validadas(...)`
   y `procesar(<entrada...>, opts, *, log, progreso, pausar, confirmar) -> Resultado`.
   Reutiliza `Resultado`, `humano`, `duracion`, `Interrupcion` (de `motor_comprimir`),
   `recursos.preparar/PoliticaHilos/calcular_hilos` y, si paraleliza, `paralelo.Ejecutor`.
   → **Esta capa ya reutiliza bien.**

2. **Nueva `PestanaX(PestanaBase)`** en `kakoli.py`: atributos de clase
   (`etiqueta_origen`, `tipo_origen`, `etiqueta_destino`, `titulo_dialogo`,
   `texto_inicio`, `aviso`, `usa_hilos`, `usa_compacto`, `estilo_accion`) + los
   ganchos (`_opciones`, `_validar` construyendo `opts`, `_ejecutar` llamando al
   motor, y opcionalmente `_destino_automatico`, `_confirmar`, `_al_terminar`).
   → **La mayor parte del trabajo y de la duplicación está aquí.**

3. **Registrar la pestaña en `App`** ([kakoli.py:808](kakoli.py), [:851](kakoli.py)):
   añadir `self.tab_X = PestanaX(...)`, meterla en la tupla `self.pestanas` y añadir
   su nombre a la tupla `NOMBRES`. **Tres ediciones acopladas por índice** que hay
   que mantener sincronizadas.

**Lo que YA se reutiliza sin tocar nada** (la columna vertebral, no conviene
cambiarla): el contrato de callbacks `log/progreso/pausar/confirmar`; `Resultado`;
el perfilado de máquina + auto-hilos + throttling + prioridad baja (`recursos`); el
pool genérico (`paralelo.Ejecutor` + `Plan`); el modelo de hilo+cola de la GUI
(`_iniciar`/`procesar_cola`/`_fin`/`App._bomba`); el bloqueo "una tarea a la vez";
la reanudabilidad; el anti-zip-slip; y todo el tema visual (`tema.py`).

---

## 2. Puntos de fricción / duplicidad (hallazgos)

Ordenados por impacto en la escalabilidad.

### F1 — Registro de pestañas acoplado por índice *(alto)*
`NOMBRES` (tupla), los atributos `self.tab_*`, y la tupla `self.pestanas` se
mantienen a mano y **en el mismo orden**. `bloquear`/`desbloquear`
([kakoli.py:1000](kakoli.py)) recorren `zip(pestanas, NOMBRES)` por posición.
Añadir una pestaña = 3 ediciones que deben cuadrar. Riesgo de desincronización.

### F2 — El nombre vive fuera de la pestaña *(alto)*
Todo lo de una pestaña está en su clase salvo el nombre visible, que está en
`App.NOMBRES`. La pestaña **no es autodescriptiva**.

### F3 — `_opciones` es imperativo y muy repetitivo *(alto — la mayor duplicación)*
Cada opción son ~5-6 líneas casi idénticas: crear `BooleanVar`, crear `Checkbutton`
sobre `self.marco_ops`, `self._add_control(c)`, `self._bloqueables.append(c)`,
`self._add_ayuda("…")`. Se repite en las 3 pestañas (comprimir 5, descomprimir 3,
eliminar 3) y se repetirá en cada nueva. Es fácil olvidar `_bloqueables` o la ayuda.

### F4 — Firmas de `procesar` no uniformes *(medio)*
La aridad de entrada varía: comprimir `procesar(raiz, salida, opts, …)`,
descomprimir `procesar(zip, destino, opts, …)`, eliminar `procesar(carpeta, opts, …)`
(1 vs 2 rutas). Cada `_ejecutar` codifica a mano la forma de los argumentos. La GUI
no puede invocar un motor "a ciegas".

### F5 — `Opciones` repite `politica` + `detallado` *(bajo)*
Las tres dataclass repiten `detallado: bool` y el bloque
`politica: PoliticaHilos = field(default_factory=…)`. Sin una base común.

### F6 — Acoplamiento entre pestañas por nombre de atributo *(medio)*
`PestanaComprimir._al_terminar` hace
`self.app.tab_descomprimir.establecer_origen(...)` ([kakoli.py:601](kakoli.py)):
una tarea "productora" conoce a la "consumidora" por su atributo concreto.

### F7 — Modelo de entrada rígido: origen (+destino) *(medio)*
`PestanaBase` asume **un** selector "origen" (carpeta o archivo) y **un** destino
opcional. Futuras transformaciones pueden necesitar: operar *in situ* (sin
destino), dos entradas, o **parámetros extra** (un patrón de renombrado, una
extensión objetivo, un umbral…). Hoy no hay hueco limpio para "un campo de texto
más".

### F8 — La sección "Rendimiento" es compresión-céntrica *(bajo)*
`usa_hilos`/`usa_compacto` y `_construir_comunes` saben del "modo compacto" (propio
de comprimir). Un motor nuevo que paralelice pone `usa_hilos=True` y hereda hilos +
modo ligero (bien), pero el compacto está cableado como concepto común cuando no lo es.

### F9 — Sin un `Plan` reutilizable para el caso "cada subcarpeta, independiente" *(medio)*
`paralelo.Ejecutor` es genérico, pero los dos `Plan` existentes viven en sus motores
(`Planificador` = dependencias padre/hijo; `_PlanDescomp` = cola dinámica). El caso
más probable de una transformación futura —**recorrer subdirectorios independientes
y aplicar una operación a cada uno**— no tiene un `Plan` listo; cada motor nuevo
reimplementaría el mismo plan trivial sobre una lista.

### F10 — `Resultado`, `humano`, `duracion`, `preparar` viven en `motor_comprimir` *(bajo)*
Descomprimir y eliminar **importan de comprimir** solo para reutilizar utilidades.
Un motor nuevo también tendría que importar `motor_comprimir` aunque no comprima:
dependencia conceptualmente invertida.

### F11 — CLI duplicada por motor *(bajo)*
Cada motor tiene su propio `__main__` con parseo de argumentos y cableado de
`log`/`progreso`. Añadir un motor duplica ese arnés.

---

## 3. Arquitectura objetivo (norte)

**Meta: añadir una tarea = 1 módulo de motor + 1 subclase de pestaña pequeña +
registrarla en UNA lista.** Sin ediciones acopladas por índice y con las opciones
declaradas como datos.

Cambios propuestos (todo esto es trabajo FUTURO; aquí solo se describe):

### A. Núcleo común extraído: `comun.py` (resuelve F5, F10)  — IMPLEMENTADA (2026-09-06)

> Hecho: creado `comun.py` con `Resultado`, `Interrupcion`, `humano`, `duracion`,
> `ahora`, `preguntar_consola`, `PASO_REGISTRO` y `OpcionesBase` (campos `detallado`
> + `politica`). Los tres motores hacen `class Opciones(comun.OpcionesBase)` (se
> quitó la repetición de `detallado`/`politica`). `motor_comprimir` re-exporta lo de
> `comun` por compatibilidad y conserva lo de dominio ZIP (`leer_marca`, `Estado`,
> `Planificador`…); `motor_descomprimir` importa lo genérico de `comun` y solo
> `leer_marca` de `motor_comprimir`; `motor_eliminar` ya **no** depende de
> `motor_comprimir`. `kakoli`/`bench` importan lo genérico de `comun`. Cadena:
> `recursos ← paralelo ← comun ← motor_* ← kakoli`. Verificado: bench round-trip 5/5,
> CLIs de los 3 motores, regresión GUI completa, defaults/`nivel`/re-export intactos.
> `preparar` NO se movió (ya vivía en `recursos`).

Mover a un módulo base (nombre sugerido `comun.py` o `motor_base.py`):
`Resultado`, `Interrupcion`, `humano`, `duracion`, `leer/escribir` genéricos y el
punto de entrada de rendimiento (`preparar`). Añadir una **`OpcionesBase`**
(dataclass con `detallado: bool = False` + `politica: PoliticaHilos`), de la que
hereden las `Opciones` de cada motor. Cadena de imports resultante:
`recursos` ← `paralelo` ← `comun` ← `motor_*` ← `kakoli`. Los motores dejan de
depender de `motor_comprimir` para lo genérico.

> **B y E — IMPLEMENTADAS** (2026-09-06). Detalle al final de §3.

### B. Contrato uniforme de motor (resuelve F4)
Definir un `Protocol` (o registro) de tarea con una firma única que la GUI pueda
llamar a ciegas. Opción mínima y de bajo riesgo: un **descriptor por tarea** que
empaqueta *(motor, cómo validar rutas, cómo construir Opciones, cómo invocar
procesar)*. Opción más limpia: cada motor expone
`ejecutar(entradas: Entradas, opts, *, log, progreso, pausar, confirmar)` donde
`Entradas` es `{origen, destino|None, extra: dict}`; internamente reparte a su
`procesar`. Así `PestanaBase._ejecutar` se vuelve **genérico** (una sola
implementación en la base) y las pestañas dejan de escribir `_ejecutar`.

> **C y D — IMPLEMENTADAS** (2026-09-06). Ver al final de §3.

### C. Registro de pestañas + pestañas autodescriptivas (resuelve F1, F2)
- `PestanaBase.nombre: str` como atributo de clase.
- `App.TABS = [PestanaComprimir, PestanaDescomprimir, PestanaEliminar, …]`; `App`
  construye `self.pestanas` y el `Notebook` recorriendo esa lista, y `NOMBRES` se
  deriva (`[c.nombre for c in TABS]`). `bloquear/desbloquear` usan `pes.nombre`.
- Añadir una pestaña = **añadir su clase a `TABS`** (una línea). Alternativa:
  decorador `@registrar_pestana` para auto-registro al importar.

### D. Opciones declarativas (resuelve F3 — el mayor ahorro de LOC)
Dar a `PestanaBase` ayudantes que creen el control, lo añadan a `_bloqueables` y
emitan su ayuda en **una sola llamada**:
`self._check(var, etiqueta, ayuda)`, `self._combo(var, etiqueta, valores, ayuda)`,
`self._radios(var, valores, ayuda)`. O, un paso más allá, forma **dirigida por
datos**: la pestaña declara
`OPCIONES = [Seccion("Filtros"), Check("omitir_ocultos", "Omitir ocultos", "ayuda…"), …]`
y la base la construye. Garantiza consistencia (toda opción se bloquea y lleva
ayuda) y reduce cada opción de ~6 líneas a 1.

### E. Campos de entrada generalizados (resuelve F7)
Sustituir los atributos fijos origen/destino por una **lista de campos**:
`ENTRADAS = [Campo("origen", "Carpeta:", tipo="carpeta"),
Campo("destino", "Salida:", tipo="carpeta_salida", opcional=True),
Campo("patron", "Patrón:", tipo="texto")]`. `PestanaBase` genera las filas de
selección desde esa lista y expone `self.valores` (dict) a `_validar`. Cubre *in
situ* (solo un campo), dos entradas y parámetros extra. Se mantiene origen+destino
como valor por defecto para que las pestañas actuales apenas cambien.

### F. `paralelo.PlanLista(items)` reutilizable (resuelve F9)  — IMPLEMENTADA (2026-09-06)

> Hecho: `paralelo.PlanLista(items)` — un `Plan` listo para N unidades
> INDEPENDIENTES (entrega los items de una lista y cuenta las terminadas; cerrojo
> propio; cumple el Protocol `Plan`). Un motor que mapee sobre subcarpetas
> independientes hace `Ejecutor(n).ejecutar(PlanLista(subcarpetas), trabajo=…,
> pausar=…)` sin reimplementar un plan. `Planificador` (dependencias padre/hijo) y
> `_PlanDescomp` (cola dinámica) siguen en sus motores. Verificado (test_planlista):
> cada unidad una sola vez con 1/4/8 hilos, pausa sin duplicar ni perder
> (procesadas+restantes==total), lista vacía, y conformidad con el Protocol.

Un `Plan` listo para "**N unidades independientes**" (sin dependencias): entrega
items de una lista y marca terminadas. Es el patrón esperable de casi cualquier
transformación por subdirectorio. `Planificador` y `_PlanDescomp` se quedan en sus
motores (lógica de dominio). Un motor nuevo que mapee sobre subcarpetas hace:
`Ejecutor(n).ejecutar(PlanLista(subcarpetas), trabajo=aplicar_a_una, pausar=…)`.

### G. Handoff entre tareas desacoplado (resuelve F6)  — IMPLEMENTADA (2026-09-06)

> Hecho: `PestanaBase.produce` ('archivo' | 'carpeta' | None) declara qué genera
> una tarea; al completar, `PestanaBase._fin` llama a `App.sugerir_entrada(ruta,
> tipo, excepto=self)`, que rellena el origen de la primera pestaña cuyo primer
> campo consuma ese tipo. La productora ya NO nombra a la consumidora (Comprimir
> solo declara `produce='archivo'`; el paso a Descomprimir lo hace el despachador).
> Verificado (test_g): despacho por tipo y handoff real (tras comprimir, el origen
> de Descomprimir queda puesto al ZIP).

Sustituir `self.app.tab_descomprimir.establecer_origen(...)` por un acceso por tipo
/ nombre (`self.app.pestana(PestanaDescomprimir)`) o un gancho de post-proceso
(`self.app.sugerir_entrada(ruta, tipo)`) que la pestaña consumidora recoja. La
productora deja de nombrar a la consumidora por atributo.

### H. (Opcional) Arnés CLI compartido (resuelve F11)  — IMPLEMENTADA (2026-09-06)

> Hecho: `comun.correr_cli(ejecutar, entradas, opts, *, si=False, antes=None)`
> encapsula lo idéntico de los tres `main()`: instala `Interrupcion`, imprime
> `antes` (aviso de pausa / advertencia), llama a `ejecutar(entradas, opts, ...)`
> (que ya registra Origen/Salida/Carpeta) y traduce el `Resultado` al código de
> salida (0 ok/nada, 1 error/cancelado, 2 pausado, 130 doble Ctrl+C). Cada `main()`
> queda en: parsear args → construir `opts`+`entradas` → `return correr_cli(...)`.
> Verificado por CLI: comprimir→zip, descomprimir→carpeta (rc=0), eliminar --simular.

`comun.ejecutar_cli(motor, campos)` que parsee rutas + banderas comunes
(`--detallado`, `--nivel`, `--sin-…`) y cablee `log`/`progreso`. Cada `__main__`
queda en pocas líneas.

**Qué NO tocar** (ya es genérico y es el motivo de que todo esto sea barato):
la separación `recursos`/`paralelo`/motor; el contrato de callbacks; `Resultado`;
el modelo hilo+cola+`_bomba`; el bloqueo "una tarea a la vez"; la reanudabilidad;
el anti-zip-slip; y `tema.py`.

---

### Estado: C y D implementadas (2026-09-06)

**C (registro de pestañas + `nombre`)** — hecho en `kakoli.py`:
- `PestanaBase.nombre` (atributo de clase); cada pestaña define el suyo
  ("Comprimir"/"Descomprimir"/"Eliminar").
- `App.TABS = (PestanaComprimir, PestanaDescomprimir, PestanaEliminar)`. `App`
  instancia las pestañas recorriendo `TABS`, construye `self.pestanas` y el
  `Notebook` (`text=_rotulo(pes.nombre)`), y mantiene `self._por_clase`.
- `App.pestana(clase)` (lookup); el handoff de Comprimir→Descomprimir usa
  `self.app.pestana(PestanaDescomprimir)` en vez del atributo concreto (resuelve
  también F6). Se eliminó `App.NOMBRES`; `bloquear`/`desbloquear` usan `pes.nombre`.
- **Añadir una pestaña = añadir su clase a `TABS`** (una línea). Verificado con una
  `PestanaDemo` de prueba: aparece con su rótulo de corchete, entra en el bloqueo y
  en `pestana()` sin ningún cambio extra. Se conservan aliases `tab_comprimir/…`
  por conveniencia (handoff/scripts), no necesarios para pestañas nuevas.

**D (opciones declarativas)** — hecho en `kakoli.py`:
- Helpers en `PestanaBase`: `_check(var, etiqueta, ayuda, *, command=None)` y
  `_combo(var, etiqueta, valores, ayuda, *, width=24)`. Cada uno crea el control en
  la sección vigente, lo añade a `self._bloqueables` y emite su ayuda: **una opción
  = una llamada**. Ya no se puede olvidar el bloqueo ni la ayuda.
- Los tres `_opciones` y el "Modo ligero" de `_construir_comunes` se reescribieron
  con los helpers (de ~6 líneas por opción a 1). Los radios de Hilos siguen con su
  patrón propio (no encajan en check/combo). UI idéntica (verificado por captura y
  por los tests de estructura).

**B (contrato uniforme + `_ejecutar` genérico)** — hecho:
- Cada motor expone `ejecutar(entradas: dict, opts, *, log, progreso, pausar,
  confirmar) -> Resultado` que mapea las claves de `entradas` a su `procesar`
  (claves uniformes: `"origen"`, `"destino"`). Resuelve F4.
- `PestanaBase._ejecutar` es ahora **único y genérico**: llama a
  `self.MOTOR.ejecutar(datos["entradas"], datos["opts"], …, confirmar=self._confirmador())`.
  Las pestañas ya **no** implementan `_ejecutar`; declaran `MOTOR = mcomp|mdesc|melim`
  y su `_validar` devuelve `{"entradas": {...}, "opts": <Opciones>}`. El callback
  de confirmación en marcha se declara con `_confirmador()` (solo Descomprimir lo
  redefine, → `self._preguntar`).

**E (campos de entrada declarativos)** — hecho:
- Dataclass `Campo(clave, etiqueta, tipo, opcional)` con `tipo` ∈ {carpeta,
  archivo, carpeta_salida, texto}. Una pestaña declara `ENTRADAS = [Campo(...), …]`;
  `PestanaBase` construye las filas (label + Entry + botón "Examinar…", salvo los
  campos `texto`), crea una `StringVar` por campo en `self.vars_entrada` y ofrece
  `self.valor(clave)` para `_validar`. Cubre in-situ (un solo campo), 2+ entradas y
  parámetros de texto.
- Compatibilidad: si `ENTRADAS` es None se derivan de los atributos clásicos
  (`etiqueta_origen`/`tipo_origen`/`etiqueta_destino`), así las 3 pestañas de serie
  no cambiaron; se mantienen los alias `v_origen`/`v_destino`. Verificado: UI de las
  3 pestañas idéntica (captura + tests fase4/5/6), round-trip 5/5, y una pestaña de
  prueba con 2 rutas + un campo de texto (test_be) construye filas, `valor()` y el
  `_ejecutar` genérico entrega las entradas (incluido el texto) al motor.

**TODO EL PLAN (A–H) IMPLEMENTADO** (2026-09-06). Añadir una tarea nueva es ahora:
(1) `motor_X.py` con `Opciones(comun.OpcionesBase)` + `ejecutar(entradas, opts, *,
callbacks)` (y `Ejecutor(n).ejecutar(paralelo.PlanLista(subs), …)` si mapea
subcarpetas independientes); (2) `PestanaX(PestanaBase)` que declara `nombre`,
`MOTOR`, `ENTRADAS` (Campo), opciones con `_check`/`_combo`, `_validar` →
`{"entradas", "opts"}`, y opcionalmente `produce`; (3) una línea en `App.TABS`. El
`main()` del motor usa `comun.correr_cli`.

---

## 4. "Recetario": añadir una tarea, hoy vs. objetivo

**Hoy:** módulo motor + subclase con 7-9 atributos y 4-6 ganchos (incluido
`_opciones` imperativo y `_ejecutar` con la forma de argumentos del motor) +
**3 ediciones acopladas** en `App` (`tab_*`, `pestanas`, `NOMBRES`).

**Objetivo:** módulo motor (heredando `OpcionesBase`, exponiendo `ejecutar`) +
subclase que declara `nombre`, `ENTRADAS`, `OPCIONES` (datos) y, si acaso, un
`_confirmar`/`_al_terminar` opcional + **1 edición**: añadir la clase a `App.TABS`.
`_validar`/`_ejecutar` genéricos viven en la base.

---

## 5. Prioridad recomendada (esfuerzo → beneficio)

1. **C (registro de pestañas + `nombre`)** y **D (opciones declarativas)** — máximo
   beneficio, riesgo bajo, no tocan los motores. Eliminan las 3 ediciones acopladas
   y la mayor duplicación de la GUI.
2. **A (`comun.py` + `OpcionesBase`)** — limpia la dependencia invertida y prepara B.
3. **B (contrato uniforme + `_ejecutar` genérico)** y **E (campos de entrada)** —
   habilitan de verdad las tareas con formas de entrada distintas (in situ, 2
   entradas, parámetros). Riesgo medio (tocan el flujo de validación/ejecución).
4. **F (`PlanLista`)** — pequeño, alto valor para transformaciones por subdirectorio.
5. **G (handoff)** y **H (CLI)** — pulido; hacer cuando aparezca la 2ª/3ª tarea.

Sugerencia de secuencia segura: **1 → 2 → 4 → 3 → 5**, cada paso con su verificación
(los tests de GUI y `bench.py` deben seguir verdes; el contrato de callbacks y
`Resultado` no cambian, así que los motores actuales no se ven afectados por 1, 2 y 4).

---

## 6. Riesgos y notas

- **No romper el contrato de callbacks ni `Resultado`**: es lo que permite que los
  motores actuales sigan intactos mientras se generaliza la GUI.
- **Tkinter en un hilo**: cualquier ayudante declarativo debe seguir construyendo
  widgets en el hilo principal (ya es el caso) y leyendo variables Tk en `_validar`
  (patrón ya adoptado). Un enfoque dirigido por datos encaja bien con esto.
- **Reanudabilidad y estado**: si una transformación nueva necesita ser reanudable,
  el patrón es el `Estado` JSONL de comprimir; conviene extraer también una base de
  "estado reanudable" si la 2ª tarea lo pide (no antes: YAGNI).
- **Bloqueo "una tarea a la vez"**: se mantiene igual; el registro de pestañas no lo
  cambia (sigue por `Notebook.tab(i, state=…)`).
- **Compatibilidad**: A/C/D pueden hacerse de forma incremental (una pestaña a la
  vez) sin big-bang; las pestañas no migradas conviven con las migradas.

---

## Validación del sistema: categoría "Combinación" (2026-09-06)

La primera pareja de tareas nueva (**Combinar / Descombinar**, motores
independientes) se añadió siguiendo A–H y el menú de dos niveles, confirmando que el
sistema escala:
- **Motores** `motor_combinar` / `motor_descombinar`: `Opciones(comun.OpcionesBase)` +
  `ejecutar(entradas, opts, *, callbacks)` + `comun.correr_cli`; la fusión paraleliza
  con `paralelo.PlanLista` + `paralelo.Ejecutor` (D7). Ninguno depende de
  `motor_comprimir` (descombinar solo importa el lector de índice de combinar, igual
  que descomprimir↔comprimir).
- **Pestañas** `PestanaCombinar` / `PestanaDescombinar`: declarativas (`nombre`,
  `MOTOR`, `ENTRADAS`, opciones `_check`/`_combo`, `_validar`, `_confirmar`,
  `produce`/`produce_hacia`).
- **Registro**: una entrada en `App.MENU` (`Categoria("Combinación", …)` la primera).
- **Ampliación aditiva**: hizo falta un tipo de `Campo` nuevo (**`lista`**: rutas
  multilínea tras un botón), útil para cualquier tarea futura con N entradas; y un
  destino de handoff explícito (**`produce_hacia`**). Ambos son extensiones limpias
  de E/G, no reescrituras.

Es decir: **motor + pestaña declarativa + una línea en `MENU`**, con dos pequeñas
extensiones reutilizables. El plan A–H sostiene el crecimiento horizontal.


## Validación del sistema: categoría "Aplanado" (2026-09-07)

La segunda pareja (**Aplanar / Desaplanar**, motores independientes) confirmó que el
sistema escala **sin ninguna extensión nueva del framework**:
- **Motores** `motor_aplanar` / `motor_desaplanar`: `Opciones(comun.OpcionesBase)` +
  `ejecutar(entradas, opts, *, callbacks)` + `comun.correr_cli`; paralelizan por
  archivo con `paralelo.PlanLista` + `paralelo.Ejecutor`, serializando por nombre/ruta
  de destino (como D7). Desaplanar solo importa `separador_ok` de aplanar (igual que
  descombinar↔combinar). Sin índice: la reconstrucción es por convención de nombre.
- **Pestañas** `PestanaAplanar` / `PestanaDesaplanar`: declarativas, **reutilizando
  solo primitivas ya existentes** (`Campo` `carpeta`/`carpeta_salida`, `_combo`/
  `_check`, `_validar`/`_confirmar`, `produce`/`produce_hacia`). El campo de texto del
  separador es un `ttk.Entry` normal — no hizo falta ningún tipo de `Campo` nuevo.
- **Registro**: una entrada en `App.MENU` (`Categoria("Aplanado", …)`, la tercera).
- **Lección de concurrencia**: el anti-traversal de desaplanar usaba `Path.resolve()`
  (consulta el disco) y daba **falsos positivos bajo paralelismo** (competía con la
  creación de carpetas), perdiendo archivos de forma intermitente. Se cambió a una
  comprobación **puramente léxica** (`os.path.normpath`), segura entre hilos. Lo cazó
  `bench --flatten --hilos 4` (la firma incluye mtime y contó los archivos perdidos),
  no los tests de contenido: **para validar paralelismo, comparar recuentos + firma
  completa, no solo el contenido**.

Confirma la regla: **motor + pestaña declarativa + una línea en `MENU`**; esta vez,
cero extensiones del framework.


## Nota: reanudación tras cerrar (2026-09-07, `roadmap_reanudar.md`)

Otra validación de la filosofía "maquinaria compartida en `comun`": la reanudación de
tareas tras cerrar la app se resolvió con **`comun.RegistroReanudable`** (registro de
progreso JSON reutilizable) + un contrato aditivo `info_reanudable(entradas, opts) ->
dict|None` que la base (`PestanaBase._iniciar`) usa para un **modal uniforme**
Continuar/Empezar-de-cero. Aplanar/Desaplanar lo adoptaron sin tocar el framework de
pestañas; Comprimir expone `info_reanudable` sobre su formato propio. Es el mismo patrón
que A (núcleo en `comun`) y G (`produce`/`produce_hacia`): **un gancho opcional en el
contrato + un helper compartido**, no una reescritura.


## Validación del sistema: categoría "Renombrado" (2026-09-08)

Tercera tarea nueva (**Renombrar**, `motor_renombrar`), categoría de tarea única (como
Eliminar), colocada antes de Eliminar. Otra confirmación del molde con **cero
extensiones del framework**: motor (`Opciones(OpcionesBase)` + `ejecutar` +
`comun.correr_cli`) + `PestanaRenombrar` declarativa (`ENTRADAS`, `_validar`,
`_confirmar`, opciones con `_check`/`_combo`/un pequeño helper `_entry` para los campos
de texto) + **una línea** en `App.MENU`. La "vista previa" reutiliza toda la maquinaria
de `_iniciar` con un flag `simular` — sin tocar el contrato ni el hilo+cola. Renombrar
no usa índice ni reanudación (el `rename` es rápido). En la misma tanda, la **portada
pasó a solo-tarjetas** y se añadió la **vista de Ayuda** (README): ambos son cambios de
presentación en `App`, no del contrato de motores; Ayuda no es una `PestanaBase`.
