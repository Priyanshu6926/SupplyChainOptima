"""
SupplyChainOptima - Ingestion & Data Validation Pipeline
Author: Priyanshu
Description: Ingests raw CSV order records into normalized MySQL tables
             with transactional safety, data quality gates, and high-performance bulk writes.
"""

import os
import sys
import time
from pathlib import Path
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Ensure local imports work cleanly
sys.path.append(str(Path(__file__).resolve().parent.parent))
from etl.data_quality import DataQualityValidator


def get_db_engine():
    """Constructs SQLAlchemy engine using credentials from .env."""
    load_dotenv()
    db_user = os.getenv("DB_USER", "root")
    db_pass = os.getenv("DB_PASSWORD", "password")
    db_host = os.getenv("DB_HOST", "127.0.0.1")
    db_port = os.getenv("DB_PORT", "3306")
    db_name = os.getenv("DB_NAME", "supply_chain_optima")

    connection_uri = f"mysql+pymysql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}?charset=utf8mb4"
    return create_engine(connection_uri, pool_pre_ping=True)


def run_pipeline(csv_path: str = None):
    """Executes the full ingestion, validation, and loading pipeline."""
    start_time = time.time()
    
    if csv_path is None:
        csv_path = Path(__file__).resolve().parent.parent / "data" / "raw" / "DataCoSupplyChainDataset.csv"

    print("=" * 70)
    print("      SUPPLYCHAINOPTIMA: ENTERPRISE ETL & INGESTION PIPELINE")
    print("=" * 70)
    print(f"Reading raw dataset from: {csv_path}")
    
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Source file not found at: {csv_path}")

    # 1. Ingest Raw CSV
    print("Loading CSV into memory (latin-1 encoding)...")
    df_raw = pd.read_csv(csv_path, encoding="latin-1", low_memory=False)
    print(f"Loaded {len(df_raw):,} raw transactional records.")

    # 2. Automated Data Quality Gate
    validator = DataQualityValidator()
    clean_df, quarantine_df = validator.validate_and_partition(df_raw)
    validator.print_quality_report()

    # 3. Connect to MySQL Database
    engine = get_db_engine()
    print("Connecting to MySQL warehouse...")
    with engine.connect() as conn:
        conn.execute(text("SELECT 1;"))
    print("Connected successfully.")

    # 4. Transform into Normalized Schemas
    print("\nTransforming records into 3NF normalized relational entities...")

    # A. products Table
    print("  -> Transforming `products` catalog...")
    products_df = (
        clean_df.groupby("Product Card Id", as_index=False)
        .agg({
            "Product Name": "first",
            "Category Name": "first",
            "Product Price": "mean"
        })
        .rename(columns={
            "Product Card Id": "product_card_id",
            "Product Name": "product_name",
            "Category Name": "category_name",
            "Product Price": "unit_price"
        })
    )
    products_df["unit_price"] = products_df["unit_price"].round(2)
    # Estimate annual holding cost (~20% unit price) and stockout penalty (~1.5x unit price)
    products_df["holding_cost_per_unit"] = (products_df["unit_price"] * 0.20).round(4)
    products_df["stockout_penalty_per_unit"] = (products_df["unit_price"] * 1.50).round(4)

    # B. orders Table
    print("  -> Transforming `orders` transactional line-items...")
    orders_df = pd.DataFrame({
        "order_item_id": clean_df["Order Item Id"].astype(int),
        "order_id": clean_df["Order Id"].astype(int),
        "order_date": pd.to_datetime(clean_df["order date (DateOrders)"], errors="coerce"),
        "product_card_id": clean_df["Product Card Id"].astype(int),
        "order_quantity": clean_df["Order Item Quantity"].astype(int),
        "sales_amount": clean_df["Sales"].astype(float).round(2),
        "order_region": clean_df["Order Region"].astype(str),
        "order_status": clean_df["Order Status"].astype(str)
    })

    # C. shipping_logs Table (Deduplicated per Order)
    print("  -> Transforming `shipping_logs` fulfillment records...")
    shipping_df = (
        clean_df[[
            "Order Id",
            "shipping date (DateOrders)",
            "Days for shipping (real)",
            "Days for shipment (scheduled)",
            "Shipping Mode",
            "Late_delivery_risk"
        ]]
        .drop_duplicates(subset=["Order Id"])
        .rename(columns={
            "Order Id": "order_id",
            "shipping date (DateOrders)": "shipping_date",
            "Days for shipping (real)": "days_for_shipping_real",
            "Days for shipment (scheduled)": "days_for_shipment_scheduled",
            "Shipping Mode": "shipping_mode",
            "Late_delivery_risk": "late_delivery_risk"
        })
    )
    shipping_df["shipping_date"] = pd.to_datetime(shipping_df["shipping_date"], errors="coerce")
    shipping_df["days_for_shipping_real"] = shipping_df["days_for_shipping_real"].astype(int)
    shipping_df["days_for_shipment_scheduled"] = shipping_df["days_for_shipment_scheduled"].astype(int)
    shipping_df["late_delivery_risk"] = shipping_df["late_delivery_risk"].astype(int)

    # 5. High-Performance Bulk Loading
    print("\nExecuting bulk load to MySQL warehouse...")
    with engine.begin() as conn:
        # Disable foreign key checks during clean truncate/reload
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
        conn.execute(text("TRUNCATE TABLE orders;"))
        conn.execute(text("TRUNCATE TABLE shipping_logs;"))
        conn.execute(text("TRUNCATE TABLE products;"))
        conn.execute(text("TRUNCATE TABLE audit_quarantine;"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))

    print(f"Loading {len(products_df):,} products...")
    products_df.to_sql("products", engine, if_exists="append", index=False, chunksize=1000)

    print(f"Loading {len(orders_df):,} orders line-items...")
    orders_df.to_sql("orders", engine, if_exists="append", index=False, chunksize=5000)

    print(f"Loading {len(shipping_df):,} shipping logs...")
    shipping_df.to_sql("shipping_logs", engine, if_exists="append", index=False, chunksize=5000)

    if not quarantine_df.empty:
        print(f"Loading {len(quarantine_df):,} audit quarantine records...")
        quarantine_df.to_sql("audit_quarantine", engine, if_exists="append", index=False, chunksize=1000)

    # 6. Database Row Count Verification
    print("\nVerifying database row counts:")
    with engine.connect() as conn:
        for tbl in ["products", "orders", "shipping_logs", "audit_quarantine"]:
            cnt = conn.execute(text(f"SELECT COUNT(*) FROM {tbl};")).scalar()
            print(f"  - {tbl:<18} : {cnt:,} rows")

    duration = time.time() - start_time
    print("=" * 70)
    print(f"ETL INGESTION & DATA QUALITY PIPELINE COMPLETED IN {duration:.2f}s")
    print("=" * 70)


if __name__ == "__main__":
    run_pipeline()
