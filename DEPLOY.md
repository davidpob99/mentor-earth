# Despliegue en PythonAnywhere (cuenta gratuita)

En estos pasos, sustituye `USUARIO` por tu nombre de usuario de PythonAnywhere. La web quedará en `https://USUARIO.pythonanywhere.com`.

## 1. Subir el código

Lo más cómodo es un repositorio privado en GitHub, porque después actualizar es un `git pull`.

En una consola **Bash** de PythonAnywhere:

```sh
git clone https://github.com/TU_CUENTA/mentor-earth.git
cd mentor-earth
```

Para un repositorio privado, GitHub pedirá usuario y un token de acceso personal en lugar de la contraseña.

Alternativa sin GitHub: comprime la carpeta del proyecto sin `.venv/`, `db.sqlite3` ni `media/`, súbela desde la pestaña **Files** y descomprímela con `unzip` en la consola.

## 2. Entorno virtual y dependencias

Django 6.1 necesita Python 3.12 o superior. Mira qué versiones hay con `ls /usr/bin/python3.*` y usa la más reciente:

```sh
cd ~/mentor-earth
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## 3. Configuración: archivo `.env`

Genera una clave secreta:

```sh
.venv/bin/python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
```

Crea `~/mentor-earth/.env` (por ejemplo con `nano .env`) con este contenido:

```
SECRET_KEY='la-clave-generada'
DEBUG=false
ALLOWED_HOSTS=USUARIO.pythonanywhere.com
CSRF_TRUSTED_ORIGINS=https://USUARIO.pythonanywhere.com

EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=tucuenta@gmail.com
EMAIL_HOST_PASSWORD=contraseña-de-aplicación
DEFAULT_FROM_EMAIL=tucuenta@gmail.com
```

La clave secreta va entre comillas simples porque puede contener `#` o `$`. `CSRF_TRUSTED_ORIGINS` es imprescindible: sin él, los formularios fallan con un error 403.

## 4. Base de datos, estáticos y primeras cuentas

```sh
.venv/bin/python manage.py migrate
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py invite tu@email.org
```

## 5. Crear la aplicación web

En la pestaña **Web**:

1. **Add a new web app** → **Manual configuration** (no "Django") → la misma versión de Python que usaste en el paso 2.
2. **Virtualenv**: `/home/USUARIO/mentor-earth/.venv`
3. **Source code** y **Working directory**: `/home/USUARIO/mentor-earth`
4. **WSGI configuration file**: ábrelo, borra todo y deja solo esto:

   ```python
   import os
   import sys

   path = "/home/USUARIO/mentor-earth"
   if path not in sys.path:
       sys.path.insert(0, path)

   os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"

   from django.core.wsgi import get_wsgi_application

   application = get_wsgi_application()
   ```

5. **Static files**, dos entradas:

   | URL | Directory |
   | --- | --- |
   | `/static/` | `/home/USUARIO/mentor-earth/staticfiles` |
   | `/media/` | `/home/USUARIO/mentor-earth/media` |

6. Activa **Force HTTPS** y pulsa **Reload**.

## 6. Comprobar antes de invitar al grupo

1. Abre `https://USUARIO.pythonanywhere.com/login/` y comprueba que la página tiene estilos.
2. Pide un código con tu email y comprueba que llega el correo.
3. Entra, completa el perfil y sube una foto para comprobar que `/media/` funciona.

Si algo falla, el motivo está en el **Error log** de la pestaña Web. Si el correo no sale, lo más probable es que la cuenta gratuita no permita ese servidor SMTP: prueba con Gmail.

Cuando todo funcione, invita al resto:

```sh
.venv/bin/python manage.py invite --file emails.txt
```

## Actualizar más adelante

```sh
cd ~/mentor-earth
git pull
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py collectstatic --noinput
```

Después pulsa **Reload** en la pestaña Web.

## Copias de seguridad

Todos los datos están en `db.sqlite3` y en la carpeta `media/`. Descarga ambos de vez en cuando desde la pestaña **Files**.
