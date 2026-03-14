# Manual de Usuario — Domótica (TUC TUC Smart Home)

**Módulo:** Domótica
**Versión:** 1.1
**Última actualización:** 2026-03-14
**Audiencia:** Propietarios de inmuebles registrados en TUC TUC

---

## ¿Qué es la Domótica en TUC TUC?

El módulo de Domótica te permite controlar los dispositivos eléctricos de tu propiedad (enchufes, luces, ventiladores, aires acondicionados) desde cualquier lugar usando tu celular o computador. También puedes crear **programaciones automáticas** para que los dispositivos se enciendan o apaguen solos según horarios o condiciones como el nivel de batería solar.

---

## Cómo acceder a tu panel de domótica

### Opción 1 — Desde Mis Propiedades

1. Ve a `https://tuc-tuc.onrender.com/mis-propiedades`
2. Inicia sesión con tu número de celular
3. En la lista de propiedades, busca la propiedad que tiene domótica configurada
4. Haz clic en el botón **💡 Domótica** de esa card
5. El panel abre directamente con esa propiedad seleccionada

### Opción 2 — Acceso directo

Ve a `https://tuc-tuc.onrender.com/domotica` e inicia sesión si se te solicita.

---

## Panel de control

Al entrar al panel verás:
- Un **selector de propiedad** en la parte superior — si tienes varias propiedades con dispositivos, puedes cambiar entre ellas
- Las **tarjetas de cada switch** — cada una representa un enchufe o dispositivo que puedes controlar

### Tarjeta de switch

Cada tarjeta muestra:
- El **ícono del dispositivo** (ventilador, enchufe, lámpara, etc.)
- El **nombre** del dispositivo (visible debajo del ícono)
- El **estado actual**: encendido (verde) o apagado (gris)

**Para encender o apagar**: toca o haz clic en la tarjeta. El cambio se aplica de inmediato vía la nube Tuya. Si el dispositivo está en WiFi y conectado, el estado cambia en 1-2 segundos.

---

## Temporizador

Puedes encender un dispositivo por un tiempo determinado y que se apague solo:

1. Toca la tarjeta del dispositivo para abrir el modal de detalle
2. Busca la sección **Temporizador**
3. Escribe el número de minutos
4. Clic en **Activar** — el dispositivo se enciende y se apaga automáticamente cuando termina el tiempo

---

## Programaciones

Las programaciones permiten que los dispositivos se enciendan o apaguen automáticamente en días y horarios específicos.

**Ejemplo**: Encender el ventilador de lunes a viernes a las 7:00 AM y apagarlo a las 6:00 PM.

Para crear una programación:
1. Toca la tarjeta del switch → abre el modal de detalle
2. Sección **Programaciones** → clic en **+ Agregar**
3. Selecciona: hora, minutos, días de la semana, y acción (encender o apagar)
4. Guarda

Las programaciones activas tienen un punto verde. Puedes desactivarlas temporalmente sin borrarlas.

---

## Automatizaciones

Las automatizaciones permiten que los dispositivos reaccionen a condiciones del sistema (como el nivel de batería de un banco solar).

**Ejemplo**: Encender el enchufe del cargador de laptops cuando la batería solar supera el 90%, y apagarlo cuando baja del 40%.

Esta función es avanzada y generalmente la configura el equipo técnico de TUC TUC. Comunícate si necesitas ajustar estos parámetros.

---

## Indicador de presencia

Si tu propiedad tiene el sistema de detección de presencia configurado, verás en el panel cuándo fue la última vez que se detectó actividad. Este indicador se usa para automatizaciones que reaccionan a si hay o no personas presentes (por ejemplo, apagar el ventilador cuando la sala queda vacía).

---

## Preguntas frecuentes

**¿Por qué el switch no responde?**
El dispositivo puede estar sin internet. Verifica que el enchufe inteligente tenga señal WiFi. Si el ícono de estado dice "offline", el dispositivo no está conectado a la nube Tuya.

**¿Puedo controlar desde el celular fuera de casa?**
Sí. El control es 100% en la nube — funciona desde cualquier red de internet, no necesitas estar en el WiFi de la casa.

**¿Cuántos dispositivos puedo tener?**
No hay límite técnico en la plataforma. El equipo de TUC TUC configura los dispositivos inicialmente.

**¿Puedo controlar dispositivos de otra propiedad mía?**
Sí. Si tienes varias propiedades con domótica configurada, usa el selector de propiedad en la parte superior del panel para cambiar entre ellas.

**¿Puedo darle acceso a otra persona a mi domótica?**
Por ahora el acceso es por número de celular del propietario registrado. Comunícate con el equipo TUC TUC si necesitas acceso compartido.

---

## Solución de problemas

| Problema | Probable causa | Qué hacer |
|---|---|---|
| "Sin acceso" al entrar al panel | No estás logueado o no eres propietario | Ir a `/mis-propiedades` y hacer login |
| Switch no responde | Dispositivo offline (sin WiFi) | Verificar conexión del enchufe inteligente |
| No aparecen mis dispositivos | Propiedad sin dispositivos configurados | Contactar soporte TUC TUC |
| Estado no actualiza en pantalla | Problema de sincronización | Recargar la página |
