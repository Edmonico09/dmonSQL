
# ============================================================================
# dmonSQL/query/planner.py
# ============================================================================
"""Planificateur d'exécution de requêtes"""

from typing import List, Dict


class QueryPlan:
    """Plan d'exécution d'une requête"""
    
    def __init__(self, operations: List[Dict], estimated_cost: float, estimated_rows: int):
        self.operations = operations
        self.estimated_cost = estimated_cost
        self.estimated_rows = estimated_rows
    
    def __repr__(self):
        return f"QueryPlan(cost={self.estimated_cost:.2f}, rows={self.estimated_rows})"


class QueryPlanner:
    """Génère des plans d'exécution"""
    
    def __init__(self):
        self.plans = []
    
    def create_plan(self, parsed_query: Dict) -> QueryPlan:
        """Crée un plan d'exécution"""
        operations = []
        estimated_cost = 0
        estimated_rows = 1000  # Estimation par défaut
        
        query_type = parsed_query.get('type', '').upper()
        
        if query_type == 'SELECT':
            # Ajouter opération de scan
            operations.append({'type': 'SCAN', 'table': parsed_query['table']})
            estimated_cost += 100
            
            # Ajouter filtre si WHERE
            if parsed_query.get('where'):
                operations.append({'type': 'FILTER', 'condition': parsed_query['where']})
                estimated_cost += 50
                estimated_rows = estimated_rows // 2
            
            # Ajouter projection
            if parsed_query['columns'] != '*':
                operations.append({'type': 'PROJECT', 'columns': parsed_query['columns']})
                estimated_cost += 10
        
        return QueryPlan(operations, estimated_cost, estimated_rows)
    
    def explain(self, plan: QueryPlan) -> str:
        """Génère un EXPLAIN pour le plan"""
        output = [f"Query Plan (cost={plan.estimated_cost:.2f}, rows={plan.estimated_rows})"]
        output.append("-" * 60)
        
        for i, op in enumerate(plan.operations, 1):
            op_type = op['type']
            details = ", ".join(f"{k}={v}" for k, v in op.items() if k != 'type')
            output.append(f"  {i}. {op_type} {details}")
        
        return "\n".join(output)
