# UNIS Intelligent Process Hub

Portal local de admisiones para **Oracle Fusion Cloud Sales, apartado Ventas**. Incluye una carga de oportunidades desde las pantallas de Oracle, una cartera demo tipo Excel y un simulador de seis recorridos comerciales. El repositorio no contiene registros institucionales, archivos fuente, credenciales ni sesiones.

## Datos de Oracle

La sección **Datos de Oracle** muestra oportunidades consultadas mediante un navegador automatizado, con alcance y hora de carga. Se validó una carga real de 120 oportunidades. Los valores reales existen únicamente en memoria del equipo: no se escriben en Git ni archivos intermedios y desaparecen al reiniciar el servidor.

La sección real es de **solo consulta** y permanece separada de los datos sintéticos. El botón **Cargar desde Oracle** solicita otra consulta cuando el trabajador está conectado y su sesión está vigente. Esta versión carga un máximo inicial de 120 oportunidades y siempre declara el resultado como parcial.

Consultar [carga, trabajador y límites](docs/carga-oracle.md) para repetir la consulta y configurar el ejecutor independiente opcional. El núcleo y el adaptador integrado fueron probados contra Oracle; el ejecutor Playwright independiente requiere validar su propio inicio de sesión y recorrido.

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

El puerto se publica únicamente en el equipo local. Docker no es necesario para probar la aplicación. El contenedor no monta archivos ni volúmenes de datos. El trabajador de navegador se ejecuta en el anfitrión y necesita su sesión activa. La ejecución de Docker todavía no se validó porque su motor estaba detenido.

## Qué se puede probar

- Cartera con identidad fija al desplazar columnas, filtros por asesor, facultad, ciclo y etapa, búsqueda y paginación.
- Indicadores y distribución calculados sobre los aspirantes filtrados. La distribución muestra oportunidades actuales por etapa; no pretende ser conversión histórica.
- Crear, consultar y editar contactos, prospectos, oportunidades, tareas, citas e informes de interacción.
- Cambiar etapas comerciales, asignar responsables de prueba, programar entrevistas y registrar cuatro interacciones de seguimiento.
- Borrar registros sintéticos sin relaciones; los vinculados requieren retirar primero sus relaciones.
- Bitácora local de las operaciones y control de versiones para evitar sobrescribir cambios concurrentes.

Los 60 aspirantes y sus colegios se generan por código, sin usar filas reales ni distribuciones derivadas de ellas. Los correos son `@example.invalid`. No se incluyen CUI, documentos, resultados académicos detallados ni contraseñas. No hay importación de Excel, telemetría, fuentes externas ni servicios de IA.

**En los formularios del demo, usar únicamente datos ficticios.** Sus cambios y su bitácora viven en memoria del servidor y se pierden al reiniciarlo. La fecha de corte de la demostración es el 12 de noviembre de 2026. Se comparte el mismo estado entre pestañas locales mientras el servidor funciona. Los registros de Oracle tienen su propio almacén en memoria, sin edición ni mezcla con el demo.

## Alcance de la fidelidad

La exploración real verificó navegación, nombres de controles y las seis etapas de ventas. Todos los formularios reales se cancelaron sin guardar. El simulador reproduce esos recorridos y una selección de campos; **no es una réplica completa de Oracle Fusion**, no acredita sus reglas, permisos o guardado y no hace que la automatización se pueda trasladar sin validación.

Los campos de admisión tomados del esquema del Excel están identificados como “Excel / propuesta · mapeo real pendiente”. La etapa comercial y la resolución académica son campos independientes: cambiar uno no determina el otro.

Este servidor es exclusivamente local, sin autenticación multiusuario ni publicación en red. Admite `HUB_MODE=local` o `demo`; rechaza otros modos. Antes de producción se requieren identidad institucional, permisos por cartera, controles operativos y validación completa del conector. La lectura actual no habilita escrituras reales en Oracle.

Consultar [recorridos y evidencias](docs/recorridos-oracle.md), [arquitectura adaptada](docs/arquitectura.md) y [criterios de transición](docs/validacion.md).

## Pruebas

```sh
python -m unittest discover -s tests -v
node --test tests/connector.test.mjs
```

Las pruebas usan solo datos ficticios y verifican el demo, la separación de fuentes, la importación atómica protegida, la conservación de la carga anterior ante fallos, la deduplicación de filas virtuales y los límites de campos. No acceden a Oracle.
