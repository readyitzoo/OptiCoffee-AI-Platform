import os
import json
import sqlite3
from openai import OpenAI
from dotenv import load_dotenv

from predict import DemandPredictor
from tools import TOOLS_SCHEMA, AVAILABLE_TOOLS, DB_PATH

# 1. Configurare client Groq
load_dotenv()
api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise ValueError("Eroare: GROQ_API_KEY nu este setată în fișierul .env!")

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=api_key
)
MODEL_NAME = "openai/gpt-oss-20b"


def run_agent_turn(messages: list) -> str:
    """Bucla de execuție a agentului cu Function Calling."""
    while True:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            tools=TOOLS_SCHEMA,
            tool_choice="auto"
        )
        
        response_message = response.choices[0].message
        messages.append(response_message)
        
        # Dacă nu dorește să apeleze nicio unealtă, returnăm răspunsul
        if not response_message.tool_calls:
            return response_message.content

        # Executăm uneltele solicitate
        for tool_call in response_message.tool_calls:
            fn_name = tool_call.function.name
            fn_args = json.loads(tool_call.function.arguments)
            
            print(f"\n⚙️  [ACTION] Execut unealta: '{fn_name}'({fn_args})")
            
            fn_to_call = AVAILABLE_TOOLS.get(fn_name)
            tool_output = fn_to_call(**fn_args) if fn_to_call else json.dumps({"error": f"Tool necunoscut: {fn_name}"})
                
            print(f"📥 [RESULT]: {tool_output}\n")
            
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": fn_name,
                "content": str(tool_output)
            })


def main():
    print("=" * 60)
    print("🚀 PORNIRE OPTICOFFEE AGENT (Predict → Decide → Act)")
    print("=" * 60)
    
    # 1. PREDICT: Rulăm motorul de predicție
    predictor = DemandPredictor()
    predictions_df = predictor.generate_account_predictions()
    
    # 2. DECIDE: Selectăm contul cel mai urgent
    urgent_accounts = predictions_df[predictions_df["status"] == "URGENT_RESTOCK"]
    if urgent_accounts.empty:
        target_account = predictions_df.iloc[0].to_dict()
    else:
        target_account = urgent_accounts.iloc[0].to_dict()

    print(f"\n🎯 Cont țintă: {target_account['cafe_name']} (Urgență: {target_account['urgency_score']})")
    print(f"📦 Stoc '{target_account['last_product_name']}': epuizare în ~{target_account['days_until_stockout']} zile.")
    
    # 3. CONTEXT INJECTION (Extragem catalogul real din SQLite)
    conn = sqlite3.connect(DB_PATH)
    catalog_items = conn.cursor().execute("""
        SELECT name, origin, tasting_notes, roast_type, base_price_per_kg, stock_kg 
        FROM products WHERE stock_kg > 0
    """).fetchall()
    conn.close()
    
    catalog_formatted = "\n".join([
        f"- {item[0]} ({item[1]}) | Note: {item[2]} | Prăjire: {item[3]} | Preț: {item[4]} lei/kg | Stoc: {item[5]} kg"
        for item in catalog_items
    ])

    # 4. System Prompt cu Guardrails și Two-Phase Commit
    system_prompt = f"""
Ești Alex, reprezentant comercial la compania de distribuție 'OptiCoffee'.
Comunici direct pe WhatsApp cu {target_account['contact_person']}, proprietarul cafenelei '{target_account['cafe_name']}'.

CATALOG OFICIAL (DOAR ACESTEA EXISTĂ ÎN DEPOZIT):
{catalog_formatted}

REGULI CRITICE:
1. Nu inventa sortimente de cafea. Oferă DOAR din lista de mai sus.
2. Two-Phase Commit: NU apela `create_order_draft` în timp ce negociezi! Apelează-l DOAR după ce clientul a confirmat explicit comanda (ex: 'da', 'confirm').
3. La finalul dialogului, apelează `log_interaction_feedback` pentru a înregistra rezultatul. Dacă nu se cumpără nimic, trimite ordered_kg = 0.
4. Fii concis, prietenos și profesionist (stil WhatsApp B2B).
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Generează mesajul inițial proactiv de contact pentru acest client."}
    ]

    # Mesaj inițial
    initial_message = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages
    ).choices[0].message.content

    print("\n" + "=" * 60)
    print(f"💬 MESAJ PROACTIV TRIMIS CĂTRE {target_account['contact_person'].upper()}:")
    print(initial_message)
    print("=" * 60)
    
    messages.append({"role": "assistant", "content": initial_message})
    print("\n👉 Răspunde ca proprietarul cafenelei. Scrie 'exit' pentru a încheia.")
    
    while True:
        try:
            user_input = input("\nTu: ")
            if user_input.strip().lower() in ["exit", "quit", "iesire"]:
                print("Conversație încheiată.")
                break
            if not user_input.strip():
                continue
                
            messages.append({"role": "user", "content": user_input})
            assistant_reply = run_agent_turn(messages)
            
            print(f"\nAgent: {assistant_reply}")
            
        except KeyboardInterrupt:
            print("\nIeșire din conversație.")
            break


if __name__ == "__main__":
    main()