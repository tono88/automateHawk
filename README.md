# UNIS Intelligent Process Hub

Portal de admisiones para **Oracle Fusion Cloud Sales → Ventas**, con cartera de admisiones, edición que se guarda en el CRM, tablero de trazabilidad, PostgreSQL y automatización por pantallas. Se despliega con un solo comando de Docker (ver [Despliegue con Docker](#despliegue-con-docker)). El repositorio contiene código y datos ficticios de pruebas; los registros institucionales, secretos y respaldos permanecen fuera de Git.

## Acceso y cartera global

El usuario ingresa con sus credenciales de Oracle. El servicio valida el acceso usando el formulario institucional; no utiliza APIs de Oracle ni guarda contraseñas o perfiles de navegador. Un navegador mantiene contextos aislados y temporales por usuario, con dos tareas simultáneas y un máximo inicial de ocho contextos. La cookie local es opaca y HttpOnly; la sesión vence por inactividad o cierre de sesión.

La sesión vence tras 15 minutos de inactividad, **salvo mientras haya una sincronización en curso**: la carga de inventario o de fichas cuenta como actividad (en el navegador y en el servidor) y la sesión sigue abierta hasta que termina, con el máximo de ocho horas desde el acceso. Una demora del trabajador de Oracle (por ejemplo, CPU alta durante la extracción) ya no cierra la sesión; solo se cierra si Oracle confirma que el contexto se perdió o si el trabajador no responde durante cinco minutos.

PostgreSQL conserva una única copia global. El backend guarda y aplica los permisos de cada persona por oportunidad y campo. Los permisos básicos vencen en una hora y los de detalle en cuatro horas por defecto (`HUB_DETAIL_GRANT_MINUTES`); se reutilizan entre ingresos mientras estén vigentes. La cartera abre sin filtro de asesor, ciclo o etapa y muestra todos los registros autorizados disponibles. El inventario está configurado para oportunidades abiertas y cerradas con fecha de cierre en 2026. Consulta intervalos de fechas, los subdivide cuando alcanzan 500 filas y verifica las fechas y los estados de cada exportación. El avance del inventario y la cobertura de fichas se muestran por separado. La presencia de un registro en la base no concede acceso a todos los usuarios.

La interfaz incluye base, pruebas y convocatorias, entrevistas, pagos, ayuda económica y matrícula. Los datos disponibles se muestran completos; los vacíos indican si Oracle no registró un valor o falta ampliar la lectura. Los campos de pagos y etapas comerciales no acreditan pagos ni matrícula académica.

## Operación de admisiones

Las vistas están integradas en Resumen, Oportunidades, Aspirantes, Inscripciones a prueba, Pruebas y convocatorias, Entrevistas, Matrícula, Pagos y Asistencia económica. Las jornadas se seleccionan dentro de Pruebas y convocatorias, incluyendo fechas adicionales observadas en el CRM. Las tablas permiten ordenar columnas y seleccionar 12, 25, 50, 100, 250 o todas las filas. Los filtros se aplican antes de ordenar y paginar.

La extracción ampliada abre el contacto principal desde su relación con la oportunidad, sin unir personas por nombres. Las notas de cobertura distinguen detalle pendiente, acceso por renovar y valores vacíos. Las cargas anteriores se amplían al ejecutar Completar datos de la cartera. Durante una carga se reutiliza una sola página del listado por sesión; se libera tras un minuto sin trabajo, con los mismos límites de acceso y caducidad.

Recibos, autorizaciones, pagos efectivos, asistencia, cartas y otros campos todavía requieren una fuente verificada. No se deducen de importes, calificaciones ni etapas comerciales. Matrícula muestra referencias comerciales o del perfil hasta conciliarlas con la fuente académica. Los resúmenes cuentan oportunidades y no deduplican personas por sus nombres.

La carga ampliada conserva el avance por usuario en PostgreSQL, reintenta cada lectura hasta tres veces y continúa con otras oportunidades cuando una falla. Tras tres fallos consecutivos pausa el lote. El botón Completar datos de la cartera permite retomar lo pendiente después de un nuevo ingreso. Los filtros de extracción distinguen lo pendiente y las incidencias; completar una lectura no renueva indefinidamente sus permisos de visualización.

## Edición hacia Oracle

Los campos editables muestran un lápiz ✎ en las tablas y en la ficha de cada oportunidad (pestañas Resumen, Pruebas, Pagos y Ayuda económica). Al guardar, el portal envía el cambio con la sesión de Oracle de quien edita:

1. Abre la oportunidad en Oracle y comprueba que el control esté habilitado para ese usuario y que el valor actual coincida con el que se veía en el portal (si cambió, queda en **Conflicto**).
2. Escribe el nuevo valor (texto, fecha, número o selección de la lista de Oracle) y verifica que Oracle no haya modificado otros campos (**efectos secundarios**).
3. Pulsa *Guardar y Cerrar*, vuelve a abrir el registro y confirma el valor. Solo entonces la copia local cambia y el cambio queda **Confirmado en Oracle** en la trazabilidad.

Un resultado incierto nunca se reintenta automáticamente; se verifica desde *Cambios en Oracle*. Las escrituras al mismo registro se serializan. **Se puede editar durante una sincronización**: el cambio espera a que terminen las lecturas en curso, se guarda y después la carga continúa.

| Grupo | Campos | Por defecto |
|---|---|---|
| Comercial | Nombre, Etapa de ventas, Probabilidad, Fecha de cierre, Importe, Origen | editables |
| Admisión | Ciclo, Año, Estado proceso admisión, Convocatoria PA, Prueba de admisión, Fecha PA, Tipo de prueba, Proceso PAA, Convenio PA, Entrevista | editables |
| Ayuda y pagos | Asistencia económica, Tipo AE 1/2, % solicitado AE 1/2, Estatus, Comentarios, Límite de papelería, Razón de retraso de matrícula, Cierre reserva de cupo | editables |
| Decisiones académicas y de beca | Resolución, puntajes, promedio, % otorgado AE 1/2, Aceptación | solo con `HUB_EDIT_FIELDS=all` o lista explícita |

`HUB_EDIT_FIELDS` acepta `default`, `verified` (solo Nombre, Etapa, Probabilidad, Fecha de cierre y Convocatoria PA, probados de punta a punta), `all` o una lista separada por comas. Oracle sigue mandando: si el usuario no tiene el control habilitado en Oracle, el lápiz no aparece y el trabajador rechaza el guardado. Los campos del perfil del contacto (pestaña Contacto y estudios) son de solo consulta. Antes de usarlo en producción conviene validar con los responsables un caso real por cada grupo de campos nuevos.

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
| `HUB_EDIT_FIELDS` | `default` | Campos editables (ver Edición hacia Oracle). |
| `HUB_IDLE_MINUTES` / `HUB_SESSION_MAX_HOURS` | `15` / `8` | Inactividad y duración máxima de la sesión. |
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
