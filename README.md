# UNIS Intelligent Process Hub

Laboratorio de admisiones para **Oracle Fusion Cloud Sales, apartado Ventas**. Incluye una cartera tipo Excel y un simulador de los seis recorridos inspeccionados en el portal. No se conecta a Oracle y no contiene registros institucionales, archivos fuente, credenciales ni sesiones.

## Ejecutar

Con Python 3.11 o posterior, desde la raíz del repositorio:

```sh
python -m app.server
```

Abrir http://127.0.0.1:8765. No necesita instalar dependencias. Si ese puerto está ocupado, utilizar `python -m app.server --port 8766`.

Con Docker Desktop iniciado:

```sh
docker compose up --build -d
```

El puerto se publica únicamente en el equipo local. Docker no es necesario para probar la aplicación. El contenedor no monta archivos ni volúmenes de datos.

## Qué se puede probar

- Cartera con identidad fija al desplazar columnas, filtros por asesor, facultad, ciclo y etapa, búsqueda y paginación.
- Indicadores y distribución calculados sobre los aspirantes filtrados. La distribución muestra oportunidades actuales por etapa; no pretende ser conversión histórica.
- Crear, consultar y editar contactos, prospectos, oportunidades, tareas, citas e informes de interacción.
- Cambiar etapas comerciales, asignar responsables de prueba, programar entrevistas y registrar cuatro interacciones de seguimiento.
- Borrar registros sintéticos sin relaciones; los vinculados requieren retirar primero sus relaciones.
- Bitácora local de las operaciones y control de versiones para evitar sobrescribir cambios concurrentes.

Los 60 aspirantes y sus colegios se generan por código, sin usar filas reales ni distribuciones derivadas de ellas. Los correos son `@example.invalid`. No se incluyen CUI, documentos, resultados académicos detallados ni contraseñas. No hay importación de Excel, telemetría, fuentes externas ni servicios de IA.

**Usar únicamente datos ficticios.** Todos los cambios y la bitácora viven en memoria del servidor y se pierden al reiniciarlo. La fecha de corte de la demostración es el 12 de noviembre de 2026. Se comparte el mismo estado entre pestañas locales mientras el servidor funciona.

## Alcance de la fidelidad

La exploración real verificó navegación, nombres de controles y las seis etapas de ventas. Todos los formularios reales se cancelaron sin guardar. El simulador reproduce esos recorridos y una selección de campos; **no es una réplica completa de Oracle Fusion**, no acredita sus reglas, permisos o guardado y no hace que la automatización se pueda trasladar sin validación.

Los campos de admisión tomados del esquema del Excel están identificados como “Excel / propuesta · mapeo real pendiente”. La etapa comercial y la resolución académica son campos independientes: cambiar uno no determina el otro.

Este servidor de laboratorio no tiene autenticación y no está preparado para datos reales ni publicación en red. `HUB_MODE` distinto de `demo` impide arrancar. Antes de producción se requieren identidad institucional, permisos de cartera, almacenamiento y auditoría persistentes, controles operativos y un conector de interfaz validado.

Consultar [recorridos y evidencias](docs/recorridos-oracle.md), [arquitectura adaptada](docs/arquitectura.md) y [criterios de transición](docs/validacion.md).

## Pruebas

```sh
python -m unittest discover -s tests -v
```

Las pruebas verifican altas, cambios y bajas de las seis entidades, referencias, fechas, etapas, correos de laboratorio, duplicados, conflictos de versión y protección de las rutas locales. No acceden a Oracle.
