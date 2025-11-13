"""
Fonctions d'agrégation et GROUP BY pour dmonSQL
COUNT, SUM, AVG, MIN, MAX, GROUP BY, HAVING
"""

from typing import List, Dict, Any, Callable, Optional
from collections import defaultdict


class AggregationEngine:
    """Moteur d'agrégation SQL"""
    
    @staticmethod
    def count(rows: List[Dict], column: Optional[str] = None) -> int:
        """
        COUNT(*) ou COUNT(column)
        
        Exemples:
            SELECT COUNT(*) FROM users
            SELECT COUNT(email) FROM users
        """
        if column is None or column == '*':
            return len(rows)
        
        # COUNT(column) ignore les NULL
        return sum(1 for row in rows if row.get(column) is not None)
    
    @staticmethod
    def sum(rows: List[Dict], column: str) -> float:
        """
        SUM(column)
        
        Exemple:
            SELECT SUM(salary) FROM employees
        """
        total = 0
        for row in rows:
            value = row.get(column)
            if value is not None:
                try:
                    total += float(value)
                except (ValueError, TypeError):
                    pass
        return total
    
    @staticmethod
    def avg(rows: List[Dict], column: str) -> Optional[float]:
        """
        AVG(column)
        
        Exemple:
            SELECT AVG(salary) FROM employees
        """
        values = [row.get(column) for row in rows if row.get(column) is not None]
        if not values:
            return None
        
        try:
            numeric_values = [float(v) for v in values]
            return sum(numeric_values) / len(numeric_values)
        except (ValueError, TypeError):
            return None
    
    @staticmethod
    def min(rows: List[Dict], column: str) -> Any:
        """
        MIN(column)
        
        Exemple:
            SELECT MIN(salary) FROM employees
        """
        values = [row.get(column) for row in rows if row.get(column) is not None]
        return min(values) if values else None
    
    @staticmethod
    def max(rows: List[Dict], column: str) -> Any:
        """
        MAX(column)
        
        Exemple:
            SELECT MAX(salary) FROM employees
        """
        values = [row.get(column) for row in rows if row.get(column) is not None]
        return max(values) if values else None
    
    @staticmethod
    def group_by(rows: List[Dict], group_columns: List[str]) -> Dict[tuple, List[Dict]]:
        """
        GROUP BY columns
        
        Retourne un dictionnaire : clé_groupe -> lignes du groupe
        
        Exemple:
            SELECT department, COUNT(*) FROM employees GROUP BY department
        """
        groups = defaultdict(list)
        
        for row in rows:
            # Créer la clé du groupe
            key = tuple(row.get(col) for col in group_columns)
            groups[key].append(row)
        
        return dict(groups)
    
    @staticmethod
    def apply_aggregations(
        groups: Dict[tuple, List[Dict]], 
        group_columns: List[str],
        aggregations: List[Dict]
    ) -> List[Dict]:
        """
        Applique les fonctions d'agrégation sur chaque groupe
        
        Args:
            groups: Résultat de group_by()
            group_columns: Colonnes de regroupement
            aggregations: Liste de {'func': 'COUNT', 'column': '*', 'alias': 'total'}
        
        Returns:
            Liste de résultats agrégés
        """
        results = []
        
        for group_key, group_rows in groups.items():
            result_row = {}
            
            # Ajouter les colonnes de regroupement
            for i, col in enumerate(group_columns):
                result_row[col] = group_key[i]
            
            # Appliquer chaque agrégation
            for agg in aggregations:
                func_name = agg['func'].upper()
                column = agg.get('column')
                alias = agg.get('alias', f"{func_name}_{column}")
                
                if func_name == 'COUNT':
                    value = AggregationEngine.count(group_rows, column)
                elif func_name == 'SUM':
                    value = AggregationEngine.sum(group_rows, column)
                elif func_name == 'AVG':
                    value = AggregationEngine.avg(group_rows, column)
                elif func_name == 'MIN':
                    value = AggregationEngine.min(group_rows, column)
                elif func_name == 'MAX':
                    value = AggregationEngine.max(group_rows, column)
                else:
                    value = None
                
                result_row[alias] = value
            
            results.append(result_row)
        
        return results
    
    @staticmethod
    def having(rows: List[Dict], condition: Callable[[Dict], bool]) -> List[Dict]:
        """
        HAVING clause (filtre APRÈS GROUP BY)
        
        Exemple:
            SELECT department, AVG(salary) 
            FROM employees 
            GROUP BY department 
            HAVING AVG(salary) > 50000
        """
        return [row for row in rows if condition(row)]


# ============================================================================
# PARSER POUR SELECT AVEC AGRÉGATION
# ============================================================================

import re

class AggregationParser:
    """Parse les requêtes SELECT avec agrégation"""
    
    @staticmethod
    def parse_select_with_aggregation(sql: str) -> Dict:
        """
        Parse SELECT avec GROUP BY et fonctions d'agrégation
        
        Exemple:
            SELECT department, COUNT(*), AVG(salary)
            FROM employees
            WHERE active = 1
            GROUP BY department
            HAVING COUNT(*) > 5
        """
        result = {
            'columns': [],
            'aggregations': [],
            'table': None,
            'where': None,
            'group_by': [],
            'having': None
        }
        
        # Extraire les différentes parties
        pattern = r'SELECT\s+(.*?)\s+FROM\s+(\w+)(?:\s+WHERE\s+(.*?))?(?:\s+GROUP\s+BY\s+(.*?))?(?:\s+HAVING\s+(.*?))?$'
        match = re.match(pattern, sql, re.IGNORECASE | re.DOTALL)
        
        if not match:
            raise ValueError("Invalid SELECT with aggregation syntax")
        
        columns_str = match.group(1).strip()
        result['table'] = match.group(2)
        result['where'] = match.group(3)
        group_by_str = match.group(4)
        result['having'] = match.group(5)
        
        # Parser les colonnes et agrégations
        columns = [c.strip() for c in columns_str.split(',')]
        
        for col in columns:
            # Vérifier si c'est une fonction d'agrégation
            agg_match = re.match(r'(COUNT|SUM|AVG|MIN|MAX)\s*\(\s*([^)]+)\s*\)(?:\s+AS\s+(\w+))?', 
                                col, re.IGNORECASE)
            
            if agg_match:
                func = agg_match.group(1).upper()
                arg = agg_match.group(2).strip()
                alias = agg_match.group(3) or f"{func}_{arg}".replace('*', 'all')
                
                result['aggregations'].append({
                    'func': func,
                    'column': arg if arg != '*' else None,
                    'alias': alias
                })
            else:
                result['columns'].append(col)
        
        # Parser GROUP BY
        if group_by_str:
            result['group_by'] = [c.strip() for c in group_by_str.split(',')]
        
        return result


# ============================================================================
# INTÉGRATION DANS DMONSQL
# ============================================================================

def integrate_aggregation_in_dmonsql():
    """Guide d'intégration dans dmonsql_main.py"""
    
    code_example = '''
# Dans dmonsql_main.py, ajouter dans _execute_select():

def _execute_select(self, sql: str, db: Database):
    """Exécute un SELECT (avec ou sans agrégation)"""
    sql_upper = sql.upper()
    
    # ⭐ Vérifier si c'est un SELECT avec agrégation
    if 'GROUP BY' in sql_upper or any(func in sql_upper for func in ['COUNT(', 'SUM(', 'AVG(', 'MIN(', 'MAX(']):
        return self._execute_select_with_aggregation(sql, db)
    
    # ... code SELECT normal existant ...

def _execute_select_with_aggregation(self, sql: str, db: Database):
    """Exécute un SELECT avec GROUP BY et agrégations"""
    from dmonSQL.query.aggregation import AggregationEngine, AggregationParser
    
    # Parser la requête
    parsed = AggregationParser.parse_select_with_aggregation(sql)
    
    table = db.get_table(parsed['table'])
    rows = table.rows
    
    # Appliquer WHERE si présent
    if parsed['where']:
        where_func = self._parse_where(parsed['where'])
        rows = [row for row in rows if where_func(row)]
    
    # Si GROUP BY
    if parsed['group_by']:
        # Regrouper
        groups = AggregationEngine.group_by(rows, parsed['group_by'])
        
        # Appliquer les agrégations
        result = AggregationEngine.apply_aggregations(
            groups, 
            parsed['group_by'], 
            parsed['aggregations']
        )
        
        # Appliquer HAVING si présent
        if parsed['having']:
            # Parser HAVING (similaire à WHERE)
            # Ex: COUNT(*) > 5
            having_func = self._parse_having(parsed['having'])
            result = AggregationEngine.having(result, having_func)
    
    else:
        # Pas de GROUP BY : agrégation sur toutes les lignes
        result_row = {}
        for agg in parsed['aggregations']:
            func_name = agg['func']
            column = agg['column']
            alias = agg['alias']
            
            if func_name == 'COUNT':
                value = AggregationEngine.count(rows, column)
            elif func_name == 'SUM':
                value = AggregationEngine.sum(rows, column)
            elif func_name == 'AVG':
                value = AggregationEngine.avg(rows, column)
            elif func_name == 'MIN':
                value = AggregationEngine.min(rows, column)
            elif func_name == 'MAX':
                value = AggregationEngine.max(rows, column)
            
            result_row[alias] = value
        
        result = [result_row]
    
    self._print_result(result)
    return result
    '''
    
    return code_example


# ============================================================================
# EXEMPLES D'UTILISATION
# ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("EXEMPLES : Agrégations et GROUP BY")
    print("=" * 80)
    
    # Données de test
    employees = [
        {'id': 1, 'name': 'Alice', 'department': 'IT', 'salary': 70000},
        {'id': 2, 'name': 'Bob', 'department': 'IT', 'salary': 80000},
        {'id': 3, 'name': 'Charlie', 'department': 'HR', 'salary': 60000},
        {'id': 4, 'name': 'Dave', 'department': 'HR', 'salary': 65000},
        {'id': 5, 'name': 'Eve', 'department': 'Sales', 'salary': 55000},
    ]
    
    print("\n📊 Données employees:")
    for emp in employees:
        print(f"  {emp}")
    
    # 1. COUNT(*)
    print("\n1️⃣  COUNT(*) - Nombre total d'employés:")
    count = AggregationEngine.count(employees)
    print(f"  Total: {count}")
    
    # 2. AVG(salary)
    print("\n2️⃣  AVG(salary) - Salaire moyen:")
    avg_salary = AggregationEngine.avg(employees, 'salary')
    print(f"  Moyenne: ${avg_salary:,.2f}")
    
    # 3. GROUP BY department
    print("\n3️⃣  GROUP BY department:")
    groups = AggregationEngine.group_by(employees, ['department'])
    for dept, emps in groups.items():
        print(f"  {dept[0]}: {len(emps)} employé(s)")
    
    # 4. SELECT department, COUNT(*), AVG(salary) GROUP BY department
    print("\n4️⃣  SELECT department, COUNT(*), AVG(salary) GROUP BY department:")
    groups = AggregationEngine.group_by(employees, ['department'])
    result = AggregationEngine.apply_aggregations(
        groups,
        ['department'],
        [
            {'func': 'COUNT', 'column': '*', 'alias': 'count'},
            {'func': 'AVG', 'column': 'salary', 'alias': 'avg_salary'}
        ]
    )
    for row in result:
        print(f"  {row['department']}: {row['count']} employés, "
              f"salaire moyen ${row['avg_salary']:,.2f}")
    
    # 5. HAVING
    print("\n5️⃣  ... HAVING COUNT(*) > 1:")
    filtered = AggregationEngine.having(result, lambda row: row['count'] > 1)
    print(f"  Départements avec plus d'1 employé:")
    for row in filtered:
        print(f"    {row['department']}: {row['count']} employés")
    
    print("\n" + "=" * 80)
    print("USAGE SQL:")
    print("=" * 80)
    print("""
-- Compter tous les employés
SELECT COUNT(*) FROM employees;

-- Salaire moyen
SELECT AVG(salary) FROM employees;

-- Par département
SELECT department, COUNT(*), AVG(salary), MAX(salary)
FROM employees
GROUP BY department;

-- Avec filtre HAVING
SELECT department, COUNT(*) as count
FROM employees
GROUP BY department
HAVING COUNT(*) > 1;
    """)