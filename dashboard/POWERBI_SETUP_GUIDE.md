# Power BI Executive Dashboard Setup Guide: SupplyChainOptima

This guide provides end-to-end instructions for connecting **Power BI Desktop** to MySQL, importing the analytical models, setting up relationships, creating the DAX measures table, and designing the two executive pages.

---

## 1. Connecting Power BI to MySQL Warehouse

1. Open **Power BI Desktop**.
2. Click **Get Data** $\rightarrow$ **Database** $\rightarrow$ **MySQL Database**.
3. In the connection dialog:
   * **Server:** `127.0.0.1:3306` (or `localhost:3306`)
   * **Database:** `supply_chain_optima`
   * **Data Connectivity Mode:** `Import`
4. When prompted for credentials, select the **Database** tab:
   * **User name:** `root`
   * **Password:** `password` (or your configured `.env` password)
5. In the Navigator pane, select the following 4 tables/views:
   * `vw_sku_metrics` (SKU dimension table with volatility & ABC-XYZ classes)
   * `scenario_results` (Fact table with 10,000-iteration Monte Carlo & LP outcomes)
   * `orders` (Fact table for transactional sales)
   * `shipping_logs` (Fact table for fulfillment logistics & late delivery risks)
6. Click **Load**.

---

## 2. Data Modeling & Relationship Diagram

Navigate to the **Model View** (left sidebar icon with boxes) and verify/create the following 1-to-many single-direction relationships:

```
      +-----------------------------+
      |       vw_sku_metrics        |  (Dimension Table)
      |  (PK: product_card_id)      |
      +--------------+--------------+
                     | 1
                     |
         +-----------+-----------+
         | *                     | *
+--------v-------+      +--------v---------+
|     orders     |      | scenario_results | (Fact Table)
|  (FK: product) |      |  (FK: product)   |
+--------+-------+      +------------------+
         | *
         |
         | 1 (by order_id)
+--------v---------+
|  shipping_logs   |    (Fact Table)
+------------------+
```

---

## 3. Dedicated `_Measures` Table Setup

1. In the **Home** ribbon, click **Enter Data**.
2. Name the table `_Measures` and click **Load**.
3. Right-click `_Measures` $\rightarrow$ **New Measure**, and paste each measure from [dax_measures.dax](file:///Users/priyanshu/Desktop/Projects/SupplyChainOptima/dashboard/dax_measures.dax).

---

## 4. Page 1: Supply Chain Health (Executive Operational View)

### Palette & Typography
* **Corporate Theme:** Consulting Executive Palette
  * Primary Navy: `#1B365D`
  * Slate Grey: `#4A5568`
  * Accent Teal: `#008080`
  * Warning Coral: `#E53E3E`
  * Background: `#F7FAFC`

### Visual Layout
1. **Header Banner:**
   * Title: **"SupplyChainOptima: Supply Chain Health & Operational Risk"**
   * Subtitle: "Portfolio Volatility, ABC-XYZ Segmentation, and Logistics Fulfillment Integrity"
2. **Top KPI Cards (Row 1):**
   * Card 1: `[Total Revenue]` (formatted as currency `$36.6M`)
   * Card 2: `[On Time Delivery Rate %]` (formatted as percentage `45.2%`)
   * Card 3: `[Late Delivery Risk %]` (formatted as percentage `54.8%`)
   * Card 4: `[Average Lead Time Days]` (formatted as `3.50 Days`)
3. **ABC-XYZ Matrix Visual (Left Column, Row 2):**
   * **Visual Type:** Matrix / Heatmap
   * **Rows:** `vw_sku_metrics[abc_class]`
   * **Columns:** `vw_sku_metrics[xyz_class]`
   * **Values:** `COUNT(vw_sku_metrics[product_card_id])`, `SUM(vw_sku_metrics[total_revenue])`
   * **Conditional Formatting:** Gradient background from light teal to deep navy.
4. **Logistics Delay by Global Region (Right Column, Row 2):**
   * **Visual Type:** Clustered Bar Chart
   * **Y-Axis:** `orders[order_region]`
   * **X-Axis:** `Average Lead Time Days` or `Late Delivery Count`
   * **Color:** Accent Teal (`#008080`)
5. **SKU Volatility Scatter Plot (Row 3):**
   * **Visual Type:** Scatter Chart
   * **X-Axis:** `vw_sku_metrics[mean_daily_demand]`
   * **Y-Axis:** `vw_sku_metrics[cv_demand]` (Coefficient of Variation)
   * **Size:** `vw_sku_metrics[total_revenue]`
   * **Legend:** `vw_sku_metrics[abc_xyz_class]`

---

## 5. Page 2: What-If Scenario Simulator (Prescriptive Analytics)

### Visual Layout
1. **Dynamic Header Banner:**
   * Visual: Card visual bound to `[Dynamic Scenario Title]`
   * Subtitle: "Stochastic Monte Carlo (10,000 Iterations) vs. PuLP Linear Program Optimization"
2. **Interactive Slicer (Top Ribbon):**
   * **Visual Type:** Slicer (Tile/Button style)
   * **Field:** `scenario_results[scenario_name]`
   * **Options:** `Baseline` | `Supplier_Delay_25pct` | `Demand_Surge_40pct`
3. **Comparative Executive KPI Cards (Row 1):**
   * Card 1: `[Total Cost Savings $]` (Formatted as `$122.4K` / `$145.3K` / `$168.6K`)
   * Card 2: `[Stockout Risk Reduction %]` (Formatted as `-37.8 pp`)
   * Card 3: `[Overall Fill Rate %]` (Target: `95.0%`)
   * Card 4: `[Total Recommended Safety Stock Units]`
4. **Side-by-Side Policy Comparison (Middle Row):**
   * **Visual Type:** Clustered Column Chart
   * **X-Axis:** Top 15 SKUs (`product_name`)
   * **Values:** `scenario_results[static_rop]` vs `scenario_results[optimized_rop]`
   * **Visual 2:** Clustered Column Chart for Total Cost Before vs After
5. **Executive Callout Narrative Box:**
   * Text Card bound to measure `[Dynamic Executive Callout]`.
   * Automatically prints executive summary for consulting client presentations.
