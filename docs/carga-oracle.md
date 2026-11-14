# Carga de Oracle por pantallas

El despliegue actual utiliza login por pantalla, cartera global y permisos persistentes. Iniciar los tres servicios con `docker compose up --build -d`, ingresar en el portal y utilizar Actualizar desde Oracle o Completar datos de la cartera. El trabajador interno ejecuta las solicitudes con el contexto aislado del usuario. No se requiere acceso a APIs de Oracle.

La primera entrada sin permisos vigentes solicita una lectura; las entradas posteriores reutilizan permisos hasta su vencimiento. La navegación normal usa PostgreSQL. La consulta usa Todos los registros que puedo ver, los estados Abierta/Inscrito/Perdida y fechas de cierre de 2026. Un plan de intervalos mensuales subdivide las exportaciones que alcanzan 500 filas, evita usar una exportación truncada como inventario completo y verifica que las filas pertenezcan al intervalo solicitado. No equivale a una sincronización certificada de todo el CRM. Los campos no leídos y la ausencia de una fila en una carga parcial no acreditan una revocación ni un borrado.

La carga masiva usa la acción Acciones → Exportar de la lista de Oracle. El archivo HTML de Excel se procesa en memoria y se elimina del área temporal en memoria del trabajador. Se incorporan las diecisiete columnas verificadas, incluido el importe comercial y el correo del responsable. El importe comercial no acredita un pago. El lector deduplica por número oficial de oportunidad; no usa APIs de Oracle. La lectura por desplazamiento se conserva como referencia del recorrido. El detalle se abre por ese número, se expanden módulos y se consultan las actividades visibles. Cada resultado se persiste antes de continuar. La carga por lotes cede el turno entre expedientes para permitir otras consultas y escrituras.

El servidor bloquea la importación directa, tickets y reclamación de trabajos desde clientes autenticados. El antiguo ejecutor independiente y el adaptador CUA se conservan como referencia del recorrido, pero no son el mecanismo de carga del despliegue autenticado. El secreto de comunicación del trabajador se genera fuera de Git y su servicio no publica puertos.

Los fallos conservan la copia anterior. Una sesión vencida exige ingresar de nuevo; no se conservan contraseñas para repetir el acceso. La visibilidad se limita a permisos vigentes comprobados en Oracle. La copia global puede conservar datos que esa persona no pueda consultar.

Ver [acceso y permisos](acceso-multiusuario.md), [guardado y roadmap](roadmap.md) y [actividades y prueba oficial](actividades-y-prueba-oficial.md). Los guardados escalares son un escritor piloto, pendiente de la prueba institucional real; las actividades siguen siendo locales.


## Recuperación de detalles pendientes

La carga usa un registro de avance por usuario y número oficial en PostgreSQL. Cada lectura admite tres intentos; un fallo deja esa oportunidad pendiente y permite continuar con las demás. Tres oportunidades consecutivas fallidas pausan el lote para evitar insistir durante una caída. La expiración de sesión detiene la lectura inmediatamente y requiere volver a ingresar, sin guardar credenciales.

Completar datos de la cartera retoma las oportunidades sin una extracción ampliada confirmada, incluyendo los fallos anteriores. Los registros confirmados no se descargan otra vez por haber reiniciado el servidor. El estado de extracción no concede acceso a valores cuyos permisos vencieron: la renovación del permiso de consulta es independiente. Si vence la autorización básica durante un lote largo, se vuelve a consultar la lista antes de continuar.

Los filtros Estado de extracción permiten revisar Detalles por descargar y Lecturas con incidencias. El contador distingue recuperados, pendientes e incidencias; un lote terminado con incidencias no equivale a una cartera completa. Los valores anteriores se conservan ante errores de lectura. Los reintentos se aplican exclusivamente a consultas; las escrituras inciertas en Oracle nunca se repiten automáticamente.

El adaptador abre Resumen explícitamente al entrar a una oportunidad, porque Oracle puede conservar Contactos u otra pestaña del registro anterior. Tampoco vuelve a alternar una búsqueda avanzada que ya está desplegada.


Si Oracle exige completar una selección al cambiar de sección, el lector conserva los campos ya verificados y marca los módulos de contacto/actividades como pendientes. No introduce valores supuestos ni guarda el formulario. Las lecturas parciales se distinguen de las completas y quedan al final del siguiente lote, después de los registros aún no consultados. La selección obligatoria debe corregirse en Oracle con un valor oficial para permitir consultar las secciones bloqueadas.

La apertura de Exportar utiliza la flecha del botón dividido Acciones. El cambio de rango respeta un intervalo válido durante la edición y espera los reajustes de los filtros de Oracle antes de verificar fechas y estados. La espera observa el fin de las actualizaciones POST disparadas desde la pantalla y un breve período estable; no espera la conexión GET persistente, ni consulta respuestas o APIs. Se limita a la configuración de intervalos; el lector de fichas conserva las esperas por condiciones de pantalla.
