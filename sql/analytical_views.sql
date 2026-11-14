-- ============================================================================
-- SupplyChainOptima: Analytical Views Layer (MySQL 8.0+)
-- Author: Priyanshu
-- Description: CTEs and Window Functions for SKU volatility, lead-time variance,
--              rolling 30-day demand, and ABC-XYZ matrix segmentation.
-- ============================================================================

USE supply_chain_optima;

-- Drop existing views
DROP VIEW IF EXISTS vw_sku_abc_xyz;
DROP VIEW IF EXISTS vw_sku_metrics;
DROP VIEW IF EXISTS vw_sku_daily_demand;

-- ----------------------------------------------------------------------------
-- 1. View: vw_sku_daily_demand
-- Daily aggregated demand per SKU with 30-day rolling demand window function
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_sku_daily_demand AS
WITH daily_aggregation AS (
    SELECT 
        o.product_card_id,
        DATE(o.order_date) AS order_day,
        SUM(o.order_quantity) AS daily_demand,
        SUM(o.sales_amount) AS daily_sales
    FROM orders o
    GROUP BY o.product_card_id, DATE(o.order_date)
)
SELECT 
    product_card_id,
    order_day,
    daily_demand,
    daily_sales,
    -- Window Function: Rolling 30-day demand
    SUM(daily_demand) OVER (
        PARTITION BY product_card_id 
        ORDER BY order_day 
        ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
    ) AS rolling_30d_demand,
    AVG(daily_demand) OVER (
        PARTITION BY product_card_id 
        ORDER BY order_day 
        ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
    ) AS rolling_30d_avg_demand
FROM daily_aggregation;

-- ----------------------------------------------------------------------------
-- 2. View: vw_sku_metrics
-- SKU-level statistical profiling (demand & lead time) + ABC-XYZ Segmentation
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_sku_metrics AS
WITH sku_demand_stats AS (
    -- Daily demand statistical moments: mean (mu_d) and standard deviation (sigma_d)
    SELECT 
        product_card_id,
        COUNT(order_day) AS active_demand_days,
        SUM(daily_demand) AS total_units_sold,
        SUM(daily_sales) AS total_revenue,
        AVG(daily_demand) AS mean_daily_demand,
        COALESCE(STDDEV_SAMP(daily_demand), 0.0) AS std_daily_demand
    FROM vw_sku_daily_demand
    GROUP BY product_card_id
),
sku_lead_time_stats AS (
    -- Supplier lead time moments: mean (mu_L) and standard deviation (sigma_L)
    SELECT 
        o.product_card_id,
        AVG(s.days_for_shipping_real) AS mean_lead_time,
        COALESCE(STDDEV_SAMP(s.days_for_shipping_real), 0.0) AS std_lead_time,
        AVG(s.days_for_shipment_scheduled) AS scheduled_lead_time,
        AVG(s.late_delivery_risk) AS late_delivery_rate
    FROM orders o
    JOIN shipping_logs s ON o.order_id = s.order_id
    GROUP BY o.product_card_id
),
sku_consolidated AS (
    SELECT 
        p.product_card_id,
        p.product_name,
        p.category_name,
        p.unit_price,
        p.holding_cost_per_unit,
        p.stockout_penalty_per_unit,
        d.total_units_sold,
        d.total_revenue,
        d.active_demand_days,
        d.mean_daily_demand,
        d.std_daily_demand,
        l.mean_lead_time,
        l.std_lead_time,
        l.scheduled_lead_time,
        l.late_delivery_rate,
        -- Demand Coefficient of Variation (CV = sigma_d / mu_d)
        CASE 
            WHEN d.mean_daily_demand > 0 THEN d.std_daily_demand / d.mean_daily_demand 
            ELSE 0.0 
        END AS cv_demand,
        -- Window Function: Total Portfolio Revenue across all SKUs
        SUM(d.total_revenue) OVER () AS portfolio_total_revenue,
        -- Window Function: Cumulative Revenue Pareto running total
        SUM(d.total_revenue) OVER (
            ORDER BY d.total_revenue DESC, p.product_card_id ASC
        ) AS cumulative_revenue
    FROM products p
    JOIN sku_demand_stats d ON p.product_card_id = d.product_card_id
    JOIN sku_lead_time_stats l ON p.product_card_id = l.product_card_id
),
sku_segmented AS (
    SELECT 
        *,
        (cumulative_revenue / portfolio_total_revenue) AS cumulative_revenue_share,
        -- ABC Classification (Revenue Contribution Pareto Rule)
        CASE 
            WHEN (cumulative_revenue / portfolio_total_revenue) <= 0.80 THEN 'A'
            WHEN (cumulative_revenue / portfolio_total_revenue) <= 0.95 THEN 'B'
            ELSE 'C'
        END AS abc_class,
        -- XYZ Classification (Demand Volatility / Predictability)
        CASE 
            WHEN cv_demand <= 0.50 THEN 'X'
            WHEN cv_demand <= 1.00 THEN 'Y'
            ELSE 'Z'
        END AS xyz_class
    FROM sku_consolidated
)
SELECT 
    product_card_id,
    product_name,
    category_name,
    unit_price,
    holding_cost_per_unit,
    stockout_penalty_per_unit,
    total_units_sold,
    total_revenue,
    active_demand_days,
    ROUND(mean_daily_demand, 4) AS mean_daily_demand,
    ROUND(std_daily_demand, 4) AS std_daily_demand,
    ROUND(mean_lead_time, 4) AS mean_lead_time,
    ROUND(std_lead_time, 4) AS std_lead_time,
    ROUND(scheduled_lead_time, 4) AS scheduled_lead_time,
    ROUND(late_delivery_rate, 4) AS late_delivery_rate,
    ROUND(cv_demand, 4) AS cv_demand,
    ROUND(cumulative_revenue_share, 4) AS cumulative_revenue_share,
    abc_class,
    xyz_class,
    CONCAT(abc_class, xyz_class) AS abc_xyz_class
FROM sku_segmented;

-- ----------------------------------------------------------------------------
-- 3. View: vw_sku_abc_xyz
-- Executive ABC-XYZ Matrix Summary
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_sku_abc_xyz AS
SELECT 
    abc_xyz_class,
    abc_class,
    xyz_class,
    COUNT(*) AS sku_count,
    ROUND(SUM(total_revenue), 2) AS segment_revenue,
    ROUND(AVG(unit_price), 2) AS avg_unit_price,
    ROUND(AVG(mean_daily_demand), 2) AS avg_daily_demand,
    ROUND(AVG(cv_demand), 4) AS avg_demand_volatility,
    ROUND(AVG(mean_lead_time), 2) AS avg_lead_time_days,
    CASE 
        WHEN abc_xyz_class = 'AX' THEN 'Automated replenishment, lean buffer stock'
        WHEN abc_xyz_class = 'AY' THEN 'Periodic review, dynamic safety stock buffer'
        WHEN abc_xyz_class = 'AZ' THEN 'High-touch stochastic buffer, supplier SLA monitoring'
        WHEN abc_xyz_class = 'BX' THEN 'Standard reorder point (ROP) policy'
        WHEN abc_xyz_class = 'BY' THEN 'Safety stock buffer with seasonal tuning'
        WHEN abc_xyz_class = 'BZ' THEN 'Buffer stock or regional pooling'
        WHEN abc_xyz_class = 'CX' THEN 'Bulk ordering / min-max replenishment'
        WHEN abc_xyz_class = 'CY' THEN 'Make-to-order or low stock threshold'
        WHEN abc_xyz_class = 'CZ' THEN 'Rationalize / de-list / on-demand fulfillment'
        ELSE 'Review inventory strategy'
    END AS strategic_inventory_policy
FROM vw_sku_metrics
GROUP BY abc_xyz_class, abc_class, xyz_class
ORDER BY abc_class ASC, xyz_class ASC;
