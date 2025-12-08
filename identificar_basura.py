import sqlite3
import json

def identificar_basura():
    conn = sqlite3.connect('medicamentos.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("\n" + "="*60)
    print("   IDENTIFICANDO POSIBLE BASURA EN MEDICAMENTOS")
    print("="*60 + "\n")
    
    # Query con TODOS los filtros de exclusión
    query = """
        SELECT 
            m.id,
            m.nombre,
            m.presentacion,
            m.concentracion
        FROM medicamentos m
        WHERE 
            -- ✅ DEBE estar en tabla precios (sino excluir)
            EXISTS (
                SELECT 1 FROM precios p 
                WHERE p.medicamento_id = m.id
            )
            -- ❌ PERO con precio = 0 (no validados)
            AND NOT EXISTS (
                SELECT 1 FROM precios p 
                WHERE p.medicamento_id = m.id 
                AND p.precio > 0
            )
            -- ❌ NO tienen componente activo (no son medicamentos reales)
            AND m.componente_activo_id IS NULL
            -- ❌ NO tienen síntomas relacionados (no están en sistema diagnóstico)
            AND NOT EXISTS (
                SELECT 1 FROM medicamento_sintoma ms 
                WHERE ms.medicamento_id = m.id
            )
            -- ❌ NO son componente activo de otros medicamentos
            AND NOT EXISTS (
                SELECT 1 FROM medicamentos m2 
                WHERE m2.componente_activo_id = m.id
            )
            -- ❌ NO tienen existencias (no se han comprado/vendido)
            AND NOT EXISTS (
                SELECT 1 FROM existencias e 
                WHERE e.medicamento_id = m.id
            )
        ORDER BY m.nombre
    """
    
    cursor.execute(query)
    medicamentos = cursor.fetchall()
    
    if len(medicamentos) == 0:
        print("✨ ¡No se encontró basura! Todos los medicamentos cumplen al menos un criterio de utilidad.\n")
        conn.close()
        return
    
    # Crear lista compacta
    lista = []
    
    for med in medicamentos:
        # Construir nombre completo
        nombre_completo = med['nombre']
        if med['concentracion']:
            nombre_completo += f" {med['concentracion']}"
        if med['presentacion']:
            nombre_completo += f" {med['presentacion']}"
        
        lista.append({
            "id": med['id'],
            "nombre": nombre_completo
        })
    
    # Guardar en JSON
    with open('posible_basura.json', 'w', encoding='utf-8') as f:
        json.dump(lista, f, ensure_ascii=False, indent=2)
    
    print(f"🗑️  POSIBLE BASURA ENCONTRADA: {len(lista)} medicamento(s)\n")
    print(f"📄 Archivo creado: posible_basura.json\n")
    
    # Mostrar primeros 20 para revisión rápida
    print("📋 PRIMEROS 20 REGISTROS:\n")
    for i, med in enumerate(lista[:20], 1):
        print(f"   {i}. [{med['id']}] {med['nombre']}")
    
    if len(lista) > 20:
        print(f"\n   ... y {len(lista) - 20} más (ver archivo JSON)\n")
    
    print("\n💡 SIGUIENTE PASO:")
    print("   1. Revisa el archivo 'posible_basura.json'")
    print("   2. Identifica patrones en los nombres")
    print("   3. Dime qué patrones ves para crear reglas adicionales\n")
    
    conn.close()

if __name__ == "__main__":
    try:
        identificar_basura()
    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
        import traceback
        traceback.print_exc()