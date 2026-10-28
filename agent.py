import os
import json
from openai import OpenAI
from dotenv import load_dotenv

# Importăm modulele create anterior
from predict import DemandPredictor
from tools import TOOLS_SCHEMA, AVAILABLE_TOOLS

# 1. Încărcare cheie API Groq
load_dotenv()
api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise ValueError("Eroare: GROQ_API_KEY nu este setată în fișierul .env!")

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=api_key
)

# Folosim modelul de top open-source cu suport nativ de Tool Calling
MODEL_NAME = "openai/gpt-oss-120b"


def run_agent_turn(messages: list) -> str:
    """
    Trimite istoricul conversației către LLM.
    Dacă LLM-ul decide să apeleze un Tool, îl executăm automat
    și îi trimitem rezultatul înapoi până termină de răspuns.
    """
    while True:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            tools=TOOLS_SCHEMA,
            tool_choice="auto"
        )
        
        response_message = response.choices[0].message
        messages.append(response_message)
        
        # Verificăm dacă modelul dorește să apeleze un Tool
        if not response_message.tool_calls:
            # Dacă nu apelează niciun tool, a terminat răspunsul pentru utilizator
            return response_message.content

        # Dacă există apeluri de unelte, le executăm
        for tool_call in response_message.tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            
            print(f"\n⚙️  [AGENT ACTION] Execut unealta: '{function_name}' cu argumentele: {function_args}")
            
            # Executăm funcția Python corespunzătoare din tools.py
            function_to_call = AVAILABLE_TOOLS.get(function_name)
            if function_to_call:
                tool_output = function_to_call(**function_args)
            else:
                tool_output = json.dumps({"error": f"Tool necunoscut: {function_name}"})
                
            print(f"📥 [TOOL RESULT]: {tool_output}\n")
            
            # Trimitem rezultatul înapoi în istoricul conversației
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": function_name,
                "content": str(tool_output)
            })


def main():
    print("=" * 60)
    print("🚀 PORNIRE OPTICOFFEE AGENT (Predict → Decide → Act)")
    print("=" * 60)
    
    # 1. PREDICT: Rulăm motorul de predicție
    predictor = DemandPredictor()
    predictions_df = predictor.generate_account_predictions()
    
    # 2. DECIDE: Alegem cel mai urgent cont care necesită restock
    urgent_accounts = predictions_df[predictions_df["status"] == "URGENT_RESTOCK"]
    if urgent_accounts.empty:
        print("Niciun cont nu are nevoie urgentă de restock astăzi.")
        return

    target_account = urgent_accounts.iloc[0].to_dict()
    print(f"\n🎯 Cont țintă identificat: {target_account['cafe_name']} (Urgență: {target_account['urgency_score']})")
    print(f"📦 Stocul lor pentru '{target_account['last_product_name']}' se termină în: ~{target_account['days_until_stockout']} zile.")
    
    # 3. ACT: Configurăm System Prompt-ul cu contextul clientului
    system_prompt = f"""
Ești reprezentantul comercial autonom de la OptiCoffee Distribution pentru clientul '{target_account['cafe_name']}'.
Vorbești direct cu {target_account['contact_person']} pe {target_account['channel']}.

DATE PREDICTIVE DESPRE CLIENT:
- Ultima cafea comandată: {target_account['last_product_name']} (ID: {target_account['last_product_id']})
- Stoc estimat rămas: {target_account['estimated_stock_left_kg']} kg
- Zile până la epuizare completă: ~{target_account['days_until_stockout']} zile
- Cantitate recomandată de reofertat (pentru următoarele 2 săptămâni): {target_account['recommended_reorder_kg']} kg

REGULI STRICTE:
1. Fii concis, profesionist și prietenos (ton B2B de specialty coffee).
2. Nu inventa prețuri sau stocuri! Folosește mereu `check_stock_and_price` înainte să confirmi ceva.
3. Pentru cantități mari, folosește `calculate_discounted_price` pentru a-i oferi reducerea de volum corectă.
4. Când clientul își dă acordul final pe cantitate și preț, folosește OBLIGATORIU `create_order_draft` pentru a salva comanda.
5. Răspunde în limba română.
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Generează mesajul de inițiere proactivă pentru client."}
    ]

    # Generăm mesajul inițial proactiv (Outreach)
    initial_message = run_agent_turn(messages)
    print("\n" + "=" * 60)
    print(f"💬 MESAJ PROACTIV TRIMIS CĂTRE {target_account['contact_person'].upper()}:")
    print(initial_message)
    print("=" * 60)
    
    # Buclă de conversație interactivă în consolă
    print("\n👉 Răspunde ca și cum ai fi Andrei (proprietarul cafenelei). Scrie 'exit' pentru a încheia.")
    
    while True:
        try:
            user_input = input("\nTu (Andrei): ")
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