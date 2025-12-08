import sqlite3
from playwright.async_api import async_playwright
import asyncio
import re
import pyperclip

"""
Script para completar URLs faltantes en precios_competencia
y validar/actualizar precios existentes.

Este script:
1. Busca registros en precios_competencia que tienen precio pero no URL
2. Para cada uno, abre el navegador y te permite buscar el producto
3. Compara el precio detectado con el precio guardado
4. Guarda el URL y opcionalmente actualiza el precio
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
            precio_limpio = re.sub(r'[^\d.]', '', precio_text)
            try:
                precio = float(precio_limpio)
                return precio
            except:
                return None
        return None
    except:
        return None

async def completar_urls():
    """Modo interactivo para completar URLs faltantes"""
    conn = sqlite3.connect('medicamentos.db', timeout=10.0)
    cursor = conn.cursor()

    # Obtener registros sin URL pero con precio
    cursor.execute("""
        SELECT
            pc.id,
            pc.medicamento_id,
            pc.competidor_id,
            pc.fabricante_id,
            pc.precio,
            m.nombre as medicamento,
            t.nombre as farmacia,
            f.nombre as fabricante
        FROM precios_competencia pc
        INNER JOIN medicamentos m ON pc.medicamento_id = m.id
        INNER JOIN terceros t ON pc.competidor_id = t.id
        LEFT JOIN fabricantes f ON pc.fabricante_id = f.id
        WHERE (pc.url IS NULL OR pc.url = '')
        AND pc.precio IS NOT NULL
        AND pc.precio > 0
        ORDER BY t.nombre, m.nombre
    """)

    registros = cursor.fetchall()

    if not registros:
        print("\n✓ No hay registros sin URL que necesiten completarse")
        conn.close()
        return

    print(f"\n{'='*70}")
    print(f"Encontrados {len(registros)} registros con precio pero sin URL")
    print(f"{'='*70}")

    # Agrupar por farmacia
    por_farmacia = {}
    for registro in registros:
        farmacia = registro[6]  # Índice 6 ahora es farmacia
        if farmacia not in por_farmacia:
            por_farmacia[farmacia] = []
        por_farmacia[farmacia].append(registro)

    print("\nRegistros por farmacia:")
    for farmacia, regs in por_farmacia.items():
        print(f"  - {farmacia}: {len(regs)} medicamentos")

    print("\n¿Qué farmacia quieres procesar?")
    farmacias_lista = list(por_farmacia.keys())
    for i, farmacia in enumerate(farmacias_lista, 1):
        print(f"{i}. {farmacia} ({len(por_farmacia[farmacia])} medicamentos)")

    farmacia_idx = int(input("\nSelecciona el número: ")) - 1
    farmacia_seleccionada = farmacias_lista[farmacia_idx]
    registros_a_procesar = por_farmacia[farmacia_seleccionada]

    print(f"\n{'='*70}")
    print(f"Procesaremos {len(registros_a_procesar)} medicamentos de {farmacia_seleccionada}")
    print(f"{'='*70}")

    # URLs de farmacias
    urls_farmacias = {
        'Cruz Verde': 'https://www.cruzverde.com.co/',
        'Farmatodo': 'https://www.farmatodo.com.co/',
        'Locatel': 'https://www.locatelcolombia.com/',
        'La Rebaja': 'https://www.larebajavirtual.com/'
    }

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

        url_base = urls_farmacias.get(farmacia_seleccionada, 'https://www.google.com/')
        print(f"\nAbriendo navegador en {farmacia_seleccionada}...")
        await page.goto(url_base, wait_until='domcontentloaded', timeout=60000)
        await page.wait_for_timeout(2000)

        actualizados = 0
        omitidos = 0

        for registro in registros_a_procesar:
            pc_id, med_id, comp_id, fab_id, precio_guardado, med_nombre, farmacia, fabricante = registro

            print(f"\n{'='*70}")
            print(f"Medicamento: {med_nombre}")
            if fabricante:
                print(f"Fabricante:  {fabricante}")
            else:
                print(f"Fabricante:  (sin especificar)")
            print(f"Precio guardado: ${precio_guardado:,.0f}")
            print(f"ID en precios_competencia: {pc_id}")
            print(f"{'='*70}")

            # Construir nombre completo para búsqueda
            nombre_busqueda = f"{med_nombre} {fabricante}" if fabricante else med_nombre

            # Copiar al portapapeles
            pyperclip.copy(nombre_busqueda)

            print(f"\n✓ '{nombre_busqueda}' copiado al portapapeles")
            print(f"\n1. Presiona Ctrl+V en el buscador de {farmacia} para pegar el nombre")
            print(f"2. Haz clic en el producto para abrir su página")
            print(f"3. El script detectará el precio y comparará")

            respuesta = input("\nPresiona ENTER cuando estés en la página del producto (o 'saltar' para omitir): ")

            if respuesta.lower() == 'saltar':
                print("⊘ Medicamento omitido")
                omitidos += 1
                continue

            await page.wait_for_timeout(1000)
            url_actual = page.url

            # Verificar si navegó a un producto
            if url_actual == url_base or 'search' in url_actual or 'buscar' in url_actual:
                print(f"\n⚠ No navegaste a un producto específico")
                omitir = input("¿Omitir este medicamento? (s/n): ")
                if omitir.lower() == 's':
                    print("⊘ Medicamento omitido")
                    omitidos += 1
                    continue
                else:
                    print("Por favor navega al producto...")
                    input("Presiona ENTER cuando estés listo: ")
                    await page.wait_for_timeout(1000)
                    url_actual = page.url

            # Detectar precio
            precio_detectado = await obtener_precio_de_pagina(page)

            print(f"\n{'─'*70}")
            print(f"📊 COMPARACIÓN:")
            print(f"   Precio guardado:   ${precio_guardado:,.0f}")

            if precio_detectado:
                diferencia = precio_detectado - precio_guardado
                porcentaje = (diferencia / precio_guardado * 100) if precio_guardado > 0 else 0

                print(f"   Precio detectado:  ${precio_detectado:,.0f}")
                print(f"   Diferencia:        ${diferencia:,.0f} ({porcentaje:+.1f}%)")

                if abs(porcentaje) < 5:
                    print(f"   ✓ Precios similares (diferencia < 5%)")
                elif abs(porcentaje) < 15:
                    print(f"   ⚠ Diferencia moderada (5-15%)")
                else:
                    print(f"   ⚠⚠ Diferencia significativa (>15%)")
            else:
                print(f"   Precio detectado:  (no detectado)")

            print(f"   URL:               {url_actual}")
            print(f"{'─'*70}")

            # Preguntar qué hacer
            if precio_detectado and abs(porcentaje) > 5:
                accion = input("\n¿Qué quieres hacer? (1=guardar URL solo, 2=actualizar precio y URL, 3=omitir): ")
                if accion == '2':
                    cursor.execute("""
                        UPDATE precios_competencia
                        SET url = ?, precio = ?, fecha_actualizacion = datetime('now')
                        WHERE id = ?
                    """, (url_actual, precio_detectado, pc_id))
                    conn.commit()
                    print(f"✓ URL y precio actualizados")
                    actualizados += 1
                elif accion == '1':
                    cursor.execute("""
                        UPDATE precios_competencia
                        SET url = ?, fecha_actualizacion = datetime('now')
                        WHERE id = ?
                    """, (url_actual, pc_id))
                    conn.commit()
                    print(f"✓ URL guardado (precio sin cambios)")
                    actualizados += 1
                else:
                    print("⊘ Omitido")
                    omitidos += 1
            else:
                # Precio similar o no detectado, solo guardar URL
                cursor.execute("""
                    UPDATE precios_competencia
                    SET url = ?, fecha_actualizacion = datetime('now')
                    WHERE id = ?
                """, (url_actual, pc_id))
                conn.commit()
                print(f"✓ URL guardado")
                actualizados += 1

            continuar = input("\n¿Continuar con el siguiente? (s/n): ")
            if continuar.lower() != 's':
                break

        await browser.close()

    print(f"\n{'='*70}")
    print(f"RESUMEN:")
    print(f"  Actualizados: {actualizados}")
    print(f"  Omitidos:     {omitidos}")
    print(f"  Total:        {len(registros_a_procesar)}")
    print(f"{'='*70}")

    conn.close()

if __name__ == "__main__":
    asyncio.run(completar_urls())
