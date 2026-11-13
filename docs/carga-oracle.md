# Carga local mediante las pantallas de Oracle

## Estado verificado

Se ejecutó la lectura automatizada de las pantallas de oportunidades y se cargaron 120 filas al portal local. Los registros reales nunca se escribieron en archivos, fixtures, bitácoras del proyecto ni Git. La consulta no guardó ni modificó registros en Oracle.

El alcance es **todos los registros que esta cuenta puede ver, oportunidades abiertas, año actual**. La consulta inicial por propietario y trimestre no representaba ese alcance. Se aplican los filtros desde la búsqueda avanzada de la interfaz, respetando los permisos existentes.

El listado es virtual: Oracle va incorporando filas al desplazarlo. El lector recorre la tabla, reúne las filas y deduplica por Número de oportunidad. El máximo inicial del trabajador es 120 oportunidades por carga. Aunque llegue al final visible, esta versión sigue declarando la carga como parcial porque no puede certificar un total global de Oracle.

## Uso

Abrir **Datos de Oracle** en el portal local y pulsar **Cargar desde Oracle** cuando el trabajador figure conectado. La pantalla se actualiza al terminar y muestra alcance, hora de carga y resultado. El botón se deshabilita cuando el trabajador está desconectado o ya hay una consulta en curso.

El trabajador necesita una sesión vigente en el navegador. En el navegador integrado, las acciones deben ejecutarse dentro de una llamada activa del entorno: no es un servicio autónomo que siga trabajando después de cerrar esta interacción. El adaptador integrado permite ejecutar una carga durante el trabajo asistido. Para atender futuras solicitudes del botón de forma autónoma se necesita mantener en ejecución el trabajador independiente. Después de cerrar la sesión o reiniciar la aplicación puede ser necesario volver a iniciar sesión. No se guarda una contraseña ni un estado autenticado en el repositorio.

## Trabajador independiente opcional

La implementación también incluye un ejecutor Playwright para no depender del navegador integrado. Requiere Node.js compatible con Playwright y sus dependencias:

```sh
npm install
npx playwright install chromium
```

Definir `ORACLE_URL` en el entorno con la dirección institucional normal, sin usuario, contraseña ni parámetros de sesión. Opcionalmente definir `HUB_URL` con el destino local, por defecto `http://127.0.0.1:8765`. Después:

```sh
npm run oracle-worker
```

Se abre una ventana de navegador para iniciar sesión directamente en Oracle. El trabajador espera solicitudes del botón del portal. La autenticación permanece en un contexto efímero: no genera archivos de sesión, capturas, vídeos ni trazas. No automatiza ni evita MFA.

El núcleo de lectura y el adaptador del navegador integrado se validaron con Oracle. El ejecutor Playwright independiente comparte ese núcleo, pero **su autenticación y recorrido completo no se han probado en esta entrega**. La ejecución Docker del servidor sigue pendiente de disponer de su motor activo. El trabajador independiente se ejecuta en el equipo anfitrión, no dentro de ese contenedor.

## Flujo de datos

Botón local → solicitud en memoria → trabajador → navegación y filtros de Oracle → lectura de la tabla visible y desplazamiento → selección de campos → permiso local de carga de un solo uso → sustitución atómica del modelo de lectura → actualización de la pantalla.

La entrega al servidor utiliza exclusivamente loopback. El trabajador no llama API de Oracle ni inspecciona su red, tokens o estado interno. No escribe una exportación intermedia. Solo conserva en memoria los valores necesarios para la vista local.

## Separación y límites

- La sección Oracle es de solo consulta. Sus registros no pasan por los formularios del demo.
- El demo mantiene sus 60 contactos sintéticos y sus propias operaciones.
- Cada fila real representa una oportunidad, no una persona única. No se unen personas por nombre.
- La carga permite nombre del contacto, número y nombre de oportunidad, cuenta, etapa, estado, responsable, segmento, teléfono y fechas visibles. Se excluye el correo del responsable porque no es el correo del aspirante.
- No se infieren ciclo, carrera, pagos, expediente, pruebas, resolución académica ni matrícula desde la etapa de ventas. Esos campos requieren una lectura posterior del detalle y su mapeo confirmado.
- Si la lectura está vacía, la estructura cambia o la sesión falla, se conserva la carga anterior y se indica el fallo. No se muestra una consulta fallida como una cartera vacía actualizada.
- Reiniciar el servidor elimina los datos reales en memoria. La información no se recupera desde un archivo.
- El portal sigue siendo local, sin acceso remoto ni autenticación multiusuario. No publicarlo en red ni usarlo como servicio institucional hasta implementar los controles correspondientes.

## Referencias técnicas

[Documentación de Playwright](https://playwright.dev/docs/intro) y [consideraciones de autenticación](https://playwright.dev/docs/auth). Los archivos autenticados pueden contener material sensible; esta implementación evita crearlos.
