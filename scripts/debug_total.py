import sys
sys.path.insert(0, '/home/ubuntu/tuctucv2')
from app.services.vision_facturas import get_ocr_engine

engine = get_ocr_engine()
result, _ = engine('/home/ubuntu/tuctucv2/test_ticket.png')
for i, item in enumerate(result):
    box, text, score = item
    ys = [pt[1] for pt in box]
    xs = [pt[0] for pt in box]
    print(f"[{i:02d}] Y={min(ys):.0f}..{max(ys):.0f} X={min(xs):.0f}..{max(xs):.0f} -> {text}")
