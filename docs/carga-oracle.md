# Carga de Oracle por pantallas

El despliegue actual utiliza login por pantalla, cartera global y permisos persistentes. Iniciar los tres servicios con `docker compose up --build -d`, ingresar en el portal y utilizar Actualizar desde Oracle o Completar datos de la cartera. El trabajador interno ejecuta las solicitudes con el contexto aislado del usuario. No se requiere acceso a APIs de Oracle.

La primera entrada sin permisos vigentes solicita una lectura; las entradas posteriores reutilizan permisos hasta su vencimiento. La navegación normal usa PostgreSQL. La consulta predeterminada es Todos los registros que puedo ver, oportunidades abiertas del año actual, con un máximo de 1,000 filas por exportación. No equivale a una sincronización certificada de todo el CRM. Los campos no leídos y la ausencia de una fila en una carga parcial no acreditan una revocación ni un borrado.

La carga masiva usa la acción Acciones → Exportar de la lista de Oracle. El archivo HTML de Excel se procesa en memoria y se elimina del área temporal en memoria del trabajador. Solo se incorporan las columnas permitidas, excluyendo el correo del responsable. El lector deduplica por número oficial de oportunidad; no usa APIs de Oracle. La lectura por desplazamiento se conserva como referencia del recorrido. El detalle se abre por ese número, se expanden módulos y se consultan las actividades visibles. Cada resultado se persiste antes de continuar. La carga por lotes cede el turno entre expedientes para permitir otras consultas y escrituras.

El servidor bloquea la importación directa, tickets y reclamación de trabajos desde clientes autenticados. El antiguo ejecutor independiente y el adaptador CUA se conservan como referencia del recorrido, pero no son el mecanismo de carga del despliegue autenticado. El secreto de comunicación del trabajador se genera fuera de Git y su servicio no publica puertos.

Los fallos conservan la copia anterior. Una sesión vencida exige ingresar de nuevo; no se conservan contraseñas para repetir el acceso. La visibilidad se limita a permisos vigentes comprobados en Oracle. La copia global puede conservar datos que esa persona no pueda consultar.

Ver [acceso y permisos](acceso-multiusuario.md), [guardado y roadmap](roadmap.md) y [actividades y prueba oficial](actividades-y-prueba-oficial.md). Los guardados escalares son un escritor piloto, pendiente de la prueba institucional real; las actividades siguen siendo locales.
