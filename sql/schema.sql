-- ============================================================================
-- SupplyChainOptima: Database Schema (MySQL 8.0+)
-- Author: Priyanshu
-- Description: Normalized analytical schema for supply chain stochastic 
--              inventory simulation & scenario planning.
-- ============================================================================

CREATE DATABASE IF NOT EXISTS supply_chain_optima;
USE supply_chain_optima;

-- Drop dependent tables in reverse dependency order
DROP TABLE IF EXISTS scenario_results;
DROP TABLE IF EXISTS audit_quarantine;
DROP TABLE IF EXISTS shipping_logs;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;

-- ----------------------------------------------------------------------------
-- 1. Table: products
-- Master product catalog with estimated cost and penalty parameters
-- ----------------------------------------------------------------------------
CREATE TABLE products (
    product_card_id INT NOT NULL,
    product_name VARCHAR(255) NOT NULL,
    category_name VARCHAR(100) NOT NULL,
    unit_price DECIMAL(10, 2) NOT NULL,
    holding_cost_per_unit DECIMAL(10, 4) NOT NULL COMMENT 'Unit holding cost per period (~20% annual rate)',
    stockout_penalty_per_unit DECIMAL(10, 4) NOT NULL COMMENT 'Stockout penalty per unit (~1.5x margin/price)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (product_card_id),
    INDEX idx_category (category_name),
    INDEX idx_unit_price (unit_price)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 2. Table: orders
-- Transactional line-item records for customer orders
-- ----------------------------------------------------------------------------
CREATE TABLE orders (
    order_item_id INT NOT NULL,
    order_id INT NOT NULL,
    order_date DATETIME NOT NULL,
    product_card_id INT NOT NULL,
    order_quantity INT NOT NULL,
    sales_amount DECIMAL(12, 2) NOT NULL,
    order_region VARCHAR(100) NOT NULL,
    order_status VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (order_item_id),
    INDEX idx_order_id (order_id),
    INDEX idx_order_date (order_date),
    INDEX idx_product_card_id (product_card_id),
    INDEX idx_order_region (order_region),
    INDEX idx_order_status (order_status),
    CONSTRAINT fk_orders_product FOREIGN KEY (product_card_id)
        REFERENCES products (product_card_id)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 3. Table: shipping_logs
-- Logistics and fulfillment tracking per order
-- ----------------------------------------------------------------------------
CREATE TABLE shipping_logs (
    shipping_id INT AUTO_INCREMENT NOT NULL,
    order_id INT NOT NULL,
    shipping_date DATETIME NOT NULL,
    days_for_shipping_real INT NOT NULL,
    days_for_shipment_scheduled INT NOT NULL,
    shipping_mode VARCHAR(50) NOT NULL,
    late_delivery_risk TINYINT(1) NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (shipping_id),
    INDEX idx_shipping_order_id (order_id),
    INDEX idx_shipping_mode (shipping_mode),
    INDEX idx_late_delivery (late_delivery_risk),
    INDEX idx_shipping_date (shipping_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 4. Table: audit_quarantine
-- Automated data governance and integrity quarantine table
-- ----------------------------------------------------------------------------
CREATE TABLE audit_quarantine (
    quarantine_id INT AUTO_INCREMENT NOT NULL,
    order_id INT NULL,
    order_item_id INT NULL,
    product_card_id INT NULL,
    issue_type VARCHAR(100) NOT NULL,
    issue_description TEXT NOT NULL,
    raw_payload JSON NULL,
    quarantined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (quarantine_id),
    INDEX idx_quarantine_issue (issue_type),
    INDEX idx_quarantined_at (quarantined_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ----------------------------------------------------------------------------
-- 5. Table: scenario_results
-- Prescriptive inventory policies and Monte Carlo risk outputs
-- ----------------------------------------------------------------------------
CREATE TABLE scenario_results (
    result_id INT AUTO_INCREMENT NOT NULL,
    product_card_id INT NOT NULL,
    scenario_name VARCHAR(100) NOT NULL,
    static_rop DECIMAL(12, 2) NOT NULL,
    optimized_rop DECIMAL(12, 2) NOT NULL,
    recommended_safety_stock DECIMAL(12, 2) NOT NULL,
    stockout_prob_before DECIMAL(6, 4) NOT NULL,
    stockout_prob_after DECIMAL(6, 4) NOT NULL,
    total_cost_before DECIMAL(14, 2) NOT NULL,
    total_cost_after DECIMAL(14, 2) NOT NULL,
    service_level_achieved DECIMAL(6, 4) NOT NULL,
    simulated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (result_id),
    UNIQUE KEY uq_sku_scenario (product_card_id, scenario_name),
    INDEX idx_scenario_name (scenario_name),
    CONSTRAINT fk_scenario_product FOREIGN KEY (product_card_id)
        REFERENCES products (product_card_id)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
