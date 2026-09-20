# Reestructuración de kakoli — auditoría arquitectónica y roadmap por fases

Documento de especificación para ejecutar la reestructuración fase a fase.
Fecha de la auditoría: 2026-09-15. Análisis por lectura estática del código (sin
ejecutar la app ni `bench.py`).

**Leyenda de etiquetas:**
- **[H]** hecho observado en el código.
- **[I]** interpretación arquitectónica.
- **[R]** recomendación.
- **[D]** decisión que requiere confirmación del usuario.

---

## 0. Estado de ejecución

| Fase | Nombre | Estado |
|---|---|---|
| 0 | Línea base reproducible y andamiaje de tests | **HECHA** (2026-09-15) |
| 1 | Caracterización de `core`, motores y pares (sin Tk) | **HECHA** (2026-09-16) |
| 2 | Caracterización de la GUI y guardián de fronteras en modo trinquete | **HECHA** (2026-09-16) |
| 3 | Correcciones previas sin cambio de estructura | **HECHA** (2026-09-16) |
| 4 | Paquetes `core/` y `gui/` (movimiento mecánico) | **HECHA** (2026-09-16) |
| 5 | Contrato de tarea y registro en `core`; `App` desacoplada | **HECHA** (2026-09-16) |
| 6 | GUI común: `gui/componentes.py` y `PestanaBase` sin fugas | **HECHA** (2026-09-16) |
| 7 | Ejecución sin Tk en `core` e interfaz de contexto explícita | **HECHA** (2026-09-16) |
| 8 | Piloto: `tasks/renombrar/` y manifiesto `tasks/__init__.py` | **HECHA** (2026-09-16) |
| 9 | `tasks/eliminar/` | **HECHA** (2026-09-16) |
| 10 | Par Aplanado + `tasks/formatos/nombres_aplanado.py` | **HECHA** (2026-09-16) |
| 11 | Par Combinación + `tasks/formatos/indice_combinacion.py` | **HECHA** (2026-09-16) |
| 12 | Par Compresión + `tasks/formatos/formato_zip.py` | **HECHA** (2026-09-16) |
| 13 | Retirada de la estructura antigua; `kakoli.py` como raíz de composición | **HECHA** (2026-09-16) |
| 14 | Validación arquitectónica final y documentación | **HECHA** (2026-09-16) |

**REESTRUCTURACIÓN COMPLETA (fases 0–14).** La app quedó en `core/` (núcleo estable sin Tk)
← `gui/` (interfaz genérica) ← `tasks/` (8 tareas verticales + formatos + manifiesto) ←
`kakoli.py`. Guardián de fronteras estricto (BASELINE vacía). Suite: 240 passed en 3.13.

**Decisiones ya tomadas por el usuario:**
- **D14 — Intérprete:** venv (`.venv/`) con el **Python 3.13** instalado en el equipo
  de desarrollo. El código debe seguir siendo compatible con Python 3.11 (requisito
  declarado en `README.md`): no usar sintaxis ni APIs exclusivas de 3.12+.
- **Documentos de tareas pendientes:** se guardan en `docs/`.

---

## 1. Resumen ejecutivo

- **[H] Organización actual.** Kakoli está organizado **por capa técnica**, no por tarea:
  `nucleo/` (base común) ← `motores/` (lógica) ← `clases/` (interfaz) ← `kakoli.py`.
  Tiene 8 tareas en 5 categorías: Combinar/Descombinar, Comprimir/Descomprimir,
  Aplanar/Desaplanar, Renombrar y Eliminar. Tamaño aproximado: `nucleo` 1.909 líneas,
  `motores` 3.655, `clases` 2.202 y `bench.py` 769.

- **[H] Lo que ya está bien, y es mucho:**
  - Los 8 motores comparten un contrato uniforme:
    `ejecutar(entradas, opts, *, log, progreso, pausar, confirmar) -> Resultado`.
  - Ningún motor importa Tkinter ni importa a otro motor.
  - La base común de rendimiento (`recursos`, `paralelo`) es genérica.
  - Las pestañas son declarativas (`ENTRADAS`, `_check`/`_combo`).

- **[I] El problema de fondo no es el acoplamiento entre motores, sino la dispersión de
  cada tarea.** Una tarea vive repartida en 4–6 archivos compartidos:
  - `motores/motor_X.py` y `clases/pestana_X.py`;
  - los mapeos de desplegables en `clases/constantes.py`;
  - su texto en `clases/ayuda_contenido.py`;
  - su registro y su enlace con la tarea gemela en `clases/menu.py`;
  - los re-exports de `kakoli.py`.

  Además, la ventana principal y el punto de entrada **importan tareas concretas**, y
  `nucleo` contiene código Tkinter (`tema.py`).

- **[H] No hay ni un test versionado en el repositorio.** Unos 31 tests vivieron en el
  scratchpad de sesiones anteriores y no están aquí. `.pytest_cache` está vacío. La
  única verificación versionada es `bench.py`, que cubre los tres pares reversibles,
  pero ni Eliminar, ni Renombrar, ni la GUI.

- **[H] Evidencia de ese riesgo: hay un fallo latente.** `clases/pestana_descomprimir.py:63`
  usa `threading.Event()` sin importar `threading`.
  - Cuándo se dispara: el motor pide confirmación porque la carpeta destino ya existe y
    está completa (`motores/motor_descomprimir.py:307`).
  - Qué pasa: se produce un `NameError` en el hilo de trabajo y la tarea termina en
    «Error» en lugar de preguntar.
  - Origen: es un import que se perdió al trocear `kakoli.py`, y ningún test lo detectó.

- **[I] `ARQUITECTURA.md` no describe la arquitectura objetivo.** Documenta, con desfases,
  la arquitectura **horizontal** actual. El objetivo (`core`/`tasks`/`gui`/`tests` con
  una carpeta por tarea) es **vertical**, así que hay que diseñarlo, no «terminar de
  implementarlo».

- **[R] Roadmap propuesto: 15 fases (0–14):**
  1. Red de seguridad: tests de caracterización y un guardián de imports en modo trinquete.
  2. Correcciones sin cambio de estructura.
  3. Creación de `core/` y `gui/` (movimiento mecánico).
  4. Registro de tareas en `core` y ventana principal desacoplada.
  5. Limpieza de la base común de la GUI.
  6. Migración tarea a tarea, empezando por un piloto (Renombrar) y terminando por Compresión.
  7. Retirada de la estructura antigua.
  8. Validación arquitectónica y documentación.

---

## 2. Arquitectura real actual

### 2.1 Estructura y módulos

| Paquete / archivo | Contenido real **[H]** | Rol conceptual **[I]** |
|---|---|---|
| `kakoli.py` (73) | `main()`, `--version`; re-exporta `App`, las 8 `Pestana*`, los 8 motores como alias y **constantes privadas** (`_CODIGOS`…) (`kakoli.py:25-52`) | Punto de entrada y fachada de compatibilidad para tests que ya no existen en el repo |
| `nucleo/comun.py` (308) | `Resultado`, `OpcionesBase`, `Interrupcion`, `RegistroReanudable`, `correr_cli`, `humano`/`duracion`/`ahora`, `PASO_REGISTRO` | core |
| `nucleo/recursos.py` (854) | Perfil de la máquina (sondas ctypes para Windows), `PoliticaHilos`, `calcular_hilos`, `techo_hilos`, `preparar`, regulador de carga, `bajar_prioridad` | core |
| `nucleo/paralelo.py` (226) | `Plan` (Protocol), `PlanLista`, `Ejecutor`, `_Regulador` | core |
| `nucleo/tema.py` (509) | Paleta, fuentes, estilos ttk/tk, icono. **Importa tkinter** (`nucleo/tema.py:29`) | **gui** (mal ubicado) |
| `motores/motor_*.py` (×8) | `Opciones(OpcionesBase)`, `rutas_validadas`, `ejecutar`, `procesar`, `info_reanudable` opcional, `main()` para consola | tasks (lógica) |
| `motores/formato_zip.py`, `indice_combinacion.py`, `nombres_aplanado.py` | Formatos en disco compartidos por cada par de gemelas | contratos entre gemelas |
| `clases/app.py` (633) | `App(tk.Tk)`: navegación en dos niveles, portada, Ayuda, monitor compartido, bloqueo, bomba de colas, cierre | gui global |
| `clases/pestana_base.py` (566) | `PestanaBase(ttk.Frame)`: entradas declarativas, secciones, scroll, hilo+cola, modal de reanudación, handoff | gui común (con fugas de tareas concretas) |
| `clases/pestana_*.py` (×8, 45–120) | Una pestaña por tarea | gui específica de tarea |
| `clases/menu.py` (38) | `MENU` (5 `Categoria`) y **mutación de clases al importar** (`produce_hacia`) (`clases/menu.py:36-38`) | registro |
| `clases/constantes.py` (63) | Identidad de la app, ajustes de GUI, `politica_desde` **y mapeos de desplegables de 4 tareas** | mezcla gui y tasks |
| `clases/ayuda_contenido.py` (108) | Texto de Ayuda de **todas** las tareas | mezcla gui y tasks |
| `clases/campo.py`, `categoria.py` | Dataclasses `Campo` y `Categoria` | gui / registro |
| `bench.py` (769) | Generación de árboles, firma, comparación, round-trip de comprimir, combinar y aplanar, reanudación y métricas | tests + herramienta |
| `build_nuitka.ps1` | Nuitka onefile; incluye `fuentes`, `iconos` | build |

### 2.2 Flujo de ejecución real **[H]**

**Arranque.**
- `kakoli.main()` → `App()` → `tema.configurar` y `aplicar_icono` → ventana maximizada
  (ctypes `SPI_GETWORKAREA`).
- `recursos.perfil()` mide la máquina **una vez al arrancar** para el monitor y `techo_hilos`.
- Se construye el monitor: equipo, rendimiento (`v_hilos`, `v_ligero`), consola
  (`v_detallado`) y pie.
- **Se instancian las 8 pestañas de golpe** (`clases/app.py:98`); cada una ejecuta
  `_construir()` → `_opciones()`.
- `_ir_menu()` muestra la portada y `after(150, _bomba)` arranca la bomba.

**Navegación.**
- Tarjeta → `_entrar(categoría)` → `_seleccionar(pestaña)`: `grid`/`grid_remove` sobre
  frames persistentes.
- Se recuerda la última tarea abierta en cada categoría.

**Ejecución de una tarea** (hilo principal → hilo de trabajo → hilo principal):
1. `PestanaBase._iniciar` (`clases/pestana_base.py:451`) llama a `_validar()` en el hilo
   principal. Esta lee variables Tk, llama a `MOTOR.rutas_validadas` y construye
   `Opciones`. Devuelve `{"entradas", "opts"}`.
2. `_preguntar_reanudar` llama a `MOTOR.info_reanudable` si existe → modal. Si el usuario
   elige «de cero», se hace `opts.reiniciar = True`.
3. `_confirmar` (confirmación propia de la tarea) → se deshabilitan los `_bloqueables` →
   hilo daemon `trabajo()` → `MOTOR.ejecutar(...)`. `log` y `progreso` escriben en una
   `queue.Queue`, y `pausar` es `Event.is_set`.
4. Dentro del motor: `recursos.preparar` (perfil + prioridad baja) → `calcular_hilos` →
   camino secuencial o `paralelo.Ejecutor(Plan…)` → `Resultado`.
5. Cualquier excepción del motor se convierte en `Resultado("error")`
   (`clases/pestana_base.py:488`).
6. `App._bomba` (cada 150 ms) → `procesar_cola` de cada pestaña → `App.escribir_lote`
   (colorea por prefijo con `_tag_log`) → `_fin`: estado, handoff `sugerir_entrada`,
   `_al_terminar`, `desbloquear`, `comprobar_cierre`.

**Cierre.** Si hay trabajo en marcha se pregunta → `pedir_cierre` (pausa ordenada) →
`destroy` cuando ninguna pestaña está ocupada.

**Consola.** `python -m motores.motor_X` → `argparse` → `rutas_validadas` →
`comun.correr_cli` (manejador de Ctrl+C, `log=print`, código de salida).

### 2.3 Comunicación, estado, patrones y aspectos transversales

**Comunicación GUI ↔ lógica [H].**
- Solo por el contrato de callbacks y `Resultado`. Los motores no conocen la GUI. ✓
- Excepción implícita: `App._tag_log` colorea según textos concretos que emiten los
  motores (`"Eliminado:"`, `"[Simulaci"`, `"Máquina:"`, `"Completado"`,
  `"Nada que hacer"`) (`clases/app.py:499-511`).
- Las pestañas acceden a atributos concretos de `App`: `self.app.v_detallado` en las 8,
  más `v_hilos`, `v_ligero`, `escribir_lote`, `bloquear`, `desbloquear`,
  `sugerir_entrada` y `comprobar_cierre`.

**Estado global o compartido [H]:**
- Variables Tk comunes en `App`.
- `recursos._prioridad_bajada`: la prioridad del proceso se baja una vez y **nunca se
  restaura**. Afecta también a la propia GUI.
- `lru_cache` de `leer_marca`.
- Fuentes registradas en `tema`.
- Atributos de clase mutados al importar `menu.py`.

**Patrones [H]:**
- Template Method: ganchos de `PestanaBase`.
- Motor como módulo-estrategia (`MOTOR = módulo`).
- Configuración declarativa (`Campo`, `ENTRADAS`).
- Productor-consumidor con cola y sondeo (`_bomba`).
- Protocol (`Plan`), registro (`MENU`) y fachada (`kakoli.py`).

**Configuración [H].**
- Sin persistencia: hilos, modo ligero y detallado se pierden al cerrar.
- Valores por defecto en `Opciones`/`PoliticaHilos`; umbrales como constantes de módulo
  en cada motor.

**Errores [H]:**
- Validación → `ValueError` → `messagebox`.
- Ejecución → `Resultado("error")`.
- Sondas de hardware «best-effort» con `except Exception: pass`, intencionado y documentado.
- Confirmación desde el hilo de trabajo (Descomprimir) → `after(0)` + `Event.wait(300)`:
  **responde el valor por defecto en silencio a los 5 minutos**
  (`clases/pestana_descomprimir.py:73`).

**Logging [H].** Solo el callback `log` (consola de la GUI, recortada a 2.000 líneas) o
`print` en consola. Sin módulo `logging` ni fichero de registro.

**Recursos [H]:**
- Escritura atómica: temporal `.part`/`.__parcial__` + `os.replace`.
- Hilos daemon y `ThreadPoolExecutor` con `with`.
- Archivo `PAUSA` como señal de pausa externa.
- Referencia viva al `PhotoImage` del icono.

**Tests [H]:**
- 0 en el repo.
- `bench.py` no es pytest: es un CLI con escenarios `rapido/ancho/profundo/mixto/polvo`.
- Los docs citan `test_exhaustivo.py`, `test_menu`, `test_cd`, `test_g`… en el
  scratchpad; no existen aquí.

**Entorno [H].** En el equipo de desarrollo actual está instalado Python **3.13.10**
(elegido para el venv, ver D14). Los `__pycache__` existentes son `cpython-311`.

### 2.4 Coste real de añadir una tarea hoy **[H]**

| Qué se toca | Tipo |
|---|---|
| `motores/motor_X.py` | nuevo |
| `clases/pestana_X.py` | nuevo |
| `clases/menu.py` (import + `Categoria` + quizá `produce_hacia`) | edición compartida |
| `clases/ayuda_contenido.py` | edición compartida |
| `clases/constantes.py` (si hay desplegables) | edición compartida |
| `kakoli.py` (re-export, por convención) | edición compartida |
| `bench.py` (si es reversible), `docs/GUI.md`, `README.md` | edición compartida |

`docs/escalabilidad.md` dice «motor + pestaña + **una línea** en MENU». En la práctica son
2 archivos nuevos y 2–5 archivos compartidos editados.

---

## 3. Arquitectura definida en `ARQUITECTURA.md`

### 3.1 Qué establece **[H]**

- **Capas:** `nucleo` (framework agnóstico de dominio **y de la GUI**) ← `motores` (un
  motor por tarea, sin GUI) ← `clases` (una clase o concepto por archivo) ← `kakoli`.
  «Sin ciclos».
- **Reglas:**
  - Los motores no orquestan hilos: piden un `Ejecutor`.
  - Las gemelas importan su formato del módulo **compartido**, no de la gemela.
  - Un motor nuevo hereda `OpcionesBase`, devuelve `Resultado` y usa `Ejecutor`.
- **Contrato uniforme** `ejecutar(entradas, opts, …)` con claves «uniformes»
  `origen`/`destino`, e `info_reanudable` opcional.
- **Invariantes:** round-trip byte a byte, reanudable tras cerrar, seguro entre hilos,
  anti-zip-slip, «buen ciudadano» (prioridad baja + throttling), una tarea a la vez,
  variables Tk leídas solo en el hilo principal.
- **Extensibilidad:** «Añadir una categoría o tarea = editar `MENU` (una línea)».
- **Pruebas:** `bench.py` (round-trip y métricas).

### 3.2 Qué **no** define **[H]**

- Organización por tarea (carpeta por tarea).
- Registro de tareas desacoplado de la clase Tk.
- Biblioteca de componentes GUI comunes.
- Reglas de dependencia `gui ↔ tasks` y `task ↔ task`.
- Estructura de `tests/` y tests de GUI o de arquitectura.

### 3.3 Contradicciones y desfases con el código

| Afirmación del documento | Realidad **[H]** |
|---|---|
| `nucleo` es «agnóstico de dominio y de la GUI» | `nucleo/tema.py` es Tkinter puro |
| Claves de `entradas` «uniformes: origen, destino» | Combinar usa `{"principal","fuentes"}` (`motores/motor_combinar.py:190`) |
| «Añadir tarea = editar MENU (una línea)» | Ver §2.4: también ayuda, constantes y re-export |
| §1 «tres pestañas», §3 «Los tres exponen», §7 «GUI (`kakoli.py`)», §8 «`python recursos.py .`» | 8 tareas; la GUI está en `clases/`; el comando es `python -m nucleo.recursos` (`docs/ARQUITECTURA.md:19`, `:82`, `:253`, `:323`) |
| Verificación exhaustiva con `test_exhaustivo.py` | No está en el repositorio |
| Docstrings de código: «tres motores», «`python3.11 tema.py`», «Mejora 5 … todavía inactiva» | Desfasados (el agrupado ya está implementado) |

### 3.4 Decisiones del documento que conviene revisar **[I]**

- **Registro basado en clases Tk y `produce_hacia` con referencias a clases.** Impide que
  `core` registre tareas y obliga a `menu.py` a conocer los pares.
- **Fachada de re-exports en `kakoli.py`.** Existía para tests del scratchpad; hoy solo
  acopla el punto de entrada a todo.
- **`clases/` «una clase por archivo».** Es organización por tipo, justo lo contrario del
  aislamiento por tarea que se busca.
- **Correctas y a conservar:** motores como módulos (no clases), el contrato de callbacks
  y **no** micro-trocear `recursos`/`paralelo`/`tema` por clase (decisión refinada en
  `roadmap_reorganizacion.md`, Fase 1).

---

## 4. Diferencias entre arquitectura real y objetivo

| Área | Situación actual | Situación objetivo | Diferencia | Prioridad |
|---|---|---|---|---|
| Red de tests | 0 tests en el repo; solo `bench.py` (3 pares) | `tests/core`, `tests/gui`, `tests/tasks`, pares y guardianes | Crear todo antes de mover nada | **Crítica** |
| Estado de partida | Cambios sin commitear; Python 3.13 en el equipo | Commit base limpio; venv 3.13 (código compat. 3.11) | Preparar el entorno | **Crítica** (bloquea la Fase 0) |
| Eje de organización | Horizontal: `nucleo`/`motores`/`clases` | Vertical: `core`/`gui`/`tasks/<tarea>` | Reubicar cada tarea en su carpeta | Alta |
| `core` | `comun` + `recursos` + `paralelo` + **`tema` (Tk)** | `core` sin Tk, con contrato y registro de tareas | Sacar `tema`; añadir el registro | Alta |
| Registro de tareas | `clases/menu.py` importa las 8 pestañas y muta clases; la identidad de una tarea es su clase Tk | Manifiesto de una línea por tarea; descriptor sin Tk en `core` | Mecanismo nuevo | Alta |
| GUI global | `App` importa 3 pestañas concretas (alias `tab_*`); `kakoli.py` importa todo | `gui` nunca importa `tasks`; `kakoli.py` compone | Invertir la dependencia | Alta |
| GUI común | `PestanaBase` monolítica con fugas (ZIP, combinar, compacto); el scroll repetido 3 veces; no hay módulo de componentes | `gui/componentes.py` + base limpia | Extraer y limpiar | Media |
| GUI de tarea | `pestana_X` + mapeos en `constantes` + texto en `ayuda_contenido` | `tasks/X/pestana.py` + `ayuda.py` | Agrupar | Media |
| Motores | Planos en `motores/`; contrato uniforme; sin Tk; sin cruces | `tasks/X/motor.py` sin cambio de lógica | Mover | Media |
| Contratos entre gemelas | `motores/{formato_zip, indice_combinacion, nombres_aplanado}` | `tasks/formatos/` con regla de uso | Mover y fijar la regla | Media |
| Dependencias entre tareas | `pestana_desaplanar` → `motor_aplanar`; `menu.py` enlaza los pares | 0 cruces (solo `tasks/formatos`) | Eliminar | Media |
| Ejecución hilo+cola | Dentro de `PestanaBase` (no se puede probar sin Tk) | Ejecutor sin Tk en `core` | Extraer | Media |
| Configuración | `constantes.py` mezcla app, GUI y 4 tareas | `gui/constantes` (app) + mapeos dentro de cada tarea | Partir | Media |
| Documentación | Desfasada y contradictoria | Reescrita y reflejada en tests guardianes | Actualizar al final | Media |
| Build / consola | `-m motores.motor_X`; `spec` analiza `kakoli.py` | `-m tasks.X.motor`; build verificado | Ajustar | Media |
| Errores | `Resultado` + captura en el hilo | Igual | Preservar y cubrir con tests | Baja |
| Registro de mensajes | Callback `log`; prefijos implícitos | Igual, con prefijos documentados y probados | Documentar | Baja |

---

## 5. Dependencias actuales

### 5.1 Grafo de imports real **[H]**

```text
kakoli.py ──► clases.app, clases.{campo,categoria,pestana_base,ayuda_contenido,constantes(privadas)},
              clases.pestana_* (8), motores.motor_* (8), nucleo.comun
clases.app ──► clases.menu ──► clases.pestana_* (8)
clases.app ──► clases.pestana_{comprimir,descomprimir,eliminar}          ✗ GUI global → tareas
clases.app ──► nucleo.{recursos,tema,comun}, clases.{categoria,pestana_base,ayuda_contenido,constantes}
clases.menu ═(mutación al importar)═► Pestana{Comprimir,Combinar,Aplanar}.produce_hacia   ✗
clases.pestana_X ──► clases.pestana_base, clases.constantes, motores.motor_X, nucleo.tema
clases.pestana_desaplanar ──► motores.motor_aplanar                      ✗ cruce entre tareas
clases.pestana_base ──► nucleo.{tema,recursos,comun}, clases.{campo,constantes}
clases.constantes ──► nucleo.recursos
motores.motor_X ──► nucleo.{comun,recursos,paralelo}, motores.<formato compartido>
motores.*  ──►  (nunca) tkinter / clases / otro motor                    ✓
nucleo.comun ──► nucleo.recursos ;  nucleo.{recursos,paralelo} ──► stdlib ✓
nucleo.tema ──► tkinter                                                   ✗ (nucleo «sin GUI»)
bench.py ──► motores.* (6, sin eliminar ni renombrar), nucleo.{recursos,comun}
tests ──► (no existen)                                                    ✗
```

**[H] Sin ciclos de import**, gracias a las anotaciones en forma de cadena (`"App"`) y a
`from __future__ import annotations`. Ninguno de los módulos no gráficos del núcleo
(`comun`, `recursos`, `paralelo`) depende de motores ni de clases. ✓

### 5.2 Traducción a las cuatro áreas conceptuales **[I]**

```text
core  ≈ nucleo.{comun, recursos, paralelo}
gui   ≈ clases.{app, pestana_base, campo, categoria} + nucleo.tema + parte de clases.{constantes, ayuda_contenido}
tasks ≈ motores.* + clases.pestana_* + parte de clases.{constantes, ayuda_contenido, menu}
tests ≈ bench.py (fuera de pytest)
```

| Relación | Estado | Problema |
|---|---|---|
| core → tasks | No existe ✓ | — |
| core → gui | **`nucleo/tema.py` es gui dentro de core** | Impide declarar «core sin Tk» |
| gui global → tasks | **Existe**: `app.py` (alias), `menu.py` (las 8), `kakoli.py` | Añadir o quitar una tarea toca la GUI global |
| gui de tarea → gui común | `pestana_X` → `PestanaBase` ✓ | `PestanaBase` sabe de ZIP, combinar y compacto |
| task → task | `pestana_desaplanar` → `motor_aplanar`; `menu.py` enlaza los pares | Una tarea conoce la implementación de otra |
| tasks → core | Motores → `nucleo` ✓ | — |

### 5.3 Acoplamientos que no aparecen en los imports **[H]**

1. **`_tag_log` depende del texto de los mensajes.** Si un motor cambia un mensaje, cambia
   el color en la consola.
2. **`PestanaBase` asume que el motor tiene `opts.reiniciar`** cuando expone
   `info_reanudable` (`clases/pestana_base.py:468`).
3. **`sugerir_entrada` depende de la forma de las entradas.** Busca pestañas cuyo
   `campos[0].clave == "origen"`.
4. **Hay dos fuentes del destino por defecto dentro de la misma tarea.** Por ejemplo,
   `clases/pestana_comprimir.py:60-64` y `motores/motor_comprimir.py:753-754` calculan
   ambos `<nombre>_zips`.

---

## 6. Problemas arquitectónicos

### Crítico

- **P1 — Sin red de tests versionada.**
  - [H] 0 tests. `bench.py` no cubre Eliminar (destructiva), Renombrar ni la GUI, que es
    la capa que más va a cambiar.
  - [I] Crítico porque la reestructuración propuesta es estructural. La extracción
    anterior ya introdujo un `NameError` (P2) que pasó sin detectarse.

- **P16 — Punto de partida no reproducible.**
  - [H] Hay cambios sin commitear (4 archivos + imágenes movidas) y un único commit.
  - [I] Mezclar esos cambios con la reestructuración impediría revertir una fase.

### Alto

- **P2 — Fallo latente: falta `import threading` en `clases/pestana_descomprimir.py`.**
  - [H] Rompe la confirmación durante la tarea en Descomprimir (ver §1).
  - Es funcional y no arquitectónico, pero debe corregirse **antes** de mover archivos.

- **P3 — Cada tarea está dispersa en archivos compartidos.**
  - [H] §2.4.
  - [I] Añadir o modificar una tarea edita archivos que comparten todas: riesgo de
    regresión cruzada y conflictos. Con N tareas, `constantes.py`, `ayuda_contenido.py`
    y `menu.py` crecen sin límite: son cajones de sastre.

- **P4 — El registro de tareas está atado a Tk.**
  - [H] La identidad de una tarea es su clase de pestaña. `menu.py` importa las 8 y muta
    atributos de clase al importarse.
  - [I] `core` no puede alojar el registro sin depender de Tk. El orden de import pasa a
    ser una dependencia oculta.

- **P5 — La GUI global conoce tareas concretas.**
  - [H] `clases/app.py:17-19` y `:102-104`; `kakoli.py` importa las 8 pestañas y los 8 motores.
  - [I] Imposible probar `App` con un registro ficticio. Borrar una tarea rompe la ventana.

- **P6 — `nucleo` contiene Tkinter.**
  - [H] `nucleo/tema.py`.
  - [I] Contradice el documento e impide una regla automática «core no importa tkinter».

- **P7 — `PestanaBase` mezcla responsabilidades y conoce tareas concretas.**
  - [H] Conocimiento de tareas concretas:
    - `usa_hilos`/`usa_compacto` definidos pero **nunca leídos** (`clases/pestana_base.py:40-41`);
    - `v_compacto`, solo de Comprimir (`:77`);
    - filtro «Archivos ZIP» para cualquier campo de tipo archivo (`:408`);
    - título «Añade un directorio a combinar» en cualquier campo de lista (`:394`);
    - suposición de `opts.reiniciar`.
  - [H] Responsabilidades mezcladas: maquetación, helpers de widgets, scroll, máquina de
    ejecución con hilos, modal de reanudación y handoff.
  - [I] Cada tarea nueva con una forma distinta obliga a editar la base. La ejecución no
    se puede probar sin Tk.

### Medio

- **P8 — Cruce entre tareas.** [H] `clases/pestana_desaplanar.py:10` y `:63` usan
  `motor_aplanar.separador_ok`, que ya vive en `nombres_aplanado`.
- **P9 — `constantes.py` como cajón de sastre.** [H] Mezcla identidad de la app, ajustes
  de GUI y mapeos de 4 tareas (`clases/constantes.py:35-55`). Los valores ya existen como
  tuplas en los motores (`CONFLICTOS`, `CRITERIOS`): dos fuentes de verdad.
- **P10 — `ayuda_contenido.py` centraliza el texto de todas las tareas.**
- **P11 — Duplicación perjudicial en la GUI común.** [H] El patrón Canvas + barra
  auto-oculta + rueda de ratón aparece 3 veces (`clases/pestana_base.py:151`,
  `clases/app.py:219`, `clases/app.py:320`). La fila Label + Entry + bloqueable aparece 4
  veces (Aplanar, Desaplanar, Combinar y el `_entry` de Renombrar).
- **P12 — Protocolo textual implícito motor → GUI** (`_tag_log`).
- **P13 — Interfaz implícita pestaña → `App`** (`self.app.v_detallado` en las 8 pestañas…).
- **P14 — Documentación no fiable como especificación** (§3.3).
- **P15 — Destino por defecto duplicado entre motor y pestaña** de la misma tarea.

### Bajo

- **P17 — `rutas_validadas` tiene efectos secundarios.** [H] Aplanar crea el destino y
  Combinar crea el principal, en `_validar`, antes de `_confirmar`: cancelar deja carpetas
  vacías. [R] Anotarlo; **no** cambiarlo durante la reestructuración.
- **P18 — Instanciación ansiosa** de todas las pestañas al arrancar.
- **P19 — Restos de la extracción:** comentarios «Pestaña 2: Descomprimir» al final de
  los archivos y docstrings desfasados.
- **P20 — Duplicación entre motores:** `PAUSE_NAME`, `_copiar`, `_gana_entrante`,
  `_walk_rel`; `_destino_seguro` con tres implementaciones distintas. [I] **Mayoritariamente
  aceptable**; aumenta independencia. `_destino_seguro` es de seguridad: vigilar con tests,
  no unificar.
- **P21 — `motor_comprimir.py` tiene 1.070 líneas**, pero es cohesivo.
- **P22 — La prioridad baja nunca se restaura** en el proceso de la GUI.

### Problemas de escala futura **[I]**

- **Con 20 tareas:** `menu.py` importa 20 pestañas; `constantes.py` y `ayuda_contenido.py`
  pasan de 1.000 líneas; `PestanaBase` acumula casos especiales; una modificación de una
  tarea puede romper otra por edición accidental de archivos compartidos, y sin tests no
  se detecta.
- **Handoff:** `produce='carpeta'` es demasiado genérico (Combinar y Aplanar producen
  «carpeta»). Por eso existe `produce_hacia` con clases, que no escala.
- **Barra de navegación:** sin overflow horizontal (ya anotado en `roadmap_menu_pestanas.md`).
- **`core` como cajón de sastre:** hoy **no** lo es. El riesgo aparece si se «unifica» la
  duplicación de los motores en `core`.

---

## 7. Decisiones arquitectónicas recomendadas

Deben cerrarse **antes de la Fase 0**. Se indica la recomendación y el problema que resuelve.

| Id | Decisión | Recomendación [R] | Resuelve | Confirmar [D] |
|---|---|---|---|---|
| D1 | Nombres de paquetes | `core/`, `tasks/`, `gui/`, `tests/`; identificadores internos en español | P3, P6 | Sí (alt.: `nucleo/tareas/gui/tests`) |
| D2 | Ubicación de los formatos compartidos por gemelas | `tasks/formatos/`. Solo los importan los motores y pestañas de su par. **No duplicar** (es el contrato del round-trip). **No a `core`** (son de dominio) | P8, D4 | Sí |
| D3 | Cómo se registran y descubren las tareas | **Manifiesto explícito** en `tasks/__init__.py`. **Sin autodescubrimiento** (un empaquetador no incluye módulos no importados; orden implícito; errores silenciosos) | P4, P5 | Sí |
| D4 | Identidad de una tarea | **Descriptor sin Tk** en `core` (`DescriptorTarea`: `id`, nombre, categoría, motor, fábrica de UI opaca, `produce`/`consume`, ayuda) + `Categoria` + `Registro` con validación | P4 | Sí |
| D5 | Handoff entre gemelas | Tipos de **artefacto** específicos (`"zip_anidado"`, `"carpeta_combinada"`, `"carpeta_aplanada"`); la productora declara `produce`, la consumidora `consume`. Adiós a `produce_hacia` con clases | P4, P8 | Sí |
| D6 | Dirección de dependencias | **`tasks → gui(común) → core`, `tasks → core`, `gui ↛ tasks`**; `kakoli.py` como raíz de composición | P5 | Sí |
| D7 | Ejecución hilo+cola | Extraer a `core/ejecucion.py` un ejecutor **sin Tk** | P7 (testabilidad) | Sí |
| D8 | Qué más entra en `core` | **Nada más** por ahora (ni `_copiar`, ni `_destino_seguro`, ni `PAUSE_NAME`) | Evita el cajón de sastre (P20) | Sí |
| D9 | Herramientas de test | `pytest` + `pyflakes` como dependencias **solo de desarrollo** | P1, P2 | Sí |
| D10 | Fachada de `kakoli.py` | Eliminar los re-exports en la fase de retirada | P5 | Sí |
| D11 | Consola de los motores | Ruta a `python -m tasks.<tarea>.motor`, sin shims; mismas banderas | — | Sí |
| D12 | `bench.py` | Se queda en la raíz y reutiliza `tests/soporte/arboles.py` | Duplicación bench↔tests | Sí |
| D13 | Cambios pendientes en la copia de trabajo | Commitearlos o apartarlos **antes** de la Fase 0 y trabajar en una rama | P16 | **Usuario** |
| D14 | Intérprete | **venv 3.13** (instalado); código compatible con 3.11 | P16 | **RESUELTA (usuario): 3.13** |
| D15 | Verificación visual | Capturas de referencia (`img/`) comparadas a mano tras cada fase de GUI | Regresión visual | Sí |
| D16 | Ayuda por tarea | `tasks/X/ayuda.py`; `gui` compone la sección general y la de cada tarea en el orden del registro | P10 | Sí |

**Por qué D6 y no `GUI → TASKS → CORE` [I].** La interfaz específica de una tarea
(`pestana_X`) *usa* la base común de la GUI (`PestanaBase`, `tema`): las tareas dependen
de la GUI común. Como la ventana principal no puede depender de tareas concretas, solo
cuadra con inversión: la GUI consume un `Registro` sin Tk (en `core`) que `kakoli.py`
rellena con el manifiesto de `tasks`.

**Decisiones de diseño derivadas (quién hace qué) [R]:**

| Cuestión | Respuesta propuesta |
|---|---|
| Dónde se registra una tarea nueva | Una línea en `tasks/__init__.py` |
| Cómo se descubren | `kakoli.py` importa `tasks` (import estático; el empaquetador lo ve) |
| Cómo se instancian | `gui.App(registro)` crea `descriptor.fabrica_ui(area, contexto)` por tarea |
| Ciclo de vida | `App` crea, muestra/oculta, bloquea y cierra; cada pestaña posee su ejecución; los motores no tienen estado |
| Quién crea los widgets | La pestaña de la tarea, con `gui/componentes`; `App` crea marco, portada, monitor y Ayuda |
| GUI ↔ lógica | `_validar` (hilo principal) → `{entradas, Opciones}` → ejecutor de `core` → `motor.ejecutar` con callbacks → cola → bomba |
| Tarea → GUI | Solo callbacks (`log`, `progreso`, `confirmar`) y `Resultado` (`ruta_final` + `produce`) |
| Qué ve una tarea de `core` | `comun`, `recursos`, `paralelo`, registro y ejecución |
| Qué ve una tarea de `gui` | `pestana_base`, `componentes`, `tema`, `campo` (solo desde su `pestana.py`) |
| Qué nunca se ven las tareas entre sí | Nada, salvo `tasks/formatos` dentro de su par |
| Modelos | `Opciones` y dataclasses de dominio en su motor; `Resultado`/`OpcionesBase`/`DescriptorTarea`/`Categoria` en `core`; `Campo` en `gui` |
| Servicios | `recursos` y `paralelo` en `core` |
| Utilidades de archivos | Dentro de cada motor (duplicación intencionada) |
| Configuración | Defaults en `Opciones`/`PoliticaHilos`; constantes de app en `gui/constantes`; umbrales en cada motor; sin persistencia (fuera de alcance) |
| Aislar el sistema de archivos | **Sin** capa de abstracción: motores con rutas validadas; tests con `tmp_path` real |
| Errores | Validación → `ValueError`; ejecución → `Resultado`, nunca excepción hacia la GUI |
| Sin Tkinter | Todo `core`, todos los motores, `formatos`, registro, ejecutor y mapeos etiqueta→valor |
| Con integración | Pares, GUI (humo + mapeo `_validar`), consola, build de Nuitka |

---

## 8. Arquitectura objetivo propuesta

```text
kakoli/
├── kakoli.py                 # raíz de composición: main(), --version, App(tasks.REGISTRO)
├── bench.py                  # métricas; reutiliza tests/soporte
├── build_nuitka.ps1
│
├── core/                     # estable, stdlib, SIN tkinter, SIN nombres de tareas
│   ├── comun.py              # Resultado, OpcionesBase, Interrupcion, RegistroReanudable, correr_cli…
│   ├── recursos.py           # perfil, PoliticaHilos, calcular_hilos, preparar, regulador
│   ├── paralelo.py           # Plan, PlanLista, Ejecutor
│   ├── registro.py           # NUEVO: Categoria, DescriptorTarea, Registro (validación, consumidor_de)
│   └── ejecucion.py          # NUEVO: ejecutor hilo+cola+pausa sin Tk
│
├── gui/                      # estructura de la app Tkinter (no conoce tareas)
│   ├── app.py                # ventana, navegación 2 niveles, portada, monitor, bloqueo, bomba, cierre
│   ├── pestana_base.py       # esqueleto común de una pestaña de tarea (sin casos concretos)
│   ├── componentes.py        # NUEVO: MarcoDesplazable, fila_texto, caja_aviso, valor_ui…
│   ├── campo.py
│   ├── tema.py
│   ├── ayuda.py              # sección general + composición de la ayuda de cada tarea
│   └── constantes.py         # versión, marca, enlaces, ajustes de GUI, politica_desde
│
├── tasks/
│   ├── __init__.py           # MANIFIESTO: categorías + orden + una línea por tarea → REGISTRO
│   ├── formatos/             # contratos entre gemelas (sin importar ninguna tarea)
│   │   ├── formato_zip.py
│   │   ├── indice_combinacion.py
│   │   └── nombres_aplanado.py
│   ├── comprimir/            # __init__.py (DESCRIPTOR) · motor.py · pestana.py · ayuda.py
│   ├── descomprimir/
│   ├── combinar/
│   ├── descombinar/
│   ├── aplanar/
│   ├── desaplanar/
│   ├── renombrar/
│   └── eliminar/
│
└── tests/
    ├── soporte/              # arboles.py (generar/firmar/comparar), fixtures con artefactos de referencia
    ├── core/                 # sin Tk
    ├── gui/                  # requiere Tk (marcador gui)
    ├── tasks/
    │   ├── <tarea>/          # motor de cada tarea, sin Tk
    │   └── pares/            # integración bidireccional de gemelas
    └── test_fronteras.py     # guardián AST de dependencias
```

**Reglas de dependencia (verificadas por `tests/test_fronteras.py`):**

```text
            kakoli.py  (composición)
             │      │
             ▼      ▼
   tasks/<X>/pestana ──► gui (pestana_base, componentes, tema, campo)
        │                   │
        ▼                   ▼
   tasks/<X>/motor ───────► core ◄── gui
        │
        ▼
   tasks/formatos  (solo el par que lo usa)

PROHIBIDO:  core → gui | tasks | tkinter
            gui  → tasks
            tasks/X → tasks/Y   (salvo tasks/formatos del propio par)
            tasks/*/motor → tkinter | gui
            tasks/formatos → tasks/<cualquier tarea>
```

**Añadir una tarea (estado objetivo):**
1. Crear la carpeta `tasks/nueva/` (descriptor, motor, pestaña, ayuda).
2. Añadir **una línea** en `tasks/__init__.py`.
3. Crear `tests/tasks/nueva/` y, si tiene gemela, `tests/tasks/pares/test_x_y.py`.

Cero ediciones en `core/` y `gui/`.

---

## 9. Roadmap completo por fases

Convenciones para todas las fases **[R]**:
- Una fase = una rama o commit revertible.
- Mover archivos con `git mv` para conservar el historial.
- Nunca mezclar movimiento y cambio de lógica en la misma fase.
- Editar `.py` UTF-8 solo con herramientas seguras (nunca `Get-Content`/`Set-Content` de PowerShell).
- Suite por áreas al final de cada fase.

### Fase 0 — Línea base reproducible y andamiaje de tests

- **Objetivo:** partir de un estado conocido y ejecutable, sin tocar código de producción.
- **Problemas que resuelve:** P16 y la base de P1.
- **Cambios:**
  - Aplicar D13 (commit o apartar lo pendiente) y crear la rama de reestructuración.
  - Crear el venv 3.13 (D14).
  - Añadir `pytest` y `pyflakes` como dependencias de desarrollo (D9).
  - Crear `tests/` con la estructura objetivo, carpetas vacías incluidas.
  - `tests/soporte/arboles.py`: portar generar/firmar/comparar desde `bench.py` sin modificarlo.
  - `tests/soporte/modulos.py`: **tabla de indirección** de nombre lógico → módulo actual.
  - Configuración de pytest con marcadores `gui` y `lento`.
  - Añadir `.pytest_cache/` y `.venv/` a `.gitignore`.
- **Archivos afectados:** nuevos `tests/**`, `pytest.ini` (o `pyproject.toml`),
  `requirements-dev.txt`; editado `.gitignore`. **Ninguno de producción.**
- **Dependencias:** D1, D9, D13 y D14 decididas.
- **Riesgos:** bajos; divergencia temporal `bench.py` ↔ `tests/soporte` (se resuelve en la Fase 13).
- **Tests:**
  - `test_importa_todo`: importar cada módulo con `python -B`.
  - Ejecutar `pyflakes` y guardar su salida como línea base; debe señalar `threading` sin
    definir en `pestana_descomprimir`.
- **Criterio de finalización:** `pytest tests -q` corre en 3.13 con al menos el test de
  import en verde; el árbol git no muestra más cambios que los nuevos archivos de test.
- **Resultado arquitectónico:** sin cambios; existe el esqueleto de tests alineado con la
  arquitectura objetivo.
- **ESTADO: HECHA** (2026-09-15). Base commiteada en `main` (icono + portada scroll + spec
  onefile + capturas a `img/` + este documento). venv `.venv/` con **Python 3.13.10**;
  `requirements-dev.txt` (pytest, pyflakes). `pytest.ini` (testpaths=`tests`, marcadores
  `gui`/`lento`), `conftest.py` (raíz del repo en `sys.path`). `tests/` con la estructura
  objetivo (`core/`, `gui/`, `tasks/`, `tasks/pares/`, `soporte/`), cada área con su README.
  `tests/soporte/modulos.py` (indirección nombre lógico → módulo actual, 33 entradas),
  `tests/soporte/arboles.py` (crear/firmar/comparar árboles, deterministas).
  `tests/test_importa_todo.py` (importa los 33 módulos + contrato `ejecutar` de los 8
  motores + humo de `arboles`) y `tests/test_pyflakes_baseline.py` (trinquete de nombres
  indefinidos; documenta el bug **P2** `threading` en `pestana_descomprimir`, a corregir en
  la Fase 3). `.pytest_cache/` ignorado. **Suite: 36 passed** en 3.13; `kakoli.py --version`
  = «kakoli 0.9»; sin tocar código de producción.

### Fase 1 — Caracterización de `core`, motores y pares (sin Tk)

- **Objetivo:** fijar el comportamiento observable de toda la lógica antes de moverla.
- **Problemas que resuelve:** P1 (parte sin GUI).
- **Cambios:** solo tests nuevos.
  - **`tests/core/`:** tabla de `calcular_hilos`; `techo_hilos`, `objetivo_activos`;
    `PlanLista`/`Ejecutor` (cada unidad una vez con 1/4/8 hilos, pausa sin pérdidas,
    propagación del primer error); `RegistroReanudable`; `humano`, `duracion`, códigos de
    salida de `correr_cli`.
  - **`tests/tasks/<tarea>/`**, por motor vía `ejecutar`: caso normal y errores de
    `rutas_validadas`; pausa tras k + reanudación; equivalencia 1 vs 4 hilos (con
    `PoliticaHilos(prioridad_baja=False)`); seguridad (`..` en zip, nombres aplanados con
    `..`, índice manipulado).
  - **Eliminar:** simular no borra; rechaza raíz/carpeta personal/profundidad ≤2;
    `confirmar`→False → `cancelado`.
  - **Renombrar:** extensiones compuestas, `numerar`/`omitir`, simular.
  - **`tests/tasks/pares/`:** Comprimir→Descomprimir (normal, compacto, paralelo,
    reanudación; nombres+bytes+carpetas vacías; mtime ±2 s); Combinar(renombrar+índice)→
    Descombinar; Aplanar(ruta)→Desaplanar (identidad). Casos NO reversibles como tests
    explícitos (`final`, `reemplazar`, `crear_indice=False`, separador en el nombre).
  - **Artefactos de referencia versionados**, generados con la versión actual.
- **Archivos afectados:** `tests/core/**`, `tests/tasks/**`, `tests/soporte/fixtures/**`.
- **Dependencias:** Fase 0.
- **Riesgos:** tests frágiles por textos de log (comparar solo `Resultado` y disco), mtime, hilos.
- **Criterio de finalización:** todo verde con el marcador `lento` separado; cada
  `ejecutar`/`info_reanudable` invocado al menos una vez; `tests/core` y `tests/tasks`
  ejecutables por separado.
- **Resultado arquitectónico:** contrato de motores y relaciones bidireccionales congelados por tests.
- **ESTADO: HECHA** (2026-09-16). **114 tests nuevos** (suite total **150 passed** en 3.13,
  1 marcado `lento`). `tests/soporte/util.py` (política determinista `prioridad_baja=False`,
  `throttling=False`; `nolog`). **core:** `test_comun.py` (humano/duracion, Resultado,
  RegistroReanudable —anota/inspeccionar/completar/reiniciar—, códigos de `correr_cli` con
  fixture que preserva SIGINT/SIGTERM), `test_recursos.py` (tabla de `calcular_hilos`
  2→1·4→3·8→7·HDD→3·mismo disco→1·swap→1·batería→2·carga externa; `techo_hilos`;
  `objetivo_activos`), `test_paralelo.py` (`PlanLista`, `Ejecutor` 1/4/8 hilos entrega
  única, pausa desde inicio, propagación del primer error, `pedir_parada`). **tasks:**
  por motor `renombrar` (nombre puro + conflictos), `eliminar` (borra/simula/confirma +
  guardas de `rutas_validadas`), `comprimir` (rutas + explorar + marca), `descomprimir`
  (rutas + `es_contenedor` + anti zip-slip `_destino_seguro`), `combinar` (rutas +
  índice); `test_formatos.py` (nombres_aplanado inverso + anti-traversal, marca ZIP,
  índice); `test_info_reanudable.py` (los 3 motores que lo exponen). **pares:** los 3
  round-trips bidireccionales por firma completa (nombres+bytes+carpetas vacías):
  Comprimir↔Descomprimir (normal, compacto, paralelo forzado [lento], reanudación por
  max_dirs), Combinar↔Descombinar (renombrar+índice, y el caso NO reversible sin índice),
  Aplanar↔Desaplanar (modo ruta; casos NO reversibles: modo final y separador en el
  nombre). Los 8 `ejecutar` y los 3 `info_reanudable` se invocan al menos una vez.
  **Decisión de alcance:** los artefactos de formato se generan y leen *inline* en los
  tests (round-trips + `test_formatos`) en lugar de versionar binarios de referencia; un
  artefacto congelado se puede añadir en la Fase 12 si se toca el formato ZIP.

### Fase 2 — Caracterización de la GUI y guardián de fronteras (trinquete)

- **Objetivo:** congelar el comportamiento de la GUI y medir las violaciones de dependencia.
- **Problemas que resuelve:** P1 (GUI), P2 (documentado) y la medición de P5, P6, P8.
- **Cambios:** solo tests.
  - **`tests/gui/`:** fixture `app` que se salta si hay `TclError`, `withdraw()`,
    `messagebox` con monkeypatch. Tests: arranque (8 tareas, 5 categorías, orden actual);
    navegación; bloqueo/desbloqueo; handoff de los 3 pares; mapeo `_tag_log`; **por
    pestaña:** fijar variables → `_validar()` → comparar con `Opciones` esperadas y con
    los `ValueError`; botón de Eliminar deshabilitado sin confirmación; destino automático;
    flujo completo con motor real pequeño bombeando `procesar_cola` a mano.
  - **P2** como `xfail(strict=True)`.
  - **`tests/test_fronteras.py`:** reglas AST del §8 + **lista de excepciones** con las
    violaciones actuales exactas. Solo puede encoger. La mutación de `menu.py` con test propio.
  - Lista de comprobación visual contra `img/`.
- **Archivos afectados:** `tests/gui/**`, `tests/test_fronteras.py`.
- **Dependencias:** Fase 0 (independiente de la Fase 1).
- **Riesgos:** Tk headless; orden de creación de widgets.
- **Criterio de finalización:** `pytest tests/gui` verde en Windows; la lista de
  excepciones coincide exactamente con las violaciones reales.
- **Resultado arquitectónico:** fronteras medidas y protegidas contra retrocesos.
- **ESTADO: HECHA** (2026-09-16). **38 tests nuevos** (34 GUI + 4 guardián). **GUI**
  (`tests/gui/`, marcador `gui`): `conftest.py` con fixture `app` de **un solo `App` por
  sesión** y reseteo completo de estado antes de cada test (navegación al menú + todas las
  variables Tk a su valor por defecto) — decisión tomada porque crear/destruir muchos roots
  `Tk()` en el mismo proceso provoca una **carrera intermitente de Tcl en Windows**
  (`tcl_findLibrary`/`winTheme.tcl`, ~2 skips de 34 por pasada); con un único root la suite
  es estable y **10× más rápida** (~3 s vs ~30 s). `messagebox` neutralizado. Tests:
  `test_arranque` (8 tareas·5 categorías·orden·`_tag_log`), `test_navegacion` (entrar/mostrar/
  ir_menu/estado_barra + bloqueo deshabilita ← y hermanas), `test_handoff` (cableado
  `produce_hacia` de los 3 pares + despacho de `sugerir_entrada`), `test_validar` (mapeo por
  pestaña `_validar()`→`Opciones` de las 8 + sus `ValueError`), `test_flujo` (flujo completo
  Renombrar vista-previa: `_iniciar`→hilo→cola→`_fin` bombeado a mano; y validación que no
  arranca), `test_p2_descomprimir` (**xfail estricto** que reproduce el `NameError` de P2, se
  invertirá en la Fase 3). **Guardián** (`tests/test_fronteras.py`): análisis AST por ROL
  (no por carpeta, así las reglas no cambian cuando la Fase 4 mueva archivos); BASELINE con
  las **4 violaciones actuales** exactas (`app`→3 pestañas · `pestana_desaplanar`→
  `motor_aplanar`), que solo puede encoger; `test_core_no_importa_tkinter` (verde: comun/
  recursos/paralelo no importan Tk aunque `tema` viva en `nucleo/`) y
  `test_menu_cablea_produce_hacia` (documenta la mutación de clases al importar `menu`).
  **Suite total: 187 passed, 1 xfailed** en 3.13 (~10 s). Estabilidad de la GUI
  verificada en 8 pasadas seguidas sin skips.

### Fase 3 — Correcciones previas sin cambio de estructura

- **Objetivo:** eliminar fallos y residuos para que los movimientos sean mecánicos.
- **Problemas que resuelve:** P2, P8 y P19; código muerto de P7.
- **Cambios:**
  - Añadir `import threading` en `clases/pestana_descomprimir.py`.
  - `pestana_desaplanar` importa `separador_ok` desde `motores.nombres_aplanado`.
  - Quitar `usa_hilos`/`usa_compacto` (sin lectores).
  - Borrar comentarios residuales de la extracción.
  - Corregir docstrings desfasados. **No** tocar P17.
- **Archivos afectados:** `clases/pestana_descomprimir.py`, `clases/pestana_desaplanar.py`,
  `clases/pestana_base.py`, `clases/pestana_{comprimir,descomprimir,eliminar}.py`,
  docstrings de `nucleo/*.py` y `motores/motor_comprimir.py`.
- **Dependencias:** Fases 1 y 2.
- **Criterio de finalización:** `pyflakes` sin nombres indefinidos; el `xfail` de P2 pasa a
  verde; la lista de excepciones de fronteras pierde `pestana_desaplanar → motor_aplanar`;
  todo en verde.
- **Resultado arquitectónico:** 0 dependencias entre tareas en el código de producción.
- **ESTADO: HECHA** (2026-09-16). Correcciones sin mover archivos:
  - **P2 corregido:** `import threading` en `clases/pestana_descomprimir.py` (la
    confirmación durante Descomprimir ya no lanza `NameError`).
  - **4.ª violación de fronteras eliminada:** `pestana_desaplanar` importa `separador_ok`
    de `motores.nombres_aplanado` (formato compartido), no de `motor_aplanar` (gemelo).
  - **Código muerto:** quitados `usa_hilos`/`usa_compacto` de `PestanaBase` y de las
    pestañas (nadie los leía) y los comentarios residuales de la extracción
    («Pestaña N: …», «Categoría …»).
  - **Docstrings al día:** «los tres motores»→«los motores/todas las tareas»;
    `python3.11 X.py`→`python -m paquete.modulo`; `tema` «vive en kakoli.py»→«en clases/»;
    el «PUNTO DE EXTENSIÓN … todavía inactivo» de `motor_comprimir` pasó a «MODO COMPACTO,
    ya activo» (verificado: `crear_agrupado` está implementado y el round-trip compacto pasa).
  - **Nombres indefinidos a CERO** (superando lo listado, para dejar el trinquete de pyflakes
    en base vacía): los falsos positivos de anotación (`App` en `pestana_base`, `Resultado`
    en comprimir/descomprimir/eliminar) se resolvieron con imports bajo `TYPE_CHECKING` (sin
    ciclos ni imports en runtime).
  - **Tests-trinquete avanzados:** `test_pyflakes_baseline` (base vacía; `test_p2_corregido`),
    `test_fronteras` (BASELINE de 4→3), y el xfail de P2 sustituido por una regresión positiva
    (`test_preguntar_no_lanza_nameerror` + `test_modulo_descomprimir_tiene_threading`).
  - **Verificado:** `pyflakes` sin nombres indefinidos; `import kakoli` y arranque real de
    `App` (8 tareas) OK; `--version` = «kakoli 0.9». **Suite: 189 passed, 0 xfailed** en 3.13.

### Fase 4 — Paquetes `core/` y `gui/` (movimiento mecánico)

- **Objetivo:** separar el núcleo sin Tk de la GUI global, sin cambiar lógica.
- **Problemas que resuelve:** P6 y parte de P3.
- **Cambios:** `nucleo/{comun,recursos,paralelo}.py` → `core/`; `nucleo/tema.py` →
  `gui/tema.py`; `clases/{app,pestana_base,campo,constantes,ayuda_contenido}.py` → `gui/`.
  Se quedan en `clases/` las 8 `pestana_*`, `menu.py` y `categoria.py`; `motores/` no
  cambia. Actualizar imports y `tests/soporte/modulos.py`. Verificar `_raiz_datos()` de `tema`.
- **Archivos afectados:** los movidos + imports en `motores/*.py`, `clases/*.py`,
  `kakoli.py`, `bench.py`, `tests/soporte/modulos.py`.
- **Dependencias:** Fase 3.
- **Riesgos:** rutas de fuentes/iconos, empaquetado, imports olvidados.
- **Criterio de finalización:** no existe `nucleo/`; la regla «core no importa tkinter, gui
  ni tasks» pasa a estricta; suite completa + `import kakoli` + `python -m core.recursos .`
  + build de Nuitka como humo; fuentes e icono cargan.
- **Resultado arquitectónico:** `core` sin Tk; GUI global en su paquete.
- **ESTADO: HECHA** (2026-09-16). Movimiento **mecánico** con `git mv` (historial
  conservado): `nucleo/{comun,recursos,paralelo}.py`→`core/`; `nucleo/tema.py`→`gui/`;
  `clases/{app,pestana_base,campo,constantes,ayuda_contenido}.py`→`gui/`. En `clases/`
  quedan las 8 `pestana_*`, `menu.py` y `categoria.py`; `motores/` sin cambios.
  `nucleo/` eliminado; nuevos `core/__init__.py` y `gui/__init__.py`. Imports reescritos
  en 22 archivos con un script UTF-8 explícito (nunca PowerShell Get/Set-Content):
  `from nucleo…`→`from core…`/`from gui…`; `from clases.{app,pestana_base,campo,
  constantes,ayuda_contenido}`→`from gui.…`. `tema._raiz_datos()` sigue subiendo un nivel
  (`gui/`→raíz, misma profundidad). Docstrings/consola al día (`python -m core.recursos`,
  `python -m gui.tema`, docstring de `kakoli.py` con el árbol core/gui). Tests: `modulos.py`
  repunta la indirección (una línea por módulo movido), `conftest` de GUI importa `gui.app`,
  el guardián actualiza sus ROL a los nuevos nombres (BASELINE ahora `gui.app`→3 pestañas),
  pyflakes analiza `core gui motores clases`. **Verificado:** pyflakes sin nombres
  indefinidos; `import kakoli`, arranque de `App` y `python -m core.recursos .` OK;
  **build de Nuitka correcto** (empaquetado completado, fuentes + `kakoli.ico` incluidos,
  ningún paquete propio ausente). El exe recién construido **no
  se pudo EJECUTAR** por una política de Windows App Control que bloquea binarios sin firmar
  (limitación del entorno, ajena al build). **Suite: 189 passed** en 3.13. Regla «core no
  importa tkinter/gui/tareas» ahora ESTRICTA (0 excepciones en `test_core_no_importa_tkinter`).

### Fase 5 — Contrato de tarea y registro en `core`; `App` desacoplada

- **Objetivo:** invertir la dependencia entre la GUI global y las tareas.
- **Problemas que resuelve:** P4, P5, P10 (preparación) y parte de P13.
- **Cambios:** `core/registro.py` (`Categoria`, `DescriptorTarea`, `Registro` con
  validación); eliminar `clases/categoria.py`; `clases/menu.py` construye `REGISTRO` sin
  mutar clases y con tipos de artefacto (D5); `gui/app.py` recibe `App(registro)`, sin
  imports de pestañas concretas ni alias `tab_*`, `sugerir_entrada(ruta, artefacto)`,
  `mostrar(id_tarea)`; ayuda indexada por id; `kakoli.py` → `App(REGISTRO)`.
- **Archivos afectados:** `core/registro.py` (nuevo), `gui/app.py`, `gui/pestana_base.py`
  (`produce`/`consume`), `gui/ayuda_contenido.py`, `clases/menu.py`, `clases/pestana_*.py`
  (6 con handoff/orden), `kakoli.py`.
- **Dependencias:** Fase 4.
- **Riesgos:** semántica del handoff, orden de categorías, API `mostrar`.
- **Criterio de finalización:** «gui no importa tasks/pestañas/motores» estricta; ningún
  atributo de clase mutado al importar; **test de extensibilidad** (App arranca con 1 tarea
  ficticia); todo verde.
- **Resultado arquitectónico:** la ventana principal ya no conoce tareas concretas.
- **ESTADO: HECHA** (2026-09-16). Se invirtió la dependencia GUI→tareas:
  - **`core/registro.py`** (nuevo): `DescriptorTarea` (id, nombre, `clase` opaca=fábrica de
    UI, `produce`/`consume`), `Categoria` (nombre, descripción, tareas) y `Registro` con
    **validación** (ids y clases únicos, categorías no vacías) + búsquedas
    (`descriptores`, `descriptor_de`, `consumidor_de`). Sin Tkinter.
  - **Handoff por tipo de ARTEFACTO** (D5): las pestañas declaran `produce`/`consume` con
    tipos específicos (`zip_anidado`, `carpeta_combinada`, `carpeta_aplanada`); el Registro
    los casa. Eliminado `produce_hacia` y la **mutación de clases al importar** `menu`.
  - **`clases/menu.py`** reescrito: construye `REGISTRO` (un `DescriptorTarea` por pestaña),
    sin mutar nada. `clases/categoria.py` eliminado (`Categoria` vive en `core.registro`).
  - **`gui/app.py`** desacoplada: `App(registro)`, sin imports de pestañas concretas ni
    alias `tab_*`; navegación por descriptores; `sugerir_entrada(ruta, artefacto)` usa
    `registro.consumidor_de`. `kakoli.py` → `App(REGISTRO)`.
  - **Tests:** `tests/core/test_registro.py` (validación + búsquedas, sin Tk),
    `tests/gui/test_extensibilidad.py` (`test_app_es_registro_driven`: las pestañas de App
    son exactamente las clases del registro en orden — SIEMPRE corre; y un arranque con
    tareas ficticias que se salta cuando Tk no admite un 2.º root vivo). Actualizados
    `test_arranque`/`test_navegacion`/`test_handoff` al nuevo modelo; el guardián pasa a
    **BASELINE VACÍA** (regla «gui no importa tareas» estricta, 0 excepciones) y sustituye
    el test de mutación por `test_menu_construye_registro_sin_mutar_clases`; `modulos.py`
    añade `core.registro`.
  - **Fuera de alcance (diferido):** el reindexado de la Ayuda por id de tarea se hará en la
    migración por tareas (Fases 8-12), cuando la ayuda de cada tarea pase a `tasks/<t>/ayuda.py`;
    en la Fase 5 `gui/ayuda_contenido` sigue centralizado.
  - **Verificado:** pyflakes limpio; `import kakoli`, arranque de `App(REGISTRO)` (8 tareas);
    guardián estricto; GUI estable en varias pasadas. **Suite: 201 passed, 1 skipped** (el
    arranque ficticio, por la limitación de Tk de dos roots) en 3.13.

### Fase 6 — GUI común: `gui/componentes.py` y `PestanaBase` sin fugas

- **Objetivo:** una API común de GUI estable y genérica.
- **Problemas que resuelve:** P7 (fugas) y P11.
- **Cambios:** `gui/componentes.py` (`MarcoDesplazable` adoptado por base, portada y Ayuda;
  `fila_texto` con registro automático en `_bloqueables`; `valor_ui`); `PestanaBase`:
  `v_compacto`→Comprimir, filtro ZIP → `Campo.filtros`, título de lista → `Campo.titulo_dialogo`,
  `reiniciar` solo si existe el campo. Las 4 pestañas con fila de texto usan `fila_texto`.
- **Archivos afectados:** `gui/componentes.py` (nuevo), `gui/pestana_base.py`, `gui/app.py`,
  `gui/campo.py`, `gui/constantes.py`, `clases/pestana_{comprimir,descomprimir,combinar,aplanar,desaplanar,renombrar}.py`.
- **Dependencias:** Fase 4; en serie tras la Fase 5 (comparten `gui/app.py`).
- **Riesgos:** `bind_all` de la rueda, controles sin bloquear, regresión visual.
- **Criterio de finalización:** `gui/pestana_base.py` sin «zip»/«combinar»/«compact»; el
  patrón Canvas+scroll una sola vez; todo verde.
- **Resultado arquitectónico:** GUI común genérica y reutilizable.
- **ESTADO: HECHA** (2026-09-16). **`gui/componentes.py`** (nuevo):
  - **`MarcoDesplazable`** — el patrón Canvas + barra auto-oculta + rueda del ratón que
    estaba **triplicado** (opciones de la pestaña, portada y Ayuda) ahora es una sola pieza
    (params `padding`/`margen`/`auto_ocultar`/`on_reconfigure`). Adoptado en los 3 sitios;
    `tk.Canvas` aparece **una sola vez** en toda la GUI.
  - **`fila_texto`** — la fila «etiqueta + Entry» que estaba repetida 4 veces; `PestanaBase._entry`
    la usa y las 4 pestañas (Aplanar/Desaplanar sep, Combinar código, Renombrar) la adoptan
    (se eliminó el `_entry` propio de Renombrar). Ningún `ttk.Entry(fila…)` manual en `clases/`.
  - **`PestanaBase` sin fugas de tareas concretas:** `v_compacto`→`PestanaComprimir`;
    el filtro ZIP hardcodeado → `Campo.filtros` (+ `filtros_origen` de clase, lo fija
    Descomprimir); el título del diálogo de lista → `Campo.titulo_dialogo` (lo fija Combinar);
    `reiniciar` solo si `Opciones` tiene el campo (`hasattr`). `pestana_base` ya no menciona
    «zip/combinar/compact» salvo en comentarios ilustrativos del mecanismo genérico.
  - **Decisión de alcance:** `_valor_ui` NO se movió a componentes (ya vive en `gui/constantes`,
    es un helper de GUI; relocarlo era churn sin beneficio arquitectónico).
  - **Tests:** `tests/gui/test_componentes.py`; la suite de GUI existente sigue verde
    (iso-comportamiento). Verificado a mano: portada + Ayuda + área de opciones se construyen
    sin fallo. **Suite: 205 passed** (GUI estable en varias pasadas) en 3.13.

### Fase 7 — Ejecución sin Tk en `core` e interfaz de contexto explícita

- **Objetivo:** ciclo de ejecución probable sin Tkinter; pestañas dependientes de un
  contrato, no de `App`.
- **Problemas que resuelve:** P7 (responsabilidades) y P13.
- **Cambios:** `core/ejecucion.py` (hilo, cola de eventos, pausa, `ocupada`, `pedir_cierre`,
  excepción → `Resultado("error")`); `PestanaBase` delega en el ejecutor; `ContextoApp`
  (Protocol en `gui`) con `opciones_comunes()`, `escribir_lote`, `bloquear`, `desbloquear`,
  `sugerir_entrada`, `comprobar_cierre`; las pestañas usan `self.opciones_comunes()`;
  documentar como constantes los prefijos de log (P12), sin cambiar el contrato.
- **Archivos afectados:** `core/ejecucion.py` (nuevo), `gui/pestana_base.py`, `gui/app.py`,
  las 8 `clases/pestana_*.py`.
- **Dependencias:** Fase 4 (en serie tras la Fase 6).
- **Riesgos:** regresiones de hilos; lectura de variables Tk fuera del hilo principal.
- **Criterio de finalización:** 0 apariciones de `self.app.v_` en las pestañas; ejecutor
  cubierto sin Tk; todo verde.
- **Resultado arquitectónico:** API de tareas cerrada: `core` (contrato, registro,
  ejecución) + `gui` (base, componentes, tema, campo, contexto).
- **ESTADO: HECHA** (2026-09-16). Ejecución testeable sin Tk + contexto explícito:
  - **`core/ejecucion.py`** (nuevo): `Ejecucion` — hilo daemon + cola de eventos
    (`log`/`prog`/`fin`), `iniciar(trabajo)`, `recoger()` (drena sin bloquear),
    `pedir_pausa()`, `ocupada()`; excepción del trabajo → `Resultado("error")` (nunca
    sube). SIN Tkinter. `PestanaBase` delega: posee `self._ejec`; `procesar_cola` solo
    drena con `recoger()` y actualiza widgets; `_iniciar` lanza el trabajo con
    `self._ejec.iniciar(...)`. Se conserva `pes.hilo` (property) por compat de tests.
  - **`gui/contexto.py`** (nuevo): `ContextoApp` (Protocol) documenta lo que la ventana
    ofrece a una pestaña: `opciones_comunes`, `escribir_lote`, `bloquear`, `desbloquear`,
    `sugerir_entrada`, `comprobar_cierre`. `PestanaBase.app` se anota como `ContextoApp`.
  - **Fin de la fuga `self.app.v_*`** (P13): `App.opciones_comunes() -> (detallado,
    PoliticaHilos)`; `PestanaBase._detallado()`/`_politica()` lo usan; las 8 pestañas
    cambian `self.app.v_detallado.get()` → `self._detallado()`. **0 apariciones de
    `self.app.v_` en el código.**
  - **Prefijos de log documentados** (P12): `App._tag_log` usa constantes nombradas
    (`PREFIJO_AVISO`/`PREFIJOS_SISTEMA`/`PREFIJOS_EXITO`); el contrato textual motor→consola
    no cambia.
  - **Tests:** `tests/core/test_ejecucion.py` (6, SIN Tk: arranque, excepción→error, log/
    progreso, solo-último-progreso, pausa cooperativa, `ocupada`); `modulos.py` y el guardián
    añaden `core.ejecucion`/`gui.componentes`/`gui.contexto`. **Suite: 214 passed** en 3.13;
    pyflakes limpio; GUI estable.

### Fase 8 — Piloto: `tasks/renombrar/` y manifiesto `tasks/__init__.py`

- **Objetivo:** validar el patrón de migración con el menor impacto.
- **Problemas que resuelve:** P3 (primera tarea), P9 y P10 (parcial).
- **Por qué Renombrar:** tarea sola, sin gemela, formato, handoff ni reanudación; pequeña,
  pero ejercita todo el patrón.
- **Cambios:** `motores/motor_renombrar.py` → `tasks/renombrar/motor.py`;
  `clases/pestana_renombrar.py` → `tasks/renombrar/pestana.py` (con `_CONFLICTOS_RENOM`);
  ayuda → `tasks/renombrar/ayuda.py`; `tasks/renombrar/__init__.py` con `DESCRIPTOR`; se
  crea `tasks/__init__.py` (manifiesto) que sustituye a `clases/menu.py` (durante la
  transición declara las no migradas desde sus módulos antiguos); consola
  `python -m tasks.renombrar.motor`.
- **Archivos afectados:** movidos/creados, `clases/menu.py` (se elimina), `gui/constantes.py`,
  `gui/ayuda_contenido.py`, `kakoli.py`, `tests/soporte/modulos.py`, `README.md`.
- **Dependencias:** Fases 5, 6 y 7.
- **Riesgos:** estado mixto temporal; empaquetado.
- **Criterio de finalización:** no quedan restos de Renombrar en `motores/`, `clases/`,
  `gui/constantes`, `gui/ayuda_contenido`; pestaña idéntica; humo de consola `--help`; todo verde.
- **Resultado arquitectónico:** primera tarea vertical; el manifiesto es el único registro.
- **ESTADO: HECHA** (2026-09-16). Piloto de migración vertical con Renombrar (la más
  simple: sin gemela, formato, handoff ni reanudación):
  - **`tasks/renombrar/`** (paquete): `motor.py` (git mv de `motores/motor_renombrar.py`;
    CLI `python -m tasks.renombrar.motor`), `pestana.py` (git mv; su mapeo `_CONFLICTOS_RENOM`
    ahora vive aquí, no en `gui/constantes`), `ayuda.py` (su sección de Ayuda, extraída de
    `gui/ayuda_contenido`) e `__init__.py` con el `DESCRIPTOR`.
  - **`tasks/__init__.py`** (manifiesto): construye el `REGISTRO`; **sustituye a
    `clases/menu.py`** (eliminado). Renombrar entra por `tasks.renombrar.DESCRIPTOR`; las 7
    tareas no migradas se declaran con un descriptor mínimo desde `clases/pestana_*` (su
    Ayuda sigue en `gui/ayuda_contenido.AYUDA_TAREAS`, un dict por id).
  - **Ayuda componible** (resuelve el diferido de la Fase 5): `DescriptorTarea` gana
    `ayuda`; `gui/ayuda_contenido` se parte en `AYUDA_INTRO` + `AYUDA_TAREAS[id]` (no
    migradas) + `AYUDA_CIERRE`; `App._secciones_ayuda()` compone intro + (por tarea del
    registro: `descriptor.ayuda` o `AYUDA_TAREAS[id]`) + cierre. Cada tarea que migre saca
    su sección de `AYUDA_TAREAS` a su carpeta.
  - `kakoli.py`/`conftest` importan `REGISTRO` de `tasks`. **Guardián reescrito** (clasifica
    por rol con reglas, soporta el esquema antiguo y `tasks/<t>/…`; BASELINE sigue VACÍA).
    `modulos.py` repunta `motor/pestana.renombrar` a `tasks.renombrar.*`.
  - **Tests:** `tests/tasks/renombrar/test_cli.py` (humo `--help` + simular por subprocess);
    los tests del motor de Renombrar siguieron el movimiento **sin cambios** (indirección
    `modulos.py`). **Suite: 217 passed, 1 skipped** en 3.13; pyflakes limpio; CLI y arranque OK.
  - **Nota:** `python -m tasks.<t>.motor` emite un `RuntimeWarning` benigno de `runpy` (el
    paquete importa el motor antes de ejecutarlo como `__main__`); no afecta al resultado.

### Fase 9 — `tasks/eliminar/`

- **Objetivo:** migrar la tarea destructiva y validar ganchos sobrescritos.
- **Problemas que resuelve:** P3.
- **Cambios:** mismo patrón; ayuda a su carpeta.
- **Archivos afectados:** `motores/motor_eliminar.py`, `clases/pestana_eliminar.py`,
  `gui/ayuda_contenido.py`, `tasks/__init__.py`, `tests/soporte/modulos.py`.
- **Dependencias:** Fase 8.
- **Riesgos:** medidas de seguridad del borrado.
- **Criterio de finalización:** como la Fase 8; GUI: botón deshabilitado sin confirmación.
- **Resultado arquitectónico:** 2 tareas verticales.
- **ESTADO: HECHA** (2026-09-16). `tasks/eliminar/` (motor, pestana con botón de peligro +
  confirmación reforzada + ganchos `_fin`/`_al_terminar`, ayuda, descriptor). Manifiesto:
  Eliminar entra por su `DESCRIPTOR`; su sección sale de `AYUDA_TAREAS`. `kakoli.py`/`modulos`
  repuntados; consola `python -m tasks.eliminar.motor`. **Ajuste de tooling:** al aparecer un
  segundo `test_cli.py` (colisión de nombre de archivo con el de Renombrar) se activó
  `--import-mode=importlib` en `pytest.ini` — cada `tasks/<t>/` podrá tener su `test_cli.py`
  sin `__init__.py`. Tests: `tests/tasks/eliminar/test_cli.py` (humo + simular); los del motor
  siguieron el movimiento sin cambios. **Suite: 221 passed, 1 skipped** en 3.13; pyflakes limpio.

### Fase 10 — Par Aplanado + `tasks/formatos/nombres_aplanado.py`

- **Objetivo:** migrar el primer par y crear `tasks/formatos/`.
- **Problemas que resuelve:** P3, P9, P15.
- **Cambios:** `aplanar/` y `desaplanar/` en sus carpetas; `nombres_aplanado.py` →
  `tasks/formatos/`; mapeos (`_MODOS_NOMBRE`, `_POLITICAS_APLANAR`, `_POLITICAS_DESAPLANAR`
  y su copia de `_CRITERIOS`) a cada pestaña; descriptores con `produce/consume =
  "carpeta_aplanada"`; opcional: motor expone `destino_por_defecto()`.
- **Archivos afectados:** `motores/motor_{aplanar,desaplanar}.py`, `motores/nombres_aplanado.py`,
  `clases/pestana_{aplanar,desaplanar}.py`, `gui/constantes.py`, `gui/ayuda_contenido.py`,
  `tasks/__init__.py`, `tests/soporte/modulos.py`.
- **Dependencias:** Fase 8.
- **Riesgos:** compatibilidad de `.kakoli_aplanado.json`/`.kakoli_desaplanado.json`;
  anti-traversal léxico.
- **Criterio de finalización:** test del par en verde y aislado; `gui/constantes` sin
  mapeos de aplanado; guardián (formatos no importa tareas; pestañas del par no se importan
  entre sí); todo verde.
- **Resultado arquitectónico:** primer par independiente unido solo por su formato.
- **ESTADO: HECHA** (2026-09-16). Primer par migrado + creación de `tasks/formatos/`:
  - `tasks/aplanar/` y `tasks/desaplanar/` (motor, pestana, ayuda, descriptor); Aplanar
    `produce="carpeta_aplanada"`, Desaplanar `consume="carpeta_aplanada"`.
  - `tasks/formatos/nombres_aplanado.py` (git mv de `motores/`); ambos motores y la pestaña
    de Desaplanar importan de ahí (`tasks.formatos.nombres_aplanado`), **no del gemelo**.
  - Mapeos propios en cada pestaña (`_MODOS_NOMBRE`/`_POLITICAS_APLANAR`/`_CRITERIOS` en
    Aplanar; `_POLITICAS_DESAPLANAR` en Desaplanar) — duplicación intencionada; salen de
    `gui/constantes` (que conserva `_POLITICAS`/`_CRITERIOS`/`_CODIGOS` para Combinar).
  - Manifiesto usa `APLANAR`/`DESAPLANAR`; sus secciones salen de `AYUDA_TAREAS`.
    `kakoli.py`/`modulos` repuntados; consola `python -m tasks.{aplanar,desaplanar}.motor`.
  - **Guardián:** `tasks.formatos.*` clasifica como rol *formato* (regla `tasks.formatos`);
    `motores.nombres_aplanado` sale de FORMATOS. BASELINE sigue VACÍA.
  - Tests: CLI smoke de ambas; el **test del par Aplanar↔Desaplanar** y `test_formatos`
    siguieron el movimiento **sin cambios** (indirección). **Suite: 228 passed** en 3.13.

### Fase 11 — Par Combinación + `tasks/formatos/indice_combinacion.py`

- **Objetivo:** migrar el par con campo `lista` e índice JSON.
- **Problemas que resuelve:** P3, P9.
- **Cambios:** patrón de la Fase 10; `_POLITICAS`, `_CRITERIOS`, `_CODIGOS` →
  `tasks/combinar/pestana.py`; `produce/consume = "carpeta_combinada"`.
- **Archivos afectados:** `motores/motor_{combinar,descombinar}.py`, `motores/indice_combinacion.py`,
  `clases/pestana_{combinar,descombinar}.py`, `gui/constantes.py`, `gui/ayuda_contenido.py`,
  `tasks/__init__.py`, `tests/soporte/modulos.py`.
- **Dependencias:** Fase 8.
- **Riesgos:** compatibilidad de `.kakoli_combinacion.json`; campo `lista`.
- **Criterio de finalización:** como la Fase 10.
- **Resultado arquitectónico:** 6 tareas verticales.
- **ESTADO: HECHA** (2026-09-16). Segundo par migrado:
  - `tasks/combinar/` y `tasks/descombinar/` (motor, pestana, ayuda, descriptor). Combinar
    `produce="carpeta_combinada"`, Descombinar lo `consume`.
  - `tasks/formatos/indice_combinacion.py` (git mv); ambos motores lo importan de ahí,
    no del gemelo. El campo `lista` (Combinar) y el índice JSON funcionan igual.
  - Mapeos `_POLITICAS`/`_CRITERIOS`/`_CODIGOS` a la pestaña de Combinar (duplicación
    intencionada); `gui/constantes` queda **sin ningún mapeo** (solo `_valor_ui` genérico +
    constantes de app), porque Comprimir/Descomprimir no usan desplegables etiqueta→valor.
  - Manifiesto usa `COMBINAR`/`DESCOMBINAR`; sus secciones salen de `AYUDA_TAREAS`.
    `kakoli.py`/`modulos` repuntados; consola `python -m tasks.{combinar,descombinar}.motor`.
  - **Guardián:** `motores.indice_combinacion` sale de FORMATOS (lo cubre la regla
    `tasks.formatos`); BASELINE sigue VACÍA. Tests: CLI smoke de ambas; el **test del par
    Combinar↔Descombinar** siguió el movimiento sin cambios. **Suite: 233 passed, 1 skipped**
    en 3.13. En `clases/`+`motores/` solo queda Compresión.

### Fase 12 — Par Compresión + `tasks/formatos/formato_zip.py`

- **Objetivo:** migrar el par más grande y crítico.
- **Problemas que resuelve:** P3, P15.
- **Por qué último:** 1.070 + 469 líneas, confirmación desde el hilo, `info_reanudable` con
  formato propio, presets, modo compacto; lo que más cubre `bench.py`.
- **Cambios:** patrón de la Fase 10; `produce/consume = "zip_anidado"`; `v_compacto` ya en
  la pestaña (Fase 6). **No** trocear `motor.py`.
- **Archivos afectados:** `motores/motor_{comprimir,descomprimir}.py`, `motores/formato_zip.py`,
  `clases/pestana_{comprimir,descomprimir}.py`, `gui/ayuda_contenido.py`, `tasks/__init__.py`,
  `tests/soporte/modulos.py`.
- **Dependencias:** Fase 8.
- **Riesgos:** compatibilidad de la marca `zip-anidado/1` y de `_estado_zip.jsonl`
  (migración del `.json` antiguo); caché de `leer_marca`; confirmación en hilo.
- **Criterio de finalización:** `motores/` y las pestañas de `clases/` vacíos; par en todas
  sus variantes; artefactos de referencia; confirmación de Descomprimir (P2) en GUI;
  `bench.py --todos` sin regresión; todo verde.
- **Resultado arquitectónico:** las 8 tareas son verticales.
- **ESTADO: HECHA** (2026-09-16). Último par migrado; `clases/` y `motores/` quedan solo
  con su `__init__.py`.
  - `tasks/comprimir/` y `tasks/descomprimir/` (motor, pestana, ayuda, descriptor).
    Comprimir `produce="zip_anidado"`, Descomprimir lo `consume`. `motor_comprimir` (1070
    líneas) se movió íntegro, sin trocear.
  - `tasks/formatos/formato_zip.py` (git mv); ambos motores importan de ahí la marca.
  - **Manifiesto en su forma final:** ya no importa `clases/` ni usa el helper `_desc`;
    todas las tareas entran por su `DESCRIPTOR`. `AYUDA_TAREAS` queda **vacío** (toda la
    Ayuda llega por los descriptores). `kakoli.py`/`modulos` repuntados; el mensaje de
    consola del arranque usa las rutas `tasks.*`.
  - **`bench.py` repuntado a `tasks.*`** (estaba roto tras mover los motores; el D12 pleno
    —reutilizar `tests/soporte`— queda para la Fase 13). **Verificado con round-trip real:**
    compresión, merge y aplanado byte-a-byte OK; la marca ZIP y `_estado_zip.jsonl` funcionan.
  - **Guardián:** `FORMATOS` (motores) queda vacío (todo bajo `tasks.formatos`); BASELINE
    VACÍA. Tests: CLI smoke de ambas; el par Comprimir↔Descomprimir (normal/compacto/
    paralelo/reanudación) y `info_reanudable` siguieron el movimiento sin cambios.
    **Suite: 240 passed** en 3.13; pyflakes limpio.

### Fase 13 — Retirada de la estructura antigua; `kakoli.py` raíz de composición

- **Objetivo:** eliminar lo transitorio y verificar empaquetado y consola.
- **Problemas que resuelve:** P5 (fachada) y P14 (parcial).
- **Cambios:** borrar `motores/`, `clases/` y los shims; `gui/ayuda_contenido.py` →
  `gui/ayuda.py` (solo sección general); `gui/constantes.py` solo con valores de la app;
  `kakoli.py` = `main` + `--version` + `App(REGISTRO)` sin re-exports (D10); `bench.py`
  importa `tasks.*` y `tests/soporte` (D12); `README.md` (estructura y consola).
- **Archivos afectados:** `kakoli.py`, `bench.py`, `gui/ayuda*.py`, `gui/constantes.py`,
  `tasks/__init__.py`, `build_nuitka.ps1` (si falla el análisis), `README.md`, `tests/soporte/**`.
- **Dependencias:** Fases 9, 10, 11 y 12.
- **Riesgos:** el empaquetador no encuentra módulos (mitigado por imports estáticos); scripts
  que usaban `kakoli.X`.
- **Criterio de finalización:** árbol = §8; ejecutable congelado arranca; consola
  `python -m tasks.<t>.motor --help` para las 8; build + `--version`; todo verde.
- **Resultado arquitectónico:** arquitectura objetivo implementada.
- **ESTADO: HECHA** (2026-09-16). Retirada de lo transitorio:
  - **Borrados `clases/` y `motores/`** (ya solo tenían `__init__.py`).
  - `gui/ayuda_contenido.py` → **`gui/ayuda.py`** (solo intro/cierre + `AYUDA_TAREAS`
    vacío como punto de extensión). `gui/constantes` queda con constantes de app +
    `politica_desde` + `_valor_ui`.
  - **`kakoli.py` = raíz de composición limpia** (D10): `main()` + `--version` +
    `App(REGISTRO)`, **sin re-exports** (ningún test dependía de `kakoli.X`). Docstring
    con el árbol `core/gui/tasks` y la cadena `core ← gui ← tasks ← kakoli`.
  - `bench.py` repuntado a `tasks.*` (hecho en la Fase 12). **Decisión sobre D12:** bench
    conserva sus propios generadores de árboles (más ricos que `tests/soporte`, y es una
    herramienta autónoma); no se le hace importar de `tests/` (sería raro que producción
    dependiera de tests). La duplicación menor es aceptable.
  - `README.md`: «Estructura del proyecto» reescrita (core/gui/tasks + cadena de
    dependencias + CLIs `python -m tasks.<t>.motor`).
  - **Verificado:** pyflakes limpio; `import kakoli` + `--version`; los 8 CLIs por sus
    `test_cli.py`; **build de Nuitka correcto** (exe + fuentes + `kakoli.ico`; ningún
    paquete propio ausente). El exe sin firmar no se ejecuta por la política de Windows
    App Control (ajeno al build). **Suite: 239 passed, 1 skipped** en 3.13.

### Fase 14 — Validación arquitectónica final y documentación

- **Objetivo:** convertir las reglas en garantías automáticas y dejar docs fiables.
- **Problemas que resuelve:** P14 y la protección futura de P3–P8.
- **Cambios:** `test_fronteras.py` sin lista de excepciones (todo estricto); **test «añadir
  tarea»** (paquete ficticio registrado solo en el test aparece en portada, se ejecuta con
  motor falso y recibe handoff, sin tocar `core/` ni `gui/`); reescribir `docs/ARQUITECTURA.md`;
  actualizar `docs/GUI.md` y `docs/escalabilidad.md`; marcar `docs/roadmap_*` como históricos.
- **Archivos afectados:** `tests/test_fronteras.py`, `tests/gui/test_extensibilidad.py`,
  `docs/*.md`, `README.md`.
- **Dependencias:** Fase 13.
- **Criterio de finalización:** guardián estricto en verde; test de extensibilidad pasa;
  `grep` de `nucleo|motores/|clases/|tres motores` sin resultados fuera de los roadmaps históricos.
- **Resultado arquitectónico:** arquitectura mantenible, verificada y documentada.
- **ESTADO: HECHA** (2026-09-16). Cierre:
  - **Guardián estricto** (`tests/test_fronteras.py`): BASELINE VACÍA; se limpió la
    clasificación (fuera las ramas de los esquemas antiguos `motores/clases` y el
    `_PREFIJOS` muerto), quedando reglas por rol del esquema final.
  - **Extensibilidad** (`tests/gui/test_extensibilidad.py`): `test_app_es_registro_driven`
    (las pestañas de App son exactamente las del registro) SIEMPRE corre, y el arranque con
    tareas ficticias + handoff prueba que añadir una tarea es solo un dato del registro
    (sin tocar `core/`/`gui/`).
  - **Docs:** `docs/ARQUITECTURA.md` **reescrito** (estructura core/gui/tasks, reglas de
    dependencia = las del guardián, contrato de motor, registro + handoff por artefacto,
    ejecución, invariantes, formatos y la receta para añadir una tarea). `GUI.md` y
    `escalabilidad.md` marcados como **HISTÓRICOS** con nota que apunta a ARQUITECTURA.md.
    `README.md` con el árbol nuevo. Corregidas las últimas docstrings con rutas obsoletas.
  - **Verificado:** grep de referencias obsoletas a `nucleo/motores/clases` en producción =
    solo la palabra genérica «motores» y la variable local `clases`. **Suite: 240 passed**
    en 3.13; pyflakes limpio; build de Nuitka correcto.

---

## 10. Dependencias entre fases

```text
Fase 0
  │
  ├──► Fase 1 ──┐
  └──► Fase 2 ──┴──► Fase 3 ──► Fase 4 ──┬──► Fase 5 ──┐
                                         ├──► Fase 6 ──┼──► Fase 8 ──┬──► Fase 9  ──┐
                                         └──► Fase 7 ──┘             ├──► Fase 10 ──┤
                                                                     ├──► Fase 11 ──┼──► Fase 13 ──► Fase 14
                                                                     └──► Fase 12 ──┘
```

- **F1 ∥ F2:** independientes; solo necesitan el andamiaje de la Fase 0.
- **F5, F6, F7:** lógicamente independientes, pero comparten `gui/app.py` y
  `gui/pestana_base.py`. Orden práctico: **5 → 6 → 7**.
- **F9–F12:** solo necesitan el patrón y el manifiesto de la Fase 8; comparten
  `tasks/__init__.py`, `gui/constantes.py` y `gui/ayuda_contenido.py`, así que en serie.
  Orden por riesgo creciente: **9 → 10 → 11 → 12**.

---

## 11. Tests y estrategia de validación

### 11.1 Capas de test

| Capa | Ubicación | Requiere | Qué valida | Comando |
|---|---|---|---|---|
| Unitarios de núcleo | `tests/core/` | stdlib | `recursos` (tabla de hilos), `paralelo`, `comun`, `registro`, `ejecucion` | `pytest tests/core` |
| Motores | `tests/tasks/<tarea>/` | `tmp_path` real | `ejecutar`, `rutas_validadas`, pausa/reanudación, 1 vs N hilos, seguridad | `pytest tests/tasks/<tarea>` |
| Pares | `tests/tasks/pares/` | `tmp_path` | Relación bidireccional e irreversibilidades | `pytest tests/tasks/pares` |
| Compatibilidad en disco | `tests/tasks/<tarea>/` + fixtures | artefactos versionados | Los formatos actuales se siguen leyendo | con su tarea |
| GUI | `tests/gui/` | Tk (marcador `gui`) | Arranque, navegación, bloqueo, handoff, mapeo `_validar`→`Opciones`, componentes | `pytest tests/gui` |
| Arquitectura | `tests/test_fronteras.py` | AST | Reglas de dependencia (§8) | `pytest tests/test_fronteras.py` |
| Consola | `tests/tasks/<tarea>/test_cli.py` | subprocess | `-m … --help`, códigos de salida | con su tarea |
| Build | manual | Nuitka | Ejecutable onefile arranca | Fases 4 y 13 |

### 11.2 Qué debe existir antes de cada parte

| Antes de… | Debe estar verde |
|---|---|
| Corregir (Fase 3) | Fase 1 + mapeo `_validar` de las 8 pestañas + `xfail` de P2 + guardián con lista de excepciones |
| Mover `nucleo` (Fase 4) | Lo anterior + `test_importa_todo` + carga de fuentes/icono |
| Cambiar el registro (Fase 5) | Tests GUI de navegación, orden de categorías y handoff de los 3 pares |
| Tocar `PestanaBase` (Fases 6–7) | Flujo completo GUI, pausa, cierre con tarea en marcha, bloqueo de `_bloqueables` |
| Migrar una tarea (Fases 8–12) | Tests de su motor, su mapeo `_validar`, su test de par (si lo tiene) y sus artefactos |
| Retirar lo antiguo (Fase 13) | Suite completa + humo de consola de las 8 |

### 11.3 Tests de pares sin crear dependencia arquitectónica

- **[R]** Viven solo en `tests/tasks/pares/`, un archivo por relación.
- Usan solo la API pública (`ejecutar` + `Opciones` + `rutas_validadas`), nunca funciones privadas.
- El guardián prohíbe que `tasks/X` importe `tasks/Y`; la relación está en los tests y en
  `tasks/formatos`.
- Propiedad: `Descomprimir(Comprimir(árbol)) == árbol`; `Descombinar(Combinar(...)) == ...`;
  `Desaplanar(Aplanar(...)) == ...`; con semillas fijas y los escenarios de `generar_arbol`.
- Irreversibilidades como tests explícitos (`final`, `reemplazar`, `crear_indice=False`, separador en el nombre).
- Comparación completa: recuento + firma (tamaño, mtime, sha256), no solo contenido.
- Renombrar y Eliminar (sin gemela): solo tests de motor.

### 11.4 Reglas para que los tests sobrevivan a la reestructuración

- Acceso a módulos vía `tests/soporte/modulos.py` hasta la Fase 13.
- No comparar textos de log, salvo prefijos contractuales (`[!]` y los de `_tag_log`).
- `PoliticaHilos(prioridad_baja=False)` en todos los tests (P22).
- `messagebox`/`filedialog` siempre sustituidos en los tests de GUI.
- Tests GUI con `withdraw()` y bombeo manual de `procesar_cola`, sin `mainloop`.

---

## 12. Componentes que NO deberían modificarse

### 12.1 Interfaces que deben preservarse **[R]**

- Contrato de motor `ejecutar(...) -> Resultado` e `info_reanudable(...)` opcional.
- `Resultado` (campos y estados).
- `OpcionesBase` y `PoliticaHilos` con sus defaults.
- Banderas de consola de cada motor (solo cambia la ruta del módulo, D11).
- Claves de `entradas` de cada motor (no unificar `principal`/`fuentes` de Combinar).

### 12.2 Comportamiento que no debe cambiar **[R]**

- Formatos en disco: marca `zip-anidado/1`, `_estado_zip.jsonl` (`zip-anidado-estado/2`) +
  migración del `.json`, `.kakoli_combinacion.json`, `.kakoli_aplanado.json`,
  `.kakoli_desaplanado.json`, `kakoli-reanudable/1`, archivo `PAUSA`, sufijos `.part`/`.__parcial__`.
- Reglas de `calcular_hilos`, `techo_hilos`, umbrales de throttling (0,25 / 0,75).
- Modelo hilo+cola+`_bomba`, variables Tk solo en `_validar`, una tarea a la vez, cierre ordenado.
- Aspecto visual y textos (reestructuración iso-visual).
- P17 y el timeout de 300 s de la confirmación: se anotan, no se cambian aquí.

### 12.3 Código que se mueve pero no se toca por dentro

`core/recursos.py` (sondas ctypes), `core/paralelo.py`, `_destino_seguro` de cada motor,
`motor_comprimir.py` completo, `gui/tema.py`, lógica de medición de `bench.py`.

### 12.4 Duplicación intencionada (no unificar)

`_copiar`, `_gana_entrante`, `_walk_rel`, `_destino_seguro` (semánticas distintas),
`PAUSE_NAME`, tuplas `CONFLICTOS`/`CRITERIOS`, `_CRITERIOS` de UI, `_actualizar_conflicto`,
`_destino_automatico`. Solo se elimina la duplicación de la **GUI común** (P11) y la de
**tests/bench** (D12).

### 12.5 Cambios que añadirían complejidad sin beneficio (no hacer)

Autodescubrimiento de tareas; clase base de motor; abstracción de «par»; capa de FS;
`logging`/bus de eventos/inyección de dependencias; micro-troceo de `recursos`/`paralelo`/
`comun`/`tema`; trocear `motor_comprimir.py` durante la migración; instanciación perezosa
de pestañas; persistencia de preferencias.

---

## 13. Riesgos globales de la reestructuración

| Riesgo | Prob. / impacto | Mitigación **[R]** |
|---|---|---|
| Regresión funcional no detectada (como P2) | Alta / alto | Fases 1–2 antes de mover; `pyflakes` cada fase; nunca mezclar movimiento y lógica |
| Imports rotos o ciclos al mover | Media / medio | Un grupo por fase; `test_importa_todo` con `-B`; guardián AST; `git mv` |
| Pérdida de compatibilidad de formatos | Baja / **alto** | Artefactos de referencia en la Fase 1; ninguna constante de formato cambia |
| El empaquetador no incluye módulos | Media / alto | Manifiesto con imports estáticos (D3); build de humo en Fases 4 y 13 |
| Regresiones de hilos al extraer el ejecutor | Media / alto | Tests del ejecutor sin Tk; flujo completo GUI; Tk solo en `_validar` |
| Regresión visual | Media / bajo | Capturas de `img/` tras Fases 4, 6, 7 y 13 (D15) |
| Estado intermedio incoherente | Media / medio | El manifiesto es la única fuente desde la Fase 8; cada fase termina en verde y revertible |
| Tests frágiles | Media / medio | Indirección `modulos.py`; comparar `Resultado` y disco; artefactos pequeños |
| Mezclar cambios pendientes | Alta / medio | D13 antes de la Fase 0; una rama; commits por fase |
| Corrupción UTF-8 al editar desde PowerShell | Media / medio | Editar `.py` solo con herramientas UTF-8 seguras; `pyflakes` + tests de import |
| Deriva de documentación | Alta / bajo | Reescritura solo al final (Fase 14) |
| Fases demasiado grandes | Media / medio | Fases 0–14 acotadas; alcance/archivos/criterio explícitos |
| Tests GUI no ejecutables sin pantalla | Baja / bajo | Marcador `gui` + salto con `TclError`; el resto corre por separado |

---

## 14. Orden recomendado de implementación

1. **Fases 0–2: primero la red de seguridad.** No hay tests y la última reorganización ya
   perdió un import (P2). La GUI se caracteriza aparte porque es lo que más cambia y lo
   único que requiere Tk.
2. **Fase 3: corregir antes de mover.** Aislar el cambio de comportamiento del movimiento.
3. **Fase 4: separar `core`/`gui` antes que las tareas.** Todo depende del núcleo; cada
   archivo se mueve una sola vez.
4. **Fase 5: invertir la dependencia antes de migrar tareas.** Cada migración cambia solo
   una línea del manifiesto.
5. **Fases 6–7: estabilizar la API común de la GUI antes de mover pestañas.**
6. **Fase 8: piloto con la tarea más simple.**
7. **Fases 9–12: riesgo creciente**, terminando por Compresión.
8. **Fase 13: retirar lo antiguo solo cuando nada lo usa.**
9. **Fase 14: blindar y documentar al final.**

---

## 15. Estado final esperado

**Estructura.** El árbol del §8: `core/` (5 módulos, stdlib, sin Tk), `gui/`, `tasks/` (8
carpetas autónomas + `formatos/` + manifiesto) y `tests/` reflejando esa estructura.

**Dependencias.** `core` no importa nada del proyecto salvo a sí mismo; `gui` solo importa
`core`; cada tarea importa `core`, la API común de `gui` y, en un par, su módulo de
`tasks/formatos`, nunca otra tarea; `kakoli.py` es la única pieza que une `gui` y `tasks`.
Todo comprobado por `tests/test_fronteras.py`.

**Extensibilidad.** Añadir una tarea = una carpeta + una línea en `tasks/__init__.py` + sus
tests. Lo demuestra un test con una tarea ficticia que aparece, se ejecuta y recibe un
handoff sin tocar `core/` ni `gui/`.

**Independencia.** Modificar una tarea solo edita archivos de su carpeta (y, en un par, su
formato compartido, protegido por el test del par). Ningún archivo compartido crece con el
número de tareas.

**Testabilidad.** Sin Tk: `core`, los 8 motores, formatos, registro y ejecutor.
Integración: los 3 pares. GUI: navegación, bloqueo, handoff y mapeo de controles a
`Opciones`. Cada área se ejecuta por separado.

**Lo que no cambia para el usuario.** Misma interfaz, textos y formatos en disco; mismo
rendimiento; mismas banderas de consola (solo cambia la ruta: `python -m tasks.<tarea>.motor`).

**Documentación.** `docs/ARQUITECTURA.md` describe el estado real, con las reglas de
dependencia reflejadas en el guardián y la receta para añadir una tarea; los roadmaps
anteriores quedan marcados como históricos.

**Fuera de alcance, para después:** trocear `motor_comprimir.py`, crear pestañas bajo
demanda, guardar preferencias entre sesiones, restaurar la prioridad del proceso, y separar
en `_validar` la validación de sus efectos secundarios (P17).

