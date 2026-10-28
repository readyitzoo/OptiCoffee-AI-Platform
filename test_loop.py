"""
Test de verificare a Feedback Loop-ului (Closing the Loop):
Demonstrează cum un refuz sau o negociere a clientului actualizează direct
parametrii modelului predictiv la următoarea rulare.
"""
import sqlite3
from datetime import datetime
from predict import DemandPredictor

def test_feedback_recalibration():
    print("=" * 60)
    print("🧪 TESTARE FEEDBACK LOOP: PREDICT → ACT → RECALIBRATE")
    print("=" * 60)

    predictor = DemandPredictor()

    # 1. Starea inițială a predicției
    initial_preds = predictor.generate_account_predictions()
    artisan_before = initial_preds[initial_preds["cafe_name"] == "Artisan Brew SRL"].iloc[0]
    print(f"\n[1. ÎNAINTE DE FEEDBACK]")
    print(f"Cafenea: {artisan_before['cafe_name']}")
    print(f"Cantitate recomandată: {artisan_before['recommended_reorder_kg']} kg")
    print(f"Notă calibrare: {artisan_before['model_recalibration']}")

    # 2. Simulăm salvarea unui feedback de negociere (Clientul vrea doar 16 kg în loc de 28 kg)
    print(f"\n[2. EVENIMENT DE FEEDBACK: Clientul negociază la 16 kg]")
    conn = sqlite3.connect("coffee_b2b.db")
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO interaction_logs (customer_id, timestamp, outcome, ordered_kg, summary, cadence_feedback)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        "CUST_01", 
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ORDER_CONFIRMED", 
        16.0, 
        "Clientul a cerut ajustare la 16kg pentru ciclu de 2 săptămâni.", 
        "Consumul săptămânal scade la 8kg/săptămână."
    ))
    conn.commit()
    conn.close()
    print("✅ Feedback salvat în tabela 'interaction_logs'.")

    # 3. Rulăm predicția din nou (Recalibrare)
    recalibrated_preds = predictor.generate_account_predictions()
    artisan_after = recalibrated_preds[recalibrated_preds["cafe_name"] == "Artisan Brew SRL"].iloc[0]
    print(f"\n[3. DUPĂ RECALIBRARE MODEL]")
    print(f"Cafenea: {artisan_after['cafe_name']}")
    print(f"Cantitate recomandată NOUĂ: {artisan_after['recommended_reorder_kg']} kg (ajustat automat)")
    print(f"Notă calibrare: {artisan_after['model_recalibration']}")

    # Verificare aserțiune
    assert artisan_after['recommended_reorder_kg'] == 16.0, "Eroare: Modelul nu a recalibrat cantitatea!"
    print("\n🎉 REZULTAT: Testul Feedback Loop a trecut cu succes! Modelul s-a recalibrat autonom.")

if __name__ == "__main__":
    test_feedback_recalibration()