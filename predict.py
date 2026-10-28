import sqlite3
from datetime import datetime
import pandas as pd
import numpy as np


class DemandPredictor:
    """
    Modulul de PREDICT:
    Extrage istoricul de comenzi, calculează ritmul de consum
    și estimează momentul epuizării stocului și riscul de churn.
    """

    def __init__(self, db_path: str = "coffee_b2b.db"):
        self.db_path = db_path

    def _fetch_data(self) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Extrage datele și redenumește coloanele pentru a evita coliziunile de nume."""
        conn = sqlite3.connect(self.db_path)
        customers = pd.read_sql_query("SELECT * FROM customers", conn)
        orders = pd.read_sql_query("SELECT * FROM orders", conn)
        products = pd.read_sql_query("SELECT * FROM products", conn)
        conn.close()

        # Redenumim explicit pentru a ști exact ce este fiecare 'name'
        customers = customers.rename(columns={"name": "cafe_name"})
        products = products.rename(columns={"name": "product_name"})

        # Convertim data comenzilor la datetime
        orders["order_date"] = pd.to_datetime(orders["order_date"])
        return customers, orders, products

    def generate_account_predictions(self) -> pd.DataFrame:
        customers, orders, products = self._fetch_data()
        today = pd.to_datetime(datetime.now().strftime("%Y-%m-%d"))

        # Extragem feedback-ul recent din interaction_logs (FEEDBACK LOOP)
        conn = sqlite3.connect(self.db_path)
        try:
            feedback_df = pd.read_sql_query(
                "SELECT customer_id, outcome, ordered_kg, cadence_feedback FROM interaction_logs ORDER BY log_id DESC", 
                conn
            )
        except Exception:
            feedback_df = pd.DataFrame()
        conn.close()

        latest_orders = orders.sort_values("order_date").groupby(["customer_id", "product_id"]).last().reset_index()
        merged = latest_orders.merge(customers, on="customer_id").merge(products, on="product_id")

        predictions = []

        for _, row in merged.iterrows():
            cust_id = row["customer_id"]
            weekly_consumption = row["weekly_consumption_kg"]
            
            # --- RECALIBRARE DIN FEEDBACK LOOP ---
            recalibration_note = "Baseline"
            if not feedback_df.empty:
                cust_feedback = feedback_df[feedback_df["customer_id"] == cust_id]
                if not cust_feedback.empty:
                    last_fb = cust_feedback.iloc[0]
                    # Dacă clientul a cerut explicit o cantitate diferită, recalibrăm consumul
                    if last_fb["outcome"] == "ORDER_CONFIRMED" and last_fb["ordered_kg"] and last_fb["ordered_kg"] > 0:
                        # Recalibrăm consumul săptămânal bazat pe cantitatea reală agreată
                        weekly_consumption = last_fb["ordered_kg"] / 2.0  # ciclu de 2 săptămâni
                        recalibration_note = f"Recalibrat din feedback recent ({last_fb['ordered_kg']} kg/2 săpt)"
            
            daily_burn_rate = weekly_consumption / 7.0
            days_since_order = (today - row["order_date"]).days
            total_purchased = row["quantity_kg"]

            estimated_consumed = days_since_order * daily_burn_rate
            estimated_stock_left = max(0.0, total_purchased - estimated_consumed)

            if daily_burn_rate > 0:
                days_until_stockout = estimated_stock_left / daily_burn_rate if estimated_stock_left > 0 else -(days_since_order - (total_purchased / daily_burn_rate))
            else:
                days_until_stockout = 999

            if days_until_stockout < -5:
                status, urgency_score, action_needed = "CHURN_ALERT", 0.95, "WIN_BACK_CAMPAIGN"
            elif 0 <= days_until_stockout <= 2:
                status, urgency_score, action_needed = "URGENT_RESTOCK", 0.90, "TRIGGER_RESTOCK_AGENT"
            elif 2 < days_until_stockout <= 5:
                status, urgency_score, action_needed = "MONITOR", 0.50, "NO_ACTION"
            else:
                status, urgency_score, action_needed = "HEALTHY", 0.10, "NO_ACTION"

            recommended_reorder_kg = round(weekly_consumption * 2, 1)

            predictions.append({
                "customer_id": cust_id,
                "cafe_name": row["cafe_name"],
                "contact_person": row["contact_person"],
                "channel": row["channel"],
                "last_product_id": row["product_id"],
                "last_product_name": row["product_name"],
                "estimated_stock_left_kg": round(estimated_stock_left, 1), 
                "days_until_stockout": round(days_until_stockout, 1),
                "recommended_reorder_kg": recommended_reorder_kg,
                "urgency_score": urgency_score,
                "status": status,
                "action_needed": action_needed,
                "model_recalibration": recalibration_note
            })

        df_results = pd.DataFrame(predictions).sort_values(by="urgency_score", ascending=False)
        return df_results


if __name__ == "__main__":
    predictor = DemandPredictor()
    results = predictor.generate_account_predictions()

    print("\n--- REZULTATE PREDICTIVE ENGINE (OptiComm Style) ---")
    print(
        results[
            [
                "cafe_name",
                "last_product_name",
                "days_until_stockout",
                "status",
                "action_needed",
                "urgency_score",
            ]
        ].to_string(index=False)
    )