# UNIS Intelligent Process Hub

Portal local de admisiones para **Oracle Fusion Cloud Sales, apartado Ventas**. Incluye una carga de oportunidades desde las pantallas de Oracle, una cartera demo tipo Excel y un simulador de seis recorridos comerciales. El repositorio no contiene registros institucionales, archivos fuente, credenciales ni sesiones.

## Datos de Oracle

La sección **Datos de Oracle** muestra oportunidades consultadas mediante un navegador automatizado, con alcance y hora de carga. La copia actual de 120 oportunidades se guarda en PostgreSQL 18 y se recupera después de reiniciar. Los datos reales, respaldos y secretos están fuera de Git.

La interfaz incorpora vistas de base, pruebas y convocatorias, entrevistas y citas, pagos, ayuda económica y matrícula. El detalle se consulta por oportunidad; los campos no leídos permanecen marcados como no consultados. La muestra inicial de detalle ampliado es limitada y no representa cobertura de toda la cartera.

El editor local puede registrar propuestas en lista para campos permitidos y observados como editables. Las propuestas quedan en una cola persistente y **todavía no se aplican al CRM**. El lector no puede proponer cambios. Estos perfiles locales no sustituyen SSO ni permisos por cartera de una instalación multiusuario.

La consulta continúa siendo parcial, con un máximo inicial de 120 oportunidades por recorrido. La copia hace upsert por número oficial y no elimina filas ausentes en cargas parciales. El temporizador de lectura es configurable y necesita un trabajador conectado con sesión vigente.

Consultar [carga, trabajador y límites](docs/carga-oracle.md) para repetir la consulta y configurar el ejecutor independiente opcional. El núcleo y el adaptador integrado fueron probados contra Oracle; el ejecutor Playwright independiente requiere validar su propio inicio de sesión y recorrido.

## Ejecutar

Con Python 3.11 o posterior y Docker Desktop iniciado, desde la raíz del repositorio:

```sh
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m scripts.provision_local
.venv/Scripts/python -m scripts.run_local
```

Abrir http://127.0.0.1:8765. Ver [PostgreSQL y recuperación](docs/postgresql.md). `python -m app.server` sin configuración de base mantiene el modo de memoria para pruebas, sin propuestas persistentes.

Con Docker Desktop iniciado:

```sh
docker compose up --build -d
```

Los puertos se publican únicamente en el equipo local. PostgreSQL utiliza un volumen persistente. Los contenedores de PostgreSQL y del servidor web fueron iniciados y validados en esta entrega. El trabajador de navegador es un proceso separado y necesita sesión activa.

## Qué se puede probar

- Cartera con identidad fija al desplazar columnas, filtros por asesor, facultad, ciclo y etapa, búsqueda y paginación.
- Indicadores y distribución calculados sobre los aspirantes filtrados. La distribución muestra oportunidades actuales por etapa; no pretende ser conversión histórica.
- Crear, consultar y editar contactos, prospectos, oportunidades, tareas, citas e informes de interacción.
- Cambiar etapas comerciales, asignar responsables de prueba, programar entrevistas y registrar cuatro interacciones de seguimiento.
- Borrar registros sintéticos sin relaciones; los vinculados requieren retirar primero sus relaciones.
- Bitácora local de las operaciones y control de versiones para evitar sobrescribir cambios concurrentes.

Los 60 aspirantes y sus colegios se generan por código, sin usar filas reales ni distribuciones derivadas de ellas. Los correos son `@example.invalid`. No se incluyen CUI, documentos, resultados académicos detallados ni contraseñas. No hay importación de Excel, telemetría, fuentes externas ni servicios de IA.

**En los formularios del demo, usar únicamente datos ficticios.** Sus cambios y su bitácora siguen en memoria y se pierden al reiniciar. La copia real y las propuestas se conservan por separado en PostgreSQL.

## Alcance de la fidelidad

La exploración real verificó navegación, nombres de controles y las seis etapas de ventas. Todos los formularios reales se cancelaron sin guardar. El simulador reproduce esos recorridos y una selección de campos; **no es una réplica completa de Oracle Fusion**, no acredita sus reglas, permisos o guardado y no hace que la automatización se pueda trasladar sin validación.

Los campos de admisión tomados del esquema del Excel están identificados como “Excel / propuesta · mapeo real pendiente”. La etapa comercial y la resolución académica son campos independientes: cambiar uno no determina el otro.

Este servidor es exclusivamente local, sin autenticación multiusuario ni publicación en red. Admite `HUB_MODE=local` o `demo`; rechaza otros modos. Antes de producción se requieren identidad institucional, permisos por cartera, controles operativos y validación completa del conector. La lectura actual no habilita escrituras reales en Oracle.

Consultar el [roadmap completo](docs/roadmap.md), la [estrategia de sincronización](docs/sincronizacion.md), [PostgreSQL y respaldos](docs/postgresql.md), [recorridos y evidencias](docs/recorridos-oracle.md) y [criterios de transición](docs/validacion.md).

## Pruebas

```sh
python -m unittest discover -s tests -v
node --test tests/connector.test.mjs
.venv/Scripts/python -m scripts.verify_postgres
.venv/Scripts/python -m scripts.backup_local --verify
```

Las pruebas usan solo datos ficticios y verifican el demo, la separación de fuentes, la importación atómica protegida, la conservación de la carga anterior ante fallos, la deduplicación de filas virtuales y los límites de campos. No acceden a Oracle.
