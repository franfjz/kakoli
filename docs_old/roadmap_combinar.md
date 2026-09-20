# Roadmap: categoría "Combinación" — pestañas Combinar / Descombinar

Objetivo: dos tareas nuevas y complementarias (motores independientes) que **funden
árboles de directorios** (merge) y **deshacen** esa fusión, agrupadas en una
categoría nueva **"Combinación"**, colocada **la primera** (orden final:
**Combinación / Compresión / Eliminar**).

Este documento **solo diseña y analiza**: no toca código. Se apoya en el sistema
real de pestañas (escalabilidad A–H y menú de dos niveles). Referencias:
`escalabilidad.md`, `roadmap_menu_pestanas.md`, `ARQUITECTURA.md`, `GUI.md`.

Fecha: 2026-09-06.

---

## 1. Cómo se crea hoy una pestaña (sistema real) y qué encaja directamente

Añadir una tarea hoy es (verificado en el código):

1. **Motor** `motor_X.py`: `class Opciones(comun.OpcionesBase)` (hereda `detallado`
   + `politica`), `rutas_validadas(...)`, `procesar(<entrada>, opts, *, log,
   progreso, pausar, confirmar) -> comun.Resultado`, y un contrato uniforme
   `ejecutar(entradas: dict, opts, *, log, progreso, pausar, confirmar)` que mapea
   `entradas` a `procesar`. El `main()` usa `comun.correr_cli(ejecutar, …)`.
   Reutiliza `recursos.preparar()` (perfil + hilos + prioridad baja) y, si
   paraleliza sobre unidades independientes, `paralelo.Ejecutor(n).ejecutar(
   paralelo.PlanLista(unidades), trabajo, pausar)`.
2. **Pestaña** `PestanaX(PestanaBase)`: declara `nombre`, `MOTOR = motor_X`,
   `ENTRADAS = [Campo(clave, etiqueta, tipo)]`, las opciones con `_check`/`_combo`
   (una llamada por opción), `_validar()` (hilo principal) → `{"entradas": {...},
   "opts": <Opciones>}`, y opcionalmente `produce` ('archivo'/'carpeta') para el
   handoff (`App.sugerir_entrada`) y `_confirmar(datos)` (modal previo, como
   Eliminar).
3. **Registro**: añadir la categoría/tarea a **`App.MENU`** (`Categoria(nombre,
   tareas=[clases])`). El navegador de dos niveles la pinta sola. **Orden**: poner
   `Categoria("Combinación", [PestanaCombinar, PestanaDescombinar])` **la primera**
   de la tupla `App.MENU`.

Lo que **encaja sin cambios**: el registro (`MENU`), la navegación 1↔2, el bloqueo
"una tarea a la vez", el monitor compartido (perfil + Rendimiento + consola + info),
las opciones de rendimiento comunes (`App.v_hilos`/`v_ligero`), el `_ejecutar`
genérico, el `_confirmar` modal, la barra inferior con estados de color, y el
handoff por tipo. **El motor NO tiene por qué usar el formato ZIP**: comprimir/
descomprimir sí, pero `comun`/`recursos`/`paralelo` son agnósticos del dominio.

---

## 2. Qué NO cubre el sistema aún (huecos a extender)

Estas tareas piden cosas que el molde actual no tiene todavía. Cada hueco tiene una
extensión limpia y reutilizable (para futuras tareas, no solo estas):

- **H1 — Campo de "lista de rutas" (multilínea tras un botón).** `Campo` hoy solo
  tiene tipos `carpeta`/`archivo`/`carpeta_salida`/`texto` (una `Entry` por campo,
  valor en `self.vars_entrada[clave]` StringVar; `self.valor(clave)`). Falta un tipo
  nuevo, p. ej. **`tipo="lista"`**, que se pinte como un **botón** ("Añadir más
  directorios…") que **despliega/oculta un `Text` multilínea** (una ruta por línea).
  Extensión: en `Campo` no hace falta nada nuevo (solo el tipo); en
  `PestanaBase._construir` (bucle `for campo in self.campos`) tratar `tipo=="lista"`
  aparte (Text + botón toggle, no `Entry`); y un accesor `self.valores_lista(clave)`
  → líneas no vacías. Es una ampliación del sistema declarativo E, útil a futuro
  para cualquier tarea con N entradas.
- **H2 — Entradas de aridad variable.** El contrato `ejecutar(entradas: dict, …)` ya
  admite cualquier forma: aquí `entradas = {"principal": <dir1>, "fuentes":
  [<dir2>, <dir3>, …]}`. `_validar` construye esa lista (principal + secundario +
  las líneas de la lista) y comprueba que **todas** existen (omitiendo líneas
  vacías); si falta alguna, `ValueError`. No hay que tocar `_ejecutar` genérico.
- **H3 — Metadatos de origen por archivo para deshacer (reversibilidad).** kakoli
  solo tiene "marca" en el **comentario del ZIP** (`leer_marca`); los archivos
  sueltos (txt/jpg/bin…) **no tienen un campo de comentario portable**. Hace falta
  un mecanismo nuevo (ver Decisión D1). Es la pieza central de "Descombinar".
- **H4 — Motor sobre árbol de archivos sueltos (no ZIP).** Reutiliza `explorar`
  conceptualmente (recorrer un árbol) y `paralelo.PlanLista` (por subcarpeta o por
  archivo independiente), `recursos.preparar` y `comun.Resultado`, pero necesita
  utilidades nuevas de **copia con metadatos + resolución de conflictos**. No
  reutiliza `motor_comprimir` (ZIP).
- **H5 — Aviso dinámico según la opción elegida.** El `aviso` rojo de `PestanaBase`
  es estático (siempre visible, como Eliminar). El aviso de "reemplazar" debe salir
  **solo cuando esa política está seleccionada** → se hace en `_confirmar(datos)`
  (modal, como Eliminar), no con el `aviso` estático.
- **H6 — `produce`/handoff carpeta→carpeta.** `App.sugerir_entrada` reparte por tipo
  al **primer** consumidor. Con "Combinación" primera, el orden de `App.pestanas` es
  Combinar, Descombinar, Comprimir, Descomprimir, Eliminar; `Combinar` con
  `produce="carpeta"` (excepto=self) cae en **Descombinar** (primer consumidor
  `carpeta`). Funciona, pero depende del orden; ver Decisión D6.

---

## 3. Semántica de la fusión (Combinar)

**Entrada**: un **directorio principal** (dir1, puede estar vacío) + uno o más
**directorios a fundir** (dir2, dir3, …, en ese orden). **Resultado**: el principal
pasa a contener la **unión** de todos los árboles, respetando la estructura común
(mismo nombre y mismo nivel ⇒ misma carpeta).

Para cada archivo de una fuente en la ruta relativa `R`:
- **No existe `R` en el principal** → se copia a `R`, registrando su **origen** y su
  **nombre/ruta original** (para el undo).
- **Existe `R`** (misma ruta de carpetas y mismo nombre) → **conflicto** → aplica la
  política elegida:
  - **Renombrar (por defecto)**: se conservan ambos; el entrante se copia con un
    **código de su carpeta de origen** añadido al nombre, p. ej.
    `nombre_<código>.ext` (ej. `informe_dir2.pdf`). El código identifica la fuente
    (ver D3). Reversible.
  - **Mantener el original**: se omite el entrante (no se combina ese archivo).
    Reversible (no se pierde nada del principal; el entrante no entra).
  - **Reemplazar por criterio**: mayor tamaño / menor tamaño / más reciente / más
    antiguo (selector adicional). El archivo perdedor **se descarta** → **NO
    reversible** para ese archivo (aviso, H5/D5).

**Ejemplos del enunciado** (validan la unión profunda):
- principal `nivel1/nivel2/archivo.txt` + fuente `nivel1/nivel2/archivo2.txt`
  ⇒ `nivel1/nivel2/` con **dos** archivos.
- principal `nivel1/nivel2/archivo.txt` + fuente `nivel1/nivel3/archivo.txt`
  ⇒ `nivel1/` con **dos** subcarpetas, cada una con su archivo.

**Registro de origen (para el undo)**: se anota el origen de **cada** archivo del
resultado, incluidos los que ya estaban en el principal (origen = principal). Así
Descombinar puede regenerar **también** el árbol original del principal. Los archivos
**descartados** por "reemplazar" no se pueden recuperar.

---

## 4. Semántica del deshacer (Descombinar)

**Entrada**: un directorio generado por "Combinar" (que lleva su índice de origen,
D1). **Resultado**: se regeneran los **directorios originales** — uno por cada
origen (principal + cada fuente) — restaurando la **estructura y los nombres de
archivo originales** (deshaciendo el sufijo de renombrado). Cada carpeta de salida
reproduce lo que aquella fuente aportó.

- Un directorio combinado **copiado a otro sitio sigue siendo descombinable** (el
  índice viaja dentro de él): "agregando un directorio generado por Combinar se
  pueden generar todos los directorios principales".
- Si en la combinación se eligió **reemplazar**, los archivos descartados faltan;
  Descombinar los omite (y puede avisar de las ausencias detectadas en el índice).
- Descombinar **no borra** el combinado; produce las carpetas reconstruidas en un
  destino (por defecto, al lado).

---

## 5. Diseño de los motores (independientes)

**`motor_combinar.py`**
- `class Opciones(comun.OpcionesBase)`: `conflicto: str = "renombrar"` (|"mantener"
  |"reemplazar"), `criterio_reemplazo: str = "mas_reciente"` (|"mayor"|"menor"|
  "mas_antiguo"), `modo_codigo: str = "basename"` (|"id"|"personalizado", D3),
  `codigo_personalizado: str = ""`, **`crear_indice: bool = True`** (D9), 
  `omitir_ocultos: bool`, `seguir_enlaces: bool`, + `detallado`/`politica` heredados.
- `rutas_validadas(principal, fuentes)` → normaliza y comprueba existencia.
- `procesar(principal, fuentes, opts, *, callbacks)`:
  1. `recursos.preparar(principal, opts.politica, log)` (perfil + prioridad baja).
  2. Si `crear_indice` (D9): construye/actualiza el **índice de origen** (D1) del
     principal (registrando primero los archivos que ya tenía como origen=principal).
     Si NO se crea índice, se salta este paso y todo el registro por archivo → más
     rápido y sin espacio extra, pero el resultado **no será descombinable**.
  3. Por cada fuente (en orden): recorre su árbol y, por cada archivo, resuelve
     conflicto y copia; si `crear_indice`, anota metadatos (origen + ruta/nombre
     original) en el índice. Reanudable por índice (si se crea) como `Estado` en
     comprimir; sin índice, no reanudable por progreso fino.
  4. Paralelizable con `paralelo.PlanLista` si el destino es SSD (por archivo/
     subcarpeta independiente); en HDD, secuencial (lo decide `politica`/perfil).
- `ejecutar(entradas, opts, *, callbacks)`: `entradas={"principal","fuentes"}`.
- CLI con `comun.correr_cli`.

**`motor_descombinar.py`**
- `class Opciones(comun.OpcionesBase)`: `conservar_combinado: bool = True`,
  `sobrescribir: bool = False` + heredados.
- `procesar(combinado, destino, opts, *, callbacks)`: lee el índice; por cada
  entrada reconstruye `<destino>/<etiqueta_origen>/<ruta_original>` copiando el
  archivo (nombre original), saltando/avisando los ausentes. `ejecutar` con
  `entradas={"origen": combinado, "destino": destino}`. Anti-path-traversal como
  `_destino_seguro` (reutilizar la idea de `motor_descomprimir`).

**Índice de origen** (D1, formato propuesto): un JSON dentro del combinado, p. ej.
`.kakoli_combinacion.json`:
```
{ "formato": "kakoli-combinacion/1",
  "principal": "<ruta original del principal>",
  "origenes": { "principal": {"ruta": "...", "codigo": "..."},
                "d1": {"ruta": ".../dir2", "codigo": "dir2"}, ... },
  "archivos": { "<ruta relativa en el combinado>":
                {"origen": "d1", "ruta_original": "nivel1/nivel2/archivo.txt"} },
  "descartados": [ {"origen":"d1","ruta_original":"...","motivo":"reemplazado"} ] }
```
El índice se **excluye** de la fusión y de la reconstrucción, y hace la operación
**reanudable** y **portable**.

---

## 6. Diseño de la GUI (las dos pestañas)

**`PestanaCombinar(PestanaBase)`**
- `nombre="Combinar"`, `MOTOR=motor_combinar`, `produce="carpeta"`.
- `ENTRADAS = [Campo("principal","Directorio principal:","carpeta"),
  Campo("secundario","Directorio a combinar:","carpeta"),
  Campo("mas","Añadir más directorios (uno por línea):","lista")]` (H1).
- Opciones (secciones `LabelFrame`, helpers `_check`/`_combo`):
  - "Conflictos" → **Combobox** política (`Renombrar (por defecto)` / `Mantener el
    original` / `Reemplazar`) + **Combobox** criterio (relevante solo si
    "Reemplazar").
  - "Código de origen" (D3) → **Combobox**: `Nombre de la carpeta` (basename) /
    `Id corto estable` (`_d1`,`_d2`…) / `Personalizado`, + `Entry` de texto activo
    solo con "Personalizado".
  - "Filtros" → Omitir ocultos, (seguir enlaces).
  - "Reversibilidad" (D9) → **Checkbutton** "Crear índice para poder deshacer
    (Descombinar)", **activado por defecto**. Al desmarcarlo: más rápido y sin
    espacio extra (útil en procesos enormes que no se van a deshacer), pero el
    resultado **no será descombinable**.
- `_validar()`: principal + secundario + `valores_lista("mas")`; comprueba que
  **todas** existen (omite vacías) → `ValueError` si falta alguna; construye
  `Opciones`; devuelve `{"entradas": {"principal": ..., "fuentes": [...]}, "opts": …}`.
- `_confirmar(datos)` (avisos modales, H5/D9): avisa si la política es
  **reemplazar** (los originales descartados no se recuperan) y/o si **no se va a
  crear el índice** (no se podrá volver a las carpetas de origen). Si se dan ambos,
  un solo modal con las dos advertencias.

**`PestanaDescombinar(PestanaBase)`**
- `nombre="Descombinar"`, `MOTOR=motor_descombinar`.
- `ENTRADAS = [Campo("origen","Directorio combinado:","carpeta"),
  Campo("destino","Carpeta de salida:","carpeta_salida")]` (patrón clásico;
  autodestino como Descomprimir).
- Opciones: "Conservar el combinado", "Sobrescribir si el destino existe".
- `_validar()` comprueba que el combinado tiene índice (`.kakoli_combinacion.json`);
  si no, `ValueError` con ayuda ("no parece un directorio de Combinar").

**Registro y orden** (`App.MENU`, la primera):
```
MENU = ( Categoria("Combinación", [PestanaCombinar, PestanaDescombinar]),
         Categoria("Compresión",  [PestanaComprimir, PestanaDescomprimir]),
         Categoria("Eliminar",    [PestanaEliminar]) )
```
Nivel 2 de "Combinación": `[ ← ] [ Combinar ] [ Descombinar ]`. Handoff: al terminar
Combinar, `App.sugerir_entrada(ruta, "carpeta")` rellena el origen de Descombinar.

---

## 7. Decisiones (RESUELTAS por el usuario, 2026-09-06)

- **D1 — Reversibilidad → ÍNDICE JSON en la carpeta principal.** Un único
  `.kakoli_combinacion.json` guardado en el directorio principal (sin ADS). Es
  portable, atómico y viaja con el directorio (una copia del combinado sigue siendo
  descombinable). Es el único punto de verdad del undo.
- **D2 — IN SITU en el principal.** La fusión se hace *en* el directorio principal;
  **se documenta que el principal cambia**. Para preservar las fuentes, usar una
  carpeta vacía como principal. El índice permite deshacer.
- **D3 — Código de origen: TRES opciones (elegibles en la pestaña Combinar).**
  Un selector con: (a) **basename** de la fuente (p. ej. `_dir2`); (b) **id corto
  estable** (p. ej. `_d1`, `_d2`… asignado por orden); (c) **editado por el
  usuario** (campo de texto). Colisiones de código → sufijo numérico. El índice
  mapea código→ruta real.
- **D4 — Registrar TODOS los archivos del resultado** (incluidos los preexistentes
  del principal, con origen=principal), para poder reconstruir también el principal.
  Requiere un recorrido inicial del principal antes de fundir.
- **D5 — Reemplazo IRREVERSIBLE.** Con política "reemplazar", los perdedores se
  borran: `_confirmar` avisa (modal), el índice anota `descartados` y Descombinar
  informa de lo que no puede recuperar.
- **D6 — Handoff robusto (destino explícito).** No depender del orden: se añade al
  sistema un `produce_hacia` (clase de tarea destino) para que Combinar entregue su
  salida a **Descombinar** explícitamente. Es una mejora aditiva de `produce`/
  `App.sugerir_entrada` (beneficia a futuras parejas de tareas).
- **D7 — Paralelismo con serialización de conflictos.** Fusión por archivo/subárbol
  independiente con `paralelo.PlanLista` (SSD; secuencial en HDD según perfil),
  **serializando** la resolución de conflicto y la escritura del índice sobre el
  mismo destino (cerrojo por ruta destino o reparto por subárbol) para no corromper
  datos ni el índice.
- **D8 — Reanudable por índice.** Como el `Estado` de comprimir: si se corta, al
  relanzar se salta lo ya combinado (el índice registra el progreso).
- **D9 — Índice OPCIONAL (`crear_indice`, def. True).** Se puede desactivar la
  creación del índice para **ahorrar espacio y ganar velocidad** en procesos muy
  largos que generarían un índice enorme y que no se van a descombinar. Con el
  índice desactivado: no hay registro por archivo, la fusión es más rápida y ligera,
  pero **el resultado NO es descombinable** y no es reanudable por progreso fino;
  `_confirmar` avisa de que no se podrá volver a las carpetas de origen.

---

## 8. Fases

- **Fase 0 — Prototipo de motor (sin GUI).** `motor_combinar.py` +
  `motor_descombinar.py` mínimos por consola (`comun.correr_cli`): unión profunda +
  índice + las 3 políticas de conflicto (con criterios) + descombinar. Banco de
  pruebas de **round-trip**: combinar A+B → descombinar → comparar con A y B byte a
  byte (para "renombrar" y "mantener"; "reemplazar" solo comprueba coherencia). Es
  el equivalente a la Fase 0 de rendimiento: correctness primero.
  **ESTADO: HECHA** (2026-09-06). DOS motores independientes creados:
  `motor_combinar.py` (`Opciones(OpcionesBase)` con `conflicto`/`criterio_reemplazo`/
  `modo_codigo`/`codigo_personalizado`/`crear_indice`/`omitir_ocultos`/
  `seguir_enlaces`; `rutas_validadas(principal, fuentes)`; `procesar` = fusión in
  situ + índice `.kakoli_combinacion.json` + snapshot del principal (D4) +
  renombrar/mantener/reemplazar + reanudable por índice + `_walk_rel`/`_copiar`
  (copy2, .part+replace)/`_codigos`(D3)/`_gana_entrante`; `cargar_indice`/
  `guardar_indice`; `ejecutar`+`main`+`correr_cli` con avisos de reemplazo/sin-índice)
  y `motor_descombinar.py` (lee el índice — importa `INDICE_NOMBRE`/`cargar_indice`
  de motor_combinar, como descomprimir↔comprimir con leer_marca; reconstruye una
  carpeta por origen con nombres originales; `_destino_seguro` anti-traversal;
  `_etiquetas` únicas). Verificado test_combinar (18/18): unión profunda (ejemplos
  del enunciado), round-trip A/B byte a byte (renombrar), las 3 políticas, multi-
  fuente + validación (todas deben existir), y D9 sin-índice (no descombinable). CLIs
  end-to-end OK. La app principal (kakoli) no se toca (motores independientes).
- **Fase 1 — Metadatos/índice (D1).** Formato, escritura atómica (`.part`+replace),
  exclusión del índice, portabilidad; (opcional) ADS en Windows.
- **Fase 2 — Campo "lista" (H1).** Extender `Campo`/`_construir`/`valor` con el tipo
  `lista` (botón + `Text` multilínea) y `valores_lista(clave)`; test headless.
  **ESTADO: HECHA** (2026-09-06). `Campo(tipo="lista")` (sin cambios en la dataclass;
  el tipo es un string). En `PestanaBase`: `vars_entrada` ya NO crea StringVar para
  los campos `lista`; nuevo `self._widgets_lista` (clave→`tk.Text`). El bucle de
  selectores desvía los `lista` a `_construir_campo_lista(top, campo, r)`: un botón
  "▸ Escribir rutas (una por línea)" que despliega/oculta (`_toggle_lista`) un `Text`
  (oculto de inicio, `wrap="char"`, estilo de consola) + un "Examinar…" que añade una
  carpeta (`_anexar_carpeta`, abre la caja si estaba cerrada). `valores_lista(clave)`
  → líneas no vacías y recortadas. `Text` y sus botones entran en `_bloqueables`
  (se deshabilitan durante una tarea). Verificado test_campo_lista (Text oculto→
  visible al pulsar, omite vacías/recorta, `_validar` combina secundario+lista en
  `fuentes`) + regresión GUI sin cambios. Ampliación aditiva del sistema E.
- **Fase 3 — Pestañas + categoría.** `PestanaCombinar`/`PestanaDescombinar`
  (declarativas: `ENTRADAS`, opciones `_check`/`_combo`, `_validar`, `_confirmar`,
  `produce`); `Categoria("Combinación", …)` **la primera** en `App.MENU`.
  **ESTADO: HECHA** (2026-09-06). kakoli importa `motor_combinar as mcombi` /
  `motor_descombinar as mdescombi`. `PestanaCombinar` (nombre="Combinar",
  MOTOR=mcombi, produce="carpeta", ENTRADAS = principal/secundario carpeta +
  `mas` tipo "lista"; opciones en secciones: "Conflictos" (Combobox política + de
  criterio, éste habilitado solo si "Reemplazar"), "Código de origen" (Combobox D3 +
  Entry "Personalizado" habilitado solo con esa opción), "Filtros" (omitir ocultos),
  "Reversibilidad" (checkbox crear índice, D9); `_validar` construye fuentes =
  secundario + `valores_lista("mas")`, valida con `mcombi.rutas_validadas` (todas
  deben existir); `_confirmar` avisa si reemplazar y/o sin índice). `PestanaDescombinar`
  (nombre="Descombinar", MOTOR=mdescombi, ENTRADAS origen/destino, `_destino_automatico`
  = `<combinado>_descombinado`, opción sobrescribir; `_validar` con
  `mdescombi.rutas_validadas` que exige índice). `App.MENU` = **(Combinación,
  Compresión, Eliminar)** → nivel 2 de Combinación: `[ ← ] [ Combinar ] [ Descombinar ]`.
  Handoff Combinar→Descombinar por `produce="carpeta"` (Descombinar es el 1er
  consumidor tras Combinar). Verificado: test_combinar_gui (combinar por la GUI →
  índice → handoff → descombinar round-trip A/B byte a byte), habilitación dinámica
  de criterio/personalizado, y regresión completa (4 tests de scratchpad ajustados al
  nuevo nº/orden de pestañas). GOTCHA: ttk.Combobox NO tiene `command`; usar
  `bind("<<ComboboxSelected>>")`.
- **Fase 4 — Conflictos + aviso + handoff.** Combobox de política + criterio (con
  su lógica en el motor), aviso modal de "reemplazar" (H5), handoff Combinar→
  Descombinar (D6).
  **ESTADO: HECHA** (2026-09-06). Los Combobox de conflicto/criterio/código y su
  lógica en el motor + el aviso modal (reemplazar/sin-índice en `_confirmar`) ya
  quedaron en Fase 3. Aquí se añadió el **handoff robusto (D6)**: nuevo atributo
  `PestanaBase.produce_hacia` (clase de la pestaña consumidora); `App.sugerir_entrada`
  admite `destino=` y, si se da, entrega directamente ahí (si no, cae al primer
  consumidor por tipo, como antes); `_fin` pasa `destino=self.produce_hacia`. Fijados
  `PestanaComprimir.produce_hacia = PestanaDescomprimir` y
  `PestanaCombinar.produce_hacia = PestanaDescombinar` (asignados tras las clases,
  para evitar referencias hacia delante). Verificado: destino explícito entrega a la
  pestaña indicada aunque NO sea la primera del tipo; el fallback por tipo sigue;
  test_g/test_combinar_gui (handoffs) OK.
- **Fase 5 — Rendimiento.** Paralelizar con `PlanLista` (D7), reanudable (D8),
  buffers de copia adaptativos (como descomprimir); respetar el perfil/hilos común.
  **ESTADO: HECHA** (2026-09-06). `motor_combinar.procesar` refactorizado: el trabajo
  por archivo se extrajo a `_combinar_uno(item)`; `perf = recursos.preparar(...)` +
  `n = recursos.calcular_hilos(perf, politica, unidades)` deciden secuencial (n<=1,
  HDD/pocos núcleos) o **paralelo** (`paralelo.PlanLista(items)` + `paralelo.Ejecutor(n)
  .ejecutar(plan, _combinar_uno, debe_pausar, limite_activos=regulador_carga…)`,
  throttling incluido). Serialización D7: un **cerrojo por ruta de destino**
  (`_lock_ruta(rel)`, solo se serializan items del MISMO destino → detección de
  conflicto + copia atómicas) + un **cerrojo de índice** (`ilock`) para las
  mutaciones del índice/contadores/errores y el `guardar_indice` periódico. Reanudable
  (D8): los items ya hechos se saltan al construir la lista (`_procesados`). Verificado
  test_combinar_par (paralelo n=4, 135 items: todos una vez, índice coherente sin
  descartes, round-trip A/B/C byte a byte con colisiones cruzadas, y **paralelo ==
  secuencial**). El secuencial (test_combinar 18/18) y la GUI siguen OK. (Buffers
  adaptativos de copia: `shutil.copy2` ya es eficiente; no se añadió buffer manual.)
- **Fase 6 — Verificación y docs.** Round-trip byte a byte (combinar↔descombinar);
  pruebas de conflictos (renombrar/mantener/reemplazar×criterios); casos límite
  (principal vacío, colisiones de código, ocultos, unicode, enlaces, índice
  ausente/corrupto, combinado copiado a otro sitio). Actualizar `ARQUITECTURA.md`,
  `GUI.md`, `escalabilidad.md` y `bench.py` (nuevo escenario de merge).
  **ESTADO: HECHA** (2026-09-06). Verificación: test_combinar (18/18 secuencial),
  test_combinar_par (paralelo n=4, round-trip + paralelo==secuencial),
  test_combinar_edge (principal vacío, unicode, combinado copiado a otro sitio,
  índice corrupto rechazado, colisión de códigos), test_combinar_gui (round-trip por
  la GUI + handoff), y toda la regresión de la app. `bench.py`: nuevo modo `--merge`
  (combinar dos árboles → descombinar → round-trip byte a byte a nivel de archivo);
  `bench --merge --todos` = 5/5 (secuencial y con `--hilos 4`). Docs: `ARQUITECTURA.md`
  §2 (motores combinar/descombinar + cadena de imports) y §7 (MENU con Combinación +
  tipo de Campo `lista`); `GUI.md` §2 (tipo `lista`) y **§5b** (Combinar/Descombinar
  con sus selectores y opciones); `escalabilidad.md` (validación del sistema con la
  categoría Combinación).

---

## CATEGORÍA "COMBINACIÓN" — COMPLETA (fases 0–6)

Dos tareas nuevas (Combinar/Descombinar) con motores independientes, integradas en
la categoría "Combinación" (la primera del menú), siguiendo A–H + el menú de dos
niveles. Fusión profunda in situ con índice JSON reversible, 3 políticas de
conflicto (código de origen configurable), opción de índice (D9), handoff explícito
(D6), paralelismo serializado (D7), reanudable (D8). Round-trip byte a byte verde.

Orden recomendado: 0 → 1 → 2 → 3 → 4 → 5 → 6 (motor y correctness antes que GUI).

---

## 9. Riesgos y notas

- **Reversibilidad real** depende del índice: si el usuario borra
  `.kakoli_combinacion.json`, Descombinar no puede operar (avisar; el nombre con
  código de origen da una pista parcial, pero no reconstruye el principal).
- **"Reemplazar" destruye datos**: exigir confirmación explícita (D5) y anotar
  descartados.
- **In situ** modifica el principal (D2): documentarlo; ofrecer usar una carpeta
  vacía como principal si se quiere preservar las fuentes.
- **Concurrencia de conflictos** (D7): serializar la resolución sobre el mismo
  destino para no corromper el índice.
- **Recombinar** un directorio ya combinado (índices anidados): definir política
  (rechazar, o combinar índices). Marcar como caso límite de la Fase 6.
- **No romper A–H ni el menú**: las dos pestañas son declarativas y se registran en
  `App.MENU`; el único cambio transversal es el nuevo tipo de `Campo` (H1/Fase 2),
  que es una ampliación aditiva del sistema y sirve para futuras tareas con N
  entradas.
