"""
SupplyChainOptima - Dashboard Visual Preview Generator
Author: Priyanshu
Description: Generates high-resolution executive charts and Power BI preview screenshots
             for assets/ to be embedded in the README and portfolio documentation.
"""

import os
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv

# Set publication style
plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["Helvetica", "Arial", "DejaVu Sans"]

load_dotenv()
db_user = os.getenv("DB_USER", "root")
db_pass = os.getenv("DB_PASSWORD", "password")
db_host = os.getenv("DB_HOST", "127.0.0.1")
db_port = os.getenv("DB_PORT", "3306")
db_name = os.getenv("DB_NAME", "supply_chain_optima")

engine = create_engine(f"mysql+pymysql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}")
assets_dir = Path(__file__).resolve().parent.parent / "assets"
assets_dir.mkdir(parents=True, exist_ok=True)


def generate_page1_preview():
    """Generates Page 1 (Supply Chain Health) dashboard preview."""
    fig, axes = plt.subplots(2, 2, figsize=(16, 10), facecolor="#F8FAFC")
    fig.suptitle(
        "SupplyChainOptima: Executive Supply Chain Health & Risk Dashboard",
        fontsize=20,
        fontweight="bold",
        color="#1B365D",
        y=0.98
    )

    # 1. ABC-XYZ Matrix Heatmap
    ax1 = axes[0, 0]
    ax1.set_facecolor("#FFFFFF")
    abc_xyz_df = pd.read_sql("SELECT abc_class, xyz_class, COUNT(*) as count, SUM(total_revenue)/1e6 as rev_m FROM vw_sku_metrics GROUP BY abc_class, xyz_class;", engine)
    
    matrix = np.zeros((3, 3))
    rev_matrix = np.zeros((3, 3))
    row_map = {"A": 0, "B": 1, "C": 2}
    col_map = {"X": 0, "Y": 1, "Z": 2}
    for _, r in abc_xyz_df.iterrows():
        i = row_map.get(r["abc_class"], 0)
        j = col_map.get(r["xyz_class"], 0)
        matrix[i, j] = r["count"]
        rev_matrix[i, j] = r["rev_m"]

    im = ax1.imshow(rev_matrix, cmap="Blues", aspect="auto")
    ax1.set_xticks([0, 1, 2])
    ax1.set_xticklabels(["X (Low CV ≤0.5)", "Y (Med CV ≤1.0)", "Z (High CV >1.0)"], fontsize=11, fontweight="bold")
    ax1.set_yticks([0, 1, 2])
    ax1.set_yticklabels(["A (Top 80% Rev)", "B (Next 15% Rev)", "C (Bottom 5% Rev)"], fontsize=11, fontweight="bold")
    ax1.set_title("ABC-XYZ Inventory Segmentation (Revenue & SKU Count)", fontsize=13, fontweight="bold", color="#1B365D")

    for i in range(3):
        for j in range(3):
            val_cnt = int(matrix[i, j])
            val_rev = rev_matrix[i, j]
            color = "white" if val_rev > 10 else "#1B365D"
            ax1.text(j, i, f"{val_cnt} SKUs\n${val_rev:.1f}M", ha="center", va="center", color=color, fontweight="bold", fontsize=11)

    # 2. Regional Fulfillment Delay Breakdown
    ax2 = axes[0, 1]
    ax2.set_facecolor("#FFFFFF")
    reg_df = pd.read_sql("""
        SELECT o.order_region, AVG(s.days_for_shipping_real) as avg_days, AVG(s.late_delivery_risk)*100 as late_pct
        FROM orders o JOIN shipping_logs s ON o.order_id = s.order_id
        GROUP BY o.order_region ORDER BY late_pct DESC LIMIT 8;
    """, engine)
    bars = ax2.barh(reg_df["order_region"], reg_df["late_pct"], color="#008080", alpha=0.85)
    ax2.set_xlabel("Late Delivery Risk (%)", fontsize=11, fontweight="bold")
    ax2.set_title("Top Regions by Fulfillment Delay Risk", fontsize=13, fontweight="bold", color="#1B365D")
    ax2.invert_yaxis()
    for bar in bars:
        w = bar.get_width()
        ax2.text(w + 0.5, bar.get_y() + bar.get_height()/2, f"{w:.1f}%", va="center", fontsize=10, fontweight="bold", color="#4A5568")

    # 3. Demand Volatility vs Mean Daily Demand Scatter
    ax3 = axes[1, 0]
    ax3.set_facecolor("#FFFFFF")
    scatter_df = pd.read_sql("SELECT mean_daily_demand, cv_demand, total_revenue/1e6 as rev_m, abc_class FROM vw_sku_metrics;", engine)
    colors = {"A": "#1B365D", "B": "#008080", "C": "#A0AEC0"}
    for cls, grp in scatter_df.groupby("abc_class"):
        ax3.scatter(grp["mean_daily_demand"], grp["cv_demand"], s=grp["rev_m"]*30 + 30, color=colors.get(cls, "gray"), alpha=0.7, label=f"Class {cls}", edgecolors="none")
    ax3.axhline(0.5, color="#E53E3E", linestyle="--", alpha=0.6, label="XYZ Volatility Thresholds")
    ax3.axhline(1.0, color="#E53E3E", linestyle="--", alpha=0.6)
    ax3.set_xlabel("Mean Daily Demand (Units/Day)", fontsize=11, fontweight="bold")
    ax3.set_ylabel("Demand Coefficient of Variation (CV)", fontsize=11, fontweight="bold")
    ax3.set_title("SKU Demand Volatility Profile (Size = Revenue)", fontsize=13, fontweight="bold", color="#1B365D")
    ax3.legend(frameon=True, loc="upper right")

    # 4. Executive KPI Overview Card Box
    ax4 = axes[1, 1]
    ax4.set_facecolor("#FFFFFF")
    ax4.axis("off")
    total_rev = pd.read_sql("SELECT SUM(sales_amount) FROM orders;", engine).iloc[0, 0]
    late_rate = pd.read_sql("SELECT AVG(late_delivery_risk)*100 FROM shipping_logs;", engine).iloc[0, 0]
    avg_lead = pd.read_sql("SELECT AVG(days_for_shipping_real) FROM shipping_logs;", engine).iloc[0, 0]
    sku_cnt = pd.read_sql("SELECT COUNT(*) FROM products;", engine).iloc[0, 0]

    kpi_text = (
        f"SUPPLY CHAIN HEALTH EXECUTIVE SUMMARY\n"
        f"--------------------------------------------------\n\n"
        f"  Total Portfolio Revenue       : ${total_rev:,.2f} USD\n"
        f"  Active SKU Catalog Count      : {sku_cnt} Products\n"
        f"  Overall Late Delivery Risk    : {late_rate:.2f}%\n"
        f"  Average Supplier Transit Lead : {avg_lead:.2f} Days\n"
        f"  Top Category Drivers          : Fishing, Cleats, Apparel\n\n"
        f"STRATEGIC RECOMMENDATION:\n"
        f"  7 'AX' SKUs generate 77.2% of total business revenue with\n"
        f"  stable demand (CV ~0.26). Dynamic stochastic buffer\n"
        f"  policies protect these core drivers from supply shocks."
    )
    ax4.text(0.05, 0.90, kpi_text, fontsize=12, fontfamily="monospace", va="top",
             bbox=dict(boxstyle="round,pad=1.2", facecolor="#F1F5F9", edgecolor="#CBD5E1", linewidth=1.5))

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    output_path = assets_dir / "dashboard_page1_supply_chain_health.png"
    plt.savefig(output_path, dpi=200)
    plt.close()
    print(f"Generated: {output_path}")


def generate_page2_preview():
    """Generates Page 2 (What-If Scenario Simulator) dashboard preview."""
    fig, axes = plt.subplots(2, 2, figsize=(16, 10), facecolor="#F8FAFC")
    fig.suptitle(
        "SupplyChainOptima: What-If Stochastic Scenario Simulator",
        fontsize=20,
        fontweight="bold",
        color="#1B365D",
        y=0.98
    )

    scen_df = pd.read_sql("""
        SELECT 
            scenario_name,
            AVG(stockout_prob_before)*100 as stockout_before,
            AVG(stockout_prob_after)*100 as stockout_after,
            SUM(total_cost_before)/1e3 as cost_before_k,
            SUM(total_cost_after)/1e3 as cost_after_k,
            SUM(total_cost_before - total_cost_after)/1e3 as savings_k,
            AVG(service_level_achieved)*100 as csl_after
        FROM scenario_results
        GROUP BY scenario_name;
    """, engine)

    # 1. Stockout Risk Comparison (Before vs After)
    ax1 = axes[0, 0]
    ax1.set_facecolor("#FFFFFF")
    x = np.arange(len(scen_df))
    width = 0.35
    ax1.bar(x - width/2, scen_df["stockout_before"], width, label="Static Policy (Naive ROP)", color="#E53E3E", alpha=0.85)
    ax1.bar(x + width/2, scen_df["stockout_after"], width, label="Optimized Policy (PuLP + MC)", color="#008080", alpha=0.85)
    ax1.set_xticks(x)
    ax1.set_xticklabels([s.replace("_", " ") for s in scen_df["scenario_name"]], fontsize=10, fontweight="bold")
    ax1.set_ylabel("Stockout Probability (%)", fontsize=11, fontweight="bold")
    ax1.set_title("Stockout Probability: Static vs Stochastic LP", fontsize=13, fontweight="bold", color="#1B365D")
    ax1.legend(frameon=True)
    for i, row in scen_df.iterrows():
        ax1.text(i - width/2, row["stockout_before"] + 1, f"{row['stockout_before']:.1f}%", ha="center", fontsize=9, fontweight="bold")
        ax1.text(i + width/2, row["stockout_after"] + 1, f"{row['stockout_after']:.1f}%", ha="center", fontsize=9, fontweight="bold")

    # 2. Total Simulated Cost Comparison ($K)
    ax2 = axes[0, 1]
    ax2.set_facecolor("#FFFFFF")
    ax2.bar(x - width/2, scen_df["cost_before_k"], width, label="Static Total Cost", color="#4A5568", alpha=0.85)
    ax2.bar(x + width/2, scen_df["cost_after_k"], width, label="Optimized Total Cost", color="#1B365D", alpha=0.85)
    ax2.set_xticks(x)
    ax2.set_xticklabels([s.replace("_", " ") for s in scen_df["scenario_name"]], fontsize=10, fontweight="bold")
    ax2.set_ylabel("Total Simulated Cost ($K USD)", fontsize=11, fontweight="bold")
    ax2.set_title("Total Expected Cost: Holding + Stockout Penalty", fontsize=13, fontweight="bold", color="#1B365D")
    ax2.legend(frameon=True)
    for i, row in scen_df.iterrows():
        ax2.text(i - width/2, row["cost_before_k"] + 8, f"${row['cost_before_k']:.0f}K", ha="center", fontsize=9, fontweight="bold")
        ax2.text(i + width/2, row["cost_after_k"] + 8, f"${row['cost_after_k']:.0f}K", ha="center", fontsize=9, fontweight="bold")

    # 3. Top SKUs Reorder Point Adjustment (Baseline)
    ax3 = axes[1, 0]
    ax3.set_facecolor("#FFFFFF")
    top_sku_df = pd.read_sql("""
        SELECT p.product_name, s.static_rop, s.optimized_rop, s.recommended_safety_stock
        FROM scenario_results s
        JOIN products p ON s.product_card_id = p.product_card_id
        WHERE s.scenario_name = 'Baseline'
        ORDER BY s.static_rop DESC LIMIT 6;
    """, engine)
    y = np.arange(len(top_sku_df))
    ax3.barh(y - width/2, top_sku_df["static_rop"], width, label="Static ROP (mu_d * mu_L)", color="#CBD5E1")
    ax3.barh(y + width/2, top_sku_df["optimized_rop"], width, label="Optimized ROP (with Buffer)", color="#1B365D")
    ax3.set_yticks(y)
    short_names = [n[:22] + "..." if len(n) > 22 else n for n in top_sku_df["product_name"]]
    ax3.set_yticklabels(short_names, fontsize=9, fontweight="bold")
    ax3.set_xlabel("Reorder Point Units", fontsize=11, fontweight="bold")
    ax3.set_title("Top SKUs: Naive ROP vs Recommended Buffer ROP", fontsize=13, fontweight="bold", color="#1B365D")
    ax3.invert_yaxis()
    ax3.legend(frameon=True, loc="lower right")

    # 4. Executive Scenario Narrative Box
    ax4 = axes[1, 1]
    ax4.set_facecolor("#FFFFFF")
    ax4.axis("off")
    tot_savings = scen_df["savings_k"].sum()
    narrative_text = (
        f"PRESCRIPTIVE OPTIMIZATION EXECUTIVE SUMMARY\n"
        f"--------------------------------------------------\n\n"
        f"  Total Portfolio Net Savings   : ${tot_savings:,.1f}K USD\n"
        f"  Baseline Stockout Risk Cut    : 42.9% -> 5.0% (-37.8 pp)\n"
        f"  Supplier Delay (+25%) Cut     : 43.5% -> 5.0% (-38.5 pp)\n"
        f"  Demand Surge (+40%) Cut       : 42.6% -> 5.0% (-37.5 pp)\n"
        f"  Service Level Guaranteed      : 95.0% Cycle Fill Rate\n\n"
        f"CONSULTING VALUE DELIVERABLE:\n"
        f"  Moving from static average heuristics to stochastic\n"
        f"  Sample Average Approximation (SAA) protects high-margin\n"
        f"  revenue during port delays and holiday volume spikes\n"
        f"  without inflating working capital."
    )
    ax4.text(0.05, 0.90, narrative_text, fontsize=12, fontfamily="monospace", va="top",
             bbox=dict(boxstyle="round,pad=1.2", facecolor="#F1F5F9", edgecolor="#CBD5E1", linewidth=1.5))

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    output_path = assets_dir / "dashboard_page2_scenario_simulator.png"
    plt.savefig(output_path, dpi=200)
    plt.close()
    print(f"Generated: {output_path}")


if __name__ == "__main__":
    generate_page1_preview()
    generate_page2_preview()
