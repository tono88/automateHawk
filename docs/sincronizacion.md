# Estrategia de sincronización del piloto

## Recomendación

Para la integración actual por pantallas se recomienda una estrategia híbrida: PostgreSQL atiende las consultas del usuario; el trabajador lee Oracle por intervalo, bajo demanda y para verificar cambios. No se consulta Oracle por cada clic. La copia muestra cuándo se observó cada registro y qué detalle falta.

Como hipótesis inicial del piloto: 15 minutos para la cartera activa, 30 minutos como vigencia de los permisos observados del detalle y una reconciliación completa diaria cuando exista un recorrido capaz de certificar cobertura total. No son intervalos universales del mercado ni un SLA: se deben ajustar al volumen, duración del recorrido, concurrencia permitida y resultados de las pruebas.

## Implementado

- Intervalo configurable de 5 a 240 minutos, guardado en PostgreSQL. Inicialmente desactivado para no consultar sin un trabajador operativo.
- El temporizador solicita lectura solo si el trabajador está conectado y no hay un trabajo pendiente o en ejecución.
- Solicitud de cartera o detalle de una oportunidad desde el portal.
- Cola serial de consulta; confirmación explícita de carga y conservación de la última copia si falla la lectura.
- Upsert por número oficial; una consulta parcial nunca elimina registros no vistos.
- Huella de contenido, versión e historia al detectar cambios. Una vuelta al estado anterior genera otra versión histórica.
- Propuestas de edición separadas. Un cambio observado en el valor de origen produce un conflicto en la propuesta pendiente.

La relectura tras una escritura se implementará junto con los escritores reales. La reconciliación completa diaria permanece pendiente: no se simula una consulta completa con las primeras 120 filas.

## Evolución a eventos

Oracle documenta eventos de negocio de creación, modificación y eliminación, e integración mediante su adaptador de CX Sales. Eso permitiría evaluar una sincronización por eventos más eficiente si UNIS habilita los componentes, permisos y licencias necesarios. La documentación del producto no confirma que esta instalación los tenga disponibles.

Mientras no exista ese acceso, el trabajador debe tratar las pantallas como un recurso limitado: una sesión dedicada, concurrencia acotada, pausas ante fallos de sesión y reintentos limitados. Se priorizarán detalles que el usuario solicita y cambios pendientes sobre recorridos amplios. Antes de producción deben implementarse arrendamiento de trabajos, recuperación de procesos y métricas de demora.

Fuentes oficiales: [Oracle Manage Business Events](https://docs.oracle.com/en/cloud/saas/sales/faaps/Managing_Business_Events.html) y [capacidades del adaptador CX Sales](https://docs.oracle.com/en/cloud/paas/integration-cloud/sales-adapter/oracle-sales-cloud-capabilities.html).
