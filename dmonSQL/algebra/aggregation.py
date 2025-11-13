
# ============================================================================
# AGGREGATION (GROUP BY, HAVING)
# ============================================================================

import json
from typing import Dict, List, Any, Optional, Callable
from collections import defaultdict
from dmonSQL.types.json_type import JSONType, JSONQuery
import re


class AggregateFunction:
    """Classe de base pour les fonctions d'agrégation"""
    
    def __init__(self):
        self.values = []
    
    def add(self, value):
        """Ajoute une valeur"""
        if value is not None:
            self.values.append(value)
    
    def compute(self):
        """Calcule le résultat"""
        raise NotImplementedError


class Count(AggregateFunction):
    """COUNT(*)"""
    
    def compute(self):
        return len(self.values)


class Sum(AggregateFunction):
    """SUM(column)"""
    
    def compute(self):
        if not self.values:
            return 0
        return sum(self.values)


class Avg(AggregateFunction):
    """AVG(column)"""
    
    def compute(self):
        if not self.values:
            return None
        return sum(self.values) / len(self.values)


class Min(AggregateFunction):
    """MIN(column)"""
    
    def compute(self):
        if not self.values:
            return None
        return min(self.values)


class Max(AggregateFunction):
    """MAX(column)"""
    
    def compute(self):
        if not self.values:
            return None
        return max(self.values)


class StdDev(AggregateFunction):
    """STDDEV(column) - Écart-type"""
    
    def compute(self):
        if len(self.values) < 2:
            return None
        
        mean = sum(self.values) / len(self.values)
        variance = sum((x - mean) ** 2 for x in self.values) / len(self.values)
        return variance ** 0.5


class Aggregator:
    """Gestion des agrégations avec GROUP BY et HAVING"""
    
    AGGREGATE_FUNCTIONS = {
        'COUNT': Count,
        'SUM': Sum,
        'AVG': Avg,
        'MIN': Min,
        'MAX': Max,
        'STDDEV': StdDev
    }
    
    @staticmethod
    def parse_select_with_aggregates(sql: str) -> Dict:
        """Parse un SELECT avec GROUP BY et HAVING"""
        # SELECT columns FROM table WHERE ... GROUP BY ... HAVING ... ORDER BY ...
        
        result = {
            'select': [],
            'from': None,
            'where': None,
            'group_by': [],
            'having': None,
            'order_by': []
        }
        
        # Extraire SELECT
        select_match = re.search(r'SELECT\s+(.+?)\s+FROM', sql, re.IGNORECASE)
        if select_match:
            select_clause = select_match.group(1)
            result['select'] = [c.strip() for c in select_clause.split(',')]
        
        # Extraire FROM
        from_match = re.search(r'FROM\s+(\w+)', sql, re.IGNORECASE)
        if from_match:
            result['from'] = from_match.group(1)
        
        # Extraire WHERE
        where_match = re.search(r'WHERE\s+(.+?)\s+GROUP BY', sql, re.IGNORECASE)
        if not where_match:
            where_match = re.search(r'WHERE\s+(.+?)(?:\s+ORDER BY|\s*$)', sql, re.IGNORECASE)
        if where_match:
            result['where'] = where_match.group(1).strip()
        
        # Extraire GROUP BY
        group_match = re.search(r'GROUP BY\s+(.+?)(?:\s+HAVING|\s+ORDER BY|\s*$)', sql, re.IGNORECASE)
        if group_match:
            group_clause = group_match.group(1)
            result['group_by'] = [c.strip() for c in group_clause.split(',')]
        
        # Extraire HAVING
        having_match = re.search(r'HAVING\s+(.+?)(?:\s+ORDER BY|\s*$)', sql, re.IGNORECASE)
        if having_match:
            result['having'] = having_match.group(1).strip()
        
        # Extraire ORDER BY
        order_match = re.search(r'ORDER BY\s+(.+?)$', sql, re.IGNORECASE)
        if order_match:
            order_clause = order_match.group(1)
            result['order_by'] = [c.strip() for c in order_clause.split(',')]
        
        return result
    
    @staticmethod
    def execute_group_by(rows: List[Dict], group_by_columns: List[str],
                        select_columns: List[str]) -> List[Dict]:
        """Exécute un GROUP BY avec agrégations"""
        
        # Grouper les lignes
        groups = defaultdict(list)
        
        for row in rows:
            # Créer la clé de groupe
            group_key = tuple(row.get(col) for col in group_by_columns)
            groups[group_key].append(row)
        
        # Calculer les agrégations
        results = []
        
        for group_key, group_rows in groups.items():
            result_row = {}
            
            # Colonnes de groupe
            for i, col in enumerate(group_by_columns):
                result_row[col] = group_key[i]
            
            # Colonnes avec agrégations
            for select_expr in select_columns:
                if select_expr in group_by_columns:
                    # Déjà ajouté
                    continue
                
                # Parser l'expression d'agrégation
                agg_result = Aggregator._parse_and_compute_aggregate(
                    select_expr, group_rows
                )
                
                if agg_result is not None:
                    alias = select_expr
                    # Extraire l'alias si présent (ex: COUNT(*) AS total)
                    if ' AS ' in select_expr.upper():
                        parts = re.split(r'\s+AS\s+', select_expr, flags=re.IGNORECASE)
                        alias = parts[1].strip()
                    
                    result_row[alias] = agg_result
            
            results.append(result_row)
        
        return results
    
    @staticmethod
    def _parse_and_compute_aggregate(expr: str, rows: List[Dict]) -> Any:
        """Parse et calcule une expression d'agrégation"""
        expr = expr.strip()
        
        # Détecter le type d'agrégation
        for func_name, func_class in Aggregator.AGGREGATE_FUNCTIONS.items():
            pattern = rf'{func_name}\s*\(([^)]+)\)'
            match = re.match(pattern, expr, re.IGNORECASE)
            
            if match:
                arg = match.group(1).strip()
                
                # Créer l'agrégateur
                aggregator = func_class()
                
                # Ajouter les valeurs
                if arg == '*':
                    # COUNT(*) : compter toutes les lignes
                    for row in rows:
                        aggregator.add(1)
                else:
                    # Agrégation sur une colonne
                    for row in rows:
                        aggregator.add(row.get(arg))
                
                return aggregator.compute()
        
        # Si pas d'agrégation, retourner la première valeur (pour GROUP BY)
        if rows and expr in rows[0]:
            return rows[0][expr]
        
        return None
    
    @staticmethod
    def apply_having(groups: List[Dict], having_condition: str) -> List[Dict]:
        """Applique la clause HAVING pour filtrer les groupes"""
        filtered = []
        
        for group in groups:
            # Remplacer les colonnes par leurs valeurs
            condition = having_condition
            for col, val in group.items():
                condition = condition.replace(col, str(val))
            
            # Évaluer la condition
            try:
                if eval(condition):
                    filtered.append(group)
            except:
                # Si l'évaluation échoue, inclure le groupe
                filtered.append(group)
        
        return filtered


# ============================================================================
# EXEMPLES
# ============================================================================

if __name__ == "__main__":
    print("="*60)
    print("JSON TYPE DEMO")
    print("="*60)
    
    # Créer un objet JSON
    user_data = {
        'id': 1,
        'name': 'Alice',
        'address': {
            'city': 'Paris',
            'country': 'France'
        },
        'hobbies': ['reading', 'coding', 'travel']
    }
    
    json_obj = JSONType(user_data)
    print("\nObjet JSON créé:")
    print(json_obj)
    
    # Extraction de données
    print("\nExtraction:")
    print(f"Name: {json_obj.get('name')}")
    print(f"City: {json_obj.get('address.city')}")
    print(f"First hobby: {json_obj.get('hobbies.0')}")
    
    # Modification
    json_obj.set('address.postal_code', '75001')
    print(f"\nAprès ajout du code postal: {json_obj.get('address')}")
    
    # Requêtes JSON
    print(f"\nContient 'address'? {JSONQuery.contains_key(json_obj, 'address')}")
    print(f"Nombre de hobbies: {JSONQuery.array_length(JSONType(json_obj.get('hobbies')))}")
    print(f"Clés de l'adresse: {JSONQuery.keys(JSONType(json_obj.get('address')))}")
    
    print("\n" + "="*60)
    print("AGGREGATION DEMO")
    print("="*60)
    
    # Données de test
    sales_data = [
        {'region': 'East', 'product': 'A', 'amount': 100, 'quantity': 5},
        {'region': 'East', 'product': 'B', 'amount': 150, 'quantity': 3},
        {'region': 'West', 'product': 'A', 'amount': 200, 'quantity': 10},
        {'region': 'West', 'product': 'B', 'amount': 180, 'quantity': 8},
        {'region': 'East', 'product': 'A', 'amount': 120, 'quantity': 6},
    ]
    
    print("\nDonnées de ventes:")
    for row in sales_data:
        print(f"  {row}")
    
    # GROUP BY region
    print("\n--- GROUP BY region ---")
    result1 = Aggregator.execute_group_by(
        sales_data,
        group_by_columns=['region'],
        select_columns=['region', 'SUM(amount)', 'AVG(quantity)', 'COUNT(*)']
    )
    
    print("Résultat:")
    for row in result1:
        print(f"  {row}")
    
    # GROUP BY region, product
    print("\n--- GROUP BY region, product ---")
    result2 = Aggregator.execute_group_by(
        sales_data,
        group_by_columns=['region', 'product'],
        select_columns=['region', 'product', 'SUM(amount) AS total', 'COUNT(*) AS count']
    )
    
    print("Résultat:")
    for row in result2:
        print(f"  {row}")
    
    # HAVING
    print("\n--- HAVING SUM(amount) > 200 ---")
    result3 = Aggregator.apply_having(result2, "total > 200")
    
    print("Résultat filtré:")
    for row in result3:
        print(f"  {row}")
    
    # Parse SQL complet
    print("\n" + "="*60)
    print("SQL PARSING DEMO")
    print("="*60)
    
    sql = """
    SELECT region, product, SUM(amount) AS total_sales, AVG(quantity) AS avg_qty
    FROM sales
    WHERE amount > 50
    GROUP BY region, product
    HAVING SUM(amount) > 200
    ORDER BY total_sales DESC
    """
    
    print(f"\nSQL: {sql}")
    parsed = Aggregator.parse_select_with_aggregates(sql)
    print("\nParsé:")
    for key, value in parsed.items():
        print(f"  {key}: {value}")
