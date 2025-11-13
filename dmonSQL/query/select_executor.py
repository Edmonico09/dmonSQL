"""
dmonSQL/query/select_executor.py
Exécuteur spécialisé pour les requêtes SELECT
Gère : SELECT simple, JOIN, GROUP BY, WHERE, ORDER BY, LIMIT
"""

import re
from typing import List, Dict, Any, Tuple

from dmonSQL.core.database import Database
from dmonSQL.core.table import Table
from dmonSQL.utils.logger import get_logger


class SelectExecutor:
    """Exécuteur spécialisé pour toutes les variantes de SELECT"""
    
    def __init__(self, dmonsql_instance):
        """
        Args:
            dmonsql_instance: Instance de DmonSQL (pour accès aux attributs)
        """
        self.dmonsql = dmonsql_instance
        self.logger = get_logger("SelectExecutor")
    
    def execute(self, sql: str, db: Database) -> List[Dict]:
        """
        Point d'entrée principal pour exécuter un SELECT
        
        Args:
            sql: Requête SELECT
            db: Base de données
            
        Returns:
            Liste de dictionnaires (résultat)
        """
        sql_upper = sql.upper()
        
        # Vérifier GROUP BY (prioritaire)
        if ' GROUP BY ' in sql_upper:
            return self._execute_with_group_by(sql, db)
        
        # Vérifier JOIN
        if ' JOIN ' in sql_upper:
            return self._execute_with_join(sql, db)
        
        # SELECT simple
        return self._execute_simple(sql, db)
    
    # ==================== SELECT SIMPLE ====================
    
    def _execute_simple(self, sql: str, db: Database) -> List[Dict]:
        """
        Exécute un SELECT simple (sans JOIN ni GROUP BY)
        
        Exemples:
            SELECT * FROM users
            SELECT name, email FROM users WHERE id = 1
            SELECT * FROM users ORDER BY name DESC LIMIT 10
        """
        # Pattern de parsing
        match = re.match(
            r'SELECT\s+(.*?)\s+FROM\s+(\w+)(?:\s+WHERE\s+(.*?))?(?:\s+ORDER BY\s+(.*?))?(?:\s+LIMIT\s+(\d+))?$',
            sql, re.IGNORECASE | re.DOTALL
        )
        
        if not match:
            raise ValueError("Invalid SELECT syntax")
        
        columns_str = match.group(1).strip()
        table_name = match.group(2)
        where_clause = match.group(3)
        order_by_clause = match.group(4)
        limit_clause = match.group(5)
        
        # Récupérer la table
        table = db.get_table(table_name)
        
        # Parser les colonnes
        columns = None if columns_str == '*' else [c.strip() for c in columns_str.split(',')]
        
        # Parser WHERE
        where_func = None
        if where_clause:
            where_func = self._parse_where(where_clause)
        
        # Parser ORDER BY
        order_by = None
        if order_by_clause:
            order_by = self._parse_order_by(order_by_clause)
        
        # Parser LIMIT
        limit = int(limit_clause) if limit_clause else None
        
        # Exécuter via la méthode select() de Table
        result = table.select(
            columns=columns,
            where=where_func,
            order_by=order_by,
            limit=limit
        )
        
        # Afficher le résultat
        self.dmonsql._print_result(result)
        return result
    
    # ==================== SELECT WITH JOIN ====================
    
    def _execute_with_join(self, sql: str, db: Database) -> List[Dict]:
        """
        Exécute un SELECT avec JOIN
        
        Exemples:
            SELECT * FROM users u JOIN orders o ON u.id = o.user_id
            SELECT u.name, o.total FROM users u LEFT JOIN orders o ON u.id = o.user_id
        """
        # Pattern pour parser le JOIN
        pattern = r'SELECT\s+(.*?)\s+FROM\s+(\w+)(?:\s+(?:AS\s+)?(\w+))?\s+(INNER\s+JOIN|LEFT\s+JOIN|RIGHT\s+JOIN|JOIN)\s+(\w+)(?:\s+(?:AS\s+)?(\w+))?\s+ON\s+([\w.]+)\s*=\s*([\w.]+)(?:\s+WHERE\s+(.*))?'
        
        match = re.match(pattern, sql, re.IGNORECASE | re.DOTALL)
        if not match:
            raise ValueError("Invalid JOIN syntax")
        
        columns_str = match.group(1).strip()
        table1_name = match.group(2)
        table1_alias = match.group(3) or table1_name
        join_type = match.group(4).upper().strip()
        table2_name = match.group(5)
        table2_alias = match.group(6) or table2_name
        join_col1 = match.group(7)
        join_col2 = match.group(8)
        where_clause = match.group(9)
        
        # Récupérer les tables
        table1 = db.get_table(table1_name)
        table2 = db.get_table(table2_name)
        
        # Extraire les noms de colonnes (sans préfixe de table)
        col1 = join_col1.split('.')[-1] if '.' in join_col1 else join_col1
        col2 = join_col2.split('.')[-1] if '.' in join_col2 else join_col2
        
        # Exécuter le JOIN approprié
        if join_type in ('JOIN', 'INNER JOIN'):
            result = self._inner_join(table1, table2, col1, col2, table1_alias, table2_alias)
        elif join_type == 'LEFT JOIN':
            result = self._left_join(table1, table2, col1, col2, table1_alias, table2_alias)
        elif join_type == 'RIGHT JOIN':
            result = self._right_join(table1, table2, col1, col2, table1_alias, table2_alias)
        else:
            raise ValueError(f"Unsupported join type: {join_type}")
        
        # Appliquer WHERE si présent
        if where_clause:
            where_func = self._parse_where_join(where_clause)
            result = [row for row in result if where_func(row)]
        
        # Projection des colonnes
        if columns_str.strip() != '*':
            requested_cols = [c.strip() for c in columns_str.split(',')]
            result = self._project_columns(result, requested_cols)
        
        # Afficher le résultat
        self.dmonsql._print_result(result)
        return result
    
    def _inner_join(self, table1: Table, table2: Table, col1: str, col2: str, 
                    alias1: str, alias2: str) -> List[Dict]:
        """INNER JOIN : Retourne uniquement les lignes correspondantes"""
        result = []
        for row1 in table1.rows:
            for row2 in table2.rows:
                val1 = row1.get(col1)
                val2 = row2.get(col2)
                
                if val1 is not None and val1 == val2:
                    # Combiner les lignes avec préfixes
                    combined = {}
                    for k, v in row1.items():
                        combined[f"{alias1}.{k}"] = v
                    for k, v in row2.items():
                        combined[f"{alias2}.{k}"] = v
                    result.append(combined)
        return result
    
    def _left_join(self, table1: Table, table2: Table, col1: str, col2: str,
                   alias1: str, alias2: str) -> List[Dict]:
        """LEFT JOIN : Toutes les lignes de table1, avec correspondances de table2"""
        result = []
        for row1 in table1.rows:
            matched = False
            for row2 in table2.rows:
                if row1.get(col1) == row2.get(col2):
                    # Ligne correspondante trouvée
                    combined = {}
                    for k, v in row1.items():
                        combined[f"{alias1}.{k}"] = v
                    for k, v in row2.items():
                        combined[f"{alias2}.{k}"] = v
                    result.append(combined)
                    matched = True
            
            # Si aucune correspondance, ajouter quand même la ligne de table1
            if not matched:
                combined = {}
                for k, v in row1.items():
                    combined[f"{alias1}.{k}"] = v
                for k in table2.columns.keys():
                    combined[f"{alias2}.{k}"] = None
                result.append(combined)
        
        return result
    
    def _right_join(self, table1: Table, table2: Table, col1: str, col2: str,
                    alias1: str, alias2: str) -> List[Dict]:
        """RIGHT JOIN : Toutes les lignes de table2, avec correspondances de table1"""
        # RIGHT JOIN = LEFT JOIN inversé
        return self._left_join(table2, table1, col2, col1, alias2, alias1)
    
    # ==================== SELECT WITH GROUP BY ====================
    
    def _execute_with_group_by(self, sql: str, db: Database) -> List[Dict]:
        """
        Exécute un SELECT avec GROUP BY et agrégations
        
        Exemples:
            SELECT department, COUNT(*) FROM users GROUP BY department
            SELECT department, AVG(salary) FROM users GROUP BY department HAVING AVG(salary) > 50000
        """
        if not hasattr(self.dmonsql, 'aggregation_engine'):
            raise ValueError("Aggregation engine not available")
        
        # Pattern de parsing
        select_match = re.match(
            r'SELECT\s+(.*?)\s+FROM\s+(.*?)(?:\s+WHERE\s+(.*?))?(?:\s+GROUP BY\s+(.*?))?(?:\s+HAVING\s+(.*?))?(?:\s+ORDER BY\s+(.*?))?(?:\s+LIMIT\s+(\d+))?$',
            sql, re.IGNORECASE | re.DOTALL
        )
        
        if not select_match:
            raise ValueError("Invalid SELECT ... GROUP BY syntax")
        
        select_clause = select_match.group(1).strip()
        from_clause = select_match.group(2).strip()
        where_clause = select_match.group(3)
        group_by_clause = select_match.group(4)
        having_clause = select_match.group(5)
        order_by_clause = select_match.group(6)
        limit_clause = select_match.group(7)
        
        # Gérer FROM avec JOIN
        if 'JOIN' in from_clause.upper():
            join_sql = f"SELECT * FROM {from_clause}"
            if where_clause:
                join_sql += f" WHERE {where_clause}"
            rows = self._execute_with_join(join_sql, db)
        else:
            # Table simple
            table_name = from_clause.split()[0].strip()
            table = db.get_table(table_name)
            rows = table.rows
            
            if where_clause:
                where_func = self._parse_where(where_clause)
                rows = [row for row in rows if where_func(row)]
        
        # Parser GROUP BY
        group_by_cols = [col.strip() for col in group_by_clause.split(',')]
        
        # Parser SELECT et gérer les alias
        select_parts = []
        for expr in select_clause.split(','):
            expr = expr.strip()
            
            # Détecter alias avec AS ou espace
            if ' AS ' in expr.upper():
                parts = re.split(r'\s+AS\s+', expr, 1, re.IGNORECASE)
                real_col = parts[0].strip()
                alias = parts[1].strip()
            elif ' ' in expr and not any(func in expr.upper() for func in ['COUNT', 'SUM', 'AVG', 'MIN', 'MAX']):
                parts = expr.rsplit(' ', 1)
                if len(parts) == 2:
                    real_col = parts[0].strip()
                    alias = parts[1].strip()
                else:
                    real_col = expr
                    alias = expr
            else:
                real_col = expr
                alias = expr
            
            if alias != real_col:
                select_parts.append(f"{real_col} AS {alias}")
            else:
                select_parts.append(real_col)
        
        # Exécuter l'agrégation via l'AggregationEngine
        result = self.dmonsql.aggregation_engine.execute_group_by(
            rows, 
            select_parts, 
            group_by_cols
        )
        
        # Appliquer HAVING
        if having_clause:
            having_func = self._parse_having(having_clause)
            result = [row for row in result if having_func(row)]
        
        # Appliquer ORDER BY
        if order_by_clause:
            order_parts = self._parse_order_by(order_by_clause)
            for col, direction in reversed(order_parts):
                reverse = direction == 'DESC'
                result = sorted(
                    result,
                    key=lambda x: (x.get(col) is None, x.get(col) or 0),
                    reverse=reverse
                )
        
        # Appliquer LIMIT
        if limit_clause:
            result = result[:int(limit_clause)]
        
        # Afficher le résultat
        self.dmonsql._print_result(result)
        return result
    
    # ==================== HELPERS - PARSING ====================
    
    def _parse_where(self, where_clause: str) -> callable:
        """Parse une clause WHERE simple (col = val)"""
        match = re.match(r'(\w+)\s*(=|>|<|>=|<=|!=)\s*(.+)', where_clause.strip())
        if not match:
            raise ValueError(f"Invalid WHERE clause: {where_clause}")
        
        col = match.group(1)
        op = match.group(2)
        val = match.group(3).strip().strip("'\"")
        
        # Convertir la valeur
        try:
            val = int(val)
        except:
            try:
                val = float(val)
            except:
                pass
        
        # Opérateurs
        ops = {
            '=': lambda a, b: a == b,
            '>': lambda a, b: a is not None and b is not None and a > b,
            '<': lambda a, b: a is not None and b is not None and a < b,
            '>=': lambda a, b: a is not None and b is not None and a >= b,
            '<=': lambda a, b: a is not None and b is not None and a <= b,
            '!=': lambda a, b: a != b,
        }
        
        op_func = ops.get(op)
        return lambda row: op_func(row.get(col), val)
    
    def _parse_where_join(self, where_clause: str) -> callable:
        """Parse WHERE pour JOIN (avec préfixes de table)"""
        match = re.match(r'([\w.]+)\s*(=|>|<|>=|<=|!=|<>)\s*(.+)', where_clause.strip())
        if not match:
            raise ValueError(f"Invalid WHERE clause: {where_clause}")
        
        col = match.group(1).strip()
        op = match.group(2)
        val = match.group(3).strip()
        
        # Parser la valeur
        if (val.startswith("'") and val.endswith("'")) or \
           (val.startswith('"') and val.endswith('"')):
            val = val[1:-1]
        else:
            try:
                val = int(val)
            except ValueError:
                try:
                    val = float(val)
                except ValueError:
                    pass
        
        # Opérateurs
        ops = {
            '=': lambda a, b: a == b,
            '>': lambda a, b: a is not None and b is not None and a > b,
            '<': lambda a, b: a is not None and b is not None and a < b,
            '>=': lambda a, b: a is not None and b is not None and a >= b,
            '<=': lambda a, b: a is not None and b is not None and a <= b,
            '!=': lambda a, b: a != b,
            '<>': lambda a, b: a != b,
        }
        
        op_func = ops.get(op)
        return lambda row: op_func(row.get(col), val)
    
    def _parse_having(self, having_clause: str) -> callable:
        """Parse HAVING (similaire à WHERE mais sur résultats agrégés)"""
        match = re.match(r'(\w+)\s*(=|>|<|>=|<=|!=)\s*(.+)', having_clause.strip())
        if not match:
            raise ValueError(f"Invalid HAVING clause: {having_clause}")
        
        col = match.group(1)
        op = match.group(2)
        val = match.group(3).strip()
        
        # Convertir la valeur
        try:
            val = int(val)
        except ValueError:
            try:
                val = float(val)
            except ValueError:
                val = val.strip("'\"")
        
        # Opérateurs
        ops = {
            '=': lambda a, b: a == b,
            '>': lambda a, b: a is not None and b is not None and a > b,
            '<': lambda a, b: a is not None and b is not None and a < b,
            '>=': lambda a, b: a is not None and b is not None and a >= b,
            '<=': lambda a, b: a is not None and b is not None and a <= b,
            '!=': lambda a, b: a != b,
        }
        
        op_func = ops.get(op)
        return lambda row: op_func(row.get(col), val)
    
    def _parse_order_by(self, order_by_clause: str) -> List[Tuple[str, str]]:
        """
        Parse ORDER BY
        
        Exemples:
            "name" -> [("name", "ASC")]
            "name DESC" -> [("name", "DESC")]
            "age DESC, name" -> [("age", "DESC"), ("name", "ASC")]
        """
        order_parts = []
        for part in order_by_clause.split(','):
            part = part.strip()
            if ' ' in part:
                col, direction = part.rsplit(' ', 1)
                order_parts.append((col.strip(), direction.strip().upper()))
            else:
                order_parts.append((part, 'ASC'))
        return order_parts
    
    def _project_columns(self, rows: List[Dict], columns: List[str]) -> List[Dict]:
        """
        Projection de colonnes (pour SELECT avec colonnes spécifiques)
        
        Gère les colonnes avec et sans préfixes de table
        """
        if not rows:
            return []
        
        result = []
        for row in rows:
            projected = {}
            for col in columns:
                col = col.strip()
                value = None
                
                # Chercher la colonne exacte
                if col in row:
                    value = row[col]
                else:
                    # Chercher avec préfixes
                    for key in row.keys():
                        if key == col or key.endswith(f".{col}"):
                            value = row[key]
                            break
                        if '.' in col:
                            _, col_name = col.rsplit('.', 1)
                            if key.endswith(f".{col_name}"):
                                value = row[key]
                                break
                
                projected[col] = value
            result.append(projected)
        
        return result