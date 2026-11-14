"""
SupplyChainOptima - Ingestion Entrypoint
Author: Priyanshu
Description: Standard entrypoint for Module 1 Data Ingestion.
"""

from etl.ingest_and_validate import run_pipeline

if __name__ == "__main__":
    run_pipeline()
