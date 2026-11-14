"""
SupplyChainOptima - Mathematical & Model Unit Tests
Author: Priyanshu
Description: Verifies stochastic properties, non-negativity constraints,
             and optimization dominance (optimized stockout < static stockout).
"""

import pytest
import numpy as np
import pandas as pd
from models.monte_carlo import MonteCarloEngine, run_sku_simulation
from models.lp_optimizer import InventoryLPOptimizer


@pytest.fixture
def mock_sku_data():
    """Provides representative SKU parameters for unit testing."""
    return pd.Series({
        "product_card_id": 9999,
        "mean_daily_demand": 25.0,
        "std_daily_demand": 6.0,
        "mean_lead_time": 4.0,
        "std_lead_time": 1.5,
        "holding_cost_per_unit": 3.0,
        "stockout_penalty_per_unit": 20.0,
        "total_units_sold": 10000
    })


def test_monte_carlo_lead_time_demand_properties(mock_sku_data):
    """Verifies that lead-time demand samples obey non-negativity and central limit bounds."""
    engine = MonteCarloEngine(iterations=5000, seed=42)
    ltd = engine.simulate_lead_time_demand(
        mu_d=mock_sku_data["mean_daily_demand"],
        sigma_d=mock_sku_data["std_daily_demand"],
        mu_l=mock_sku_data["mean_lead_time"],
        sigma_l=mock_sku_data["std_lead_time"]
    )
    # Physical validity: Demand cannot be negative
    assert np.all(ltd >= 0.0), "Lead-time demand realizations must be non-negative"
    
    # Expected lead-time demand approx E[L]*E[D] = 4 * 25 = 100
    expected_ltd = mock_sku_data["mean_lead_time"] * mock_sku_data["mean_daily_demand"]
    simulated_mean = np.mean(ltd)
    assert abs(simulated_mean - expected_ltd) / expected_ltd < 0.08, (
        f"Simulated mean {simulated_mean} drifted significantly from expected {expected_ltd}"
    )


def test_lp_optimizer_dominance_over_static(mock_sku_data):
    """
    Verifies that the LP-optimized policy strictly reduces stockout probability
    compared to the naive static policy (ROP = mu_d * mu_l).
    """
    engine = MonteCarloEngine(iterations=5000, seed=42)
    optimizer = InventoryLPOptimizer(target_service_level=0.95)

    mu_d = mock_sku_data["mean_daily_demand"]
    mu_l = mock_sku_data["mean_lead_time"]
    mean_ltd = mu_d * mu_l
    h = mock_sku_data["holding_cost_per_unit"]
    p = mock_sku_data["stockout_penalty_per_unit"]

    ltd_samples = engine.simulate_lead_time_demand(
        mu_d=mu_d,
        sigma_d=mock_sku_data["std_daily_demand"],
        mu_l=mu_l,
        sigma_l=mock_sku_data["std_lead_time"]
    )

    static_rop = mean_ltd
    static_eval = engine.evaluate_policy_risk(ltd_samples, static_rop, h, p)

    opt_result = optimizer.optimize_reorder_policy(
        sku_id=mock_sku_data["product_card_id"],
        lead_time_demands=ltd_samples,
        mean_lead_time_demand=mean_ltd,
        annual_demand=mock_sku_data["total_units_sold"],
        holding_cost_unit=h,
        stockout_penalty_unit=p
    )

    opt_rop = opt_result["optimized_rop"]
    rec_ss = opt_result["recommended_safety_stock"]
    opt_eval = engine.evaluate_policy_risk(ltd_samples, opt_rop, h, p)

    # 1. Non-negativity constraints
    assert opt_rop >= 0.0, "Optimized ROP must be non-negative"
    assert rec_ss >= 0.0, "Recommended Safety Stock must be non-negative"
    assert opt_result["eoq_quantity"] > 0.0, "EOQ Quantity must be strictly positive"

    # 2. Strict dominance: Optimized stockout probability < Static stockout probability
    assert opt_eval["stockout_probability"] < static_eval["stockout_probability"], (
        f"Optimized stockout ({opt_eval['stockout_probability']}) must be strictly lower "
        f"than static stockout ({static_eval['stockout_probability']})"
    )

    # 3. Target service level attainment (>= 95% CSL, within sampling tolerance)
    assert opt_eval["service_level"] >= 0.94, (
        f"Expected service level >= 0.94, got {opt_eval['service_level']}"
    )


def test_scenario_perturbation_scaling(mock_sku_data):
    """Verifies that lead-time delay and demand surge scenarios scale ROP monotonically."""
    engine = MonteCarloEngine(iterations=2000, seed=42)
    optimizer = InventoryLPOptimizer(target_service_level=0.95)

    # Baseline
    ltd_base = engine.simulate_lead_time_demand(20.0, 5.0, 3.0, 1.0)
    opt_base = optimizer.optimize_reorder_policy(1, ltd_base, 60.0, 5000, 2.0, 10.0)

    # Delay Scenario (+25% Lead Time)
    ltd_delay = engine.simulate_lead_time_demand(20.0, 5.0, 3.0 * 1.25, 1.0 * np.sqrt(1.25))
    opt_delay = optimizer.optimize_reorder_policy(1, ltd_delay, 75.0, 5000, 2.0, 10.0)

    # Demand Surge (+40% Demand)
    ltd_surge = engine.simulate_lead_time_demand(20.0 * 1.4, 5.0 * np.sqrt(1.4), 3.0, 1.0)
    opt_surge = optimizer.optimize_reorder_policy(1, ltd_surge, 84.0, 5000 * 1.4, 2.0, 10.0)

    assert opt_delay["optimized_rop"] > opt_base["optimized_rop"], (
        "Supplier delay should strictly increase the required ROP"
    )
    assert opt_surge["optimized_rop"] > opt_base["optimized_rop"], (
        "Demand surge should strictly increase the required ROP"
    )
