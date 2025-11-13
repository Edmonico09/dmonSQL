"""
dmonSQL - Fonctionnalités avancées P2
DISTINCT, LIMIT+OFFSET, SUBQUERIES, UNION/INTERSECT/EXCEPT
"""

import re
from typing import List, Dict, Any, Tuple


# ==================== DISTINCT ====================

def execute_distinct(rows: List[Dict], columns: List[str] = None) -> List[Dict]:
    """
    Élimine les doublons d'un résultat
    
    SELECT DISTINCT city FROM users;
    SELECT DISTINCT department, level FROM employees;
    """
    if not rows:
        return []
    
    seen = set()
    unique_rows = []
    
    for row in rows:
        # Si colonnes spécifiées, ne comparer que ces colonnes
        if columns:
            row_tuple = tuple(row.get(col) for col in columns if col in row)
        else:
            # Sinon, comparer toute la ligne
            row_tuple = tuple(sorted(row.items()))
        
        if row_tuple not in seen:
            seen.add(row_tuple)
            unique_rows.append(row)
    
    return unique_rows


# ==================== LIMIT + OFFSET ====================

def apply_limit_offset(rows: List[Dict], limit: int = None, offset: int = None) -> List[Dict]:
    """
    Applique LIMIT et OFFSET à un résultat
    
    SELECT * FROM users LIMIT 10;
    SELECT * FROM users LIMIT 10 OFFSET 20;  -- Pagination
    SELECT * FROM users OFFSET 5 LIMIT 10;   -- Ordre inversé supporté
    """
    if not rows:
        return []
    
    # Appliquer OFFSET d'abord
    if offset and offset > 0:
        rows = rows[offset:]
    
    # Puis LIMIT
    if limit and limit > 0:
        rows = rows[:limit]
    
    return rows


# ==================== SUBQUERIES (sous-requêtes) ====================

class SubqueryEngine:
    """Moteur d'exécution des sous-requêtes"""
    
    def __init__(self, db_system):
        self.db_system = db_system
    
    def execute_subquery(self, subquery_sql: str) -> List[Any]:
        """
        Exécute une sous-requête et retourne les résultats
        """
        result = self.db_system.execute(subquery_sql)
        
        if not result:
            return []
        
        # Si c'est une sous-requête scalaire (une seule valeur)
        if len(result) == 1 and len(result[0]) == 1:
            return list(result[0].values())[0]
        
        # Si c'est une liste de valeurs (pour IN)
        if len(result[0]) == 1:
            col_name = list(result[0].keys())[0]
            return [row[col_name] for row in result]
        
        # Sinon retourner tout
        return result
    
    def parse_and_execute_with_subquery(self, sql: str) -> List[Dict]:
        """Version améliorée avec meilleure gestion des erreurs"""
        
        # Essayer d'abord les sous-requêtes IN
        in_pattern = r'WHERE\s+(\w+)\s+IN\s*\(\s*(SELECT[^)]+)\s*\)'
        in_match = re.search(in_pattern, sql, re.IGNORECASE | re.DOTALL)
        
        if in_match:
            try:
                column = in_match.group(1)
                subquery = in_match.group(2).strip()
                
                # Exécuter la sous-requête
                subquery_result = self.execute_subquery(subquery)
                
                if not subquery_result:
                    return []  # Aucun résultat si sous-requête vide
                
                # Construire la nouvelle requête
                if isinstance(subquery_result, list):
                    values_str = ', '.join(
                        f"'{v}'" if isinstance(v, str) else str(v) 
                        for v in subquery_result
                    )
                    new_sql = re.sub(
                        in_pattern, 
                        f'WHERE {column} IN ({values_str})', 
                        sql, 
                        flags=re.IGNORECASE
                    )
                else:
                    # Sous-requête scalaire
                    new_sql = re.sub(
                        in_pattern,
                        f'WHERE {column} = {subquery_result}',
                        sql,
                        flags=re.IGNORECASE
                    )
                
                return self.db_system.execute(new_sql)
                
            except Exception as e:
                self.db_system.logger.warning(f"IN subquery failed: {e}")
        
        # Essayer les sous-requêtes scalaires
        scalar_pattern = r'WHERE\s+(\w+)\s*([><=!]+)\s*\(\s*(SELECT[^)]+)\s*\)'
        scalar_match = re.search(scalar_pattern, sql, re.IGNORECASE | re.DOTALL)
        
        if scalar_match:
            try:
                column = scalar_match.group(1)
                operator = scalar_match.group(2)
                subquery = scalar_match.group(3).strip()
                
                # Exécuter la sous-requête
                value = self.execute_subquery(subquery)
                
                new_sql = re.sub(
                    scalar_pattern,
                    f'WHERE {column} {operator} {value}',
                    sql,
                    flags=re.IGNORECASE
                )
                
                return self.db_system.execute(new_sql)
                
            except Exception as e:
                self.db_system.logger.warning(f"Scalar subquery failed: {e}")
        
        # Si aucune sous-requête n'est reconnue, lever une erreur claire
        raise ValueError("Unsupported subquery type or invalid subquery syntax")

# ==================== UNION / INTERSECT / EXCEPT ====================

def execute_union(result1: List[Dict], result2: List[Dict], all_duplicates: bool = False) -> List[Dict]:
    """
    UNION : Combine deux résultats en éliminant les doublons
    UNION ALL : Combine deux résultats en gardant les doublons
    
    SELECT name FROM employees UNION SELECT name FROM contractors;
    SELECT id FROM users UNION ALL SELECT user_id FROM orders;
    """
    if not result1:
        return result2
    if not result2:
        return result1
    
    # Vérifier que les colonnes sont compatibles
    cols1 = set(result1[0].keys())
    cols2 = set(result2[0].keys())
    
    if cols1 != cols2:
        raise ValueError("UNION requires same number and type of columns")
    
    # Combiner
    combined = result1 + result2
    
    # Éliminer les doublons si nécessaire
    if not all_duplicates:
        return execute_distinct(combined)
    
    return combined


def execute_intersect(result1: List[Dict], result2: List[Dict]) -> List[Dict]:
    """
    INTERSECT : Retourne uniquement les lignes présentes dans les deux résultats
    
    SELECT id FROM users INTERSECT SELECT user_id FROM orders;
    """
    if not result1 or not result2:
        return []
    
    # Vérifier que les colonnes sont compatibles
    cols1 = set(result1[0].keys())
    cols2 = set(result2[0].keys())
    
    if cols1 != cols2:
        raise ValueError("INTERSECT requires same number and type of columns")
    
    # Convertir les résultats en tuples pour comparaison
    set1 = {tuple(sorted(row.items())) for row in result1}
    set2 = {tuple(sorted(row.items())) for row in result2}
    
    # Intersection
    common = set1 & set2
    
    # Reconvertir en dictionnaires
    return [dict(items) for items in common]


def execute_except(result1: List[Dict], result2: List[Dict]) -> List[Dict]:
    """
    EXCEPT (ou MINUS) : Retourne les lignes de result1 qui ne sont pas dans result2
    
    SELECT id FROM all_users EXCEPT SELECT id FROM banned_users;
    """
    if not result1:
        return []
    if not result2:
        return result1
    
    # Vérifier que les colonnes sont compatibles
    cols1 = set(result1[0].keys())
    cols2 = set(result2[0].keys())
    
    if cols1 != cols2:
        raise ValueError("EXCEPT requires same number and type of columns")
    
    # Convertir les résultats en tuples pour comparaison
    set1 = {tuple(sorted(row.items())) for row in result1}
    set2 = {tuple(sorted(row.items())) for row in result2}
    
    # Différence
    difference = set1 - set2
    
    # Reconvertir en dictionnaires
    return [dict(items) for items in difference]


# ==================== ORDER BY Multiple Columns ====================

def parse_order_by(order_by_clause: str) -> List[Tuple[str, str]]:
    """
    Parse ORDER BY avec plusieurs colonnes
    
    ORDER BY col1 ASC, col2 DESC, col3
    ORDER BY 1, 2 DESC  (ordre par position)
    """
    parts = []
    
    for part in order_by_clause.split(','):
        part = part.strip()
        
        if ' ' in part:
            col, direction = part.rsplit(' ', 1)
            col = col.strip()
            direction = direction.strip().upper()
        else:
            col = part
            direction = 'ASC'
        
        # Valider la direction
        if direction not in ('ASC', 'DESC'):
            direction = 'ASC'
        
        parts.append((col, direction))
    
    return parts


def apply_order_by(rows: List[Dict], order_by_parts: List[Tuple[str, str]]) -> List[Dict]:
    """
    Applique ORDER BY avec plusieurs colonnes
    """
    if not rows or not order_by_parts:
        return rows
    
    # Trier en appliquant les ordres dans l'ordre inverse
    # (pour que le premier critère soit prioritaire)
    for col, direction in reversed(order_by_parts):
        reverse = (direction == 'DESC')
        
        # Gérer l'ordre par position (1, 2, 3...)
        if col.isdigit():
            col_index = int(col) - 1
            cols = list(rows[0].keys())
            if 0 <= col_index < len(cols):
                col = cols[col_index]
        
        rows = sorted(
            rows,
            key=lambda x: (x.get(col) is None, x.get(col)),  # NULL en dernier
            reverse=reverse
        )
    
    return rows


# ==================== TESTS ====================

if __name__ == "__main__":
    # Test DISTINCT
    print("="*60)
    print("Test DISTINCT")
    print("="*60)
    
    data = [
        {'city': 'Paris', 'country': 'France'},
        {'city': 'London', 'country': 'UK'},
        {'city': 'Paris', 'country': 'France'},  # Doublon
        {'city': 'Berlin', 'country': 'Germany'},
    ]
    
    result = execute_distinct(data)
    print(f"Original: {len(data)} rows")
    print(f"After DISTINCT: {len(result)} rows")
    for row in result:
        print(row)
    
    # Test LIMIT + OFFSET
    print("\n" + "="*60)
    print("Test LIMIT + OFFSET")
    print("="*60)
    
    data = [{'id': i, 'name': f'User{i}'} for i in range(1, 21)]
    
    result = apply_limit_offset(data, limit=5, offset=10)
    print("LIMIT 5 OFFSET 10:")
    for row in result:
        print(row)
    
    # Test UNION
    print("\n" + "="*60)
    print("Test UNION")
    print("="*60)
    
    employees = [
        {'name': 'Alice', 'role': 'Engineer'},
        {'name': 'Bob', 'role': 'Manager'},
    ]
    
    contractors = [
        {'name': 'Charlie', 'role': 'Consultant'},
        {'name': 'Alice', 'role': 'Engineer'},  # Doublon
    ]
    
    result = execute_union(employees, contractors)
    print(f"UNION: {len(result)} rows")
    for row in result:
        print(row)
    
    # Test INTERSECT
    print("\n" + "="*60)
    print("Test INTERSECT")
    print("="*60)
    
    set1 = [
        {'id': 1, 'value': 'A'},
        {'id': 2, 'value': 'B'},
        {'id': 3, 'value': 'C'},
    ]
    
    set2 = [
        {'id': 2, 'value': 'B'},
        {'id': 3, 'value': 'C'},
        {'id': 4, 'value': 'D'},
    ]
    
    result = execute_intersect(set1, set2)
    print(f"INTERSECT: {len(result)} rows")
    for row in result:
        print(row)
    
    # Test EXCEPT
    print("\n" + "="*60)
    print("Test EXCEPT")
    print("="*60)
    
    result = execute_except(set1, set2)
    print(f"EXCEPT: {len(result)} rows")
    for row in result:
        print(row)
    
    # Test ORDER BY multiple
    print("\n" + "="*60)
    print("Test ORDER BY multiple columns")
    print("="*60)
    
    data = [
        {'dept': 'IT', 'level': 2, 'name': 'Alice'},
        {'dept': 'HR', 'level': 1, 'name': 'Bob'},
        {'dept': 'IT', 'level': 1, 'name': 'Charlie'},
        {'dept': 'HR', 'level': 2, 'name': 'David'},
    ]
    
    order_parts = parse_order_by('dept ASC, level DESC')
    result = apply_order_by(data, order_parts)
    
    print("ORDER BY dept ASC, level DESC:")
    for row in result:
        print(row)