# ☕ OptiCoffee.AI – Autonomous B2B Commerce Platform

> **Predict demand → Decide next-best-action → Act via autonomous agent → Close the feedback loop.**

Platformă end-to-end de comerț predictiv și execuție agentică autonomă pentru distribuitori B2B din industria de cafea de specialitate. Sistemul conectează analiza datelor tabulare de consum cu agenți conversaționali dotați cu unelte deterministe (Tool Calling).
---

## 🏛️ Arhitectura Sistemului

```text
┌─────────────────────────────────────────────────────────────┐
│                 Baza de Date SQLite (ERP)                   │
│          • Catalog Produse  • Clienți  • Comenzi             │
└──────────────┬──────────────────────────────▲───────────────┘
               │                              │
               │ (istoric vânzări)            │ (scădere stoc și comenzi noi)
               ▼                              │
┌──────────────────────────────┐              │
│      1. PREDICT ENGINE       │              │
│  • Feature engineering       │              │
│  • Estimare epuizare stoc    │              │
│  • Urgency & Churn scoring   │              │
└──────────────┬───────────────┘              │
               │                              │
               │ (conturi prioritizate)       │
               ▼                              │
┌──────────────────────────────┐              │
│       2. DECIDE LAYER        │              │
│  • Selectare cont critic     │              │
│  • Next Best Action          │              │
└──────────────┬───────────────┘              │
               │                              │
               │ (target brief)               │
               ▼                              │
┌──────────────────────────────┐              │
│    3. ACT (AI Sales Agent)   │──────────────┘
│  • Dialog proactiv WhatsApp  │  (Tool Calling: stoc, discount, draft)
│  • Negociere cantități       │
└──────────────┬───────────────┘
               │
               │ (obiecții, refuz sau acord)
               ▼
┌──────────────────────────────┐
│     4. FEEDBACK LOOP         │
│  • Logare interacțiuni       │─────────────────────────────┐
│  • Închidere buclă           │  (recalibrare automată      │
└──────────────────────────────┘   cadență de consum)        │
               ▲                                             │
               └─────────────────────────────────────────────┘
```

## 📂 Structura Proiectului

```text
Opticomm/
├── coffee_b2b.db        # Baza de date SQLite: clienți, produse, comenzi și log-uri
├── predict.py           # PREDICT: feature engineering, consum mediu și scor de urgență
├── tools.py             # Funcții deterministe și scheme JSON pentru Tool Calling
├── agent.py             # Agent CLI: execuție autonomă cu Llama/GPT-OSS prin Groq
├── app.py               # Interfață Streamlit: dashboard predictiv și WhatsApp Simulator
├── test_loop.py         # Test automat pentru validarea Feedback Loop-ului
├── eval_agents.py       # Benchmarking și guardrails pentru 4 scenarii
├── requirements.txt     # Dependențele proiectului
├── .gitignore           # Fișiere ignorate: venv, .env și __pycache__
├── .env.example         # Șablon pentru cheia API
└── README.md            # Documentația tehnică
```

## ✨ Componentele Principale

### 1. Modulul de Predicție (`predict.py`)

- **Feature Engineering:** Extrage din istoricul tranzacțional consumul zilnic mediu (`daily_burn_rate`), calculează zilele scurse de la ultima livrare și estimează stocul curent rămas la fiecare client.
- **Scor de Urgență și Churn:** Clasifică dinamic conturile în categorii precum `URGENT_RESTOCK`, `CHURN_ALERT`, `HEALTHY` și `MONITOR`.
- **Recalibrare Dinamică (Closed-Loop):** Citește semnalele agregate din `interaction_logs`. Când un client negociază o cantitate diferită sau semnalează modificări ale consumului, sistemul recalibrează cantitatea recomandată pentru ciclul următor.

### 2. Modulul de Execuție Agentică și Unelte (`tools.py` și `agent.py`)

Agent autonom echipat cu unelte native prin Function Calling:

- **`check_stock_and_price`:** Interoghează catalogul de produse și disponibilitatea stocurilor.
- **`calculate_discounted_price`:** Calculează determinist discounturile de volum B2B: 5% pentru 15–29 kg și 10% pentru minimum 30 kg.
- **`create_order_draft`:** Înregistrează comanda în baza de date și actualizează stocul.
- **`log_interaction_feedback`:** Înregistrează concluziile și obiecțiile clientului pentru optimizarea motorului predictiv.

### 3. Panoul de Control Web (`app.py`)

Interfață dezvoltată în Streamlit, organizată în două componente principale:

- **Predict & Decide (stânga):** Dashboard analitic cu alerte de reaprovizionare, clasamentul conturilor după urgență și istoricul feedback-ului primit.
- **Act & Observability (dreapta):** Simulator interactiv de WhatsApp în care agentul inițiază proactiv conversația, alături de un panou de observabilitate care afișează apelurile uneltelor și parametrii executați.

## 🛡️ Decizii de Arhitectură și Guardrails

- **Context Injection împotriva Halucinațiilor:** Catalogul activ de produse este extras din SQLite și injectat în System Prompt la inițializare, reducând riscul inventării unor sortimente inexistente în catalog sau în stoc.
- **Two-Phase Commit (Integritate Tranzacțională):** Agentul nu trebuie să execute `create_order_draft` în timpul negocierii. Comanda se înregistrează numai după confirmarea explicită a clientului, prevenind comenzile neconfirmate sau duplicate.
- **Defensive Parameter Handling:** Funcțiile Python acceptă variante de parametri precum `product_id` sau `product_name` și folosesc `**kwargs`, acolo unde este necesar, pentru a tolera variațiile de sintaxă ale LLM-ului.

## 🧪 Suită de Testare și Validare Automată

### 1. Validarea Feedback Loop-ului (`test_loop.py`)

Verifică dacă feedback-ul salvat în `interaction_logs` recalibrează automat predicția următoare.

```bash
python test_loop.py
```

**Rezultat raportat:** `PASSED`. Testul validează recalibrarea cantității recomandate de la 15 kg la 16 kg, pe baza semnalului clientului.

### 2. Agent Benchmarking și Guardrails (`eval_agents.py`)

Evaluează automat comportamentul agentului în patru scenarii critice.

```bash
python eval_agents.py
```

Scenariile evaluate:

1. **TC_01 – Out of Stock:** Verifică refuzul comenzii pentru un produs cu stoc zero, precum Decaf.
2. **TC_02 – Anti-Hallucination:** Verifică respingerea cererilor pentru produse inexistente în catalog, precum Kenya AA.
3. **TC_03 – Prompt Injection Guard:** Verifică respingerea solicitărilor off-topic, precum cererile de rețete, și menținerea rolului comercial.
4. **TC_04 – Order Execution:** Verifică identificarea clientului și execuția apelului `create_order_draft`.

**Rezultat raportat:** 4 din 4 scenarii validate cu succes (100%).

> Notă: Rezultatele sunt cele indicate în documentația proiectului. Rulează testele în mediul tău pentru a confirma aceste rezultate.

## 🔮 Scalare în Producție (Next Steps)

Direcțiile viitoare de dezvoltare includ:

- **LLM-as-a-Judge:** Integrarea unui framework de evaluare semantică, precum [DeepEval](https://github.com/confident-ai/deepeval) sau [Ragas](https://github.com/vibrantlabsai/ragas), pentru măsurarea unor metrici precum faithfulness, tone consistency și answer relevance.
- **Generare de Clienți Sintetici:** Simularea automată a sute de negocieri cu agenți adverși pentru identificarea anomaliilor de marjă comercială.
- **Integrarea Canalelor Reale:** Conectarea simulatorului la un webhook Twilio și la WhatsApp Business API.

Acestea sunt propuneri pentru dezvoltarea ulterioară, nu funcționalități care trebuie considerate deja implementate.

## 🚀 Ghid de Instalare și Rulare

### Cerințe preliminare

- Python 3.10+
- Cheie API Groq: [console.groq.com](https://console.groq.com/)

### 1. Configurarea mediului

Creează mediul virtual:

```bash
python -m venv venv
```

**Windows (PowerShell):**

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

**macOS / Linux:**

```bash
source venv/bin/activate
```

Instalează dependențele:

```bash
pip install -r requirements.txt
```

### 2. Configurarea variabilelor de mediu

Creează un fișier `.env` în directorul rădăcină al proiectului și adaugă cheia API:

```dotenv
GROQ_API_KEY=gsk_cheia_ta_reala_groq
```

Înlocuiește valoarea exemplificativă cu cheia ta API reală.

> **Important:** Nu publica niciodată cheia API în repository. Asigură-te că `.env` este inclus în `.gitignore`. Poți folosi `.env.example` pentru a documenta variabilele necesare fără a expune secrete.

### 3. Rularea aplicației

**Interfața Streamlit (recomandată pentru demo):**

```bash
streamlit run app.py
```

**Rularea suitei de evaluare a agentului:**

```bash
python eval_agents.py
```

**Rularea testului Feedback Loop:**

```bash
python test_loop.py
```

**Rularea agentului CLI:**

```bash
python agent.py
```

---

## 📌 Obiectivul Proiectului

OptiCoffee.AI demonstrează modul în care predicțiile bazate pe date pot fi conectate la un agent AI capabil să utilizeze unelte, să gestioneze interacțiuni comerciale și să integreze feedback-ul în deciziile viitoare.

Arhitectura urmărește un flux complet **Predict → Decide → Act → Feedback**, cu accent pe automatizare, integritatea comenzilor, reducerea halucinațiilor și observabilitatea execuției agentului.
