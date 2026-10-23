import time
import os
import psutil
from rapidocr_onnxruntime import RapidOCR

process = psutil.Process(os.getpid())
ram_init = process.memory_info().rss / (1024 * 1024)

print("=" * 60)
print("BENCHMARK RAPIDOCR EN SERVIDOR AWS EC2")
print("=" * 60)

t0 = time.time()
engine = RapidOCR()
t_init = time.time() - t0
ram_after_engine = process.memory_info().rss / (1024 * 1024)

img_path = "/home/ubuntu/tuctucv2/test_ticket.png"
if not os.path.exists(img_path):
    print(f"ERROR: No se encontró la imagen en {img_path}")
    exit(1)

t1 = time.time()
result, elapse_list = engine(img_path)
t_infer = time.time() - t1
ram_after_infer = process.memory_info().rss / (1024 * 1024)

print(f"Tiempo de carga del modelo en memoria: {t_init:.2f} s")
print(f"Tiempo de lectura e inferencia de la imagen: {t_infer:.2f} s")
if elapse_list:
    print(f"Desglose interno: Detección={elapse_list[0]:.3f}s | Clasificación={elapse_list[1]:.3f}s | Reconocimiento={elapse_list[2]:.3f}s")
print(f"Consumo de RAM: Inicial={ram_init:.1f} MB | Con modelo cargado={ram_after_engine:.1f} MB | Pico inferencia={ram_after_infer:.1f} MB")
print(f"Incremento neto de RAM: +{ram_after_infer - ram_init:.1f} MB")
print("=" * 60)
print(f"RESULTADOS DETECTADOS ({len(result) if result else 0} líneas de texto):")
print("-" * 60)

if result:
    for i, line in enumerate(result):
        box, text, score = line
        print(f"[{i+1:02d}] (Confianza: {score*100:.1f}%) -> {text}")
else:
    print("No se detectó texto en la imagen.")
print("=" * 60)
