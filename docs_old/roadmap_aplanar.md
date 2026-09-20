# Roadmap: categoría "Aplanado" — pestañas Aplanar / Desaplanar

Objetivo: dos tareas nuevas y complementarias (motores independientes) que
**aplanan** un árbol de directorios (todos los archivos a una sola carpeta) y lo
**deshacen** (reconstruyen el árbol), agrupadas en una categoría nueva
**"Aplanado"**.

Este documento **solo diseña y analiza**: no toca código. Se apoya en el sistema
real de pestañas (escalabilidad A–H + menú de dos niveles) y en la pareja ya hecha
Combinar/Descombinar. Referencias: `escalabilidad.md`, `roadmap_menu_pestanas.md`,
`roadmap_combinar.md`, `ARQUITECTURA.md`, `GUI.md`.

Fecha: 2026-09-07.

---

## 1. Semántica de Aplanar

**Entrada**: un **directorio origen** (con su árbol) + una **carpeta de salida**.
**Resultado**: la carpeta de salida contiene **todos los archivos** del árbol,
**sin subcarpetas** (un solo nivel).

Para cada archivo en la ruta relativa `nivel1/nivel2/archivo.txt` hay **dos modos
de nombrado** (A3):

- **Solo el nombre final** (por defecto): se guarda como `archivo.txt`. Es el modo
  natural pero **propenso a colisiones** (dos `archivo.txt` en subcarpetas distintas
  chocan). Aquí es donde importa la política de conflicto (A4).
- **Incluir la ruta en el nombre** (con `-`): se guarda como
  `nivel1-nivel2-archivo.txt`. Los niveles de carpeta se unen al nombre con el
  separador `-`. Este modo es **el que permite desaplanar** después (§2), porque la
  ruta queda codificada en el nombre.

**Ejemplo del enunciado**: `nivel1/nivel2/archivo.txt` → (modo ruta) →
`nivel1-nivel2-archivo.txt` dentro de la carpeta de destino.

**Conflictos** (dos archivos aterrizan con el mismo nombre en el destino) — opción
`conflicto`, con las mismas políticas que Combinar (A4):
- **Renombrar (por defecto)**: se conservan ambos añadiendo un sufijo distintivo
  (ver A4: sufijo numérico `_2`, `_3`… o el nombre de la carpeta padre). Nadie se
  pierde.
- **Mantener el primero**: se omite el segundo (se queda el que llegó antes).
- **Reemplazar por criterio**: gana mayor / menor / más reciente / más antiguo; el
  perdedor **se descarta** → **NO reversible** para ese archivo (aviso modal, A8).

En **modo "incluir la ruta"** los choques son rarísimos (la ruta relativa completa
es única), salvo cuando un nombre real ya contiene el separador `-` (ver §2, misma
raíz que la ambigüedad de desaplanar); la política de conflicto sigue siendo la red
de seguridad.

---

## 2. Semántica de Desaplanar (y su ambigüedad inherente)

**Entrada**: una **carpeta aplanada** (plana, un solo nivel) + una **carpeta de
salida**. **Resultado**: se reconstruye el árbol **únicamente a partir de los
nombres de archivo**, partiéndolos por el separador `-`:

`nivel1-nivel2-archivo.txt` → `nivel1/nivel2/archivo.txt`.

El **último segmento** tras partir por `-` es el nombre del archivo (con su
extensión); los segmentos anteriores son las carpetas. Un archivo **sin `-`** (p. ej.
`archivo.txt`) no tiene ruta codificada → **se queda en la raíz** del destino.

**Decisión de diseño clave del usuario**: *"la única forma de construir el árbol es
a partir de los nombres de los archivos, usando `-`"*. Por tanto Desaplanar **NO usa
un índice** (a diferencia de Descombinar): es una reconstrucción **heurística por
convención de nombre**, no un undo perfecto con metadatos. Consecuencias que hay que
documentar y avisar:

- **Ambigüedad con guiones literales**: si un nombre o carpeta original ya contenía
  `-`, Desaplanar no puede distinguir separador de guion real. `mi-informe.txt`
  (archivo suelto en la raíz) se reconstruiría como `mi/informe.txt`. Es una
  limitación **fundamental** del método, no un bug.
- **Solo el modo "incluir la ruta" es reconstruible**: los archivos aplanados con
  "solo el nombre final" no llevan ruta y quedarán en la raíz al desaplanar (lo
  esperado). El par Aplanar↔Desaplanar es round-trip **solo** cuando se aplanó en
  modo ruta y ningún nombre contenía `-`.
- **Sufijos de renombrado** (`_2`) introducidos al aplanar quedarían pegados al
  último segmento (`archivo_2.txt`): el árbol se reconstruye, pero el nombre lleva el
  sufijo. Aceptable y esperable (no había índice para revertirlo).

Desaplanar **no borra** la carpeta aplanada; produce el árbol reconstruido en un
destino (por defecto, al lado).

---

## 3. Encaje en el sistema (qué se reutiliza, qué es nuevo)

A diferencia de Combinar (que necesitó el `Campo` tipo `lista`, H1), **esta pareja
NO necesita ninguna primitiva de GUI nueva**. Es una buena validación adicional de la
escalabilidad A–H: se resuelve con **motor + pestaña declarativa + una línea en
`App.MENU`**.

**Encaja sin cambios**:
- `Campo` tipos `carpeta` + `carpeta_salida` (los dos campos de cada pestaña).
- Opciones declarativas `_seccion` / `_check` / `_combo`.
- Contrato de motor `ejecutar(entradas, opts, *, callbacks)` + `comun.correr_cli`.
- `recursos.preparar` / `calcular_hilos` / `paralelo.PlanLista` (paralelizar por
  archivo, cada archivo es una unidad independiente).
- `_confirmar(datos)` modal para el aviso de "reemplazar" (como Eliminar/Combinar).
- Handoff por tipo + `produce_hacia` (D6 de combinar): Aplanar→Desaplanar.
- Monitor compartido, Rendimiento común (`v_hilos`/`v_ligero`), bloqueo 1‑tarea,
  barra inferior con estados de color.

**Lo único genuinamente nuevo** son las **utilidades de transformación de nombre**
dentro de los motores:
- `aplanar_nombre(rel, sep)` : `nivel1/nivel2/archivo.txt` → `nivel1-nivel2-archivo.txt`.
- `desaplanar_nombre(nombre, sep)` : inverso (último segmento = archivo).
No hay huecos transversales que abrir en el framework de pestañas.

---

## 4. Diseño de los motores (independientes)

**`motor_aplanar.py`**
- `class Opciones(comun.OpcionesBase)` (hereda `detallado` + `politica`):
  - `modo_nombre: str = "ruta"` (`ruta` | `final`) — A3 (por defecto incluir ruta).
  - `separador: str = "-"` — A2.
  - `conflicto: str = "renombrar"` (`renombrar` | `mantener` | `reemplazar`) — A4.
  - `criterio_reemplazo: str = "mas_reciente"` (`mayor`|`menor`|`mas_reciente`|`mas_antiguo`).
  - Renombrado (A4): **carpeta padre** + sufijo numérico de respaldo (fijo, sin opción).
  - `omitir_ocultos: bool = False`, `seguir_enlaces: bool = False`.
  - (A1: siempre **copia**; no hay opción de mover.)
- `rutas_validadas(origen, destino)`: origen existe y es carpeta; destino se crea;
  origen ≠ destino y no contenidos mutuamente (evitar recursión al aplanar sobre sí).
- `procesar(origen, destino, opts, *, callbacks)`:
  1. `recursos.preparar(origen, opts.politica, log)`.
  2. Recorre el árbol (`os.walk`, salta ocultos/enlaces según opts) → lista de
     archivos (unidades independientes).
  3. Por cada archivo calcula el nombre destino (`aplanar_nombre` en modo ruta, o
     basename en modo final), resuelve conflicto (renombrar/mantener/reemplazar) y
     copia/mueve (`shutil.copy2`/`move`, `.part`+replace atómico como en combinar).
  4. Paraleliza con `paralelo.PlanLista` si el perfil lo aconseja (SSD), **serializando
     la resolución de colisión + escritura sobre el mismo nombre destino** (cerrojo por
     nombre destino, como el `_lock_ruta` de combinar, D7) para no pisar dos archivos
     a la vez. Contadores compartidos bajo `ilock`.
  5. `Resultado` uniforme (`comun.Resultado`): copiados/renombrados/mantenidos/
     reemplazados, errores, destino, duración.
- `ejecutar(entradas={"origen","destino"}, opts, *, callbacks)` + `main` con
  `comun.correr_cli` (avisos de reemplazo/mover).

**`motor_desaplanar.py`**
- `class Opciones(comun.OpcionesBase)`:
  - `separador: str = "-"` (debe coincidir con el usado al aplanar).
  - `conflicto: str = "renombrar"` (por si dos nombres reconstruyen la misma ruta).
  - `sobrescribir: bool = False`, `omitir_ocultos: bool = False`.
- `procesar(origen, destino, opts, *, callbacks)`:
  1. Recorre la carpeta aplanada (idealmente plana; si hubiera subcarpetas se
     recorren igual y su ruta real se antepone, o se ignora — ver A6).
  2. Por cada archivo: `desaplanar_nombre` (partir por `sep`; último = archivo, resto
     = carpetas). **Anti-path-traversal** en cada segmento (reutilizar la idea de
     `_destino_seguro` de `motor_descomprimir`/`motor_descombinar`): rechazar `..`,
     rutas absolutas, unidades.
  3. Copia a `<destino>/<carpetas reconstruidas>/<archivo>`; resuelve colisión.
  4. Paralelizable igual que aplanar.
  5. `Resultado` uniforme + aviso de que la reconstrucción depende de la convención
     de nombres (ambigüedad con `-` literal).
- `ejecutar(entradas={"origen","destino"}, opts, *, callbacks)` + `main`.

**Sin índice** (contraste con combinar): la simetría Aplanar↔Desaplanar es por
**convención de nombre**, no por metadatos. `motor_desaplanar` **no importa nada** de
`motor_aplanar` salvo, opcionalmente, la pareja de utilidades `aplanar_nombre`/
`desaplanar_nombre` y el separador por defecto (para mantenerlos en un solo sitio).

---

## 5. Diseño de la GUI (las dos pestañas)

**`PestanaAplanar(PestanaBase)`**
- `nombre="Aplanar"`, `MOTOR=motor_aplanar`, `produce="carpeta"`,
  `produce_hacia=PestanaDesaplanar` (handoff explícito, D6).
- `ENTRADAS = [Campo("origen","Directorio a aplanar:","carpeta"),
  Campo("destino","Carpeta de salida:","carpeta_salida")]` (patrón clásico;
  autodestino `<origen>_aplanado`, como Descomprimir/Descombinar).
- Opciones (secciones `LabelFrame`, `_check`/`_combo`):
  - "Nombre" → **Combobox** modo: `Incluir la ruta en el nombre (con -)` (por
    defecto) / `Solo el nombre final`, + **`Entry` "Separador de niveles:"** (texto
    libre, por defecto `-`, uno o varios caracteres, A2). Se valida en `_validar`
    (`separador_ok`); en modo "solo nombre final" queda inerte (se puede atenuar).
  - "Conflictos" → **Combobox** política (`Renombrar` / `Mantener el primero` /
    `Reemplazar`) + **Combobox** criterio (activo solo con "Reemplazar"). El
    renombrado es fijo (carpeta padre + numérico, A4): sin combobox.
  - "Filtros" → Omitir ocultos, (seguir enlaces).
- `_validar()`: origen + destino; `Opciones`; devuelve
  `{"entradas": {"origen":…, "destino":…}, "opts": …}`.
- `_confirmar(datos)`: aviso modal si la política es **reemplazar** (descartes
  irrecuperables). Recordatorio de que el modo "solo nombre final" **no será
  desaplanable**.

**`PestanaDesaplanar(PestanaBase)`**
- `nombre="Desaplanar"`, `MOTOR=motor_desaplanar`.
- `ENTRADAS = [Campo("origen","Carpeta aplanada:","carpeta"),
  Campo("destino","Carpeta de salida:","carpeta_salida")]` (autodestino
  `<origen>_desaplanado`).
- Opciones: **`Entry` "Separador de niveles:"** (texto libre, por defecto `-`, uno o
  varios caracteres, A2 — debe coincidir con el usado al aplanar); "Sobrescribir si el
  destino existe"; "Conflictos" (renombrar/mantener/reemplazar) por si dos nombres
  reconstruyen la misma ruta.
- `_validar()`: origen es carpeta con archivos; `Opciones`.
- `_confirmar(datos)` **o** aviso estático: recordar la **ambigüedad** — el árbol se
  deduce de los nombres partiendo por `-`; los nombres con `-` literal pueden
  reconstruir carpetas no deseadas.

**Registro y orden** (`App.MENU`, A7):
```
MENU = ( Categoria("Combinación", [PestanaCombinar,  PestanaDescombinar]),
         Categoria("Compresión",  [PestanaComprimir, PestanaDescomprimir]),
         Categoria("Aplanado",    [PestanaAplanar,   PestanaDesaplanar]),
         Categoria("Eliminar",    [PestanaEliminar]) )
```
Posición de "Aplanado" **a decidir** (A7); propuesta: tras "Compresión" y antes de
"Eliminar". Nivel 2: `[ ← ] [ Aplanar ] [ Desaplanar ]`. Handoff: al terminar
Aplanar, `App.sugerir_entrada(ruta, "carpeta", destino=PestanaDesaplanar)` rellena
el origen de Desaplanar.

---

## 6. Decisiones (RESUELTAS por el usuario, 2026-09-07)

- **A1 — Copiar (NO mover).** Aplanar **copia** al destino; el origen se conserva
  intacto. No hay opción "mover" (se descarta para simplificar y evitar destrucción).
- **A2 — Separador `-`, configurable y compartido.** **Campo de texto editable en
  AMBAS pestañas** (Aplanar y Desaplanar), por defecto `-`. Admite **uno o varios
  caracteres** (p. ej. `-`, `__`, `::`). Aplanar y Desaplanar deben usar el mismo
  texto para que el round-trip funcione. Validación (`motor_aplanar.separador_ok`,
  reutilizada por desaplanar): no puede estar **vacío** ni contener **`/`** o **`\`**
  (romperían los nombres); en modo "solo nombre final" el separador no se usa y no se
  valida. `_validar` de cada pestaña hace la pre-comprobación con un mensaje claro.
- **A3 — Modo de nombre por defecto = "Incluir la ruta en el nombre" (con `-`).** El
  otro modo ("Solo el nombre final") queda como alternativa. Por defecto el resultado
  es **desaplanable**.
- **A4 — Renombrado en colisión = por carpeta padre.** El entrante que choca se
  renombra añadiendo el **nombre de la carpeta padre** (`archivo_nivel2.txt`); si aún
  colisiona, sufijo **numérico** de respaldo (`archivo_nivel2_2.txt`). Sin combobox de
  estrategia: carpeta padre + numérico de respaldo.
- **A5 — Desaplanar sin índice** (solo por nombres, partiendo por el separador).
  **Confirmado.** Se documenta la ambigüedad y se avisa en la GUI.
- **A6 — Entrada de Desaplanar robusta**: se recorre lo que haya y se reconstruye
  usando solo el **nombre de archivo** (basename) de cada fichero.
- **A7 — Categoría "Aplanado" tras "Compresión"** (orden **Combinación / Compresión /
  Aplanado / Eliminar**). **Confirmado.**
- **A8 — "Reemplazar" irreversible** → aviso modal (como D5 de combinar). Los
  perdedores se descartan sin recuperación.

---

## 7. Fases

- **Fase 0 — Prototipo de motor (sin GUI).** `motor_aplanar.py` +
  `motor_desaplanar.py` mínimos por consola (`comun.correr_cli`): recorrido + los dos
  modos de nombre + las 3 políticas de conflicto (con criterios) + `aplanar_nombre`/
  `desaplanar_nombre`. Banco de pruebas **round-trip**: aplanar (modo ruta) →
  desaplanar → comparar con el árbol original byte a byte (para nombres sin `-`
  literal); casos de colisión (modo "solo final") con renombrar/mantener/reemplazar.
  Cada proceso su **propio motor** (uno aplanar, otro desaplanar).
  **ESTADO: HECHA** (2026-09-07). DOS motores independientes:
  `motor_aplanar.py` (`Opciones(OpcionesBase)` con `modo_nombre` [ruta/final, def.
  ruta], `separador` [def. `-`], `conflicto`, `criterio_reemplazo`, `omitir_ocultos`,
  `seguir_enlaces`; SIEMPRE copia [A1]; `aplanar_nombre(rel, sep)`; `rutas_validadas`
  [impide destino dentro de origen]; `procesar` = recorrido + nombre destino por modo
  + renombrar por **carpeta padre** + numérico de respaldo [A4] / mantener / reemplazar
  por criterio + `_copiar` (.part+replace); reanudable de facto por existencia en
  destino) y `motor_desaplanar.py` (`desaplanar_nombre(nombre, sep)` = partir por sep,
  último=archivo, resto=carpetas, **anti path-traversal** [`_sanea_seg` + `_destino_
  seguro`]; A6: recorre lo que haya y usa el basename; conflicto renombrar[numérico]/
  mantener/reemplazar; sin índice [A5]). Verificado test_aplanar (25/25): transformación
  de nombre (ida/vuelta, sep custom, quita `..`), **round-trip byte a byte** (modo ruta,
  y con sep `~`), colisiones modo final (renombrar por carpeta padre / mantener /
  reemplazar-mayor), archivo sin sep → raíz, con sep → subcarpeta. CLIs end-to-end OK.
  La app principal (kakoli) no se toca (motores independientes).
  **Separador multi-carácter + validación** (2026-09-07, A2): `separador` es texto
  libre de uno o varios caracteres; `motor_aplanar.separador_ok(sep)` (reutilizado por
  desaplanar) rechaza vacío o con `/`/`\`; `procesar` devuelve `Resultado("error", …)`
  si el separador es inválido (en aplanar solo en modo ruta; en desaplanar siempre; en
  modo "final" el separador no se usa). Verificado (test_aplanar 32/32): round-trip con
  sep `__` (multi), y separador inválido → error sin escribir / ignorado en modo final.
- **Fase 1 — Transformación de nombres.** Definir y probar `aplanar_nombre` /
  `desaplanar_nombre` con el separador; casos límite (nombres con `-`, extensiones
  compuestas `.tar.gz`, unicode, nombre sin `-`, separador multichar). Documentar la
  ambigüedad. Anti-path-traversal en desaplanar.
  **ESTADO: HECHA** (2026-09-07). Test unitario dedicado test_aplanar_nombres (39/39)
  que consolida y amplía: `aplanar_nombre` (profunda/raíz/**ext compuesta `.tar.gz`**/
  sep multi `__` y `::`/unicode/segmento vacío); `desaplanar_nombre` (inversa, sin sep→
  raíz, sep multi, unicode, ext compuesta, recorte de vacíos en bordes/dobles, **quita
  `..`**, neutraliza **`C:`/ADS `nombre:flujo`** y `\`, archivo degenerado `..`→`_`);
  **propiedad de ida y vuelta** de los nombres para varios separadores (`-`/`__`/`::`/
  `|`); `separador_ok` (acepta `-`/`__`/`::`/`|`/`.`/` - `; rechaza vacío y `/`/`\`);
  `_destino_seguro` (backstop léxico: bloquea `../fuera.txt` y `a/../../fuera.txt`); y
  la ext compuesta en modo final+renombrar (colisión `backup.tar.gz` → `backup.tar_p2.gz`).
  **Endurecido** `motor_desaplanar._sanea_seg`: además de `/` y `\`, neutraliza `:` en
  los segmentos de carpeta (evita unidad/ADS en Windows), como defensa en profundidad
  sobre `_destino_seguro`. Ambigüedad ya documentada en la ayuda de Desaplanar (GUI) y
  en §2/§8.
- **Fase 2 — Pestañas + categoría.** `PestanaAplanar` / `PestanaDesaplanar`
  (declarativas: `ENTRADAS`, opciones `_combo`/`_check`, `_validar`, `_confirmar`,
  `produce`/`produce_hacia`); `Categoria("Aplanado", …)` en `App.MENU` (posición A7).
  **No requiere primitivas nuevas de GUI** (solo `carpeta`/`carpeta_salida`).
  **ESTADO: HECHA** (2026-09-07). kakoli importa `motor_aplanar as maplan` /
  `motor_desaplanar as mdesaplan`. `PestanaAplanar` (nombre="Aplanar", MOTOR=maplan,
  produce="carpeta", origen/destino clásicos + `_destino_automatico`=`<origen>_aplanado`;
  secciones: "Nombre de los archivos" (Combobox modo `_MODOS_NOMBRE` [ruta def/final] +
  **Entry "Separador de niveles:"** def `-`, que se atenúa en modo final vía
  `_actualizar_modo`), "Conflictos" (Combobox `_POLITICAS_APLANAR` + criterio `_CRITERIOS`
  habilitado solo si reemplazar), "Filtros" (omitir ocultos); `_validar` valida el
  separador con `maplan.separador_ok` solo en modo ruta; `_confirmar` avisa si reemplazar
  y/o modo final). `PestanaDesaplanar` (nombre="Desaplanar", MOTOR=mdesaplan, origen/
  destino, `_destino_automatico`=`<origen>_desaplanado`; secciones "Reconstrucción del
  árbol" (**Entry separador** def `-` + ayuda sobre la ambigüedad), "Conflictos"
  (`_POLITICAS_DESAPLANAR`), "Filtros"; `_validar` valida el separador siempre).
  `App.MENU`=(Combinación, Compresión, **Aplanado**, Eliminar) → 7 tareas; nivel 2 de
  Aplanado: `[ ← ] [ Aplanar ] [ Desaplanar ]`. Handoff explícito
  `PestanaAplanar.produce_hacia=PestanaDesaplanar`. `rutas_validadas` de ambos motores
  ahora acepta `destino=None` (autodestino, como descombinar). Verificado test_aplanar_gui
  16/16 (orden MENU, separador `-` por defecto en ambas, atenuado dinámico modo/criterio,
  `_validar` arma Opciones + rechaza separador `/`, **round-trip por la GUI con sep `__`:
  aplanar→handoff→desaplanar byte a byte**) + regresión completa (test_gui_fase5 ajustado
  al 4º corchete `[ Aplanado ]`). Sin primitivas GUI nuevas (solo carpeta/carpeta_salida).
- **Fase 3 — Conflictos + avisos + handoff.** Combobox política/criterio/renombrado y
  su lógica en el motor; aviso modal de "reemplazar"/"mover" (A1/A8); recordatorio de
  ambigüedad en Desaplanar; handoff Aplanar→Desaplanar (`produce_hacia`).
  **ESTADO: HECHA** (2026-09-07). El grueso (Combobox política+criterio, lógica en el
  motor, `_confirmar` con avisos, ayuda de ambigüedad en Desaplanar, `produce_hacia`)
  ya se implementó en la Fase 2; aquí se **verificó end-to-end por la GUI** con
  test_aplanar_conf (11/11): (A) los 4 casos de `_confirmar` — renombrar+ruta sin
  modal; reemplazar avisa "no se podrán recuperar"; modo final avisa "no se podrá
  desaplanar"; reemplazar+final avisa de ambas; (B) las **3 políticas reales por la
  GUI** en modo final — renombrar (2 archivos, uno con la carpeta padre), mantener (un
  solo archivo, sin renombrados), reemplazar por "mayor" (gana el mayor, determinista);
  (C) la ayuda de ambigüedad presente en Desaplanar; (D) handoff explícito
  `produce_hacia=PestanaDesaplanar` (Desaplanar recibe la carpeta aplanada). No había
  "mover" (A1: siempre copia), así que no hay aviso de mover.
- **Fase 4 — Rendimiento.** Paralelizar con `PlanLista` (unidad = archivo),
  serializando la escritura por nombre destino (cerrojo por nombre, como combinar
  D7); respetar perfil/hilos común; comprobar paralelo == secuencial.
  **ESTADO: HECHA** (2026-09-07). `motor_aplanar` y `motor_desaplanar` importan
  `threading`+`paralelo`; `procesar` extrae el trabajo por archivo a `_aplanar_uno(rel)`
  / `_desaplanar_uno(src)`; `perf = recursos.preparar(...)` + `n = recursos.calcular_hilos(
  perf, politica, unidades=total)` deciden secuencial (n<=1) o **paralelo**
  (`paralelo.PlanLista(items)` + `paralelo.Ejecutor(n).ejecutar(plan, _fn, debe_pausar,
  limite_activos=regulador_carga si throttling)`). Serialización D7: en aplanar un
  **cerrojo por NOMBRE de destino** (`_lock_nombre`, el nombre plano es el dominio de
  colisión → detección de conflicto + `_renombrar` + copia atómicas por grupo de
  colisión); en desaplanar un **cerrojo por RUTA reconstruida** (`_lock_rel`, para que
  `_sin_colision` + copia sean atómicos); en ambos un `ilock` para contadores/errores/
  progreso. Pausa: para limpiamente (Resultado "pausado"); sin índice (A5) no hay
  reanudado fino, al continuar se re-procesa. Verificado test_aplanar_par (13/13, con
  `PoliticaHilos(hilos=4)` forzando 4 hilos reales — confirmado por el log del motor):
  modo ruta **paralelo == secuencial (snapshots idénticos)**, round-trip paralelo byte
  a byte, desaplanar paralelo==secuencial, y modo final con 40 colisiones
  (renombrar) → multiset de contenidos idéntico seq/par y ninguno perdido, reemplazar
  "mayor" determinista. Secuencial (test_aplanar 32/32), GUI (16/16) y conflictos
  (11/11) siguen verdes.
- **Fase 5 — Verificación y docs.** Round-trip byte a byte (modo ruta, sin `-`
  literal); colisiones (renombrar/mantener/reemplazar×criterios); casos límite
  (nombres con `-`, unicode, ocultos, enlaces, destino existente,
  path-traversal en desaplanar). Actualizar `ARQUITECTURA.md`, `GUI.md`,
  `escalabilidad.md` y `bench.py` (nuevo escenario `--flatten`).
  **ESTADO: HECHA** (2026-09-07). Verificación: test_aplanar (32/32), test_aplanar_par
  (25/25, con **estrés de concurrencia** hilos=8 en árbol profundo × varias corridas:
  0 errores, sin pérdidas), test_aplanar_conf (11/11), test_aplanar_edge (15/15:
  unicode, ocultos, ambigüedad `-`, **path-traversal**, destino no vacío, enlaces), y
  toda la regresión (combinar + GUI). `bench.py`: nuevo modo **`--flatten`** (aplanar
  modo ruta → desaplanar → round-trip byte a byte por archivo); `bench --flatten
  --todos` = 5/5 secuencial y con `--hilos 4`. **BUG de concurrencia cazado y
  corregido**: `motor_desaplanar._destino_seguro` usaba `Path.resolve()` (toca el disco)
  y daba falsos positivos bajo paralelismo (competía con la creación de carpetas),
  perdiendo archivos de forma intermitente; se cambió a comprobación **léxica**
  (`os.path.normpath`), segura entre hilos y con el mismo anti-traversal. Lo detectó
  `bench --flatten --hilos 4` (firma con mtime + recuento), no los tests de contenido.
  Docs: `ARQUITECTURA.md` (§2 motores aplanar/desaplanar + cadena de imports; §7 MENU
  con Aplanado), `GUI.md` (§5c Aplanar/Desaplanar con selectores y separador),
  `escalabilidad.md` (validación "Aplanado": cero extensiones del framework + lección
  de concurrencia).

---

## CATEGORÍA "APLANADO" — COMPLETA (fases 0–5 + 1)

Dos tareas nuevas (Aplanar/Desaplanar) con motores independientes, integradas como
tercera categoría (Combinación / Compresión / **Aplanado** / Eliminar). Aplanado a una
carpeta con dos modos de nombre (ruta con separador configurable / solo nombre final),
políticas de conflicto (renombrar por carpeta padre / mantener / reemplazar por
criterio), separador de niveles **editable en ambas pestañas** (A2). Desaplanado
**solo por los nombres** (sin índice, A5), con anti path-traversal léxico. Paralelismo
por archivo serializado (D7). Round-trip byte a byte verde (secuencial y paralelo).
**Cero extensiones del framework**: motor + pestaña declarativa + una línea en
`App.MENU`. Orden recomendado: 0 → 1 → 2 → 3 → 4 → 5.

Orden recomendado: 0 → 1 → 2 → 3 → 4 → 5 (motor y correctness antes que GUI), igual
que en Combinación.

---

## 8. Riesgos y notas

- **Reconstrucción por convención, no por metadatos**: Desaplanar es intrínsecamente
  ambiguo con `-` literal en nombres/carpetas. Es una limitación aceptada y elegida
  por el usuario; hay que **avisarla** claramente en la GUI (no venderla como un undo
  exacto). El par exacto/reversible ya existe (Combinar/Descombinar con índice); éste
  es deliberadamente ligero.
- **Modo "solo nombre final" pierde la ruta**: no es desaplanable; documentarlo. La
  política de conflicto es imprescindible en este modo (colisiones frecuentes).
- **"Reemplazar" destruye datos** (A8): confirmación modal explícita. (Aplanar
  siempre copia, A1: el origen nunca se toca.)
- **Aplanar sobre un destino dentro del origen**: `rutas_validadas` debe impedir que
  el destino esté dentro del origen (recursión infinita al recorrer). Caso límite de
  la Fase 5.
- **No rompe A–H ni el menú**: dos pestañas declarativas + una `Categoria` en
  `App.MENU`; **cero cambios transversales** en el framework (a diferencia de
  Combinación, que aportó el `Campo` tipo `lista`). Refuerza que el sistema escala
  con solo motor + pestaña + registro.
