# ☕ OptiCoffee.AI – Autonomous B2B Commerce Platform

> **Predict demand → Decide next-best-action → Act via autonomous agent → Close the feedback loop.**

Implementare tehnică end-to-end a unei platforme de comerț predictiv și execuție autonomă pentru distribuitori B2B de cafea de specialitate, dezvoltată pentru rolul de **Junior AI Engineer la OptiComm.AI**.

---

## 🏛️ Arhitectura Sistemului

```text
┌─────────────────────────────────────────────────────────────┐
│                 Baza de Date SQLite (ERP)                   │
│          • Catalog Produse  • Clienți  • Comenzi             │
└──────────────┬──────────────────────────────▲───────────────┘
               │                              │
               │ (istoric vânzări)            │ (scădere stoc & comenzi noi)
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
├── predict.py           # Motorul PREDICT: feature engineering, cadență și scor de urgență
├── tools.py             # Unelte deterministe și scheme pentru Tool Calling
├── agent.py             # Agent CLI: execuție autonomă cu Llama/GPT-OSS prin Groq
├── app.py               # Interfață Streamlit: dashboard predictiv și WhatsApp Simulator
├── test_loop.py         # Test automat pentru validarea Feedback Loop-ului
├── eval_agents.py       # Benchmarking și evaluarea guardrails pe 4 scenarii
├── requirements.txt     # Dependențele Python ale proiectului
├── .gitignore           # Fișiere ignorate: venv, .env și cache-ul bazei de date
└── README.md            # Documentația tehnică a sistemului
```

## ✨ Componentele Principale

### 1. Modulul de Predicție (`predict.py`)

- **Feature Engineering:** Extrage din istoricul tranzacțional consumul zilnic mediu (`daily_burn_rate`), calculează zilele scurse de la ultima livrare și estimează stocul curent rămas la fiecare client.
- **Scor de Urgență și Clasificare:** Categorisește dinamic conturile în categorii precum `URGENT_RESTOCK`, `CHURN_ALERT`, `HEALTHY` și `MONITOR`.
- **Recalibrare Dinamică (Closed-Loop):** Citește semnalele agregate din tabela `interaction_logs`. Dacă un client negociază o cantitate diferită sau semnalează o scădere a consumului, sistemul recalibrează cantitatea recomandată pentru următoarea perioadă.

### 2. Modulul de Execuție Agentică și Unelte (`tools.py` și `agent.py`)

Agent autonom echipat cu unelte native prin Function Calling:

- **`check_stock_and_price`:** Interoghează catalogul de produse și stocurile din depozit.
- **`calculate_discounted_price`:** Calculează determinist discounturile de volum B2B, de exemplu 5% pentru 15–29 kg și 10% pentru minimum 30 kg.
- **`create_order_draft`:** Înregistrează comanda în baza de date și actualizează stocul.
- **`log_interaction_feedback`:** Înregistrează concluziile și obiecțiile clientului pentru alimentarea motorului predictiv.

### 3. Panoul de Control Web (`app.py`)

Interfață Streamlit concepută pentru nevoile operaționale ale unui distribuitor:

- **Predict & Decide:** Dashboard analitic cu alerte de reaprovizionare, clasamentul conturilor după urgență și istoricul feedback-ului primit.
- **Act & Observability:** Simulator interactiv de WhatsApp în care agentul inițiază proactiv conversația. O secțiune de observabilitate afișează apelurile uneltelor și parametrii executați.

## 🛡️ Decizii Inginerești și Guardrails Implementate

- **Context Injection împotriva Halucinațiilor:** Catalogul activ de produse este extras din SQLite și injectat în System Prompt la inițializare. Această abordare reduce riscul ca agentul să inventeze sortimente inexistente în catalog sau în stoc, precum Kenya AA ori Santos.
- **Two-Phase Commit și Integritatea Tranzacțiilor:** Agentul nu trebuie să execute `create_order_draft` sau `log_interaction_feedback` în faza de negociere. Comanda se înregistrează numai după confirmarea explicită a clientului, prevenind comenzile duplicate sau neconfirmate.
- **Defensive Parameter Handling:** Funcțiile Python acceptă variante de parametri precum `product_id` sau `product_name` și utilizează `**kwargs` acolo unde este necesar pentru a gestiona variațiile de sintaxă ale LLM-ului.

## 🧪 Suită de Testare și Validare Automată

Sistemul include teste automate reproductibile pentru verificarea comportamentului agentului și a buclei de feedback.

### 1. Validarea Feedback Loop-ului (`test_loop.py`)

Verifică dacă o negociere salvată în `interaction_logs` influențează predicția următoare.

```bash
python test_loop.py
```

**Rezultat raportat:** 100% PASSED. Testul demonstrează recalibrarea cantității recomandate de la 15 kg la 16 kg, pe baza semnalului clientului.

### 2. Agent Benchmarking și Guardrails (`eval_agents.py`)

Evaluează rezistența agentului în patru scenarii critice:

```bash
python eval_agents.py
```

Scenariile evaluate:

1. **TC_01 – Out of Stock:** Verifică dacă agentul refuză comanda pentru un produs cu stoc zero, precum Decaf.
2. **TC_02 – Anti-Hallucination:** Verifică dacă agentul refuză cererea pentru un produs inexistent în depozit, precum Kenya AA.
3. **TC_03 – Prompt Injection Guard:** Verifică respingerea cererilor off-topic, precum solicitările de rețete, și menținerea rolului comercial.
4. **TC_04 – Order Execution:** Verifică identificarea corectă a clientului și execuția apelului `create_order_draft`.

**Rezultat raportat:** 4 din 4 scenarii validate cu succes (100%).

> Notă: Rezultatele de mai sus sunt cele raportate în documentația inițială. Rulează testele în mediul tău pentru a confirma rezultatele.

## 🔮 Scalare în Producție: De la Unit Tests la LLM-as-a-Judge

În arhitectura actuală, validarea se bazează pe verificări deterministe ale apelurilor de funcții și ale guardrails. Pentru un mediu enterprise, direcțiile viitoare de dezvoltare includ:

- **Evaluare Semantică (LLM-as-a-Judge):** Integrarea unor framework-uri precum [DeepEval](https://github.com/confident-ai/deepeval) sau [Ragas](https://github.com/vibrantlabsai/ragas) pentru evaluarea conversațiilor pe criterii precum faithfulness, tone consistency și answer relevance.
- **Generarea de Clienți Sintetici:** Simularea automată a sute de negocieri, inclusiv scenarii adverse, pentru identificarea anomaliilor de marjă comercială și a comportamentelor nedorite.
- **Integrarea Canalelor Reale:** Înlocuirea simulatorului web cu un webhook conectat la Twilio și WhatsApp Business API.

Acestea sunt direcții propuse pentru scalare, nu funcționalități care trebuie considerate deja implementate.

## 🚀 Ghid de Instalare și Rulare

### Cerințe preliminare

- Python 3.10+
- Cheie API Groq: [console.groq.com](https://console.groq.com/)

### 1. Clonarea și configurarea mediului

Clonează repository-ul și navighează în directorul proiectului:

```bash
git clone <URL_REPOSITORY>
cd Opticomm
```

Creează și activează mediul virtual.

**Windows (PowerShell):**

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Dacă PowerShell blochează activarea scriptului, poți folosi temporar:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

**macOS / Linux:**

```bash
python3 -m venv venv
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

Înlocuiește valoarea exemplificativă cu propria cheie API. **Nu publica cheia API pe GitHub.** Asigură-te că fișierul `.env` este inclus în `.gitignore`.

### 3. Rularea aplicației

**Interfața Streamlit — recomandată pentru demo:**

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
