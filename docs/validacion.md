# Validación y transición al portal real

## Prueba funcional del laboratorio

1. Abrir Admisiones. Verificar los 60 aspirantes ficticios y cambiar filtros; los indicadores deben corresponder a las filas filtradas.
2. Abrir una etapa comercial desde la tabla, cambiarla y guardar. Verificar la tabla y la distribución; la resolución académica no cambia.
3. Crear un contacto con correo único `@example.invalid`; verificar que aparezca en Contactos y en la cartera.
4. Crear oportunidad vinculada al nuevo contacto; cambiar su etapa, volver a abrir y verificar el valor.
5. Crear tarea con Responsable y Contacto principal. Registrar una interacción y Fecha de Seguimiento; comprobarla en el listado de Tareas.
6. Crear cita vinculada con finalización posterior al inicio. Verificar el indicador de entrevista en la cartera.
7. Crear prospecto e informe de interacción. Verificar que aparecen en sus respectivos listados.
8. Abrir un registro en dos pestañas. Guardar en una y luego intentar guardar en la otra: el cambio obsoleto debe rechazarse.
9. Borrar los registros de prueba en orden de relaciones. Verificar la bitácora y que no reaparezcan hasta reiniciar el servidor.
10. Reiniciar el servicio: deben volver los datos sintéticos iniciales. No cargar el Excel real.

## Validación necesaria en Oracle

Definir con el propietario del proceso una cartera y registros de prueba claramente identificados. Confirmar si hay sandbox; la sesión explorada no se consideró un ambiente de pruebas. Antes de altas, determinar las automatizaciones que podrían enviar correos, asignaciones o integraciones al guardar.

Para cada recorrido, verificar búsqueda por identificador, lectura del detalle, actualización de un campo permitido, persistencia al reabrir, auditoría del cambio y limpieza recuperable. Esta validación real no se ejecutó en esta entrega. Borrado y aprobación requieren validar las consecuencias y permisos efectivos antes de ejecutarse.

No basta con cambiar la URL del simulador. Un adaptador real necesita selectores y esperas de Oracle, manejo de sesión y MFA, permisos, lectura y validación de extensiones académicas, reconciliación, límites y pruebas ante fallos. Deben verificarse por separado persona, oportunidad, ciclo y carrera.

## Operación y privacidad

No añadir adjuntos institucionales a este repositorio. No activar capturas, grabaciones, trazas HAR, registros de formularios ni guardado de sesiones con datos reales. Las exclusiones de Git son una ayuda, no una garantía de anonimización; revisar explícitamente los archivos antes de cada publicación.

El laboratorio publica su puerto solo en loopback. La puesta en producción exige sustituir el servidor de demo por un servicio autenticado, TLS, permisos por rol y cartera, almacenamiento persistente, gestión de secretos, monitoreo sin PII y procedimientos de soporte y recuperación.
