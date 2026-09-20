# GUI de kakoli — selectores y su significado

> ⚠️ **DOCUMENTO HISTÓRICO.** Los selectores y su mapeo a opciones del motor siguen
> siendo válidos, pero las RUTAS de código están desfasadas: la GUI vive ahora en
> `gui/` y cada pestaña en `tasks/<tarea>/pestana.py` (ya no en `clases/`). Para la
> estructura y las reglas actuales, ver `ARQUITECTURA.md`. El mapeo GUI→motor lo
> congela `tests/gui/test_validar.py`.

Referencia detallada de **todos los selectores de las pestañas** de la interfaz
gráfica (código en el paquete `clases/`; `kakoli.py` solo la lanza): qué son, tipo
de control, variable interna, valor por defecto, a qué opción del motor mapean, qué
función los lee y qué consecuencia tienen en el resultado.

> Nota: la GUI expone un subconjunto de las opciones de los motores; las que solo
> están por consola se listan al final (sección 8).

---

## 1. Estructura común y flujo

**Ventana**: abre **maximizada** (`self.state("zoomed")` + `geometry` al área de
trabajo, `App._area_trabajo()` → Windows `SPI_GETWORKAREA`).

**Menú en DOS NIVELES** (categorías → tareas; ver `roadmap_menu_pestanas.md`):
`App.MENU` agrupa las tareas por categoría (Combinación / Compresión / Aplanado /
Renombrado / Eliminar), cada una con una `descripcion`. La izquierda es `barra_nav`
(fila de botones-pestaña) + `area_tarea` (donde se muestra la tarea activa).
**Nivel 1 = portada SOLO con tarjetas** (recuadro con nombre + descripción + tareas);
la `barra_nav` se **oculta** en este nivel. **Nivel 2** = `[ ← ]` (volver) + las tareas
de la categoría. Se recuerda la última tarea abierta de cada categoría. Añadir una
categoría/tarea = editar `App.MENU`. Una **tarjeta final "Ayuda"** abre una vista
scrollable de solo lectura (README con una sección técnica por tarea, `AYUDA_SECCIONES`;
barra reducida a `[ ← ]`).

**Monitor derecho COMPARTIDO** (a nivel `App`, ancho fijo): (1) **"Equipo
detectado"** (`lbl_perfil`/`_texto_perfil`: núcleos, RAM libre, disco, paralelo
recomendado, batería); (2) **"Consola"** = el **registro** (`texto_log`, con tags
de color por prefijo; su barra de scroll **solo aparece cuando el contenido no
cabe**) + el checkbox único **"Registro detallado"**
(`App.v_detallado`); (3) **info de la app** (marca + versión + enlaces
`@franfjz`/☕). El registro y el detallado son ÚNICOS (compartidos por todas las
tareas).

**Cada tarea** hereda de **`PestanaBase`** y su frame tiene tres regiones
(`_construir`):

1. **ARRIBA** — **campos de entrada declarativos** (`ENTRADAS = [Campo(clave,
   etiqueta, tipo)]`): una fila por campo (label + Entry + *Examinar…*, salvo los
   de tipo `texto`). Si `ENTRADAS` es None se derivan de los atributos clásicos
   (origen [+ destino]). En Eliminar, además, la **caja de aviso** roja.
2. **MEDIO** — **opciones agrupadas en secciones `LabelFrame`** (`_seccion`),
   dentro de un **área con scroll** (Canvas): cada opción se crea con los helpers
   declarativos `_check(var, etiqueta, ayuda)` / `_combo(var, etiqueta, valores,
   ayuda)` (crean el control, lo añaden a `_bloqueables` y ponen su ayuda gris).
   Las opciones de **rendimiento** (Hilos + Modo ligero) NO están aquí: son
   comunes y viven en el monitor derecho (§6).
3. **ABAJO** — barra inferior POR tarea: botón de acción (verde; **rojo** en
   Eliminar), *Pausar*, **estado con color** (`_estado`: lima *Listo/Completado*,
   verde *Trabajando*, ámbar *Pausado/Cancelado*, rojo *Error*) y la **barra de
   progreso**.

**Flujo al pulsar Iniciar** (`_iniciar`): `_validar()` valida en el **hilo
principal** y devuelve `{"entradas": {...}, "opts": <Opciones>}` (lee ahí TODAS las
variables Tk) → `_confirmar()` (modal opcional) → arranca un **hilo** de trabajo →
`_ejecutar` **genérico** llama a `self.MOTOR.ejecutar(entradas, opts, …)` que mapea
a `motor_*.procesar(...)`. Los callbacks `log`/`progreso` vuelcan a una
`queue.Queue`; `App._bomba` (150 ms) la vacía a la ventana.

**Una tarea a la vez**: al arrancar, `App.bloquear` deshabilita `[ ← ]` y las
tareas hermanas (la activa lleva `•`); al terminar/pausar, `App.desbloquear` las
reactiva. Los selectores de rendimiento pasan por `_politica()` →
`politica_desde(hilos, ligero)` → `recursos.PoliticaHilos`. Al completar, si la
tarea declara `produce` ('archivo'/'carpeta'), `App.sugerir_entrada` rellena el
origen de la tarea que consuma ese tipo (handoff Comprimir→Descomprimir).

---

## 2. Selectores de entrada/salida (comunes)

| Selector | Tipo | Variable | Lee | Consecuencia |
|---|---|---|---|---|
| **Origen** | Entry + botón (`filedialog`) | `v_origen` (`vars_entrada["origen"]`) | `_validar` → `valor("origen")` → `rutas_validadas` | Qué se procesa. Comprimir: carpeta; Descomprimir: **archivo .zip**; Eliminar: carpeta. |
| **Destino** | Entry + botón | `v_destino` (`vars_entrada["destino"]`) | `_validar` → `valor("destino")` | Dónde se escribe. Se autocompleta (`_destino_automatico` vía `_origen_cambiado`) mientras no se edite a mano (`auto_destino`). |

- Comprimir: destino por defecto `<carpeta>_zips` (al lado del origen).
- Descomprimir: destino por defecto = carpeta del propio ZIP.
- Eliminar: **no tiene destino** (no produce salida).

Los campos son **declarativos** (`ENTRADAS = [Campo(clave, etiqueta, tipo)]`, tipo
`carpeta`/`archivo`/`carpeta_salida`/`texto`/`lista`); si no se declaran, se derivan
de `etiqueta_origen`/`tipo_origen`/`etiqueta_destino`. Botón *Examinar*:
`_examinar_campo(campo)` (abre el diálogo según el tipo). El tipo **`lista`** es un
botón que despliega un `Text` multilínea (una ruta por línea) → `valores_lista(clave)`
(usado en Combinar para "añadir más directorios").

---

## 3. Pestaña **Comprimir**

Motor: `motor_comprimir.procesar`. `_ejecutar` construye
`mcomp.Opciones(nivel, limpiar, verificar, omitir_ocultos, detallado, politica)`
y, si el modo compacto está activo, llama a `mcomp.aplicar_modo_compacto(opts)`.

Orden en la interfaz (secciones `LabelFrame`): "Opciones de compresión"
(Compresión + Modo compacto), "Filtros" (Omitir ocultos), "Manejo de archivos"
(Verificar + Borrar intermedios). **Hilos y Modo ligero NO están aquí**: son
comunes y viven en el monitor derecho (§6).

| Selector (texto) | Tipo | Variable | Def. | Mapea a | Consecuencia en el resultado |
|---|---|---|---|---|---|
| **Compresión** (Rápido/Equilibrado/Máximo) | Combobox (readonly) | `v_preset` | `Rápido (1)` | `opts.nivel` (vía `_nivel()`) | Nivel DEFLATE. `1` rápido (def.), `5` equilibrado, `9` máximo y **mucho** más lento a cambio de ~poco tamaño. Los precomprimidos (.jpg/.mp4/.zip…) van STORED igual. |
| **Modo compacto (juntar carpetas pequeñas)** | Checkbutton | `v_compacto` | `False` | `aplicar_modo_compacto()` → `agrupar_mb=8`, `agrupar_archivos=300`, `profundidad_max=0` | Empaqueta los subárboles pequeños en UN solo ZIP (`crear_agrupado`). **Mucho** más rápido en discos lentos y árboles con muchas carpetas diminutas. **Cambia la estructura**: no podrás re-extraer una subcarpeta suelta sin abrir todo el grupo. |
| **Omitir ocultos** | Checkbutton | `v_ocultos` | `False` | `opts.omitir_ocultos` | Excluye archivos del sistema o invisibles (nombres que empiezan por `.`), en la exploración y en el agrupado. El resultado NO los incluirá. |
| **Verificar ZIP ya hechos al reanudar** | Checkbutton | `v_verificar` | **`True`** | `opts.verificar` | Al **reanudar**, comprueba el CRC (`testzip`) de los ZIP ya creados y **rehace los dañados**. Reanudación más segura, algo más lenta. No afecta si no hay nada previo. |
| **Borrar ZIP intermedios al integrarlos** | Checkbutton | `v_limpiar` | **`True`** | `opts.limpiar` | Al embeber el ZIP de un hijo en su padre, borra el intermedio (`_partes/`). Menos espacio temporal; el ZIP final es autocontenido. Sin marcar, quedan los intermedios. |
| **Hilos** / **Modo ligero** *(monitor derecho, compartidos)* | Radios / Checkbutton | `App.v_hilos` / `App.v_ligero` | `Auto` / `True` | `politica.hilos` / `prioridad_baja` | Comunes a todas las tareas (§6). Paralelismo entre carpetas hermanas + prioridad baja. |
| **Registro detallado** *(monitor derecho, compartido)* | Checkbutton | `App.v_detallado` | `False` | `opts.detallado` | Una línea de log por carpeta en vez de una cada 50. Útil para seguir el detalle; más lento por el volumen de texto. |

Al terminar (`_al_terminar`): pasa el ZIP final a la pestaña Descomprimir y
muestra un aviso.

---

## 4. Pestaña **Descomprimir**

Motor: `motor_descomprimir.procesar`. `_ejecutar` construye
`mdesc.Opciones(verificar, conservar_zips, expandir_todos, detallado, politica)`.
La descompresión ya paraleliza (usa `politica.hilos` compartido, §6).

Sección "Opciones de extracción": (1) Expandir cualquier .zip, (2) Verificar CRC,
(3) Conservar. Hilos y Modo ligero están en el monitor derecho (§6).

| Selector (texto) | Tipo | Variable | Def. | Mapea a | Consecuencia |
|---|---|---|---|---|---|
| **Expandir cualquier .zip (archivos antiguos)** | Checkbutton | `v_todos` | `False` | `opts.expandir_todos` | Expande TODO `.zip`, lleve o no la marca de kakoli. Úsalo solo para archivos de versiones antiguas sin marca: si no, podría expandir `.zip` que eran datos legítimos del usuario. |
| **Verificar CRC al extraer** | Checkbutton | `v_verificar` | `False` | `opts.verificar` | Comprueba el CRC de cada ZIP antes de extraerlo (`testzip`); si está dañado, aborta ese ZIP con error. Más seguro, más lento. |
| **Conservar los .zip ya expandidos** | Checkbutton | `v_conservar` | `False` | `opts.conservar_zips` | No borra los `.zip` internos tras convertirlos en carpetas. Deja copias (más espacio); útil para inspeccionar. Sin marcar, se borran según se expanden. |
| **Hilos** / **Modo ligero** *(monitor derecho, compartidos)* | Radios / Checkbutton | `App.v_hilos` / `App.v_ligero` | `Auto` / `True` | `politica.hilos` / `prioridad_baja` | Comunes (§6). Extrae contenedores independientes en paralelo + prioridad baja. |
| **Registro detallado** *(monitor derecho, compartido)* | Checkbutton | `App.v_detallado` | `False` | `opts.detallado` | Una línea por ZIP expandido en vez de cada 50. |

`_preguntar`: si la carpeta destino ya existe y parece completa, el motor pide
confirmación con un modal en el hilo de la ventana.

---

## 5. Pestaña **Eliminar**

Motor: `motor_eliminar.procesar`. `_ejecutar` construye
`melim.Opciones(simular, detallado, contar=not sin_contar, politica)`.
El borrado es **secuencial por diseño**: usa la política compartida solo para el
**Modo ligero** (`politica.hilos` se ignora aquí).

> AVISO: el borrado es **DEFINITIVO** (no pasa por la papelera).

Sección "Seguridad": (1) Solo simular, (2) Borrar sin contar, (3) Confirmo…
Hilos/Modo ligero en el monitor derecho (§6; Hilos no afecta a Eliminar).

| Selector (texto) | Tipo | Variable | Def. | Mapea a | Consecuencia |
|---|---|---|---|---|---|
| **Solo simular (no borra nada)** | Checkbutton | `v_simular` | `False` | `opts.simular` | Enumera y cuenta sin borrar. El botón pasa a decir **"Simular"**. Seguro para comprobar antes. |
| **Borrar sin contar antes** | Checkbutton | `v_sin_contar` | `False` | `opts.contar = not v` | Salta el conteo previo (que recorre el árbol dos veces). Empieza **antes** en carpetas enormes; a cambio la barra de progreso es **aproximada** y el resumen final cuenta lo realmente borrado. |
| **Confirmo que quiero borrar…** | Checkbutton | `v_confirmo` | `False` | *(no es opción del motor)* | **Puerta de seguridad**: habilita el botón "Eliminar". `_validar` exige simular **o** confirmo; `_confirmar` muestra además un modal de confirmación. Se desmarca sola al terminar (`_al_terminar`). |
| **Modo ligero** *(monitor derecho, compartido)* | Checkbutton | `App.v_ligero` | `True` | `politica.prioridad_baja` | Baja la prioridad del proceso (§6). `App.v_hilos` no afecta a Eliminar. |
| **Registro detallado** *(monitor derecho, compartido)* | Checkbutton | `App.v_detallado` | `False` | `opts.detallado` | Una línea por carpeta visitada en vez de cada 50. |

`_actualizar_boton`: activa/desactiva y renombra el botón (Simular/Eliminar)
según las casillas. `_fin` lo reajusta al terminar.

---

## 5b. Categoría **Combinación** (Combinar / Descombinar)

Es la **primera** categoría del menú (orden Combinación / Compresión / Aplanado /
Eliminar). Funde árboles de directorios y deshace esa fusión. Motores independientes:
`motor_combinar` / `motor_descombinar`.

### Combinar (motor `motor_combinar`)

Funde varios directorios **dentro del principal** (in situ; el principal cambia).
Cada archivo del resultado se anota en un **índice** (`.kakoli_combinacion.json`)
guardado en el principal, que permite deshacer con Descombinar.

Entradas (`ENTRADAS`): **Directorio principal** (`principal`, carpeta; puede estar
vacío), **Directorio a combinar** (`secundario`, carpeta) y **Añadir más directorios**
(`mas`, tipo `lista`: botón que despliega una caja de texto, una ruta por línea).
`_validar` = `secundario` + `valores_lista("mas")`; **todas** deben existir.

| Selector | Tipo | Variable | Mapea a | Consecuencia |
|---|---|---|---|---|
| **Al coincidir** (Renombrar / Mantener / Reemplazar) | Combobox | `v_conflicto` | `opts.conflicto` | Qué hacer si un archivo coincide en ruta y nombre. **Renombrar** (def.): conserva ambos; el entrante se copia con un código de origen (`nombre_dir2.ext`). **Mantener**: conserva el del principal, omite el entrante. **Reemplazar**: gana uno por criterio; el perdedor se descarta (**IRREVERSIBLE**). |
| **Reemplazar por** (reciente/antiguo/mayor/menor) | Combobox | `v_criterio` | `opts.criterio_reemplazo` | Solo activo si "Reemplazar". Criterio para elegir el ganador. |
| **Código** (nombre carpeta / id `_d1` / personalizado) | Combobox (+Entry) | `v_codigo` / `v_codigo_texto` | `opts.modo_codigo` / `codigo_personalizado` | Sufijo que identifica el origen en los renombrados. El Entry solo se habilita con "Personalizado". |
| **Omitir ocultos** | Checkbutton | `v_ocultos` | `opts.omitir_ocultos` | Excluye archivos/carpetas que empiezan por `.`. |
| **Crear índice para poder deshacer** | Checkbutton | `v_indice` | `opts.crear_indice` | Def. **activado**. Desactivarlo: más rápido y sin espacio extra, pero el resultado **NO se podrá descombinar**. |

`_confirmar`: si la política es "Reemplazar" y/o no se crea índice, muestra un modal
de aviso (se pierden originales / no se podrá descombinar). `produce="carpeta"` y
`produce_hacia = PestanaDescombinar` → al terminar, el combinado pasa a Descombinar.

### Descombinar (motor `motor_descombinar`)

Deshace una combinación: lee el índice del directorio combinado y **reconstruye los
directorios originales** (uno por origen: principal + cada fuente), restaurando los
**nombres originales**. Los archivos descartados (mantener/reemplazar) no están en el
combinado y se informan como no recuperables.

Entradas: **Directorio combinado** (`origen`, carpeta) y **Carpeta de salida**
(`destino`, autodestino `<combinado>_descombinado`). `_validar` exige que el
combinado tenga índice legible (si no, `ValueError`). Opción **"Sobrescribir si ya
existe en el destino"** (`v_sobrescribir` → `opts.sobrescribir`).

---

## 5c. Categoría **Aplanado** (Aplanar / Desaplanar)

Tercera categoría (orden Combinación / Compresión / **Aplanado** / Eliminar). Aplana
un árbol a una sola carpeta y lo deshace. Motores independientes `motor_aplanar` /
`motor_desaplanar`. **NO usa índice**: la reconstrucción es solo por los nombres.

### Aplanar (motor `motor_aplanar`)

Copia (siempre; nunca mueve) todos los archivos a una carpeta de salida en un solo
nivel. Entradas: **Directorio a aplanar** (`origen`, carpeta) y **Carpeta de salida**
(`destino`, autodestino `<origen>_aplanado`).

| Selector | Tipo | Variable | Mapea a | Consecuencia |
|---|---|---|---|---|
| **Al aplanar** (Incluir la ruta / Solo el nombre final) | Combobox | `v_modo` | `opts.modo_nombre` (`ruta`/`final`) | **Incluir la ruta** (def.): codifica las carpetas en el nombre con el separador (`n1/n2/a.txt`→`n1-n2-a.txt`); es el único modo **desaplanable**. **Solo el nombre final**: deja `a.txt` (no se podrá desaplanar). |
| **Separador de niveles** | Entry | `v_sep` | `opts.separador` | Texto libre (uno o varios caracteres), por defecto `-`. Se **atenúa** en modo "solo nombre final". Validado con `separador_ok` (no vacío, sin `/` ni `\`). |
| **Al coincidir** (Renombrar / Mantener el primero / Reemplazar) | Combobox | `v_conflicto` | `opts.conflicto` | Colisión de nombre en el destino (frecuente en modo "final"). **Renombrar** (def.): añade la carpeta padre (`a_n2.txt`) + numérico de respaldo. **Mantener**: se queda el primero. **Reemplazar**: gana uno por criterio; el perdedor se descarta (**IRREVERSIBLE**). |
| **Reemplazar por** (reciente/antiguo/mayor/menor) | Combobox | `v_criterio` | `opts.criterio_reemplazo` | Solo activo si "Reemplazar". |
| **Omitir ocultos** | Checkbutton | `v_ocultos` | `opts.omitir_ocultos` | Excluye lo que empieza por `.`. |

`_confirmar`: avisa (modal) si la política es "Reemplazar" (descartes irrecuperables)
y/o si el modo es "Solo el nombre final" (no se podrá desaplanar). `produce="carpeta"`
y `produce_hacia = PestanaDesaplanar` → al terminar, la carpeta aplanada pasa a
Desaplanar.

### Desaplanar (motor `motor_desaplanar`)

Reconstruye el árbol **solo a partir de los nombres**, partiendo cada nombre por el
separador (último segmento = archivo, resto = carpetas). Sin índice. Entradas:
**Carpeta aplanada** (`origen`, carpeta) y **Carpeta de salida** (`destino`,
autodestino `<origen>_desaplanado`).

| Selector | Tipo | Variable | Mapea a | Consecuencia |
|---|---|---|---|---|
| **Separador de niveles** | Entry | `v_sep` | `opts.separador` | Debe **coincidir** con el usado al aplanar. Aviso (ayuda): un nombre que ya contenga ese texto creará carpetas no deseadas (ambigüedad inherente al método). |
| **Al coincidir** (Renombrar / Mantener / Reemplazar) | Combobox | `v_conflicto` | `opts.conflicto` | Por si dos nombres reconstruyen la misma ruta. Renombrar = sufijo numérico. |
| **Omitir ocultos** | Checkbutton | `v_ocultos` | `opts.omitir_ocultos` | Excluye lo que empieza por `.`. |

Anti path-traversal: cada segmento se sanea y `_destino_seguro` (comprobación léxica,
segura entre hilos) garantiza que todo queda dentro del destino.

---

## 5d. Categoría **Renombrado** (Renombrar)

Cuarta categoría (orden Combinación / Compresión / Aplanado / **Renombrado** /
Eliminar). Tarea única. Renombra archivos en bloque **sin tocar la extensión** (se
conservan también las compuestas, p. ej. `.tar.gz`): `prefijo + reemplazar(stem) +
sufijo`. Motor `motor_renombrar`. Entrada: **Carpeta** (`origen`).

| Selector | Tipo | Variable | Mapea a | Consecuencia |
|---|---|---|---|---|
| **Al inicio (prefijo)** | Entry | `v_prefijo` | `opts.prefijo` | Texto delante del nombre. |
| **Al final (sufijo)** | Entry | `v_sufijo` | `opts.sufijo` | Texto al final del nombre, ANTES de la extensión. |
| **Buscar / Reemplazar por** | Entry | `v_buscar` / `v_reemplazar` | `opts.buscar` / `opts.reemplazar` | Sustituye un fragmento del nombre. Reemplazar vacío = eliminar el fragmento. |
| **Distinguir mayúsculas** | Checkbutton | `v_sensible` | `opts.sensible_mayusculas` | Si está marcado, ‘ABC’≠‘abc’. |
| **Solo la primera coincidencia** | Checkbutton | `v_solo_primera` | `opts.solo_primera` | Sustituye solo la primera vez en cada nombre. |
| **Incluir subdirectorios** | Checkbutton | `v_recursivo` | `opts.recursivo` | Renombra también los archivos de las subcarpetas. |
| **Omitir ocultos** | Checkbutton | `v_ocultos` | `opts.omitir_ocultos` | Excluye lo que empieza por ‘.’. |
| **Al coincidir** (Numerar / Omitir) | Combobox | `v_conflicto` | `opts.conflicto` | El nuevo nombre ya existe: **Numerar** añade `_2`, `_3`… (no se pierde nada); **Omitir** deja ese archivo. |
| **Vista previa (no renombra)** | Botón | — (`_previsualizar`→`opts.simular`) | — | Ejecuta en modo `simular`: vuelca `antes → después` en la consola sin tocar el disco. |

`_validar` exige **alguna** operación (prefijo, buscar o sufijo); si no, `ValueError`.
`_confirmar`: la vista previa no pregunta; el renombrado real muestra un modal de aviso
(en bloque, **sin ‘deshacer’**; recomienda usar la vista previa antes).

---

## 6. Opciones de rendimiento — COMUNES (monitor derecho compartido)

Hilos y Modo ligero son **comunes a todas las tareas y persistentes**: viven en el
**monitor derecho**, en el panel **"Rendimiento"** justo debajo de "Equipo
detectado" (`App._construir_rendimiento`). Sus variables son de `App`
(`App.v_hilos` / `App.v_ligero`), así que **lo que elijas se mantiene** al cambiar
de tarea o de categoría. Las lee `PestanaBase._politica()` →
`politica_desde(app.v_hilos, app.v_ligero)`. Mientras una tarea trabaja, el panel se
deshabilita (no se cambia la política a mitad) y se restaura al terminar (los hilos
atenuados por hardware siguen deshabilitados). El **Modo compacto** (comprimir) NO
es de rendimiento: es una opción normal (sección "Opciones de compresión").

### 6.1 Hilos — **radios** (`tk.Radiobutton`), variable `App.v_hilos` (str)

- Valores: `Auto` (recomendado) + `1..min(núcleos_lógicos, 8)`.
- Mapea vía `politica_desde`: `Auto` → `PoliticaHilos.hilos=0` (lo decide
  `recursos.calcular_hilos` según CPU/RAM/disco/carga); un número → lo fuerza.
- **Consecuencia**: cuántas carpetas (o contenedores, al descomprimir) se
  procesan a la vez. Más hilos = más rápido en equipos capaces; en HDD o pocos
  núcleos puede ir **más lento**.
- **Atenuado por equipo (adaptación a equipo antiguo)**: `App.__init__` mide el
  perfil una vez y calcula `self.techo_hilos = recursos.techo_hilos(perfil)` (máx
  de hilos aprovechables por el hardware ESTABLE: núcleos físicos + tipo de
  disco). Los radios **por encima del techo** se muestran pero **deshabilitados y
  en cursiva gris** (no seleccionables), porque perjudicarían el rendimiento en
  ese equipo. Ejemplo real (2 núcleos físicos, HDD): techo = 1 → solo `Auto` y `1`
  elegibles. Los radios se disponen en **rejilla que se envuelve** (5 por fila) para
  caber en la columna estrecha y admitir más hilos en equipos con más núcleos. El
  panel no lleva descripciones (compacto).

### 6.2 Modo ligero — Checkbutton, `App.v_ligero`, def. `True`

- Mapea a `PoliticaHilos.prioridad_baja`.
- **Consecuencia**: baja la prioridad del proceso (BELOW_NORMAL / `nice`) para
  que el equipo siga usable mientras trabaja. Recomendado.

> **Modo compacto** (`v_compacto`, solo Comprimir) ya NO es una opción de
> rendimiento: es una opción normal (posición 2 de Comprimir). Ver §3.

---

## 7. Botones y mecanismos

| Elemento | Tipo | Función | Efecto |
|---|---|---|---|
| **Iniciar / Comprimir / Descomprimir / Eliminar / Simular** | Botón | `_iniciar` | Valida, confirma y lanza el hilo de trabajo. El texto cambia a "Continuar" si quedó pausado o con error. |
| **Pausar** | Botón | `_pausar` → `pausa` (Event) | Para de forma **ordenada** entre unidades: los workers terminan la carpeta/ZIP en curso y salen; el avance se guarda y se reanuda. |
| **Archivo `PAUSA`** | (externo) | los motores lo detectan | Crear un archivo llamado `PAUSA` en la carpeta de salida pausa el proceso (equivalente a Pausar). |
| **Registro detallado** | (ver por pestaña) | — | Cambia la verbosidad del log. |

Selector implícito de **modo automático**: si no se toca nada, todo va en `Auto`
+ modo ligero, y el log de cada tarea imprime el perfil detectado
(`Máquina: …`) y los hilos elegidos.

### 7.1 Reanudar tras cerrar la app (modal)

Si una tarea con registro de progreso quedó **a medias** (se pausó y se cerró el
programa), al pulsar *Iniciar* de nuevo con el **mismo origen y destino**,
`PestanaBase._iniciar` detecta el progreso (vía `self.MOTOR.info_reanudable(entradas,
opts)`) y muestra un modal: **Sí = Continuar** donde se quedó · **No = Empezar de
cero** · **Cancelar**. Elegir "Empezar de cero" fija `opts.reiniciar` (deshace lo ya
hecho y arranca limpio). **No** aparece al pulsar *Continuar* de una tarea pausada en
la MISMA sesión (`_reanudando_en_sesion`): ese caso continúa directo. Lo soportan las
tareas con registro JSON: **Comprimir**, **Aplanar** y **Desaplanar** (Combinar reanuda
en silencio, sin modal; Descomprimir/Descombinar/Eliminar reanudan por sistema de
archivos). El registro se borra al completar, así que el modal nunca sale sobre una
tarea ya terminada. Ver `roadmap_reanudar.md`.

---

## 8. Opciones de los motores NO expuestas en la GUI (solo consola)

Existen en las `Opciones` de cada motor pero no tienen selector en la ventana
(se usan por línea de comandos):

- **Comprimir**: `max_dirs` (parar tras N carpetas), `preguntar_cada`,
  `reiniciar` (empezar de cero), `seguir_enlaces`, `estricto` (abortar al primer
  error). Y los ajustes finos de `PoliticaHilos`: `hilos_max`, `ram_por_hilo_mb`,
  `ram_reservada_mb`, `ram_minima_paralelo_mb`, `throttling`.
- **Descomprimir**: `sobrescribir` (borrar destino previo), `max_zips`.
- **Eliminar**: `estricto`, `max_entradas`.

Para tocarlos: `python -m motores.motor_comprimir CARPETA [opciones]` (y análogos), o
editar `PoliticaHilos` en el código. Ver `--help` de cada motor y `ARQUITECTURA.md`.
