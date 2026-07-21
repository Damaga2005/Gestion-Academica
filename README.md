# Gestión Académica GREELEC

App local (Flask + SQLite) para llevar el seguimiento del grado GREELEC: asignaturas,
documentos, calendario, repaso espaciado, dashboard con widgets y buscador global.
Pensada para correr en tu propio ordenador (`python app.py`) o como ejecutable de
escritorio empaquetado (ver `build.ps1`).

## Puesta en marcha

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt      # o requirements-dev.txt si vas a tocar el icono/empaquetado
python seed.py                       # primera vez: aplica migraciones y siembra los datos reales
python app.py                        # arranca en http://localhost:5000
```

`python seed.py` (sin argumentos) es seguro de ejecutar tantas veces como quieras: no
borra ni duplica nada, solo rellena lo que falte (ver "Migraciones" y "Seed" más abajo).

## Migraciones de base de datos (Flask-Migrate / Alembic)

El esquema se gestiona con Alembic a través de Flask-Migrate. Los scripts viven en
`migrations/versions/`.

### Aplicar migraciones (upgrade)

La app las aplica **sola** al arrancar (`aplicar_migraciones()` en `create_app()`), así
que en el uso normal no tienes que hacer nada. Para aplicarlas a mano:

```powershell
$env:FLASK_APP = "app:create_app"
flask db upgrade
```

### Revertir migraciones (downgrade)

```powershell
$env:FLASK_APP = "app:create_app"
flask db downgrade -1      # retrocede una migración
flask db downgrade base    # retrocede TODAS (vuelve a un esquema vacío)
```

### Backup antes de migrar (obligatorio)

Antes de aplicar una migración nueva sobre una base de datos con datos reales, copia el
archivo SQLite:

```powershell
Copy-Item academico.db "backups\academico_$(Get-Date -Format yyyy-MM-dd_HHmmss).db"
```

Si algo sale mal, basta con volver a copiar ese archivo de vuelta a `academico.db`
(con la app cerrada) para restaurar el estado anterior. También puedes usar el botón
"Exportar todo" de Ajustes, que hace lo mismo (BD + documentos) en un `.zip` con fecha.

### Crear una migración nueva (si tocas el modelo)

```powershell
$env:FLASK_APP = "app:create_app"
flask db migrate -m "descripcion del cambio"
# revisa el archivo generado en migrations/versions/ antes de aplicarlo
flask db upgrade
```

### Limitaciones de SQLite a tener en cuenta

SQLite tiene un `ALTER TABLE` muy limitado (no permite modificar tipos de columna,
añadir `NOT NULL` sin default, ni borrar columnas directamente). Por eso
`migrations/env.py` tiene activado `render_as_batch=True`: Alembic recrea la tabla
entera por debajo cuando hace falta, en vez de fallar. Añadir columnas nullable (como
las de esta fase) funciona sin necesitar ese modo, pero se deja activado por si una
futura migración sí lo necesita.

## Bloqueo de la app (opcional)

Por defecto la app está completamente abierta, igual que siempre. Si quieres protegerla
con una clave (por ejemplo, antes de exponerla en tu red local), define la variable de
entorno `GREELEC_LOCK_KEY`.

### Activar / desactivar

Copia `.env.example` a `.env` (mismo sitio que `academico.db`) y rellena:

```
GREELEC_LOCK_KEY=una-clave-larga-y-dificil-de-adivinar
FLASK_SECRET_KEY=otra-clave-distinta-para-firmar-las-sesiones
```

Para desactivar el bloqueo, deja `GREELEC_LOCK_KEY` vacía o borra la línea del `.env`.
No hace falta reiniciar nada más que la app.

### Entrar desde el navegador

Con el bloqueo activo, cualquier pantalla te redirige a `/unlock`. Escribe la clave y
tras acertarla te lleva de vuelta a la página que querías ver. Hay un botón 🔒 en la
cabecera para cerrar sesión (`/lock`) cuando quieras volver a bloquear la app.

### Autenticar llamadas a la API

Añade la clave en una de estas cabeceras a cada petición:

```
Authorization: Bearer TU_CLAVE
```
o
```
X-GREELEC-KEY: TU_CLAVE
```

Sin la clave (o con una incorrecta), la API responde `401` con
`{"error": "authentication_required"}`.

### Rutas que siempre quedan públicas

- `/unlock` (formulario de desbloqueo) y `/lock` (cerrar sesión)
- Archivos estáticos (`/static/...`), necesarios para mostrar el propio formulario
- `/api`, como comprobación mínima de salud (no expone datos)

Todo lo demás —asignaturas, documentos, calendario, backup, búsqueda, etc.— exige
autenticación en cuanto `GREELEC_LOCK_KEY` está definida.

## Seed de datos

- `python seed.py` — idempotente, no destructivo. Aplica migraciones pendientes y
  rellena lo que falte sin tocar nada ya existente (ni asignaturas duplicadas, ni
  datos editados a mano sobrescritos).
- `python seed.py --reset` — **destructivo**: borra la base de datos y la recrea desde
  cero. Solo para desarrollo local; nunca sobre una base con datos reales sin backup.

## Tests

```powershell
pip install -r requirements-dev.txt
pytest
```

Cubren: acceso abierto/bloqueado, login por sesión y por API (clave correcta e
incorrecta), protección de GET/POST/PATCH/DELETE, cambio de estado de asignatura
(válido/inválido/404/idempotente), conservación de datos tras migrar, y que `seed.py`
no duplique nada al repetirlo.

## Empaquetado como ejecutable de escritorio

```powershell
.\build.ps1
```

Genera `dist\GestionAcademicaGREELEC.exe` (PyWebview + PyInstaller). La primera vez que
se ejecuta crea `academico.db` y `documentos\` junto al propio `.exe`, y aplica las
migraciones y el seed inicial automáticamente (sin terminal). Si usas `GREELEC_LOCK_KEY`
con el `.exe`, coloca el `.env` en esa misma carpeta.
