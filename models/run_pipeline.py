"""
SupplyChainOptima - Execution Pipeline Entrypoint
Author: Priyanshu
Description: Standard runner for Monte Carlo and LP Optimization engine.
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from models.scenario_runner import run_scenario_pipeline

if __name__ == "__main__":
    run_scenario_pipeline()
