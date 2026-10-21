with open('app/blueprints/compras.py', 'r', encoding='utf-8') as f:
    text = f.read()

pos1 = text.find('# Enviar mensaje al chat interno')
pos2 = text.find('_enviar_telegram_negocio(conn, chat_id', pos1)
end_line = text.find('\n', pos2) + 1
old_block = text[pos1:end_line]

new_block = '''# Enviar mensaje al chat interno
        if oc['conversacion_id']:
            if nuevo_estado == 'confirmada':
                msg_chat = f"✅ He confirmado la Orden #{oc['numero_oc']}. Entrega estimada: {fecha_entrega or 'Pronta'} ({franja or 'Por confirmar'}). Total: {_formatear_moneda(total_confirmado)}."
            else:
                msg_chat = f"⚠️ He revisado la Orden #{oc['numero_oc']} y propongo los siguientes cambios pendientes de su aprobación:\\n" + "\\n".join(cambios_resumen)
            if observaciones_prov:
                msg_chat += f"\\nNota: {observaciones_prov}"

            conn.execute("""
                INSERT INTO mensajes (remitente_id, destinatario_id, mensaje, tipo, conversacion_id, estado, fecha)
                VALUES (%s, %s, %s, 'texto', %s, 'pendiente', CURRENT_TIMESTAMP)
            """, (oc['proveedor_id'], oc['negocio_id'], msg_chat, oc['conversacion_id']))

        # Notificar por Telegram al negocio si está configurado
        try:
            from .negocios import _enviar_telegram_negocio
            chat_id = conn.execute("SELECT telegram_chat_id FROM terceros WHERE id = %s", (oc['negocio_id'],)).fetchone()
            if chat_id and chat_id['telegram_chat_id']:
                if nuevo_estado == 'confirmada':
                    t_msg = (
                        f"🟢 <b>Orden de Compra Confirmada #{oc['numero_oc']}</b>\\n"
                        f"Proveedor: <b>{oc['proveedor_nombre']}</b>\\n"
                        f"📅 Entrega estimada: {fecha_entrega or 'Pronta'} ({franja or ''})\\n"
                        f"💰 Total confirmado: <b>{_formatear_moneda(total_confirmado)}</b>"
                    )
                else:
                    t_msg = (
                        f"⚠️ <b>Propuesta de cambios en OC #{oc['numero_oc']}</b>\\n"
                        f"Proveedor: <b>{oc['proveedor_nombre']}</b>\\n"
                        f"Requiere tu aprobación:\\n" + "\\n".join(cambios_resumen) + "\\n"
                        f"Total propuesto: <b>{_formatear_moneda(total_confirmado)}</b>"
                    )
                _enviar_telegram_negocio(conn, chat_id['telegram_chat_id'], t_msg)
'''

text = text[:pos1] + new_block + text[end_line:]

with open('app/blueprints/compras.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Second block fixed.")
