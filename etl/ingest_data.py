"""
SupplyChainOptima - Ingestion Entrypoint
Author: Priyanshu
Description: Standard entrypoint for Module 1 Data Ingestion.
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from etl.ingest_and_validate import run_pipeline

if __name__ == "__main__":
    run_pipeline()
