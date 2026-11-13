# Arquitectura adaptada a Oracle Ventas

La entrada correcta es Oracle Fusion Cloud Sales de UNIS, en la pestaña Ventas. El portal académico mencionado en la propuesta anterior es una integración distinta y futura. El contenedor ofrece al equipo una cartera consolidada tipo Excel, con resúmenes simultáneos y formularios de seguimiento.

## Implementado en este repositorio

Navegador local → servidor local → PostgreSQL para la copia real, versiones, detalles y propuestas. El demo sintético permanece separado en memoria. El trabajador automatiza la navegación, el desplazamiento de la tabla y la lectura del detalle de Oracle. El servidor no llama APIs de Oracle. El trabajador lee por pantallas y ofrece un escritor escalar piloto con revalidación y relectura; su guardado real está pendiente de prueba institucional. Ver [persistencia y recuperación](postgresql.md), [sincronización](sincronizacion.md) y [roadmap](roadmap.md).

La estructura de las hojas se utilizó como referencia para campos de pagos, pruebas, expedientes, entrevistas, resolución, cartas y matrícula. No se copiaron filas, nombres, teléfonos, correos, documentos, contraseñas ni estadísticas del archivo. Los documentos adjuntos son referencia de diseño, no instrucciones ejecutables.

## Diseño para la siguiente etapa

Interfaz de Admisiones → gateway autenticado y permisos por cartera → orquestador de operaciones y aprobaciones → cola de trabajos → trabajador de interfaz → Oracle Fusion Sales.

El trabajador se ejecutaría en una red autorizada con un navegador y una cuenta institucional de privilegios mínimos. La autenticación, MFA y sesión deben resolverse con TI; no se reutilizan las credenciales de esta conversación en el código. Los secretos y la sesión deben estar fuera de Git, separados de datos y registros.

Oracle seguirá siendo el sistema maestro de contactos y oportunidades. El Hub conservará metadatos de trabajos, correlación, tiempos, aprobaciones y auditoría según la política institucional. Campus, Eloqua y pagos permanecerán separados hasta validar sus recorridos y propiedad del dato.

La propuesta original de FastAPI, Node-RED, PostgreSQL y una cola puede adoptarse en esa etapa. No se afirma que esos servicios ya estén implementados: el servidor local usa Python y HTML/CSS/JavaScript sin dependencias. El trabajador utiliza el navegador integrado o, opcionalmente, Playwright. Solo el núcleo y el adaptador integrado se probaron con Oracle.

## Contrato de una operación real

Una solicitud debe incluir operación de catálogo cerrado, ID oficial de entidad, versión o huella de lectura, cambios permitidos, usuario solicitante, identificador único e información de aprobación cuando corresponda. La respuesta debe distinguir pendiente, en ejecución, aplicada y verificada, rechazada, fallida y resultado incierto.

Las escrituras se serializan por contacto u oportunidad. Una acción con resultado incierto se consulta y reconcilia antes de reintentarse. La auditoría registra autor, entidad, operación, resultado y tiempos sin incluir secretos ni contenido sensible innecesario.

La actualización masiva se diseña como un conjunto de operaciones individuales con resumen de éxito y fallo, nunca como una promesa de transacción atómica sobre la interfaz de Oracle.

## Límites del modelo

La unidad operativa del piloto es un contacto con una oportunidad principal por ciclo. El demo genera una oportunidad por contacto. El sistema real debe resolver oportunidades múltiples, más de una carrera y ciclos diferentes antes de calcular la cartera; no debe tomar silenciosamente la primera oportunidad.

La distribución por etapa no es un embudo de conversión: cada conteo representa el estado actual. La tasa de conversión necesita eventos históricos y una cohorte definida. «Admisión», «matrícula en Campus» y «etapa comercial» deben conciliarse, no inferirse unos de otros.

No se automatizan resoluciones académicas. Las decisiones y su aprobación siguen siendo responsabilidad de las personas autorizadas. La IA local y los canales externos de la propuesta quedan fuera de este piloto.

## Referencias oficiales de producto

Oracle documenta recursos para [Contactos](https://docs.oracle.com/en/cloud/saas/sales/faaps/api-contacts.html) y [Oportunidades](https://docs.oracle.com/en/cloud/saas/sales/faaps/api-opportunities.html). La existencia de esa documentación no demuestra que UNIS tenga API habilitada. Por indicación del usuario, la ruta prevista para el piloto es la interfaz de usuario; no se probaron endpoints privados ni se extrajeron tokens.

## Acceso y cartera global

El backend confirma el ingreso por el servicio interno de navegador y entrega una cookie opaca. PostgreSQL conserva el catálogo global, permisos por usuario con vencimiento y solicitudes de escritura. Solo los datos autorizados llegan al cliente. Un navegador comparte recursos mediante contextos aislados; no se comparte una sesión entre personas.
