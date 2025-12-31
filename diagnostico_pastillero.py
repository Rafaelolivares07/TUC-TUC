# -*- coding: utf-8 -*-
import psycopg2
import os
import sys
from datetime import datetime

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Conectar a la base de datos PostgreSQL
DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL:
    # Usar URL de producción directamente
    DATABASE_URL = 'postgresql://tuc_tuc_admin:1kfLANdRV90pUXUNQZkNjHg81mBgZR8i@dpg-cu66g4pu0jms738fepq0-a.oregon-postgres.render.com/tuc_tuc'
    print("Usando DATABASE_URL de produccion")

try:
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cursor = conn.cursor()

    print("OK - Conectado a PostgreSQL\n")
    print("=" * 80)
    print("DIAGNÓSTICO DEL PASTILLERO - RECORDATORIOS")
    print("=" * 80)

    ahora = datetime.now()
    print(f"\nHora del servidor: {ahora.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Día de la semana: {ahora.strftime('%A')}\n")

    # Obtener todos los medicamentos del pastillero con recordatorio activo
    cursor.execute('''
        SELECT
            p.id,
            p.usuario_id,
            p.nombre,
            p.cantidad,
            p.horas_entre_tomas,
            p.proxima_toma,
            p.recordatorio_activo,
            t.nombre as usuario_nombre,
            t.telefono,
            t.telegram_chat_id
        FROM pastillero_usuarios p
        INNER JOIN terceros t ON p.usuario_id = t.id
        WHERE p.recordatorio_activo = TRUE
        ORDER BY p.proxima_toma
    ''')

    medicamentos = cursor.fetchall()

    print(f"Total de recordatorios activos: {len(medicamentos)}\n")

    if len(medicamentos) == 0:
        print("⚠️  NO HAY RECORDATORIOS ACTIVOS EN EL PASTILLERO")
        print("\nPosibles causas:")
        print("1. No se han agregado medicamentos al pastillero")
        print("2. Los medicamentos no tienen recordatorio_activo = TRUE")
        print("3. Los medicamentos no tienen proxima_toma configurada")
    else:
        print("-" * 80)

        for i, med in enumerate(medicamentos, 1):
            med_id, usuario_id, nombre, cantidad, horas, proxima_toma, activo, usuario, telefono, chat_id = med

            print(f"\n[{i}] {nombre}")
            print(f"    Usuario: {usuario} (ID: {usuario_id})")
            print(f"    Teléfono: {telefono}")
            print(f"    Telegram Chat ID: {chat_id or 'NO CONFIGURADO ❌'}")
            print(f"    Cantidad restante: {cantidad} pastillas")
            print(f"    Frecuencia: cada {horas} horas")
            print(f"    Recordatorio activo: {'SÍ ✓' if activo else 'NO ✗'}")

            if proxima_toma:
                diferencia = (proxima_toma - ahora).total_seconds() / 60  # minutos

                if diferencia < 0:
                    estado = f"⚠️  VENCIDO hace {abs(int(diferencia))} minutos"
                    print(f"    Próxima toma: {proxima_toma.strftime('%Y-%m-%d %H:%M:%S')}")
                    print(f"    Estado: {estado}")
                    print(f"    🔴 DEBIÓ ENVIARSE RECORDATORIO")
                else:
                    horas_restantes = int(diferencia // 60)
                    minutos_restantes = int(diferencia % 60)
                    print(f"    Próxima toma: {proxima_toma.strftime('%Y-%m-%d %H:%M:%S')}")
                    print(f"    Estado: ⏰ Faltan {horas_restantes}h {minutos_restantes}m")
            else:
                print(f"    Próxima toma: NO CONFIGURADA ❌")

            print("-" * 80)

    # Verificar si hay contactos adicionales configurados
    print("\n\n" + "=" * 80)
    print("CONTACTOS ADICIONALES PARA RECORDATORIOS")
    print("=" * 80 + "\n")

    cursor.execute('''
        SELECT
            pca.usuario_id,
            t_usuario.nombre as usuario_nombre,
            t_contacto.nombre as contacto_nombre,
            t_contacto.telegram_chat_id
        FROM pastillero_contactos_adicionales pca
        INNER JOIN terceros t_usuario ON pca.usuario_id = t_usuario.id
        INNER JOIN terceros t_contacto ON pca.contacto_id = t_contacto.id
    ''')

    contactos = cursor.fetchall()

    if len(contactos) == 0:
        print("ℹ️  No hay contactos adicionales configurados")
    else:
        for contacto in contactos:
            usuario_id, usuario, contacto_nombre, chat_id = contacto
            print(f"Usuario: {usuario}")
            print(f"  → Contacto: {contacto_nombre}")
            print(f"  → Telegram Chat ID: {chat_id or 'NO CONFIGURADO ❌'}")
            print()

    # Verificar configuración de Telegram
    print("\n" + "=" * 80)
    print("CONFIGURACIÓN DE TELEGRAM")
    print("=" * 80 + "\n")

    cursor.execute('SELECT telegram_token, notificaciones_activas FROM CONFIGURACION_SISTEMA WHERE id = 1')
    config = cursor.fetchone()

    if config:
        token, notif_activas = config
        print(f"Token configurado: {'SÍ ✓' if token else 'NO ❌'}")
        print(f"Notificaciones activas: {'SÍ ✓' if notif_activas else 'NO ❌'}")

        if token:
            print(f"Token: {token[:20]}...")
    else:
        print("⚠️  NO HAY CONFIGURACIÓN DE SISTEMA")

    cursor.close()
    conn.close()

    print("\n" + "=" * 80)
    print("FIN DEL DIAGNÓSTICO")
    print("=" * 80)

except Exception as e:
    print(f"\nError: {e}")
    import traceback
    traceback.print_exc()
