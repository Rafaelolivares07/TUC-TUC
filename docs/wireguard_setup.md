# WireGuard — Setup y Arquitectura

## Concepto
VPN peer-to-peer que hace que equipos remotos se vean como si estuvieran en la misma LAN.
Sin servidor intermediario, sin Render, sin relay. Tráfico directo entre equipos.

## Caso de uso principal
- Rafael accede a BD de Administrator en PC de Pilar (Palmira) desde su oficina (Cali)
- Pilar accede a su empresa desde casa sin AnyDesk ni TeamViewer
- Administrator selecciona la ruta `\\10.0.0.x\BASEDATOSEMPRESAS\` como si fuera red local

## Arquitectura
```
Tu PC (servidor WireGuard — hub)
    IP VPN: 10.0.0.1
    IP pública: 191.95.39.93
    Puerto: 51820 UDP
        ↕
Celular/PC cliente
    IP VPN: 10.0.0.2, 10.0.0.3, etc.
```

## Estado actual (2026-04-19)
- WireGuard instalado en PC Rafael (Windows 11)
- Túnel "administrator" creado con:
  - PrivateKey generada
  - PublicKey: RJ/qDYVcUJfH4FZM1TuXbqfM4xluW2kKs/rNXmnn+wM=
  - Address: 10.0.0.1/24
  - ListenPort: 51820
- Firewall Windows: puerto 51820 UDP abierto
- Prueba con cel pendiente (cel es el router — necesita otra red para probar)

## Config PC (servidor) — túnel administrator
```ini
[Interface]
PrivateKey = 6Gb7fOklADuXVM4KzGHYDkkogrWHS7BRjQ7+8PjoA3c=
Address = 10.0.0.1/24
ListenPort = 51820

[Peer]
# Celular Rafael
PublicKey = GTVNfFe/H3HOVZTtTxot0EZlvzCQZiXIaND36rPdFBw=
AllowedIPs = 10.0.0.2/32
```

## Config celular Android (cliente)
```ini
[Interface]
PrivateKey = (guardada en el cel)
Address = 10.0.0.2/24

[Peer]
PublicKey = RJ/qDYVcUJfH4FZM1TuXbqfM4xluW2kKs/rNXmnn+wM=
Endpoint = 191.95.39.93:51820
AllowedIPs = 10.0.0.0/24
PersistentKeepalive = 25
```

## Para agregar nuevo cliente (ej. Pilar)
1. En el PC de Pilar: instalar WireGuard, crear túnel con Address = 10.0.0.3/24
2. Obtener su PublicKey
3. En tu PC agregar al túnel administrator:
```ini
[Peer]
# PC Pilar
PublicKey = <clave publica de pilar>
AllowedIPs = 10.0.0.3/32
```
4. En el PC de Pilar agregar:
```ini
[Peer]
PublicKey = RJ/qDYVcUJfH4FZM1TuXbqfM4xluW2kKs/rNXmnn+wM=
Endpoint = 191.95.39.93:51820
AllowedIPs = 10.0.0.0/24
PersistentKeepalive = 25
```

## Requisito crítico
Tu IP pública 191.95.39.93 debe ser fija o usar DNS dinámico (No-IP gratuito).
Si cambia, los clientes no pueden encontrar el servidor.

## Negocio
- Instalación y configuración: $400.000–$600.000 única vez por cliente
- Estrategia: primero vender consultas browser (Admin Agent), luego ofrecer WireGuard como upgrade total
- Para hacer independiente al cliente: IP fija del ISP en su ubicación (~sin costo extra) o VPS $5/mes
