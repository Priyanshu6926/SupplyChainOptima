"""
SupplyChainOptima - Execution Pipeline Entrypoint
Author: Priyanshu
Description: Standard runner for Monte Carlo and LP Optimization engine.
"""

from models.scenario_runner import run_scenario_pipeline

if __name__ == "__main__":
    run_scenario_pipeline()
