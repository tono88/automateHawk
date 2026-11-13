# Acceso multiusuario y sesiones de Oracle

## Decisión propuesta

El despliegue institucional debe usar el inicio de sesión de Oracle mediante SSO. La persona escribe su contraseña directamente en Oracle; automateHawk recibe una identidad verificada y una sesión temporal. No se deben pedir ni almacenar contraseñas de Oracle en el Hub, el navegador local, PostgreSQL, archivos de configuración o Git.

La sesión del cliente contiene solo un identificador opaco en una cookie HttpOnly, Secure y SameSite, con vencimiento y cierre de sesión. El servidor verifica esa sesión en cada operación y conserva temporalmente la información necesaria para validarla. Una cookie, nombre de usuario o rol enviados libremente por el cliente no acreditan identidad ni permisos. Los tokens y cookies de Oracle también son secretos: deben tener caducidad, aislamiento y no aparecer en registros o respaldos.

Oracle documenta autorización delegada mediante flujo de código de autorización para Sales. Su configuración requiere que TI registre la aplicación y valide el dominio de identidad, redirecciones, ámbitos y compatibilidad de la instalación. SSO identifica a la persona, pero por sí solo no concede acceso al CRM ni proporciona una sesión de navegación de Fusion. El acceso delegado a datos y la autorización deben configurarse y probarse por separado.

Fuentes oficiales: [OAuth para Sales](https://docs.oracle.com/en/cloud/saas/sales/faaps/configure_oauth.html), [configuración con IDCS o IAM](https://docs.oracle.com/en/cloud/saas/sales/faaps/Configure_OAuth_Using_Oracle_IDCS_or_IAM.html).

## Si la integración sigue siendo exclusivamente por pantallas

Un grupo limitado de procesos de navegador atiende una cola. Como punto de partida para medir el piloto: dos trabajadores concurrentes; se ajustará con pruebas de carga y las reglas de Oracle. Cada usuario tiene un contexto aislado con sus propias cookies y permisos; nunca se comparte una sesión entre personas. Se abre una página solamente durante una consulta o modificación, se libera al terminar y se expira el contexto por inactividad. No se guarda el estado de sesión en disco. Al expirar, la persona debe volver a autenticarse directamente en Oracle.

Esto evita un navegador completo permanentemente abierto por cada usuario conectado, aunque los contextos y páginas activos siguen consumiendo recursos. Concurrencia limitada implica espera cuando hay muchas tareas. El ingreso SSO del Hub no crea automáticamente el contexto de Fusion: el vínculo entre ambos requiere validación institucional; no se copiarán cookies del navegador personal ni se guardarán contraseñas para recrearlo.

Un trabajador con una cuenta compartida no reproduce los permisos de cada persona. No se usará la cartera de esa cuenta como autorización para todos.

## Copia de datos y permisos

PostgreSQL conserva los valores reales y su historial fuera del repositorio. Cada consulta, búsqueda, detalle, contador y exportación debe aplicar permisos por usuario y registro en el servidor. No basta con filtrar en la pantalla ni con comparar el nombre del asesor. Se necesitan identificadores oficiales y reglas autorizadas por TI; ante permisos vencidos o no comprobados, el servidor deniega el acceso. La invalidación de permisos debe retirar el acceso a la copia, aunque el dato continúe almacenado para fines autorizados.

Cada escritura requerirá autorización vigente en Oracle bajo la identidad de la persona, relectura del registro, control de conflicto, ejecución y confirmación por relectura. Las propuestas locales actuales no se consideran escrituras en Oracle.

## Estado de esta entrega

La instalación actual sigue limitada a este equipo. Conserva un perfil local configurado en el servidor y una copia obtenida con una cuenta de Oracle. No implementa todavía SSO, aislamiento de carteras o un grupo multiusuario de navegadores. No debe publicarse a varios usuarios antes de completar estos controles. Esta propuesta no introduce una pantalla de acceso que aparente verificar credenciales sin hacerlo.

## Próximas entregas

1. TI confirma proveedor de identidad y modalidad de autorización delegada disponible.
2. SSO, sesiones temporales, cierre de sesión e invalidación; pruebas con lector, editor y usuario sin acceso.
3. Permisos por registro y campo sobre la copia, filtros y agregados; bitácora por identidad verificada.
4. Grupo de trabajadores aislados, límites, vencimiento y recuperación de sesión; medición de memoria, latencia y concurrencia.
5. Escrituras verificadas por operación. Node-RED y automatizaciones de procesos quedan pendientes después de estabilizar consulta y autorización.
