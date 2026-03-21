# Proyectos de Rafael — Mapa General
_Actualizado: 2026-03-21_

Rafael tiene tres proyectos activos en desarrollo. Este documento sirve de mapa para orientar a Claude en cualquier sesión.

---

## Proyecto 1 — TUC TUC (app principal)
**Ruta local**: `C:\Users\RAFAEL OLIVARES\Documents\MiAppMedicamentos\`
**Repo git**: este mismo proyecto
**Deploy**: Render (producción) + local Flask para desarrollo

### Descripción
Plataforma multi-módulo: transporte TUC TUC, restaurantes, tiendas, domótica, CRM vendedor, asistencia remota.
- Backend: Python / Flask / PostgreSQL
- Frontend: HTML + vanilla JS + Leaflet

### Documentación disponible en `docs/`
| Archivo | Qué cubre |
|---|---|
| `estrategia_comercial.md` | Pricing, vendedores, ciclo de venta, CRM |
| `vendedor_crm_desarrollo.md` | Módulo CRM `/vendedor` — técnico |
| `vendedor_manual.md` | Manual del vendedor |
| `restaurante_desarrollo.md` | Módulo restaurante |
| `restaurante_usuario.md` | Manual usuario restaurante |
| `tienda_desarrollo.md` / `tienda_usuario.md` | Módulo tienda |
| `domotica_desarrollo.md` / `domotica_usuario.md` | Módulo domótica |
| `captura_chat_desarrollo.md` | Sistema de captura de ideas y chat bridge |
| `convenios_desarrollo.md` | Módulo convenios |
| `asistencia_remota_desarrollo.md` / `_usuario.md` | Módulo asistencia remota |
| `vfp_administrator_pilar.md` | Proyecto VFP SAR — cliente Pilar Peralta |
| `contabilidad_desarrollo.md` / `_usuario.md` | Módulo contabilidad |

---

## Proyecto 2 — TangTechnologies
**Ruta local**: `C:\Users\RAFAEL OLIVARES\Documents\TangTechnologies\`
**Tipo**: Aplicación web PHP (sin framework)
**Servidor**: AWS EC2 — IP `3.128.192.211`
**URL producción**: `http://3.128.192.211/tangtechnologies/menuprincipal.php`

### Descripción
Sistema de gestión empresarial para un cliente. Módulos identificados:
- Administración de usuarios (`adminusuarios.php`)
- Asignación de aires (`asignarnuevoaire.php`)
- Asignación de teléfonos (`asignartelefono.php`)
- Login (`login.php`)
- Sistema de backups (`backup_trigger.php`)

### Notas técnicas
- PHP puro con FPDF para PDFs
- Backups manejados vía scripts
- Acceso servidor: AWS EC2, acceso vía SSM (Systems Manager) — sin SSH directo
- El servidor usa PowerShell para comandos remotos vía SSM

### Estado
En mantenimiento activo. Pendiente revisar qué desarrollos hay en curso.

---

## Proyecto 3 — Administrator (VFP / SAR)
**Ruta local proyecto VFP**: `C:\S.A.R\PROYECTO\`
**Ruta scripts Python de apoyo**: `C:\S.A.R\`
**Tipo**: Aplicativo Visual FoxPro compilado — sistema contable/administrativo empresarial

### Descripción
Sistema de gestión empresarial construido en Visual FoxPro. Módulos: inventarios, compras, contabilidad, facturación. Rafael lo instala y mantiene en empresas clientes.

### Cliente activo: Pilar Peralta
- BD cliente: `C:\D\Pilar Peralta\basedatosempresas\`
- Tabla facturas Allegra: `prod_fact1.dbf`
- Ver detalle completo en `docs/vfp_administrator_pilar.md`

### Notas técnicas
- Los archivos `.scx` / `.SCT` son binarios — se modifican con scripts Python en `C:\S.A.R\`
- En equipos del cliente NO está instalado VFP — solo los ejecutables compilados
- Rafael tiene años de experiencia en VFP — no necesita explicaciones básicas

---

## Mapa de directorios Claude (memorias y contexto)
```
C:\Users\RAFAEL OLIVARES\.claude\projects\
  └── C--Users-RAFAEL-OLIVARES-Documents-MiAppMedicamentos\
        └── memory\
              ├── MEMORY.md                  ← índice principal
              ├── SESION_ACTIVA.md           ← estado de última sesión
              ├── project_vfp_pilar.md       ← contexto VFP rápido
              ├── user_rafael_perfil.md      ← quién es Rafael
              ├── feedback_*.md              ← reglas de colaboración
              └── project_*.md              ← contextos de proyectos
```

---

## Nota importante para Claude
Cuando Rafael abre Claude Code en `C:\Users\RAFAEL OLIVARES` (sin subcarpeta), generalmente es para trabajar en VFP (SAR) o TangTechnologies. Cuando está en `C:\Users\RAFAEL OLIVARES\Documents\MiAppMedicamentos`, es TUC TUC. Las memorias de Claude Code solo se sincronizan con el proyecto activo — por eso el contexto de VFP/TangTechnologies no aparecía en las memorias de TUC TUC.
