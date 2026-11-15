# Roadmap de automateHawk para la gestión del CRM

El objetivo es una interfaz operativa de admisiones similar al Excel del equipo, conectada con Oracle Fusion Sales y respaldada por PostgreSQL. Oracle conserva la autoridad sobre los registros del CRM; automateHawk ofrece consulta consolidada, tareas, formularios y cambios controlados. La inteligencia de negocio se desarrollará después de asegurar cobertura, identidad y calidad de datos.

## Secuencia y criterios de salida

| Etapa | Resultado | Estado de esta entrega | Criterio para avanzar |
|---|---|---|---|
| 1 Persistencia y recuperación | PostgreSQL local, historial de observaciones, respaldo y restauración | Implementado y verificado localmente | Reiniciar sin perder datos; restaurar una copia y comparar registros |
| 2 Interfaz de trabajo | Cartera, filtros por asesor/ciclo/etapa/fecha, paneles por módulo y permisos de campo observados | Piloto implementado; cartera de cierre 2026 recorrida en los tres estados observados | Validar cada columna y entidad con usuarios del proceso; resolver restricciones de acceso en la fuente |
| 3 Gestión sobre Oracle | Edición en lista o formulario, cola, aprobación y escritura verificada | Cola y escritor escalar piloto implementados; prueba institucional real pendiente | Para cada operación: permiso válido, ID estable, control de conflicto, idempotencia, guardado y relectura |
| 4 Sincronización operativa | Lecturas temporizadas, detalle bajo demanda, reconciliación y recuperación de sesión | Inventario completo de 2026, lotes reanudables, cuatro lecturas, pausa, consulta de hasta ocho horas y edición con vencimiento independiente verificados en el piloto | Validar más cuentas y roles reales, mantener reconciliación y medir carga institucional |
| 5 Operación institucional | SSO, cartera por usuario, mínimos privilegios, secretos, soporte, monitoreo y recuperación externa | Login por pantalla y permisos persistentes implementados; SSO y publicación pendientes | Validar autorización institucional por rol y conjunto de datos; pruebas de restauración y operación |
| 6 Inteligencia de negocio | Indicadores históricos y tableros confiables | Solo roadmap | Datos completos por cohorte y definiciones aprobadas; reconciliación de CRM, Campus y pagos |

## Vistas derivadas de la estructura del Excel

Se inspeccionaron solamente los nombres de las hojas y sus encabezados. Las familias de trabajo son Resumen, BBDD, Inscrito a PDA, Matrículas, Entrevistas y numerosas hojas de PDA por fecha, incluida una convocatoria asociada a colegio.

En automateHawk estas familias se representan como vistas de una misma copia normalizada. Las convocatorias y fechas se filtran desde los valores reales consultados; no se duplicará físicamente una tabla por cada fecha. Se incorporan además Asistencia económica, Cambios y Sincronización. Las filas del Excel no se cargan ni se usan para poblar estas vistas.

## Gestión por módulo

- Asesor: asignación y cartera; perfil, suplencias y equipo después de validar identificadores y permisos oficiales.
- Contacto y oportunidad: identidad y correlación por IDs oficiales; una persona puede tener más de una oportunidad, carrera o ciclo. No unir por nombre.
- Pruebas: convocatoria, PDA/PAA, fecha y resolución observadas. Los resultados sensibles y las decisiones académicas requieren roles específicos y aprobación humana.
- Citas y tareas: actividades vinculadas consultadas en su módulo. Antes de modificar, capturar ID de actividad y sus reglas de fechas, responsables y notificaciones.
- Pagos: distinguir importe de oportunidad, inscripción, recibo, transacción y pago confirmado. La razón de retraso de matrícula no acredita un pago. Conciliar con la fuente institucional autorizada.
- Matrícula: distinguir las etapas comerciales 05/06 de la matrícula académica efectiva en Campus.
- Ayuda económica: solicitud, tipo, porcentaje y estado; la aprobación se mantiene en el proceso institucional.

## Política de edición

El perfil local se configura en el servidor; no se selecciona libremente desde la pantalla. El lector consulta. El editor puede registrar propuestas únicamente para campos habilitados por el catálogo y observados como editables en una consulta reciente de Oracle.

Esta entrega permite enviar cambios de nombre, etapa, probabilidad y fecha de cierre mediante el escritor piloto por pantallas. Se almacenan con el valor original, versión, nuevo valor, autor y estado. Los valores confirmados solo se sustituyen tras releer Oracle después de un envío solicitado explícitamente por el usuario. Si Oracle cambia el mismo campo, la propuesta se marca en conflicto. Los campos con formulario se abren por módulo; los campos simples pueden proponer cambios dentro de la lista.

El escritor escalar revalida permisos, compara el valor actual y relee el resultado; requiere la prueba oficial de guardado con responsables. Los escritores de actividades y otros módulos siguen pendientes. No se habilitarán escrituras genéricas sobre cualquier etiqueta de la pantalla.

El perfil local del piloto no equivale a SSO ni a permisos multiusuario de Oracle. La correspondencia de identidad y restricciones por cartera es un requisito de la etapa institucional.

## Inteligencia de negocio futura

Primero se definirán las métricas: conversión por cohorte y ciclo, tiempos entre etapas, carga y atención por asesor, asistencia a pruebas/entrevistas, documentación pendiente, confirmación de pagos y matrícula conciliada. Los denominadores deben reflejar la cobertura completa, no las primeras filas de una consulta parcial.

Después se construirá un modelo analítico separado del operativo: hechos de oportunidades, transiciones, actividades y pagos; dimensiones de fecha, ciclo, carrera, asesor, origen y colegio. Se conservarán cambios de estado con su fecha de observación y se definirán reglas para eventos tardíos, correcciones y reingresos. Las marcas observadas por una consulta no deben presentarse como la hora exacta del evento en Oracle.

Finalmente se evaluarán tableros con filtros, acceso por rol y diccionario de datos. La selección de herramienta de BI y las predicciones quedan pendientes. No se realizarán decisiones de admisión automatizadas a partir de puntuaciones o predicciones.

## Acceso y automatización pendiente

La propuesta de identidad, sesiones y recursos compartidos se detalla en [acceso multiusuario](acceso-multiusuario.md). Node-RED y el mapeo de procesos quedan pendientes; la prioridad actual es completar consultas, hacer visibles los datos reales y validar acceso por persona antes del despliegue institucional.

## Actividades locales

Implementados los formularios de seguimiento, cita e informe de interacción sobre la cartera real, con persistencia separada, edición por versión y estados locales. Los accesos y campos de creación se volvieron a verificar en Oracle cancelando los formularios. La [prueba oficial de actividades](actividades-y-prueba-oficial.md) define los vínculos, catálogos, permisos y confirmaciones pendientes para habilitar el escritor real.

## Cartera global y permisos

La copia activa es única en PostgreSQL, con permisos por usuario y campo guardados con vencimiento. La lista comienza sin filtros por responsable. El login verifica la identidad por pantalla y reutiliza permisos vigentes; el escritor vuelve a verificarlos al guardar. Los detalles de funcionamiento y las limitaciones están en [acceso multiusuario](acceso-multiusuario.md).

La carga masiva usa Exportar de Oracle, consulta todos los estados de 2026 por intervalos y subdivide los intervalos densos. Su manifiesto por usuario se guarda en PostgreSQL; se distingue el inventario del año del detalle disponible por ficha. La lectura por desplazamiento permanece como referencia. La cobertura sigue limitada al filtro aplicado en Oracle; no se presenta como un volcado certificado de todo el CRM.

## Avance en sincronización y medición

Implementados: esperas por condiciones de pantalla, lote reanudable con autorización limitada de lectura en segundo plano, pausa cooperativa, ritmo observado y estimado de duración en la interfaz. Obscura se ensayó en el acceso público de Oracle y no pasó la comprobación de compatibilidad; Chromium continúa siendo el motor operativo. Los resultados y límites se explican en [rendimiento de extracción](rendimiento-extraccion.md).

Próximos criterios de salida: revisar con los responsables los perfiles que Oracle declara inaccesibles y las relaciones sin contacto principal único; validar otras cuentas y roles; confirmar fuentes de recibos, matrícula y asistencia; ampliar el alcance histórico solo si se autoriza. La inteligencia de negocio requiere definiciones de cohorte y fuentes institucionales aprobadas además de la cobertura de oportunidades.

La cola compara la versión de la oportunidad observada al iniciar cada lectura con la versión actual de la copia. Si cambia el registro, su ficha vuelve a quedar pendiente; una lectura concurrente no acredita la versión nueva que aún no había observado. Para lecturas anteriores a este control se compara su finalización con la última versión del historial, sin inventar una versión leída. También se vuelven a consultar fichas con más de 24 horas, para cubrir cambios de contacto que no alteren la oportunidad. Con la consulta periódica activada y una sesión válida, estas fichas se incorporan al lote; desactivar la frecuencia conserva el control manual. Una ficha pendiente puede conservar valores anteriores visibles dentro del permiso de lectura y muestra que requiere actualización. La comparación no constituye una transacción común entre pantallas de Oracle ni reemplaza la verificación al guardar.
