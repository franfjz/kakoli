# Roadmap: aplicar el diseño "retro-modern" y separar tema ↔ layout

Plan por fases para (1) **separar** el archivo actual de la GUI (`kakoli.py`:
frames + widgets + organización) de un **archivo nuevo de tema** (colores,
fuentes, estilos), configurable de forma independiente; y (2) aplicar el diseño
de las capturas (proyecto Figma Make adjunto). No cambia la lógica de los motores.

Fecha: 2026-09-04. Referencias del sistema: `ARQUITECTURA.md`, `GUI.md`.

---

## 0. Objetivo y restricciones (del encargo)

- **Separación tema ↔ layout**: `kakoli.py` mantiene SOLO la estructura (qué
  frames, qué widgets, cómo se organizan y cablean). Un módulo nuevo
  (`tema.py`) define TODO lo visual (paleta, fuentes, estilos ttk, ayudas para
  widgets clásicos). Cambiar un color o una fuente debe hacerse en un único sitio
  sin tocar el layout.
- **Mantener los TIPOS de widget actuales**. El mockup usa radios para "Nivel" y
  un desplegable para "Hilos"; nosotros conservamos lo que ya hay: **Combobox**
  para el nivel de compresión y **radios** para los hilos. Igual con el resto
  (checkbuttons, Text del registro, Notebook de pestañas, Progressbar...).
- **Cambios de layout permitidos** (los pide el encargo):
  - **Columna derecha FIJA** (ancho fijo, no proporcional).
  - **Integrar el frame superior** (selectores de origen/destino) **en el panel
    izquierdo, sobre las opciones** (se disuelve el frame superior a todo el ancho).

---

## 1. Tokens del diseño (fuente de verdad para `tema.py`)

Extraídos de `src/index.css` y `src/App.tsx` del proyecto adjunto.

**Colores**
| Nombre | Hex | Uso |
|---|---|---|
| bg | `#1E2522` | fondo de la ventana |
| container | `#141917` | paneles/tarjetas |
| black | `#000000` | fondo de inputs, consola y cabecera del monitor |
| primary | `#4AF626` | verde principal: acentos, bordes activos, botón acción |
| success | `#A3E635` | verde lima: estado "Listo.", líneas de éxito del log |
| danger | `#EF4444` | rojo: pestaña/acciones de Eliminar, aviso definitivo |
| border-subtle | `#313D39` | bordes y separadores tenues |
| text | `#E5E7EB` | texto normal |
| text-muted | `#9CA3AF` | descripciones/ayudas y etiquetas secundarias |

**Tipografía**: `Space Mono` → fallback `Courier New`/`Consolas`/monospace.
Tamaños: normal ~13–14 px (`text-sm`), pequeño ~11–12 px (`text-xs`).

**Rasgos visuales**: bordes de 1 px `border-subtle`; pestañas estilo corchete
`[ Comprimir ]` (activa: texto verde, negrita, fondo `border-subtle`, borde
inferior verde); `LabelFrame` con leyenda verde "flotando" sobre el borde;
inputs con fondo negro y borde que pasa a verde con foco; botón de acción
verde relleno (rojo en Eliminar), "Pausar" apagado; hover general → texto blanco.

---

## 2. Mapeo diseño → estructura actual (qué se conserva y qué cambia)

| Zona del diseño | Widget/tipo (se mantiene) | Estado actual | Cambio |
|---|---|---|---|
| Pestañas `[ … ]` | `ttk.Notebook` | igual | re-estilar tabs |
| Panel izquierdo (contenido de pestaña) | `Frame` + secciones | opciones en lista | agrupar en `LabelFrame` |
| Selector de ruta (origen/destino) | `Entry` + `Button` | en frame superior a todo el ancho | **mover al panel izq., arriba** |
| Secciones de opciones | `LabelFrame` + checks/combos/radios | lista plana + cabecera | **agrupar** por secciones |
| Nivel de compresión | **Combobox** (se mantiene) | Combobox | solo re-estilo |
| Hilos | **radios** (se mantienen) | radios | solo re-estilo |
| Columna derecha "Equipo Detectado" | `LabelFrame`/`Label` | `lbl_perfil` | formato label:valor |
| Consola + "Registro detallado" | `Text` + `Checkbutton` | ya está en la dcha. | re-estilo (fondo negro, tags de color) |
| Cabecera "CARPETAS EN ZIP v…" | `Label`s | no existe | añadir |
| Barra inferior: acción + Pausar + estado | `Button`s + `Label` | existe (por pestaña) | re-estilo + posible compartir |
| Barra de progreso | `Progressbar` | existe | el diseño no la muestra → decidir ubicación |
| Aviso rojo (Eliminar) | `Label`/`Frame` | existe | re-estilo (borde/relleno rojo) |

Secciones por pestaña (según el mockup):
- **Comprimir**: "Opciones de Compresión" (Nivel + Modo compacto) · "Filtros"
  (Omitir ocultos) · "Manejo de Archivos" (Verificar + Borrar intermedios) ·
  "Rendimiento" (Hilos + Modo ligero).
- **Descomprimir**: "Opciones de Extracción" (Expandir + Verificar CRC +
  Conservar) · "Rendimiento" (Hilos + Modo ligero).
- **Eliminar**: aviso rojo · selector · "Seguridad" (Solo simular + Borrar sin
  contar + separador + Confirmo, en rojo).

---

## 3. Decisiones clave (leer antes de empezar)

- **D1 — Base de ttk**: los temas nativos de Windows (`vista`/`xpnative`) NO
  respetan colores en muchos elementos. Se usará **`ttk.Style().theme_use("clam")`**
  como base (totalmente re-estilable) y sobre ella se construye el look retro.
- **D2 — Clásicos vs ttk**: los indicadores de check/radio y el fondo del
  `Text`/`Entry`/consola se controlan mejor con **tk clásico** (`selectcolor`,
  `bg`, `fg`, `insertbackground`). El tema expondrá helpers para clásicos además
  de estilos ttk. (Ya usamos `tk.Radiobutton`, `tk.Text`, `tk.Label` en varios
  sitios; encaja.)
- **D3 — Fuente Space Mono**: no viene con el SO. Opciones: (a) registrarla en
  runtime desde un `.ttf` empaquetado con `ctypes AddFontResourceExW` (Windows);
  (b) fallback a `Consolas`/`Courier New`. El tema decide una sola vez y expone
  fuentes con nombre.
- **D4 — RESUELTA (afinada)**:
  - La **columna derecha es COMPARTIDA** a nivel de `App`, fija, ocupando toda la
    parte derecha; muestra solo: **perfil del equipo**, **checkbox "Registro
    detallado"** y **widget de registro** (el log). El registro y el detallado
    pasan a ser ÚNICOS (de `App`); el motor activo vuelca ahí su log.
  - La **barra inferior NO es compartida**: sigue **por pestaña** (botón de
    acción, Pausar, estado y barra de progreso), porque cada una es de un proceso
    distinto.
  - **Una sola tarea a la vez**: no se admite comprimir/descomprimir/eliminar
    simultáneamente. Se garantiza **bloqueando el acceso al resto de pestañas**
    mientras un motor trabaja (deshabilitar las otras pestañas del `Notebook`);
    al terminar/pausar, se reactivan. Como la barra es por pestaña y no se puede
    cambiar de pestaña durante un trabajo, el log compartido siempre refleja el
    motor en marcha.
- **D4 (contexto) — ¿compartidas o por pestaña?**
  El diseño tiene UNA columna derecha y UNA barra inferior a nivel de ventana
  (fuera del contenido de pestaña).
  - *Opción A (recomendada, fiel al diseño)*: mover el **monitor derecho** y la
    **barra de estado** al nivel de `App` (fijos, compartidos), y que reflejen la
    pestaña activa. Requiere recablear el log/progreso/estado/botones (hoy son
    por pestaña) a una superficie compartida y conmutar al cambiar de pestaña.
    Elimina la triplicación actual.
  - *Opción B (ligera)*: mantener el monitor + barra **por pestaña** (como ahora)
    pero re-estilados y con ancho fijo. Visualmente casi idéntico (solo se ve una
    pestaña a la vez); cero recableado. La diferencia con el diseño es que la
    columna derecha queda por debajo de la tira de pestañas, no a su altura.
  - Decisión por defecto de este roadmap: **A** para la meta final, pero las
    fases están ordenadas para que la separación de tema (lo esencial) no dependa
    de esta decisión.
- **D5 — Barra de progreso**: el mockup no la muestra. Se conserva (es funcional)
  integrándola en la barra inferior como una barra fina verde, o justo encima de
  ella. Definir en Fase 6.
- **D6 — Etiquetas del nivel**: el mockup dice None/Fast/Normal/Ultra; hoy son
  "Rápido/Equilibrado/Máximo". Se mantiene el widget (Combobox) y se decide si se
  conservan las etiquetas actuales o se adoptan las del diseño (cosmético).

---

## 4. Resumen de fases

- **Fase 1** Módulo `tema.py`: paleta + fuentes + estilos ttk + helpers clásicos.
- **Fase 2** Desacoplar `kakoli.py` del estilo (sin tocar layout): todo color/
  fuente sale del tema. Punto de control: app "temada" con el layout actual.
- **Fase 3** Estructura compartida (D4): columna derecha fija + barra de estado a
  nivel de `App` (o mantener por pestaña si se elige B).
- **Fase 4** Panel izquierdo: selectores integrados arriba + opciones agrupadas
  en secciones `LabelFrame` según el diseño.
- **Fase 5** Estética de detalle: pestañas de corchete, botones acción/pausar,
  aviso rojo, consola con tags de color, leyendas verdes.
- **Fase 6** Barra de progreso y estados (Listo./Trabajando…/Pausado…).
- **Fase 7** Fuente Space Mono + pulido (paddings, hover, contraste, legibilidad
  del atenuado de hilos sobre fondo oscuro).
- **Fase 8** Verificación (headless + visual + funcional).

Orden recomendado de entrega: 1 → 2 (aquí ya se ve el cambio de tema) → 5 →
4 → 3 → 6 → 7 → 8. Cada fase es publicable por separado.

---

## 5. Fases detalladas

### Fase 1 — Módulo de tema (`tema.py`)
**Objetivo**: un módulo que NO sabe nada de la organización de la GUI; solo
provee estilo. Contrato en el Apéndice A.
**Contenido**
- Constantes de **paleta** (los 9 colores del §1) y de **fuentes** (`fuente`,
  `fuente_bold`, `fuente_peque`), como `tkfont.Font` con nombre.
- `configurar(root)`:
  - `style = ttk.Style(root); style.theme_use("clam")`.
  - Define los estilos ttk con nombre (ver Apéndice A): `TFrame`, `Card.TFrame`,
    `TLabel`, `Muted.TLabel`, `Head.TLabel`, `TButton`, `Accion.TButton`,
    `Peligro.TButton`, `Fantasma.TButton`, `Tab.TButton`, `TEntry`, `TCombobox`,
    `TCheckbutton`, `TLabelframe`/`TLabelframe.Label`, `TNotebook`/`TNotebook.Tab`,
    `Horizontal.TProgressbar`, `TScrollbar`, `TSeparator`.
  - `root.option_add(...)` para clásicos y para el listbox del Combobox
    (`*TCombobox*Listbox.background/foreground/selectBackground`).
  - Fija `root.configure(bg=BG)`.
- Helpers para **tk clásico**: `estilo_text(w)`, `estilo_entry(w)`,
  `estilo_radio(w)`, `estilo_check(w)`, `estilo_label(w, tono)` — aplican
  bg/fg/font/selectcolor/insertbackground. Alternativa: exponer la paleta y que
  la GUI la use directamente (menos helpers, más acoplamiento en el punto de uso).
- Nombres de estilo como **constantes** exportadas (evita strings mágicos en la
  GUI): `ACCION`, `PELIGRO`, `TARJETA`, etc.
**Criterios**: `import tema; tema.configurar(root)` deja la ventana con el fondo y
las fuentes retro. Cambiar `PRIMARY` en `tema.py` recolorea toda la app.
**Riesgos**: elementos ttk cuyo color es difícil (indicadores de check/radio en
`clam`); mitigar usando tk clásico para esos (D2).

**ESTADO: HECHA** (2026-09-04). `tema.py` creado: paleta (9 tokens), fuentes con
fallback (Space Mono→Consolas→Courier New), `configurar(root)` sobre base `clam`
con todos los estilos (frames, labels semánticos, botones Accion/Peligro/Fantasma,
Entry, Combobox, Checkbutton, Labelframe, Notebook, Progressbar, Scrollbar,
Separator + option_add del Listbox del Combobox), y helpers de clásicos
(`estilo_text`/`tags_consola`/`estilo_radio`/`estilo_check`/`estilo_label`). Nombres
de estilo exportados como constantes. Galería visual: `python tema.py`. Verificado
headless: estilos con colores de la paleta, clam, creación de todos los widgets,
helpers, y propagación al cambiar un token. La GUI (kakoli.py) NO se ha tocado.

### Fase 2 — Desacoplar `kakoli.py` del estilo
**Objetivo**: que `kakoli.py` no contenga ni un color ni una fuente literal.
**Trabajo**
- Sustituir `COLOR_AVISO`, `COLOR_AYUDA`, `font=("",8)`, `font=("",9,"bold")`,
  `disabledforeground`, etc., por referencias al tema (paleta/fuentes/estilos).
- `App.__init__`: `tema.configurar(self)` antes de construir pestañas.
- Los widgets ttk pasan `style=tema.XXX`; los clásicos pasan por los helpers.
- SIN cambios de layout todavía. **Punto de control**: la app se ve retro pero
  con la disposición actual; todo sigue funcionando.
**Criterios**: `grep` de colores hex / `font=(` en `kakoli.py` → 0 resultados
(salvo, si acaso, en el propio `tema.py`).

**ESTADO: HECHA** (2026-09-04). `kakoli.py` importa `tema`; `App.__init__` llama
`tema.configurar(self)`. Eliminadas las constantes `COLOR_AVISO`/`COLOR_AYUDA`; 0
colores/fuentes hardcodeados (grep vacío). Widgets ttk con `style=` semántico
(TARJETA en frames de contenido, LBL_TITULO en etiquetas verdes, LBL_PELIGRO en el
aviso, SECCION en los LabelFrame, ACCION/PELIGRO_BTN en el botón principal según
la pestaña —atributo de clase `estilo_accion`—, FANTASMA en Pausar, BARRA en la
Progressbar, LBL_EXITO en el estado). Clásicos por helpers: `estilo_text` +
`tags_consola` (registro negro con tags sistema/exito/aviso), `estilo_radio` (con
itálica para los hilos atenuados) y `estilo_label("muted")` para las ayudas y
`("normal")` para el perfil. LAYOUT SIN CAMBIOS. Verificado: compila, `--version`,
construcción+orden (test_gui7) y estilos aplicados a los widgets (test_tema2).

### Fase 3 — Columna derecha COMPARTIDA + una tarea a la vez (D4 afinada)
**Objetivo**: subir SOLO la columna derecha a nivel de `App` (compartida, fija);
la barra inferior se queda por pestaña; garantizar un único motor a la vez
bloqueando el resto de pestañas mientras uno trabaja.
**Trabajo**
- `App` pasa a un layout `[ Notebook (expandible) | Monitor (ancho fijo) ]` en
  un frame principal a toda la ventana. El monitor ocupa toda la altura derecha
  (`grid_propagate(False)` + ancho fijo ~280 px; columna del Notebook `weight=1`,
  la del monitor `weight=0`).
- **Monitor (App)**: cabecera de marca ("CARPETAS EN ZIP" verde + versión muted),
  "Equipo detectado" (perfil, desde `App.perfil_base`), "Consola" (título +
  checkbox **"Registro detallado"** ÚNICO en `App.v_detallado`) y el `Text` del
  registro con scrollbar. El log y las ayudas de escritura (`escribir`/
  `escribir_lote`) pasan a `App` (`App.texto_log`).
- **Cada pestaña (`PestanaBase`)**: pierde la columna derecha y el split 70/30; su
  contenido queda: selectores (arriba) → opciones (rellenan) → **barra inferior**
  (botón acción + Pausar + estado + progreso), que sigue siendo por pestaña.
- **Recableado del log**: `procesar_cola` vuelca las líneas a `App.texto_log`
  (progreso/estado siguen en la barra por pestaña, `self.barra`/`self.v_estado`).
  `_ejecutar` lee el detallado de `App.v_detallado`. Se quita `v_detallado`,
  `texto`, `lbl_perfil` de `PestanaBase`; `_texto_perfil` se mueve a `App`.
- **Una tarea a la vez**: al arrancar (`_iniciar`), `App.bloquear(pestaña_activa)`
  deshabilita las demás pestañas del `Notebook` (`cuaderno.tab(i, state="disabled")`)
  y marca la activa; al terminar/pausar (`_fin`), `App.desbloquear()` reactiva
  todas. Como no se puede cambiar de pestaña mientras trabaja, el log compartido
  siempre corresponde al motor en marcha.
**Criterios**: una sola columna derecha (perfil + detallado + log) a la derecha,
toda la altura; barras inferiores por pestaña; con un trabajo en curso, las otras
pestañas quedan bloqueadas; round-trip/pausa/reanudación intactos.
**Riesgos**: el recableado del log a `App`; el bloqueo/reactivación de pestañas
(no dejar pestañas deshabilitadas si el trabajo acaba por error o al cerrar).

**ESTADO: HECHA** (2026-09-05). `App` con layout `[Notebook | Monitor(minsize 280)]`;
`_construir_monitor` (marca + "Equipo detectado" + "Consola"/detallado + `texto_log`).
`App.v_detallado`, `App.texto_log`, `App.escribir/escribir_lote`, `App._texto_perfil`,
`App.bloquear(activa)`/`desbloquear()`. `PestanaBase` pierde el split 70/30 y la
columna derecha: contenido = selectores → opciones (a todo el ancho) → barra
inferior (por pestaña). `escribir*` delegan en `App`; los 3 `_ejecutar` leen el
detallado de `App.v_detallado`; `_iniciar`→`bloquear(self)`, `_fin`→`desbloquear()`;
`actualizar_pestanas` eliminado. Verificado: construcción/estilos (test_gui8:
compartidos, sin log por pestaña, bloqueo con solo la activa accesible + '•',
monitor fijo 280) y FUNCIONAL con mainloop (test_func_ml: durante la tarea el resto
de pestañas bloqueadas, al terminar reactivadas, log compartido con "Completado",
ZIP generado, barra por pestaña avanza). CIERRE DEL BLOQUE (2026-09-05): resuelta la
deuda de hilos — toda lectura de variables Tk se hace ahora en el HILO PRINCIPAL
dentro de `_validar` (que ya construye el objeto `Opciones` del motor: `_nivel`,
`_politica`, `v_*.get()`, `app.v_detallado.get()`) y se pasa al worker por el dict
`datos["opts"]`; `_ejecutar` ya no toca ninguna variable Tk (solo lee de `datos`).
Documentado el contrato en los docstrings de `_validar`/`_ejecutar` de la clase base.
Esto elimina el `RuntimeError: main thread is not in main loop`: ahora también pasa
el test headless SIN mainloop (test_func_gui, que antes lo lanzaba), además de
test_func_ml.

### Fase 4 — Panel izquierdo: selectores arriba + opciones en secciones
**Objetivo**: mover los selectores al panel izquierdo, sobre las opciones, y
agrupar las opciones en `LabelFrame` según el diseño.
**Trabajo**
- Disolver el frame superior a todo el ancho; poner el/los selector(es) de ruta
  como primer bloque del contenido de cada pestaña.
- Reagrupar las opciones actuales en secciones (§2): mismos widgets, mismos
  `variable=`, mismas ayudas; solo cambia el contenedor (de lista plana +
  cabecera a varios `LabelFrame`).
- Mantener "Registro detallado" en la consola (columna derecha), como el diseño.
- Mantener tipos: Combobox nivel, radios hilos, y el atenuado por `techo_hilos`.
**Criterios**: el orden y las opciones son los de `GUI.md`, reagrupados; el
round-trip y los cableados (`_ejecutar`, `_politica`, `_nivel`) no cambian.

**ESTADO: HECHA** (2026-09-05). Selectores ya estaban arriba (fila 0 del tab desde
Fase 3); las opciones se agrupan ahora en secciones `LabelFrame` (leyenda verde).
Helper nuevo `PestanaBase._seccion(titulo)`: crea un `LabelFrame` dentro de
`contenedor_ops` y lo fija como `self.marco_ops`, de modo que los controles se
siguen creando igual (padre `self.marco_ops`) pero caen en la sección vigente;
`_add_control`/`_add_ayuda` sin cambios; se elimina `_add_cabecera`;
`_construir_comunes` abre `_seccion("Rendimiento")`. Secciones por pestaña:
Comprimir = "Opciones de compresión" (nivel Combobox + modo compacto) · "Filtros"
(omitir ocultos) · "Manejo de archivos" (verificar + borrar intermedios) ·
"Rendimiento" (hilos radios + modo ligero); Descomprimir = "Opciones de extracción"
(expandir + CRC + conservar) · "Rendimiento"; Eliminar = aviso rojo + "Seguridad"
(simular + sin contar + confirmo) · "Rendimiento". SCROLL: como el contenido puede
superar el alto de media pantalla (Comprimir pide ~768 px de opciones), el área de
opciones se envolvió en un `tk.Canvas` desplazable (`_lienzo` + `_barra_ops`
Vertical.TScrollbar); el frame interior sigue el ancho del lienzo, la barra solo
aparece cuando no cabe (`_reajustar_scroll`) y la rueda del ratón desplaza mientras
el puntero está encima (`_rueda_ops`, bind_all en Enter/Leave). Tipos de widget y
cableados intactos (Combobox nivel, radios hilos con atenuado por `techo_hilos`).
Verificado: test_gui_fase4 (4/2/2 secciones en orden, combo en su sección, sin el
LabelFrame plano "Opciones", selectores arriba, vars/monitor intactos), medición
(Rendimiento alcanzable por scroll), funcional test_func_ml (6/6) y 3 capturas
visuales (secciones + scroll + auto-ocultado de la barra).

### Fase 5 — Estética de detalle
- Pestañas de corchete `[ Comprimir ]` con activo en verde (re-estilo del
  `Notebook.Tab` o, si no se logra en `clam`, tabs como `Tab.TButton`).
- Botón de acción: verde relleno (Comprimir/Descomprimir), rojo (Eliminar);
  "Pausar" apagado; estado "Listo." en verde lima.
- Aviso de Eliminar: borde y relleno rojos, texto rojo en mayúsculas.
- Consola: fondo negro; tags de color (`[SISTEMA]`=muted, `>`/éxito=verde lima,
  `[!]`=rojo).
- `LabelFrame` con leyenda verde; separadores `border-subtle`.

**ESTADO: HECHA** (2026-09-05). (1) PESTAÑAS DE CORCHETE: helper
`App._rotulo(nombre, activa=False)` → `[ Comprimir ]` / `[ Comprimir • ]`; usado en
el alta (`cuaderno.add`) y en `bloquear`/`desbloquear`. El activo ya salía verde por
el `style.map` del `TNotebook.Tab` (Fase 2). (2) CAJA DE AVISO (Eliminar): token
nuevo `tema.PELIGRO_FONDO="#2A1717"` + helper `tema.estilo_caja_aviso(frame)` (borde
`DANGER` 1px vía highlightthickness + relleno rojizo); en `PestanaBase._construir` el
aviso pasó de un `ttk.Label` plano a un `tk.Frame` (caja) con `tk.Label` dentro
(`estilo_label(danger, fondo=PELIGRO_FONDO)`), con wraplength que se adapta al ancho
real de la caja por `<Configure>` (el panel izq. es estrecho, ~360px, si no se
cortaba el texto). (3) TAGS DE CONSOLA APLICADOS: `App._tag_log(linea)` clasifica por
prefijo real de los motores — `[!]`→aviso(rojo), `===`/`Máquina:`/`[Simulaci`→
sistema(gris), `Completado`/`Eliminado:`/`Nada que hacer`→exito(lima), resto normal;
`escribir_lote` lo usa (antes solo distinguía `[!]`). Botones/estado ya estaban
(ACCION/PELIGRO_BTN/FANTASMA/LBL_EXITO, Fase 2). Verificado: test_gui_fase5 (rótulos
con corchete + '•' al bloquear, caja de aviso con borde/relleno/texto rojos, 4 tags
presentes y aplicados a ===/[!]/Completado), test_func_ml (6/6), test_gui_fase4 sin
regresión, y capturas (consola con colores tras compresión real + caja de aviso). El
"mayúsculas" del aviso NO se aplicó (el texto es un párrafo explicativo de 4 líneas;
en bloque quedaba ilegible); se mantiene el énfasis con AVISO:/DEFINITIVO en el texto.

### Fase 6 — Barra de progreso y estados
- Ubicar la `Progressbar` (D5): barra fina verde en la barra inferior o encima.
- Textos de estado con colores del tema: "Listo." (lima), "Trabajando…" (verde),
  "Pausado…" (muted/ámbar), "Error" (rojo).

**ESTADO: HECHA** (2026-09-05). ESTADOS CON COLOR: token nuevo `tema.AMBAR="#F59E0B"`
+ estilos de etiqueta `LBL_TRABAJANDO` (verde PRIMARY) y `LBL_PAUSA` (ámbar) además de
los ya existentes `LBL_EXITO` (lima) y `LBL_PELIGRO` (rojo). La etiqueta de estado se
guarda en `PestanaBase.lbl_estado` y se cambia por el helper
`_estado(texto, estilo=LBL_EXITO)` (fija texto + `style`). Mapeo: inicial/"Listo." y
"Completado"/"Nada que hacer" = lima; "Trabajando..." y el progreso (`N/M — etiqueta`)
= verde; "Pausando"/"Pausado"/"Cerrando"/"Cancelado" = ámbar; "Error." = rojo. Se
sustituyeron todos los `v_estado.set(...)` de `_iniciar`/`_pausar`/`pedir_cierre`/
`procesar_cola`/`_fin` por `_estado(...)`. BARRA DE PROGRESO: se mantiene donde estaba
(barra verde `BARRA` a todo el ancho, bajo los botones de la barra inferior; 0 en
reposo, avance durante el trabajo, 100% al completar) — cumple D5; probado que `clam`
no reduce su alto con `thickness`, así que no se tocó. Verificado: test_gui_fase6
(inicial lima; ramas de `_fin` pausado→ámbar/error→rojo/cancelado→ámbar; run real:
arranque y progreso en verde, fin en lima, barra al 100%), captura mid-run
(`[ Comprimir • ]`, estado "17/61 — sub" en verde, barra parcial) y regresión
test_func_gui/fase4/fase5 sin cambios.

### Fase 7 — Fuente y pulido
- Registrar Space Mono en runtime (ctypes `AddFontResourceExW`) con fallback;
  el tema elige la familia disponible una sola vez.
- Paddings/espaciados como el mockup; hover donde ttk lo permita.
- Revisar contraste y que el **atenuado de hilos** (cursiva gris) siga legible
  sobre fondo oscuro (usar `text-muted` en vez del gris claro actual).

**ESTADO: HECHA** (2026-09-06). FUENTE EN RUNTIME: `tema.registrar_fuentes(dir=None)`
registra las .ttf/.otf de la carpeta `kakoli/fuentes/` con
`ctypes.windll.gdi32.AddFontResourceExW(ruta, FR_PRIVATE=0x10, None)` — privado del
proceso: NO instala en el sistema ni pide admin. Silenciosa y robusta (si no hay
carpeta/archivos, no es Windows o falla, no hace nada; try/except amplio),
idempotente (`_fuentes_registradas`). Se llama en `_crear_fuentes` ANTES de
`_familia(root)`, así que si Space Mono está presente Tk la ve y el orden de
preferencia `_FAMILIAS=("Space Mono","Consolas","DejaVu Sans Mono","Courier New")` la
elige; si no, cae a Consolas (esta máquina: NO instalada → Consolas, verificado).
Añadida carpeta `fuentes/` con `LEEME.txt` (de dónde bajar Space Mono —Google Fonts,
OFL— y qué 4 archivos dejar). No se descarga la fuente (licencia/red fuera de
alcance): el mecanismo se activa solo al dejar el .ttf. NOTA/caveat: con algunas
versiones de Tk las fuentes FR_PRIVATE podrían no listarse en `tkfont.families`; no
verificable aquí sin el .ttf (probados los caminos de 0 fuentes, carpeta inexistente
e idempotencia). PULIDO: el atenuado de hilos ya usaba `MUTED`
(`estilo_radio` fija `disabledforeground=MUTED`) + cursiva → cumple el requisito de
`text-muted`; botones con hover por `style.map` (Fase 2). Verificado: registrar_fuentes
(0 sin ttf / robusto / idempotente / familia=Consolas), `--version`, y regresión
test_func_ml/fase4/fase5/fase6 sin cambios.

### Fase 8 — Verificación
- Headless: construcción de las 3 pestañas sin error; `grep` sin colores/fuentes
  hardcodeados fuera de `tema.py`; cambiar un token del tema y comprobar que se
  propaga (p.ej. recolorear y releer un widget).
- Visual: lanzar la ventana y comparar con las 3 capturas.
- Funcional: round-trip de `bench.py` sigue verde; la GUI lanza/pausa/reanuda.

**ESTADO: HECHA** (2026-09-06). HEADLESS: 0 colores hex y 0 `font=(` hardcodeados
en kakoli.py (todo el estilo vive en tema.py); las 3 pestañas se construyen sin error
(contenedor de opciones, etiqueta de estado, monitor compartido); PROPAGACIÓN de
token verificada — cambiar `tema.PRIMARY` recolorea `LBL_TITULO` y el botón de acción
(test_fase8). FUNCIONAL: `bench.py --todos` = los 5 escenarios pasan el round-trip
byte a byte (pico 26 MB); GUI lanza/pausa/reanuda end-to-end (test_func_pausa: pausar
→ ámbar + "Continuar" + pestañas reactivadas + progreso parcial guardado; reanudar →
"Completado" lima + ZIP + barra 100%). VISUAL: la fuente Space Mono YA está disponible
(el usuario dejó los 4 .ttf en `fuentes/`) → `registrar_fuentes()` registra 4, Tk la
ve y el tema la usa: **queda RESUELTO el caveat de la Fase 7** (las fuentes FR_PRIVATE
sí las enumera Tk aquí). Con Space Mono (más ancha que Consolas) se detectaron y
CORRIGIERON dos recortes: (a) el estado se movió a su propia fila del `bottom`
(grid row 1, sticky ew) para no cortarse ("Listo." salía "List"); (b) el padding de
`TNotebook.Tab` bajó de (12,4) a (7,4) para que quepan las tres pestañas de corchete.
Regresión completa verde (func_ml, func_gui, func_pausa, fase4/5/6, fase8) +
`--version`. RESIDUAL MENOR (cosmético): con Space Mono, 2 etiquetas de checkbox muy
largas de Eliminar ("Borrar sin contar antes (más rápido en árboles enormes)" y
"Confirmo que quiero borrar esta carpeta definitivamente") se recortan un poco por la
derecha en el panel estrecho; el texto de ayuda debajo (que sí ajusta) lo aclara.
Arreglo futuro opcional: envolver el texto del Checkbutton o acortar esas etiquetas.

---

## Estado final del rediseño

**Fases 1–8 HECHAS.** El aspecto (paleta, fuentes, estilos) vive por completo en
`tema.py` y se cambia sin tocar el layout de `kakoli.py`. Diseño "retro-modern"
aplicado: pestañas de corchete, columna derecha compartida (perfil + registro), panel
izquierdo con selectores arriba + opciones en secciones `LabelFrame` (con scroll),
consola con tags de color, caja de aviso roja, estados con color y fuente Space Mono
(con fallback a Consolas). Una sola tarea a la vez (bloqueo de pestañas). Lectura de
variables Tk en el hilo principal. Motores intactos (round-trip verde).

---

## Apéndice A — Contrato del módulo `tema.py`

El tema **no importa** `kakoli` ni conoce frames/pestañas. Expone:

```
# Paleta (constantes)
BG, CONTAINER, NEGRO, PRIMARY, SUCCESS, DANGER, BORDE, TEXT, MUTED

# Fuentes (tkfont.Font con nombre; elegidas según disponibilidad)
def fuentes() -> {"base":Font, "bold":Font, "peque":Font}

# Nombres de estilo ttk (constantes de string)
TARJETA="Card.TFrame"; ACCION="Accion.TButton"; PELIGRO="Peligro.TButton"; ...

def configurar(root: tk.Misc) -> None
    # theme_use("clam"); define todos los estilos; option_add; root.configure(bg)

# Helpers para widgets clásicos (tk.Text/Entry/Radiobutton/Checkbutton/Label)
def estilo_text(w); estilo_entry(w); estilo_radio(w); estilo_check(w)
def estilo_label(w, tono="normal"|"muted"|"head"|"danger")
```

La GUI: `import tema` → `tema.configurar(self)` una vez; crea ttk con
`style=tema.ACCION` y clásicos pasando por `tema.estilo_*`. Para cambiar el look,
se edita SOLO `tema.py`.

## Apéndice B — Gotchas de Tkinter/ttk (para no perder tiempo)

- **`theme_use("clam")` es obligatorio** para colorear; los nativos ignoran
  `configure` en muchos elementos.
- **Combobox**: el desplegable es un `Listbox` aparte → colores vía
  `root.option_add('*TCombobox*Listbox.background', …)` (y foreground/select).
- **Check/Radio**: el color del indicador en ttk `clam` es limitado; para el
  look del mockup (relleno verde) conviene tk clásico con `selectcolor`,
  `activebackground`, `bg`, `fg`.
- **`Text`/`Entry` (clásicos/negros)**: fijar `bg`, `fg`, `insertbackground`
  (cursor), `selectbackground`, `highlightthickness=0` o color de foco.
- **Space Mono**: sin registrar en el SO, Tk no la ve; registrar en runtime o
  fallback. No bloquear el arranque si falla.
- **Notebook.Tab** en `clam`: se puede colorear con `style.map(...)` para
  seleccionado/activo; si el corchete `[ … ]` no queda bien, usar botones.
- **No mezclar** `grid` y `pack` en el MISMO contenedor (ya respetado hoy).
