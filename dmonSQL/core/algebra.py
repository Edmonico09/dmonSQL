from dmonSQL.core.table import Table 
from typing import List, Dict, Any, Tuple
try:
    from dmonSQL.transaction.transaction_manager import TransactionManager
    TRANSACTIONS_AVAILABLE = True
except ImportError:
    TRANSACTIONS_AVAILABLE = False

try:
    from dmonSQL.procedures.procedure import ProcedureManager
    PROCEDURES_AVAILABLE = True
except ImportError:
    PROCEDURES_AVAILABLE = False

try:
    from dmonSQL.procedures.trigger import TriggerManager
    TRIGGERS_AVAILABLE = True
except ImportError:
    TRIGGERS_AVAILABLE = False

try:
    from dmonSQL.query.optimizer import QueryOptimizer
    OPTIMIZER_AVAILABLE = True
except ImportError:
    OPTIMIZER_AVAILABLE = False


class RelationalAlgebra:
    """Opérations d'algèbre relationnelle"""
    
    @staticmethod
    def projection(table: Table, columns: List[str]) -> List[Dict]:
        """Projection (SELECT colonnes)"""
        return table.select(columns=columns)
    
    @staticmethod
    def selection(table: Table, condition: callable) -> List[Dict]:
        """Sélection (WHERE)"""
        return table.select(where=condition)
    
    @staticmethod
    def cross_product(table1: Table, table2: Table) -> List[Dict]:
        """Produit cartésien"""
        result = []
        for row1 in table1.rows:
            for row2 in table2.rows:
                combined = {}
                for k, v in row1.items():
                    combined[f"{table1.name}.{k}"] = v
                for k, v in row2.items():
                    combined[f"{table2.name}.{k}"] = v
                result.append(combined)
        return result
    
    @staticmethod
    def join(table1: Table, table2: Table, on: Tuple[str, str]) -> List[Dict]:
        """Jointure naturelle"""
        col1, col2 = on
        result = []
        
        for row1 in table1.rows:
            for row2 in table2.rows:
                if row1.get(col1) == row2.get(col2):
                    combined = {}
                    for k, v in row1.items():
                        combined[k] = v
                    for k, v in row2.items():
                        if k not in combined:
                            combined[k] = v
                    result.append(combined)
        
        return result
    
    @staticmethod
    def union(rows1: List[Dict], rows2: List[Dict]) -> List[Dict]:
        """Union"""
        result = list(rows1)
        for row in rows2:
            if row not in result:
                result.append(row)
        return result
    
    @staticmethod
    def difference(rows1: List[Dict], rows2: List[Dict]) -> List[Dict]:
        """Différence"""
        return [row for row in rows1 if row not in rows2]
    
    @staticmethod
    def division(dividend_table: Table, divisor_table: Table, 
                 common_attrs: List[str], dividend_attrs: List[str]) -> List[Dict]:
        """Division relationnelle"""
        divisor_tuples = []
        for row in divisor_table.rows:
            divisor_tuple = tuple(row[attr] for attr in common_attrs)
            divisor_tuples.append(divisor_tuple)
        
        if not divisor_tuples:
            return []
        
        groups = {}
        for row in dividend_table.rows:
            key = tuple(row[attr] for attr in dividend_attrs)
            if key not in groups:
                groups[key] = []
            value = tuple(row[attr] for attr in common_attrs)
            if value not in groups[key]:
                groups[key].append(value)
        
        result = []
        for key, values in groups.items():
            if all(divisor_tuple in values for divisor_tuple in divisor_tuples):
                result_dict = {dividend_attrs[i]: key[i] for i in range(len(dividend_attrs))}
                result.append(result_dict)
        
        return result
