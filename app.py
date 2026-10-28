import os
import json
import sqlite3
import streamlit as st
import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv

from predict import DemandPredictor
from tools import TOOLS_SCHEMA, AVAILABLE_TOOLS, DB_PATH
# Importăm generatorul de date inițiale pentru butonul de Reset
import subprocess

# Setări pagină
st.set_page_config(page_title="OptiCoffee AI Platform", layout="wide", page_icon="☕")

# Încărcare cheie Groq
load_dotenv()
api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    st.error("Lipsește GROQ_API_KEY din fișierul .env!")
    st.stop()

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=api_key
)
MODEL_NAME = "openai/gpt-oss-20b"

# --- SIDEBAR: CONTROALE DE SISTEM ---
st.sidebar.title("⚙️ Control Panel")
if st.sidebar.button("🔄 Reset Mock Database (Scenariu Inițial)"):
    # Resetează baza de date la starea inițială rulând scriptul de setup
    import sys
    # Re-rulăm scriptul de generare a datelor inițiale
    from datetime import datetime, timedelta
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    today = datetime.now()
    cur.execute("DELETE FROM orders")
    cur.execute("DELETE FROM interaction_logs")
    cur.execute("UPDATE products SET stock_kg = 120.0 WHERE product_id = 'PRD_01'")
    
    # Re-inserăm comenzile inițiale
    orders = [
        ("CUST_01", "PRD_01", (today - timedelta(days=9)).strftime("%Y-%m-%d"), 20.0, 75.0),
        ("CUST_01", "PRD_02", (today - timedelta(days=9)).strftime("%Y-%m-%d"), 2.0, 110.0),
        ("CUST_02", "PRD_01", (today - timedelta(days=3)).strftime("%Y-%m-%d"), 30.0, 75.0),
        ("CUST_03", "PRD_04", (today - timedelta(days=28)).strftime("%Y-%m-%d"), 20.0, 85.0),
    ]
    cur.executemany("INSERT INTO orders (customer_id, product_id, order_date, quantity_kg, unit_price) VALUES (?, ?, ?, ?, ?)", orders)
    conn.commit()
    conn.close()
    
    # Resetăm starea sesiunii
    st.session_state.messages = []
    st.session_state.system_prompt_set = False
    st.session_state.tool_logs = []
    st.sidebar.success("Baza de date a fost resetată cu succes!")
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.info("💡 **OptiCoffee Loop:**\n1. **Predict:** Detectează consumul\n2. **Decide:** Alege campania optimă\n3. **Act:** Agent conversațional autonom\n4. **Feedback:** Învață din obiecții")

# Titlu Principal
st.title("☕ OptiCoffee.AI – Autonomous Commerce Platform")
st.caption("Predict demand → Decide next-best-action → Act via autonomous agent → Close feedback loop.")

# Inițializare stare sesiune chat
if "messages" not in st.session_state:
    st.session_state.messages = []
if "system_prompt_set" not in st.session_state:
    st.session_state.system_prompt_set = False
if "tool_logs" not in st.session_state:
    st.session_state.tool_logs = []
if "current_customer_id" not in st.session_state:
    st.session_state.current_customer_id = None

# Layout 2 Coloane
col_left, col_right = st.columns([1.1, 0.9], gap="large")

# ========================================================
# COLOANA STÂNGA: PREDICT & DECIDE DASHBOARD
# ========================================================
with col_left:
    st.subheader("📊 1. Predictive Engine (Demand & Urgency)")
    
    predictor = DemandPredictor()
    predictions_df = predictor.generate_account_predictions()

    urgent_cnt = len(predictions_df[predictions_df["status"] == "URGENT_RESTOCK"])
    churn_cnt = len(predictions_df[predictions_df["status"] == "CHURN_ALERT"])
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Alerte Restock", f"{urgent_cnt} conturi")
    m2.metric("Risc Churn", f"{churn_cnt} conturi")
    m3.metric("Conturi Monitorizate", f"{len(predictions_df)}")
    
    st.dataframe(
        predictions_df[[
            "cafe_name", "last_product_name", "days_until_stockout", 
            "status", "action_needed", "urgency_score"
        ]],
        width="stretch",
        hide_index=True
    )

    st.markdown("---")
    st.subheader("🔄 4. Closed-Loop Feedback Logs")
    conn = sqlite3.connect(DB_PATH)
    logs_df = pd.read_sql_query("SELECT timestamp, customer_id, outcome, summary, cadence_feedback FROM interaction_logs ORDER BY log_id DESC LIMIT 5", conn)
    conn.close()
    
    if not logs_df.empty:
        st.dataframe(logs_df, width="stretch", hide_index=True)
    else:
        st.info("Niciun feedback salvat încă. Finalizează o tranzacție pentru a popula datele de feedback.")


# ========================================================
# COLOANA DREAPTA: ACT (AGENTIC EXECUTION)
# ========================================================
with col_right:
    st.subheader("🤖 2 & 3. Decide & Act (WhatsApp Agent)")

    # Selectăm contul din interfață (implicit cel cu cel mai mare scor de urgență)
    cafe_options = predictions_df["cafe_name"].unique().tolist()
    selected_cafe_name = st.selectbox("Selectează Contul de contactat:", cafe_options, index=0)

    target_account = predictions_df[predictions_df["cafe_name"] == selected_cafe_name].iloc[0].to_dict()

    # Dacă utilizatorul a schimbat contul, resetăm istoricul de chat
    if st.session_state.current_customer_id != target_account["customer_id"]:
        st.session_state.messages = []
        st.session_state.system_prompt_set = False
        st.session_state.tool_logs = []
        st.session_state.current_customer_id = target_account["customer_id"]

    st.info(f"Target: **{target_account['cafe_name']}** ({target_account['contact_person']}) | Status: **{target_account['status']}** | Recomandat: **{target_account['recommended_reorder_kg']} kg**")

    # Inițializare chat la prima încărcare a contului
    if not st.session_state.system_prompt_set:
        
        # 1. Extragem dinamic catalogul REAL din baza de date pentru CONTEXT INJECTION
        conn = sqlite3.connect(DB_PATH)
        catalog_items = conn.cursor().execute("""
            SELECT name, origin, tasting_notes, roast_type, base_price_per_kg, stock_kg 
            FROM products 
            WHERE stock_kg > 0
        """).fetchall()
        conn.close()
        
        catalog_formatted = "\n".join([
            f"- {item[0]} ({item[1]}) | Note: {item[2]} | Prăjire: {item[3]} | Preț: {item[4]} lei/kg | Stoc: {item[5]} kg"
            for item in catalog_items
        ])

        system_prompt = f"""
Ești Alex, reprezentant comercial dedicat la compania de distribuție 'OptiCoffee'.
Comunici direct pe WhatsApp cu {target_account['contact_person']}, proprietarul cafenelei '{target_account['cafe_name']}'.

CATALOGUL NOSTRU OFICIAL ȘI COMPLET (DOAR ACESTEA EXISTĂ ÎN DEPOZIT):
{catalog_formatted}

REGULĂ ZERO (INTERZIS HALUCINAȚIA DE CATALOG):
1. Compania noastră vinde EXCLUSIV cele 4 cafele din catalogul de mai sus! 
2. Este STRICT INTERZIS să inventezi sau să menționezi alte sortimente (nu avem Kenya, nu avem Santos, nu avem Antigua etc.).
3. Dacă stocul unei cafele este insuficient, propune alternative STRICT din lista de mai sus (ex: dacă Geisha are doar 8 kg, propune completare cu Guatemala sau House Blend).

REGULI DE TRANZACȚIE & INTEGRITATE (TWO-PHASE COMMIT):
1. NU APELA NICIODATĂ `create_order_draft` ÎN TIMP CE NEGOCIEZI! Dacă schimbi cantitățile sau propui alternative, mai întâi întreabă clientul și prezintă totalul.
2. Apelează unealta `create_order_draft` DOAR DUPĂ ce clientul a spus explicit „DA”, „CONFIRM” sau „E ÎN REGULĂ” la oferta și cantitățile finale!
3. O singură comandă per tranzacție: dacă o comandă conține două produse (ex: 8 kg Geisha + 2 kg Guatemala), apelează `create_order_draft` o singură dată pentru fiecare produs, DOAR în momentul confirmării finale.
4. Apelează `log_interaction_feedback` o singură dată, la finalul absolut al conversației. Dacă nu s-a cumpărat nimic, trimite obligatoriu ordered_kg = 0 (niciodată null).

REGULI DE SECURITATE & CONFIDENȚIALITATE (ANTI-LEAK):
1. NU afișa NICIODATĂ blocuri de cod JSON, dicționare, note interne de debug sau rezultate de unelte în mesajele către client! Tot ce vede clientul trebuie să fie text uman, cald și prietenos.
2. NU folosi ID-uri tehnice interne în conversație (fără PRD_01, CUST_01 etc.). Folosește doar denumirile comerciale ale cafelelor.

STIL & COMUNICARE B2B:
1. Vorbește natural, concis și profesionist (stil mesagerie WhatsApp).
2. Ai grijă la acordul gramatical în limba română (ex: 'o reaprovizionare', nu 'un reaprovizionare'; 'ți se potrivește', nu 'ţi‑se').

CONTEXT CLIENT:
- Client ID: {target_account['customer_id']}
- Ultima cafea consumată: {target_account['last_product_name']}
- Recomandare cantitate: {target_account['recommended_reorder_kg']} kg
"""
        st.session_state.messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Generează mesajul inițial proactiv de contact pentru acest client."}
        ]
        
        with st.spinner("Agentul pregătește mesajul proactiv..."):
            resp = client.chat.completions.create(
                model=MODEL_NAME,
                messages=st.session_state.messages
            )
            first_msg = resp.choices[0].message.content
            st.session_state.messages.append({"role": "assistant", "content": first_msg})
            st.session_state.system_prompt_set = True
        

   # Afișare conversație robustă
    chat_container = st.container(height=380)
    for msg in st.session_state.messages:
        role = getattr(msg, "role", None) if hasattr(msg, "role") else (msg.get("role") if isinstance(msg, dict) else None)
        content = getattr(msg, "content", None) if hasattr(msg, "content") else (msg.get("content") if isinstance(msg, dict) else None)

        if role in ["assistant", "user"] and content:
            if "Generează mesajul inițial" not in content:
                chat_container.chat_message(role).write(content)

    # Afișare log-uri unelte (Observability)
    if st.session_state.tool_logs:
        with st.expander("🛠️ Tool Executions (Agent Observability Logs)", expanded=False):
            for t_log in st.session_state.tool_logs:
                st.text(t_log)

    # Câmpul de răspuns al utilizatorului
    if user_prompt := st.chat_input("Răspunde ca proprietarul cafenelei..."):
        chat_container.chat_message("user").write(user_prompt)
        st.session_state.messages.append({"role": "user", "content": user_prompt})

        with st.spinner("Agentul procesează și execută unelte..."):
            while True:
                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=st.session_state.messages,
                    tools=TOOLS_SCHEMA,
                    tool_choice="auto"
                )
                msg_obj = response.choices[0].message
                st.session_state.messages.append(msg_obj)

                if not msg_obj.tool_calls:
                    chat_container.chat_message("assistant").write(msg_obj.content)
                    break

                for tool_call in msg_obj.tool_calls:
                    fn_name = tool_call.function.name
                    fn_args = json.loads(tool_call.function.arguments)
                    st.session_state.tool_logs.append(f"⚙️ CALL: {fn_name}({fn_args})")
                    
                    fn_to_call = AVAILABLE_TOOLS.get(fn_name)
                    res = fn_to_call(**fn_args) if fn_to_call else "{'error': 'tool not found'}"
                    st.session_state.tool_logs.append(f"📥 RESULT: {res}")

                    st.session_state.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": fn_name,
                        "content": str(res)
                    })
        
        st.rerun()