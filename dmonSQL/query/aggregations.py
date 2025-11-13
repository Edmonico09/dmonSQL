"""
dmonSQL/query/aggregations.py
Support pour GROUP BY et fonctions d'agrégation
"""

from typing import List, Dict, Any, Callable
from collections import defaultdict
import statistics
import re

class AggregationFunction:
    """Classe de base pour les fonctions d'agrégation"""
    
    def __init__(self, column: str = None, distinct: bool = False):
        self.column = column
        self.distinct = distinct
        self.name = self.__class__.__name__.upper()
    
    def compute(self, values: List[Any]) -> Any:
        """Calcule l'agrégation sur une liste de valeurs"""
        raise NotImplementedError
    
    def __repr__(self):
        distinct_str = "DISTINCT " if self.distinct else ""
        col_str = self.column if self.column else "*"
        return f"{self.name}({distinct_str}{col_str})"


class CountFunction(AggregationFunction):
    """COUNT(*) ou COUNT(column) ou COUNT(DISTINCT column)"""
    
    def compute(self, values: List[Any]) -> int:
        if self.column is None:  # COUNT(*)
            return len(values)
        
        # Filtrer les NULL
        non_null_values = [v for v in values if v is not None]
        
        if self.distinct:
            return len(set(non_null_values))
        
        return len(non_null_values)


class SumFunction(AggregationFunction):
    """SUM(column)"""
    
    def compute(self, values: List[Any]) -> float:
        non_null_values = [v for v in values if v is not None]
        if not non_null_values:
            return None
        
        try:
            return sum(float(v) for v in non_null_values)
        except (ValueError, TypeError):
            return None


class AvgFunction(AggregationFunction):
    """AVG(column)"""
    
    def compute(self, values: List[Any]) -> float:
        non_null_values = [v for v in values if v is not None]
        if not non_null_values:
            return None
        
        try:
            numeric_values = [float(v) for v in non_null_values]
            return statistics.mean(numeric_values)
        except (ValueError, TypeError):
            return None


class MinFunction(AggregationFunction):
    """MIN(column)"""
    
    def compute(self, values: List[Any]) -> Any:
        non_null_values = [v for v in values if v is not None]
        if not non_null_values:
            return None
        
        return min(non_null_values)


class MaxFunction(AggregationFunction):
    """MAX(column)"""
    
    def compute(self, values: List[Any]) -> Any:
        non_null_values = [v for v in values if v is not None]
        if not non_null_values:
            return None
        
        return max(non_null_values)


class StdDevFunction(AggregationFunction):
    """STDDEV(column) - Écart-type"""
    
    def compute(self, values: List[Any]) -> float:
        non_null_values = [v for v in values if v is not None]
        if len(non_null_values) < 2:
            return None
        
        try:
            numeric_values = [float(v) for v in non_null_values]
            return statistics.stdev(numeric_values)
        except (ValueError, TypeError):
            return None


class AggregationEngine:
    """Moteur d'exécution des agrégations avec GROUP BY"""
    
    # Mapping des noms de fonctions vers les classes
    FUNCTION_MAP = {
        'COUNT': CountFunction,
        'SUM': SumFunction,
        'AVG': AvgFunction,
        'MIN': MinFunction,
        'MAX': MaxFunction,
        'STDDEV': StdDevFunction,
        'STD': StdDevFunction,
    }
    
    def __init__(self):
        self.aggregations = []
        self.group_by_columns = []
        self.select_columns = []
        self.aliases = {}
    

    def parse_aggregation(self, expr: str):
        """
        Parse une expression d'agrégation - Version améliorée
        Exemples: COUNT(*), SUM(o.total_amount), AVG(DISTINCT u.age)
        """
        import re
        
        # Pattern amélioré pour gérer les préfixes de table
        # COUNT(*), SUM(o.price), AVG(DISTINCT table.column)
        pattern = r'(\w+)\s*\(\s*(DISTINCT\s+)?(\*|[\w.]+)\s*\)'
        match = re.match(pattern, expr.strip(), re.IGNORECASE)
        
        if not match:
            return None
        
        func_name = match.group(1).upper()
        distinct = match.group(2) is not None
        column = match.group(3)
        
        if column == '*':
            column = None
        
        if func_name not in self.FUNCTION_MAP:
            raise ValueError(f"Unknown aggregation function: {func_name}")
        
        func_class = self.FUNCTION_MAP[func_name]
        return func_class(column=column, distinct=distinct)
    
    def is_aggregation(self, expr: str) -> bool:
        """Vérifie si une expression est une agrégation"""
        import re
        pattern = r'\w+\s*\([^)]*\)'
        return bool(re.match(pattern, expr.strip(), re.IGNORECASE))
    
    def execute_group_by(self, rows: List[Dict], 
                        select_exprs: List[str],
                        group_by_cols: List[str]) -> List[Dict]:
        """
        Exécute une requête avec GROUP BY et agrégations
        VERSION CORRIGÉE pour gérer les préfixes de table dans les JOINs
        """
        if not rows:
            return []
        
        # 1. Parser les expressions SELECT
        aggregations = {}  # {alias: AggregationFunction}
        regular_columns = []  # [(colonne_réelle, alias)]
        
        for expr in select_exprs:
            # Gérer les alias (col AS alias)
            if ' AS ' in expr.upper():
                parts = re.split(r'\s+AS\s+', expr, 1, re.IGNORECASE)
                expr_clean = parts[0].strip()
                alias = parts[1].strip()
            else:
                expr_clean = expr.strip()
                alias = expr_clean
            
            if self.is_aggregation(expr_clean):
                agg_func = self.parse_aggregation(expr_clean)
                if agg_func:
                    aggregations[alias] = agg_func
            else:
                # Garder le nom de colonne avec préfixe (u.id, o.total_amount, etc.)
                regular_columns.append((expr_clean, alias))
        
        # 2. Vérifier que les colonnes non-agrégées sont dans GROUP BY
        for col, alias in regular_columns:
            if col not in group_by_cols:
                raise ValueError(
                    f"Column '{col}' must appear in GROUP BY or be in an aggregate function"
                )
        
        # 3. Grouper les lignes (utiliser les colonnes avec préfixes)
        from collections import defaultdict
        groups = defaultdict(list)
        
        for row in rows:
            # Créer la clé de groupe avec les vraies colonnes
            group_key = tuple(row.get(col) for col in group_by_cols)
            groups[group_key].append(row)
        
        # 4. Calculer les agrégations pour chaque groupe
        result = []
        
        for group_key, group_rows in groups.items():
            result_row = {}
            
            # Ajouter les colonnes GROUP BY avec leurs alias
            for i, col in enumerate(group_by_cols):
                # Trouver l'alias correspondant
                alias = col
                for reg_col, reg_alias in regular_columns:
                    if reg_col == col:
                        alias = reg_alias
                        break
                result_row[alias] = group_key[i]
            
            # Calculer les agrégations
            for alias, agg_func in aggregations.items():
                if agg_func.column:
                    # Extraire les valeurs avec le nom de colonne complet (préfixe inclus)
                    values = [row.get(agg_func.column) for row in group_rows]
                else:
                    # COUNT(*) - toutes les lignes
                    values = group_rows
                
                result_row[alias] = agg_func.compute(values)
            
            result.append(result_row)
        
        return result
    
    def execute_simple_aggregation(self, rows: List[Dict], 
                                   select_exprs: List[str]) -> List[Dict]:
        """
        Exécute des agrégations sans GROUP BY
        Exemple: SELECT COUNT(*), AVG(age) FROM users
        """
        if not rows:
            # Retourner une ligne avec des valeurs NULL ou 0
            result_row = {}
            for expr in select_exprs:
                parts = expr.split(' AS ', 1)
                alias = parts[1].strip() if len(parts) == 2 else expr.strip()
                
                if 'COUNT' in expr.upper():
                    result_row[alias] = 0
                else:
                    result_row[alias] = None
            
            return [result_row]
        
        # Traiter comme un seul groupe
        result_row = {}
        
        for expr in select_exprs:
            parts = expr.split(' AS ', 1)
            expr_clean = parts[0].strip()
            alias = parts[1].strip() if len(parts) == 2 else expr_clean
            
            if self.is_aggregation(expr_clean):
                agg_func = self.parse_aggregation(expr_clean)
                
                if agg_func.column:
                    values = [row.get(agg_func.column) for row in rows]
                else:
                    values = rows
                
                result_row[alias] = agg_func.compute(values)
            else:
                raise ValueError(
                    f"Column '{expr_clean}' must be in an aggregate function or GROUP BY"
                )
        
        return [result_row]

    def execute_group_by_fixed(self, rows: List[Dict], 
                    select_exprs: List[str],
                    group_by_cols: List[str]) -> List[Dict]:
        """Version corrigée avec meilleure gestion des alias"""
        
        if not rows:
            return []
        
        # 1. Parser les expressions SELECT
        aggregations = {}
        regular_columns = []
        
        for expr in select_exprs:
            # Gérer les alias (col AS alias)
            if ' AS ' in expr.upper():
                parts = re.split(r'\s+AS\s+', expr, 1, re.IGNORECASE)
                expr_clean = parts[0].strip()
                alias = parts[1].strip()
            else:
                expr_clean = expr.strip()
                alias = expr_clean
            
            if self.is_aggregation(expr_clean):
                agg_func = self.parse_aggregation(expr_clean)
                if agg_func:
                    aggregations[alias] = agg_func
            else:
                # Extraire le vrai nom de colonne (enlever préfixe table)
                if '.' in expr_clean:
                    real_col = expr_clean.split('.')[-1]
                else:
                    real_col = expr_clean
                regular_columns.append((real_col, alias))
        
        # 2. Normaliser les colonnes GROUP BY (enlever préfixes)
        normalized_group_cols = []
        for col in group_by_cols:
            if '.' in col:
                normalized_group_cols.append(col.split('.')[-1])
            else:
                normalized_group_cols.append(col)
        
        # 3. Vérifier que les colonnes non-agrégées sont dans GROUP BY
        for col, alias in regular_columns:
            # Vérifier avec ou sans préfixe
            col_without_prefix = col.split('.')[-1] if '.' in col else col
            if col not in normalized_group_cols and col_without_prefix not in normalized_group_cols:
                raise ValueError(
                    f"Column '{col}' must appear in GROUP BY or be in an aggregate function"
                )
        
        # 4. Grouper les lignes (utiliser les colonnes normalisées)
        groups = defaultdict(list)
        
        for row in rows:
            # Créer la clé de groupe avec les colonnes normalisées
            group_key = tuple(row.get(col) for col in normalized_group_cols)
            groups[group_key].append(row)
        
        # 5. Calculer les agrégations
        result = []
        
        for group_key, group_rows in groups.items():
            result_row = {}
            
            # Ajouter les colonnes GROUP BY avec leurs alias
            for i, col in enumerate(normalized_group_cols):
                # Trouver l'alias correspondant
                alias = col
                for reg_col, reg_alias in regular_columns:
                    if reg_col.split('.')[-1] == col:
                        alias = reg_alias
                        break
                result_row[alias] = group_key[i]
            
            # Calculer les agrégations
            for alias, agg_func in aggregations.items():
                if agg_func.column:
                    # Gérer les préfixes de table
                    col_name = agg_func.column.split('.')[-1] if '.' in agg_func.column else agg_func.column
                    values = [row.get(col_name, row.get(agg_func.column)) for row in group_rows]
                else:
                    values = group_rows
                
                result_row[alias] = agg_func.compute(values)
            
            result.append(result_row)
        
        return result


# Exemples d'utilisation
if __name__ == "__main__":
    # Données de test
    employees = [
        {'id': 1, 'name': 'Alice', 'department': 'IT', 'salary': 5000},
        {'id': 2, 'name': 'Bob', 'department': 'IT', 'salary': 6000},
        {'id': 3, 'name': 'Charlie', 'department': 'HR', 'salary': 4500},
        {'id': 4, 'name': 'David', 'department': 'HR', 'salary': 4800},
        {'id': 5, 'name': 'Eve', 'department': 'IT', 'salary': 5500},
    ]
    
    engine = AggregationEngine()
    
    # Test 1: GROUP BY avec COUNT et AVG
    print("Test 1: SELECT department, COUNT(*), AVG(salary) FROM employees GROUP BY department")
    result = engine.execute_group_by(
        employees,
        select_exprs=['department', 'COUNT(*)', 'AVG(salary) AS avg_salary'],
        group_by_cols=['department']
    )
    for row in result:
        print(row)
    
    print("\n" + "="*60 + "\n")
    
    # Test 2: Agrégation simple sans GROUP BY
    print("Test 2: SELECT COUNT(*), AVG(salary), MAX(salary) FROM employees")
    result = engine.execute_simple_aggregation(
        employees,
        select_exprs=['COUNT(*) AS total', 'AVG(salary) AS avg_sal', 'MAX(salary) AS max_sal']
    )
    for row in result:
        print(row)
    
    print("\n" + "="*60 + "\n")
    
    # Test 3: COUNT(DISTINCT)
    print("Test 3: SELECT COUNT(DISTINCT department) FROM employees")
    result = engine.execute_simple_aggregation(
        employees,
        select_exprs=['COUNT(DISTINCT department) AS dept_count']
    )
    for row in result:
        print(row)