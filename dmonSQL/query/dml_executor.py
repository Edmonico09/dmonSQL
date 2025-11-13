"""
dmonSQL/query/dml_executor.py
Exécuteur spécialisé pour INSERT, UPDATE, DELETE
Gère : Manipulation des données
"""

import re
from typing import Dict, Any

from dmonSQL.core.database import Database
from dmonSQL.utils.logger import get_logger


class DMLExecutor:
    """Exécuteur spécialisé pour les opérations DML (Data Manipulation Language)"""
    
    def __init__(self, dmonsql_instance):
        """
        Args:
            dmonsql_instance: Instance de DmonSQL (pour accès aux attributs)
        """
        self.dmonsql = dmonsql_instance
        self.logger = get_logger("DMLExecutor")
    
    # ==================== INSERT ====================
    
    def execute_insert(self, sql: str, db: Database) -> int:
        """
        Exécute INSERT INTO
        
        Syntaxes supportées:
            INSERT INTO table (col1, col2) VALUES (val1, val2)
            INSERT INTO table (col1, col2) VALUES (val1, val2), (val3, val4)
        
        Args:
            sql: Requête INSERT
            db: Base de données
            
        Returns:
            Nombre de lignes insérées
        """
        # Pattern pour parser INSERT avec multi-valeurs
        insert_pattern = r"INSERT\s+INTO\s+(\w+)\s*\(([^)]+)\)\s*VALUES\s*((?:\([^)]*\)(?:\s*,\s*\([^)]*\))*)\s*)"
        match = re.match(insert_pattern, sql, re.IGNORECASE | re.DOTALL)
        
        if not match:
            raise ValueError("Invalid INSERT syntax")
        
        table_name = match.group(1).strip()
        columns_str = match.group(2)
        values_str = match.group(3)
        
        # Récupérer la table
        table = db.get_table(table_name)
        
        # Parser les colonnes
        columns = [c.strip() for c in columns_str.split(",")]
        
        # Parser les tuples de valeurs
        value_tuples = re.findall(r"\(([^)]*)\)", values_str)
        
        if not value_tuples:
            raise ValueError("No VALUES found in INSERT statement")
        
        inserted_count = 0
        
        # Insérer chaque tuple
        for value_tuple in value_tuples:
            raw_values = [v.strip() for v in value_tuple.split(",")]
            
            if len(raw_values) != len(columns):
                raise ValueError(
                    f"Column count mismatch: expected {len(columns)}, got {len(raw_values)}"
                )
            
            # Parser chaque valeur
            values = []
            for val in raw_values:
                val = val.strip()
                parsed_val = self._parse_value(val)
                values.append(parsed_val)
            
            # Créer le dictionnaire de valeurs
            values_dict = dict(zip(columns, values))
            
            # Insérer la ligne
            table.insert(values_dict)
            inserted_count += 1
            
            # Logger dans la transaction si active
            if self._is_in_transaction():
                self.dmonsql.transaction_manager.log_operation('INSERT', table_name, values_dict)
        
        # Sauvegarder si pas en transaction
        if not self._is_in_transaction():
            self.dmonsql.save_database(self.dmonsql.current_db)
        
        print(f"✓ Inserted {inserted_count} row(s)")
        return inserted_count
    
    # ==================== UPDATE ====================
    
    def execute_update(self, sql: str, db: Database) -> int:
        """
        Exécute UPDATE
        
        Syntaxe:
            UPDATE table SET col1=val1, col2=val2 WHERE condition
        
        Args:
            sql: Requête UPDATE
            db: Base de données
            
        Returns:
            Nombre de lignes modifiées
        """
        # Pattern pour parser UPDATE
        match = re.match(
            r'UPDATE\s+(\w+)\s+SET\s+(.*?)(?:\s+WHERE\s+(.*))?$',
            sql, re.IGNORECASE
        )
        
        if not match:
            raise ValueError("Invalid UPDATE syntax")
        
        table_name = match.group(1)
        set_clause = match.group(2)
        where_clause = match.group(3)
        
        # Récupérer la table
        table = db.get_table(table_name)
        
        # Parser SET clause (col1=val1, col2=val2)
        values = {}
        assignments = re.findall(r"(\w+)\s*=\s*('[^']*'|\"[^\"]*\"|\S+)", set_clause)
        
        for col, val in assignments:
            col = col.strip()
            val = val.strip()
            values[col] = self._parse_value(val)
        
        if not values:
            raise ValueError("No valid SET assignments found")
        
        # Parser WHERE
        where_func = None
        if where_clause:
            where_func = self._parse_where(where_clause)
        
        # Exécuter l'UPDATE
        count = table.update(values, where=where_func)
        
        # Logger dans la transaction si active
        if self._is_in_transaction():
            self.dmonsql.transaction_manager.log_operation('UPDATE', table_name, values)
        
        # Sauvegarder si pas en transaction
        if not self._is_in_transaction():
            self.dmonsql.save_database(self.dmonsql.current_db)
        
        print(f"✓ {count} row(s) updated")
        return count
    
    # ==================== DELETE ====================
    
    def execute_delete(self, sql: str, db: Database) -> int:
        """
        Exécute DELETE
        
        Syntaxe:
            DELETE FROM table WHERE condition
            DELETE FROM table  (supprime toutes les lignes)
        
        Args:
            sql: Requête DELETE
            db: Base de données
            
        Returns:
            Nombre de lignes supprimées
        """
        # Pattern pour parser DELETE
        match = re.match(
            r'DELETE\s+FROM\s+(\w+)(?:\s+WHERE\s+(.*))?',
            sql, re.IGNORECASE
        )
        
        if not match:
            raise ValueError("Invalid DELETE syntax")
        
        table_name = match.group(1)
        where_clause = match.group(2)
        
        # Récupérer la table
        table = db.get_table(table_name)
        
        # Parser WHERE
        where_func = None
        if where_clause:
            where_func = self._parse_where(where_clause)
        
        # Exécuter le DELETE
        count = table.delete(where=where_func)
        
        # Logger dans la transaction si active
        if self._is_in_transaction():
            self.dmonsql.transaction_manager.log_operation('DELETE', table_name, where_clause)
        
        # Sauvegarder si pas en transaction
        if not self._is_in_transaction():
            self.dmonsql.save_database(self.dmonsql.current_db)
        
        print(f"✓ Deleted {count} row(s)")
        return count
    
    # ==================== HELPERS ====================
    
    def _parse_value(self, val: str) -> Any:
        """
        Parse une valeur SQL en Python
        
        Exemples:
            'Alice' -> 'Alice'
            42 -> 42
            3.14 -> 3.14
            NULL -> None
        """
        val = val.strip()
        
        # Gestion des types spéciaux dmonSQL
        if val.upper().startswith('MATRIX('):
            from dmonSQL.data_types.matrixType import MatrixType
            return MatrixType.from_string(val)
        
        if '@' in val and (val.startswith("'") and val.endswith("'")): 
            from dmonSQL.data_types.email_type import EmailType
            return EmailType(val[1:-1])
        
        if val.startswith('{') and val.endswith('}'):
            from dmonSQL.data_types.json_type import JSONType
            return JSONType(val)
        
        # NULL
        if val.upper() == 'NULL':
            return None
        
        # String entre quotes
        if (val.startswith("'") and val.endswith("'")) or \
           (val.startswith('"') and val.endswith('"')):
            return val[1:-1]
        
        # Nombre entier
        try:
            return int(val)
        except ValueError:
            pass
        
        # Nombre décimal
        try:
            return float(val)
        except ValueError:
            pass
        
        # Autre (retourner tel quel)
        return val
    
    def _parse_where(self, where_clause: str) -> callable:
        """
        Parse une clause WHERE simple
        
        Exemple:
            id = 1
            name = 'Alice'
            age > 18
        """
        match = re.match(r'(\w+)\s*(=|>|<|>=|<=|!=)\s*(.+)', where_clause.strip())
        if not match:
            raise ValueError(f"Invalid WHERE clause: {where_clause}")
        
        col = match.group(1)
        op = match.group(2)
        val = self._parse_value(match.group(3))
        
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
    
    def _is_in_transaction(self) -> bool:
        """Vérifie si une transaction est active"""
        return (
            hasattr(self.dmonsql, 'transaction_manager') and
            self.dmonsql.transaction_manager and
            self.dmonsql.transaction_manager.is_in_transaction()
        )