"""
Registro de cambios de la propia app (spec, punto 22). Añade una entrada nueva
al principio de CAMBIOS cada vez que se implemente una fase o funcionalidad nueva.
"""

CAMBIOS = [
    {
        "version": "0.7",
        "titulo": "Fase 11 — Evaluación jerárquica, importadores y hábito de estudio",
        "cambios": [
            "Bloques de evaluación: un grupo (p. ej. Laboratorio 40%) cuya nota se calcula sola a partir de sus componentes",
            "Editar nombre y peso de componentes y bloques, reordenarlos (▲▼) y aviso si los pesos no suman 100%",
            "Nota mínima por componente: aunque la media llegue a 5, suspende si un componente queda por debajo de su mínimo",
            "Duplicar un esquema de evaluación (estructura sin notas) para probar fórmulas alternativas",
            "La guía docente en PDF ahora importa las sub-fórmulas como bloques",
            "Importar tareas desde el .ics de Atenea, con previsualización, asignatura sugerida y aviso previo",
            "El recordatorio de cada tarea manda de verdad sobre el ajuste general de avisos",
            "Marcar como hecha y posponer un día desde el Resumen y la campanita",
            "Repetir una tarea cada semana (hasta 52 veces)",
            "Temporizador de estudio en el Resumen: cada sesión suma a la racha y a un resumen de minutos",
            "Media ponderada por ECTS, media por cuatrimestre y objetivo de media con la nota que necesitas",
            "Exportar el expediente a CSV desde Ajustes",
            "Imprimir el horario, el calendario y \"Esta semana\"",
            "Ajustes muestra qué base de datos usa la app, y avisa de copias en conflicto de Syncthing",
            "Aviso si la base de datos cambia en disco mientras la app está abierta (otro ordenador)",
            "Corregido: el estado de notas contaba los componentes de un bloque como sueltos",
        ],
    },
    {
        "version": "0.6",
        "titulo": "Fase 10 — Integridad de datos y línea de tiempo",
        "cambios": [
            "Línea de tiempo del cuatrimestre: horario + exámenes/entregas de todas las asignaturas en una sola vista Gantt",
            "Notas al vuelo: renombradas (chocaban de nombre con las Notas rápidas por asignatura), ahora buscables",
            "Filtro Sin empezar/En progreso/Completados y badge de aviso en Espacios de Estudio",
            "Aviso visual en Modo examen si el examen está cerca y no has empezado a repasar",
            "Descartar un aviso de la campanita por hoy, sin completar la tarea de verdad",
            "Editar el texto de una Nota al vuelo en línea, con fecha relativa (\"hace 2h\")",
            "Convertir una Nota al vuelo en tarea con un clic",
            "Descargar una copia de backup automático concreta desde Ajustes",
            "Corregidos varios bulk-delete que se saltaban las cascadas de borrado (datos huérfanos)",
        ],
    },
    {
        "version": "0.5",
        "titulo": "Fase 9 — Automatizaciones y hábito de estudio",
        "cambios": [
            "Campanita de avisos en la cabecera + aviso nativo de Windows al arrancar",
            "Widget \"Repaso y Hitos\" en el Dashboard",
            "Widget \"Esta semana\" en el Dashboard (horario + tareas de la semana)",
            "Calculadora de \"¿qué nota necesito?\" en cada asignatura",
            "Checkbox para crear el Espacio de Estudio directamente al guardar un examen en el Calendario",
            "Modo examen: vista resumida del día del examen, con chuleta imprimible",
            "Sección Laboratorio en Espacios de Estudio",
            "El buscador global también encuentra Hitos y Conceptos de repaso",
            "Al programar un examen se crea solo su Espacio de Estudio (y se borra solo si borras el examen)",
            "Los exámenes ya pasados dejan de salir como \"atrasados\" en los avisos",
            "Racha de estudio: días seguidos y récord histórico, con badge en el Dashboard",
            "Notas al vuelo: bloc de notas accesible desde cualquier página (atajo \"n\")",
            "El número de avisos pendientes aparece en el título de la pestaña",
            "Backup automático diario + visibilidad de las copias guardadas en Ajustes",
        ],
    },
    {
        "version": "0.4",
        "titulo": "Fase 8 — Calidad de vida",
        "cambios": [
            "Modo oscuro/claro con toggle en la cabecera y preferencia guardada",
            "Página de ajustes: umbrales de notificación, tema, ruta de documentos, IP local, backup",
            "Backup: exportar todo a .zip e importar backup para restaurar",
            "Confirmación antes de borrar marcadores y tareas del calendario",
            "Vista previa de imágenes en el almacén de documentos con lightbox",
            "Pantalla de registro de cambios (esta misma pantalla)",
        ],
    },
    {
        "version": "0.3",
        "titulo": "Fase 6 — Empaquetado de escritorio",
        "cambios": [
            "Ventana de escritorio nativa con PyWebview (en vez de navegador)",
            "Empaquetado en un único .exe con PyInstaller, icono propio",
            "Autocarga del seed real la primera vez que se ejecuta el .exe",
            "Servidor Flask sigue escuchando en 0.0.0.0 para no perder el acceso móvil",
        ],
    },
    {
        "version": "0.2",
        "titulo": "Fase 2 — Documentos, calendario y visor de PDF",
        "cambios": [
            "Apartados por asignatura (Teoría/Exámenes/Laboratorio + personalizados)",
            "Almacén de documentos con subida múltiple y almacenamiento físico organizado",
            "Visor de PDF integrado (PDF.js) con marcadores y recuerdo de última página",
            "Calendario de tareas/eventos con vista mensual",
        ],
    },
    {
        "version": "0.1",
        "titulo": "Fase 1 — Base de datos y backend",
        "cambios": [
            "Modelo de datos: Año, Cuatrimestre, Asignatura, Componente de evaluación",
            "Rutas CRUD básicas para todas las entidades",
            "Catálogo de optativas por cuatrimestre con elección/deselección",
            "Seed inicial con el plan de estudios real de GREELEC",
        ],
    },
]
