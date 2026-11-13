# Recorridos observados en Oracle Ventas

Exploración autenticada del 12 de noviembre de 2026. Solo se registran estructuras y controles; no registros personales, identificadores de usuario, cookies ni direcciones con parámetros de sesión.

## Entrada y navegación

Acceso institucional → Oracle Identity Cloud → página inicial de Oracle Fusion → pestaña **Ventas**. La página inicial pertenece a `hcmUI`; las acciones comerciales navegan a `crmUI`. No se deben fijar las direcciones completas: contienen parámetros de sesión dinámicos.

La pestaña ofrece Contactos, Oportunidades potenciales, Oportunidades, Actividades, Cuentas, Análisis y otras aplicaciones. La exploración se limitó a los recorridos de admisión descritos abajo.

| Recorrido | Clics observados | Campos y controles inspeccionados | Resultado comprobado |
|---|---|---|---|
| Crear contacto | Ventas → Crear contacto | Nombre y Apellidos obligatorios; segundo nombre, segundo apellido, correo, teléfonos, cuenta, documento, nacimiento, graduación, segmento y dirección | Formulario abierto y cancelado; sin guardado |
| Consultar contactos | Ventas → Contactos → Vista de lista; Mostrar búsqueda avanzada | Buscar, Lista, Mis contactos, Mis contactos de negocios, Mis contactos favoritos; búsqueda guardada Nombre de contacto, Nombre Operador, Buscar, Restablecer, Agregar | Navegación y criterios; no se verificó recuperación de expediente por ID |
| Crear oportunidad | Ventas → Crear oportunidad | Nombre y Fecha de cierre obligatorios; Cuenta, Contacto principal, Probabilidad de ganar, Moneda GTQ, Etapa de ventas | Formulario y catálogo de etapas; cancelado |
| Consultar oportunidades | Ventas → Oportunidades | Buscar, Lista con Mis oportunidades abiertas, Mostrar búsqueda avanzada, Acciones, Crear oportunidad, Guardar y Desechar cambios | Listado inspeccionado; edición y guardado no probados |
| Crear tarea | Ventas → Crear tarea | Asunto y Responsable obligatorios; Actividad se realizará con, Actividad, Estado, Prioridad, Contacto principal, Cuenta, cuatro interacciones y respuestas, Fecha de Seguimiento, Estatus, Telefono Corresponde a, Descripción | Formulario y catálogo de respuesta inspeccionados; cancelado |
| Crear cita | Ventas → Crear cita | Asunto, fechas y horas de inicio/finalización obligatorias; Privada, Ubicación, Type, Subtipo Actividad, Zona horaria, Todo el día, Repetición, Cuenta, Oportunidad, Contacto principal, Mostrar hora como, Definir recordatorio, Descripción | Formulario inspeccionado; cancelado |
| Crear prospecto | Ventas → Crear oportunidad potencial | Contacto existente, Nombre de oportunidad potencial, Cargo, Cuenta existente, Grupo, Grupo de productos, teléfono, correo, Origen, Campaña, Responsable, Dirección; botón Calificar | Formulario inspeccionado; sin calificar ni guardar |
| Informe de interacción | Ventas → Crear informe de interacción | Asunto, Privada, Outcome, fechas y horas, Ubicación, Type, Cuenta, Oportunidad, Oportunidad potencial y Acta de reunión | Formulario inspeccionado; cancelado |

## Catálogos confirmados

Etapa de ventas:

1. 01 - Interesado
2. 02 - Inscrito a prueba
3. 03 - Presente a prueba: resolución
4. 04 - Perdida
5. 05 - Matriculado
6. 06 - Inscrito

La etiqueta de la primera etapa presentaba un espacio adicional en el control real. La interfaz del laboratorio normaliza espacios; un conector debe resolver la opción visible, sin asumir un código interno a partir del texto.

Respuesta Interacción 1: Llamada Contestada, No responde, Número Equivocado, Respuesta Positiva, Respuesta Negativa. Los controles 2 a 4 existen, pero sus catálogos no se desplegaron individualmente. El simulador usa el mismo catálogo como hipótesis. El desplegable Estatus se abrió sin opciones visibles en esa observación; no se inventa un catálogo oficial.

## Columnas observadas

Contactos: Nombre, Cuenta, Cargo, Teléfono, Correo electrónico, Año, Año de graduación Colegio, Año de graduación Universidad, Ciclo de Ingreso y Correo electrónico de contacto.

Oportunidades: Número de oportunidad, nombre y apellido del contacto principal, Nombre, Cuenta, Importe, Fecha de cierre, Éxito, Etapa de ventas, Estado, Segmento, Contacto principal, Responsable, Teléfono, correo del responsable, fechas de creación y última actualización.

## Reglas para automatizar posteriormente

- Usar nombres accesibles y etiquetas, no coordenadas ni identificadores ADF con sesión.
- Esperar el encabezado de la pantalla de destino y el fin de las actualizaciones ADF. En la exploración hubo transiciones en las que la pantalla anterior aún aparecía inmediatamente después del clic.
- Las listas y búsquedas dependen de la cartera y filtros del usuario. Un listado vacío no acredita ausencia global del contacto.
- Resolver contacto y oportunidad mediante un identificador oficial comprobado; no seleccionar por coincidencia de nombre solamente.
- No repetir un guardado por un simple tiempo de espera. Primero recuperar y reconciliar el resultado para evitar duplicados.
- Tras cada escritura, volver a consultar y comparar el registro. No confundir navegación con éxito de guardado.
- No guardar contraseñas, perfiles de navegador, capturas con datos personales ni trazas de red en Git.

## Pendiente de comprobar

Detalle de un expediente conocido, pestañas de datos académicos, nombres técnicos de extensiones, asignación del responsable en contacto/oportunidad, altas y cambios reales, persistencia, deduplicación de Oracle, borrado recuperable, aprobación, auditoría institucional, MFA y límites de concurrencia. El botón Calificar no se ejecutó. No se enviaron comunicaciones ni se crearon citas reales.
