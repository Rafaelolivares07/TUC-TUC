import sys
sys.path.insert(0, '/home/ubuntu/tuctucv2')
from app.services.vision_facturas import get_ocr_engine
from app.db import get_db_connection

engine = get_ocr_engine()
img_path = "/home/ubuntu/tuctucv2/test_d1.png"
result, elapse = engine(img_path)

print("=" * 60)
print(f"RAW OCR OUTPUT ({len(result) if result else 0} líneas):")
print("=" * 60)
if result:
    for i, item in enumerate(result):
        box, text, score = item
        ys = [pt[1] for pt in box]
        xs = [pt[0] for pt in box]
        print(f"[{i:02d}] Y={min(ys):.0f}..{max(ys):.0f} X={min(xs):.0f}..{max(xs):.0f} (Conf: {score*100:.1f}%) -> {text}")

# Check what products exist in DB for Negocio 1
print("\n" + "=" * 60)
print("PRODUCTOS EN BD (Negocio 1):")
print("=" * 60)
conn = get_db_connection()
prods = conn.execute("SELECT id, nombre, costo FROM productos WHERE negocio_id = 1 ORDER BY id ASC").fetchall()
for p in prods[:20]:
    print(f"ID {p['id']}: {p['nombre']} (Costo: {p['costo']})")
conn.close()
