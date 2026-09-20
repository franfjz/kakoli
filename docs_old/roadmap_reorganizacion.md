# Roadmap: renombrar a «kakoli» + reorganizar en `motores/` y `clases/`

Tres objetivos (este documento **solo planifica**, no toca código):

1. **Nombre final = «kakoli»**: sustituir el codename antiguo *Zip Anidado* / `ZipAnidado`
   / `zip_anidado` por **kakoli**, y fijar la **versión = «0.9»**.
2. **Carpeta `motores/`** con todos los archivos de motor.
3. **Carpeta `clases/`** con un archivo por clase de la GUI (trocear `kakoli.py`).

Meta: archivos **más cortos y comprensibles** para quien no conoce la arquitectura,
sin cambiar el comportamiento. Fecha: 2026-09-10.

---

## 1. Estado actual (medido)

| Archivo | Líneas | Clases | Rol |
|---|---:|---|---|
| `kakoli.py` | 2033 | 12 (Campo, Categoria, PestanaBase, 8×`Pestana*`, App) | GUI + entry point |
| `motor_comprimir.py` | 1098 | 5 (Opciones, InfoDir, Estado, Planificador, Comprimidor) | motor |
| `motor_descomprimir.py` | 469 | 2 | motor |
| `motor_combinar.py` | 424 | 1 | motor |
| `motor_aplanar.py` | 397 | 1 | motor |
| `motor_desaplanar.py` | 363 | 1 | motor |
| `motor_eliminar.py` | 308 | 1 | motor |
| `motor_renombrar.py` | 300 | 1 | motor |
| `motor_descombinar.py` | 221 | 1 | motor |
| `comun.py` | 294 | 4 | núcleo compartido |
| `recursos.py` | 854 | 2 | núcleo (perfil + hilos) |
| `paralelo.py` | 226 | 4 | núcleo (ejecutor) |
| `tema.py` | 475 | 0 | tema visual |

**Grafo de imports**: `recursos ← paralelo ← comun ← motor_* ← kakoli`. Cruces entre
gemelos: `motor_descomprimir`←`leer_marca` de comprimir; `motor_descombinar`←
`cargar_indice`/`INDICE_NOMBRE` de combinar; `motor_desaplanar`←`separador_ok`/
`REGISTRO_NOMBRE` de aplanar. `bench.py` y los tests importan motores + `kakoli`. Los
motores son además **CLIs autónomos** (`python motor_X.py ...`).

---

## 2. Parte 1 — Nombre «kakoli» + versión «0.9»

Hay que distinguir **tres cosas** que hoy se solapan:

- **Codename antiguo** (a sustituir → «kakoli»): `zip_anidado` (docstring de `kakoli.py`),
  `ZipAnidado` (salida de `--version`: `print(f"ZipAnidado {VERSION}")`, y el docstring
  del comando `--name ZipAnidado`).
- **Formato/técnica** (**NO se toca**): «ZIP anidado» = los zips anidados que produce la
  compresión (p. ej. «genera un .zip anidado», «Formato del ZIP anidado», «Rehace el árbol
  a partir de un ZIP anidado»). Es el nombre de la técnica, no de la app.
- **Marca visible** (decisión N-marca): título de ventana `"Carpetas en ZIP anidados"` y
  la etiqueta `"CARPETAS EN ZIP"` del pie. Son descriptivos; hay que decidir si pasan a
  «kakoli».

Cambios concretos de la Parte 1:
- `VERSION = "1.0"` → `VERSION = "0.9"`.
- Docstring de `kakoli.py` (`zip_anidado.py — …` y `--name ZipAnidado zip_anidado.py`) →
  `kakoli.py` / `--name kakoli`.
- `print(f"ZipAnidado {VERSION}")` → `print(f"kakoli {VERSION}")`.
- Marca/título (según N-marca): p. ej. `self.title("kakoli")` y etiqueta de marca
  «kakoli» (opcionalmente con el subtítulo descriptivo «Carpetas en ZIP anidados»).
- Docs (`docs/*.md`, `README.md`): revisar textos; conservar «ZIP anidado» donde sea el
  formato.

Es un cambio de bajo riesgo (texto), independiente de la reorganización → **Fase 0**.

---

## 3. Parte 2 — Paquete `motores/`

Mover los **8** `motor_*.py` a `motores/` con un `__init__.py`, y **extraer las piezas
compartidas entre gemelos** a módulos con nombre por concepto dentro de `motores/`
(R-compartido): `motores/formato_zip.py` (`leer_marca` + la marca), `motores/
indice_combinacion.py` (`cargar_indice`/`guardar_indice`/`INDICE_NOMBRE`),
`motores/nombres_aplanado.py` (`separador_ok`/`aplanar_nombre`/`desaplanar_nombre`/
`REGISTRO_NOMBRE`). Así descomprimir/descombinar/desaplanar importan del módulo
compartido, no del motor gemelo. El **núcleo** va a su propia carpeta `nucleo/` (R-nucleo,
ver Parte 4b).

**Estilo de imports (decisión R-imports)** — recomendado:
- Dentro de cada motor: `import comun` / `import recursos` / `import paralelo` (absolutos;
  la raíz está en `sys.path` al ejecutar desde ella o vía `-m`).
- Cruces entre gemelos: **imports relativos** dentro del paquete, p. ej.
  `from .motor_combinar import cargar_indice, INDICE_NOMBRE`.
- `kakoli.py` y `bench.py`: `from motores import motor_comprimir as mcomp`, etc.
- **CLIs**: pasan a ejecutarse como módulo del paquete → `python -m motores.motor_comprimir
  CARPETA ...` (los imports relativos exigen contexto de paquete; `python motores/
  motor_X.py` directo dejaría de funcionar). Se documenta en `--help`/README.

**Qué se actualiza**: los 9 imports de `kakoli.py`, los de `bench.py`, los 3 cruces
entre gemelos, y los **imports de motor de los tests** (`import motor_X` →
`from motores import motor_X`). El empaquetador (que sigue el grafo de imports desde `kakoli.py`) sigue detectando
los motores por el grafo de imports; no hace falta tocar `datas`/`icon` del `.spec`.

---

## 4. Parte 3 — Paquete `clases/` (trocear `kakoli.py`)

`kakoli.py` (2033 líneas) es el archivo que más gana al partirse. Propuesta: un archivo
por **clase de la GUI** + un par de módulos para lo que no es clase (constantes,
contenido de ayuda). Núcleo (`comun`/`recursos`/`paralelo`) **no** se trocea (sus clases
están fuertemente acopladas a sus funciones; separarlas dispersaría y **empeoraría** la
comprensión — justo lo contrario del objetivo); ver decisión R-alcance.

Estructura propuesta de `clases/`:
```
clases/
├─ __init__.py
├─ modelos.py          # Campo, Categoria (dataclasses de apoyo)   [o campo.py + categoria.py]
├─ constantes.py       # VERSION/AUTOR/URLs, _POLITICAS/_CRITERIOS/_CODIGOS/_MODOS_NOMBRE/
│                       #   _POLITICAS_APLANAR/_DESAPLANAR/_CONFLICTOS_RENOM, _valor_ui, politica_desde
├─ ayuda_contenido.py  # AYUDA_SECCIONES (el README interno, ~80 líneas)
├─ pestana_base.py     # PestanaBase (la base ~430 líneas)
├─ pestana_comprimir.py, pestana_descomprimir.py, pestana_eliminar.py,
│  pestana_combinar.py, pestana_descombinar.py, pestana_aplanar.py,
│  pestana_desaplanar.py, pestana_renombrar.py     # una por pestaña
├─ menu.py             # App.MENU + wiring de produce_hacia (importa todas las pestañas)
└─ app.py              # App (la ventana principal ~600 líneas)
```

**Orden de imports / dependencias** (evitar ciclos):
- `pestana_base` importa `modelos`, `constantes`, motores (para tipos) — o los motores se
  importan en cada pestaña concreta, no en la base.
- Cada `pestana_X` importa `PestanaBase`, su motor (`from motores import motor_X`) y las
  constantes que use.
- `menu.py` importa **todas** las pestañas, construye `MENU` y fija los
  `produce_hacia` (`PestanaComprimir.produce_hacia = PestanaDescomprimir`, etc.) — así el
  *wiring* que hoy está suelto al final de `kakoli.py` queda en un solo sitio claro.
- `app.py` importa `menu` (para `MENU`), `constantes`, `ayuda_contenido`, `tema`.
- **`kakoli.py` queda como entry point fino**: importa `App` de `clases.app`, define
  `main()` y el `if __name__ == "__main__"`, y **re-exporta** los nombres públicos
  (`App`, todas las `Pestana*`, `Campo`, `Categoria`, alias de motores, constantes usadas
  por tests) para no romper `import kakoli; kakoli.X` (tests, scripts). Esa fachada
  minimiza el impacto y da una **API pública** clara del proyecto.

---

## 5. Decisiones (RESUELTAS por el usuario, 2026-09-10)

- **R-marca — RESUELTA.** La marca/título pasan a **«kakoli»**, con **subtítulo
  "Herramientas de gestión de directorios y archivos"** (NO «Carpetas en ZIP anidados»).
  El formato «ZIP anidado» se mantiene en los textos técnicos.
- **R-nucleo — RESUELTA: SÍ.** Se crea una carpeta **`nucleo/`** con `comun`, `recursos`,
  `paralelo` y `tema` (el framework transversal, agnóstico de dominio).
- **R-compartido — RESUELTA (por el usuario): separar el código compartido de los motores
  específicos.** Hoy hay piezas compartidas entre gemelos que viven DENTRO de un motor
  (difíciles de localizar cuando haya muchos motores): `leer_marca` (en `motor_comprimir`,
  la usa descomprimir), `cargar_indice`/`guardar_indice`/`INDICE_NOMBRE` (en
  `motor_combinar`, las usa descombinar), `separador_ok`/`aplanar_nombre`/
  `desaplanar_nombre`/`REGISTRO_NOMBRE` (en `motor_aplanar`, las usa desaplanar). Se
  **extraen a módulos compartidos con nombre por concepto** dentro de `motores/` (p. ej.
  `motores/formato_zip.py`, `motores/indice_combinacion.py`, `motores/nombres_aplanado.py`)
  para que ningún motor "esconda" código que otros necesitan; ambos gemelos importan del
  módulo compartido. (No van a `nucleo/` porque son de dominio, no framework agnóstico.)
- **R-alcance — RESUELTA: separación amplia.** Se troceará **por clase** también el
  núcleo: las clases de `comun`/`recursos`/`paralelo` van a archivos independientes dentro
  de `nucleo/` (Resultado, OpcionesBase, RegistroReanudable, Interrupcion; PerfilSistema,
  PoliticaHilos; Plan, PlanLista, Ejecutor…), con un módulo de funciones/constantes por
  paquete. Prioridad: que a largo plazo cada pieza sea fácil de localizar aunque al
  principio haya más archivos.
- **R-imports** — Estilo de imports de los paquetes (`nucleo/`, `motores/`, `clases/`) e
  imports relativos entre módulos del mismo paquete; CLIs de motor vía `python -m
  motores.motor_X`. Propuesta: aceptar.
- **R-dataclasses** — `Campo`/`Categoria`: un archivo cada una (coherente con la
  separación por clase); `clases/campo.py` + `clases/categoria.py`.

---

## 6. Fases

- **Fase 0 — Nombre «kakoli» + versión 0.9.** Sustituir codename (`ZipAnidado`/
  `zip_anidado`) por «kakoli», `VERSION="0.9"`; título/marca «kakoli» + subtítulo
  «Herramientas de gestión de directorios y archivos». Conservar «ZIP anidado» como
  formato. Actualizar `README.md`/`docs`. **Sin mover archivos.** Verificar: la app
  arranca, `--version` dice «kakoli 0.9», suite verde.
  **ESTADO: HECHA** (2026-09-10). `VERSION="0.9"` + nueva const `SUBTITULO`; docstring de
  `kakoli.py` actualizado (nombre + lista de tareas al día); marca del pie «CARPETAS EN
  ZIP»→**«kakoli»** con subtítulo debajo; `self.title("kakoli")`; `--version` → «kakoli
  0.9». Conservado «ZIP anidado» como formato (comprimir/descomprimir, §4 docs). README
  (título/tagline) y `docs/ARQUITECTURA.md` (referencia a `zip_anidado`) actualizados;
  capturas regeneradas (pie «kakoli v0.9» + subtítulo). Sin restos de codename. Verificado:
  arranque + `--version` + suite verde.
- **Fase 1 — Paquete `nucleo/`.** Crear `nucleo/` (con `__init__.py`); mover `comun`,
  `recursos`, `paralelo`, `tema`, troceando sus clases en archivos independientes
  (R-alcance) con un módulo de funciones/constantes por paquete. Arreglar imports de todos
  los que dependen del núcleo (motores, kakoli, bench, tests). Verificar suite + bench.
  **ESTADO: HECHA** (2026-09-10). Creado el paquete `nucleo/` (`__init__.py` + los 4
  módulos). **REFINAMIENTO de R-alcance**: los 4 módulos se movieron **cohesivos, sin
  micro-trocear sus clases** — `recursos` (medir el equipo + calcular hilos), `paralelo`
  (ejecución paralela) y `tema` (paleta+estilos+fuentes) son de una sola responsabilidad y
  separar `PerfilSistema`/`PoliticaHilos` de las funciones que las construyen, o los
  colores de los estilos, crearía acoplamiento entre archivos y **empeoraría** la claridad.
  El troceo por clase (el gran beneficio) se reserva para las 12 clases de la GUI en
  `clases/` (fases 3-4). Cambios: `nucleo/comun.py` usa `from . import recursos`;
  `nucleo/tema.py` calcula `_DIR_FUENTES` de forma robusta (`_raiz_datos()`: sube un nivel
  `nucleo/→raíz` en fuente, datos empaquetados junto al ejecutable). Imports repuntados a `from nucleo
  import X` / `from nucleo.comun import Y` en kakoli, bench, los 8 motores y 13 tests
  (incluidos imports combinados `import kakoli, tema`). Verificado: `--version` = «kakoli
  0.9», app arranca con fuentes registradas, **build del `.spec` OK** (exe + 4 ttf; el
  `.exe` frozen importa y da «kakoli 0.9»), suite 31/31 + los 4 bench. Limpiados los `.pyc`
  huérfanos del núcleo en el `__pycache__` raíz.
- **Fase 2 — Paquete `motores/` + módulos compartidos.** Crear `motores/`; mover los 8
  `motor_*.py`; **extraer** `formato_zip.py` / `indice_combinacion.py` /
  `nombres_aplanado.py` (R-compartido) y repuntar los gemelos a ellos. Imports relativos
  dentro del paquete; CLIs a `python -m motores.motor_X`. Verificar: suite + 4 bench + CLIs.
  **ESTADO: HECHA** (2026-09-10). **2a — movimiento**: paquete `motores/` (`__init__.py` +
  los 8 motores). Imports cruzados → relativos temporales; luego repuntados. Externos:
  kakoli y bench `from motores import motor_X as mX`; 10 tests scratchpad vía sed
  (incluidos **imports combinados e indentados** `import kakoli, tema` / `    import
  motor_aplanar as ma` que los grep `^import` no pillaban). CLIs a `python -m
  motores.motor_X` (descomprimir/descombinar/desaplanar usan imports relativos → requieren
  `-m`). **2b — extracción de compartidos**: `motores/formato_zip.py` (`MARCA_FORMATO`,
  `leer_marca` + caché; comprimir escribe la marca, descomprimir la lee),
  `motores/indice_combinacion.py` (`INDICE_NOMBRE`/`INDICE_FORMATO`/`cargar_indice`/
  `guardar_indice`; combinar+descombinar), `motores/nombres_aplanado.py` (`separador_ok`/
  `aplanar_nombre`/`desaplanar_nombre`/`_sanea_seg` + `REGISTRO_APLANADO`/
  `REGISTRO_DESAPLANADO`; aplanar+desaplanar). **Ya NO hay imports cruzados entre motores**
  (los gemelos importan del módulo compartido, no del gemelo). Quitados imports sin uso
  (`json` en combinar, `functools` en comprimir); reexpuestas las funciones como atributos
  del motor para compat de tests (`ma.aplanar_nombre`, `mc.INDICE_NOMBRE`…). Verificado:
  suite **31/31** + 4 bench + **build del `.spec`** (exe + 4 ttf; `.exe` frozen «kakoli
  0.9»; nucleo y motores en el PYZ). Limpiados los `.pyc` huérfanos de motores en la raíz.
- **Fase 3 — `clases/`: base y apoyo.** Crear `clases/` con `campo.py`, `categoria.py`,
  `constantes.py`, `ayuda_contenido.py` y `pestana_base.py` (extraídos de `kakoli.py`).
  `kakoli.py` re-exporta. Verificar suite.
  **ESTADO: HECHA** (2026-09-11). Paquete `clases/` (`__init__.py`) con: `campo.py`
  (`Campo`), `categoria.py` (`Categoria`), `constantes.py` (VERSION/SUBTITULO/enlaces +
  ajustes GUI + `politica_desde` + los mapeos `_POLITICAS`/`_CRITERIOS`/`_CODIGOS`/
  `_MODOS_NOMBRE`/`_POLITICAS_APLANAR`/`_POLITICAS_DESAPLANAR`/`_CONFLICTOS_RENOM` +
  `_valor_ui`), `ayuda_contenido.py` (`AYUDA_SECCIONES`) y `pestana_base.py`
  (`PestanaBase`, ~540 líneas; usa tema/recursos/comun/Campo/politica_desde, sin motores
  ni App → sin ciclos: las refs a `App`/subclases son anotaciones-string). `kakoli.py`
  **re-exporta** todo desde `clases/` (los Pestana*/App siguen usándolo por nombre) y
  pasó de **2037 → 1314 líneas**. Extracción con `sed` (bloques exactos) + borrado por
  rango de línea (script). Verificado: `--version` = «kakoli 0.9», App arranca (8 tareas,
  Ayuda abre), suite **31/31** + 4 bench + build del `.spec`.
- **Fase 4 — `clases/`: pestañas + App + entry point.** Un archivo por `Pestana*`,
  `menu.py` (MENU + produce_hacia), `app.py` (App); `kakoli.py` queda fino (main + CLI +
  re-exports). Verificar suite + captura (la GUI idéntica).
  **ESTADO: HECHA** (2026-09-11). 8 archivos `clases/pestana_*.py` (uno por tarea, con
  imports mínimos calculados por análisis de símbolos), `clases/menu.py` (el `MENU` de dos
  niveles + los 3 `produce_hacia`, sacados de dentro de `App`), `clases/app.py` (la clase
  `App`, ~600 líneas; `MENU = MENU` viene de `clases/menu.py`). `kakoli.py` pasó a ser un
  **entry point fino de 73 líneas** (antes 1323): `main()` + `--version` + `if __name__`,
  y **re-exporta** por compatibilidad todo lo público (`App`, las 8 `Pestana*`,
  `PestanaBase`/`Campo`/`Categoria`, `AYUDA_SECCIONES`, las constantes, `Resultado` y los
  alias de motor `mcomp`/`maplan`/… — verificado contra los `kakoli.X` que usan los tests).
  **Sin ciclos**: `app → menu → pestana_* → (pestana_base, motores, constantes)`; las refs
  a `App`/subclases en las pestañas son anotaciones-string. CLI de arranque actualizada a
  `python -m motores.motor_X`. Verificado: `--version` = «kakoli 0.9», App instancia +
  navega + Ayuda, suite **31/31** + 4 bench + build del `.spec`. `__pycache__` raíz
  eliminado (kakoli.py ya no genera artefactos de clases).
- **Fase 5 — Docs + verificación cruzada.** Actualizar `docs/ARQUITECTURA.md` (mapa de
  módulos con `nucleo/`, `motores/`, `clases/` y la cadena de imports), `docs/GUI.md`,
  `README.md` (estructura del proyecto) y la memoria. Suite + 4 bench + build del `.spec`.
  Limpieza de `__pycache__`.
  **ESTADO: HECHA** (2026-09-11). `README.md`: nueva "Estructura del proyecto" con los 3
  paquetes (árbol nucleo/·motores/·clases/) + la cadena de imports. `docs/ARQUITECTURA.md`
  §2: mapa de módulos reescrito y agrupado por paquete (con los formatos compartidos y el
  paquete `clases/`) + cadena de imports `nucleo ← motores ← clases ← kakoli`. `docs/GUI.md`:
  el código de la GUI vive en `clases/`, CLI de motor a `python -m motores.motor_X`.
  Limpiados todos los `__pycache__`. Verificado: suite 31/31 + 4 bench + build del `.spec`
  (exe + 4 ttf, `.exe` frozen «kakoli 0.9») + portada idéntica.

---

## REORGANIZACIÓN — COMPLETA (fases 0–5)

Renombre a **kakoli 0.9** (marca «kakoli» + subtítulo «Herramientas de gestión de
directorios y archivos») y reestructuración en tres paquetes por capas
**`nucleo/`** (framework) ← **`motores/`** (una tarea por motor + formatos compartidos
`formato_zip`/`indice_combinacion`/`nombres_aplanado`) ← **`clases/`** (la GUI: `Campo`,
`Categoria`, constantes, Ayuda, `PestanaBase`, una `pestana_*` por tarea, `menu`, `app`),
con `kakoli.py` como entry point fino (73 líneas, re-exporta la API por compat). Sin
cambios de comportamiento (GUI idéntica); suite + 4 bench + build verdes en cada fase.

Orden: 0 → 1 → 2 → 3 → 4 → 5 (núcleo primero — todo depende de él; luego motores; luego la
GUI; cada fase deja la suite en verde).

---

## 7. Riesgos y notas

- **Imports rotos / ciclos**: el mayor riesgo. Se mitiga con el orden de fases (motores
  primero, luego GUI), imports relativos solo entre gemelos, `menu.py` como único punto de
  *wiring*, y `kakoli.py` como fachada que re-exporta.
- **CLIs de los motores**: pasan a `python -m motores.motor_X` (imports relativos). Hay
  que documentarlo (`--help`, README) y ajustar cualquier script que los invoque directo.
- **Tests del scratchpad (~30)**: importan `motor_X` y `kakoli.X`. Los de `kakoli.X`
  siguen porque `kakoli.py` re-exporta; los de `motor_X` se actualizan a `from motores
  import motor_X`. Es trabajo mecánico pero hay que hacerlo para verificar cada fase.
- **Empaquetado**: el compilador sigue el grafo de imports desde `kakoli.py` → detecta
  `motores.*` y `clases.*` solos; `datas`/`icon` no cambian. Se reconstruye en Fase 4 para
  confirmar.
- **Docs y memoria**: referencian rutas `motor_*.py`, `kakoli.py`. Se actualizan en la
  Fase 4 (mapa de módulos, estructura del README, `MEMORY.md`).
- **Comportamiento**: la reorganización es **puramente estructural**; ninguna lógica
  cambia. La verificación (suite + bench + captura idéntica de la GUI) es la red de
  seguridad.
