# Actividades locales y prueba oficial de Oracle

## Relación verificada en la interfaz

| Registro del Hub | Acceso real verificado | Relación y límite |
|---|---|---|
| Seguimiento | Página Inicial → Ventas → Crear tarea | Responsable, Contacto principal, Cuenta, Interacciones 1 a 4, respuestas y Fecha de Seguimiento. No se observó selector de oportunidad en ese formulario. |
| Cita | Página Inicial → Ventas → Crear cita; Ventas → Actividades → Mi calendario → Crear cita | Contacto principal, Cuenta, Oportunidad, fechas, horas, zona horaria, privacidad, disponibilidad y recordatorio. No se observó un campo Responsable equivalente al de las tareas. |
| Informe de interacción | Página Inicial → Ventas → Crear informe de interacción | Cuenta, Oportunidad u Oportunidad potencial, Outcome, fechas, horas, Type y Ubicación. |

La revisión se hizo abriendo los formularios reales y cancelándolos sin guardar. La disponibilidad de controles en esta cuenta no acredita los permisos de otros usuarios ni confirma un guardado. Las actividades se consultan también desde una oportunidad en Actividades → Mostrar → Todas las actividades. El módulo general abre Mi calendario; no se presupone que todos los tipos sean una única tabla o un mismo formulario.

## Implementación local

Los tres formularios se abren desde las acciones de cada fila, el detalle de Citas y tareas o la vista Seguimientos y citas locales. Heredan la oportunidad por número oficial. El contacto es una referencia local por nombre, todavía sin un ID oficial validado. El vínculo local a oportunidad no acredita un vínculo equivalente para una tarea de Oracle.

Se guardan en PostgreSQL, en hub.local_activities, por separado de las observaciones del CRM y del demo. Tienen ID propio, versión, fechas, autor local y estado Pendiente/Completado/Cancelado. El perfil editor local puede crearlos y modificarlos; el lector solo consulta. El estado del envío es siempre local_only. No hay envío, invitación, correo, recordatorio, aprobación académica o modificación de Oracle. El responsable de citas e informes se identifica como responsable local hasta validar organizador y participantes en Oracle.

La fecha y hora de citas e informes se interpretan con America/Guatemala. Se valida que el final sea posterior al inicio. Las actualizaciones comprueban la versión para evitar sobrescribir cambios concurrentes. Reintentar una creación con el mismo ID y contenido no duplica el registro.

## Preparación para la prueba oficial

La interfaz incluye una revisión del formulario destino y de los requisitos pendientes. Esta entrega prepara los formularios y el almacenamiento; todavía no contiene un escritor de actividades de Oracle habilitado. La prueba de guardado real requiere implementar y validar el recorrido de escritura antes de ofrecer un botón de envío. No basta con que el formulario local se guarde correctamente.

1. Los responsables eligen cuenta, ambiente y caso de prueba autorizado, además de las notificaciones permitidas y del método de cancelación o limpieza.
2. Se resuelven contacto, cuenta y oportunidad por identificadores oficiales; no se unen por nombres. Para tareas se confirma cómo asociar la oportunidad desde la operación admitida por Oracle.
3. Se validan los catálogos dependientes (tipo, subtipo, estado, prioridad, resultado y recordatorio), responsable de tarea, organizador y participantes de cita bajo la sesión del usuario real.
4. El escritor debe abrir el formulario, seleccionar relaciones verificadas y llenar únicamente campos aprobados. Una revisión previa muestra destino, valores, cambios y posibles notificaciones. No debe pulsar Guardar en una sesión de exploración.
5. En la prueba oficial autorizada se guarda un caso por tipo. Se obtiene el identificador de la actividad, se relee y se comprueba su vínculo y visibilidad desde Oracle y el Hub.
6. Se prueba rechazo por permisos, conflicto, sesión vencida y fallo después de guardar. Ante resultado incierto se reconcilia antes de reintentar; no se vuelve a crear a ciegas.
7. El registro local solo podrá cambiar a confirmado tras esa relectura, conservando ID de Oracle, actor verificado y resultado. Nunca se borrará automáticamente una actividad real como limpieza.

Criterio de salida: responsables validan cada tipo y su efecto sobre agenda y notificaciones; el escritor pasa estas comprobaciones. El acceso por pantallas y los permisos persistentes ya existen como piloto; SSO, MFA y la validación institucional multiusuario siguen siendo requisitos independientes.
