"""
SupplyChainOptima - Data Quality & Governance Unit Tests
Author: Priyanshu
Description: Verifies quarantine gating, anomaly isolation, and schema integrity.
"""

import pandas as pd
from etl.data_quality import DataQualityValidator


def test_data_quality_quarantine_negative_shipping():
    """Tests that negative actual shipping days are successfully quarantined."""
    validator = DataQualityValidator()
    
    mock_df = pd.DataFrame([
        {
            "Order Id": 101,
            "Order Item Id": 1001,
            "Product Card Id": 50,
            "Product Name": "Test Widget",
            "Category Name": "Hardware",
            "Product Price": 100.0,
            "Order Item Quantity": 2,
            "Sales": 200.0,
            "order date (DateOrders)": "2024-01-01 10:00",
            "shipping date (DateOrders)": "2024-01-03 10:00",
            "Days for shipping (real)": -3,  # ANOMALOUS NEGATIVE
            "Days for shipment (scheduled)": 4,
            "Shipping Mode": "Standard Class",
            "Late_delivery_risk": 0
        },
        {
            "Order Id": 102,
            "Order Item Id": 1002,
            "Product Card Id": 50,
            "Product Name": "Test Widget",
            "Category Name": "Hardware",
            "Product Price": 100.0,
            "Order Item Quantity": 1,
            "Sales": 100.0,
            "order date (DateOrders)": "2024-01-01 10:00",
            "shipping date (DateOrders)": "2024-01-04 10:00",
            "Days for shipping (real)": 3,   # VALID
            "Days for shipment (scheduled)": 4,
            "Shipping Mode": "Standard Class",
            "Late_delivery_risk": 0
        }
    ])

    clean_df, quarantine_df = validator.validate_and_partition(mock_df)

    assert len(clean_df) == 1, "Only clean record should pass"
    assert clean_df.iloc[0]["Order Item Id"] == 1002
    assert len(quarantine_df) == 1, "Anomalous record should be quarantined"
    assert quarantine_df.iloc[0]["issue_type"] == "NEGATIVE_LEAD_TIME"
    assert quarantine_df.iloc[0]["order_item_id"] == 1001


def test_data_quality_quarantine_null_product():
    """Tests that missing or zero Product IDs are quarantined."""
    validator = DataQualityValidator()
    
    mock_df = pd.DataFrame([
        {
            "Order Id": 103,
            "Order Item Id": 1003,
            "Product Card Id": None,  # MISSING PRODUCT ID
            "Product Name": "Ghost SKU",
            "Category Name": "Hardware",
            "Product Price": 50.0,
            "Order Item Quantity": 1,
            "Sales": 50.0,
            "order date (DateOrders)": "2024-01-01 10:00",
            "shipping date (DateOrders)": "2024-01-04 10:00",
            "Days for shipping (real)": 3,
            "Days for shipment (scheduled)": 4,
            "Shipping Mode": "Standard Class",
            "Late_delivery_risk": 0
        }
    ])

    clean_df, quarantine_df = validator.validate_and_partition(mock_df)
    assert len(clean_df) == 0
    assert len(quarantine_df) == 1
    assert quarantine_df.iloc[0]["issue_type"] == "NULL_OR_INVALID_PRODUCT_ID"
