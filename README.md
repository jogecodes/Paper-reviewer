# Comparación local del paper AutoCUSUM

Abre [comparador.html](comparador.html) en el navegador. Es un único archivo con todo incluido y funciona sin servidor ni conexión de red. Si el workspace es remoto, descarga o copia ese archivo a tu equipo y ábrelo allí.

El texto completo y los resaltados están escritos directamente en el HTML; JavaScript solo activa los dos controles. El generador actualiza únicamente `comparador.html`, con la versión en el título de la pestaña; no crea copias por revisión. Una copia descargada no recibe los cambios hechos después en el workspace remoto: hay que descargar la nueva versión.

La dirección habitual es `http://127.0.0.1:3000/papers/paper-review/comparador.html?vscode-livepreview=true`. No crear archivos ni enlaces secundarios por revisión.

El generador solo guarda `comparador.html`; no abre ni enfoca pestañas de VS Code. Por petición de Jorge, las actualizaciones se revisan refrescando manualmente la misma URL. No reabrir automáticamente el archivo para forzar la actualización de Live Preview.

El visor usa `data-server-no-reload`, la opción de Live Preview que bloquea las recargas automáticas de esta página para evitar parpadeos. Después de actualizar el texto, refrescar manualmente la misma URL. Los controles de sincronización y marcado siguen funcionando sin recargar.

Si lo abres con **Live Preview** de VS Code, sigue interviniendo el servidor de esa extensión. El workspace configura el puerto inicial 3000, actualización de archivos guardados y conservación del servidor al cerrar la vista. Live Preview puede elegir otro puerto si el inicial está ocupado. Para recuperar una pestaña bloqueada, ciérrala y vuelve a abrir `comparador.html` desde **Live Preview: Show Preview**, en lugar de reutilizar una URL antigua.

El manuscrito original está a la izquierda y el mismo paper con las propuestas está a la derecha. Los párrafos cambiados aparecen resaltados. [index.html](index.html) es la versión con archivos separados para servir por HTTP.

La leyenda superior distingue tres estados con los mismos colores en ambas columnas: verde para **Aprobado**, ámbar para **En revisión** y el fondo habitual para **Sin revisar**. Los párrafos aprobados se muestran sin marcas de palabras. El estado aprobado registra que la revisión de ese párrafo está terminada; no modifica el original ni aplica la propuesta a las fuentes LaTeX. Las referencias nuevas conservan el fondo habitual mientras no se estén revisando.

El fragmento operativo y el cierre se guardan en [operational-paragraph.tex](operational-paragraph.tex). En la propuesta, la descripción de dificultades operativas se une al párrafo sobre supervisión y robustez. El párrafo final comienza con «A practical decision rule must therefore balance…», incluye la restricción de calibración y el beneficio de evitar anotación, y termina en «An open challenge remains…», antes de «Sequential Evidence Accumulation for Robust Thresholding». El hueco correspondiente al cierre en el original permite mantener la sincronización sin añadir texto al manuscrito original.

Solo hay dos controles:

- **Sincronizar** vincula el desplazamiento de ambos papers.
- **Marcar palabras** resalta en rojo las palabras retiradas del original y en azul las añadidas a la propuesta, sin tachado. Empieza activado y solo afecta a las ediciones pendientes; conserva las viñetas y los títulos de las listas.

A su lado, una barra de progreso y un porcentaje muestran la posición de lectura del paper que se está desplazando. Funcionan también cuando la sincronización está desactivada.

Al cargar, ambos documentos centran su bloque en revisión cuando cabe en la ventana. Si el bloque es demasiado alto, muestran su inicio; al principio o al final del documento se respeta el límite de desplazamiento. Un enlace con un fragmento válido conserva ese destino explícito. Después se puede desplazar la página libremente.

Las decisiones y comentarios se hacen en el chat. La vista no guarda decisiones ni modifica el manuscrito. Se muestran las propuestas incluidas en `review-data.js`, sin cargar revisiones anteriores del navegador.

Las referencias nuevas de una propuesta aparecen al final de la bibliografía de la columna derecha; la columna original conserva sus referencias. La numeración original se mantiene durante esta revisión y se recalculará al aplicar y compilar las modificaciones aceptadas.

Para servirlo por HTTP si hace falta:

```bash
python3 /app/papers/paper-review/server.py
```

Abre la dirección desde el mismo equipo del servidor. En un entorno remoto debes reenviar el puerto 8765 en la pestaña Puertos de VS Code y usar la dirección local que muestre; el `127.0.0.1` del navegador no apunta directamente al contenedor remoto.

La composición es aproximada; las fórmulas se representan de forma simplificada. Para regenerar el contenido desde las fuentes, ejecuta `python3 -I /app/papers/paper-review/build_review.py` y después `python3 -I /app/papers/paper-review/make_standalone.py`.

## Historial local de revisión

`/app/papers/paper-review` y `/app/papers/AutoCUSUM_v2` son repositorios Git independientes. El primero conserva los borradores, los estados aprobados y pendientes, el código del visor, sus imágenes y el único `comparador.html`. El segundo conserva el historial del manuscrito, la bibliografía y los documentos de `revision/`. Los logs, los PID y las cachés del visor quedan fuera del historial.

Los checkpoints deben describir los cambios y distinguir texto aprobado de propuestas pendientes. Una aprobación en verde no aplica automáticamente el texto al manuscrito. Las decisiones detalladas permanecen en `../AutoCUSUM_v2/revision/notas_redaccion.md`. Los cambios del visor y sus borradores se reconstruyen con los generadores anteriores, conservando las dos carpetas como hermanas.

Para consultar el estado y los últimos checkpoints:

```bash
git -C /app/papers/paper-review status --short
git -C /app/papers/paper-review log -5 --oneline
git -C /app/papers/AutoCUSUM_v2 status --short
git -C /app/papers/AutoCUSUM_v2 log -5 --oneline
```

Este flujo guarda commits locales; no publica ni ejecuta `push`.
