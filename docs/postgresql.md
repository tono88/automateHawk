# PostgreSQL local y recuperación

La copia se conserva en PostgreSQL 18, servicio `postgres` del proyecto Docker Compose, con volumen persistente. El puerto del anfitrión es `127.0.0.1:55432`. La cuenta `hub_app` tiene su propio esquema y no es superusuario. La cuenta de mantenimiento se utiliza únicamente para provisión y respaldo.

Los secretos se generan en el directorio privado `automateHawk` de los datos locales del usuario, fuera del repositorio. En Windows se restringen sus permisos al usuario actual. El archivo `.env` del checkout contiene solamente referencias locales y está excluido de Git. No se guardan credenciales de Oracle.

## Preparación y arranque

Con Docker Desktop iniciado, desde el checkout:

```sh
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m scripts.provision_local
.venv/Scripts/python -m scripts.run_local
```

`run_local` utiliza el perfil local `editor` para el único operador del equipo. Se puede definir `HUB_LOCAL_ROLE=reader` antes de arrancar para impedir propuestas de cambio. No es autenticación multiusuario ni sustituye los permisos de Oracle.

La aplicación también se puede ejecutar en el servicio `hub` de Compose después de provisionar PostgreSQL. El servicio del contenedor usa perfil lector por defecto. El servidor y el trabajador de navegador siguen siendo procesos separados.

## Datos persistidos

Se guardan oportunidades, fechas de primera/última observación, versiones históricas, cargas, detalles consultados, propuestas, auditoría y configuración. No se importan filas del Excel. No se guardan sesiones de navegador ni archivos de credenciales de Oracle.

Al volver a arrancar, el servidor recupera la copia desde PostgreSQL. No elimina registros al faltar en una carga parcial. La copia es un modelo local de consulta y operación, no una réplica transaccional de la base interna de Oracle.

## Respaldo y restauración

```sh
.venv/Scripts/python -m scripts.backup_local --verify
```

El respaldo `pg_dump` se escribe en la carpeta privada `automateHawk/backups`, fuera de Git, y genera una suma SHA-256. La verificación restaura en una base temporal exclusiva, compara conteos y huellas de contenido de las tablas del esquema `hub`, y elimina únicamente esa base de prueba. No modifica la base operativa durante la prueba.

El volumen y el respaldo del mismo equipo protegen frente a algunos fallos, pero no constituyen alta disponibilidad ni protección frente a pérdida del dispositivo. La copia externa cifrada, retención, automatización de respaldos, RPO/RTO y restauraciones periódicas forman parte de la etapa institucional. No publicar estos respaldos ni incorporarlos al repositorio.

Fuente oficial: [PostgreSQL Backup and Restore](https://www.postgresql.org/docs/current/backup.html).

La copia activa es global en hub. user_permissions conserva permisos por identidad con vencimiento. La cuenta técnica tiene CREATE en esta base para ejecutar migraciones, sin ser superusuario; el cliente no puede elegir esquemas ni enviar SQL. Los respaldos verifican todas las tablas activas y cualquier esquema previo del piloto.
