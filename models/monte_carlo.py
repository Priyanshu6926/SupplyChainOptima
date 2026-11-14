"""
SupplyChainOptima - Stochastic Monte Carlo Simulation Engine
Author: Priyanshu
Description: Vectorized 10,000-iteration Monte Carlo simulation of lead-time demand
             across top SKUs and disruption scenarios.
"""

from typing import Dict, List, Tuple, Any
import numpy as np
import pandas as pd


class MonteCarloEngine:
    """
    Stochastic simulation engine for supply chain inventory uncertainty.
    Simulates joint distributions of daily customer demand and supplier transit lead time.
    """

    def __init__(self, iterations: int = 10000, seed: int = 42):
        self.iterations = iterations
        self.seed = seed
        self.rng = np.random.default_rng(seed)

    def simulate_lead_time_demand(
        self,
        mu_d: float,
        sigma_d: float,
        mu_l: float,
        sigma_l: float,
        lead_time_dist: str = "lognormal"
    ) -> np.ndarray:
        """
        Generates 10,000 empirical realizations of total lead-time demand (D_L).
        D_L = sum_{t=1}^L d_t where L ~ LeadTimeDist and d_t ~ max(0, N(mu_d, sigma_d^2))
        """
        # Ensure positive physical parameters
        mu_d = max(0.01, float(mu_d))
        sigma_d = max(0.01, float(sigma_d))
        mu_l = max(1.0, float(mu_l))
        sigma_l = max(0.01, float(sigma_l))

        # Sample Lead Times (L_samples)
        if lead_time_dist == "lognormal":
            # Parametrize lognormal from mean and standard deviation
            var_l = sigma_l ** 2
            mu_log = np.log((mu_l ** 2) / np.sqrt(var_l + mu_l ** 2))
            sigma_log = np.sqrt(np.log(var_l / (mu_l ** 2) + 1.0))
            l_samples = self.rng.lognormal(mean=mu_log, sigma=sigma_log, size=self.iterations)
        else:
            # Truncated normal lead times (min 1 day)
            l_samples = self.rng.normal(loc=mu_l, scale=sigma_l, size=self.iterations)

        # Enforce discrete non-zero shipping days (min 1 day)
        l_days = np.clip(np.round(l_samples), 1, 60).astype(int)

        # Vectorized simulation of Lead-Time Demand (D_L)
        # Using conditional compound normal approximation:
        # D_L | L ~ Normal(L * mu_d, L * sigma_d^2)
        cond_mean = l_days * mu_d
        cond_std = np.sqrt(l_days) * sigma_d
        standard_normals = self.rng.standard_normal(size=self.iterations)
        d_l_samples = cond_mean + cond_std * standard_normals

        # Demand cannot be negative
        d_l_samples = np.maximum(0.0, d_l_samples)
        return d_l_samples

    def evaluate_policy_risk(
        self,
        lead_time_demands: np.ndarray,
        reorder_point: float,
        holding_cost_unit: float,
        stockout_penalty_unit: float
    ) -> Dict[str, float]:
        """
        Evaluates stockout probability, expected unmet units, and total simulated costs.
        """
        # Stockout occurs whenever demand during lead time exceeds reorder point
        is_stockout = lead_time_demands > reorder_point
        stockout_prob = float(np.mean(is_stockout))

        unmet_demand = np.maximum(0.0, lead_time_demands - reorder_point)
        expected_unmet = float(np.mean(unmet_demand))

        ending_inventory = np.maximum(0.0, reorder_point - lead_time_demands)
        expected_inventory = float(np.mean(ending_inventory))

        expected_holding_cost = expected_inventory * holding_cost_unit
        expected_penalty_cost = expected_unmet * stockout_penalty_unit
        total_cost = expected_holding_cost + expected_penalty_cost

        fill_rate = 1.0 - (expected_unmet / max(0.01, float(np.mean(lead_time_demands))))
        fill_rate = float(np.clip(fill_rate, 0.0, 1.0))

        return {
            "reorder_point": float(reorder_point),
            "stockout_probability": round(stockout_prob, 4),
            "service_level": round(1.0 - stockout_prob, 4),
            "fill_rate": round(fill_rate, 4),
            "expected_ending_inventory": round(expected_inventory, 2),
            "expected_unmet_demand": round(expected_unmet, 2),
            "holding_cost": round(expected_holding_cost, 2),
            "penalty_cost": round(expected_penalty_cost, 2),
            "total_cost": round(total_cost, 2)
        }


def run_sku_simulation(
    sku_row: pd.Series,
    scenario_multiplier_lead: float = 1.0,
    scenario_multiplier_demand: float = 1.0,
    iterations: int = 10000,
    seed: int = 42
) -> Tuple[np.ndarray, float, float]:
    """
    Convenience wrapper to run Monte Carlo for a single SKU under a specific scenario.
    Returns: (lead_time_demands, static_rop, dynamic_safety_stock)
    """
    engine = MonteCarloEngine(iterations=iterations, seed=seed)
    
    mu_d = float(sku_row["mean_daily_demand"]) * scenario_multiplier_demand
    sigma_d = float(sku_row["std_daily_demand"]) * np.sqrt(scenario_multiplier_demand)
    mu_l = float(sku_row["mean_lead_time"]) * scenario_multiplier_lead
    sigma_l = float(sku_row["std_lead_time"]) * np.sqrt(scenario_multiplier_lead)

    ltd_samples = engine.simulate_lead_time_demand(mu_d, sigma_d, mu_l, sigma_l)
    
    # Static Policy: Traditional naive rule (no safety stock buffer)
    static_rop = mu_d * mu_l

    # Traditional Dynamic Safety Stock: z * sigma_LTD at 95% service level (z = 1.645)
    sigma_ltd = np.sqrt(mu_l * (sigma_d ** 2) + (mu_d ** 2) * (sigma_l ** 2))
    safety_stock_heuristic = 1.645 * sigma_ltd

    return ltd_samples, static_rop, safety_stock_heuristic
