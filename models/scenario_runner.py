"""
SupplyChainOptima - Batch Scenario Simulation & Optimization Pipeline
Author: Priyanshu
Description: Orchestrates Monte Carlo simulations and PuLP Linear Programs
             across disruption scenarios for top SKUs, persisting results to MySQL.
"""

import os
import sys
import time
from pathlib import Path
from typing import List, Dict, Any
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

sys.path.append(str(Path(__file__).resolve().parent.parent))
from models.monte_carlo import MonteCarloEngine
from models.lp_optimizer import InventoryLPOptimizer


def get_db_engine():
    """Builds SQLAlchemy connection using .env credentials."""
    load_dotenv()
    db_user = os.getenv("DB_USER", "root")
    db_pass = os.getenv("DB_PASSWORD", "password")
    db_host = os.getenv("DB_HOST", "127.0.0.1")
    db_port = os.getenv("DB_PORT", "3306")
    db_name = os.getenv("DB_NAME", "supply_chain_optima")

    connection_uri = f"mysql+pymysql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}?charset=utf8mb4"
    return create_engine(connection_uri, pool_pre_ping=True)


def run_scenario_pipeline(top_n_skus: int = 100, iterations: int = 10000, seed: int = 42):
    """
    Executes the batch Monte Carlo and LP optimization across 3 scenarios:
      1. Baseline
      2. Supplier_Delay_25pct (Lead time +25%)
      3. Demand_Surge_40pct (Demand +40%)
    """
    total_start_time = time.time()
    engine = get_db_engine()

    print("=" * 75)
    print("   SUPPLYCHAINOPTIMA: STOCHASTIC INVENTORY SCENARIO SIMULATION ENGINE")
    print("=" * 75)
    print(f"Loading top {top_n_skus} SKUs by revenue from `vw_sku_metrics`...")

    query = f"""
        SELECT 
            product_card_id,
            product_name,
            category_name,
            unit_price,
            holding_cost_per_unit,
            stockout_penalty_per_unit,
            total_revenue,
            total_units_sold,
            mean_daily_demand,
            std_daily_demand,
            mean_lead_time,
            std_lead_time,
            cv_demand,
            abc_class,
            xyz_class,
            abc_xyz_class
        FROM vw_sku_metrics
        ORDER BY total_revenue DESC
        LIMIT {top_n_skus};
    """
    skus_df = pd.read_sql(query, engine)
    print(f"Retrieved {len(skus_df)} SKUs representing ${skus_df['total_revenue'].sum():,.2f} in revenue.")

    scenarios = [
        {
            "name": "Baseline",
            "lead_time_mult": 1.0,
            "demand_mult": 1.0,
            "description": "Historical demand volatility and standard supplier transit times"
        },
        {
            "name": "Supplier_Delay_25pct",
            "lead_time_mult": 1.25,
            "demand_mult": 1.0,
            "description": "Port congestion / logistics shock (+25% supplier transit delay)"
        },
        {
            "name": "Demand_Surge_40pct",
            "lead_time_mult": 1.0,
            "demand_mult": 1.40,
            "description": "Festive / promotional demand surge (+40% daily order volume)"
        }
    ]

    mc_engine = MonteCarloEngine(iterations=iterations, seed=seed)
    lp_optimizer = InventoryLPOptimizer(target_service_level=0.95)

    scenario_records: List[Dict[str, Any]] = []

    print("\nRunning vectorized Monte Carlo (10,000 iterations) & PuLP LP solves...")
    for s_idx, scenario in enumerate(scenarios, 1):
        s_name = scenario["name"]
        lt_mult = scenario["lead_time_mult"]
        d_mult = scenario["demand_mult"]
        s_start = time.time()

        print(f"\n[Scenario {s_idx}/3] Processing '{s_name}' ({scenario['description']})...")

        for _, row in skus_df.iterrows():
            sku_id = int(row["product_card_id"])
            mu_d = float(row["mean_daily_demand"]) * d_mult
            sigma_d = float(row["std_daily_demand"]) * np.sqrt(d_mult)
            mu_l = float(row["mean_lead_time"]) * lt_mult
            sigma_l = float(row["std_lead_time"]) * np.sqrt(lt_mult)
            h = float(row["holding_cost_per_unit"])
            p = float(row["stockout_penalty_per_unit"])
            annual_demand = float(row["total_units_sold"]) * d_mult

            # 1. 10,000-iteration Monte Carlo Lead-Time Demand Simulation
            ltd_samples = mc_engine.simulate_lead_time_demand(
                mu_d=mu_d,
                sigma_d=sigma_d,
                mu_l=mu_l,
                sigma_l=sigma_l
            )
            mean_ltd = mu_d * mu_l

            # 2. Traditional Static Policy Evaluation (ROP_static = mu_d * mu_l)
            static_rop = max(1.0, mean_ltd)
            static_eval = mc_engine.evaluate_policy_risk(
                lead_time_demands=ltd_samples,
                reorder_point=static_rop,
                holding_cost_unit=h,
                stockout_penalty_unit=p
            )

            # 3. PuLP Linear Program Stochastic Optimization
            lp_res = lp_optimizer.optimize_reorder_policy(
                sku_id=sku_id,
                lead_time_demands=ltd_samples,
                mean_lead_time_demand=mean_ltd,
                annual_demand=annual_demand,
                holding_cost_unit=h,
                stockout_penalty_unit=p
            )
            opt_rop = lp_res["optimized_rop"]
            rec_ss = lp_res["recommended_safety_stock"]

            # 4. Optimized Policy Evaluation
            opt_eval = mc_engine.evaluate_policy_risk(
                lead_time_demands=ltd_samples,
                reorder_point=opt_rop,
                holding_cost_unit=h,
                stockout_penalty_unit=p
            )

            scenario_records.append({
                "product_card_id": sku_id,
                "scenario_name": s_name,
                "static_rop": round(static_rop, 2),
                "optimized_rop": round(opt_rop, 2),
                "recommended_safety_stock": round(rec_ss, 2),
                "stockout_prob_before": round(static_eval["stockout_probability"], 4),
                "stockout_prob_after": round(opt_eval["stockout_probability"], 4),
                "total_cost_before": round(static_eval["total_cost"], 2),
                "total_cost_after": round(opt_eval["total_cost"], 2),
                "service_level_achieved": round(opt_eval["service_level"], 4)
            })

        print(f"  -> Finished {len(skus_df)} SKUs for '{s_name}' in {time.time() - s_start:.2f}s")

    # 5. Persist Results to MySQL
    results_df = pd.DataFrame(scenario_records)
    print(f"\nPersisting {len(results_df)} optimization results into `scenario_results`...")
    
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE scenario_results;"))

    results_df.to_sql("scenario_results", engine, if_exists="append", index=False, chunksize=1000)

    # 6. Executive Verification & KPI Reporting
    print("\n" + "=" * 75)
    print("         EXECUTIVE SCENARIO RESULTS & KPI AUDIT")
    print("=" * 75)
    
    with engine.connect() as conn:
        kpi_query = text("""
            SELECT 
                scenario_name,
                COUNT(*) AS sku_count,
                AVG(static_rop) AS avg_static_rop,
                AVG(optimized_rop) AS avg_opt_rop,
                AVG(recommended_safety_stock) AS avg_safety_stock,
                AVG(stockout_prob_before) * 100 AS avg_stockout_before_pct,
                AVG(stockout_prob_after) * 100 AS avg_stockout_after_pct,
                (AVG(stockout_prob_before) - AVG(stockout_prob_after)) * 100 AS stockout_risk_reduction_pp,
                AVG(service_level_achieved) * 100 AS avg_csl_achieved_pct,
                SUM(total_cost_before) AS total_simulated_cost_before,
                SUM(total_cost_after) AS total_simulated_cost_after,
                SUM(total_cost_before - total_cost_after) AS net_cost_savings
            FROM scenario_results
            GROUP BY scenario_name;
        """)
        summary_df = pd.read_sql(kpi_query, conn)
        print(summary_df.to_string(index=False))

    total_duration = time.time() - total_start_time
    print("=" * 75)
    print(f"BATCH SCENARIO PIPELINE EXECUTED IN {total_duration:.2f}s (NFR Target: <30s)")
    print("=" * 75)


if __name__ == "__main__":
    run_scenario_pipeline()
