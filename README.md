# UNIS Intelligent Process Hub

Portal de admisiones para **Oracle Fusion Cloud Sales → Ventas**, con cartera de admisiones, edición que se guarda en el CRM, tablero de trazabilidad, PostgreSQL y automatización por pantallas. Se despliega con un solo comando de Docker (ver [Despliegue con Docker](#despliegue-con-docker)). El repositorio contiene código y datos ficticios de pruebas; los registros institucionales, secretos y respaldos permanecen fuera de Git.

## Acceso y cartera global

El usuario ingresa con sus credenciales de Oracle. El servicio valida el acceso usando el formulario institucional; no utiliza APIs de Oracle ni guarda contraseñas o perfiles de navegador. Un navegador mantiene contextos aislados y temporales por usuario, con dos tareas simultáneas y un máximo inicial de ocho contextos. La cookie local es opaca y HttpOnly; la sesión vence por inactividad o cierre de sesión.

La sesión vence tras 15 minutos de inactividad, **salvo mientras se esté descargando la cartera**: la carga de inventario o de fichas cuenta como actividad (en el navegador y en el servidor) y la sesión sigue abierta en segundo plano, aunque se cierre la pestaña, hasta que se descargue todo (máximo `HUB_SYNC_MAX_HOURS`, 24 horas por defecto). Si Oracle deja de responder a mitad de la carga, el avance se conserva y la descarga se retoma sola tras una espera creciente (de 1 a 30 minutos). Las fichas que fallan tres veces quedan para revisión y no se reintentan sin fin. Solo una pérdida de la sesión de Oracle exige volver a iniciar sesión. Sin descarga en curso, la sesión dura como máximo `HUB_SESSION_MAX_HOURS` (8 horas). Una demora del trabajador de Oracle (por ejemplo, CPU alta durante la extracción) ya no cierra la sesión; solo se cierra si Oracle confirma que el contexto se perdió o si el trabajador no responde durante cinco minutos.

**Sincronización incremental.** La primera extracción lee todas las fichas; después solo se vuelven a leer las oportunidades que Oracle informa como modificadas (cambia su fila en la exportación, incluida la «Última actualización de oportunidad»), las lecturas con incidencias y, como red de seguridad, las fichas con más de `HUB_DETAIL_MAX_AGE_HOURS` horas (168 por defecto). Cuando el inventario confirma que un registro no cambió, sus permisos de detalle y edición se renuevan sin volver a abrir la ficha. El inventario de la lista sigue recorriendo los intervalos del año porque es la forma de detectar cambios y altas, pero no reescribe registros sin cambios.

**Vista inmediata al iniciar sesión.** Al volver a entrar, el portal muestra de inmediato la última copia de las oportunidades que ese usuario vio en Oracle en los últimos `HUB_STALE_VIEW_DAYS` días (7 por defecto), con el aviso «Mostrando la última copia» y la marca «Por reconfirmar» en cada registro. Al mismo tiempo arranca el inventario, que las reconfirma intervalo por intervalo: las confirmadas recuperan la edición y las que Oracle ya no muestra a ese usuario desaparecen al terminar. Mientras un registro no está reconfirmado se puede consultar pero no editar. Con `HUB_STALE_VIEW_DAYS=0` se vuelve al modo estricto: solo se muestra lo confirmado en la sesión.

**Refresco ligero.** El navegador recibe la cartera completa una vez; después, cada pocos segundos, solo recibe los registros, fichas y estados que cambiaron. En el servidor, cada petición comprueba con una consulta liviana si la base cambió y solo entonces recarga la copia de ese usuario.

PostgreSQL conserva una única copia global. El backend guarda y aplica los permisos de cada persona por oportunidad y campo. Los permisos básicos vencen en una hora y los de detalle en cuatro horas por defecto (`HUB_DETAIL_GRANT_MINUTES`); se reutilizan entre ingresos mientras estén vigentes. La cartera abre sin filtro de asesor, ciclo o etapa y muestra todos los registros autorizados disponibles. El inventario está configurado para oportunidades abiertas y cerradas con fecha de cierre en 2026. Consulta intervalos de fechas, los subdivide cuando alcanzan 500 filas y verifica las fechas y los estados de cada exportación. El avance del inventario y la cobertura de fichas se muestran por separado. La presencia de un registro en la base no concede acceso a todos los usuarios.

La interfaz incluye base, pruebas y convocatorias, entrevistas, pagos, ayuda económica y matrícula. Los datos disponibles se muestran completos; los vacíos indican si Oracle no registró un valor o falta ampliar la lectura. Los campos de pagos y etapas comerciales no acreditan pagos ni matrícula académica.

## Operación de admisiones

Las vistas están integradas en Resumen, Oportunidades, Aspirantes, Inscripciones a prueba, Pruebas y convocatorias, Entrevistas, Matrícula, Pagos y Asistencia económica. Las jornadas se seleccionan dentro de Pruebas y convocatorias, incluyendo fechas adicionales observadas en el CRM. Las tablas permiten ordenar columnas y seleccionar 12, 25, 50, 100, 250 o todas las filas. Los filtros se aplican antes de ordenar y paginar.

La extracción ampliada abre el contacto principal desde su relación con la oportunidad, sin unir personas por nombres. Las notas de cobertura distinguen detalle pendiente, acceso por renovar y valores vacíos. Las cargas anteriores se amplían al ejecutar Completar datos de la cartera. Durante una carga se reutiliza una sola página del listado por sesión; se libera tras un minuto sin trabajo, con los mismos límites de acceso y caducidad.

Recibos, autorizaciones, pagos efectivos, asistencia, cartas y otros campos todavía requieren una fuente verificada. No se deducen de importes, calificaciones ni etapas comerciales. Matrícula muestra referencias comerciales o del perfil hasta conciliarlas con la fuente académica. Los resúmenes cuentan oportunidades y no deduplican personas por sus nombres.

La carga ampliada conserva el avance por usuario en PostgreSQL, reintenta cada lectura hasta tres veces y continúa con otras oportunidades cuando una falla. Tras tres fallos consecutivos pausa el lote. El botón Completar datos de la cartera permite retomar lo pendiente después de un nuevo ingreso. Los filtros de extracción distinguen lo pendiente y las incidencias; completar una lectura no renueva indefinidamente sus permisos de visualización.

## Edición y creación hacia Oracle

El portal permite hacer el proceso completo sin entrar a Oracle: cada cambio se guarda en el CRM con la sesión de Oracle de quien edita y la copia local solo se actualiza después de releer el registro en Oracle.

### Editar campos

Los campos editables muestran un lápiz ✎ en las tablas y en la ficha de cada oportunidad (pestañas Resumen, Asesor, Contacto y estudios, Pruebas, Entrevista, Pagos y Ayuda económica). Al guardar:

1. Se abre la oportunidad en Oracle y se comprueba que el control esté habilitado para ese usuario y que el valor actual coincida con el del portal (si cambió, queda en **Conflicto**).
2. Se escribe el nuevo valor (texto, fecha, número, correo, Sí/No o selección de la lista de Oracle) y se verifica que Oracle no haya modificado otros campos (**efectos secundarios**).
3. Se pulsa *Guardar y Cerrar*, se vuelve a abrir el registro y se confirma el valor. Solo entonces el cambio queda **Confirmado en Oracle**.

Los campos del contacto principal (nombre, apellidos, nacimiento, documento, correo, teléfono, carrera, facultad, estatus lead, mes y tipo de prueba, papelería, interés en ayuda, año de graduación, homeschool, talla) se guardan abriendo el contacto vinculado desde la oportunidad.

Un resultado incierto nunca se reintenta automáticamente; se verifica desde *Cambios en Oracle*. Las escrituras al mismo registro se serializan y **se puede editar durante una sincronización**: el cambio espera a que terminen las lecturas en curso.

| Grupo | Campos |
|---|---|
| Comercial | Nombre, Etapa de ventas, Probabilidad, Fecha de cierre, Importe, Origen, Responsable |
| Admisión | Ciclo, Año, Estado proceso admisión, Convocatoria PA, Prueba de admisión, Fecha PA, Tipo de prueba, Proceso PAA, Convenio PA, Entrevista, Resolución, puntajes y promedio |
| Ayuda y pagos | Asistencia económica, Tipo AE 1/2, % solicitado y otorgado AE 1/2, Estatus, Aceptación, Comentarios, Límite de papelería, Razón de retraso de matrícula, Cierre reserva de cupo |
| Contacto principal | Datos personales y académicos del perfil del contacto |
| Solo con opt-in | ID Campus, ID SCALA y Estado en Campus (los mantienen las integraciones) |

`HUB_EDIT_FIELDS` acepta `default` (todo lo anterior salvo los identificadores de integración), `safe` (además excluye resolución, puntajes y porcentajes otorgados), `verified` (solo Nombre, Etapa, Probabilidad, Fecha de cierre y Convocatoria PA, probados de punta a punta), `all` o una lista separada por comas. Oracle sigue mandando: si el usuario no tiene el control habilitado, el lápiz no aparece y el trabajador rechaza el guardado.

### Crear oportunidades

El botón **+ Nueva oportunidad** abre un formulario con nombre, fecha de cierre (dentro de 2026, el año que cubre la cartera), etapa, probabilidad, contacto principal y, opcionalmente, datos de admisión. El trabajador:

1. Si el aspirante es nuevo, lo registra con *Ventas → Crear contacto* (nombre, apellidos, correo y teléfono móvil).
2. Abre *Ventas → Crear oportunidad*, completa los datos, elige el contacto principal (debe coincidir con un único contacto) y guarda.
3. Identifica el registro por su número oficial (en la ficha que abre *Guardar y continuar* o buscando el nombre, que debe ser único) y lo incorpora a la copia local con su detalle.
4. Guarda los datos de admisión elegidos como cambios verificados.

El avance queda en *Cambios en Oracle → Oportunidades creadas desde el portal*. Si el contacto se creó pero la oportunidad no, el reintento no vuelve a crear el contacto. Si se pulsó guardar pero no se pudo identificar el registro, queda en *Verificación requerida* y no se reintenta.

### Antes de usarlo en producción

Los recorridos de creación y de edición del contacto siguen los formularios inspeccionados en Oracle (ver `docs/recorridos-oracle.md`), pero su guardado real todavía no se ha probado en el tenant. Conviene validar con los responsables un caso real por cada grupo de campos y una creación con un aspirante de prueba, y revisar el resultado en Oracle.

## Tablero de trazabilidad

El menú **Trazabilidad** reúne, con los permisos de quien consulta:

- Indicadores: oportunidades visibles, cobertura de fichas, asesores y cambios confirmados o abiertos.
- Embudo por etapa comercial y frescura de la copia (última observación en Oracle).
- **Cruce de datos** configurable: cualquier par entre etapa, asesor, estado, segmento, ciclo, facultad, carrera, proceso de admisión, convocatoria, mes de prueba, resolución, entrevista, ayuda económica, estatus lead, estado en Campus, origen, mes de cierre y estado de extracción. Cada celda abre la lista de oportunidades y desde ahí su ficha para editar.
- Controles de consistencia: sin asesor, cierre vencido y abierto, inscrito sin convocatoria, presente sin fecha PA, matriculado sin resolución, perdida con prueba futura, sin detalle extraído y cambios en curso o inciertos.
- Actividad de 30 días (cambios observados en Oracle y acciones del portal) y últimas acciones con su autor.
- Historial de una oportunidad: cada versión observada en Oracle con los campos que cambiaron, los cambios solicitados desde el portal, quién los hizo y su confirmación.

Seguimientos, citas e informes de interacción tienen formularios locales persistentes, con creación, consulta, edición y estados. **Continúan sin envío a Oracle ni notificaciones** hasta validar sus vínculos, catálogos y efectos.

## Despliegue con Docker

Requisitos: Docker Desktop (Windows/macOS) o Docker Engine con Compose v2 (Linux). No hace falta Python ni Node en el equipo.

```sh
git clone https://github.com/tono88/automateHawk.git
cd automateHawk
docker compose up -d --build
```

Abrir http://127.0.0.1:8765 e iniciar sesión con el usuario de Oracle. La primera construcción descarga Chromium y tarda varios minutos.

Qué levanta Compose:

| Servicio | Función |
|---|---|
| `secrets` | Genera una sola vez las contraseñas de PostgreSQL y el secreto del trabajador en el volumen `hub_secrets` (fuera del repositorio) y termina. |
| `postgres` | PostgreSQL 18 con volumen persistente `postgres_data`; puerto `127.0.0.1:55432` para respaldos. |
| `db-setup` | Crea o actualiza la cuenta `hub_app` y su esquema; idempotente, se ejecuta en cada arranque y termina. |
| `oracle-worker` | Chromium sin interfaz que opera las pantallas de Oracle; no publica puertos. |
| `hub` | Portal y API en el puerto 8765; aplica las migraciones al iniciar. |

Configuración opcional: copiar `.env.example` como `.env` y ajustar. Las variables más usadas:

| Variable | Por defecto | Uso |
|---|---|---|
| `HUB_BIND` / `HUB_PORT` | `127.0.0.1` / `8765` | Interfaz y puerto publicados. |
| `HUB_ALLOWED_HOSTS` | vacío | Nombres o IP adicionales con los que se abrirá el portal (además de localhost). |
| `HUB_COOKIE_SECURE` | `0` | `1` detrás de un proxy HTTPS. |
| `HUB_LOCAL_ROLE` | `editor` | `reader` para desactivar la edición hacia Oracle. |
| `HUB_EDIT_FIELDS` | `default` | Campos editables (ver Edición y creación hacia Oracle). |
| `HUB_DETAIL_MAX_AGE_HOURS` | `168` | Antigüedad máxima de una ficha sin cambios antes de releerla (0 = nunca). |
| `HUB_STALE_VIEW_DAYS` | `7` | Días de la última copia que se muestran al iniciar sesión mientras Oracle los reconfirma (0 = solo lo confirmado). |
| `HUB_IDLE_MINUTES` / `HUB_SESSION_MAX_HOURS` | `15` / `8` | Inactividad y duración máxima de la sesión. |
| `HUB_SYNC_MAX_HOURS` | `24` | Tiempo máximo que la sesión sigue activa en segundo plano mientras se descarga la cartera. |
| `HUB_DETAIL_GRANT_MINUTES` / `HUB_EDIT_GRANT_MINUTES` | `240` | Vigencia de los permisos de detalle y edición observados (15–480). |
| `HUB_READ_LANES` / `HUB_SCREEN_OPERATIONS` | `2` | Lecturas simultáneas por sesión / pantallas simultáneas del trabajador. |

### Operación diaria

```sh
docker compose ps                         # estado de los servicios
docker compose logs -f hub oracle-worker  # registros (sin datos personales)
git pull && docker compose up -d --build   # actualizar a la última versión
docker compose restart hub                # reiniciar el portal (requiere volver a iniciar sesión)
docker compose down                       # detener (los datos permanecen en los volúmenes)
```

Respaldo y restauración de la base:

```sh
docker compose exec -T postgres pg_dump -U hub_admin -d automatehawk -Fc > respaldo.dump
docker compose exec -T postgres pg_restore -U hub_admin -d automatehawk --clean --if-exists < respaldo.dump
```

`docker compose down -v` borra también la base y los secretos: solo para empezar de cero.

### Acceso desde la red interna

Por defecto el portal solo responde en el propio equipo. Para que el equipo de admisiones lo use desde otros equipos:

```env
HUB_BIND=0.0.0.0
HUB_ALLOWED_HOSTS=admisiones.unis.local,10.0.0.25
```

Para uso institucional se recomienda publicarlo detrás de un proxy HTTPS (IIS, Nginx, Caddy o Traefik) que reenvíe la cabecera `Host`, con `HUB_COOKIE_SECURE=1` y `HUB_BIND=127.0.0.1`. Cada persona entra con su propio usuario de Oracle; los desafíos de MFA no se resuelven automáticamente.

### Migración desde la instalación anterior

Si ya se usaba `scripts/provision_local.py`, el `.env` existente contiene `HUB_PG_ADMIN_SECRET_FILE`: Compose reutiliza esa contraseña y conserva la base y su historial. Basta con `git pull` y `docker compose up -d --build`. Si `db-setup` informa que la contraseña de administrador no coincide, agregar esa línea al `.env` (ruta a `postgres-admin.secret` en `%LOCALAPPDATA%/automateHawk`), ejecutar `docker compose down`, `docker volume rm automatehawk_hub_secrets` y volver a levantar.

### Ejecución sin Docker (desarrollo)

```sh
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m scripts.provision_local
.venv/Scripts/python -m scripts.run_local
```

## Verificación

```sh
python -m unittest discover -s tests
npm test
.venv/Scripts/python -m scripts.verify_postgres
.venv/Scripts/python -m scripts.backup_local --verify
```

Las pruebas automáticas usan datos ficticios y una base desechable para PostgreSQL. Verifican autenticación, aislamiento por permisos sobre la base global, expiración, conflictos, resultados inciertos, relectura y persistencia. No modifican Oracle.

Ver [acceso y permisos](docs/acceso-multiusuario.md), [actividades y prueba oficial](docs/actividades-y-prueba-oficial.md), [PostgreSQL y respaldos](docs/postgresql.md), [carga y límites](docs/carga-oracle.md) y [roadmap](docs/roadmap.md).

### Rendimiento y continuidad de la extracción

La carga ampliada usa hasta dos ventanas independientes, comprueba el número oficial de cada ficha y conserva el avance en PostgreSQL. La interfaz muestra porcentaje extraído, ritmo observado, tiempo orientativo y pausa. Mientras la carga está en curso la sesión no vence por inactividad (máximo ocho horas desde el acceso), aunque se cierre la pestaña. Cerrar sesión revoca también el lote. No se guardan contraseñas ni cookies. Los permisos para ver y editar siguen separados del progreso de extracción.

Obscura v0.2.7 se probó en la pantalla pública de acceso y no pudo renderizar el formulario IDCS. El motor operativo sigue siendo Chromium. Las mediciones y límites están en [rendimiento de extracción](docs/rendimiento-extraccion.md). El diagnóstico local `python scripts/extraction_status.py` devuelve únicamente conteos agregados, sin datos personales.
