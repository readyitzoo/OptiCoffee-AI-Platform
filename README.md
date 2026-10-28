# ☕ OptiCoffee.AI – Autonomous B2B Commerce Platform
> **Predict demand → Decide next-best-action → Act via autonomous agent → Close the feedback loop.**

Implementare tehnică end-to-end a unei platforme de comerț predictiv și execuție autonomă pentru distribuitori B2B de cafea de specialitate, dezvoltată pentru rolul de **Junior AI Engineer la OptiComm.AI**.

---

## 🏛️ Arhitectura Sistemului

Sistemul implementează bucla completă descrisă în misiunea OptiComm.AI:

```mermaid
flowchart TD
    subgraph Data Layer
        DB[(SQLite / Orders & Inventory)]
    end

    subgraph 1. PREDICT Engine
        DB -->|Istoric comenzi & cadență| FE[Feature Engineering: Burn Rate & Churn Risk]
        FE --> Pred[Calcul zile până la epuizare & Scorit urgență]
    end

    subgraph 2. DECIDE Layer
        Pred --> Prioritize[Ordonare conturi după urgență & Next Best Action]
    end

    subgraph 3. ACT - Autonomous Agent
        Prioritize -->|Target Brief| Agent[Llama / GPT-OSS Agent cu Tool Calling]
        Agent <-->|Verificare stoc & Prețuri volum| Tools[Python Tools]
        Tools <--> DB
        Agent -->|Conversație WhatsApp B2B| User[Proprietar Cafenea]
    end

    subgraph 4. FEEDBACK LOOP
        User -->|Negocieri, Confirmări, Obiecții| Agent
        Agent -->|log_interaction_feedback| Logs[(interaction_logs)]
        Logs -->|Recalibrare dinamică cadență| FE
    end