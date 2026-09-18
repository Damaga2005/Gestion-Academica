# Gestión Académica GREELEC — Funcionalidades

App local (Flask + SQLite) para llevar el seguimiento completo del grado GREELEC
(Ingeniería Electrónica de Telecomunicación, UPC): asignaturas, documentos,
evaluación, calendario, horario, repaso espaciado y copias de seguridad. Corre como
servidor web local (`python app.py`) o como aplicación de escritorio empaquetada
(`GestionAcademicaGREELEC.exe`, PyWebview + PyInstaller).

Este documento describe **qué hace la app**, no cómo está programada (para eso,
`README.md` y los comentarios del código).

---

## 1. Estructura académica

- **Años (1º-4º) y cuatrimestres (1º-8º)**, cada uno con un estado: `superado`,
  `actual` o `pendiente`.
- **Asignaturas** dentro de cada cuatrimestre, con:
  - Nombre, siglas (código corto, único), créditos ECTS, tipo (`obligatoria` /
    `optativa`) y estado (`superada`, `cursando`, `pendiente`, `no_superada`,
    `no_elegida`).
  - **Prerrequisitos**: relación entre asignaturas; la ficha muestra si están
    cumplidos (todas superadas) o no.
  - **Notas rápidas**: cuadro de texto libre con autoguardado, para apuntes sueltos
    sobre la asignatura.
  - **Nota final**: se puede colgar directamente a mano (por si la asignatura no
    tiene un desglose de evaluación claro) o queda determinada por el esquema de
    evaluación aplicable (ver más abajo).
- **Catálogo de optativas**: por cuatrimestre, lista de optativas disponibles
  (`no_elegida`) para elegir; al elegir una pasa a `cursando`/`pendiente` y se
  puede "quitar la elección" para devolverla al catálogo (o borrarla del todo si
  se creó a mano).

## 2. Profesorado

Cada asignatura puede tener **varios profesores** (no solo uno), útil cuando
teoría y laboratorio los imparte gente distinta:
- Nombre, rol/grupos (texto libre, p. ej. "Responsable (grupos 11, 12, 13)"),
  correo, despacho y enlace al aula virtual.
- Añadir, **editar en línea** y eliminar cada profesor desde la ficha de la
  asignatura.
- Si hay correo o aula virtual, aparecen botones directos de "Enviar email" y
  "Abrir aula virtual".

## 3. Evaluación

- **Componentes de evaluación**: nombre, tipo (`teoria`, `parcial`,
  `examen_final`, `laboratorio`, `otro`), peso (%) y nota (opcional).
- **Varios esquemas de evaluación por asignatura** (p. ej. "Con examen parcial"
  vs. "Solo examen final", el caso típico UPC de nota = máximo entre evaluación
  continua y fórmula alternativa): cada esquema es una lista de componentes
  independiente, y la app calcula automáticamente cuál de los esquemas es el
  "aplicado" (el de mejor media ponderada entre los que ya tienen nota).
- Para cada esquema: % evaluado, media ponderada actual, y una **calculadora de
  "¿qué nota necesito?"** que dice qué nota hace falta sacar en el peso restante
  para llegar a un objetivo.
- **Bloques de evaluación** (nota jerárquica): un esquema puede tener bloques
  cuyo peso se expresa sobre la nota final (p. ej. *Laboratorio 40%*) y cuya
  nota se calcula sola como media ponderada de sus propios componentes
  (*Prácticas 25% + P4 37,5% + Control 37,5%*). Un nivel de anidamiento; el
  resto de la app (calculadora, comparación de esquemas, estado de notas) los
  trata como un componente más.
- **Editar y reordenar**: el nombre y el peso de cada componente y bloque se
  editan con ✎ y se reordenan con ▲▼ (dentro de su bloque o del esquema).
  Si los pesos de un esquema o bloque no suman 100% aparece un aviso.
- **Nota mínima por componente**: p. ej. un 4 en el examen final. Si la nota
  queda por debajo, la fila lo marca y la asignatura, ya evaluada del todo,
  cuenta como suspendida aunque la media ponderada llegue a 5. Una nota final
  puesta a mano ignora los mínimos.
- **Duplicar un esquema**: copia bloques, componentes y pesos (con mínimos) sin
  las notas, para probar una fórmula alternativa partiendo de la actual.
- **Importar de la guía docente**: desde un PDF de guía docente ya subido se
  proponen profesores y esquemas (revisables antes de guardar). Una variable
  con definición propia en la fórmula (p. ej. `Laboratorio = 0.5*A + 0.5*B`)
  se propone como bloque.
- **Nota final directa**: cuando una asignatura no tiene un desglose de
  porcentajes claro (rúbricas de proyecto, TFG...), se puede escribir la nota
  final tal cual en el resumen de la asignatura, sin pasar por componentes.
- **Progreso** de la asignatura en el dashboard/ficha: % del peso total que ya
  tiene nota puesta.

## 4. Documentos

- **Subida de archivos** por asignatura (PDF, Office, imágenes, texto, zip...),
  con validación de tipo/tamaño y comprobación de que no sea un ejecutable
  disfrazado.
- **Organización jerárquica** en 4 categorías fijas por asignatura: *Teoría*,
  *Exámenes*, *Laboratorios*, *Otros*. Dentro de cada categoría se pueden crear
  **subgrupos libres** (p. ej. "Tema 3", "Práctica 5") para ordenar más; un
  documento sin subgrupo queda en "Sin clasificar" dentro de su categoría.
  Los documentos y subgrupos se pueden **mover** entre categorías/subgrupos
  (drag & drop en la interfaz).
- **Visor integrado de PDF** (pdf.js) con recuerdo de la última página vista.
- **Marcadores** dentro de un PDF (número de página + título), para volver
  rápido a un punto concreto.
- **Selección y copia de texto** en el PDF como en cualquier lector: al
  seleccionar (o al hacer clic derecho sobre la selección) aparece una barra
  flotante con **Copiar**, **Resaltar**, **Subrayar**, **Tachar** y **Nota**.
- **Anotaciones persistentes** por documento, en seis colores. Se guardan con
  coordenadas relativas a la página, así que se mantienen en su sitio con
  cualquier zoom. Al pulsar sobre una se puede cambiarle el color, escribirle un
  comentario, copiar su texto o eliminarla. El panel lateral del visor lista
  todas las anotaciones del documento con acceso directo a su página.
- **Etiquetas libres** por documento, con selector que sugiere las ya usadas.
- **Indexado de texto de PDFs**: al subir un PDF se extrae el texto de cada
  página (si es texto real, no un escaneado) para que el buscador global
  encuentre contenido *dentro* de los documentos, no solo por nombre.
- Vista en **lista o en cuadrícula**, con navegación tipo explorador de
  carpetas (categoría → subgrupo → documentos).

## 5. Recursos externos

Por asignatura, lista libre de enlaces a plataformas externas (Wuolah, Studocu,
Academia, Drive, GitHub, u "Otro"), cada uno con nombre y URL. Sirve para tener
a mano los apuntes/exámenes de la comunidad sin salir de la app.

## 6. Calendario académico

- **Tareas/eventos**: examen parcial, examen final, reevaluación, entrega,
  tarea general, tutoría o evento puntual. Cada uno con fecha, hora de
  inicio/fin, aula, ubicación, descripción, prioridad (alta/media/baja),
  recordatorio (días de aviso), enlace relacionado y si está completada.
- Vista de **calendario mensual** con las tareas de cada día.
- **Detección de conflictos de horario**: al crear una tarea o una clase, avisa
  si se solapa con otra tarea o con una clase recurrente del horario.
- **Exportación a `.ics`**: una tarea suelta, una serie de horario, todo el
  horario, o el calendario completo (tareas + horario) — importable en Google
  Calendar, Outlook, etc.
- **Importación desde `.ics`** (p. ej. el calendario exportado de Atenea/Moodle):
  se analiza el archivo y se propone cada evento con su hora (convertida a
  hora peninsular), tipo (entrega o tarea) y la asignatura que más se parece
  al nombre del curso. Se revisa y se marca qué importar; las que ya existen
  (mismo título y fecha) se ignoran. Un campo "avisar N días antes" se aplica
  a todas las importadas.
- **Recordatorio por tarea**: los días de aviso de cada tarea mandan sobre el
  ajuste general al decidir cuándo aparece en la campanita.
- **Repetir cada semana**: al crear una tarea se puede pedir que se repita
  hasta 52 semanas más (una tarea normal por semana; no vale para exámenes).
- **Imprimir**: botón 🖨️ que imprime la vista activa (mensual, semanal o
  agenda) en apaisado, negro sobre blanco y sin menús.

## 7. Horario semanal

- **Series recurrentes de clase** (teoría, problemas, laboratorio, seminario):
  día de la semana, hora de inicio/fin, aula, rango de fechas de vigencia,
  cada semana o quincenal, y notas. Una sola fila representa toda la serie
  (no una copia por sesión); las fechas concretas de cada clase se calculan
  al vuelo.
- Vista semanal tipo cuadrícula lunes-viernes.
- Comparte la misma detección de conflictos que el calendario.
- Botón 🖨️ para imprimir el horario (apaisado, negro sobre blanco).

## 8. Línea de tiempo

Vista Gantt de todo el cuatrimestre "actual": una fila por asignatura, con
una barra para el rango de sus clases (horario) y un marcador por cada
examen/entrega. Línea vertical marcando el día de hoy. Complementa al
calendario mes a mes con una vista de todo el cuatrimestre de un vistazo.

## 9. Repaso espaciado

- **Conceptos** libres por asignatura (temas, definiciones, lo que se quiera
  repasar), con 3 niveles: *no visto*, *flojo*, *dominado*.
- Al subir o bajar de nivel un concepto, se recalcula su próxima fecha de
  repaso (repetición espaciada simplificada: 0 / 3 / 18 días según el nivel).
- Pantalla **"Repaso de hoy"**: lista solo los conceptos cuya fecha de repaso
  ya ha llegado.

## 10. Hitos

Lista libre de certificaciones, proyectos personales u objetivos fuera del
plan de estudios, cada uno con nombre, estado (pendiente/en progreso/hecho) y
fecha opcional.

## 11. Espacios de Estudio

Cada examen/entrega del calendario puede tener su propio **Espacio de Estudio**:
una carpeta de preparación que agrupa **referencias** (nunca copias) a
documentos ya subidos, organizadas en secciones (Material destacado, Exámenes
de años anteriores, Teoría, Ejercicios, Laboratorio), más una checklist de
tareas propia.

- Se crea **solo** al programar un examen (parcial, final o recuperación) en
  el calendario, sin ningún paso aparte; y se borra en cascada si se borra el
  examen.
- Cada documento referenciado se puede marcar como leído/destacado sin que
  eso afecte al documento en sí ni a otros espacios que también lo referencien.
- **Modo examen**: pantalla resumida del día del examen — cuenta atrás,
  hora/aula/ubicación, solo el material destacado y la checklist de tareas,
  sin el resto de secciones. Incluye una **chuleta imprimible** (botón 🖨️) con
  estilos propios para llevarla en papel.

## 12. Racha de estudio

Contador de días consecutivos con actividad real (leer un documento,
completar una tarea, subir/bajar un concepto en repaso): badge 🔥 en el
Dashboard con la racha actual y, en el tooltip, el récord histórico. Al
igualar o superar el récord, aviso nativo de Windows al arrancar.

**Temporizador de estudio**: sección del Resumen con cuenta atrás (25 min por
defecto, configurable), asignatura opcional, pausa/reanudar y "Terminar y
guardar". Cada sesión guardada cuenta como día de estudio para la racha y se
suma a un resumen de minutos de hoy y de la semana, con las asignaturas que
más han sumado. Si sales de la página con el reloj en marcha, esa sesión no
se guarda (el navegador avisa antes).

## 13. Notas al vuelo

Bloc de notas accesible desde cualquier página (icono ✏️ en la cabecera, o
atajo de teclado **n**): para apuntar algo sin perder de vista lo que se
está mirando ni tener que crear una tarea formal para ello. Buscable desde
el buscador global. Nombre distinto de las "Notas rápidas" por asignatura
(sección 1): son dos cosas distintas.

## 14. Notificaciones

- **Campanita** en la cabecera de cada página: lista los avisos activos
  (examen/entrega inminente o atrasada, asignatura "cursando" sin actividad
  reciente) con acceso directo a cada uno.
- El **número de avisos pendientes** aparece también en el título de la
  pestaña del navegador (p. ej. "(2) Resumen · GREELEC").
- **Aviso nativo de Windows** al arrancar la app, solo con lo urgente de
  verdad (nivel rojo), para no repetir lo que ya se ve en la campanita.
- Un examen ya pasado sin marcar como completado se autocompleta solo (no
  puede quedar "atrasado": ya ocurrió).
- Cada aviso de tarea se puede **marcar como hecha** (✓, cuenta para la racha)
  o **posponer un día** (⏭; si estaba atrasada pasa a mañana) sin salir de la
  campanita. La ventana de aviso de cada tarea es su propio recordatorio, y
  si no tiene, el ajuste general.

## 15. Dashboard (Resumen)

- **Progreso del grado**: ECTS aprobados sobre el total, desglosado en
  obligatorias / optativas / TFG.
- **Media del curso** y desglose de asignaturas aprobadas/suspendidas/
  pendientes de evaluar, con la **media simple**, la **media ponderada por
  ECTS** (como la nota media del expediente) y la **media de cada
  cuatrimestre**.
- **Objetivo de media**: se fija una nota objetivo (0-10) y la app calcula qué
  media hace falta en las ECTS que aún no tienen nota (o avisa de que ya está
  asegurado o de que es inalcanzable).
- **Temporizador de estudio** (ver sección 12).
- **Esta semana**: horario + tareas de los próximos 7 días en una sola vista,
  con botón 🖨️ para imprimir solo esta sección.
- **Repaso y Hitos**: conceptos pendientes de repasar hoy y checklist de hitos.
- **Racha de estudio** (badge 🔥, ver sección 11).
- **Asignaturas cursándose** ahora mismo.
- **Próximas entregas**: tareas/eventos más cercanos en el tiempo, cada uno
  con un ✓ para marcarla como hecha.
- **Accesos rápidos**: atajos internos (nueva asignatura, calendario,
  documentos, configuración) y enlaces externos a los portales de la UPC
  (Plan de estudios, Prisma, UPCommons, calendario de trámites y calendario
  de exámenes).

## 16. Buscador global

Barra de búsqueda en la cabecera, disponible desde cualquier pantalla (atajo
**Ctrl+K**): busca a la vez en nombres de asignatura, **contenido de
documentos PDF ya indexado**, notas rápidas de asignatura, notas al vuelo,
tareas, hitos y conceptos de repaso, y muestra resultados agrupados con el
fragmento de texto donde
aparece la coincidencia.

## 17. Atajos de teclado

Navegación estilo Gmail: **g** seguido de una letra (d Resumen, a
Asignaturas, c Calendario, h Horario, r Repaso, s Configuración). Además,
**Ctrl+K** para buscar, **n** para una nota rápida, **?** para ver el
registro completo de atajos y **Esc** para cerrar lo que esté abierto. Se
ignoran mientras se escribe en un campo de formulario.

## 18. Ajustes

- **Notificaciones**: umbral de días para avisar de examen/entrega próxima y
  para considerar una asignatura abandonada.
- **Apariencia**: tema claro/oscuro (con detección y toggle).
- **Almacenamiento**: ruta de la carpeta donde se guardan los documentos, y
  la **base de datos en uso** (ruta, fecha de modificación y nº de tareas y
  documentos: una "huella" para comprobar que dos ordenadores abren el mismo
  archivo). Avisa si hay copias `sync-conflict` de Syncthing, señal de que se
  editó en dos ordenadores a la vez.
- **Cambios externos**: si la base de datos cambia en disco mientras la app
  está abierta (p. ej. un sincronizador trayendo cambios de otro PC), sale un
  aviso con botón Recargar.
- **Acceso desde el móvil**: IP local + puerto para entrar desde otro
  dispositivo en la misma red WiFi.
- **Backup**:
  - *Automático*: una copia diaria (las últimas 10) sin ninguna acción manual,
    generada en segundo plano al arrancar la app; Ajustes muestra fecha de la
    última, cuántas hay guardadas y cuánto ocupan en total.
  - *Exportar todo*: `.zip` con la base de datos completa + todos los
    documentos, con fecha en el nombre.
  - *Exportar expediente*: `.csv` (compatible con Excel en español) con una
    fila por asignatura: cuatrimestre, siglas, ECTS, tipo, estado y nota.
  - *Importar backup*: restaura BD + documentos desde un `.zip` exportado
    antes, con validaciones de seguridad (que sea un SQLite válido de esta
    app, protección contra zip bombs, rutas que intenten salirse de la
    carpeta, etc.) y snapshot previo por si la restauración falla a medias.
- **Acerca de**: registro de cambios de la app y el design system interno
  (tokens y componentes de UI).

## 19. Bloqueo opcional de la app

Si se define la variable de entorno `GREELEC_LOCK_KEY`, toda la app (web y
API) exige una clave para entrar:
- Por navegador: formulario `/unlock` → sesión; botón 🔒 para volver a
  bloquear (`/lock`).
- Por API: cabecera `Authorization: Bearer <clave>` o `X-GREELEC-KEY: <clave>`.
- Rate limit progresivo ante intentos fallidos repetidos (backoff creciente,
  nunca bloqueo permanente).
- Sin la variable definida, la app funciona exactamente igual que siempre,
  completamente abierta — pensado para poder exponerla en la red local (móvil)
  sin dejarla expuesta a cualquiera.

## 20. Multiplataforma / despliegue

- Modo servidor web normal (`python app.py`), accesible también desde el
  móvil en la misma red si se define `GREELEC_HOST=0.0.0.0`.
- Modo aplicación de escritorio nativa (`escritorio.py` + PyWebview), sin
  necesidad de navegador ni terminal, empaquetada como `.exe` con PyInstaller
  (`build.ps1` / `escritorio.spec`).
- Migraciones de base de datos (Alembic vía Flask-Migrate) y seed de datos
  iniciales aplicados automáticamente al arrancar, tanto en modo servidor como
  en el `.exe`.

---

## Estado actual de los datos (a fecha de este documento)

- 54 asignaturas de las 4 años del grado; 53 con siglas oficiales UPC.
- 61 profesores cargados (33 asignaturas; el resto, sobre todo de
  cuatrimestres futuros, aún sin profesorado publicado por la UPC).
- 65 esquemas de evaluación / 168 componentes, extraídos de las guías docentes
  oficiales (4 asignaturas sin desglose claro se dejan para nota final directa).
  Diseño Digital usa ya un bloque *Laboratorio 40%* (Prácticas P0-P3, P4 y
  Control) en sus dos esquemas, como dice su guía.
- 676 documentos organizados en 185 subgrupos, con ~7400 páginas de PDF
  indexadas para búsqueda de contenido.
- 81 recursos externos: enlaces de Wuolah (50 asignaturas) y Studocu (31
  asignaturas) verificados.
- Horario semanal (9 clases recurrentes) y calendario (15 tareas/eventos, con
  7 Espacios de Estudio) rellenos con datos reales del cuatrimestre en curso.
- Hitos y conceptos de repaso: **sin usar todavía** — son de uso personal
  continuo (certificaciones propias, repaso espaciado), no se pueden
  completar desde fuera y dependen de que el usuario los vaya añadiendo.
