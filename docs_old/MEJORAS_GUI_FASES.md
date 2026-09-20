# Plan por fases — mejoras de la interfaz

Plan de implementación **incremental** de las mejoras recogidas en
[`MEJORAS_GUI.md`](MEJORAS_GUI.md). Cada fase es autónoma, de bajo riesgo, cabe dentro
de `gui/` (respetando `tests/test_fronteras.py`) y termina con la app funcionando y con
tests en verde. Fecha: 2026-09-18.

**Cómo usar este plan.** Las fases están ordenadas por dependencia y retorno. Se pueden
implementar de una en una (una rama/commit por fase). Cada ficha trae: objetivo, qué se
toca, pasos, pruebas, riesgos y **criterio de aceptación** (cómo saber que está lista).
Referencia a §X = sección de `MEJORAS_GUI.md`.

Convenciones:
- **Esfuerzo**: S (≤ media jornada) · M (1–2 jornadas) · L (varias).
- Ninguna fase toca `core/` ni los motores salvo que se indique (no ocurre en este plan).
- Regla transversal: si una fase añade comportamiento observable, añade su test en
  `tests/gui/`.

---

## Fase 0 · Preparación (media hora) — ✅ HECHA (2026-09-18)

Línea base verde antes de empezar: `pytest -m gui` 44 passed; suite completa 340 passed.

**Objetivo:** dejar el terreno listo sin cambiar comportamiento.

- Confirmar que `pytest -m gui` pasa en limpio (línea base).
- Crear `tests/gui/` como destino de los tests nuevos (ya existe; solo confirmar).
- Anotar en cada fila del roadmap el commit que la implementa.

**Aceptación:** suite verde antes de empezar; nada modificado.

---

## Fase 1 · Bucle de eventos que descansa — §1.1, §1.3, §1.5, §1.6 · **S** — ✅ HECHA (2026-09-18)

Implementada en `gui/app.py` (`_id_bomba`, `_arrancar_bomba`, `_bomba` con re-armado
condicional, `destroy` que cancela el timer) y `gui/componentes.py` (debounce de
`_on_reconfigure` a 80 ms y rueda enganchada al Toplevel por `funcid`, sin pisar el
binding global). Tests nuevos: `tests/gui/test_bomba.py` (3). Suite: 47 gui + 343 total,
verde. **Nota de diseño:** la bomba se re-arma según `_bloqueado` (no según `ocupada()`
como decía el borrador): el hilo pone el evento `fin` como última acción y luego muere,
así que `ocupada()` puede ser `False` con `fin` aún sin drenar; `_bloqueado` solo baja
cuando `_fin` procesa ese evento, garantizando que no se pierde ninguna línea ni el remate.

**Objetivo:** que en reposo (sin tarea trabajando) no haya timers ni recorridos. Es la
mejora de mayor retorno para el portátil de referencia (CPU/batería).

**Se toca:** `gui/app.py` (`_bomba`, `bloquear`, `desbloquear`, `_cerrar`, `__init__`),
`gui/componentes.py` (rueda del ratón, debounce del reconfigure).

**Pasos:**
1. **Bomba bajo demanda:** guardar el id del `after` (`self._id_bomba`). Arrancar la
   bomba en `bloquear` si no está viva; en `_bomba`, tras `procesar_cola`, re-armar solo
   si **alguna** pestaña sigue `ocupada()`, si no dejarla parada (`self._id_bomba = None`).
   Quitar el `after(...)` incondicional del `__init__`.
2. **Cancelar al cerrar:** en `_cerrar`/`destroy` hacer `after_cancel(self._id_bomba)` si
   está vivo.
3. **Debounce del reajuste de ancho** (§1.3): en `MarcoDesplazable._reajustar`, en vez de
   llamar a `_on_reconfigure` directo, programarlo con `after(80, ...)` cancelando el
   pendiente. Afecta a `_ajustar_ayudas` y `_ajustar_ayuda_wrap`.
4. **Rueda del ratón selectiva** (§1.5): sustituir `bind_all/unbind_all("<MouseWheel>")`
   por `bind`/`unbind` con `funcid` propio para no pisar otros bindings globales.

**Pruebas (`tests/gui/`):**
- Tras arrancar y sin iniciar tarea, `App._id_bomba is None` (o equivalente: la bomba no
  está armada).
- Al `bloquear`, la bomba se arma; al terminar y `desbloquear` con nada ocupado, se para.
- `procesar_cola` sigue drenando correctamente durante una tarea simulada.

**Riesgos:** olvidar re-armar la bomba en algún punto (una tarea quedaría “muda”). Mitiga
el test de arranque/parada. **Aceptación:** con la app abierta e inactiva, no hay
despertares periódicos; una tarea corre y actualiza progreso igual que antes.

---

## Fase 2 · Persistencia de preferencias — §2 · **M** — ✅ HECHA (2026-09-18)

Implementada: nuevo `gui/preferencias.py` (cargar/guardar JSON atómico en
`%APPDATA%/kakoli/config.json`, robusto ante ausencia/corrupción; escritor local para
no depender de piezas del núcleo sin commitear). `gui/app.py` carga al arrancar y
guarda en `destroy()`: rendimiento (Hilos validados contra el equipo / Modo ligero /
Registro detallado), última tarea abierta (por id estable, no por clase), geometría
(validada para no restaurar fuera de pantalla) y carpeta de diálogos. `gui/pestana_base.py`
usa `initialdir` = última carpeta y la recuerda; contrato ampliado en `gui/contexto.py`.
Tests: `tests/gui/test_preferencias.py` (5) + `tests/gui/test_persistencia.py` (8);
`conftest.py` redirige el config a un temporal (fixture `_config_temporal`) para no
tocar el del usuario. Suite: 55 gui / 357 total, verde. **Nota:** la geometría se guarda
con un flag `maximizada`; al restaurar una ventana que estaba maximizada, el tamaño
«normal» puede no ser exacto (limitación conocida de Tk, aceptable).

**Objetivo:** recordar entre sesiones lo que hoy se pierde. Es cimiento de fases
posteriores (7 guarda el sash; 4/2.2 la última carpeta).

**Se toca:** nuevo `gui/preferencias.py`; `gui/app.py` (cargar al iniciar, guardar al
cerrar); `gui/pestana_base.py` (`initialdir` en los diálogos).

**Pasos:**
1. **Módulo `preferencias.py`:** `cargar() -> dict` / `guardar(dict)` sobre
   `%APPDATA%/kakoli/config.json` (en otros SO, `~/.config/kakoli/`). Escritura atómica al
   estilo de `core.json_util` (sin importar de una tarea; si se quiere reutilizar
   `core.json_util`, está permitido: `gui` puede importar `core`). Robusto: si el fichero
   falta o está corrupto, devolver valores por defecto.
2. **Rendimiento y registro** (§2.1): al iniciar, poblar `v_hilos`/`v_ligero`/
   `v_detallado` desde config; al cerrar, guardarlos. Validar que el valor de hilos siga
   siendo válido para el equipo actual (si no, `Auto`).
3. **Última tarea/categoría** (§2.1): persistir `_ultima_tarea` y la categoría abierta;
   al arrancar, abrir donde se dejó (o portada si estaba en portada).
4. **Última carpeta de diálogos** (§2.2): guardar el directorio del último `filedialog`
   y pasarlo como `initialdir` en `_examinar_campo`/`_anexar_carpeta`.
5. **Geometría** (§2.3): guardar tamaño/posición y estado (maximizado sí/no); restaurar
   al abrir en vez de forzar `zoomed` siempre. Mantener maximizado como valor por defecto
   la primera vez.

**Pruebas:** `cargar` sobre fichero inexistente/corrupto devuelve defaults; `guardar`
seguido de `cargar` conserva los valores; migración de claves ausentes no rompe.

**Riesgos:** claves nuevas en versiones futuras → tolerar ausencias (defaults por clave).
**Aceptación:** cerrar con Hilos=2 + Modo ligero off + en la pestaña Aplanar y reabrir
deja todo igual, y “Examinar…” abre en la última carpeta.

---

## Fase 3 · Progreso legible — §3.1, §3.2 · **M** — ✅ HECHA (2026-09-18)

Implementada en `gui/pestana_base.py`: la barra pasa a modo `indeterminate`
(marquesina) cuando el progreso llega sin total (exploración/conteo) y vuelve a
`determinate` en cuanto se conoce; el estado muestra `NN %` + `hechas/total` y un ETA
aproximado por media móvil del ritmo (unidades/seg), oculto hasta un breve calentamiento
para no dar cifras erráticas. `_reset_progreso` limpia el estado al iniciar y `_fin`
detiene la marquesina. Tests: `tests/gui/test_progreso.py` (5). Suite: 60 gui / 362 total,
verde (el flaky `test_extensibilidad` de segundo root Tcl salta de forma intermitente).

**Objetivo:** que las fases sin total no parezcan colgadas y que se vea %/ETA.

**Se toca:** `gui/pestana_base.py` (`procesar_cola`, `_estado`, barra), quizá un helper
de formato en `gui/` (o reutilizar `core.formato.duracion`).

**Pasos:**
1. **Barra indeterminada** (§3.1): cuando `total == 0` (exploración/conteo), poner la
   barra en modo `indeterminate` (`barra.start()`); al llegar el primer `total`, `stop()`
   y volver a determinado. Reset limpio en `_iniciar`/`_fin`.
2. **Porcentaje** (§3.2): mostrar `NN %` en el texto de estado junto a `hechas/total`.
3. **ETA** (§3.2): media móvil de unidades/seg calculada en `procesar_cola` (guardar
   marca de tiempo y hechas de la muestra anterior); estimar restante y formatear con
   `duracion`. Ocultar ETA hasta tener una muestra estable.

**Pruebas:** con `total=0` la barra entra en indeterminado; con progreso simulado el %
se calcula bien; el ETA no aparece con una sola muestra.

**Riesgos:** ruido del ETA en tareas irregulares → usar media móvil y no mostrarlo si la
varianza es alta. **Aceptación:** durante la exploración inicial la barra se mueve; en
régimen, se ve `45 % · 120/266 · ~1 m 30 s`.

---

## Fase 4 · Remate final unificado + “Abrir carpeta” — §3.3, §3.4, §3.5 · **S–M** — ✅ HECHA (2026-09-18)

Implementada en `gui/pestana_base.py` (`_acciones_finales`, `_abrir_resultado`, fila de
acciones bajo la barra) y `gui/componentes.py` (`abrir_en_explorador`, robusto y
multiplataforma). Al completar: línea con la ruta en consola (sin modal), botón "Abrir
carpeta" (salvo `ofrece_abrir = False`, que pone Eliminar) y, si el handoff casa una
gemela, un enlace "Ir a <tarea> →" que navega a ella. Se retiraron los `showinfo` de fin
de Comprimir/Descomprimir/Eliminar (los modales quedan solo para errores y confirmaciones
destructivas). Tests: `tests/gui/test_remate.py` (8). Suite: 68 gui / 370 total, verde.

**Objetivo:** terminar sin modales que interrumpan, de forma consistente en todas las
tareas, y ofrecer abrir el resultado.

**Se toca:** `gui/pestana_base.py` (`_fin`/`_al_terminar`, estado final); las pestañas
que hoy hacen `showinfo` (`comprimir`, `descomprimir`, `eliminar`) para retirarlo.

**Pasos:**
1. **Remate no modal** (§3.3): al completar, mostrar en el estado “Completado · <ruta>”
   y, si hay `ruta_final`, un botón/enlace **“Abrir carpeta”** junto al estado. Reservar
   `messagebox` solo para errores y avisos destructivos.
2. **Abrir carpeta** (§3.4): helper `abrir_en_explorador(ruta)` (`os.startfile` en
   Windows; `xdg-open`/`open` como respaldo). Robusto y silencioso.
3. **Unificar** (§3.3): quitar los `showinfo` de las tres pestañas; el remate pasa a ser
   común en `PestanaBase`. Verificar que Eliminar mantiene su confirmación previa (esa
   sí modal, no se toca).
4. **Handoff visible** (§3.5): cuando `sugerir_entrada` rellena a la gemela, indicarlo
   (p. ej. estado “Listo para Descomprimir” + enlace que navega a esa pestaña con
   `App.mostrar`).

**Pruebas:** al completar una tarea con `ruta_final`, el estado muestra el remate y el
botón; ninguna pestaña abre `showinfo` en COMPLETADO; el enlace de handoff navega.

**Riesgos:** cambiar de modal a no-modal reduce “acuse de recibo”; compensarlo con el
remate bien visible. **Aceptación:** encadenar Comprimir→Descomprimir sin cerrar ni un
diálogo, con “Abrir carpeta” funcionando.

---

## Fase 5 · Consola con acciones — §3.6 · **S** — ✅ HECHA (2026-09-18)

Implementada en `gui/app.py`: fila de acciones (Limpiar / Copiar / Guardar…) en la
cabecera de la consola, menú contextual (clic derecho: Copiar / Seleccionar todo /
Limpiar) y empty state ("Aquí aparecerá el registro de la tarea.") que se retira al
primer mensaje y se restaura al limpiar. `Copiar` usa la selección si la hay, `Guardar…`
vuelca a un `.txt` elegido. Estilo de botón compacto `tema.MINI` (monitor estrecho).
Tests: `tests/gui/test_consola.py` (7); el conftest limpia la consola compartida entre
tests. Suite: 75 gui / 377 total, verde.

**Objetivo:** poder limpiar, copiar y guardar el registro, y no dejar la consola vacía
sin contexto.

**Se toca:** `gui/app.py` (`_construir_monitor`, cabecera de la consola, `texto_log`).

**Pasos:**
1. Botones **Limpiar** / **Copiar** / **Guardar registro…** en la cabecera “Consola”
   (junto a “Registro detallado”). “Guardar” usa `filedialog.asksaveasfilename`.
2. **Menú contextual** (clic derecho) con Copiar/Seleccionar todo/Limpiar.
3. **Empty state** (§3.6, §7.4): placeholder gris “Aquí aparecerá el registro de la
   tarea.” cuando el log está vacío; se borra al primer mensaje.

**Pruebas:** “Limpiar” vacía el `Text`; “Copiar” deja el contenido en el portapapeles;
el empty state aparece/desaparece.

**Riesgos:** el `Text` está `state="disabled"`; recordar habilitar/deshabilitar alrededor
de las operaciones (como ya hace `escribir_lote`). **Aceptación:** las tres acciones
funcionan y el placeholder se comporta.

---

## Fase 6 · Teclado y foco — §4.1, §4.4 · **M** — ✅ HECHA (2026-09-18)

Implementada en `gui/app.py` (`_configurar_atajos`, `_atajo_boton`, `_atajo_escape`),
`gui/tema.py` (anillo de foco visible: `focuscolor=PRIMARY` en Fantasma/Mini/Pestañas) y
el rótulo del botón de volver `[ ← Menú ]`. Atajos globales enganchados al Toplevel (los
eventos de teclado de los hijos siempre llegan ahí por bindtags): **Ctrl+Enter** =
Iniciar/Continuar, **Ctrl+P** = Pausar, **Ctrl+.** = Cancelar, **Esc** = volver al menú /
cerrar Ayuda. Iniciar/Pausar/Cancelar usan `boton.invoke()`, que respeta el estado
`disabled` (mismo comportamiento que el clic: p. ej. Cancelar solo mientras se trabaja).
Tests: `tests/gui/test_teclado.py` (8). Suite: 83 gui / 385 total, verde.

**Decisiones de diseño (resolviendo la ambigüedad del borrador):**
- **Esc = navegación, no cancelar.** El borrador listaba «Esc = volver» y «Esc =
  Cancelar»; se resolvió a favor de navegar (menos sorpresa; cancelar es Ctrl+. con su
  confirmación). Esc no navega si hay tarea en marcha ni si el foco está en un campo
  editable (ahí Esc es del widget: cerrar un desplegable, etc.).
- **Los atajos se enganchan en App**, no en cada pestaña: en Tk los eventos de teclado
  de un widget hijo solo suben por sus bindtags hasta el Toplevel, no hasta el frame de
  la pestaña, así que un binding por pestaña no capturaría el teclado con el foco en un
  Entry. App enruta a la tarea visible (`_tarea_actual`).
- Se pospone el **foco automático** al abrir una tarea (podría sorprender y fragilizar
  tests); la tabulación por defecto de Tk basta, ahora con anillo visible.

**Objetivo:** operar sin ratón y con foco visible.

**Se toca:** `gui/app.py` (bindings globales, `Esc`), `gui/pestana_base.py` (atajos de la
pestaña activa), `gui/tema.py` (revisar `focuscolor`/anillo de foco).

**Pasos:**
1. `Esc` = volver a la portada si no está bloqueado (o cerrar Ayuda).
2. Atajos de la pestaña activa: `Enter`/`Ctrl+Enter` = Iniciar (si habilitado),
   `Ctrl+P` = Pausar, `Ctrl+.`/`Esc` = Cancelar (con la confirmación existente). Solo
   actúan sobre la pestaña visible.
3. Orden de tabulación y **anillo de foco** visible y coherente con el tema en botones,
   entries y checks.
4. Tooltip “Volver” en `[ ← ]` (usa el componente de la Fase 8; si esta va antes, dejar
   solo el texto “← Categorías”).

**Pruebas:** con una pestaña visible, invocar el atajo de Iniciar dispara `_iniciar`;
`Esc` vuelve a portada solo si no está bloqueado.

**Riesgos:** atajos que se disparen con foco en un `Entry` de texto (p. ej. Enter). Acotar
por foco/estado. **Aceptación:** flujo completo de una tarea usando solo teclado.

---

## Fase 7 · Divisor ajustable — §4.2 · **M** — ✅ HECHA (2026-09-18)

Implementada en `gui/app.py`: el layout de dos columnas por `grid` pasa a un
`ttk.PanedWindow` horizontal con divisor arrastrable (navegador `weight=1`, monitor
`weight=0`, así el monitor conserva su ancho y el navegador absorbe el redimensionado).
La posición se fija cuando el paned tiene tamaño real (`_al_configurar_paned` →
`_restaurar_sash`) a partir del ancho de monitor guardado (por defecto 280 px, con
límites sensatos para no ahogar la tarea) y se persiste en `monitor_ancho`
(`_guardar_prefs`, Fase 2). Sash tematizado en `gui/tema.py` (`Sash`, verde al pasar el
ratón). Tests: `tests/gui/test_layout.py` (5). Suite: 88 gui / 390 total, verde.
**Recomendado:** una comprobación visual rápida (el layout no se puede verificar sin
ventana mapeada; los tests cubren la construcción y la aritmética del sash).

**Objetivo:** que el usuario reparta el ancho entre navegador y monitor, y se recuerde.

**Se toca:** `gui/app.py` (`__init__` del layout: sustituir el `grid` de dos columnas por
`ttk.PanedWindow`). Depende de la **Fase 2** para persistir la posición del sash.

**Pasos:**
1. Envolver navegador y monitor en un `ttk.PanedWindow` horizontal con “sash”
   arrastrable; conservar un mínimo sensato para el monitor.
2. Guardar/restaurar la posición del sash vía `preferencias` (Fase 2).
3. (Opcional) por debajo de cierto ancho de ventana, permitir colapsar el monitor.

**Pruebas:** el layout arranca con proporciones por defecto; mover el sash y reabrir
conserva la posición (con Fase 2).

**Riesgos:** el estilo del `PanedWindow`/sash con el tema `clam` puede necesitar ajuste en
`tema.py`. **Aceptación:** arrastrar el divisor funciona y persiste.

---

## Fase 8 · Tooltips y ayuda ampliada por opción — §5.3, §4.5, §5.4 · **M** — ✅ HECHA (2026-09-18)

Componente **`Tooltip`** reutilizable en `gui/componentes.py` (Toplevel sin bordes,
retardo, texto actualizable en caliente) + `tema.estilo_tooltip`. Aplicado a: **rutas
largas** (§4.5) — el Entry desplaza la vista al final y muestra la ruta completa al pasar
el ratón (`_enganchar_ruta_larga`); **radios de hilos atenuados** (§5.4) — tooltip
explicando por qué; **navegación** (§4.4) — tooltip en `[ ← Menú ]` y en los enlaces
autor/café.

**Decisión de §5.3 (el usuario eligió NO acortar):** se mantiene la descripción gris
inline de cada opción tal cual y se añade, al pasar el ratón por encima de la opción (el
control o su descripción, **sin ningún aviso visual**), un tooltip con información **aún
más detallada** (edge cases, rendimiento, irreversibilidad, ejemplos). Infra: parámetro
`detalle=` en `_check`/`_combo`/`_entry` + `_tooltip_opcion`. Contenido añadido en las 8
pestañas (una entrada de `detalle` por opción). Tests: `tests/gui/test_tooltip.py` (7).
Suite: 95 gui / 402 total, verde.

**Objetivo:** reducir el ruido del panel (hoy toda la ayuda va siempre visible) y explicar
estados con tooltips.

**Se toca:** nuevo `Tooltip` en `gui/componentes.py`; `gui/pestana_base.py` (`_add_ayuda`/
`_check`/`_combo`/`_entry` para admitir ayuda “bajo demanda”); `gui/app.py` (radios de
hilos, `←`, ☕).

**Pasos:**
1. **Componente `Tooltip`** reutilizable (aparece al `<Enter>`, se oculta al `<Leave>`,
   con el estilo del tema).
2. **Ayuda condensada**: dejar visible solo lo esencial y mover el detalle largo a un
   tooltip “?” junto a cada opción. Mantener compatibilidad con las pestañas actuales
   (el parámetro `ayuda` puede seguir existiendo; añadir `ayuda_detalle`).
3. **Rutas largas** (§4.5): al fijar el valor de un `Entry` de ruta, `xview_moveto(1)` y
   tooltip con la ruta completa.
4. **Radios de hilos atenuados** (§5.4): tooltip “Tu equipo no aprovecha tantos hilos”.

**Pruebas:** el `Tooltip` se muestra/oculta; una pestaña con ayuda condensada sigue
construyéndose sin error; el mapeo `_validar`→`Opciones` no cambia.

**Riesgos:** no romper el layout de las secciones al condensar. Hacerlo pestaña por
pestaña. **Aceptación:** el panel de opciones cabe con menos scroll y la ayuda sigue
accesible por tooltip.

---

## Fase 9 · Instanciación perezosa de pestañas — §1.2 · **M** — ✅ HECHA (2026-09-18)

Implementada en `gui/app.py`: las pestañas ya no se crean todas en el `__init__`; se
guardan las **clases** (`_clases`) y cada instancia se crea la primera vez que se muestra
(`_instancia(clase)`, único punto de creación, cacheado en `_por_clase`). `pestanas` pasa
a ser una **propiedad** que devuelve solo las ya instanciadas (la bomba y el cierre solo
atienden a esas). `_pintar_barra` pinta la barra sin instanciar (usa `clase.nombre` y
crea al pulsar); `_entrar`/`mostrar`/`pestana` instancian bajo demanda; **`sugerir_entrada`
instancia la consumidora** aunque no se haya abierto (el handoff crea la gemela para
rellenar su origen). En portada no se crea ninguna: arranque más rápido en el equipo
lento. Tests: nuevo `tests/gui/test_lazy.py` (arranque sin instancias, mostrar crea solo
una, handoff crea la consumidora); el `conftest` fuerza las 8 en la App de sesión
compartida (para los tests que las enumeran) y `test_extensibilidad` comprueba `_clases`
en vez de instancias. Suite: 96 gui / 398 total, verde (los dos tests de segundo root Tcl
saltan de forma intermitente). **Nota:** el arranque ya no depende del nº de pestañas; el
handoff y el cierre se cubrieron con tests antes de tocar, por ser la fase de mayor
superficie de regresión.

**Objetivo:** acelerar el arranque construyendo cada pestaña solo al abrirla por primera
vez. Va **después** de la Fase 1 (la bomba ya no recorre todas las pestañas en reposo).

**Se toca:** `gui/app.py` (`__init__`, `_por_clase`, `mostrar`/`_seleccionar`, `_bomba`,
`_cerrar`, `sugerir_entrada`, `pestana`).

**Pasos:**
1. En vez de instanciar las 8 pestañas en el `__init__`, guardar las **clases** por
   descriptor y crear la instancia perezosamente en `_seleccionar/mostrar` (cachear en
   `_por_clase`).
2. Ajustar todo lo que hoy asume “todas creadas”: `_bomba`/`procesar_cola` iteran solo
   sobre instanciadas; `_cerrar`/`comprobar_cierre` igual; `sugerir_entrada` **debe
   instanciar** la consumidora si aún no existe (para poder rellenar su origen).
3. Revisar `estado_barra` y los tests de navegación/handoff.

**Pruebas (críticas):** handoff a una gemela **no abierta todavía** la instancia y le fija
el origen; cierre con una sola pestaña creada funciona; navegación entre categorías crea
las pestañas al vuelo.

**Riesgos:** el handoff y los tests existentes asumen instancias creadas. Es la fase con
más superficie de regresión: cubrir con tests antes de tocar. **Aceptación:** arranque
perceptiblemente más rápido en el equipo lento; handoff y cierre intactos.

---

## Fase 10 · Diálogo de reanudación con botones claros — §6.1 · **S** — ✅ HECHA (2026-09-18)

Implementada: `DialogoReanudar` (+ atajo `dialogo_reanudar`) en `gui/componentes.py`, un
Toplevel modal propio, tematizado, con botones **Continuar / Empezar de cero / Cancelar**
(Enter=Continuar, Esc/cerrar=Cancelar), que devuelve el mismo contrato de antes
(False=continuar, True=de cero, None=cancelar). El constructor solo crea los widgets; el
modal (transient+grab+wait_window) lo hace `mostrar()`, así se prueba sin bloquear.
`gui/pestana_base._preguntar_reanudar` lo usa en vez del `askyesnocancel` con la leyenda
«Sí=Continuar · No=Empezar de cero». El `conftest` neutraliza el diálogo (por defecto
«continuar»). Tests: `tests/gui/test_reanudar.py` (5). Suite: 101 gui / 403 total, verde.

**Objetivo:** sustituir el `askyesnocancel` (Sí/No/Cancelar + leyenda) por un diálogo con
botones etiquetados.

**Se toca:** nuevo diálogo en `gui/componentes.py` (o `gui/dialogos.py`);
`gui/pestana_base.py` (`_preguntar_reanudar`).

**Pasos:**
1. `Toplevel` modal propio con el texto y tres botones: **Continuar** / **Empezar de
   cero** / **Cancelar**, coherente con el tema, devolviendo el mismo contrato que hoy
   (`False`=continuar, `True`=de cero, `None`=cancelar).
2. Reemplazar la llamada en `_preguntar_reanudar` sin cambiar la lógica de arriba.

**Pruebas:** el diálogo devuelve el valor correcto según el botón; `_iniciar` reacciona
igual que antes (mismo contrato).

**Riesgos:** modales propios y foco/grab en Tk; usar `transient`+`grab_set`+`wait_window`.
**Aceptación:** al reanudar tras cerrar, los botones dicen exactamente qué hacen.

---

## Fase 11 · Legibilidad: fuente y DPI — §5.1, §5.2 · **M** — ✅ HECHA (2026-09-18)

Implementada en `gui/tema.py` + `gui/app.py`: la fuente pequeña (ayuda, consola, tooltips,
versión) sube de **8 a 9 pt**; `tema.activar_dpi()` declara el proceso DPI-aware en Windows
ANTES de crear el root (Tk dibuja nítido en HiDPI en vez del escalado borroso del SO) y
`tema._ajustar_escala()` fija la escala de Tk al DPI real (fuentes en puntos con tamaño
físico correcto). En pantallas estándar (96 DPI) la escala coincide con el valor por
defecto: **sin cambios ni regresión**; en HiDPI se corrige nitidez y tamaño. Tests:
`tests/gui/test_escala.py` (3, ligeros: el efecto es visual). Suite: 104 gui / 406 total,
verde. **Requiere comprobación visual** (arranque real, y en un monitor escalado si es
posible). **Diferido (opcional):** ajuste manual de «escala de texto» del usuario — el
auto-escalado por DPI cubre el caso principal.

**Objetivo:** que la app se lea bien en pantallas pequeñas y HiDPI.

**Se toca:** `gui/tema.py` (`_crear_fuentes`, tamaños), arranque en `gui/app.py`
(DPI-awareness / `tk scaling`).

**Pasos:**
1. Subir la ayuda de 8→9 pt y revisar contrastes mínimos.
2. **DPI-awareness en Windows** (`ctypes` `SetProcessDpiAwareness`) y/o `tk.call('tk',
   'scaling', factor)` según el monitor, calculado una vez al arrancar.
3. (Opcional, encaja con Fase 2) exponer un ajuste de “escala de texto”.

**Pruebas:** difícil automatizar; validación manual en un monitor HiDPI y en 1366×768.

**Riesgos:** el DPI-awareness cambia el tamaño real de la ventana y afecta a
`_area_trabajo`. Probar antes/después de maximizar. **Aceptación:** texto cómodo en 4K sin
romper el layout en pantallas pequeñas.

---

## Fase 12 · Pulido visual — §7 · **S–M**

**Objetivo:** rematar detalles de imagen y coherencia.

**Se toca:** `gui/constantes.py` (enlaces), `gui/app.py` (tarjetas, iconos), `gui/tema.py`
(tema claro opcional).

**Pasos:**
1. **Enlaces reales** (§7.2): fijar `URL_AUTOR`/`URL_CAFE` definitivos y anteponer
   `https://` (hoy `URL_CAFE` no lleva esquema y `webbrowser.open` puede fallar).
2. **Affordance de tarjetas** (§7.5): añadir un “›” a la derecha de cada tarjeta de
   categoría.
3. **Iconografía** (§7.1): glifo por categoría/tarea (caracteres/emoji, sin dependencias).
4. **Tema claro** (§7.3, opcional): segundo juego de tokens en `tema.py` + preferencia
   (Fase 2) para elegir. Bajo riesgo por estar el color centralizado.

**Pruebas:** `tema.configurar` sigue idempotente; la galería `python -m gui.tema` refleja
los cambios; el tema claro (si se hace) no rompe estilos.

**Aceptación:** enlaces abren bien; portada más escaneable.

---

## Fase 13 · Opcionales / a futuro — §4.3, §8

- **Drag & drop** (§4.3): requiere `tkinterdnd2` (dependencia externa) → decisión de
  producto por la política “sin dependencias”. Si se acepta, aislarlo tras un try/import
  para degradar con elegancia si no está.
- **i18n** (§8): centralizar literales de `gui/` y `tasks/*/pestana.py`+`ayuda.py`. Trabajo
  amplio y transversal; solo si se plantea otro idioma.

---

## Orden recomendado y dependencias

```
Fase 1 (bomba) ─┬─► Fase 9 (perezosa)        [9 depende de 1]
                │
Fase 2 (prefs) ─┼─► Fase 7 (PanedWindow)     [7 guarda el sash → 2]
                └─► Fase 11 (escala texto)   [opcional → 2]
Fase 3 (progreso)   Fase 4 (remate+abrir)    independientes
Fase 5 (consola)    Fase 6 (teclado)         independientes
Fase 8 (tooltips) ──► la usa Fase 6 (tooltip del ←)  [suave]
Fase 10 (reanudar)  Fase 12 (pulido)         independientes
```

**Ruta corta de máximo retorno (si hay que elegir):** 1 → 2 → 3 → 4 → 6. Con eso la app
descansa en reposo, recuerda preferencias, muestra progreso legible, termina sin modales
y se maneja con teclado.

**Regla de cierre de cada fase:** `pytest -m gui` (y la suite completa antes de fusionar),
app arrancada y verificada a mano, y una línea en `REESTRUCTURACION.md`/este archivo con
el commit. Nada de `core/` ni motores tocados.
</content>
