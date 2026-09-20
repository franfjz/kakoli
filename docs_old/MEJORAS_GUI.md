# Mejoras de diseño y usabilidad de la interfaz

Análisis exhaustivo de la GUI de kakoli (ventana principal + pestañas de tarea).
Solo diagnóstico y propuestas: **no se ha tocado código**. Fecha: 2026-09-18.

Ámbito revisado: `gui/` (app, tema, pestana_base, componentes, campo, contexto,
constantes, ayuda) y las 8 pestañas de `tasks/<t>/pestana.py`.

---

## 0. Cómo está construida hoy (contexto)

- **Ventana única maximizada** (`state("zoomed")`), sin barra de menú. Layout de dos
  columnas por `grid`: izquierda navegador (barra + área de tarea, expande), derecha
  monitor compartido de ancho fijo (`minsize=280`).
- **Navegación en dos niveles**: portada de tarjetas de categoría → pestañas-botón de
  las tareas de esa categoría, con `[ ← ]` para volver. Una tarjeta final abre la Ayuda.
- **Monitor derecho compartido**: “Equipo detectado”, “Rendimiento” (Hilos + Modo
  ligero), consola (`tk.Text` con tags de color) e “info” (marca/versión/enlaces).
- **Una tarea a la vez**: `bloquear`/`desbloquear` deshabilita navegación, pestañas
  hermanas y controles de rendimiento mientras hay trabajo.
- **Bucle de eventos**: un único `after(150ms)` (`_bomba`) drena las colas de **todas**
  las pestañas y repinta progreso/consola.
- **Pestañas declarativas** (`PestanaBase`): campos de entrada (`Campo`), opciones por
  secciones (`_seccion`/`_check`/`_combo`/`_entry`), Iniciar/Pausar/Cancelar, barra de
  progreso, modal de reanudación y handoff entre gemelas.
- **Tema centralizado** (`tema.py`): un solo sitio con paleta retro-terminal (verde
  sobre fondo oscuro), fuente Space Mono y estilos ttk/tk.

Lo que ya está bien y conviene conservar: la centralización del tema, el contrato
`ContextoApp`, el modelo declarativo de opciones, el aviso rojo destacado de Eliminar,
el recorte del log por rendimiento y el batching de líneas de consola.

---

## 1. Rendimiento de la interfaz (código)

### 1.1 · La “bomba” de 150 ms no descansa nunca — **[alto impacto, esfuerzo bajo]**
`App._bomba` se re-arma cada 150 ms de forma indefinida y, en cada disparo, recorre las
**8 pestañas** llamando a `procesar_cola()` aunque no haya ninguna tarea trabajando. Es
un despertar constante del bucle de eventos que impide al proceso quedarse inactivo —
justo lo contrario del objetivo “buen ciudadano / batería” del portátil de referencia.
**Propuesta:** arrancar la bomba solo al `bloquear` (hay trabajo) y detenerla (`after_cancel`)
al `desbloquear` cuando ninguna pestaña está `ocupada()`. En reposo, 0 timers.

### 1.2 · Se instancian las 8 pestañas al arrancar — **[medio, medio]**
`self.pestanas = tuple(desc.clase(area, self) for desc in ...)` construye **todos** los
widgets de las 8 tareas en el arranque, aunque el usuario abra una sola. En el equipo
lento objetivo esto alarga el primer pintado. **Propuesta:** instanciación perezosa
(crear la pestaña la primera vez que se muestra). Requiere que `_bomba` y `_cerrar`
iteren solo sobre las ya creadas (encaja con 1.1: solo hay colas activas de la que
trabaja).

### 1.3 · `_ajustar_ayudas` / `_ajustar_ayuda_wrap` sin debounce — **[bajo, bajo]**
Cada `<Configure>` del canvas recalcula el `wraplength` de **todas** las labels de ayuda
(y de todos los párrafos de la Ayuda). En un arrastre de redimensionado se dispara en
ráfaga → posible “jank”. **Propuesta:** debouncing con `after_cancel`/`after(~80ms)`.

### 1.4 · `_pintar_barra` destruye y recrea todos los botones en cada navegación — **[bajo, medio]**
Cada `_seleccionar`/`_ir_menu` hace `w.destroy()` de la barra y reconstruye los botones.
Es barato con pocas tareas, pero innecesario. **Propuesta (opcional):** reutilizar los
botones y solo cambiar estilo/estado. Baja prioridad.

### 1.5 · `bind_all("<MouseWheel>")` / `unbind_all` global — **[bajo, bajo]**
`MarcoDesplazable` engancha la rueda con `bind_all` al entrar y hace `unbind_all` al
salir, lo que **borra cualquier** binding global de rueda (no solo el suyo). Con tres
áreas desplazables coexistiendo es frágil. **Propuesta:** usar un binding con `funcid`
propio y `unbind` selectivo, o un único gestor de rueda centralizado.

### 1.6 · Sin `after_cancel` de la bomba al cerrar — **[bajo, bajo]**
Al `destroy()` puede quedar un `after` pendiente. Tk suele tolerarlo, pero cancelarlo
explícitamente en `_cerrar` es más limpio (y necesario si se adopta 1.1).

---

## 2. Persistencia de estado y preferencias — **[alto impacto, esfuerzo medio]**

Hoy **nada persiste entre sesiones**: al reabrir se pierden Hilos, Modo ligero, Registro
detallado, la última categoría/tarea abierta, las opciones de cada tarea y el tamaño/
posición de la ventana (siempre abre maximizada). Para una herramienta de uso repetido
esto es fricción constante.

- **2.1 Config en disco** (`%APPDATA%/kakoli/config.json`, atómico como `core.json_util`):
  guardar rendimiento (Hilos/ligero/detallado), última tarea por categoría y geometría.
- **2.2 Recordar la última carpeta** usada en los diálogos `filedialog` (`initialdir`),
  por tarea o global. Hoy cada “Examinar…” abre en el directorio por defecto del SO.
- **2.3 Recordar geometría** (tamaño/posición) en vez de forzar maximizado siempre.
- **2.4 (Opcional) recordar opciones por tarea** (nivel de compresión, conflicto, etc.).

Todo esto es agnóstico del dominio y podría vivir en `gui/` + un pequeño módulo de
preferencias, sin tocar `core/` ni los motores.

---

## 3. Feedback y progreso

### 3.1 · Barra “muerta” durante fases sin total — **[alto, bajo]**
Al explorar el árbol o contar antes de empezar, `total` es 0 y la barra queda en 0 %
con “Trabajando…”; el usuario no sabe si está colgado. **Propuesta:** poner la barra en
modo `indeterminate` (marquesina) mientras no haya total, y pasar a determinado al
conocerlo.

### 3.2 · Sin ETA, velocidad ni porcentaje numérico — **[medio, medio]**
El estado muestra `hechas/total — etiqueta`, pero no % ni tiempo restante estimado, que
es lo más útil en tareas largas. **Propuesta:** añadir `NN %` y un ETA sencillo
(media móvil de unidades/seg × restantes). El `Resultado` ya trae `segundos`; el cálculo
en vivo puede hacerse en `procesar_cola`.

### 3.3 · Los “Completado” son modales que interrumpen — **[medio, bajo]**
Comprimir/Descomprimir/Eliminar abren `showinfo` al terminar; el usuario debe cerrarlo
cada vez. Además es **inconsistente** (Combinar/Aplanar/Desaplanar/Descombinar/Renombrar
no muestran nada). **Propuesta:** unificar. Preferible un remate no modal en el estado/
consola (“Completado · ruta”) con un botón **“Abrir carpeta”**; reservar el modal solo
para errores y avisos destructivos.

### 3.4 · No hay “Abrir carpeta de resultado” — **[medio, bajo]**
Tras completar solo se muestra la ruta como texto. **Propuesta:** botón/enlace “Abrir
carpeta” (`os.startfile` en Windows) junto al estado o en el remate final. Ahorra
copiar-pegar la ruta en el explorador.

### 3.5 · Handoff invisible — **[medio, bajo]**
Cuando Comprimir termina, `sugerir_entrada` rellena el origen de Descomprimir, pero el
usuario no lo percibe. **Propuesta:** avisar (“Listo para Descomprimir →”, resaltar la
pestaña destino o un enlace directo) para que el flujo gemelo sea descubrible.

### 3.6 · Consola sin acciones — **[medio, bajo]**
El log compartido no se puede **limpiar**, **copiar** ni **guardar**, y al estar
`state="disabled"` la selección con ratón es incómoda. **Propuesta:** botones “Limpiar”,
“Copiar” y “Guardar registro…”, y un menú contextual. Añadir además un *empty state*
(“Aquí aparecerá el registro de la tarea”) cuando está vacía.

---

## 4. Navegación e interacción

### 4.1 · Sin navegación por teclado ni atajos — **[alto, medio]**
Todo es ratón. No hay `Enter` = Iniciar, `Esc` = Cancelar/Volver, `Tab` con orden y foco
visible claro, ni aceleradores. **Propuesta:** definir atajos por pestaña (Iniciar/
Pausar/Cancelar), `Esc` para volver a la portada (si no está bloqueado) y asegurar un
anillo de foco visible. Mejora productividad y accesibilidad.

### 4.2 · Divisor navegador/monitor no ajustable — **[medio, medio]**
El ancho del monitor es fijo (`minsize=280`). En pantallas pequeñas roba espacio a las
opciones; en grandes desaprovecha. **Propuesta:** `ttk.PanedWindow` con “sash”
arrastrable (y recordar la posición, ver §2). En ventanas muy estrechas, permitir
colapsar el monitor.

### 4.3 · Drag & drop de carpetas/archivos — **[medio, alto]**
Los campos de ruta solo aceptan “Examinar…” o pegado manual. Arrastrar desde el
explorador es lo natural en una herramienta de archivos. **Nota:** el DnD nativo en
Tkinter requiere `tkinterdnd2` (dependencia externa), lo que choca con la política de
“sin dependencias”. Dejar como opcional/evaluación.

### 4.4 · `[ ← ]` poco descubrible — **[bajo, bajo]**
El corchete retro es coherente con la estética, pero “←” a secas no dice “volver a
categorías”. **Propuesta:** tooltip “Volver” (ver §5.3) o texto “← Categorías”.

### 4.5 · Rutas largas ilegibles en los `Entry` — **[bajo, bajo]**
Una ruta larga muestra solo el principio. **Propuesta:** auto-scroll al final al fijar el
valor (`entry.xview_moveto(1)`) y/o tooltip con la ruta completa.

---

## 5. Accesibilidad y legibilidad

### 5.1 · Tamaños de fuente fijos y pequeños — **[medio, medio]**
La ayuda gris usa 8 pt (`peque`) y el resto 10 pt, en píxeles fijos. El contraste de gris
(`#9CA3AF`) sobre panel oscuro pasa AA, pero **8 pt es incómodo** y no hay forma de
agrandar. **Propuesta:** subir la ayuda a 9 pt como mínimo y/o exponer un ajuste de
escala de texto.

### 5.2 · Sin conciencia de DPI/escala — **[medio, medio]**
En pantallas 4K/HiDPI la app puede verse minúscula (tamaños en píxeles fijos, sin
`tk scaling` ni DPI-awareness). **Propuesta:** declarar DPI-awareness en Windows y/o
ajustar `tk.call('tk','scaling', factor)` según el monitor.

### 5.3 · No hay tooltips en ningún control — **[medio, medio]**
Toda la ayuda va siempre visible bajo cada opción, lo que alarga mucho el panel (obliga a
hacer scroll) y añade ruido. Controles como ☕, `←` o los radios de hilos atenuados no
explican su estado. **Propuesta:** un componente `Tooltip` reutilizable (en
`gui/componentes.py`); mover parte de la ayuda extensa a tooltip “?” bajo demanda,
dejando visible solo lo esencial. Reduce longitud del panel y mejora el escaneo.

### 5.4 · Radios de hilos atenuados sin explicación inline — **[bajo, bajo]**
Se muestran en cursiva/gris, pero el porqué (“tu equipo no aprovecha tantos hilos”) solo
está en la Ayuda. **Propuesta:** tooltip explicativo en los deshabilitados.

---

## 6. Diálogos y confirmaciones

### 6.1 · El modal de reanudación es confuso — **[medio, medio]**
`askyesnocancel` muestra botones nativos **Sí / No / Cancelar** y el texto tiene que
aclarar “Sí = Continuar · No = Empezar de cero · Cancelar = no hacer nada”. El usuario lee
el botón, no la leyenda. **Propuesta:** un diálogo propio con botones etiquetados
literalmente (“Continuar”, “Empezar de cero”, “Cancelar”). Encaja con la estética del
tema y elimina la ambigüedad.

### 6.2 · Confirmaciones destructivas — **[bajo, —]** (ya bien resueltas)
Eliminar (casilla “Confirmo…” + botón rojo + caja de aviso + doble confirmación),
Combinar/Aplanar (avisos de irreversibilidad con `default="no"`) y Renombrar (recomienda
Vista previa) están **bien**. Mantener el patrón y, si acaso, unificar el tono del texto.

---

## 7. Consistencia visual y pulido

- **7.1 Iconografía de categorías/tareas** — **[bajo, medio]**: añadir un glifo por
  categoría/tarea ayudaría al escaneo visual (hoy todo es texto). Puede hacerse con
  caracteres/emoji para no romper la política de dependencias.
- **7.2 Enlaces placeholder** — **[bajo, bajo]**: `URL_CAFE = "buymeacoffee.com/franfjz"`
  **no lleva esquema** → `webbrowser.open` puede no abrirlo bien; `URL_AUTOR` está marcado
  “a modificar”. Fijar ambos antes de publicar y anteponer `https://`.
- **7.3 Tema claro / alternativo** — **[bajo, medio]**: solo hay tema oscuro. Como todo el
  color está centralizado en `tema.py`, ofrecer un tema claro sería factible y de bajo
  riesgo (útil para accesibilidad y preferencia personal).
- **7.4 Empty state de la portada/consola** — **[bajo, bajo]**: pequeños textos guía donde
  hoy hay vacío.
- **7.5 Affordance de las tarjetas** — **[bajo, bajo]**: las tarjetas de categoría solo
  señalan “clic” con cursor y borde en hover; un “›” a la derecha reforzaría que son
  navegables.

---

## 8. Internacionalización (nota, no urgente)

Todos los textos están embebidos en español y dispersos por `gui/`, `tasks/*/pestana.py`
y `tasks/*/ayuda.py`. Si en algún momento se quiere i18n, convendría centralizar los
literales. **No** es prioritario; se anota para tenerlo en el radar.

---

## 9. Resumen priorizado

**Empezar por aquí (impacto alto / esfuerzo bajo-medio):**
1. §1.1 Pausar la bomba de 150 ms en reposo (batería + CPU).
2. §2 Persistencia de preferencias y última carpeta/tarea/geometría.
3. §3.1 Barra `indeterminate` en fases sin total.
4. §3.3–3.4 Unificar el remate final (no modal) + “Abrir carpeta”.
5. §4.1 Atajos de teclado y foco visible.

**Segunda ola (buen retorno, algo más de trabajo):**
6. §1.2 Instanciación perezosa de pestañas (arranque).
7. §3.2 ETA + porcentaje.
8. §4.2 Divisor ajustable (PanedWindow).
9. §5.3 Tooltips + acortar el panel de opciones.
10. §6.1 Diálogo de reanudación con botones etiquetados.

**Pulido / a futuro:**
11. §5.1–5.2 Tamaños de fuente y DPI.
12. §3.6 Acciones de consola (limpiar/copiar/guardar).
13. §7 Iconografía, enlaces reales, tema claro, empty states.
14. §8 i18n.

---

## 10. Notas de método

- Prioridades expresadas como **impacto × esfuerzo** (estimación); conviene validar con
  uso real en el portátil de referencia (2 núcleos/HDD) que cita `ARQUITECTURA.md §10`.
- Casi todo cabe dentro de `gui/` respetando las fronteras (`tests/test_fronteras.py`):
  la persistencia y los tooltips son piezas nuevas de `gui/`; nada exige tocar `core/`
  ni los motores.
- Antes de implementar cada bloque, decidir si merece un test en `tests/gui/`.
</content>
</invoke>
