"""
SupplyChainOptima - Data Quality & Automated Integrity Engine
Author: Priyanshu
Description: Implements automated validation rules, anomaly detection,
             and quarantine routing for supply chain transactions.
"""

from typing import Tuple, List, Dict, Any
import json
import pandas as pd
import numpy as np


class DataQualityValidator:
    """
    Automated data quality gatekeeper for retail/CPG transactional records.
    Validates physical feasibility (non-negative lead times, valid quantities),
    referential integrity, and business logic.
    """

    def __init__(self):
        self.validation_summary = {
            "total_records_evaluated": 0,
            "clean_records_passed": 0,
            "quarantined_records": 0,
            "issues_by_type": {}
        }

    def validate_and_partition(
        self, df: pd.DataFrame
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Validates the incoming raw dataframe. Returns a tuple of:
          - clean_df: Records passing all physical and business validation checks
          - quarantine_df: Anomalous records formatted for audit_quarantine insertion
        """
        self.validation_summary["total_records_evaluated"] = len(df)
        
        # Anomaly boolean masks
        # 1. Negative or physically impossible actual shipping days
        mask_negative_shipping = df["Days for shipping (real)"] < 0
        
        # 2. Null or invalid Product Card Id
        mask_null_product = df["Product Card Id"].isnull() | (df["Product Card Id"] <= 0)
        
        # 3. Invalid Order Quantity or Sales
        mask_invalid_qty = df["Order Item Quantity"].isnull() | (df["Order Item Quantity"] <= 0)
        mask_invalid_sales = df["Sales"].isnull() | (df["Sales"] < 0)
        
        # 4. Missing critical dates
        mask_missing_dates = (
            df["order date (DateOrders)"].isnull() | 
            df["shipping date (DateOrders)"].isnull()
        )
        
        # 5. Duplicate Order Item Id (line-item collision)
        mask_duplicate_item = df.duplicated(subset=["Order Item Id"], keep="first")
        
        # Combined anomaly mask
        is_quarantine = (
            mask_negative_shipping | 
            mask_null_product | 
            mask_invalid_qty | 
            mask_invalid_sales | 
            mask_missing_dates | 
            mask_duplicate_item
        )

        clean_df = df[~is_quarantine].copy()
        raw_quarantine_df = df[is_quarantine].copy()

        quarantine_records: List[Dict[str, Any]] = []

        for idx, row in raw_quarantine_df.iterrows():
            issues = []
            if row["Days for shipping (real)"] < 0:
                issues.append(("NEGATIVE_LEAD_TIME", f"Negative actual shipping days: {row['Days for shipping (real)']}"))
            if pd.isnull(row["Product Card Id"]) or row["Product Card Id"] <= 0:
                issues.append(("NULL_OR_INVALID_PRODUCT_ID", "Product Card Id is missing or non-positive"))
            if pd.isnull(row["Order Item Quantity"]) or row["Order Item Quantity"] <= 0:
                issues.append(("INVALID_QUANTITY", f"Non-positive order quantity: {row['Order Item Quantity']}"))
            if pd.isnull(row["Sales"]) or row["Sales"] < 0:
                issues.append(("INVALID_SALES_AMOUNT", f"Negative sales amount: {row['Sales']}"))
            if pd.isnull(row["order date (DateOrders)"]) or pd.isnull(row["shipping date (DateOrders)"]):
                issues.append(("MISSING_TRANSACTION_TIMESTAMP", "Order or shipping timestamp is null"))
            if idx in df[mask_duplicate_item].index:
                issues.append(("DUPLICATE_ORDER_ITEM_ID", f"Duplicate Order Item Id: {row['Order Item Id']}"))

            for issue_type, issue_desc in issues:
                self.validation_summary["issues_by_type"][issue_type] = (
                    self.validation_summary["issues_by_type"].get(issue_type, 0) + 1
                )
                quarantine_records.append({
                    "order_id": int(row["Order Id"]) if pd.notnull(row["Order Id"]) else None,
                    "order_item_id": int(row["Order Item Id"]) if pd.notnull(row["Order Item Id"]) else None,
                    "product_card_id": int(row["Product Card Id"]) if pd.notnull(row["Product Card Id"]) else None,
                    "issue_type": issue_type,
                    "issue_description": issue_desc,
                    "raw_payload": json.dumps({
                        "order_id": row.get("Order Id"),
                        "product_card_id": row.get("Product Card Id"),
                        "sales": row.get("Sales"),
                        "days_shipping": row.get("Days for shipping (real)")
                    })
                })

        quarantine_df = pd.DataFrame(quarantine_records)
        
        self.validation_summary["clean_records_passed"] = len(clean_df)
        self.validation_summary["quarantined_records"] = len(quarantine_records)

        return clean_df, quarantine_df

    def print_quality_report(self) -> None:
        """Prints executive data quality metrics."""
        print("=" * 70)
        print("          DATA QUALITY AUDIT & GOVERNANCE REPORT")
        print("=" * 70)
        print(f"Total Transactions Evaluated : {self.validation_summary['total_records_evaluated']:,}")
        print(f"Clean Records Validated      : {self.validation_summary['clean_records_passed']:,} ({(self.validation_summary['clean_records_passed']/max(1, self.validation_summary['total_records_evaluated']))*100:.2f}%)")
        print(f"Quarantined Anomalies Logged : {self.validation_summary['quarantined_records']:,}")
        if self.validation_summary["issues_by_type"]:
            print("\nBreakdown of Quarantined Anomalies:")
            for issue, count in self.validation_summary["issues_by_type"].items():
                print(f"  - [{issue}]: {count:,} violations")
        else:
            print("  - No data anomalies detected in baseline ingestion.")
        print("=" * 70)
