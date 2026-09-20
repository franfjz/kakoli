# Arquitectura de kakoli

Referencia del estado actual del proyecto tras la reestructuración por capas y por
tarea (ver `REESTRUCTURACION.md` para el historial de la refactorización, fases 0–14).
Última revisión: 2026-09-16.

---

## 1. Qué es

**kakoli** es una app de escritorio (Python 3.11+, Tkinter, sin dependencias de
terceros) con **herramientas de gestión de directorios y archivos**, agrupadas en
categorías; a menudo una tarea y su inversa:

| Categoría | Tareas | Qué hace |
|---|---|---|
| Combinación | Combinar · Descombinar | Funde varios árboles en un principal (índice JSON reversible) y lo deshace. |
| Compresión | Comprimir · Descomprimir | Comprime una carpeta en **ZIPs anidados** (un `.zip` por subcarpeta) y la extrae. |
| Aplanado | Aplanar · Desaplanar | Lleva todos los archivos a una carpeta (codificando la ruta en el nombre) y reconstruye. |
| Renombrado | Renombrar | Renombra en bloque sin tocar la extensión, con vista previa. |
| Eliminar | Eliminar | Borrado definitivo y recursivo (no papelera). |

Cada tarea corre en su propio motor (pausable, reanudable, paralelizable según el
equipo). Interfaz de dos niveles (categorías → tareas) con un panel de rendimiento
común. Los motores son además **CLIs**: `python -m tasks.<tarea>.motor …`.

---

## 2. Estructura (fuente autoritativa)

Tres paquetes por responsabilidad + `kakoli.py` (raíz de composición) y `bench.py`.

```
kakoli/
├─ kakoli.py               # Raíz de composición: App(REGISTRO) + main() + --version
├─ bench.py                # Banco de pruebas: round-trip byte a byte + métricas
├─ build_nuitka.ps1        # Build con Nuitka (onefile .exe: fuentes + iconos + LTO)
│
├─ core/                   # Núcleo estable, agnóstico de dominio y de la GUI (sin Tkinter)
│  ├─ resultado.py         #   Resultado, EstadoResultado, Cancelado
│  ├─ opciones.py          #   OpcionesBase (detallado/politica + recorrido de FS)
│  ├─ formato.py           #   humano/duracion/ahora + PASO_REGISTRO
│  ├─ cli.py               #   correr_cli, Interrupcion, preguntar_consola
│  ├─ reanudable.py        #   RegistroReanudable: progreso reanudable (JSONL) común
│  ├─ json_util.py         #   guardar_json/cargar_json: JSON atómico, común
│  ├─ cache_arbol.py       #   CacheArbol: caché del árbol explorado (evita re-explorar)
│  ├─ control.py           #   Control: parada común (pausa/cancelar/PAUSA/límite)
│  ├─ recursos/            #   Equipo (subpaquete): sondas (mide) + politica (decide hilos)
│  ├─ paralelo.py          #   Plan, PlanLista, Ejecutor (pool de workers)
│  ├─ registro.py          #   Categoria, DescriptorTarea, Registro (contrato de tarea)
│  └─ ejecucion.py         #   Ejecucion: hilo de trabajo + cola de eventos (sin Tk)
│
├─ gui/                    # Estructura general de la interfaz (no conoce las tareas)
│  ├─ tema.py              #   Paleta, fuentes, estilos ttk/tk, icono
│  ├─ app.py               #   App(registro): navegación 2 niveles, portada, monitor,
│  │                       #   bloqueo, bomba de colas, vista de Ayuda
│  ├─ pestana_base.py      #   PestanaBase: esqueleto común de una pestaña de tarea
│  ├─ componentes.py       #   MarcoDesplazable, fila_texto (piezas reutilizables)
│  ├─ contexto.py          #   ContextoApp (Protocol): lo que App ofrece a una pestaña
│  ├─ campo.py             #   Campo (campo de entrada declarativo)
│  ├─ constantes.py        #   versión/marca, enlaces, ajustes de GUI, politica_desde, _valor_ui
│  ├─ preferencias.py      #   config.json: rendimiento, última tarea, carpeta, geometría
│  └─ ayuda.py             #   Texto general de la Ayuda (intro + cierre)
│
├─ tasks/                  # Una carpeta por tarea + manifiesto + formatos compartidos
│  ├─ __init__.py          #   REGISTRO (categorías → tareas): fuente de verdad para escalar
│  ├─ formatos/            #   contratos en disco compartidos entre gemelas:
│  │  ├─ formato_zip.py         #     marca del ZIP anidado (Comprimir/Descomprimir)
│  │  ├─ indice_combinacion.py  #     índice JSON (Combinar/Descombinar)
│  │  └─ nombres_aplanado.py    #     códec de nombres (Aplanar/Desaplanar)
│  └─ <tarea>/             #   comprimir, descomprimir, combinar, descombinar,
│     ├─ __init__.py           #   aplanar, desaplanar, renombrar, eliminar. Cada una:
│     ├─ motor.py              #     motor (lógica + CLI)
│     ├─ pestana.py            #     interfaz (Pestana*(PestanaBase))
│     ├─ ayuda.py              #     su sección de Ayuda (SECCIONES)
│     └─ __init__.py           #     DESCRIPTOR (para el registro)
│
├─ fuentes/  iconos/       # Space Mono (.ttf) + arte/.ico
├─ tests/                  # core/ · gui/ · tasks/ (+ pares) · soporte/ · test_fronteras.py
└─ docs/                   # esta referencia + REESTRUCTURACION.md + roadmaps (históricos)
```

---

## 3. Capas y reglas de dependencia

```
              kakoli.py            (raíz de composición: une gui + tasks)
               │      │
               ▼      ▼
   tasks/<t>/pestana ──► gui  (pestana_base, componentes, tema, campo, contexto)
        │                 │
        ▼                 ▼
   tasks/<t>/motor ─────► core ◄── gui
        │
        ▼
   tasks/formatos    (solo la pareja de gemelas que lo usa)
```

Reglas (las verifica **`tests/test_fronteras.py`** por análisis AST; línea base VACÍA):

| Rol | Puede importar |
|---|---|
| `core` (comun/recursos/paralelo/registro/ejecucion) | solo `core` + stdlib. **Nunca** Tkinter, `gui` ni tareas. |
| `gui` (app/pestana_base/componentes/tema/campo/contexto/constantes/ayuda) | `core`, `gui`. **Nunca** una tarea. |
| `tasks/formatos/*` | `core`. Nunca una tarea. |
| `tasks/<t>/motor` | `core`, `tasks/formatos` (el de su pareja). Nunca otra tarea ni Tkinter. |
| `tasks/<t>/pestana` | `core`, `gui`, `tasks/formatos`, y **su propio** `motor`. Nunca otra tarea. |
| `tasks/__init__` (manifiesto) | `core` + los DESCRIPTOR de cada tarea. |
| `kakoli.py` | cualquiera (compone `gui` + `tasks`). |

**Estabilidad:** `core` cambia mucho menos que las tareas; añadir una tarea no lo toca.
**Independencia:** dos tareas no se conocen; las gemelas solo comparten su módulo de
`tasks/formatos` (la duplicación entre tareas es aceptable a cambio de aislamiento).

---

## 4. Contrato de un motor

Todos los motores exponen la MISMA firma (la GUI y la consola los llaman igual):

```python
def ejecutar(entradas: dict, opts, *, log, progreso, pausar, cancelar, confirmar) -> Resultado
```
- `entradas`: dict con claves **definidas por cada tarea** (no hay un juego único):
  `{"origen"}` (Renombrar, Eliminar), `{"origen","destino"}` (la mayoría) o
  `{"principal","fuentes"}` (Combinar). El docstring de cada `ejecutar` es la FUENTE
  DE VERDAD de sus claves, y deben coincidir con las que produce el `_validar()` de su
  pestaña (`{"entradas","opts"}`). `ejecutar` reparte a un `procesar(...)` interno.
- `Resultado.estado` debe ser un valor de `core.resultado.EstadoResultado`
  (`COMPLETADO|PAUSADO|NADA|CANCELADO|ERROR`); se valida al construir (un typo salta).
  El enum hereda de `str`, así que `Resultado("error")` y `== EstadoResultado.ERROR`
  siguen siendo equivalentes.
- `log(str)` (avisos empiezan por `[!]`), `progreso(hechas, total, fraccion, etiqueta)`,
  `pausar() -> bool` (para AL TERMINAR la unidad en curso), `cancelar() -> bool` (ABORTA
  la unidad en curso y descarta su fragmento; ver `core.resultado.Cancelado`),
  `confirmar(pregunta, defecto) -> bool` (None = no preguntar).
- `Resultado` (dataclass en `core.resultado`): `estado` (completado | pausado | nada |
  cancelado | error), `procesadas`, `restantes`, `total`, `errores`, `ruta_final`,
  `mensaje`, `segundos`.
- `class Opciones(core.opciones.OpcionesBase)`: hereda `detallado`, `politica`
  (`recursos.PoliticaHilos`) y las opciones de recorrido de FS (`seguir_enlaces`,
  `omitir_ocultos`), y añade sus campos.
- Opcional: `info_reanudable(entradas, opts) -> dict|None` (Comprimir/Aplanar/Desaplanar):
  activa el modal «Continuar / Empezar de cero» de la GUI.
- `main()` reduce el CLI a: parsear args → construir `opts`+`entradas` → `core.cli.correr_cli`.

Desde el hilo de trabajo, `log`/`progreso` son seguros (en la GUI vuelcan a una cola;
en consola son `print`). Las variables Tk se leen solo en el hilo principal.

---

## 5. Registro de tareas y handoff (`core.registro`)

- **`DescriptorTarea`**: `id`, `nombre`, `clase` (la pestaña, fábrica de UI **opaca**
  para `core`: no se instancia ahí), `produce`/`consume` (tipos de artefacto), `ayuda`.
- **`Categoria`**: `nombre`, `descripcion`, `tareas` (tuplas de descriptores).
- **`Registro`**: valida (ids/clases únicos, categorías no vacías) y ofrece
  `descriptores()`, `descriptor_de(clase)`, `consumidor_de(artefacto)`.
- **`tasks/__init__.py`** arma el `REGISTRO` (una línea por tarea); `kakoli.py` se lo
  pasa a `App(REGISTRO)`. La GUI no conoce ninguna tarea concreta.
- **Handoff entre gemelas por ARTEFACTO** (no por clase): la productora declara
  `produce="zip_anidado"` y la consumidora `consume="zip_anidado"`; al terminar,
  `App.sugerir_entrada(ruta, artefacto)` busca el consumidor en el registro y le rellena
  el origen. Artefactos: `zip_anidado`, `carpeta_combinada`, `carpeta_aplanada`.

---

## 6. Ejecución y GUI

- **`core.ejecucion.Ejecucion`** (sin Tk): lanza el trabajo en un hilo daemon y lo
  comunica por una cola de eventos (`log`/`prog`/`fin`); `recoger()` drena sin bloquear;
  la excepción del trabajo se convierte en `Resultado("error")`. `PestanaBase` la usa y
  solo pinta widgets a partir de los eventos.
- **`gui.App`**: ventana maximizada; navegación en dos niveles (portada de categorías →
  tareas con `[ ← ]`); monitor derecho COMPARTIDO (equipo detectado, Rendimiento
  —Hilos + Modo ligero—, consola, versión); **una tarea a la vez** (`bloquear`/
  `desbloquear`); una sola `_bomba` (cada 150 ms) vacía las colas de todas las pestañas
  **solo mientras hay una tarea en marcha** —se arma en `bloquear` y se detiene sola al
  terminar, así el proceso no despierta en reposo—; vista de Ayuda componida desde el registro. Las pestañas leen las opciones comunes por
  `opciones_comunes()` (contrato `ContextoApp`), no de atributos internos de `App`.
- **`PestanaBase`**: campos de entrada declarativos (`ENTRADAS`/`Campo`), opciones por
  secciones (`_seccion`/`_check`/`_combo`/`_entry`), Iniciar/Pausar, progreso, el modal de
  reanudación y el handoff. Cada pestaña define `nombre`, `MOTOR`, `_validar()` →
  `{"entradas","opts"}`, y opcionalmente `_confirmar`/`_al_terminar`/`produce`/`consume`.
  La clase de pestaña cumple `core.registro.FabricaPestana` (el contrato mínimo que
  App usa: `nombre`, `procesar_cola`, `ocupada`, `pedir_cierre`, `establecer_origen`),
  verificado por `tests/test_conformidad_tareas.py`.

---

## 7. Invariantes (no romper)

- **Round-trip byte a byte** de las gemelas reversibles (validado en `bench.py` y en
  `tests/tasks/pares/`): `Descomprimir(Comprimir(x)) == x`, etc.
- **Reanudable tras cerrar**: el registro de progreso común `core.reanudable.
  RegistroReanudable` (JSONL, O(1) por unidad) lo usan Comprimir (`_estado_zip.jsonl`,
  vía `Estado`, subclase con la lógica de árbol), Aplanar y Desaplanar
  (`.kakoli_aplanado.json`/`.kakoli_desaplanado.json`); Combinar reanuda por su índice
  y Descomprimir por el propio destino. Escritura atómica (`.part` + `os.replace`).
- **Caché del árbol explorado** (evita re-recorrer el disco al reanudar): su gemelo
  «instantánea», `core.cache_arbol.CacheArbol`, guarda el resultado del recorrido en un
  JSON `{formato, firma, payload}` (`core.json_util`, atómico) y lo recupera si la
  **firma** casa —las opciones que cambian LO QUE PRODUCE el recorrido (`seguir_enlaces`/
  `omitir_ocultos`, y las fuentes en Combinar)—. Lo usan Comprimir (`_arbol_zip.json`,
  con `serializar_arbol`/`deserializar_arbol` para su árbol de `InfoDir`), Aplanar y
  Desaplanar (`.kakoli_aplanado_arbol.json`/`.kakoli_desaplanado_arbol.json`, lista de
  rutas) y Combinar (`.kakoli_combinacion_arbol.json`, rutas por fuente; solo con
  índice). Se descarta con `--reiniciar` y al completar la tarea. Descomprimir no lo usa
  (sus unidades aparecen al extraer, el árbol no se conoce de antemano) ni Renombrar/
  Eliminar (no son reanudables por unidad). El patrón: `cache.obtener(explorar, …)`.
- **Seguridad anti-zip-slip / path-traversal**: `_destino_seguro` en los motores que
  extraen o reconstruyen (rechaza `..`, absolutas y `:` en Windows).
- **Buen ciudadano**: prioridad baja (modo ligero) + throttling por carga externa.
- **Formatos en disco estables**: marca `zip-anidado/1`, `zip-anidado-estado/2`,
  `kakoli-combinacion/1`, `kakoli-reanudable/1`.

---

## 8. Añadir una tarea (receta)

1. Crear `tasks/<tarea>/` con `motor.py` (`Opciones(OpcionesBase)` + `ejecutar` +
   `main()`/`correr_cli`; si mapea subcarpetas independientes, `Ejecutor(n).ejecutar(
   PlanLista(subs), …)`), `pestana.py` (`Pestana*(PestanaBase)` con `_validar`), `ayuda.py`
   (`SECCIONES`) e `__init__.py` con el `DESCRIPTOR` (id, nombre, clase, produce/consume,
   ayuda). Si tiene gemela con formato en disco, ponerlo en `tasks/formatos/`.
2. Añadir **una línea** al `REGISTRO` de `tasks/__init__.py` (en su categoría).
3. Crear `tests/tasks/<tarea>/` (motor por `ejecutar`, CLI) y, si es reversible,
   `tests/tasks/pares/test_<x>_<y>.py`.

**Reanudable + caché del árbol (opcional, para tareas que recorren el disco):**
si la tarea es reanudable y hace un recorrido caro del disco al empezar, adóptalo con
dos piezas del núcleo, sin tocar `core/`:
  - Progreso: `core.reanudable.RegistroReanudable` (salta lo ya hecho) — ver Aplanar.
  - Árbol: `core.cache_arbol.CacheArbol` (evita re-recorrer al reanudar). Basta:
    ```python
    cache = CacheArbol(salida / ".mi_tarea_arbol.json", firma=_firma_arbol(opts))
    items = cache.obtener(lambda: list(mi_walk(origen, opts)),
                          reiniciar=opts.reiniciar, log=log)
    ```
    `_firma_arbol` devuelve solo las opciones que cambian el recorrido (`seguir_enlaces`/
    `omitir_ocultos`, filtros…). Si el árbol no es JSON nativo, pasa `serializar`/
    `deserializar` (como Comprimir). Borra la caché al completar (`cache.borrar()`) si el
    progreso también se borra. Si tiene gemela, pon el nombre del fichero en
    `tasks/formatos/` para que aquella lo excluya de su recorrido.

No se toca `core/` ni `gui/`. Lo verifica `tests/gui/test_extensibilidad.py`.

---

## 9. Pruebas

- **`tests/core/`** (sin Tk): `recursos` (tabla de hilos), `paralelo`, `comun`,
  `registro`, `ejecucion`.
- **`tests/tasks/<tarea>/`** (sin Tk): cada motor por su contrato; **`tests/tasks/pares/`**:
  round-trips bidireccionales (identidad por firma completa).
- **`tests/gui/`** (marcador `gui`; un solo `App` por sesión): arranque, navegación,
  bloqueo, handoff, mapeo `_validar`→`Opciones`, componentes, extensibilidad.
- **`tests/test_fronteras.py`**: guardián de dependencias (AST) — reglas por rol +
  imports libres DENTRO de una misma tarea (paquete vertical). Los tests importan los
  módulos reales directamente (la indirección de la migración se retiró).
- Entorno: venv con Python 3.13; el código es compatible con 3.11. `pytest`/`pyflakes`
  son dependencias solo de desarrollo (`requirements-dev.txt`).

---

## 10. Notas

- La máquina de referencia del roadmap de rendimiento es un portátil antiguo (2 núcleos/
  HDD/~4 GB); el auto suele dar 1 hilo. Detalle en `core/recursos.py`.
- `bench.py` conserva sus propios generadores de árboles (herramienta autónoma; no importa
  de `tests/`). Mide en caliente, así que subestima el castigo del HDD en frío.
- Los `docs/roadmap_*.md`, `GUI.md` y `escalabilidad.md` son **históricos** (describen el
  diseño por fases o la estructura anterior `nucleo/motores/clases`); esta referencia y
  `REESTRUCTURACION.md` son los documentos vivos.
