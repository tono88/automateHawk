# Roadmap de automateHawk para la gestión del CRM

El objetivo es una interfaz operativa de admisiones similar al Excel del equipo, conectada con Oracle Fusion Sales y respaldada por PostgreSQL. Oracle conserva la autoridad sobre los registros del CRM; automateHawk ofrece consulta consolidada, tareas, formularios y cambios controlados. La inteligencia de negocio se desarrollará después de asegurar cobertura, identidad y calidad de datos.

## Secuencia y criterios de salida

| Etapa | Resultado | Estado de esta entrega | Criterio para avanzar |
|---|---|---|---|
| 1 Persistencia y recuperación | PostgreSQL local, historial de observaciones, respaldo y restauración | Implementado y verificado localmente | Reiniciar sin perder datos; restaurar una copia y comparar registros |
| 2 Interfaz de trabajo | Vistas tipo Excel, filtros por asesor/ciclo/etapa/fecha, paneles por módulo y permisos de campo observados | Implementado como piloto; extracción ampliada validada en una muestra | Mapear y probar cada columna, fecha, ciclo y entidad con usuarios del proceso |
| 3 Gestión sobre Oracle | Edición en lista o formulario, cola, aprobación y escritura verificada | Cola y propuestas locales implementadas; escrituras reales pendientes | Para cada operación: permiso válido, ID estable, control de conflicto, idempotencia, guardado y relectura |
| 4 Sincronización operativa | Lecturas temporizadas, detalle bajo demanda, reconciliación y recuperación de sesión | Temporizador y solicitudes implementados; ejecución autónoma y cobertura completa pendientes | Medir duración, carga y errores; probar vencimiento de sesión, reinicios y consultas completas |
| 5 Operación institucional | SSO, cartera por usuario, mínimos privilegios, secretos, soporte, monitoreo y recuperación externa | Pendiente | Validar autorización institucional por rol y conjunto de datos; pruebas de restauración y operación |
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

Esta entrega permite propuestas de nombre, etapa, probabilidad y fecha de cierre. Se almacenan con el valor original, versión, nuevo valor, autor y estado. No se sustituyen los valores confirmados y no se aplica ninguna escritura real automáticamente. Si Oracle cambia el mismo campo, la propuesta se marca en conflicto. Los campos con formulario se abren por módulo; los campos simples pueden proponer cambios dentro de la lista.

El siguiente incremento debe implementar un escritor por operación, revalidar permisos inmediatamente antes de guardar, pedir aprobación cuando corresponda y volver a leer el resultado. No se habilitarán escrituras genéricas sobre cualquier etiqueta de la pantalla.

El perfil local del piloto no equivale a SSO ni a permisos multiusuario de Oracle. La correspondencia de identidad y restricciones por cartera es un requisito de la etapa institucional.

## Inteligencia de negocio futura

Primero se definirán las métricas: conversión por cohorte y ciclo, tiempos entre etapas, carga y atención por asesor, asistencia a pruebas/entrevistas, documentación pendiente, confirmación de pagos y matrícula conciliada. Los denominadores deben reflejar la cobertura completa, no las primeras filas de una consulta parcial.

Después se construirá un modelo analítico separado del operativo: hechos de oportunidades, transiciones, actividades y pagos; dimensiones de fecha, ciclo, carrera, asesor, origen y colegio. Se conservarán cambios de estado con su fecha de observación y se definirán reglas para eventos tardíos, correcciones y reingresos. Las marcas observadas por una consulta no deben presentarse como la hora exacta del evento en Oracle.

Finalmente se evaluarán tableros con filtros, acceso por rol y diccionario de datos. La selección de herramienta de BI y las predicciones quedan pendientes. No se realizarán decisiones de admisión automatizadas a partir de puntuaciones o predicciones.

## Acceso y automatización pendiente

La propuesta de identidad, sesiones y recursos compartidos se detalla en [acceso multiusuario](acceso-multiusuario.md). Node-RED y el mapeo de procesos quedan pendientes; la prioridad actual es completar consultas, hacer visibles los datos reales y validar acceso por persona antes del despliegue institucional.
