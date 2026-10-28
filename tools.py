import sqlite3
import json
from datetime import datetime

DB_PATH = "coffee_b2b.db"

# ==========================================
# 0. INIȚIALIZARE TABELĂ FEEDBACK / INTERACȚIUNI
# ==========================================
def init_feedback_table():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS interaction_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id TEXT,
            timestamp TEXT,
            outcome TEXT,             -- ex: ORDER_CONFIRMED, PRICE_OBJECTION, CHURN_CONFIRMED
            ordered_kg REAL,
            summary TEXT,             -- Notițele agentului (ex: 28kg a fost prea mult, preferă 20kg)
            cadence_feedback TEXT     -- Semnal pentru modelul de predicție
        )
    """)
    conn.commit()
    conn.close()

init_feedback_table()


# ==========================================
# 1. FUNCȚIILE PYTHON (EXECUȚIA REALĂ)
# ==========================================

def check_stock_and_price(product_name_query: str) -> str:
    """Caută un produs în catalog după nume sau origine, verifică stocul disponibil și prețul."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT product_id, name, origin, tasting_notes, stock_kg, base_price_per_kg
        FROM products 
        WHERE LOWER(name) LIKE LOWER(?) OR LOWER(origin) LIKE LOWER(?)
    """, (f"%{product_name_query}%", f"%{product_name_query}%"))
    
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return json.dumps({"error": f"Niciun produs găsit pentru '{product_name_query}'."})
    
    results = []
    for r in rows:
        results.append({
            "product_id": r[0],
            "product_name": r[1],
            "origin": r[2],
            "tasting_notes": r[3],
            "available_stock_kg": r[4],
            "base_price_per_kg": r[5],
            "in_stock": r[4] > 0
        })
    return json.dumps(results, ensure_ascii=False)


def calculate_discounted_price(quantity_kg: float, base_price: float) -> str:
    """Calculează reducerea de volum B2B: <15kg: 0%, 15-29kg: 5%, 30kg+: 10%."""
    if quantity_kg >= 30:
        discount = 0.10
    elif quantity_kg >= 15:
        discount = 0.05
    else:
        discount = 0.00
        
    final_price_per_kg = base_price * (1 - discount)
    total_cost = round(quantity_kg * final_price_per_kg, 2)
    
    return json.dumps({
        "quantity_kg": quantity_kg,
        "base_price": base_price,
        "discount_percent": int(discount * 100),
        "final_price_per_kg": round(final_price_per_kg, 2),
        "total_order_cost": total_cost
    })

def get_available_catalog() -> str:
    """
    Returnează lista completă a cafelelor disponibile în catalog, 
    cu notele de degustare și prețurile lor.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name, origin, tasting_notes, roast_type, base_price_per_kg, stock_kg 
        FROM products 
        WHERE stock_kg > 0
    """)
    rows = cursor.fetchall()
    conn.close()
    
    catalog = []
    for r in rows:
        catalog.append({
            "name": r[0],
            "origin": r[1],
            "tasting_notes": r[2],
            "roast_type": r[3],
            "price_per_kg": r[4],
            "available_stock_kg": r[5]
        })
    return json.dumps(catalog, ensure_ascii=False)


def create_order_draft(customer_id: str, product_id: str = None, product_identifier: str = None, quantity_kg: float = 0.0, agreed_price: float = 0.0, **kwargs) -> str:
    """
    Generează comanda acceptând oricare dintre parametrii trimiși de LLM (product_id sau product_identifier).
    """
    # Acceptă oricare denumire trimisă de model
    identifier = product_id or product_identifier or kwargs.get("product_name") or kwargs.get("name")
    
    if not identifier:
        return json.dumps({"status": "FAILED", "reason": "Produsul nu a fost specificat."})
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Caută după ID sau după Nume
    cursor.execute("""
        SELECT product_id, stock_kg, name 
        FROM products 
        WHERE product_id = ? OR LOWER(name) LIKE LOWER(?)
    """, (str(identifier), f"%{identifier}%"))
    
    prod = cursor.fetchone()
    
    if not prod:
        conn.close()
        return json.dumps({"status": "FAILED", "reason": f"Produsul '{identifier}' nu a fost găsit în catalog."})
        
    real_product_id, current_stock, prod_name = prod
    
    if current_stock < quantity_kg:
        conn.close()
        return json.dumps({"status": "FAILED", "reason": f"Stoc insuficient pentru {prod_name}. Doar {current_stock} kg disponibile."})
    
    # Salvează comanda
    cursor.execute("""
        INSERT INTO orders (customer_id, product_id, order_date, quantity_kg, unit_price)
        VALUES (?, ?, date('now'), ?, ?)
    """, (customer_id, real_product_id, quantity_kg, agreed_price))
    
    # Scade stocul
    cursor.execute("UPDATE products SET stock_kg = stock_kg - ? WHERE product_id = ?", (quantity_kg, real_product_id))
    
    conn.commit()
    conn.close()
    
    return json.dumps({
        "status": "CONFIRMED",
        "message": f"Comandă înregistrată cu succes pentru {quantity_kg} kg de {prod_name}.",
        "agreed_price_per_kg": agreed_price,
        "total": round(quantity_kg * agreed_price, 2)
    })


def log_interaction_feedback(customer_id: str, outcome: str, summary: str, cadence_feedback: str, ordered_kg: float = 0.0, **kwargs) -> str:
    if ordered_kg is None:
        ordered_kg = 0.0
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute("""
        INSERT INTO interaction_logs (customer_id, timestamp, outcome, ordered_kg, summary, cadence_feedback)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (customer_id, now_str, outcome, ordered_kg, summary, cadence_feedback))
    
    conn.commit()
    conn.close()
    
    return json.dumps({
        "status": "LOGGED",
        "message": "Rezultatul interacțiunii a fost salvat pentru optimizarea viitoare a modelului de cerere."
    })


# ==========================================
# 2. SCHEMELE JSON PENTRU LLM (FUNCTION CALLING)
# ==========================================

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "check_stock_and_price",
            "description": "Caută cafele în catalog, verifică notele aromatice, stocul disponibil și prețul de listă.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_name_query": {"type": "string", "description": "Numele produsului sau originea căutată"}
                },
                "required": ["product_name_query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_discounted_price",
            "description": "Calculează reducerea de volum B2B și totalul de plată.",
            "parameters": {
                "type": "object",
                "properties": {
                    "quantity_kg": {"type": "number", "description": "Cantitatea dorită în kg"},
                    "base_price": {"type": "number", "description": "Prețul de bază/kg"}
                },
                "required": ["quantity_kg", "base_price"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_order_draft",
            "description": "Înregistrează oficial comanda confirmată în baza de date și scade stocul.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string", "description": "ID-ul clientului (ex: CUST_01)"},
                    "product_id": {"type": "string", "description": "ID-ul produsului comandat (ex: PRD_01)"},
                    "quantity_kg": {"type": "number", "description": "Cantitatea confirmată"},
                    "agreed_price": {"type": "number", "description": "Prețul unitar agreat per kg"}
                },
                "required": ["customer_id", "product_id", "quantity_kg", "agreed_price"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "log_interaction_feedback",
            "description": "Înregistrează rezultatul dialogului și obiecțiile clientului pentru retrain-ul modelului predictiv.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string", "description": "ID-ul clientului"},
                    "outcome": {
                        "type": "string", 
                        "enum": ["ORDER_CONFIRMED", "PRICE_OBJECTION", "QUANTITY_ADJUSTED", "NO_NEED", "CHURN_RISK"],
                        "description": "Rezultatul principal al dialogului"
                    },
                    "summary": {"type": "string", "description": "Scurt rezumat al motivului sau acordului"},
                    "cadence_feedback": {"type": "string", "description": "Semnal de recalibrare (ex: 'Ritmul săptămânal scade de la 14kg la 10kg')"},
                    "ordered_kg": {"type": "number","description": "Cantitatea comandată în kg. Pune OBLIGATORIU 0 dacă nu s-a plasat nicio comandă sau dacă a fost refuzată/anulată."}
                },
                "required": ["customer_id", "outcome", "summary", "cadence_feedback"]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "get_available_catalog",
            "description": "Obține lista tuturor cafelelor disponibile în stoc, cu aromele și prețurile lor.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]

AVAILABLE_TOOLS = {
    "check_stock_and_price": check_stock_and_price,
    "calculate_discounted_price": calculate_discounted_price,
    "create_order_draft": create_order_draft,
    "log_interaction_feedback": log_interaction_feedback,
    "get_available_catalog" : get_available_catalog
}