# Roadmap · Zona de "arrastrar y soltar" (drag & drop) de carpetas

> Estado: **propuesta / análisis** (no implementado). Resuelve la decisión abierta de
> la **Fase 13** de [MEJORAS_GUI_FASES.md](MEJORAS_GUI_FASES.md) (§4.3, "Drag & drop →
> requiere dependencia externa → decisión de producto"). Este documento **no toca
> código**: analiza opciones, fija la recomendación y detalla el plan por fases.

---

## 1. Objetivo y alcance

Añadir, **debajo de la lista de carpetas agregadas** (el `Text` multilínea del campo
`Campo("mas", …, "lista")` de la pestaña **Combinar**), un **recuadro donde soltar
carpetas** arrastradas desde el explorador de archivos del sistema operativo. Al
soltar:

- Se **añaden** las carpetas a la lista (una por línea), reutilizando el flujo actual.
- Se **ignoran las duplicadas** (misma normalización que ya usa `_anexar_carpeta`).
- Se **filtran a directorios** (si se sueltan archivos, se descartan o se añade su
  carpeta contenedora — decisión en §6.3).

Requisitos de producto (del encargo):

1. **Multiplataforma**: Windows, Linux y macOS.
2. **Ligero**: sin penalizar arranque ni memoria en equipos antiguos.
3. **Compatible con Nuitka** (`--onefile`), que es el empaquetado actual
   ([BUILD_NUITKA.md](../BUILD_NUITKA.md), [build_nuitka.ps1](../build_nuitka.ps1)).
4. **Degradación elegante**: si la librería/binario no está disponible, la app sigue
   funcionando sin la zona de soltar (Examinar + escribir rutas siguen ahí).

Fuera de alcance por ahora: arrastrar carpetas *entre* widgets de la propia app,
arrastrar hacia fuera de la app, y DnD en campos que no sean de tipo `"lista"`.

---

## 2. Contexto técnico del proyecto (lo que condiciona la elección)

- **Stack**: Python 3.11+ / Tkinter (ttk, tema propio). **La app no tiene dependencias
  externas en runtime** ([requirements-dev.txt](../requirements-dev.txt) solo trae
  pytest y pyflakes). Introducir DnD **rompe** esa política: es una decisión consciente,
  acotada y **opcional** (la app debe compilar y correr aunque la librería no esté).
- **Root de Tk**: `class App(tk.Tk)` en [gui/app.py](../gui/app.py); en `__init__` se
  llama `tema.activar_dpi()` **antes** de `super().__init__()`. Cualquier carga de la
  extensión DnD debe respetar ese orden (cargarse *después* de crear el intérprete Tk).
- **Arquitectura por capas**: `core/` no importa Tk; `gui/` sí puede importar librerías
  externas; las fronteras las vigila `tests/test_fronteras.py` (AST). → El envoltorio de
  DnD debe vivir en `gui/` (p. ej. un nuevo `gui/dnd.py`), nunca en `core/`.
- **Control reutilizable**: la lista multilínea la construye la **base**
  (`PestanaBase._construir_campo_lista` en [gui/pestana_base.py](../gui/pestana_base.py)),
  así que añadir la zona ahí la hace **reutilizable por cualquier tarea** con un campo
  `"lista"` (hoy solo Combinar, pero queda disponible para futuras).
- **Empaquetado**: Nuitka `--onefile --plugin-enable=tk-inter`. El plugin `tk-inter`
  resuelve la Tcl/Tk estándar; **la extensión DnD es data aparte** que hay que incluir
  explícitamente (§5).

---

## 3. El problema real: DnD desde el SO necesita una extensión de Tcl/Tk

Tkinter **no trae** soporte para recibir "drops" del gestor de archivos del sistema.
Ese soporte lo aporta **tkdnd**, una extensión nativa de Tcl/Tk (protocolos XDND en
Linux, OLE en Windows, Cocoa/Carbon en macOS). Todas las opciones cross-platform
serias son, en el fondo, **envoltorios de Python sobre tkdnd**. Por eso el análisis
gira en torno a *cómo* se distribuye tkdnd, no a reinventarlo.

---

## 4. Análisis de opciones

### 4.1 Tabla comparativa

| Opción | Multiplataforma | Peso / overhead | Nuitka onefile | Mantenimiento | Veredicto |
|---|---|---|---|---|---|
| **tkinterdnd2** (PyPI, wrapper de tkdnd con binarios incluidos) | ✅ Win/Linux/macOS | Muy ligero (tkdnd ≈ cientos de KB; nativo, sin runtime pesado) | ✅ con `--include-package-data` (validar) | Activo | **Recomendado** |
| **tkinterdnd2-universal** (fork con binarios extra, p. ej. macOS arm64) | ✅ + arm64 mac | Igual | ✅ | Fork puntual | Alternativa si falla arm64 en el paquete base |
| **tkdnd "a pelo"** (extensión Tcl + `tk.call('package require tkdnd')`) | ✅ (según binarios que tú aportes) | Muy ligero | ✅ pero **tú** empaquetas y localizas los binarios | Manual | Solo si se quiere control total; más trabajo de build |
| **windnd** (ctypes, OLE) | ❌ **solo Windows** | Ultraligero (sin Tcl extra) | ✅ trivial | Escaso | Descartada (no cumple multiplataforma); posible *fallback* solo-Windows |
| **Qt/PySide, wxPython, pywebview** | ✅ | ❌ Pesados; cambian el toolkit | ✅/❔ | Activo | Descartadas (la app es Tkinter; contradicen "ligero") |
| **plyer u otras "utilidades"** | — | — | — | — | No ofrecen DnD de ficheros hacia Tk |

### 4.2 Por qué **tkinterdnd2**

- **Cumple los tres requisitos duros**: es multiplataforma (envuelve tkdnd para
  Win/Linux/macOS), **muy ligero** (tkdnd es una extensión nativa diminuta; no añade
  intérpretes ni frameworks — ideal para equipos antiguos) y **empaquetable con Nuitka**
  incluyendo su carpeta de datos.
- **Ergonomía**: API mínima —`drop_target_register(DND_FILES)` + `dnd_bind('<<Drop>>', …)`—
  y `tk.splitlist()` para parsear las rutas soltadas de forma robusta.
- **Licencia permisiva** (wrapper MIT; tkdnd, licencia estilo BSD/MIT): sin fricción para
  distribuir un ejecutable.
- **Aislable**: se puede envolver tras un `try/import` y activar solo si está presente
  (degradación elegante), sin volverla dependencia dura.

**Riesgo principal** (mitigable): la **localización de los binarios de tkdnd en runtime**
dentro del `--onefile` de Nuitka, y el **encaje de versiones de Tk** en Linux. Se validan
en el spike (Fase A) antes de comprometer la integración.

### 4.3 Licencias

- `tkinterdnd2`: **MIT**.
- `tkdnd`: licencia permisiva estilo **BSD/MIT**.
- Ambas permiten redistribución en un ejecutable cerrado sin obligaciones más allá de
  conservar el aviso de copyright. (Confirmar el texto exacto de la versión que se fije.)

---

## 5. Compatibilidad con Nuitka (`--onefile`)

El build actual usa `--onefile --plugin-enable=tk-inter` y `--include-package` para
`core/gui/tasks`. Para tkinterdnd2 hace falta **incluir sus datos** (los binarios y
`.tcl` de tkdnd que viven en `tkinterdnd2/tkdnd/<os-arch>/`):

- Añadir a [build_nuitka.ps1](../build_nuitka.ps1):
  - `--include-package=tkinterdnd2`
  - `--include-package-data=tkinterdnd2`  ← clave: arrastra los binarios de tkdnd.
  - (Si la localización automática fallara) `--include-data-dir=<venv>\Lib\site-packages\tkinterdnd2\tkdnd=tkinterdnd2/tkdnd`.
- En `--onefile`, Nuitka descomprime a un temporal y fija `__file__` del paquete; como
  tkinterdnd2 busca su carpeta `tkdnd` **relativa a su propio `__file__`**, con
  `--include-package-data` debería resolverla. **Hay que verificarlo** (el fallo típico
  es `Unable to load tkdnd library` → binario no empaquetado o ruta no encontrada).
- **Comprobación de humo** obligatoria: compilar y ejecutar el `.exe`, soltar una carpeta
  y confirmar que llega el `<<Drop>>`. Repetir en cada SO objetivo.

> Nota: el spike (Fase A) incluye un build mínimo de prueba **antes** de integrar la UI,
> para no descubrir un problema de empaquetado al final.

---

## 6. Diseño / integración (propuesto, para las fases de implementación)

### 6.1 Aislar la dependencia en `gui/dnd.py` (nuevo)

Un módulo pequeño que encapsule TODO lo externo y ofrezca una API neutra:

```
soporta_dnd() -> bool            # ¿está tkinterdnd2 + tkdnd disponible?
habilitar_en_root(root) -> bool  # carga tkdnd en el intérprete (una vez); None-safe
registrar_zona(widget, on_drop)  # drop_target_register + dnd_bind(<<Drop>>/<<DragEnter>>…)
parsear_rutas(root, data) -> list[str]   # tk.splitlist + normalización; PURO y testeable
```

Ventajas: el resto de `gui/` y las pestañas **no importan** tkinterdnd2 directamente;
si no está, `soporta_dnd()` devuelve `False` y no se crea la zona. `test_fronteras`
sigue verde (es un módulo de `gui/`).

### 6.2 Enganche en la base (reutilizable)

En `PestanaBase._construir_campo_lista(...)`, **debajo del `Text`** (y de su tirador de
redimensionado), añadir la zona **solo si `dnd.soporta_dnd()`**:

- Un recuadro con borde punteado y texto “Arrastra aquí carpetas para añadirlas”.
- Estados visuales: resaltar en `<<DragEnter>>` / restaurar en `<<DragLeave>>` (usar el
  verde `PRIMARY` del tema, coherente con el resto).
- `on_drop`: `rutas = dnd.parsear_rutas(root, event.data)` → filtrar a directorios →
  **reutilizar la deducción de duplicados** ya existente (ver §6.4) → insertar en el `Text`.

La carga de tkdnd en el intérprete (`habilitar_en_root`) se hace **una vez** desde
`App.__init__` (tras `super().__init__()`), no por pestaña.

### 6.3 Qué hacer con lo que se suelta

- **Directorios**: se añaden.
- **Archivos**: por defecto **ignorarlos** (el campo es "directorios a combinar").
  Alternativa a decidir en implementación: añadir su **carpeta contenedora**. Recomendado
  empezar por *ignorar* (comportamiento predecible) y, si se ve útil, ofrecer la carpeta
  contenedora con un aviso breve en el estado.
- **Mezcla / rutas con espacios**: `tk.splitlist(event.data)` maneja el formato de lista
  Tcl (rutas con espacios van entre llaves). No parsear "a mano".

### 6.4 Reutilizar la deducción de duplicados

Hoy la normalización/dedup vive dentro de `_anexar_carpeta`
([gui/pestana_base.py](../gui/pestana_base.py)) y en `componentes.elegir_carpetas`
([gui/componentes.py](../gui/componentes.py)). Antes de la Fase C conviene **extraer** un
helper común (p. ej. `componentes.anexar_rutas(txt, nuevas)` o una función de
normalización) para que Examinar y Drop compartan exactamente la misma lógica y no se
dupliquen reglas.

---

## 7. Consideraciones multiplataforma (a validar en el spike)

- **Windows**: caso principal; OLE DnD vía tkdnd. Suele "funcionar y ya".
- **Linux/X11**: XDND. **Encaje de versión de Tk**: el binario de tkdnd empaquetado debe
  casar con la Tk del sistema/con la que embebe Nuitka (habitualmente 8.6). Riesgo si el
  entorno trae Tk 9. **Wayland**: las apps corren sobre XWayland, así que suele ir, pero
  puede haber matices; probar en un escritorio Wayland real.
- **macOS**: DnD Cocoa vía tkdnd. **Apple Silicon (arm64)** necesita binario arm64 (paquete
  base reciente o el fork `-universal`). Para distribuir un `.app`/`.dmg` hará falta
  **firma/notarización** (ajeno a este roadmap, pero anotado).
- **Equipos antiguos**: tkdnd es nativo y minúsculo; el coste es despreciable. La zona se
  dibuja con widgets Tk normales (sin animaciones costosas).

---

## 8. Plan por fases

> Cada fase termina en verde (pyflakes + suite) y se commitea por separado, como el resto
> del proyecto. El código de la app sigue **compatible con Python 3.11** y **sin
> dependencia dura** (la DnD es opcional).

### Fase A · Spike técnico (time-boxed, ~medio día) — **bloqueante**
- Instalar `tkinterdnd2` en el venv de desarrollo.
- Prototipo mínimo (fuera del árbol de la app): cargar tkdnd en un `tk.Tk` existente con
  `TkinterDnD._require(root)` y recibir un `<<Drop>>` real de una carpeta en **Windows**.
- **Build de humo con Nuitka `--onefile`** del prototipo con
  `--include-package-data=tkinterdnd2`; ejecutar el `.exe` y confirmar el drop.
- Si es viable, repetir el drop en Linux y macOS (aunque sea en fase manual posterior).
- **Salida**: decisión Go/No-Go documentada + la receta exacta de flags de Nuitka.

### Fase B · Módulo `gui/dnd.py` + parser testeable
- Implementar `soporta_dnd`, `habilitar_en_root`, `registrar_zona`, `parsear_rutas`.
- **Tests** del parser (`parsear_rutas`) y de `soporta_dnd()` (bool), sin depender de que
  la librería esté instalada (skips si no está). Es la parte **automatizable**.

### Fase C · Zona visual en la base + reutilización de dedup
- Extraer el helper común de "anexar rutas sin duplicar" (§6.4) y hacer que Examinar lo use.
- Dibujar la zona bajo el `Text` **solo si `soporta_dnd()`**; estados hover; filtro a
  directorios; enganche del `on_drop` al helper común.
- Cargar tkdnd una vez desde `App.__init__` (tras `super().__init__()`).

### Fase D · Empaquetado Nuitka
- Actualizar [build_nuitka.ps1](../build_nuitka.ps1) con los flags de la Fase A.
- Actualizar [BUILD_NUITKA.md](../BUILD_NUITKA.md) (nueva dependencia opcional + notas).
- Añadir `tkinterdnd2` a un extra opcional de `requirements-dev.txt` (comentado/aparte),
  dejando claro que es opcional.

### Fase E · Pruebas cross-platform, degradación y cierre
- Matriz manual: Win / Linux (X11 y, si se puede, Wayland) / macOS (Intel y arm64):
  soltar 1 carpeta, varias, con espacios, duplicadas, archivos sueltos.
- Verificar **degradación elegante** (desinstalar la librería → la app arranca sin zona).
- Documentar resultados y marcar la Fase 13 (§4.3) de MEJORAS_GUI_FASES como resuelta.

---

## 9. Estrategia de pruebas

- **Automatizable** (CI, sin GUI real): `parsear_rutas` (formato lista Tcl, llaves,
  espacios, normalización), el helper de dedup, y que la zona **no** se cree cuando
  `soporta_dnd()` es `False` (monkeypatch).
- **No automatizable de forma fiable**: el evento `<<Drop>>` real del SO. Se cubre con la
  **matriz manual** de la Fase E. (Inyectar un `<<Drop>>` sintético con `event_generate`
  es frágil y no representa el SO; se puede usar como prueba de humo interna, no como
  garantía.)
- La suite debe **pasar igual con o sin** tkinterdnd2 instalado (tests marcados `skip` si
  falta).

---

## 10. Riesgos y mitigaciones

| Riesgo | Impacto | Mitigación |
|---|---|---|
| tkdnd no se localiza en el `--onefile` | El `.exe` no hace DnD | Spike con build de humo (Fase A) **antes** de integrar; flag `--include-package-data` y, si hace falta, `--include-data-dir` |
| Desajuste de versión de Tk en Linux | Falla la carga de tkdnd | Fijar binarios que casen con la Tk embebida por Nuitka; probar en distro objetivo |
| macOS arm64 sin binario | No funciona en Apple Silicon | Usar paquete base reciente o fork `-universal`; probar en arm64 |
| Introducir dependencia dura por error | Rompe "sin dependencias" y el build sin la lib | Aislar en `gui/dnd.py` tras `try/import`; `soporta_dnd()` gobierna todo; tests con y sin la lib |
| Regresión al tocar la base compartida | Afecta a `"lista"` (y futuras tareas) | Cambios detrás de `soporta_dnd()`; suite de la base verde; helper de dedup con tests |
| Firma/notarización en macOS al distribuir | Bloqueo de Gatekeeper | Fuera de alcance aquí, pero anotado para la distribución |

---

## 11. Recomendación

**Adoptar `tkinterdnd2`** como dependencia **opcional**, aislada en `gui/dnd.py`, con la
zona de soltar dibujada en la base (`_construir_campo_lista`) **solo si está disponible**,
y empaquetada en Nuitka con `--include-package-data=tkinterdnd2`. Es la única familia de
opciones que satisface a la vez *multiplataforma + ligera + compilable con Nuitka*, y su
naturaleza opcional preserva la filosofía "sin dependencias duras" del proyecto.

**Siguiente paso concreto**: ejecutar la **Fase A (spike técnico)**, cuyo build de humo con
Nuitka es el que confirma —o descarta— la viabilidad real antes de invertir en la UI.
```
