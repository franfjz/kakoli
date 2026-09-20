# Roadmap: menú de pestañas en DOS niveles (categorías → tareas)

Objetivo: agrupar tareas relacionadas (p. ej. las opuestas Comprimir/Descomprimir)
bajo una **categoría** ("Compresión"), y navegar en **dos niveles**:

1. **Menú inicial** (nivel 1): la tira de pestañas muestra las **categorías**.
2. **Categoría** (nivel 2): al entrar, la tira muestra las **tareas** de esa
   categoría (Comprimir / Descomprimir), con una **pestaña "←"** a la izquierda
   para volver al menú inicial.

Restricciones del encargo:
- **Solo dos niveles**: menú inicial y las tareas de cada categoría. Nada más
  profundo.
- La elección (categoría, y luego tarea) **reutiliza el espacio de la tira de
  pestañas** (no se añade otra fila).
- Debe ser **fácil de replicar** en futuras ampliaciones (más categorías, más
  tareas) e **integrarse en el sistema de escalabilidad** ya hecho (A–H).

No cambia la lógica de los motores. Este documento **solo diseña**: no toca código.
Referencias: `escalabilidad.md` (A–H), `ARQUITECTURA.md`, `GUI.md`,
`roadmap_diseno_gui.md`.

Fecha: 2026-09-06.

---

## 0. Punto de partida (lo que ya hay)

- **Registro plano** `App.TABS = (PestanaComprimir, PestanaDescomprimir,
  PestanaEliminar)`; `App` las instancia y las mete en UN `ttk.Notebook`
  (`self.cuaderno`), cada una como pestaña con rótulo de corchete `[ Nombre ]`
  (`_rotulo`).
- `App.pestanas` (instancias), `App._por_clase`, `App.pestana(clase)` (lookup),
  `App.sugerir_entrada(ruta, tipo)` (handoff), `App.bloquear(activa)` /
  `desbloquear()` (una tarea a la vez, deshabilitando el resto de pestañas del
  Notebook), monitor derecho COMPARTIDO, barra inferior POR tarea.
- `PestanaBase` es un `ttk.Frame` autocontenido (`nombre`, `MOTOR`, `ENTRADAS`,
  opciones declarativas, `produce`, `_validar`/`_ejecutar` genérico, `_fin`…).

El cambio es de **navegación/organización de pestañas**, no de las tareas.

---

## 1. Modelo de datos (evolución del registro de C)

Se sustituye el registro plano por uno de **dos niveles**:

```python
@dataclass
class Categoria:
    nombre: str                       # "Compresión"
    tareas: list[type[PestanaBase]]   # [PestanaComprimir, PestanaDescomprimir]
    # opcional a futuro: icono / descripción corta para la portada

class App:
    MENU: tuple[Categoria, ...] = (
        Categoria("Compresión", [PestanaComprimir, PestanaDescomprimir]),
        Categoria("Eliminar",   [PestanaEliminar]),
    )
```

- **`App.TABS` se deriva** de `MENU` (lista plana de todas las tareas) para no
  romper nada de A–H: `App.pestanas`, `App._por_clase`, `App.pestana(clase)` y
  `App.sugerir_entrada` siguen operando sobre TODAS las tareas (recorren el plano).
  → Añadir una tarea a una categoría existente = añadir su clase a `tareas`
  (una edición). Añadir una categoría = añadir un `Categoria` a `MENU` (una
  edición). Se mantiene el espíritu de C ("una línea para escalar").
- **Dos niveles garantizados por la estructura**: `Categoria.tareas` contiene solo
  hojas (clases de `PestanaBase`); no hay categorías dentro de categorías.
- Una categoría puede tener **1..N tareas**. Con 1 tarea, el nivel 2 se muestra
  igual (con "←" + esa tarea) por coherencia (D3).

---

## 2. La navegación reutiliza el espacio de la tira de pestañas

Se reemplaza el `ttk.Notebook` único por dos piezas dentro del área izquierda:

- **`barra_nav`** (la "tira"): una fila horizontal de botones-pestaña que se
  **repuebla según el nivel**.
- **`area_tarea`** (el contenido): un contenedor donde vive el frame de la tarea
  activa (se muestran/ocultan con `grid`/`grid_remove`; se crean todas una vez al
  arrancar, como ahora).

Comportamiento:

| Nivel | `barra_nav` muestra | `area_tarea` muestra |
|---|---|---|
| 1 (menú) | `[ Compresión ]` `[ Eliminar ]` … (una por categoría) | portada/bienvenida breve (sin barra inferior) |
| 2 (categoría) | `[ ← ]`  `[ Comprimir ]` `[ Descomprimir ]` | el frame de la tarea seleccionada |

- **Entrar**: clic en `[ Compresión ]` → nivel 2, con la **primera tarea**
  seleccionada (D5).
- **Volver**: clic en `[ ← ]` (primer botón, a la izquierda) → nivel 1.
- **Cambiar de tarea** (nivel 2): clic en `[ Comprimir ]` / `[ Descomprimir ]`
  intercambia el frame en `area_tarea`.
- La tarea activa lleva el punto: `[ Comprimir • ]` (se reutiliza `_rotulo`).

**Por qué un strip propio y no seguir con `ttk.Notebook`** (D1): un `Notebook`
asocia "pestaña ↔ contenido" y "seleccionar = mostrar contenido"; la navegación en
dos niveles necesita "seleccionar categoría = **cambiar el conjunto de
pestañas**" y un "volver", que en `Notebook` obliga a trucos (tabs sin contenido,
`<<NotebookTabChanged>>` para entrar). Un strip de botones repoblable modela el
árbol menú→categoría→tarea de forma directa, con el "←" como un botón más a la
izquierda, y encaja mejor con el modelo declarativo (`MENU`). Coste: reimplementar
el aspecto de pestaña con estilos de botón (se hace en la Fase de tema, reutilizando
la paleta y el look de corchete ya definidos).

Alternativa considerada (D1-bis, no recomendada): **híbrido** — mantener el
`Notebook` para las tareas del nivel 2 y poner a su izquierda un botón "←" y, para
el nivel 1, otra fila/ío de botones de categoría. Menos reestilado, pero coordina
dos widgets y deja el nivel 1 fuera del `Notebook`; peor encaje conceptual.

---

## 3. Una sola tarea a la vez (se conserva la garantía)

Regla actual: mientras un motor trabaja, el resto de pestañas quedan bloqueadas.
Con dos niveles se traduce a: **mientras una tarea corre**, en `barra_nav`
- se **deshabilita "←"** (no se puede salir de la categoría), y
- se **deshabilitan las tareas hermanas** (solo la activa, con `•`, es accesible).

Al terminar/pausar, se reactivan. Así **no** se puede volver al menú ni lanzar otra
tarea (ni de otra categoría) mientras hay trabajo — misma invariante que hoy, ahora
expresada sobre el strip. `App.bloquear(activa)` / `desbloquear()` se adaptan al
navegador (mismos nombres y semántica; dejan de tocar `cuaderno.tab(...)`).

---

## 4. Integración con el resto (sin regresiones)

- **Monitor derecho** (perfil + consola + info app): COMPARTIDO, sin cambios; se ve
  en ambos niveles.
- **Barra inferior** (acción/pausar/estado/progreso): sigue POR tarea, dentro del
  frame de cada `PestanaBase`; en nivel 1 no hay tarea → no hay barra inferior.
- **Handoff `sugerir_entrada`** (G): recorre todas las tareas y rellena el origen de
  la que consuma el tipo producido. Como Comprimir y Descomprimir quedan en la MISMA
  categoría, tras comprimir el usuario ya tiene "Descomprimir" a un clic con el
  origen puesto (la agrupación mejora este flujo). Decisión D6: el handoff **solo
  rellena el campo** (no fuerza navegación); opcional a futuro, ofrecer "ir a
  Descomprimir".
- **`_bomba`** (vacía las colas de las 3 tareas cada 150 ms), `comprobar_cierre`,
  `_cerrar`: operan sobre `App.pestanas` (todas las instancias, creadas al
  arrancar) → sin cambios.
- **Escalabilidad (A–H)**: intacta. `MENU` es el nuevo punto único para añadir
  categorías/tareas; todo lo demás (motor con `ejecutar`, `PestanaX` declarativa,
  `PlanLista`, `correr_cli`) no cambia.

---

## 5. Decisiones clave (leer antes de implementar)

- **D1 — Strip propio de botones** en vez de `ttk.Notebook` (ver §2). Recomendado.
- **D2 — `App.MENU` (categorías) es la fuente de verdad**; `App.TABS`/lista plana se
  deriva de él (compatibilidad con A–H).
- **D3 — Categorías de 1 tarea** muestran nivel 2 igual (con "←" + la tarea), por
  coherencia. (Opción futura: atajo que entre directo; se descarta ahora por
  uniformidad.)
- **D4 — "Eliminar"** queda como su propia categoría por ahora. A futuro puede
  reagruparse (p. ej. "Mantenimiento"); es solo mover su clase en `MENU`.
- **D5 — Al entrar en una categoría** se selecciona su primera tarea. Al volver y
  reentrar, se puede recordar la última (nice-to-have) o resetear a la primera
  (por defecto: primera).
- **D6 — Handoff** solo rellena el campo destino; no navega automáticamente (§4).
- **D7 — Rótulos**: se conserva el corchete `[ … ]` y el `•` de tarea activa
  (`_rotulo`). Categoría: `[ Compresión ]`. Volver: `[ ← ]` (o `[ ‹ ]`).
- **D8 — Estado inicial**: arranca en nivel 1 (menú de categorías) con una portada
  breve; no auto-entra en ninguna categoría.

---

## 6. Fases

- **Fase 1 — Modelo**: `Categoria` + `App.MENU`; derivar de él la lista plana de
  tareas y mantener `App.pestanas`/`_por_clase`/`pestana`/`sugerir_entrada`. Sin
  cambiar la UI todavía (se puede seguir pintando plano como checkpoint).
  **ESTADO: HECHA** (2026-09-06). Dataclass `Categoria(nombre, tareas)`;
  `App.MENU = (Categoria("Compresión",[Comp,Descomp]), Categoria("Eliminar",[Elim]))`
  sustituye a `App.TABS`. `App.clases_tarea()` (classmethod) aplana `MENU` y la usa
  `__init__` para instanciar las pestañas (UI plana idéntica, mismo orden). El resto
  de A–H (pestana/_por_clase/sugerir_entrada/bloqueo) intacto. Tests test_cd/test_be
  actualizados para añadir vía `App.MENU` (+`Categoria`) en vez de `App.TABS`.
  Verificado: `--version`, MENU/clases_tarea correctos, regresión completa verde.
- **Fase 2 — Navegador de dos niveles**: sustituir el `Notebook` por
  `barra_nav` (strip repoblable) + `area_tarea` (contenedor). Lógica de navegación:
  render de nivel 1 (categorías) y nivel 2 (`←` + tareas), entrar/volver/cambiar de
  tarea, mostrar/ocultar frames. Frames de tarea creados una vez al arrancar.
  **ESTADO: HECHA** (2026-09-06). Se eliminó `ttk.Notebook`/`self.cuaderno`. Nuevo
  layout izq: `barra_nav` (fila de botones-pestaña repoblable) + `area_tarea`
  (contenedor; los frames de tarea se crean una vez con padre `area_tarea` y se
  muestran/ocultan con grid/grid_remove). Métodos: `_pintar_barra` (nivel 1 =
  categorías; nivel 2 = `[ ← ]` + tareas), `_ir_menu`, `_entrar(categoria)`,
  `_seleccionar(pes)`, `mostrar(clase)` (navegar por clase; para handoff/scripts),
  `estado_barra()` (introspección para pruebas), portada del nivel 1
  (`_mostrar/_ocultar_portada`). Estilos nuevos `tema.PESTANA`/`PESTANA_ACT` (mismo
  look que las tabs: inactiva CONTAINER/gris, activa BORDE/verde). Se conserva
  `_rotulo` (corchete + `•`). Verificado headless (estado_barra en ambos niveles) y
  visual (nav1_menu = `[ Compresión ] [ Eliminar ]` + portada; nav2 =
  `[ ← ] [ Comprimir ] [ Descomprimir ]` con Comprimir activa).
- **Fase 3 — Bloqueo one-task-at-a-time**: adaptar `App.bloquear/desbloquear` al
  strip (deshabilitar "←" y hermanas; `•` en la activa; reactivar al terminar).
  **ESTADO: HECHA** (2026-09-06, integrada en la Fase 2 porque `bloquear/
  desbloquear` dejaban de usar `cuaderno`). `bloquear(activa)` pone `_bloqueado=True`,
  fija la activa y repinta: `[ ← ]` y las hermanas quedan `disabled`, la activa
  lleva `•`. `desbloquear()` reactiva. Además `_entrar/_seleccionar/_ir_menu`
  ignoran la orden si `_bloqueado` (defensa extra). Verificado en test_func_ml
  (durante la tarea: `_bloqueado` + `←` y hermana deshabilitadas; al terminar,
  reactivado), test_func_gui, test_func_pausa y test_cd.
- **Fase 4 — Portada e integración fina**: panel de bienvenida del nivel 1, estados
  vacíos (sin barra inferior), recordado (o no) de la última tarea, revisar el
  handoff dentro de la categoría.
  **ESTADO: HECHA** (2026-09-06). Portada del nivel 1 con **tarjetas de categoría
  clicables** (`_tarjeta_categoria`: nombre en verde + sus tareas como subtítulo;
  cursor mano; borde que pasa a verde al pasar el ratón vía
  `tema.estilo_tarjeta_menu(frame, resaltada)`); se puede entrar desde la tarjeta o
  desde la barra. **Recuerdo de la última tarea** por categoría
  (`App._ultima_tarea`): `_entrar` abre la última usada (la primera la primera vez),
  `_seleccionar` la registra. Estado vacío del nivel 1 sin barra inferior (no hay
  tarea). Handoff Comprimir→Descomprimir intacto (misma categoría). Verificado
  (test_menu): tarjetas por categoría, entrar desde tarjeta, recuerdo de última
  tarea al reentrar.
- **Fase 5 — Tema**: estilos de las pestañas de navegación (categoría, tarea
  activa/inactiva, botón "←", hover, deshabilitado), reutilizando la paleta y el
  look de corchete. En `tema.py`, con nombres de estilo nuevos.
  **ESTADO: HECHA** (2026-09-06). Cuatro estilos en `tema.py`: `PESTANA` (tarea
  inactiva: CONTAINER/gris, hover→blanco), `PESTANA_ACT` (tarea activa: BORDE/verde,
  negrita), `PESTANA_CAT` (categoría nivel 1: CONTAINER/texto claro, negrita,
  hover→verde) y `PESTANA_VOLVER` ("←": gris, negrita, hover→verde). Paddings
  homogéneos, `disabled` muy atenuado. `_pintar_barra` usa el estilo según el rol.
  Verificado (test_menu comprueba los estilos por rol) + capturas (nivel 1 con
  categorías resaltadas + tarjetas; nivel 2 con '←'/activa/inactiva).
- **Fase 6 — Verificación y docs**: headless (construir `MENU`, navegar 1↔2, entrar
  en categoría, volver, bloqueo durante tarea, reactivación), visual (capturas de
  nivel 1 y nivel 2), funcional (round-trip + handoff Comprimir→Descomprimir).
  Actualizar `ARQUITECTURA.md` (§7 GUI), `GUI.md` y `escalabilidad.md`.
  **ESTADO: HECHA** (2026-09-06). Headless: test_menu (navegación 1↔2, entrar desde
  tarjeta, recuerdo de última tarea, estilos por rol), test_cd (bloqueo genérico:
  `←`+hermanas deshabilitadas, `•`), test_gui_fase5 (rótulos de corchete en ambos
  niveles). Funcional: bench round-trip 5/5; test_func_ml/gui/pausa (bloqueo durante
  tarea + reactivación); test_g (handoff Comprimir→Descomprimir). Visual: capturas
  nivel 1 (portada + tarjetas + categorías) y nivel 2 (`[ ← ]` + tareas). Docs:
  reescritos `ARQUITECTURA.md` §7 (GUI) y `GUI.md` §1-§2 (navegador de 2 niveles,
  monitor compartido, entradas/opciones declarativas, `_ejecutar` genérico, bloqueo,
  handoff). Regresión completa verde.

---

## MENÚ DE PESTAÑAS — COMPLETO (fases 1–6)

La GUI pasó de tres pestañas planas a un **menú de categorías → tareas en dos
niveles** con `[ ← ]` para volver, portada con tarjetas y "una tarea a la vez"
sobre la nueva barra. `App.MENU` es el punto único para escalar (integrado con
A–H). Sin `ttk.Notebook`. Round-trip, handoff y bloqueo intactos.

Orden de entrega recomendado: 1 → 2 → 3 → 5 → 4 → 6 (el tema puede ir antes que la
portada; cada fase es verificable por separado).

---

## 7. Riesgos y notas

- **Reestilado de la tira**: al dejar el `Notebook`, hay que reproducir el aspecto
  de pestaña con botones (Fase 5). Mitiga: ya existen estilos de botón y la estética
  de corchete en `tema.py`.
- **Pruebas que usan `app.cuaderno`**: varios tests de scratchpad consultan
  `app.cuaderno.tab(i, ...)`. Al cambiar a strip, hay que **actualizar esos tests**
  para consultar el navegador (p. ej. estado de los botones). Es tooling, no la app.
- **Overflow horizontal**: si en el futuro hay muchas categorías o tareas, la tira
  podría no caber. Nota para más adelante: envolver o desplazar la tira (fuera de
  alcance ahora, pocos elementos).
- **No romper invariantes**: monitor compartido, una tarea a la vez, modelo
  hilo+cola+`_bomba`, `_validar` en el hilo principal, handoff — todo se conserva.
- **Accesibilidad** (nice-to-have): navegación por teclado entre pestañas del strip.

---

## 8. Resultado esperado

Con esto, la GUI pasa de tres pestañas planas a un menú de **categorías → tareas**
en dos niveles, con "←" para volver, sin filas extra y sin perder ninguna garantía.
Añadir una futura pareja/categoría de tareas relacionadas (otra transformación de
directorios) será: escribir sus `PestanaX` (como en A–H) y **añadir un `Categoria`
a `App.MENU`** — el navegador las pinta y gestiona solo.
