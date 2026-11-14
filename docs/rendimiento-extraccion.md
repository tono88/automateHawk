# Extracción por pantalla: cobertura y rendimiento

## Comparación de motores

Se probó el binario oficial Obscura v0.2.7 para Windows x86_64, con renderizado y sin stealth. El archivo descargado se verificó contra el SHA-256 publicado por GitHub Releases. Se conserva fuera del repositorio.

Tres cargas independientes de la pantalla pública de acceso de este tenant de Oracle tardaron 6.56, 5.83 y 5.97 segundos. Las tres produjeron `Maximum call stack size exceeded` en la ejecución del acceso IDCS y terminaron sin campos de usuario y contraseña. No se introdujeron credenciales ni se extrajeron registros con ese motor. Una terminación con código cero no equivale a una pantalla funcional.

El ensayo se puede repetir con `scripts/benchmark_obscura.py RUTA_AL_BINARIO`. Solo devuelve tiempos y disponibilidad de controles. No imprime HTML, redirecciones, cookies ni mensajes completos. Las cifras publicadas por el proyecto Obscura son comparaciones de sus autores; no demuestran una mejora para Oracle ADF.

Fuentes: [repositorio y limitaciones del motor](https://github.com/h4ckf0r0day/obscura), [release probada](https://github.com/h4ckf0r0day/obscura/releases/tag/v0.2.7).

## Métodos implementados

- Exportación de lista desde la interfaz de Oracle, procesada en memoria, en lugar de recorrer cada fila de una tabla virtual.
- Reutilización de la pantalla de consulta entre fichas. No se vuelve al inicio ni se autentica para cada registro.
- Esperas por condiciones del documento renderizado, sin pausa fija de 300 ms en cada observación. Las condiciones que aún no se cumplen tienen espera incremental y límite temporal.
- Conservación del punto de avance por usuario y número oficial. Solo se solicitan fichas pendientes; las incidencias se reintentan separadamente.
- Carga de lectura en segundo plano autorizada al iniciar el lote, limitada a cuatro horas y al máximo absoluto de ocho horas desde el login. El acceso interactivo sigue venciendo tras quince minutos de inactividad; ese vencimiento no abre acceso a la copia ni autoriza escrituras. Cerrar sesión revoca la carga; Pausar carga termina la ficha en curso y conserva el avance. Un reinicio requiere volver a autenticarse, sin guardar contraseñas ni cookies.
- Ritmo y tiempo orientativo restante visibles, calculados sobre hasta cien lecturas exitosas recientes. El estimado no incluye futuras incidencias, reintentos o renovaciones de lista y no garantiza una hora de fin.

Se ensayaron dos ventanas ADF independientes de lectura, cada una con su propia página y consulta reutilizable. Antes de capturar se exige que el número oficial del formulario visible coincida con la oportunidad solicitada. Una reserva por registro impide duplicar trabajo. El trabajador limita a dos operaciones simultáneas en total; las escrituras se rechazan durante una carga de lectura. Las sesiones siguen separadas entre personas. No se bloquean imágenes, pues el vínculo de contacto principal depende de un indicador visual.

## Qué significa completar la cobertura

Se distinguen tres cosas: oportunidades encontradas dentro del alcance de la consulta, fichas efectivamente leídas, y permisos de visualización actualmente vigentes. El vencimiento de un permiso no borra el progreso de extracción. Tampoco certifica que todos los campos de todos los módulos del CRM existan o sean visibles.

El alcance autorizado comprende los tres estados observados en Oracle —Abierta, Inscrito y Perdida— con cierre en 2026. El inventario comienza con doce intervalos mensuales, subdivide aquellos que alcanzan 500 filas y comprueba fecha y estado antes de importarlos. El umbral es conservador respecto a la exportación de 795 filas ya verificada. Si un día y estado siguen alcanzando el umbral, se conserva la información disponible y se declara el intervalo sin resolver; no se certifica cobertura completa por haber llegado al tope del lector. No se presenta como un inventario certificado de todas las oportunidades históricas ni de todas las cuentas. Alcanzar el cien por ciento requiere resolver todas las fichas pendientes del alcance acordado y verificar por separado los módulos, los límites de exportación y las fuentes financieras y académicas externas.

Los campos vacíos observados se mantienen vacíos; no se deducen pagos, fechas de examen, resultados ni decisiones académicas. Una validación de Oracle conserva los datos ya leídos y deja sus módulos bloqueados como pendientes.

## Revisión de exportación ampliada

Se abrió Ver → Columnas → Gestionar Columnas en la lista original: las diecisiete columnas disponibles estaban visibles y la lista de columnas ocultas estaba vacía. Los campos de pruebas, ayuda y contacto ampliado no estaban disponibles para añadir desde ese catálogo. Se canceló el diálogo sin cambiar la configuración. Se incorporaron al lector los dos campos de esa exportación que faltaban: importe de oportunidad y correo del responsable. El importe sigue sin acreditar un pago.

## Mediciones del piloto real

En una carga secuencial de cuarenta fichas, las lecturas promediaron 13.57 segundos y el ritmo global fue 4.42 fichas/minuto. En la muestra inicial de diecinueve fichas con dos ventanas, promediaron 16.87 segundos por lectura y el ritmo global fue 6.66 fichas/minuto, incluido el arranque de ambas ventanas. Esto representa una mejora observada cercana al cincuenta por ciento en fichas por minuto, no una prueba controlada con registros idénticos ni una garantía de duración futura. El paralelismo aumentó el tiempo individual de cada lectura y el consumo de recursos; se mantiene limitado a dos.

Se contrastaron los campos de una ficha de referencia por huellas en memoria: coincidieron los cincuenta y siete campos comparables. El teléfono estaba protegido por el navegador de inspección y no se usó como discrepancia ni se sustituyó por ese texto protegido. Los valores y huellas temporales no se incorporaron al repositorio.

## Limitaciones explícitas del contacto y reparación autorizada

Se verificó un caso en el que Oracle muestra que el contacto fue eliminado o no es accesible para la cuenta. El lector reconoce ese mensaje, cierra el aviso y conserva la oportunidad y las actividades. La limitación se registra por usuario y se muestra sin inventar campos del contacto. Resolver el acceso o la asociación exige revisión en Oracle.

La herramienta de operador `connector/repair-test-call.mjs` requiere autorización explícita, identidad oficial coincidente y Fecha PA/Convocatoria PA realmente vacías con el control habilitado. Solo permite No Aplica, verifica los demás campos y relee el guardado. Los envíos inciertos se revisan sin repetir el guardado. Esta herramienta no se importa en el lector de segundo plano. Se ensayaron dos ventanas independientes con registros distintos; cuatro correcciones verificadas tomaron aproximadamente veinte segundos en la muestra.

Se localizaron informes existentes de UNIS Admisiones 2026 en Análisis, con información de contactos, pruebas y referencias de pago. Algunos trabajan a nivel de contacto y no muestran el número oficial de oportunidad. Su incorporación requiere confirmar la granularidad y los identificadores de enlace; no se fusionan datos financieros o de admisión por coincidencias de nombres.

El informe existente de Matriculados expone ID Campus, ciclo, programa, fecha de matriculación, resultados y monto de matrícula. No muestra número de oportunidad. Antes de cruzarlo con la cartera se debe verificar una relación única con el contacto, ciclo y programa; su título de 2026 no demuestra que cada fecha de matrícula pertenezca a ese año. El informe se inspeccionó sin alterar su definición ni fusionar valores por nombres.
