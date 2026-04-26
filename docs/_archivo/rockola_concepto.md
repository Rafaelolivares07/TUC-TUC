# Tuc Tuc Rockola — Concepto y Especificación

## Qué es
Módulo independiente de TUC TUC que convierte cualquier negocio en una rockola gestionada digitalmente. Es un producto comerciable por separado (se vende como módulo adicional a restaurantes, bares, discotecas, etc.).

---

## Actores

| Actor | Rol |
|---|---|
| **Dueño / Admin del negocio** | Activa la rockola, configura precio y límites, gestiona su biblioteca, controla el reproductor |
| **Cliente** | Compra el derecho a poner una canción, la sube y la posiciona en la cola |
| **Dispositivo reproductor** | El dispositivo del local que tiene el audio activo (celular, tablet, PC) |

---

## Configuración por el dueño (desde su dashboard TUC TUC)

- Activar / desactivar la rockola para su negocio
- Definir **precio por canción** (aparece en la carta como producto)
- Definir **duración máxima permitida** por canción (en minutos)
- Asociar una **carpeta de canciones propias** (biblioteca del negocio)
- Ver el **enlace / QR** de la rockola para imprimir el afiche promocional
- Generar un **código de reproductor** para autorizar un dispositivo del local

---

## Flujo del cliente

1. El cliente escanea el QR del afiche (o lo ve en la carta digital)
2. Agrega **"Rockola — $X"** a su pedido como cualquier otro producto
3. Al confirmar el pedido queda registrado un **crédito de 1 canción**
4. El cliente accede a la URL de la rockola, sube su MP3 (respetando el límite de duración configurado)
5. Puede **posicionar su canción en la cola con drag and drop** — nadie puede mover la canción de otro cliente
6. Si quiere poner otra canción, debe agregar otro "Rockola" a su pedido
7. Si decide no usar el crédito, puede solicitar que se lo **devuelvan** (se elimina el producto del pedido)

---

## Cola de reproducción

- **Orden**: definido por drag and drop — cada cliente mueve solo su canción
- **Regla**: no se puede adelantar a una canción que ya está sonando
- **Canciones del dueño**: el dueño puede reordenar las suyas libremente con drag and drop
- **Autoplay**: cuando no hay canciones de clientes en cola, la rockola reproduce automáticamente la playlist del dueño en el orden que él definió
- **Regla canción = usuario**: nadie toca la canción de otro

---

## Dispositivo reproductor — sesión transferible

- El **primer dispositivo** que abre la rockola con el código de reproductor se convierte en el activo (el que suena)
- El audio sale por ese dispositivo (y de allí a los parlantes por Bluetooth, cable, etc.)
- Si el dueño necesita cambiar de dispositivo:
  1. Genera un nuevo código (o usa el mismo) desde su dashboard
  2. Abre la URL de la rockola en el nuevo dispositivo con ese código
  3. El nuevo dispositivo toma el rol de reproductor activo
- El código **no expone credenciales** del negocio — solo da acceso a reproducir y ver la cola
- El dueño puede **revocar o regenerar** el código en cualquier momento

---

## Funciones del reproductor

- Play / Pause
- Skip (siguiente canción)
- Control de volumen
- Shuffle (solo aplica a la playlist del dueño)
- Vista de la cola completa
- Indicador de canción actual y siguiente

---

## Biblioteca del negocio

- El dueño asocia una carpeta de canciones al activar la rockola
- Las canciones que los clientes suben **quedan guardadas en la biblioteca del negocio**
- El dueño puede:
  - Organizarlas
  - Eliminarlas
  - Incluirlas en su playlist de autoplay
- Esto le da valor acumulativo al módulo — la biblioteca crece con el tiempo

---

## Integración con TUC TUC

- La canción aparece en la **carta del restaurante** como producto normal con su precio
- Se suma a la cuenta de la mesa como cualquier otro ítem
- El crédito queda amarrado al pedido — sin pago no hay derecho a subir canción
- El módulo se activa/desactiva por negocio desde el dashboard existente

---

## Modelo comercial

- **Para el negocio**: cada canción que pone un cliente genera ingreso directo ($1.000 COP ejemplo)
- **Para TUC TUC**: el módulo Rockola se vende como producto adicional (suscripción mensual o licencia)
- **Identidad propia**: afiche con QR personalizado por negocio — marketing orgánico

---

## Formatos de audio soportados (fase inicial)
- MP3 y similares de solo audio (sin video)

---

## Almacenamiento de archivos

Los archivos MP3 **no se almacenan en el servidor** — cada canción que sube un cliente se descarga automáticamente al dispositivo reproductor del local.

- El servidor solo maneja cola, metadatos y derechos (quién pagó qué)
- El reproductor es browser puro — sin instalar nada
- La descarga automática al dispositivo es transparente para el dueño
- El dueño acumula su biblioteca en la carpeta de descargas de su dispositivo

---

## Acceso de clientes
- La URL de la rockola es **pública** — cualquiera que escanee el QR del afiche puede subir una canción pagando
- No requiere login ni cuenta
- El QR de mesa es para gestión del pedido (cuenta de la mesa); el QR de rockola es independiente

## Modelo comercial del módulo
- Es un **add-on** al plan TUC TUC del negocio
- Los negocios que ya pagan TUC TUC lo adquieren como valor agregado adicional

## Transferencia del archivo al reproductor
- El cliente sube el MP3 al servidor (en tránsito)
- El reproductor (browser del local) lo recibe en tiempo real vía WebSocket
- El reproductor lo descarga automáticamente a la carpeta `rockola_tuctuc` del dispositivo del local
- Objetivo: el negocio acumula una biblioteca propia cada vez más amplia con las canciones que los clientes van dejando

## Cambio de dispositivo reproductor
- El servidor **no guarda copia** de los archivos — la biblioteca vive en el dispositivo del local
- Al cambiar de dispositivo se muestra una advertencia:
  > "Tu biblioteca de canciones está en el dispositivo anterior (carpeta `rockola_tuctuc`). Si ya tienes esa carpeta en el nuevo dispositivo, tus canciones están disponibles de inmediato. Si no, cópialas antes de cambiar."
- Fase inicial: gestión manual por parte del dueño

## Límites de archivo
- Duración máxima absoluta: **5 minutos** (hardcodeado, no configurable)
- El dueño puede configurar un límite menor desde su dashboard (ej. 3 minutos)
- Formato: MP3 y similares de solo audio (sin video)

---
*Documento creado: 2026-04-22*
