# Acceso por pantalla de Oracle

## Implementado en el piloto local

El portal pide usuario y contraseña de Oracle y los utiliza una sola vez para llenar el formulario institucional de ingreso en un contexto nuevo y aislado. Oracle valida las credenciales por su pantalla; no se llaman APIs de Oracle ni se verifica una contraseña contra una copia local. El ingreso se confirma únicamente al regresar al portal institucional y observar el acceso autenticado a Página Inicial. Esto no es SSO federado del Hub.

La contraseña pasa transitoriamente por el servidor y el trabajador de navegador. No se guarda en PostgreSQL, archivos, Git, registros de solicitudes, capturas, vídeos ni trazas. Las referencias se liberan al finalizar la solicitud; no se promete borrado físico inmediato de la memoria administrada. Las cookies de Oracle permanecen en el contexto temporal. El contenedor utiliza /tmp en memoria y no exporta perfiles o storageState.

Solo se permiten formularios POST hacia el portal de Fusion configurado y su dominio exacto de identidad institucional. No se aceptan destinos enviados por el cliente. Si cambia el formulario o el destino, el acceso se detiene. MFA, CAPTCHA, términos u otros desafíos no se resuelven ni omiten: ese recorrido adicional requiere implementación y validación específica; no se concede acceso al Hub mientras Oracle no confirme el ingreso.

## Sesión y recursos

El cliente recibe una cookie opaca HttpOnly y SameSite=Strict; no recibe las cookies de Oracle, tokens del trabajador ni roles elegibles. La sesión se verifica en el servidor. Vence tras 15 minutos de inactividad o un máximo de ocho horas. Las consultas automáticas de la interfaz no prolongan la inactividad. Cerrar sesión revoca el acceso y cierra el contexto. Reiniciar cualquiera de los servicios exige volver a ingresar.

Un navegador Chromium atiende como máximo dos tareas simultáneas y ocho contextos activos en este piloto. Cada persona usa un contexto propio, sin compartir cookies; las páginas se cierran después de cada trabajo. Al llegar al límite se informa que debe esperar. Son límites iniciales, pendientes de medición de carga. La expiración libera contextos y sesiones, sin borrar los datos de negocio persistidos.

El servicio de navegador está únicamente en la red interna de Docker, protegido con un secreto propio fuera de Git y sin puerto publicado. El portal y PostgreSQL continúan publicados solo en loopback. La cookie no usa Secure en este acceso HTTP exclusivamente local; antes de una publicación institucional se requieren HTTPS, cookie Secure, origen público validado, límites y pruebas de carga. No debe exponerse la configuración local directamente a una red compartida.

## Cartera global y permisos persistentes

PostgreSQL mantiene una sola copia canónica en el esquema hub. La tabla user_permissions conserva por usuario y oportunidad los campos visibles, controles editables, acceso a actividades y fechas de comprobación y vencimiento. El cliente no elige el rol ni los permisos. Las consultas y agregados aplican el permiso en el servidor; cambiar filtros o IDs no concede acceso.

La lista abre sin filtros de asesor, ciclo o etapa: cada persona ve todas las oportunidades globales disponibles para las que Oracle le haya confirmado acceso. Que exista un registro en la copia global no autoriza automáticamente a todos a consultarlo. El alcance solicitado comprende Abierta, Inscrito y Perdida con cierre en 2026. El inventario se divide por fechas y se subdivide si alcanza el umbral conservador de 500 filas. La interfaz muestra su recorrido y los límites sin certificar otros años ni información no accesible en Oracle.

Los permisos básicos se reutilizan durante una hora y los campos del detalle durante 30 minutos, incluso entre ingresos. Al vencer se ocultan hasta renovar la consulta con Oracle; una consulta parcial no revoca registros ausentes antes del vencimiento. No hay detección instantánea de una revocación hecha en Oracle fuera del portal. El inicio de sesión siempre debe confirmar la identidad por pantalla, aunque los permisos estén en caché. No se guardan contraseñas para renovar la sesión automáticamente.

Cada nuevo ingreso carga inmediatamente la cartera con permisos vigentes; si no los hay, inicia su consulta en Oracle. Los cambios globales aparecen para los demás usuarios autorizados al refrescar su copia. Los campos que una cuenta no pudo observar no sobrescriben ni exponen los campos globales a los que no tiene permiso.

El demo se separa por sesión; las propuestas y escrituras se atribuyen al usuario confirmado. Las actividades locales pertenecen a la copia global, con consulta limitada a las oportunidades autorizadas y a su creador o a un permiso de actividades vigente. Su edición se limita al creador mientras no se valide una delegación específica. La copia previa de hub se conserva; los esquemas de usuario que existieran de la etapa anterior quedan sin uso por la aplicación y no se borran automáticamente. Los respaldos incluyen y verifican ambos conjuntos.

## Envío de modificaciones

Guardar en la lista solicita el envío de nombre de oportunidad, etapa comercial, probabilidad o fecha de cierre. Se persiste una solicitud con valor anterior, nuevo valor, versión y actor, y se procesa con la sesión de Oracle de esa persona. Antes del guardado se vuelve a abrir el registro, se comprueba el control habilitado y se compara el valor actual. Una modificación externa produce conflicto; un cambio adicional inducido por el formulario detiene el envío para revisión. Después de Guardar y Cerrar se abre de nuevo y se confirma el resultado.

Solo esa relectura permite actualizar el valor global confirmado. Las escrituras al mismo registro se serializan. No se reintenta un resultado incierto ni se vuelve a crear una solicitud duplicada mientras quede pendiente de verificar. La vista Cambios en Oracle ofrece una verificación de solo lectura para resolver el resultado. Reiniciar el servidor deja los envíos en curso como inciertos, sin reenviarlos automáticamente.

Este escritor es piloto: se prueban sus validaciones y persistencia con datos ficticios, pero el guardado real debe probarse oficialmente con los responsables. No se modificaron registros reales durante su desarrollo. Citas, tareas e informes permanecen locales: sus relaciones, catálogos, permisos y efectos de agenda requieren el recorrido específico descrito en actividades-y-prueba-oficial.md. No se anuncian como enviados.

## Ejecución

Preparar los secretos privados con `python -m scripts.provision_local`; después ejecutar `docker compose up --build -d`. El servicio oracle-worker instala Playwright y Chromium desde sus fuentes oficiales. No utilizar el trabajador antiguo sin autenticación para cargar este modo: los endpoints de importación directa, tickets y reclamación de trabajos se bloquean para clientes del portal.

El modo de pruebas sin autenticación solo se admite explícitamente con HUB_MODE=demo y HUB_AUTH_MODE=disabled; no es un modo de despliegue institucional. Las pruebas unitarias y de PostgreSQL utilizan cuentas, filas y contraseñas ficticias. Las pruebas reales no guardan en Oracle.

## Pendientes institucionales

MFA y recuperación interactiva de desafíos; autorización institucional por identidad y roles; HTTPS; pruebas con responsables y varias cuentas reales; métricas de carga; validación oficial del escritor piloto y envío de actividades. La alternativa futura de SSO y autorización delegada requiere registro de la aplicación por TI y no es necesaria para este piloto por pantallas. Node-RED continúa pendiente.

Referencias: [contextos aislados de Playwright](https://playwright.dev/docs/browser-contexts), [riesgos de persistir estado de autenticación](https://playwright.dev/docs/auth), [OAuth de Oracle Sales para una integración futura](https://docs.oracle.com/en/cloud/saas/sales/faaps/configure_oauth.html).
