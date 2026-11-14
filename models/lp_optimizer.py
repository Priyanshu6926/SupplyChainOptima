"""
SupplyChainOptima - Linear Programming (LP) Inventory Policy Optimizer
Author: Priyanshu
Description: Formulates and solves Sample Average Approximation (SAA) Linear Programs
             via PuLP to find cost-optimal Reorder Points (ROP) and dynamic Safety Stock (SS)
             subject to target cycle service levels (e.g., >= 95%).
"""

from typing import Dict, Any, Tuple
import numpy as np
import pulp


class InventoryLPOptimizer:
    """
    Linear Programming solver for stochastic inventory optimization.
    Finds optimal Reorder Point (ROP*) minimizing expected Holding Cost + Stockout Penalty
    while enforcing target Cycle Service Level (CSL) constraints.
    """

    def __init__(
        self,
        target_service_level: float = 0.95,
        order_cost_k: float = 50.0
    ):
        self.target_csl = target_service_level
        self.order_cost_k = order_cost_k

    def optimize_reorder_policy(
        self,
        sku_id: int,
        lead_time_demands: np.ndarray,
        mean_lead_time_demand: float,
        annual_demand: float,
        holding_cost_unit: float,
        stockout_penalty_unit: float,
        n_discretization_points: int = 150
    ) -> Dict[str, Any]:
        """
        Solves the Linear Program for a single SKU.
        
        Decision Variables:
          - ROP: Continuous reorder point
          - U_i: Unmet demand for realization i (penalty cost driver)
          - I_i: Ending inventory for realization i (holding cost driver)

        Objective:
          Minimize: sum(h * I_i + p * U_i) / M
          Subject to:
            U_i >= D_i - ROP, U_i >= 0
            I_i >= ROP - D_i, I_i >= 0
            ROP >= Quantile_(target_csl)(D_L)
        """
        holding_cost_unit = max(0.01, float(holding_cost_unit))
        stockout_penalty_unit = max(0.01, float(stockout_penalty_unit))
        annual_demand = max(1.0, float(annual_demand))

        # Enforce minimum ROP from service level requirement
        min_rop_csl = float(np.quantile(lead_time_demands, self.target_csl))

        # Discretize empirical distribution across quantiles for fast LP solving
        quantiles = np.linspace(0.005, 0.995, n_discretization_points)
        sample_demands = np.quantile(lead_time_demands, quantiles)
        m = len(sample_demands)

        # Formulate PuLP Problem
        prob = pulp.LpProblem(f"SKU_Inventory_Opt_{sku_id}", pulp.LpMinimize)

        # Decision Variables
        rop_var = prob.add_variable(f"ROP_{sku_id}", lowBound=min_rop_csl, cat="Continuous")
        u_vars = [prob.add_variable(f"U_{sku_id}_{i}", lowBound=0.0, cat="Continuous") for i in range(m)]
        i_vars = [prob.add_variable(f"I_{sku_id}_{i}", lowBound=0.0, cat="Continuous") for i in range(m)]

        # Linear Constraints for Piecewise Linear Loss
        for i, d_val in enumerate(sample_demands):
            prob += u_vars[i] >= d_val - rop_var
            prob += i_vars[i] >= rop_var - d_val

        # Objective Function
        prob += (holding_cost_unit * pulp.lpSum(i_vars) + stockout_penalty_unit * pulp.lpSum(u_vars)) / m

        # Solve using HiGHS
        try:
            solver = pulp.HiGHS(msg=False)
            prob.solve(solver)
            optimized_rop = float(rop_var.value() if hasattr(rop_var, 'value') else pulp.value(rop_var))
        except Exception:
            # Fallback to analytical quantile optimization if solver binary fails
            critical_ratio = stockout_penalty_unit / (stockout_penalty_unit + holding_cost_unit)
            opt_quantile = max(self.target_csl, min(0.999, critical_ratio))
            optimized_rop = float(np.quantile(lead_time_demands, opt_quantile))

        # Guarantee non-negativity and service level lower bound
        optimized_rop = max(min_rop_csl, optimized_rop)
        
        # Recommended Safety Stock buffer = ROP* - E[D_L]
        recommended_safety_stock = max(0.0, optimized_rop - mean_lead_time_demand)

        # Economic Order Quantity (EOQ): Q* = sqrt(2 * D * K / h)
        eoq_q_star = np.sqrt((2.0 * annual_demand * self.order_cost_k) / holding_cost_unit)

        return {
            "optimized_rop": round(optimized_rop, 2),
            "recommended_safety_stock": round(recommended_safety_stock, 2),
            "eoq_quantity": round(float(eoq_q_star), 2)
        }
