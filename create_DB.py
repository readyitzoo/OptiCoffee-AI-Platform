import sqlite3
from datetime import datetime, timedelta

def setup_database():
    conn = sqlite3.connect("coffee_b2b.db")
    cursor = conn.cursor()

    # 1. CATALOG DE PRODUSE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        product_id TEXT PRIMARY KEY,
        name TEXT,
        origin TEXT,
        tasting_notes TEXT,
        roast_type TEXT,
        stock_kg REAL,
        base_price_per_kg REAL
    )
    """)

    # 2. PROFILURILE CAFENELELOR (CUSTOMERS)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        customer_id TEXT PRIMARY KEY,
        name TEXT,
        contact_person TEXT,
        channel TEXT,               -- ex: WhatsApp, Email
        weekly_consumption_kg REAL   -- ritmul lor obișnuit de consum
    )
    """)

    # 3. ISTORIC COMENZI
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        order_id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id TEXT,
        product_id TEXT,
        order_date TEXT,
        quantity_kg REAL,
        unit_price REAL,
        FOREIGN KEY (customer_id) REFERENCES customers (customer_id),
        FOREIGN KEY (product_id) REFERENCES products (product_id)
    )
    """)

    # --- INSERARE PRODUSE ---
    products = [
        ("PRD_01", "House Blend Espresso", "Brazil & Colombia", "ciocolată cu lapte, caramel, alune de pădure", "Espresso", 120.0, 75.0),
        ("PRD_02", "Ethiopia Yirgacheffe", "Ethiopia", "flori de iasomie, bergamotă, piersică, aciditate citrică", "Light / Filter", 45.0, 110.0),
        ("PRD_03", "Colombia Geisha Limited", "Colombia", "fructul pasiunii, mango, flori albe, corp mătăsos", "Light / Omni", 8.0, 190.0),
        ("PRD_04", "Guatemala Huehuetenango", "Guatemala", "măr roșu, ciocolată neagră, zahăr brun", "Medium / Espresso", 60.0, 85.0),
        ("PRD_05", "Decaf Swiss Water Process", "Peru", "zahăr brun, nuci, aciditate foarte scăzută", "Medium", 0.0, 90.0) # OUT OF STOCK (caz de test!)
    ]
    cursor.executemany("INSERT OR REPLACE INTO products VALUES (?, ?, ?, ?, ?, ?, ?)", products)

    # --- INSERARE CLIENȚI ---
    customers = [
        ("CUST_01", "Artisan Brew SRL", "Andrei", "WhatsApp", 14.0),     # Consumă ~2 kg/zi
        ("CUST_02", "Bean & Leaf Hub", "Elena", "Email", 25.0),         # Consumă ~3.5 kg/zi
        ("CUST_03", "Old Town Specialty", "Mihai", "WhatsApp", 10.0)    # Consum redus
    ]
    cursor.executemany("INSERT OR REPLACE INTO customers VALUES (?, ?, ?, ?, ?)", customers)

    # --- INSERARE ISTORIC COMENZI (SCENARII PLANIFICATE) ---
    today = datetime.now()
    
    orders = [
        # SCENARIUL 1: "Artisan Brew" - URGENȚĂ RESTOCK
        # A comandat 20 kg acum 9 zile. La 2 kg/zi consum, mai au doar 2 kg (rămân fără stoc MÂINE).
        ("CUST_01", "PRD_01", (today - timedelta(days=9)).strftime("%Y-%m-%d"), 20.0, 75.0),
        ("CUST_01", "PRD_02", (today - timedelta(days=9)).strftime("%Y-%m-%d"), 2.0, 110.0),

        # SCENARIUL 2: "Bean & Leaf" - CADENȚĂ NORMALĂ
        # A comandat 30 kg acum 3 zile. La 3.5 kg/zi, mai au stoc pentru încă vreo 5-6 zile. Nu e alertă critică.
        ("CUST_02", "PRD_01", (today - timedelta(days=3)).strftime("%Y-%m-%d"), 30.0, 75.0),

        # SCENARIUL 3: "Old Town Specialty" - CHURN RISK / ANOMALIE
        # N-au mai comandat de 28 de zile, deși consumă 10 kg/săptămână. Risc mare să fi trecut la alt prăjitor!
        ("CUST_03", "PRD_04", (today - timedelta(days=28)).strftime("%Y-%m-%d"), 20.0, 85.0),
    ]
    cursor.executemany("INSERT INTO orders (customer_id, product_id, order_date, quantity_kg, unit_price) VALUES (?, ?, ?, ?, ?)", orders)

    conn.commit()
    conn.close()
    print("Baza de date 'coffee_b2b.db' a fost creată cu succes!")

if __name__ == "__main__":
    setup_database()