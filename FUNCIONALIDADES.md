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

## 7. Horario semanal

- **Series recurrentes de clase** (teoría, problemas, laboratorio, seminario):
  día de la semana, hora de inicio/fin, aula, rango de fechas de vigencia,
  cada semana o quincenal, y notas. Una sola fila representa toda la serie
  (no una copia por sesión); las fechas concretas de cada clase se calculan
  al vuelo.
- Vista semanal tipo cuadrícula lunes-viernes.
- Comparte la misma detección de conflictos que el calendario.

## 8. Repaso espaciado

- **Conceptos** libres por asignatura (temas, definiciones, lo que se quiera
  repasar), con 3 niveles: *no visto*, *flojo*, *dominado*.
- Al subir o bajar de nivel un concepto, se recalcula su próxima fecha de
  repaso (repetición espaciada simplificada: 0 / 3 / 18 días según el nivel).
- Pantalla **"Repaso de hoy"**: lista solo los conceptos cuya fecha de repaso
  ya ha llegado.

## 9. Hitos

Lista libre de certificaciones, proyectos personales u objetivos fuera del
plan de estudios, cada uno con nombre, estado (pendiente/en progreso/hecho) y
fecha opcional.

## 10. Dashboard (Resumen)

- **Progreso del grado**: ECTS aprobados sobre el total, desglosado en
  obligatorias / optativas / TFG.
- **Asignaturas cursándose** ahora mismo.
- **Próximas entregas**: tareas/eventos más cercanos en el tiempo.
- **Notificaciones** automáticas: aviso de examen/entrega próxima (umbral
  configurable en días) y aviso de asignatura "abandonada" (sin actividad
  reciente, umbral también configurable).
- **Accesos rápidos**: atajos internos (nueva asignatura, calendario,
  documentos, configuración) y enlaces externos a los portales de la UPC
  (Plan de estudios, Prisma, UPCommons, calendario de trámites y calendario
  de exámenes).

## 11. Buscador global

Barra de búsqueda en la cabecera, disponible desde cualquier pantalla: busca a
la vez en nombres de asignatura, **contenido de documentos PDF ya indexado**,
notas rápidas y tareas, y muestra resultados agrupados con el fragmento de
texto donde aparece la coincidencia.

## 12. Ajustes

- **Notificaciones**: umbral de días para avisar de examen/entrega próxima y
  para considerar una asignatura abandonada.
- **Apariencia**: tema claro/oscuro (con detección y toggle).
- **Almacenamiento**: ruta de la carpeta donde se guardan los documentos.
- **Acceso desde el móvil**: IP local + puerto para entrar desde otro
  dispositivo en la misma red WiFi.
- **Backup**:
  - *Exportar todo*: `.zip` con la base de datos completa + todos los
    documentos, con fecha en el nombre.
  - *Importar backup*: restaura BD + documentos desde un `.zip` exportado
    antes, con validaciones de seguridad (que sea un SQLite válido de esta
    app, protección contra zip bombs, rutas que intenten salirse de la
    carpeta, etc.) y snapshot previo por si la restauración falla a medias.
- **Acerca de**: registro de cambios de la app y el design system interno
  (tokens y componentes de UI).

## 13. Bloqueo opcional de la app

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

## 14. Multiplataforma / despliegue

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
- 61 profesores cargados (21 asignaturas, sobre todo de cuatrimestres futuros,
  aún sin profesorado publicado por la UPC).
- 65 esquemas de evaluación / 164 componentes, extraídos de las guías docentes
  oficiales (4 asignaturas sin desglose claro se dejan para nota final directa).
- 659 documentos organizados en 185 subgrupos, con ~6800 páginas de PDF
  indexadas para búsqueda de contenido.
- 81 recursos externos: enlaces de Wuolah (50 asignaturas) y Studocu (31
  asignaturas) verificados.
- Horario, tareas/eventos, hitos y conceptos de repaso: **todavía sin rellenar**
  — son de uso personal continuo, no se pueden completar desde fuera.
