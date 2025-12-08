import sqlite3
import asyncio
from playwright.async_api import async_playwright
import re

def limpiar_nombre_medicamento(nombre):
    """Limpia el nombre del medicamento para búsqueda"""
    # Remover contenido entre paréntesis
    nombre = re.sub(r'\([^)]*\)', '', nombre)
    # Remover dosificaciones y cantidades
    nombre = re.sub(r'\d+\s*mg|\d+\s*ml|\d+\s*g|x\d+|caja|tableta|capsula|inyección', '', nombre, flags=re.IGNORECASE)
    # Limpiar espacios múltiples
    nombre = ' '.join(nombre.split())
    return nombre.strip()

async def buscar_precio_cruz_verde(medicamento_nombre):
    """Busca el precio de un medicamento en Cruz Verde"""
    nombre_limpio = limpiar_nombre_medicamento(medicamento_nombre)
    print(f"\nBuscando: {nombre_limpio}")

    async with async_playwright() as p:
        # Lanzar navegador con opciones para evadir detección
        browser = await p.chromium.launch(
            headless=False,  # headless=False para ver el proceso
            args=['--disable-blink-features=AutomationControlled']
        )
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='es-CO'
        )
        page = await context.new_page()

        # Ocultar características de automatización
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)

        try:
            # Primero visitar la página principal para establecer cookies
            await page.goto('https://www.cruzverde.com.co/', wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(2000)

            # Construir URL de búsqueda
            search_url = f"https://www.cruzverde.com.co/search?query={nombre_limpio.replace(' ', '%20')}"
            print(f"URL de búsqueda: {search_url}")

            # Navegar a la página de búsqueda
            await page.goto(search_url, wait_until='domcontentloaded', timeout=60000)

            # Esperar a que carguen los resultados
            await page.wait_for_timeout(3000)

            # Cerrar el modal de ubicación si aparece
            try:
                # Buscar el botón "Aceptar" del modal de ubicación
                boton_aceptar = await page.wait_for_selector('button:has-text("Aceptar")', timeout=5000)
                if boton_aceptar:
                    await boton_aceptar.click()
                    print("Modal de ubicacion cerrado")
                    await page.wait_for_timeout(2000)
            except:
                print("No hay modal de ubicacion o ya fue cerrado")

            # Esperar a que aparezcan los productos (carga dinámica)
            # Intentar esperar por un link de producto
            try:
                await page.wait_for_selector('a[href*="/p"]', timeout=10000)
                print("Productos cargados dinamicamente")
            except:
                print("Timeout esperando productos")

            # Tomar screenshot para debug
            await page.screenshot(path='debug_busqueda.png')

            # Guardar HTML para debug
            html_content = await page.content()
            with open('debug_page.html', 'w', encoding='utf-8') as f:
                f.write(html_content)

            # Usar JavaScript para encontrar los productos en el DOM
            # Buscar de forma más directa - cualquier enlace con imagen de producto
            productos_data = await page.evaluate(r"""
                () => {
                    const productos = [];
                    // Buscar imágenes de productos primero (que tengan alt text)
                    const imgs = Array.from(document.querySelectorAll('img[alt]'));
                    imgs.forEach(img => {
                        const alt = img.alt;
                        // Si el alt tiene contenido y no es de decoración
                        if (alt && alt.length > 5 && !alt.includes('logo') && !alt.includes('banner')) {
                            // Buscar el enlace padre o cercano
                            let parent = img.closest('a');
                            if (!parent) {
                                parent = img.parentElement?.closest('a');
                            }
                            if (parent && parent.href && parent.href.startsWith('http') && !parent.href.includes('tel:') && !parent.href.includes('mailto:')) {
                                productos.push(parent.href);
                            }
                        }
                    });
                    return [...new Set(productos)]; // Eliminar duplicados
                }
            """)

            # Filtrar solo URLs que parecen ser productos (contienen /p/ o /producto/)
            # Primero intentar con /p/
            productos_filtered = [url for url in productos_data if '/p/' in url and '/p' in url]

            if not productos_filtered:
                # Si no hay con /p/, filtrar por otros criterios
                excluded_terms = ['club', 'beneficios', 'bases-legales', 'terminos', 'nosotros', 'corporativo', 'productos-mas', 'que-es']
                productos_filtered = [url for url in productos_data if url.count('/') >= 4 and not any(x in url for x in excluded_terms)]

            # Debug: mostrar las primeras URLs filtradas
            if productos_filtered:
                print(f"Primeras URLs filtradas: {productos_filtered[:3]}")

            productos_list = productos_filtered

            if productos_list and len(productos_list) > 0:
                print(f"Productos encontrados: {len(productos_list)} URLs unicas filtradas")
                # Usar la primera URL de producto
                producto_url = productos_list[0]
                productos = True  # Para que continúe el flujo
            else:
                productos = None
                producto_url = None

            if not productos:
                print("No se encontraron productos")
                await browser.close()
                return None

            # Ya tenemos la URL del producto de la evaluación JavaScript anterior
            if producto_url:
                print(f"URL del producto: {producto_url}")

                # Navegar a la página del producto
                await page.goto(producto_url, wait_until='domcontentloaded', timeout=60000)
                await page.wait_for_timeout(3000)

                # Buscar el precio usando JavaScript para ser más flexible
                precio_text = await page.evaluate(r"""
                    () => {
                        // Buscar elementos que contengan "$" y números
                        const elements = Array.from(document.querySelectorAll('*'));
                        for (const el of elements) {
                            const text = el.textContent;
                            // Buscar patrones de precio: $X,XXX o $X.XXX
                            if (text && /\$\s*[\d.,]+/.test(text) && el.children.length === 0) {
                                // Priorizar elementos con clases que sugieren precio
                                const className = el.className || '';
                                if (className.includes('price') || className.includes('Price') ||
                                    className.includes('selling') || className.includes('Selling')) {
                                    return text.trim();
                                }
                            }
                        }
                        // Si no encontramos con clase, buscar cualquier precio
                        for (const el of elements) {
                            const text = el.textContent;
                            if (text && /\$\s*[\d.,]+/.test(text) && el.children.length === 0 && text.length < 20) {
                                return text.trim();
                            }
                        }
                        return null;
                    }
                """)

                if precio_text:
                    # Limpiar el precio (remover $ y comas)
                    precio_limpio = re.sub(r'[^\d.]', '', precio_text)
                    try:
                        precio = float(precio_limpio)
                        print(f"Precio encontrado: ${precio:,.0f}")

                        await browser.close()
                        return {
                            'precio': precio,
                            'url': producto_url,
                            'farmacia': 'Cruz Verde'
                        }
                    except ValueError:
                        print(f"No se pudo convertir el precio: {precio_text}")
                else:
                    print("No se encontro el precio en la pagina del producto")
            # Si no encontramos producto_url, mostrar error
            if not productos:
                print("No se encontro producto_url")

            await browser.close()
            return None

        except Exception as e:
            print(f"Error: {str(e)}")
            await browser.close()
            return None

async def main():
    """Función principal de prueba"""
    # Conectar a la base de datos
    conn = sqlite3.connect('medicamentos.db')
    cursor = conn.cursor()

    # Obtener un medicamento de prueba
    cursor.execute("SELECT id, nombre FROM medicamentos LIMIT 1 OFFSET 4")
    medicamento = cursor.fetchone()

    if medicamento:
        med_id, med_nombre = medicamento
        print(f"Probando con: ID={med_id}, Nombre={med_nombre}")

        resultado = await buscar_precio_cruz_verde(med_nombre)

        if resultado:
            print(f"\n{'='*50}")
            print(f"RESULTADO:")
            print(f"Medicamento: {med_nombre}")
            print(f"Precio: ${resultado['precio']:,.0f}")
            print(f"URL: {resultado['url']}")
            print(f"Farmacia: {resultado['farmacia']}")
            print(f"{'='*50}")
        else:
            print("\nNo se pudo obtener el precio")

    conn.close()

if __name__ == "__main__":
    asyncio.run(main())
