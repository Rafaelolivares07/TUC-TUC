import sqlite3
from playwright.async_api import async_playwright
import asyncio
import re
import pyperclip

"""
Script para poblar precios de farmacias de forma semi-automática.

Debido a las protecciones anti-bot de sitios como Cruz Verde, este script:
1. Lee medicamentos de la base de datos
2. Para cada medicamento, abre el navegador en modo visible
3. Permite al usuario buscar manualmente el producto
4. El script detecta cuando estás en una página de producto y extrae el precio automáticamente
5. Guarda el precio y URL en la base de datos

Uso:
1. El navegador se abrirá
2. Busca manualmente el producto en la farmacia
3. Haz clic en el producto
4. El script detectará el precio automáticamente
5. Presiona ENTER para continuar al siguiente producto
"""

async def obtener_precio_de_pagina(page):
    """Extrae el precio de la página actual"""
    try:
        precio_text = await page.evaluate(r"""
            () => {
                const elements = Array.from(document.querySelectorAll('*'));
                const preciosConFormato = [];
                const preciosSinFormato = [];

                for (const el of elements) {
                    const text = el.textContent;
                    if (!text || el.children.length > 0 || text.length > 50) continue;

                    const className = el.className || '';
                    const esClasePrice = className.includes('price') || className.includes('Price') ||
                                        className.includes('selling') || className.includes('Selling') ||
                                        className.includes('valor') || className.includes('Valor');

                    // Prioridad 1: Precios con formato de miles (ej: $14.840 o $14,840)
                    const matchMiles = text.match(/\$\s*[\d]{1,3}(?:[.,][\d]{3})+(?:[.,][\d]{2})?/);
                    if (matchMiles && esClasePrice) {
                        const precioStr = matchMiles[0].replace(/[^\d]/g, '');
                        if (parseInt(precioStr) > 500) {
                            preciosConFormato.push(text.trim());
                        }
                    }

                    // Prioridad 2: Precios sin formato pero con clase price y valor > 1000
                    if (!matchMiles && esClasePrice) {
                        const matchSimple = text.match(/\$\s*[\d.,]+/);
                        if (matchSimple) {
                            const precioStr = matchSimple[0].replace(/[^\d]/g, '');
                            // Solo aceptar si es >= 4 dígitos (mínimo $1,000)
                            if (precioStr.length >= 4 && parseInt(precioStr) >= 1000) {
                                preciosSinFormato.push(text.trim());
                            }
                        }
                    }
                }

                // Retornar en orden de prioridad
                if (preciosConFormato.length > 0) return preciosConFormato[0];
                if (preciosSinFormato.length > 0) return preciosSinFormato[0];
                return null;
            }
        """)

        if precio_text:
            # Limpiar el precio
            precio_limpio = re.sub(r'[^\d.]', '', precio_text)
            try:
                precio = float(precio_limpio)
                return precio
            except:
                return None
        return None
    except:
        return None

async def poblar_precios_interactivo():
    """Modo interactivo para poblar precios"""
    conn = sqlite3.connect('medicamentos.db', timeout=10.0)
    cursor = conn.cursor()

    # Obtener lista de farmacias/terceros
    # Filtrar las farmacias conocidas por nombre
    cursor.execute("""
        SELECT id, nombre FROM terceros
        WHERE nombre IN ('Cruz Verde', 'Farmatodo', 'Locatel', 'La Rebaja')
        ORDER BY nombre
    """)
    farmacias = cursor.fetchall()

    print("\nFarmacias disponibles:")
    for i, (id_farm, nombre_farm) in enumerate(farmacias, 1):
        print(f"{i}. {nombre_farm} (ID: {id_farm})")

    farmacia_idx = int(input("\nSelecciona el número de la farmacia: ")) - 1
    farmacia_id, farmacia_nombre = farmacias[farmacia_idx]

    # Obtener medicamentos
    cursor.execute("SELECT id, nombre FROM medicamentos ORDER BY nombre LIMIT 20")
    medicamentos = cursor.fetchall()

    print(f"\n{'='*60}")
    print(f"Poblaremos precios para {len(medicamentos)} medicamentos de {farmacia_nombre}")
    print(f"{'='*60}\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=['--start-maximized']
        )

        context = await browser.new_context(
            viewport=None,
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = await context.new_page()

        # Ir a la farmacia
        urls_farmacias = {
            'Cruz Verde': 'https://www.cruzverde.com.co/',
            'Farmatodo': 'https://www.farmatodo.com.co/',
            'Locatel': 'https://www.locatelcolombia.com/',
            'La Rebaja': 'https://www.larebajavirtual.com/'
        }

        url_base = urls_farmacias.get(farmacia_nombre, 'https://www.google.com/')
        print(f"\nAbriendo navegador en {farmacia_nombre}...")
        await page.goto(url_base, wait_until='domcontentloaded', timeout=60000)
        await page.wait_for_timeout(2000)

        for med_id, med_nombre in medicamentos:
            print(f"\n{'='*60}")
            print(f"Medicamento: {med_nombre}")
            print(f"ID: {med_id}")
            print(f"{'='*60}")

            # Copiar al portapapeles
            pyperclip.copy(med_nombre)

            print(f"\n✓ '{med_nombre}' copiado al portapapeles")
            print(f"\n1. Presiona Ctrl+V en el buscador de {farmacia_nombre} para pegar el nombre")
            print(f"2. Haz clic en el producto para abrir su página")
            print(f"3. El script detectará el precio automáticamente")
            print(f"\nSi NO encuentras el producto, simplemente presiona ENTER sin buscar")

            respuesta_busqueda = input("\nPresiona ENTER cuando estés en la página del producto (o ENTER si no existe): ")

            # Esperar un momento para que cargue
            await page.wait_for_timeout(1000)

            # Obtener URL actual y precio
            url_actual = page.url

            # Verificar si seguimos en la página de inicio o búsqueda (producto no encontrado)
            if url_actual == url_base or 'search' in url_actual or 'buscar' in url_actual:
                print(f"\n⚠ Parece que no navegaste a un producto específico")
                print(f"  URL actual: {url_actual}")
                confirmar = input(f"  ¿Este medicamento está disponible en {farmacia_nombre}? (s/n): ")
                if confirmar.lower() == 'n':
                    print("✓ Medicamento omitido - no disponible")
                    continuar = input("\n¿Continuar con el siguiente medicamento? (s/n): ")
                    if continuar.lower() != 's':
                        break
                    continue
                else:
                    # Usuario dice que sí está disponible pero no navegó
                    print("\n⚠ Por favor navega a la página del producto antes de continuar")
                    input("Presiona ENTER cuando estés en la página del producto: ")
                    await page.wait_for_timeout(1000)
                    url_actual = page.url

                    # Verificar nuevamente
                    if url_actual == url_base or 'search' in url_actual or 'buscar' in url_actual:
                        print("✗ Aún no estás en una página de producto. Saltando medicamento.")
                        continuar = input("\n¿Continuar con el siguiente medicamento? (s/n): ")
                        if continuar.lower() != 's':
                            break
                        continue

            precio = await obtener_precio_de_pagina(page)

            if precio:
                print(f"\n✓ Precio detectado: ${precio:,.0f}")
                print(f"✓ URL: {url_actual}")

                # Verificar si ya existe el precio
                cursor.execute("""
                    SELECT id FROM precios_competencia
                    WHERE medicamento_id = ? AND competidor_id = ?
                """, (med_id, farmacia_id))

                existe = cursor.fetchone()

                if existe:
                    # Actualizar
                    cursor.execute("""
                        UPDATE precios_competencia
                        SET precio = ?, url = ?, fecha_actualizacion = datetime('now')
                        WHERE medicamento_id = ? AND competidor_id = ?
                    """, (precio, url_actual, med_id, farmacia_id))
                    print("✓ Precio actualizado en la base de datos")
                else:
                    # Insertar nuevo (fabricante_id puede ser NULL)
                    cursor.execute("""
                        INSERT INTO precios_competencia
                        (medicamento_id, fabricante_id, competidor_id, precio, url, fecha_actualizacion)
                        VALUES (?, NULL, ?, ?, ?, datetime('now'))
                    """, (med_id, farmacia_id, precio, url_actual))
                    print("✓ Precio guardado en la base de datos")

                conn.commit()
            else:
                print("\n✗ No se pudo detectar el precio")
                print("  ¿Deseas ingresar el precio manualmente? (s/n): ", end='')
                respuesta = input()
                if respuesta.lower() == 's':
                    precio_manual = float(input("  Ingresa el precio: "))
                    cursor.execute("""
                        INSERT OR REPLACE INTO precios_competencia
                        (medicamento_id, fabricante_id, competidor_id, precio, url, fecha_actualizacion)
                        VALUES (?, NULL, ?, ?, ?, datetime('now'))
                    """, (med_id, farmacia_id, precio_manual, url_actual))
                    conn.commit()
                    print("✓ Precio guardado manualmente")

            continuar = input("\n¿Continuar con el siguiente medicamento? (s/n): ")
            if continuar.lower() != 's':
                break

        await browser.close()

    conn.close()
    print(f"\n{'='*60}")
    print("Proceso completado")
    print(f"{'='*60}")

if __name__ == "__main__":
    asyncio.run(poblar_precios_interactivo())
