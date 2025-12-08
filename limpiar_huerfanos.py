import sqlite3

def limpiar_huerfanos():
    conn = sqlite3.connect('medicamentos.db')
    cursor = conn.cursor()
    
    print("\n" + "="*60)
    print("   BÚSQUEDA Y LIMPIEZA DE REGISTROS HUÉRFANOS")
    print("="*60 + "\n")
    
    tablas_con_medicamento_id = [
        ('MEDICAMENTO_SINTOMA', 'medicamento_id'),
        ('DIAGNOSTICO_MEDICAMENTO', 'medicamento_id'),
        ('RECETAS', 'medicamento_id'),
        ('PRECIOS', 'medicamento_id'),
        ('EXISTENCIAS', 'medicamento_id'),
        ('COMPONENTES_ACTIVOS_SUGERENCIAS', 'medicamento_id'),
        ('PRECIOS_COMPETENCIA_NEW', 'medicamento_id'),
        ('PRECIOS_COMPETENCIA', 'medicamento_id'),
        ('SUGERIR_SINTOMAS', 'medicamento_id')
    ]
    
    total_huerfanos = 0
    
    # PASO 1: Identificar huérfanos
    print("📊 IDENTIFICANDO HUÉRFANOS...\n")
    
    for tabla, columna in tablas_con_medicamento_id:
        query = f"""
            SELECT COUNT(*) as total
            FROM {tabla} t
            LEFT JOIN MEDICAMENTOS m ON t.{columna} = m.id
            WHERE m.id IS NULL
        """
        
        cursor.execute(query)
        count = cursor.fetchone()[0]
        
        if count > 0:
            print(f"❌ {tabla}: {count} registro(s) huérfano(s)")
            total_huerfanos += count
        else:
            print(f"✅ {tabla}: Sin huérfanos")
    
    print(f"\n{'='*60}")
    print(f"   TOTAL HUÉRFANOS ENCONTRADOS: {total_huerfanos}")
    print(f"{'='*60}\n")
    
    if total_huerfanos == 0:
        print("✨ ¡Tu base de datos está limpia! No hay registros huérfanos.\n")
        conn.close()
        return
    
    # PASO 2: Confirmar limpieza
    respuesta = input("¿Deseas ELIMINAR todos los registros huérfanos? (si/no): ").lower().strip()
    
    if respuesta != 'si':
        print("\n❌ Operación cancelada. No se eliminó nada.\n")
        conn.close()
        return
    
    # PASO 3: Eliminar huérfanos
    print("\n🧹 ELIMINANDO REGISTROS HUÉRFANOS...\n")
    
    total_eliminados = 0
    
    for tabla, columna in tablas_con_medicamento_id:
        query = f"""
            DELETE FROM {tabla}
            WHERE {columna} IN (
                SELECT t.{columna}
                FROM {tabla} t
                LEFT JOIN MEDICAMENTOS m ON t.{columna} = m.id
                WHERE m.id IS NULL
            )
        """
        
        cursor.execute(query)
        eliminados = cursor.rowcount
        
        if eliminados > 0:
            print(f"🗑️  {tabla}: {eliminados} registro(s) eliminado(s)")
            total_eliminados += eliminados
    
    conn.commit()
    
    print(f"\n{'='*60}")
    print(f"   ✅ TOTAL ELIMINADOS: {total_eliminados}")
    print(f"{'='*60}\n")
    print("✨ Base de datos limpia. Todos los huérfanos han sido eliminados.\n")
    
    conn.close()

if __name__ == "__main__":
    try:
        limpiar_huerfanos()
    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")