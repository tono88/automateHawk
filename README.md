# UNIS Intelligent Process Hub

Portal local de admisiones para **Oracle Fusion Cloud Sales → Ventas**, con cartera de admisiones, PostgreSQL y automatización por pantallas. El repositorio contiene código y datos ficticios de pruebas; los registros institucionales, secretos y respaldos permanecen fuera de Git.

## Acceso y cartera global

El usuario ingresa con sus credenciales de Oracle. El servicio valida el acceso usando el formulario institucional; no utiliza APIs de Oracle ni guarda contraseñas o perfiles de navegador. Un navegador mantiene contextos aislados y temporales por usuario, con dos tareas simultáneas y un máximo inicial de ocho contextos. La cookie local es opaca y HttpOnly; la sesión vence por inactividad o cierre de sesión.

PostgreSQL conserva una única copia global. El backend guarda y aplica los permisos de cada persona por oportunidad y campo. Los permisos básicos vencen en una hora y los de detalle en 30 minutos; se reutilizan entre ingresos mientras estén vigentes. La cartera abre sin filtro de asesor, ciclo o etapa y muestra todos los registros autorizados disponibles. La consulta actual es parcial: oportunidades abiertas del año actual, hasta 1,000 filas por exportación. La presencia de un registro en la base no concede acceso a todos los usuarios.

La interfaz incluye base, pruebas y convocatorias, entrevistas, pagos, ayuda económica y matrícula. Los datos disponibles se muestran completos; los vacíos indican si Oracle no registró un valor o falta ampliar la lectura. Los campos de pagos y etapas comerciales no acreditan pagos ni matrícula académica.

## Operación de admisiones

Las vistas están integradas en Resumen, Oportunidades, Aspirantes, Inscripciones a prueba, Pruebas y convocatorias, Entrevistas, Matrícula, Pagos y Asistencia económica. Las jornadas se seleccionan dentro de Pruebas y convocatorias, incluyendo fechas adicionales observadas en el CRM. Las tablas permiten ordenar columnas y seleccionar 12, 25, 50, 100, 250 o todas las filas. Los filtros se aplican antes de ordenar y paginar.

La extracción ampliada abre el contacto principal desde su relación con la oportunidad, sin unir personas por nombres. Las notas de cobertura distinguen detalle pendiente, acceso por renovar y valores vacíos. Las cargas anteriores se amplían al ejecutar Completar datos de la cartera. Durante una carga se reutiliza una sola página del listado por sesión; se libera tras un minuto sin trabajo, con los mismos límites de acceso y caducidad.

Recibos, autorizaciones, pagos efectivos, asistencia, cartas y otros campos todavía requieren una fuente verificada. No se deducen de importes, calificaciones ni etapas comerciales. Matrícula muestra referencias comerciales o del perfil hasta conciliarlas con la fuente académica. Los resúmenes cuentan oportunidades y no deduplican personas por sus nombres.

## Edición y actividades

Guardar en un campo escalar habilitado de la lista envía una solicitud por pantalla de Oracle: nombre de oportunidad, etapa comercial, probabilidad o fecha de cierre. Antes de guardar se verifica permiso y conflicto; después se relee el registro. El valor global solo cambia al confirmar el resultado. Las escrituras al mismo registro se serializan; un resultado incierto no se repite automáticamente y puede verificarse desde Cambios en Oracle.

El escritor es piloto y requiere la prueba institucional de guardado real con los responsables. Se verificaron sus controles y persistencia con datos ficticios; no se guardaron cambios reales durante el desarrollo.

Seguimientos, citas e informes de interacción tienen formularios locales persistentes, con creación, consulta, edición y estados. **Continúan sin envío a Oracle ni notificaciones** hasta validar sus vínculos, catálogos y efectos. La sección demo y el simulador conservan únicamente sus datos sintéticos y se separan por sesión.

## Ejecutar

Con Docker Desktop y Python 3.11 o posterior, desde el repositorio:

```sh
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m scripts.provision_local
docker compose up --build -d
```

Abrir http://127.0.0.1:8765. Se requieren hub, oracle-worker y postgres. Los puertos están publicados solo en loopback; el trabajador es interno. El secreto del trabajador y las credenciales de PostgreSQL se generan fuera del repositorio. Reiniciar los servicios requiere volver a iniciar sesión.

Esta configuración es un piloto local. Antes de publicarla institucionalmente se necesitan HTTPS, cookie Secure, origen público validado, pruebas de carga, validación con varias cuentas reales y manejo del MFA o desafíos que requiera Oracle. SSO y Node-RED siguen en el roadmap. Los desafíos no se omiten ni resuelven automáticamente.

## Verificación

```sh
python -m unittest discover -s tests
node --test tests/connector.test.mjs tests/oracle-write.test.mjs
.venv/Scripts/python -m scripts.verify_postgres
.venv/Scripts/python -m scripts.backup_local --verify
```

Las pruebas automáticas usan datos ficticios y una base desechable para PostgreSQL. Verifican autenticación, aislamiento por permisos sobre la base global, expiración, conflictos, resultados inciertos, relectura y persistencia. No modifican Oracle.

Ver [acceso y permisos](docs/acceso-multiusuario.md), [actividades y prueba oficial](docs/actividades-y-prueba-oficial.md), [PostgreSQL y respaldos](docs/postgresql.md), [carga y límites](docs/carga-oracle.md) y [roadmap](docs/roadmap.md).
