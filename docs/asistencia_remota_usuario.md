# Manual de Usuario — Asistencia Remota (TUC TUC Remote)

**Módulo:** Asistencia Remota
**Versión:** 1.0
**Última actualización:** 2026-03-14
**Audiencia:** Dueños de negocio, usuarios finales que necesitan soporte técnico

---

## ¿Qué es la Asistencia Remota?

La Asistencia Remota de TUC TUC permite que un técnico de soporte vea tu pantalla y la controle de forma segura desde cualquier lugar del mundo, sin necesidad de que estés en el mismo lugar. Funciona a través de internet y no requiere instalar programas complejos.

**¿Para qué sirve?**
- Recibir soporte técnico sin que el técnico tenga que desplazarse
- Que el técnico configure tu negocio en TUC TUC directamente
- Resolver dudas mostrando en vivo cómo funciona algo
- Atención rápida cuando algo no funciona como debería

---

## Cómo iniciar una sesión de soporte

La asistencia remota tiene 3 pasos: descargar el programa, ejecutarlo, y compartir el código con tu técnico.

### Paso 1 — Descargar el programa agente

1. Desde tu panel de administrador de TUC TUC, ve a la sección **🖥️ Soporte** (en tiendas) o **Asistencia Remota** (en el menú de administración).
2. Haz clic en el enlace **"Descargar agente (.exe)"**.
3. Guarda el archivo `AsistenciaTucTuc.exe` en tu computador (puede guardarse en Escritorio o Descargas, donde prefieras).

> **Nota importante:** Este programa solo necesitas descargarlo una vez. La próxima vez que necesites soporte, simplemente vuelve a ejecutarlo.

### Paso 2 — Ejecutar el programa

1. Haz doble clic sobre `AsistenciaTucTuc.exe`.
2. Si Windows muestra una advertencia de seguridad ("Windows protegió tu PC"), haz clic en **"Más información"** y luego en **"Ejecutar de todas formas"**. Esto es normal para programas que no están publicados en la tienda de Microsoft.
3. En unos segundos aparece una ventana pequeña de fondo oscuro con un código de 6 dígitos en color verde, con el formato `XXX-XXX` (por ejemplo: `847-293`).

```
┌─────────────────────────┐
│    TUC TUC Remote       │
│                         │
│   Tu código de sesión:  │
│                         │
│       847-293           │
│                         │
│ Comparte este código    │
│ con el técnico          │
└─────────────────────────┘
```

4. El programa también muestra en la barra de tareas que está corriendo en segundo plano.

> **Importante:** Cada vez que ejecutas el programa, genera un código diferente. El código es de un solo uso y es único para esta sesión.

### Paso 3 — Compartir el código con el técnico

1. Comunícate con el técnico de soporte (por WhatsApp, teléfono, chat, o como tengan acordado).
2. Dile el código de 6 dígitos que aparece en la ventana (por ejemplo: `847-293`).
3. El técnico lo ingresa en su panel de visor y se conecta a tu pantalla.
4. Una vez conectado, el técnico puede ver tu pantalla y manejarla con su mouse y teclado.

---

## Durante la sesión

- **Tu pantalla se comparte en tiempo real.** El técnico ve exactamente lo que tú ves.
- **El técnico puede hacer clic, escribir y usar el teclado** como si estuviera frente a tu computador.
- **Tú ves todo lo que hace el técnico** — puedes seguir el proceso en tu pantalla en tiempo real.
- **Puedes retomar el control en cualquier momento** simplemente moviendo tu mouse o escribiendo. El técnico y tú comparten el control.
- **Para terminar la sesión:** cierra la ventana negra de TUC TUC Remote que apareció en el Paso 2, o presiona la X. Al cerrar el programa, la conexión se corta inmediatamente.

---

## Acceso del técnico (panel de visor)

El técnico usa un panel web en **https://tuc-tuc-remote.onrender.com** donde:
1. Ingresa su token de acceso (lo tiene el equipo de soporte TUC TUC)
2. Ingresa el código `XXX-XXX` que tú le compartiste
3. Se conecta y ve tu pantalla

> Si eres parte del equipo de soporte TUC TUC y quieres acceder al panel del técnico, puedes hacerlo desde el menú de administración → Asistencia Remota → enlace al visor.

---

## Preguntas frecuentes

**¿Es seguro?**
Sí. La conexión se establece solo cuando tú compartes el código. Cada sesión tiene un código aleatorio diferente que expira al cerrar el programa. Nadie puede conectarse sin que tú hayas compartido ese código.

**¿El técnico puede ver mis contraseñas?**
El técnico ve tu pantalla completa, igual que si estuviera sentado frente a ti. No compartas contraseñas en pantalla mientras la sesión esté activa, igual que no lo harías en persona.

**¿Necesito internet?**
Sí. El programa usa tu conexión a internet para enviar la imagen de tu pantalla al servidor relay. Una conexión estándar de hogar o empresa es suficiente.

**¿Qué pasa si se corta el internet?**
El programa intenta reconectarse automáticamente. Si la conexión vuelve, la sesión se restablece sin necesidad de hacer nada.

**¿Funciona en Mac o Linux?**
El archivo `.exe` es solo para Windows. Si usas Mac o Linux, contacta al equipo de soporte para una solución alternativa.

**¿El técnico puede ver mi pantalla sin que yo lo sepa?**
No. El programa solo corre cuando tú lo ejecutas manualmente. Al cerrarlo, todo para. No hay ningún proceso corriendo en segundo plano si no abriste el programa.

---

## Solución de problemas comunes

| Problema | Solución |
|---|---|
| Windows bloquea el programa | Clic en "Más información" → "Ejecutar de todas formas" |
| No aparece la ventana con el código | Esperar 10-15 segundos; el programa se conecta al servidor |
| El técnico dice que el código no funciona | Verifica que estás compartiendo los 6 dígitos correctos (el código cambia cada vez que abres el programa) |
| La sesión se corta sola | El programa reconecta automáticamente; si no, ciérralo y ábrelo de nuevo |
| El programa se cierra solo | Puede haber un error de conexión; vuelve a abrirlo y comparte el nuevo código |

---

## ¿Dónde está la opción en mi panel de tienda?

En el panel de administración de tu tienda TUC TUC, busca la pestaña **🖥️ Soporte** en la barra de pestañas superior. Desde ahí encuentras el botón de descarga y el enlace al visor para técnicos.
