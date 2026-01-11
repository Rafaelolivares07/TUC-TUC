import psycopg2
import json
from datetime import datetime
from decimal import Decimal
import sys

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

DATABASE_URL = "postgresql://tuctuc_user:yG04kXspSIiuHtc6QeW96CFJbm0ICtvt@dpg-d4s28pje5dus7395rd90-a.virginia-postgres.render.com/tuctuc"

print("Intentando conectar a la base de datos...")

try:
    conn = psycopg2.connect(DATABASE_URL)
    print("OK Conexion exitosa!")

    cursor = conn.cursor()

    # Obtener lista de todas las tablas
    cursor.execute("""
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public'
        ORDER BY tablename;
    """)

    tablas = cursor.fetchall()
    print(f"\nTablas encontradas: {len(tablas)}")

    backup_data = {}

    for (tabla,) in tablas:
        print(f"Extrayendo datos de: {tabla}")

        try:
            cursor.execute(f'SELECT * FROM "{tabla}"')
            rows = cursor.fetchall()

            # Obtener nombres de columnas
            column_names = [desc[0] for desc in cursor.description]

            # Convertir a lista de diccionarios
            table_data = []
            for row in rows:
                row_dict = {}
                for i, col_name in enumerate(column_names):
                    value = row[i]
                    # Convertir tipos no serializables
                    if isinstance(value, datetime):
                        value = value.isoformat()
                    elif isinstance(value, bytes):
                        value = value.hex()
                    elif isinstance(value, Decimal):
                        value = float(value)
                    row_dict[col_name] = value
                table_data.append(row_dict)

            backup_data[tabla] = {
                'columns': column_names,
                'rows': table_data,
                'count': len(table_data)
            }

            print(f"   OK {len(table_data)} registros extraidos")

        except Exception as e:
            print(f"   ERROR en tabla {tabla}: {e}")
            continue

    # Guardar backup en JSON
    backup_filename = f"backup_tuctuc_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(backup_filename, 'w', encoding='utf-8') as f:
        json.dump(backup_data, f, indent=2, ensure_ascii=False)

    print(f"\nBackup completado: {backup_filename}")
    print(f"Total de tablas respaldadas: {len(backup_data)}")

    total_rows = sum(table['count'] for table in backup_data.values())
    print(f"Total de registros: {total_rows}")

    cursor.close()
    conn.close()

except psycopg2.OperationalError as e:
    print(f"\nERROR de conexion: {e}")
    print("\nLa base de datos esta suspendida y no acepta conexiones.")
    print("Necesitas reactivarla para poder hacer el backup.")

except Exception as e:
    print(f"\nERROR inesperado: {e}")
    import traceback
    traceback.print_exc()
