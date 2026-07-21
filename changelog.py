"""
Registro de cambios de la propia app (spec, punto 22). Añade una entrada nueva
al principio de CAMBIOS cada vez que se implemente una fase o funcionalidad nueva.
"""

CAMBIOS = [
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
