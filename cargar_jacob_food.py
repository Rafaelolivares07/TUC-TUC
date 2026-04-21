"""
Carga menú Jacob's Food — restaurante_id=10, slug=jacob-s-food
"""
import psycopg2, os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.environ['DATABASE_URL']

RESTAURANTE_ID = 10

ITEMS = [
    # (categoria, nombre, precio, descripcion)

    # BURGERS
    ("Burgers", "Criolla",       21000, "Pan artesanal, vegetales, carne de res premium 150gr, mozzarella, salsa de queso cheddar, carne desmechada/guisada, guacamole y chimichurri"),
    ("Burgers", "Mexicana",      19000, "Pan artesanal, vegetales, carne de res premium 150gr, mozzarella, salsa de queso cheddar, queso crema, pico de gallo, guacamole y jalapeño (opcional)"),
    ("Burgers", "Ranchera",      21000, "Pan artesanal, vegetales, carne de res premium 150gr, mozzarella, salsa de queso cheddar, queso crema, ranchera y maíz"),
    ("Burgers", "Americana",     19000, "Pan artesanal, vegetales, carne de res premium 150gr, mozarella, salsa de queso cheddar y 4 tocineta"),
    ("Burgers", "Caramelizada",  21000, "Pan artesanal, tomate, lechuga, carne de res premium 150gr, mozzarella, salsa de queso cheddar, queso crema, cebolla reducida en vino tinto con un toque de azúcar y tocineta"),
    ("Burgers", "Tradicional",   16000, "Pan artesanal, vegetales, carne de res premium 150gr, mozzarella, salsa de queso cheddar"),
    ("Burgers", "Combo",         17000, "Pan artesanal, vegetales, carne de res premium 100gr, mozzarella, salsa de queso cheddar, 2 tocinetas, papas y gaseosa"),

    # PAPAS (para 2 personas)
    ("Papas",   "Mexicana",            28000, "Papa rústica, carne desmechada con un toque de BBQ, salchicha premium, pico de gallo, salsa de queso cheddar, queso crema, guacamole y jalapeños (opcional)"),
    ("Papas",   "Criolla",             28000, "Papa rústica, salsa de la casa rosada, carne desmechada en guiso, chimichurri y guacamole"),
    ("Papas",   "Ranchera",            28000, "Papa rústica, ranchera, salchicha premium, salsa de queso cheddar, queso crema, maíz y salsa de la casa"),
    ("Papas",   "Americana",           26000, "Papa rústica, pico de gallo, tocineta, salchicha premium, salsa de queso cheddar y queso crema"),
    ("Papas",   "Especial",            28000, "Papa rústica, salsa de la casa rosada, dos porciones salchicha premium, tres quesos mozzarella, tocineta"),
    ("Papas",   "Nachos",              24000, "Nachos con queso crema, cheddar, guacamole, lechuga y pico de gallo con carne desmechada con BBQ"),
    ("Papas",   "Salchipapa Sencilla", 11000, None),
    ("Papas",   "Porción de Papas",     6500, None),

    # SANDWICH
    ("Sandwich", "Sándwich de la casa",              19500, "Pollo desmechado, queso crema, tocineta, ranchera y maíz. Pan francés, lechuga, tomate, queso mozarela"),
    ("Sandwich", "Sándwich de carne desmechada BBQ", 17000, "Pan francés, lechuga, tomate, queso mozarela"),
    ("Sandwich", "Sándwich de pollo y jamón",        17000, "Pan francés, lechuga, tomate, queso mozarela"),
    ("Sandwich", "Sándwich de cordero y jamón",      17000, "Pan francés, lechuga, tomate, queso mozarela"),
    ("Sandwich", "Sándwich hawaiano",                12000, "Pan francés, lechuga, tomate, queso mozarela"),
    ("Sandwich", "Sándwich de jamón",                10000, "Pan francés, lechuga, tomate, queso mozarela"),

    # MENÚ INFANTIL
    ("Menú Infantil", "Menú Infantil", 16000, "Sándwich con pan brioche redondo, jamón y queso con papitas. Jugo natural (mango, mora o fresa). Juguete sorpresa"),

    # ADICIONES
    ("Adiciones", "Maíz",                     1500, None),
    ("Adiciones", "Piña",                     2000, None),
    ("Adiciones", "Salsa de BBQ",             1000, None),
    ("Adiciones", "Carne de hamburguesa",     5500, None),
    ("Adiciones", "Pollo o carne desmechada", 5500, None),
    ("Adiciones", "Tocineta",                 4500, None),
    ("Adiciones", "Ranchera (3und)",          5000, None),
    ("Adiciones", "Helado (una bola)",        4000, None),
    ("Adiciones", "Queso mozzarella",         1000, None),
    ("Adiciones", "Salsa de queso cheddar",   2000, None),
    ("Adiciones", "Guacamole",                2000, None),
    ("Adiciones", "Pico de gallo",            2000, None),
    ("Adiciones", "Chimichurri",              2000, None),
    ("Adiciones", "Jalapeño",                 2000, None),
    ("Adiciones", "Hogao",                    2000, None),
    ("Adiciones", "Salchicha rica (2und)",    4000, None),

    # BEBIDAS — Limonadas
    ("Limonadas", "Limonada natural",        5000,  None),
    ("Limonadas", "Limonada de hierbabuena", 6000,  None),
    ("Limonadas", "Limonada cerezada",       7000,  None),
    ("Limonadas", "Limonada de mango viche", 7500,  None),
    ("Limonadas", "Limonada de coco",        10500, None),

    # BEBIDAS — Gaseosas
    ("Gaseosas", "Gaseosa mini",            2000, None),
    ("Gaseosas", "Gaseosa personal",        3500, None),
    ("Gaseosas", "Gaseosa litro y medio",   7500, None),
    ("Gaseosas", "Jugo Hit personal",       3500, None),
    ("Gaseosas", "Jugo Hit litro y medio",  7500, None),
    ("Gaseosas", "Cerveza",                 5000, None),

    # BEBIDAS — Jugos Naturales
    ("Jugos Naturales", "Agua",  6000, None),
    ("Jugos Naturales", "Leche", 7000, None),

    # BEBIDAS — Jugos Michelados
    ("Jugos Michelados", "Jugos Michelados", 8000, "Jugo natural en agua con un toque de limón y borde de sal. Lulo, Maracuyá o Fresa"),

    # BEBIDAS — Malteadas
    ("Malteadas", "Malteada Frutos Rojos",     12000, "Néctar de mora y trocitos de fresa. Base de helado de vainilla"),
    ("Malteadas", "Malteada Frutos Amarillos", 12000, "Néctar de maracuyá y trozos de piña. Base de helado de vainilla"),
    ("Malteadas", "Malteada Arequipe",         12000, "Base de helado de vainilla"),

    # BEBIDAS — Micheladas con cerveza
    ("Micheladas cerveza", "Tradicional", 6500, None),
    ("Micheladas cerveza", "Maracuyeah",  9500, None),
    ("Micheladas cerveza", "Reggae",      9500, "Tomate, maracuyá"),

    # BEBIDAS — Micheladas con soda
    ("Micheladas soda", "Tradicional",      6500, None),
    ("Micheladas soda", "Maracuyeah",       9000, None),
    ("Micheladas soda", "Reggae",           9000, "Tomate, maracuyá"),
    ("Micheladas soda", "Frutos rojos",     9000, None),
    ("Micheladas soda", "Frutos amarillos", 9000, None),
    ("Micheladas soda", "Sandía",           9000, None),
]

def main():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    cur.execute("DELETE FROM opciones_menu WHERE restaurante_id = %s", (RESTAURANTE_ID,))
    print(f"Registros anteriores eliminados")

    for orden, (categoria, nombre, precio, descripcion) in enumerate(ITEMS, start=1):
        cur.execute("""
            INSERT INTO opciones_menu (restaurante_id, tipo, nombre, precio, descripcion, activo, orden)
            VALUES (%s, %s, %s, %s, %s, TRUE, %s)
        """, (RESTAURANTE_ID, categoria, nombre, precio, descripcion, orden))

    conn.commit()
    cur.close()
    conn.close()
    print(f"{len(ITEMS)} ítems insertados para restaurante_id={RESTAURANTE_ID}")

if __name__ == '__main__':
    main()
