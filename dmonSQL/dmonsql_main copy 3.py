"""
dmonSQL - Système de Gestion de Base de Données Relationnelle
Version 1.1.0 - Avec GROUP BY, Agrégations et ALTER TABLE
"""
import numpy as np
import re
import json
from datetime import datetime
from typing import Any, List, Dict
from pathlib import Path

# Imports des modules dmonSQL
from dmonSQL.data_types.matrixType import MatrixType
from dmonSQL.data_types.email_type import EmailType
from dmonSQL.data_types.json_type import JSONType
from dmonSQL.data_types.base_types import DataType
from dmonSQL.storage.file_manager import FileManager
from dmonSQL.storage.serializer import DatabaseSerializer
from dmonSQL.utils.logger import get_logger
from dmonSQL.utils.helpers import format_size, format_duration
from dmonSQL.query.parser import QueryParser
from dmonSQL.core.table import Table 
from dmonSQL.core.database import Database
from dmonSQL.core.column import Column

# Nouvelles fonctionnalités
from dmonSQL.query.aggregations import AggregationEngine

from dmonSQL.query.advanced_features import (
    execute_distinct, apply_limit_offset, SubqueryEngine,
    execute_union, execute_intersect, execute_except,
    parse_order_by, apply_order_by
)

from dmonSQL.query.p3_p4_features import (
    ViewManager, SequenceManager, QueryExplainer,
    StringFunctions, DateTimeFunctions, JSONFunctions,
    FullTextIndex
)

# Nouveau : Import du moteur d'agrégation
try:
    from dmonSQL.query.aggregations import AggregationEngine
    AGGREGATIONS_AVAILABLE = True
except ImportError:
    AGGREGATIONS_AVAILABLE = False

try:
    from dmonSQL.core.transaction_manager import TransactionManager
    TRANSACTIONS_AVAILABLE = True
except ImportError:
    TRANSACTIONS_AVAILABLE = False


class DmonSQL:
    """Système de gestion de base de données principal - Version améliorée"""
    
    def __init__(self, data_dir: str = "./dmonsql_data"):
        self.data_dir = Path(data_dir)
        self.databases = {}
        self.current_db = None
        
        # Initialiser les gestionnaires
        self.file_manager = FileManager(str(self.data_dir))
        self.serializer = DatabaseSerializer(self.file_manager)
        self.logger = get_logger("dmonSQL")
        self.parser = QueryParser()
        
        # Nouveau : Moteur d'agrégation
        if AGGREGATIONS_AVAILABLE:
            self.aggregation_engine = AggregationEngine()
            self.logger.info("Aggregation engine initialized")
        
        # Gestionnaires optionnels
        if TRANSACTIONS_AVAILABLE:
            self.transaction_manager = TransactionManager()
            self.logger.info("Transaction manager initialized")
        else:
            self.transaction_manager = None
            self.logger.warning("Transaction manager not available")
        
        # Charger les bases de données existantes
        self.load_databases()
        
        self.logger.info(f"dmonSQL initialized with data directory: {self.data_dir}")
        
        # === INITIALISATION DES GESTIONNAIRES P3/P4 ===
        self.aggregation_engine = AggregationEngine()
        self.subquery_engine = SubqueryEngine(self)
        self.view_manager = ViewManager(self)
        self.sequence_manager = SequenceManager()
        self.query_explainer = QueryExplainer(self)
        
        # Enregistrer les fonctions
        self.functions = {
            # String
            'CONCAT': StringFunctions.concat,
            'SUBSTRING': StringFunctions.substring,
            'UPPER': StringFunctions.upper,
            'LOWER': StringFunctions.lower,
            'TRIM': StringFunctions.trim,
            'LENGTH': StringFunctions.length,
            'REPLACE': StringFunctions.replace,
            
            # Date/Time
            'NOW': DateTimeFunctions.now,
            'CURDATE': DateTimeFunctions.curdate,
            'CURTIME': DateTimeFunctions.curtime,
            'DATE_ADD': DateTimeFunctions.date_add,
            'DATE_SUB': DateTimeFunctions.date_sub,
            'DATEDIFF': DateTimeFunctions.datediff,
            'DATE_FORMAT': DateTimeFunctions.date_format,
            'YEAR': DateTimeFunctions.year,
            'MONTH': DateTimeFunctions.month,
            'DAY': DateTimeFunctions.day,
            
            # JSON
            'JSON_EXTRACT': JSONFunctions.json_extract,
            'JSON_SET': JSONFunctions.json_set,
            'JSON_ARRAY': JSONFunctions.json_array,
            'JSON_OBJECT': JSONFunctions.json_object,
            'JSON_CONTAINS': JSONFunctions.json_contains,
        }

    # ==================== ALTER TABLE ====================
    
    def _execute_alter_table(self, sql: str, db: Database):
        sql_upper = sql.upper()
        """
        Exécute les commandes ALTER TABLE
        
        Syntaxes supportées:
        - ALTER TABLE table ADD COLUMN col_name data_type [constraints]
        - ALTER TABLE table DROP COLUMN col_name
        - ALTER TABLE table MODIFY COLUMN col_name new_type [constraints]
        - ALTER TABLE table RENAME COLUMN old_name TO new_name
        - ALTER TABLE table ADD CONSTRAINT name constraint_definition
        - ALTER TABLE table DROP CONSTRAINT name
        """
        # ADD COLUMN
        if 'ADD COLUMN' in sql_upper or 'ADD ' in sql_upper and 'COLUMN' in sql_upper:
            match = re.match(
                r'ALTER\s+TABLE\s+(\w+)\s+ADD\s+(?:COLUMN\s+)?(\w+)\s+(.+)',
                sql, re.IGNORECASE
            )
            if match:
                table_name = match.group(1)
                col_name = match.group(2)
                col_def = match.group(3)
                
                table = db.get_table(table_name)
                
                # Parser la définition de colonne
                column = self._parse_column_definition(col_name, col_def)
                
                # Extraire DEFAULT si présent
                default_value = None
                if 'DEFAULT' in col_def.upper():
                    default_match = re.search(r'DEFAULT\s+(.+?)(?:\s|$)', col_def, re.IGNORECASE)
                    if default_match:
                        default_value = self._parse_value(default_match.group(1).strip())
                
                table.add_column(column, default_value)
                
                if not (TRANSACTIONS_AVAILABLE and self.transaction_manager.is_in_transaction()):
                    self.save_database(self.current_db)
                
                print(f"✓ Column '{col_name}' added to table '{table_name}'")
                return
        
        # DROP COLUMN
        if 'DROP COLUMN' in sql_upper or 'DROP ' in sql_upper and 'COLUMN' in sql_upper:
            match = re.match(
                r'ALTER\s+TABLE\s+(\w+)\s+DROP\s+(?:COLUMN\s+)?(\w+)',
                sql, re.IGNORECASE
            )
            if match:
                table_name = match.group(1)
                col_name = match.group(2)
                
                table = db.get_table(table_name)
                table.drop_column(col_name)
                
                if not (TRANSACTIONS_AVAILABLE and self.transaction_manager.is_in_transaction()):
                    self.save_database(self.current_db)
                
                print(f"✓ Column '{col_name}' dropped from table '{table_name}'")
                return
        
        # MODIFY COLUMN
        if 'MODIFY COLUMN' in sql_upper or 'MODIFY ' in sql_upper:
            match = re.match(
                r'ALTER\s+TABLE\s+(\w+)\s+MODIFY\s+(?:COLUMN\s+)?(\w+)\s+(.+)',
                sql, re.IGNORECASE
            )
            if match:
                table_name = match.group(1)
                col_name = match.group(2)
                col_def = match.group(3)
                
                table = db.get_table(table_name)
                new_column = self._parse_column_definition(col_name, col_def)
                table.modify_column(col_name, new_column)
                
                if not (TRANSACTIONS_AVAILABLE and self.transaction_manager.is_in_transaction()):
                    self.save_database(self.current_db)
                
                print(f"✓ Column '{col_name}' modified in table '{table_name}'")
                return
        
        # RENAME COLUMN
        if 'RENAME COLUMN' in sql_upper:
            match = re.match(
                r'ALTER\s+TABLE\s+(\w+)\s+RENAME\s+COLUMN\s+(\w+)\s+TO\s+(\w+)',
                sql, re.IGNORECASE
            )
            if match:
                table_name = match.group(1)
                old_name = match.group(2)
                new_name = match.group(3)
                
                table = db.get_table(table_name)
                table.rename_column(old_name, new_name)
                
                if not (TRANSACTIONS_AVAILABLE and self.transaction_manager.is_in_transaction()):
                    self.save_database(self.current_db)
                
                print(f"✓ Column renamed in table '{table_name}': '{old_name}' -> '{new_name}'")
                return
        
        raise ValueError(f"Unsupported ALTER TABLE syntax: {sql}")
    
    def _parse_column_definition(self, col_name: str, col_def: str) -> Column:
        """Parse une définition de colonne pour ALTER TABLE"""
        parts = col_def.strip().split()
        
        dtype = parts[0].upper()
        length = None
        nullable = True
        primary_key = False
        auto_increment = False
        unique = False
        default = None
        
        # Extraire la longueur si présente
        if '(' in dtype:
            match = re.match(r'(\w+)\((\d+)\)', dtype)
            if match:
                dtype = match.group(1)
                length = int(match.group(2))
        
        # Parser les contraintes
        col_def_upper = col_def.upper()
        
        if 'NOT NULL' in col_def_upper:
            nullable = False
        
        if 'PRIMARY KEY' in col_def_upper:
            primary_key = True
            nullable = False
        
        if 'AUTO_INCREMENT' in col_def_upper:
            auto_increment = True
        
        if 'UNIQUE' in col_def_upper:
            unique = True
        
        if 'DEFAULT' in col_def_upper:
            default_match = re.search(r'DEFAULT\s+(.+?)(?:\s|$)', col_def, re.IGNORECASE)
            if default_match:
                default = self._parse_value(default_match.group(1).strip())
        
        return Column(
            name=col_name,
            dtype=dtype,
            length=length,
            nullable=nullable,
            primary_key=primary_key,
            auto_increment=auto_increment,
            unique=unique,
            default=default
        )
    
    def _parse_value(self, value_str: str) -> Any:
        """Parse une valeur depuis une chaîne"""
        value_str = value_str.strip()
        
        if value_str.upper() == 'NULL':
            return None
        
        if value_str.upper() in ('TRUE', 'FALSE'):
            return value_str.upper() == 'TRUE'
        
        if (value_str.startswith("'") and value_str.endswith("'")) or \
           (value_str.startswith('"') and value_str.endswith('"')):
            return value_str[1:-1]
        
        try:
            return int(value_str)
        except ValueError:
            try:
                return float(value_str)
            except ValueError:
                return value_str
        
    def _execute_select_with_group_by(self, sql: str, db: Database):
        """
        Exécute un SELECT avec GROUP BY et agrégations - Version finale corrigée
        """
        if not AGGREGATIONS_AVAILABLE:
            raise ValueError("Aggregation engine not available")
        
        sql_upper = sql.upper()
        
        # Pattern pour parser la requête
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
        
        # 1. Gérer FROM avec JOIN
        if 'JOIN' in from_clause.upper():
            # Exécuter le JOIN d'abord pour obtenir les données combinées
            join_sql = f"SELECT * FROM {from_clause}"
            if where_clause:
                join_sql += f" WHERE {where_clause}"
            
            # Récupérer les résultats du JOIN (avec préfixes u., o., etc.)
            rows = self._execute_select_with_join(join_sql, db)
            
            if not rows:
                print("\n🔭 Empty set (0.00 sec)")
                return []
        else:
            # Table simple
            table_name = from_clause.split()[0].strip()
            table = db.get_table(table_name)
            rows = table.rows
            
            if where_clause:
                where_func = self._parse_where(where_clause)
                rows = [row for row in rows if where_func(row)]
        
        # 2. Parser GROUP BY et mapper les colonnes avec préfixes
        # Exemple: "u.id, u.name" -> ["u.id", "u.name"]
        group_by_cols_with_prefix = [col.strip() for col in group_by_clause.split(',')]
        
        # 3. Parser SELECT et créer le mapping des colonnes
        select_parts = []
        alias_mapping = {}  # {alias: colonne_avec_prefix}
        reverse_mapping = {}  # {colonne_avec_prefix: alias}
        
        for expr in select_clause.split(','):
            expr = expr.strip()
            
            # Détection d'alias avec AS ou espace
            if ' AS ' in expr.upper():
                parts = re.split(r'\s+AS\s+', expr, 1, re.IGNORECASE)
                real_col = parts[0].strip()
                alias = parts[1].strip()
            elif ' ' in expr and not any(func in expr.upper() for func in ['COUNT', 'SUM', 'AVG', 'MIN', 'MAX', 'FROM', 'WHERE']):
                # Format: "u.id user_id" (sans AS)
                parts = expr.rsplit(' ', 1)
                if len(parts) == 2 and not parts[1].upper() in ['FROM', 'WHERE', 'GROUP', 'ORDER', 'DESC', 'ASC']:
                    real_col = parts[0].strip()
                    alias = parts[1].strip()
                else:
                    real_col = expr
                    alias = expr
            else:
                real_col = expr
                alias = expr
            
            # Stocker les mappings
            alias_mapping[alias] = real_col
            reverse_mapping[real_col] = alias
            
            # Construire l'expression pour l'agrégation
            if alias != real_col:
                select_parts.append(f"{real_col} AS {alias}")
            else:
                select_parts.append(real_col)
        
        # 4. Exécuter l'agrégation avec les vraies colonnes (avec préfixes)
        try:
            result = self.aggregation_engine.execute_group_by(
                rows, 
                select_parts, 
                group_by_cols_with_prefix
            )
        except Exception as e:
            self.logger.error(f"GROUP BY aggregation failed: {e}")
            raise
        
        # 5. Appliquer HAVING
        if having_clause:
            having_func = self._parse_having(having_clause)
            result = [row for row in result if having_func(row)]
        
        # 6. Appliquer ORDER BY
        if order_by_clause:
            order_parts = []
            for part in order_by_clause.split(','):
                part = part.strip()
                if ' ' in part:
                    col, direction = part.rsplit(' ', 1)
                    order_parts.append((col.strip(), direction.strip().upper()))
                else:
                    order_parts.append((part, 'ASC'))
            
            # Trier par ordre inverse pour que le premier critère soit prioritaire
            for col, direction in reversed(order_parts):
                reverse = direction == 'DESC'
                
                # Vérifier si c'est un alias
                if col in alias_mapping:
                    # Utiliser l'alias directement (déjà dans le résultat)
                    sort_key = col
                else:
                    sort_key = col
                
                result = sorted(
                    result, 
                    key=lambda x: (x.get(sort_key) is None, x.get(sort_key) or 0), 
                    reverse=reverse
                )
        
        # 7. Appliquer LIMIT
        if limit_clause:
            result = result[:int(limit_clause)]
        
        self._print_result(result)
        return result
    def _print_result_advanced(self, result: List[Dict]):
        """Affiche le résultat avec des bordures ASCII avancées"""
        if not result:
            print("\n╔════════════════════════════════════════════╗")
            print("║               EMPTY SET                    ║")
            print("║          0 row in set (0.000 sec)          ║")
            print("╚════════════════════════════════════════════╝")
            return
        
        columns = list(result[0].keys())
        
        # Calcul des largeurs
        col_widths = {}
        for col in columns:
            header_len = len(str(col))
            content_len = max(len(self._format_display_value(row.get(col))) 
                            for row in result[:100])  # Échantillon pour la performance
            col_widths[col] = min(max(header_len, content_len, 8), 30)
        
        # Construction du tableau
        top_border = "╔" + "╦".join("═" * (col_widths[col] + 2) for col in columns) + "╗"
        header_line = "║ " + " ║ ".join(f"{col:<{col_widths[col]}}" for col in columns) + " ║"
        middle_border = "╠" + "╬".join("═" * (col_widths[col] + 2) for col in columns) + "╣"
        bottom_border = "╚" + "╩".join("═" * (col_widths[col] + 2) for col in columns) + "╝"
        
        print(f"\n{top_border}")
        print(header_line)
        print(middle_border)
        
        # Données
        for i, row in enumerate(result[:100]):  # Limite à 100 lignes
            values = []
            for col in columns:
                value = self._format_display_value(row.get(col))
                if len(value) > col_widths[col]:
                    value = value[:col_widths[col] - 3] + "..."
                values.append(f"{value:<{col_widths[col]}}")
            
            data_line = "║ " + " ║ ".join(values) + " ║"
            print(data_line)
        
        print(bottom_border)
        
        # Informations
        total_rows = len(result)
        if total_rows > 100:
            print(f"╔════════════════════════════════════════════╗")
            print(f"║ Showing first 100 of {total_rows:>6} rows           ║")
            print(f"╚════════════════════════════════════════════╝")
        
        print(f"{total_rows} row{'s' if total_rows != 1 else ''} in set (0.000 sec)\n")
        
    def _parse_having(self, having_clause: str) -> callable:
        """Parse une clause HAVING (similaire à WHERE mais sur les résultats agrégés)"""
        # Pattern: col operator value
        match = re.match(r'(\w+)\s*(=|>|<|>=|<=|!=)\s*(.+)', having_clause.strip())
        if not match:
            raise ValueError("Invalid HAVING clause")
        
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
        
        # Créer la fonction de filtrage
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
    
    def create_database(self, name: str):
        """Crée une base de données"""
        if name in self.databases:
            raise ValueError(f"Database {name} already exists")
        
        db = Database(name)
        self.databases[name] = db
        self.save_database(name)
        
        self.logger.info(f"Database '{name}' created")
    
    def drop_database(self, name: str):
        """Supprime une base de données"""
        if name not in self.databases:
            raise ValueError(f"Database {name} does not exist")
        
        del self.databases[name]
        self.file_manager.delete_database(name)
        
        self.logger.info(f"Database '{name}' dropped")
    
    def use_database(self, name: str):
        """Sélectionne une base de données"""
        if name not in self.databases:
            raise ValueError(f"Database {name} does not exist")
        
        self.current_db = name
        
        # Restaurer les références database pour toutes les tables
        db = self.databases[name]
        for table_name, table in db.tables.items():
            if not hasattr(table, 'database') or table.database is None:
                table.database = db
            if not hasattr(table, 'foreign_keys'):
                table.foreign_keys = []
        
        print(f"✓ Using database '{name}'")
    
    def execute(self, sql: str) -> Any:
        """Exécute une requête SQL avec logging"""
        sql = sql.strip()
        start_time = datetime.now()
        
        try:
            result = self._execute_internal(sql)
            duration = (datetime.now() - start_time).total_seconds()
            self.logger.debug(f"Query executed in {format_duration(duration)}: {sql[:50]}...")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Query failed: {sql[:50]}... - Error: {e}")
            raise
    
    def _execute_internal(self, sql: str) -> Any:
        """Exécution interne des requêtes"""
        sql_upper = sql.upper()
        
            # ==================== NOUVEAUX SUPPORTS ====================
    
        # CREATE VIEW
        if sql_upper.startswith('CREATE VIEW'):
            return self._execute_create_view(sql)
        
        # DROP VIEW
        if sql_upper.startswith('DROP VIEW'):
            return self._execute_drop_view(sql)
        
        # EXPLAIN / EXPLAIN ANALYZE
        if sql_upper.startswith('EXPLAIN'):
            return self._execute_explain(sql)
        
        # SHOW VIEWS
        if sql_upper == 'SHOW VIEWS':
            return self._execute_show_views()
        
        # ... [VOTRE CODE EXISTANT POUR CREATE DATABASE, USE, etc.] ...

        # CREATE DATABASE
        if sql_upper.startswith('CREATE DATABASE'):
            match = re.match(r'CREATE\s+DATABASE\s+(\w+)', sql, re.IGNORECASE)
            if match:
                self.create_database(match.group(1))
                return
        
        # DROP DATABASE
        if sql_upper.startswith('DROP DATABASE'):
            match = re.match(r'DROP\s+DATABASE\s+(\w+)', sql, re.IGNORECASE)
            if match:
                self.drop_database(match.group(1))
                return
        
        # USE DATABASE
        if sql_upper.startswith('USE'):
            match = re.match(r'USE\s+(\w+)', sql, re.IGNORECASE)
            if match:
                self.use_database(match.group(1))
                return
        
        # ⭐ TRANSACTIONS (AVANT vérification current_db)
        if TRANSACTIONS_AVAILABLE:
            # BEGIN TRANSACTION
            if sql_upper in ('BEGIN TRANSACTION', 'BEGIN', 'START TRANSACTION'):
                if not self.current_db:
                    raise ValueError("No database selected")
                db = self.databases[self.current_db]
                self.transaction_manager.begin_transaction(db)
                print("✓ Transaction started")
                return
            
            # COMMIT
            if sql_upper == 'COMMIT':
                if not self.transaction_manager.is_in_transaction():
                    raise ValueError("No active transaction")
                db = self.databases[self.current_db]
                self.transaction_manager.commit_transaction(db)
                # Sauvegarder après COMMIT
                self.save_database(self.current_db)
                print("✓ Transaction committed")
                return
            
            # ROLLBACK
            if sql_upper == 'ROLLBACK':
                if not self.transaction_manager.is_in_transaction():
                    raise ValueError("No active transaction")
                db = self.databases[self.current_db]
                self.transaction_manager.rollback_transaction(db)
                print("✓ Transaction rolled back")
                return
        
        # Vérifier qu'une base est sélectionnée
        if not self.current_db:
            raise ValueError("No database selected. Use 'USE database_name'")
        
        db = self.databases[self.current_db]
        
        # SELECT avec fonctions et sous-requêtes amélioré
        if sql_upper.startswith('SELECT'):
            return self._execute_select_enhanced(sql, db)

        # CREATE TABLE
        if sql_upper.startswith('CREATE TABLE'):
            result = self.parser.parse_create_table(sql)
            
            if len(result) == 3:
                table_name, columns, foreign_keys = result
            else:
                table_name, columns = result
                foreign_keys = []
            
            table = Table(table_name, columns)
            
            # Ajouter les contraintes de clé étrangère
            for fk in foreign_keys:
                table.add_foreign_key(
                    column=fk['column'],
                    ref_table=fk['ref_table'],
                    ref_column=fk['ref_column'],
                    on_delete=fk.get('on_delete', 'RESTRICT'),
                    on_update=fk.get('on_update', 'RESTRICT')
                )
            
            # Lier la table à la base de données
            table.database = db
            
            db.create_table(table)
            
            if not (TRANSACTIONS_AVAILABLE and self.transaction_manager.is_in_transaction()):
                self.save_database(self.current_db)
            
            if foreign_keys:
                print(f"✓ Table '{table_name}' created with {len(foreign_keys)} foreign key(s)")
            else:
                print(f"✓ Table '{table_name}' created successfully")
            return
        
        # DROP TABLE
        if sql_upper.startswith('DROP TABLE'):
            match = re.match(r'DROP\s+TABLE\s+(\w+)', sql, re.IGNORECASE)
            if match:
                table_name = match.group(1)
                db.drop_table(table_name)
                
                if not (TRANSACTIONS_AVAILABLE and self.transaction_manager.is_in_transaction()):
                    self.save_database(self.current_db)
                
                print(f"✓ Table '{table_name}' dropped successfully")
                return
        
        # CREATE INDEX
        if sql_upper.startswith('CREATE INDEX'):
            match = re.match(r'CREATE\s+(?:UNIQUE\s+)?INDEX\s+(\w+)\s+ON\s+(\w+)\s*\((.*?)\)', 
                           sql, re.IGNORECASE)
            if match:
                index_name = match.group(1)
                table_name = match.group(2)
                columns = [c.strip() for c in match.group(3).split(',')]
                unique = 'UNIQUE' in sql_upper
                
                table = db.get_table(table_name)
                table.create_index(index_name, columns, unique)
                
                if not (TRANSACTIONS_AVAILABLE and self.transaction_manager.is_in_transaction()):
                    self.save_database(self.current_db)
                
                print(f"✓ Index '{index_name}' created successfully")
                return
            
        # INSERT
        if sql_upper.startswith('INSERT'):
            insert_pattern = r"INSERT\s+INTO\s+(\w+)\s*\(([^)]+)\)\s*VALUES\s*((?:\([^)]*\)(?:\s*,\s*\([^)]*\))*)\s*)"
            match = re.match(insert_pattern, sql, re.IGNORECASE | re.DOTALL)
            if not match:
                raise ValueError("Invalid INSERT syntax")

            table_name = match.group(1).strip()
            columns_str = match.group(2)
            values_str = match.group(3)

            table = db.get_table(table_name)
            columns = [c.strip() for c in columns_str.split(",")]
            value_tuples = re.findall(r"\(([^)]*)\)", values_str)
            
            if not value_tuples:
                raise ValueError("No VALUES found in INSERT statement")

            inserted_count = 0
            for value_tuple in value_tuples:
                raw_values = [v.strip() for v in value_tuple.split(",")]
                if len(raw_values) != len(columns):
                    raise ValueError(f"Column count mismatch: expected {len(columns)}, got {len(raw_values)}")

                values = []
                for val in raw_values:
                    val = val.strip()
                    if val.upper() == 'NULL':
                        values.append(None)
                    elif (val.startswith("'") and val.endswith("'")) or (val.startswith('"') and val.endswith('"')):
                        values.append(val[1:-1])
                    else:
                        try:
                            values.append(int(val))
                        except ValueError:
                            try:
                                values.append(float(val))
                            except ValueError:
                                values.append(val)

                values_dict = dict(zip(columns, values))
                
                # ✅ INSERTION ICI - À L'INTÉRIEUR DE LA BOUCLE
                table.insert(values_dict)
                inserted_count += 1

                # Logger dans la transaction si active
                if TRANSACTIONS_AVAILABLE and self.transaction_manager.is_in_transaction():
                    self.transaction_manager.log_operation('INSERT', table_name, values_dict)

            # SAUVEGARDE uniquement si pas en transaction
            if not (TRANSACTIONS_AVAILABLE and self.transaction_manager.is_in_transaction()):
                self.save_database(self.current_db)
            
            print(f"✓ Inserted {inserted_count} row(s)")
            return inserted_count
        # INSERT
        # if sql_upper.startswith('INSERT'):
        #     insert_pattern = r"INSERT\s+INTO\s+(\w+)\s*\(([^)]+)\)\s*VALUES\s*((?:\([^)]*\)(?:\s*,\s*\([^)]*\))*)\s*)"
        #     match = re.match(insert_pattern, sql, re.IGNORECASE | re.DOTALL)
        #     if not match:
        #         raise ValueError("Invalid INSERT syntax")

        #     table_name = match.group(1).strip()
        #     columns_str = match.group(2)
        #     values_str = match.group(3)

        #     table = db.get_table(table_name)
        #     columns = [c.strip() for c in columns_str.split(",")]
        #     value_tuples = re.findall(r"\(([^)]*)\)", values_str)
            
        #     if not value_tuples:
        #         raise ValueError("No VALUES found in INSERT statement")

        #     inserted_count = 0
        #     for value_tuple in value_tuples:
        #         raw_values = [v.strip() for v in value_tuple.split(",")]
        #         if len(raw_values) != len(columns):
        #             raise ValueError(f"Column count mismatch: expected {len(columns)}, got {len(raw_values)}")

        #         values = []
        #         for val in raw_values:
        #             val = val.strip()
        #             if val.upper() == 'NULL':
        #                 values.append(None)
        #             elif (val.startswith("'") and val.endswith("'")) or (val.startswith('"') and val.endswith('"')):
        #                 values.append(val[1:-1])
        #             else:
        #                 try:
        #                     values.append(int(val))
        #                 except ValueError:
        #                     try:
        #                         values.append(float(val))
        #                     except ValueError:
        #                         values.append(val)

        #         values_dict = dict(zip(columns, values))

        #     # Logger dans la transaction si active
        #     if TRANSACTIONS_AVAILABLE and self.transaction_manager.is_in_transaction():
        #         self.transaction_manager.log_operation('INSERT', table_name, values_dict)

        #     # SAUVEGARDE uniquement si pas en transaction
        #     if not (TRANSACTIONS_AVAILABLE and self.transaction_manager.is_in_transaction()):
        #         self.save_database(self.current_db)
            
        #     print(f"Inserted {inserted_count} row(s)")
        #     return inserted_count
        
        # SELECT
        # if sql_upper.startswith('SELECT'):
        #     return self._execute_select(sql, db)
        
        # UPDATE
        if sql_upper.startswith('UPDATE'):
            return self._execute_update(sql, db)
        
        # DELETE
        if sql_upper.startswith('DELETE'):
            match = re.match(r'DELETE\s+FROM\s+(\w+)(?:\s+WHERE\s+(.*))?', sql, re.IGNORECASE)
            if not match:
                raise ValueError("Invalid DELETE syntax")
            
            table_name = match.group(1)
            where_clause = match.group(2)
            table = db.get_table(table_name)
            where_func = self._parse_where(where_clause) if where_clause else None
            
            count = table.delete(where=where_func)
            
            # Logger dans la transaction si active
            if TRANSACTIONS_AVAILABLE and self.transaction_manager.is_in_transaction():
                self.transaction_manager.log_operation('DELETE', table_name, where_clause)
            
            # SAUVEGARDE uniquement si pas en transaction
            if not (TRANSACTIONS_AVAILABLE and self.transaction_manager.is_in_transaction()):
                self.save_database(self.current_db)
            
            print(f"Deleted {count} row(s)")
            return count
        
        # SHOW STATS
        if sql_upper == 'SHOW STATS':
            self._show_statistics(db)
            return
        
        raise ValueError(f"Unsupported SQL statement: {sql}")
    
    def _execute_select(self, sql: str, db: Database):        
        """Exécute un SELECT (avec ou sans JOIN, GROUP BY, HAVING)"""
        sql_upper = sql.upper()
        
        # Vérifier s'il y a un GROUP BY
        if ' GROUP BY ' in sql_upper:
            return self._execute_select_with_group_by(sql, db)
        
        # Vérifier s'il y a un JOIN
        if ' JOIN ' in sql_upper:
            return self._execute_select_with_join(sql, db)
        # Vérifier s'il y a un JOIN
        if ' JOIN ' in sql_upper:
            return self._execute_select_with_join(sql, db)
        
        # SELECT simple
        match = re.match(r'SELECT\s+(.*?)\s+FROM\s+(\w+)(?:\s+WHERE\s+(.*))?', 
                        sql, re.IGNORECASE)
        if not match:
            raise ValueError("Invalid SELECT syntax")
        
        columns_str = match.group(1).strip()
        table_name = match.group(2)
        where_clause = match.group(3)
        
        table = db.get_table(table_name)
        # try:
        #     table = db.get_table_or_view(table_name, self)
        # except ValueError:
        #     table = db.get_table(table_name)

        columns = None if columns_str == '*' else [c.strip() for c in columns_str.split(',')]
        
        where_func = None
        if where_clause:
            where_func = self._parse_where(where_clause)
        
        result = table.select(columns=columns, where=where_func)
        self._print_result_advanced(result)
        return result

    def _execute_select_with_join(self, sql: str, db: Database):
        """Exécute un SELECT avec JOIN"""
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
        
        table1 = db.get_table(table1_name)
        table2 = db.get_table(table2_name)
        
        col1 = join_col1.split('.')[-1] if '.' in join_col1 else join_col1
        col2 = join_col2.split('.')[-1] if '.' in join_col2 else join_col2
        
        if join_type in ('JOIN', 'INNER JOIN'):
            result = self._inner_join(table1, table2, col1, col2, table1_alias, table2_alias)
        elif join_type == 'LEFT JOIN':
            result = self._left_join(table1, table2, col1, col2, table1_alias, table2_alias)
        elif join_type == 'RIGHT JOIN':
            result = self._right_join(table1, table2, col1, col2, table1_alias, table2_alias)
        else:
            raise ValueError(f"Unsupported join type: {join_type}")
        
        if where_clause:
            where_func = self._parse_where_join(where_clause)
            result = [row for row in result if where_func(row)]
        
        if columns_str.strip() != '*':
            requested_cols = [c.strip() for c in columns_str.split(',')]
            result = self._project_columns(result, requested_cols)
        
        self._print_result(result)
        return result

    def _inner_join(self, table1: Table, table2: Table, col1: str, col2: str, 
                    alias1: str, alias2: str) -> List[Dict]:
        """INNER JOIN"""
        result = []
        for row1 in table1.rows:
            for row2 in table2.rows:
                val1 = row1.get(col1)
                val2 = row2.get(col2)
                
                if val1 is not None and val1 == val2:
                    combined = {}
                    for k, v in row1.items():
                        combined[f"{alias1}.{k}"] = v
                    for k, v in row2.items():
                        combined[f"{alias2}.{k}"] = v
                    result.append(combined)
        return result

    def _left_join(self, table1: Table, table2: Table, col1: str, col2: str,
                   alias1: str, alias2: str) -> List[Dict]:
        """LEFT JOIN"""
        result = []
        for row1 in table1.rows:
            matched = False
            for row2 in table2.rows:
                if row1.get(col1) == row2.get(col2):
                    combined = {}
                    for k, v in row1.items():
                        combined[f"{alias1}.{k}"] = v
                    for k, v in row2.items():
                        combined[f"{alias2}.{k}"] = v
                    result.append(combined)
                    matched = True
            
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
        """RIGHT JOIN"""
        return self._left_join(table2, table1, col2, col1, alias2, alias1)

    def _parse_where_join(self, where_clause: str) -> callable:
        """Parse WHERE pour JOIN"""
        match = re.match(r'([\w.]+)\s*(=|>|<|>=|<=|!=|<>)\s*(.+)', where_clause.strip())
        if not match:
            raise ValueError("Invalid WHERE clause")
        
        col = match.group(1).strip()
        op = match.group(2)
        val = match.group(3).strip()
        
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

    def _project_columns(self, rows: List[Dict], columns: List[str]) -> List[Dict]:
        """Projection de colonnes"""
        if not rows:
            return []
        
        result = []
        for row in rows:
            projected = {}
            for col in columns:
                col = col.strip()
                value = None
                
                if col in row:
                    value = row[col]
                else:
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
    
    def _execute_update(self, sql: str, db: Database):
        """UPDATE"""
        match = re.match(r'UPDATE\s+(\w+)\s+SET\s+(.*?)(?:\s+WHERE\s+(.*))?$', 
                        sql, re.IGNORECASE)
        if not match:
            raise ValueError("Invalid UPDATE syntax")
        
        table_name = match.group(1)
        set_clause = match.group(2)
        where_clause = match.group(3)
        
        table = db.get_table(table_name)
        
        values = {}
        assignments = re.findall(r"(\w+)\s*=\s*('[^']*'|\"[^\"]*\"|\S+)", set_clause)
        
        for col, val in assignments:
            col = col.strip()
            val = val.strip()
            if (val.startswith("'") and val.endswith("'")) or \
               (val.startswith('"') and val.endswith('"')):
                val = val[1:-1]
            values[col] = val
        
        if not values:
            raise ValueError("No valid SET assignments found")
        
        where_func = None
        if where_clause:
            where_func = self._parse_where(where_clause)
        
        count = table.update(values, where=where_func)
        
        # Logger dans la transaction si active
        if TRANSACTIONS_AVAILABLE and self.transaction_manager.is_in_transaction():
            self.transaction_manager.log_operation('UPDATE', table_name, values)
        
        # SAUVEGARDE uniquement si pas en transaction
        if not (TRANSACTIONS_AVAILABLE and self.transaction_manager.is_in_transaction()):
            self.save_database(self.current_db)
        
        print(f"✓ {count} row(s) updated")
        return count
    
    def _parse_where(self, where_clause: str) -> callable:
        """Parse WHERE simple"""
        match = re.match(r'(\w+)\s*(=|>|<|>=|<=|!=)\s*(.+)', where_clause.strip())
        if not match:
            raise ValueError("Invalid WHERE clause")
        
        col = match.group(1)
        op = match.group(2)
        val = match.group(3).strip().strip("'\"")
        
        try:
            val = int(val)
        except:
            try:
                val = float(val)
            except:
                pass
        
        if op == '=':
            return lambda row: row.get(col) == val
        elif op == '>':
            return lambda row: row.get(col) > val
        elif op == '<':
            return lambda row: row.get(col) < val
        elif op == '>=':
            return lambda row: row.get(col) >= val
        elif op == '<=':
            return lambda row: row.get(col) <= val
        elif op == '!=':
            return lambda row: row.get(col) != val
    
    # def _print_result(self, result: List[Dict]):
    #     """Affiche résultat formaté"""
    #     if not result:
    #         print("\n🔭 Empty set (0 rows)")
    #         return
        
    #     columns = list(result[0].keys())
    #     col_widths = {col: max(len(col), 15) for col in columns}
        
    #     for row in result[:10]:
    #         for col in columns:
    #             val = str(row.get(col, ''))[:50]
    #             col_widths[col] = max(col_widths[col], len(val))
        
    #     header = " | ".join(f"{col:<{col_widths[col]}}" for col in columns)
    #     print(f"\n{header}")
    #     print("-" * len(header))
        
    #     for row in result:
    #         values = []
    #         for col in columns:
    #             val = row.get(col)
    #             if isinstance(val, MatrixType):
    #                 val_str = f"Matrix{val.shape}"
    #             elif isinstance(val, JSONType):
    #                 val_str = str(val)[:50]
    #             elif isinstance(val, EmailType):
    #                 val_str = str(val)
    #             else:
    #                 val_str = str(val) if val is not None else "NULL"
                
    #             values.append(val_str[:col_widths[col]])
            
    #         print(" | ".join(f"{val:<{col_widths[col]}}" for val in values))
        
    #     print(f"\n✓ {len(result)} row(s) in set\n")
    
    def _show_statistics(self, db):
        """Affiche les statistiques de la base avec le nouveau style"""
        stats = db.get_statistics()
        
        print(f"\n╔══════════════════════════════════════════════════════════════╗")
        print(f"║         📊 Database Statistics: {db.name:<24}     ║")
        print(f"╠══════════════════════════════════════════════════════════════╣")
        print(f"║  Tables:         {stats['tables']:<40}    ║")
        print(f"║  Total rows:     {stats['total_rows']:<40,}   ║")
        print(f"║  Total indexes:  {stats['total_indexes']:<40}     ║")
        print(f"║  Created:        {stats['created_at'][:19]:<40}   ║")
        print(f"║  Last modified:  {stats['last_modified'][:19]:<40}    ║")
        
        db_size = self.file_manager.get_database_size(db.name)
        if db_size > 0:
            from dmonSQL.utils.helpers import format_size
            print(f"║  Size on disk:   {format_size(db_size):<40}   ║")
        
        print(f"╠══════════════════════════════════════════════════════════════╣")
        print(f"║  Tables Overview:                                            ║")
        print(f"╠══════════════════════════════════════════════════════════════╣")
        
        for table_name, table in db.tables.items():
            table_stats = table.get_statistics()
            rows_str = f"{table_stats['rows']} rows"
            indexes_str = f"{table_stats['indexes']} indexes"
            print(f"║    • {table_name:<20} {rows_str:<15} {indexes_str:<15} ║")
        
        print(f"╚══════════════════════════════════════════════════════════════╝\n")


    
    def save_database(self, db_name: str):
        """Sauvegarde une base de données"""
        if db_name not in self.databases:
            return
        
        try:
            self.serializer.save_database(db_name, self.databases[db_name])
            self.logger.debug(f"Database '{db_name}' saved")
        except Exception as e:
            self.logger.error(f"Failed to save database '{db_name}': {e}")
            raise
    
    def load_databases(self):
        """Charge toutes les bases de données"""
        db_names = self.file_manager.list_databases()
        
        for db_name in db_names:
            try:
                db = self.serializer.load_database(db_name)
                self.databases[db_name] = db
                
                # Restaurer les références
                for table_name, table in db.tables.items():
                    table.database = db
                    if not hasattr(table, 'foreign_keys'):
                        table.foreign_keys = []
                
                self.logger.debug(f"Database '{db_name}' loaded")
            except Exception as e:
                self.logger.warning(f"Could not load database '{db_name}': {e}")

    def show_databases(self):
        """Affiche les bases de données avec le nouveau style"""
        if not self.databases:
            print("\n╔═════════════════════════════════════════════╗")
            print("║         🔭 No databases found              ║")
            print("╚════════════════════════════════════════════╝")
            return
        
        print(f"\n╔══════════════════════════════════════════════════════════════════════╗")
        print(f"║                   📚 Databases ({len(self.databases)})                         ║")
        print(f"╠══════════════════════════════════════════════════════════════════════╣")
        
        from dmonSQL.utils.helpers import format_size
        
        for db_name in sorted(self.databases.keys()):
            current = "◀" if db_name == self.current_db else " "
            db_size = self.file_manager.get_database_size(db_name)
            size_str = format_size(db_size) if db_size > 0 else "N/A"
            
            db = self.databases[db_name]
            table_count = len(db.tables)
            
            # Formater la ligne
            name_part = f"{current} {db_name}"
            info_part = f"({table_count} tables, {size_str})"
            
            # Calculer les espaces pour aligner
            padding = 68 - len(name_part) - len(info_part)
            
            print(f"║  {name_part}{' ' * padding}{info_part}  ║")
        
        print(f"╚══════════════════════════════════════════════════════════════════════╝\n")

    
    def show_tables(self):
        """Affiche les tables avec le nouveau style"""
        if not self.current_db:
            print("\n╔════════════════════════════════════════════╗")
            print("║  ⚠️  No database selected                  ║")
            print("╚════════════════════════════════════════════╝")
            return
        
        db = self.databases[self.current_db]
        
        if not db.tables:
            print(f"\n╔════════════════════════════════════════════════════════╗")
            print(f"║  🔭 No tables in database '{self.current_db}'")
            print(f"╚════════════════════════════════════════════════════════╝")
            return
        
        from dmonSQL.utils.helpers import format_size
        
        print(f"\n╔═══════════════════════════════════════════════════════════════════════════════════╗")
        print(f"║            📊 Tables in '{self.current_db}' ({len(db.tables)})                          ")
        print(f"╠═══════════════╦══════════╦══════════╦══════════╦═══════════════════════════════════╣")
        print(f"║ Table         ║ Rows     ║ Columns  ║ Indexes  ║ Size (est.)                       ║")
        print(f"╠═══════════════╬══════════╬══════════╬══════════╬═══════════════════════════════════╣")
        
        for table_name in sorted(db.tables.keys()):
            table = db.tables[table_name]
            stats = table.get_statistics()
            
            size_str = format_size(stats['size_estimate'])
            
            print(f"║ {table_name:<13} ║ {stats['rows']:<8} ║ {stats['columns']:<8} ║ {stats['indexes']:<8} ║ {size_str:<33} ║")
        
        print(f"╚═══════════════╩══════════╩══════════╩══════════╩═══════════════════════════════════╝\n")


    def _execute_create_view(self, sql: str):
        """Exécute CREATE VIEW"""
        if not self.current_db:
            raise ValueError("No database selected")
        
        # Pattern: CREATE VIEW name AS SELECT ...
        pattern = r'CREATE\s+VIEW\s+(\w+)\s+(?:AS\s+)?(.*)'
        match = re.match(pattern, sql, re.IGNORECASE | re.DOTALL)
        
        if not match:
            raise ValueError("Invalid CREATE VIEW syntax")
        
        view_name = match.group(1)
        view_query = match.group(2).strip()
        
        # Créer la vue
        self.view_manager.create_view(view_name, view_query)
        print(f"✓ View '{view_name}' created")

    def _execute_drop_view(self, sql: str):
        """Exécute DROP VIEW"""
        match = re.match(r'DROP\s+VIEW\s+(\w+)', sql, re.IGNORECASE)
        if not match:
            raise ValueError("Invalid DROP VIEW syntax")
        
        view_name = match.group(1)
        self.view_manager.drop_view(view_name)
        print(f"✓ View '{view_name}' dropped")

    def _execute_show_views(self):
        """Affiche les vues disponibles"""
        views = self.view_manager.list_views()
        
        if not views:
            print("\n🔭 No views found")
            return
        
        print(f"\n👁️  Views ({len(views)}):")
        print("-" * 40)
        for view_name in views:
            view = self.view_manager.views[view_name]
            print(f"  • {view_name}")
            print(f"    Query: {view.query[:50]}...")
        print("-" * 40)

    def _execute_explain(self, sql: str):
        """Exécute EXPLAIN et EXPLAIN ANALYZE"""
        analyze = 'ANALYZE' in sql.upper()
        
        # Extraire la requête à expliquer
        if analyze:
            query = sql.replace('EXPLAIN ANALYZE', '').strip()
        else:
            query = sql.replace('EXPLAIN', '').strip()
        
        plan = self.query_explainer.explain(query, analyze=analyze)
        self.query_explainer.print_plan(plan)
        return plan

    def _execute_select_enhanced(self, sql: str, db: Database):
        """SELECT amélioré avec fonctions et sous-requêtes"""
        sql_upper = sql.upper()
        
        # Vérifier les sous-requêtes complexes d'abord
        if any(keyword in sql_upper for keyword in [' IN (SELECT', ' > (SELECT', ' EXISTS (SELECT']):
            try:
                return self.subquery_engine.parse_and_execute_with_subquery(sql)
            except Exception as e:
                # Fallback sur le SELECT normal si échec
                self.logger.warning(f"Subquery failed, falling back to normal SELECT: {e}")
        
        # Vérifier GROUP BY
        if ' GROUP BY ' in sql_upper:
            return self._execute_select_with_group_by(sql, db)
        
        # Vérifier JOIN
        if ' JOIN ' in sql_upper:
            return self._execute_select_with_join(sql, db)
        
        # SELECT simple avec fonctions
        return self._execute_select_with_functions(sql, db)

    def _execute_select_with_functions(self, sql: str, db: Database):
        """SELECT avec support des fonctions (JSON, Date, String)"""
        # D'abord, essayer de parser avec les fonctions
        try:
            # Extraire la clause SELECT
            select_match = re.match(r'SELECT\s+(.*?)\s+FROM\s+(\w+)', sql, re.IGNORECASE | re.DOTALL)
            if not select_match:
                raise ValueError("Invalid SELECT syntax")
            
            columns_str = select_match.group(1).strip()
            table_name = select_match.group(2)
            
            # Vérifier si des fonctions sont utilisées
            has_functions = any(func in columns_str.upper() for func in [
                'JSON_EXTRACT', 'DATE_', 'CONCAT', 'SUBSTRING', 'UPPER', 'LOWER'
            ])
            
            if not has_functions:
                return self._execute_select(sql, db)
            
            result = self._execute_select(sql, db)
            if not result:
                return result
            
            # Appliquer les fonctions sur le résultat
            return self._apply_functions_to_result(result, columns_str)
            
        except Exception as e:
            # Fallback sur SELECT normal
            self.logger.warning(f"Function processing failed: {e}")
            return self._execute_select(sql, db)

    def _apply_functions_to_result(self, result: List[Dict], columns_str: str) -> List[Dict]:
        """Applique les fonctions aux résultats d'un SELECT"""
        if not result:
            return result
        
        # Parser les expressions de colonnes
        column_exprs = [expr.strip() for expr in columns_str.split(',')]
        
        new_result = []
        
        for row in result:
            new_row = {}
            
            for expr in column_exprs:
                # Gérer les alias
                if ' AS ' in expr.upper():
                    expr_parts = expr.split(' AS ')
                    expr_clean = expr_parts[0].strip()
                    alias = expr_parts[1].strip()
                else:
                    expr_clean = expr
                    alias = expr
                
                # Appliquer les fonctions
                value = self._evaluate_expression(expr_clean, row)
                new_row[alias] = value
            
            new_result.append(new_row)
        
        return new_result

    def _evaluate_expression(self, expr: str, row: Dict) -> Any:
        """Évalue une expression avec fonctions"""
        expr = expr.strip()
        
        # JSON_EXTRACT
        if 'JSON_EXTRACT(' in expr.upper():
            match = re.match(r'JSON_EXTRACT\s*\(\s*(\w+)\s*,\s*([^)]+)\s*\)', expr, re.IGNORECASE)
            if match:
                column = match.group(1)
                path = match.group(2).strip().strip("'\"")
                json_data = row.get(column, '{}')
                return JSONFunctions.json_extract(json_data, path)
        
        # DATE functions
        elif 'DATE_ADD(' in expr.upper():
            match = re.match(r'DATE_ADD\s*\(\s*(\w+)\s*,\s*(\d+)\s*,\s*[\'"]([^\'"]+)[\'"]\s*\)', expr, re.IGNORECASE)
            if match:
                column = match.group(1)
                interval = int(match.group(2))
                unit = match.group(3)
                date_value = row.get(column)
                if date_value:
                    return DateTimeFunctions.date_add(date_value, interval, unit)
        
        elif 'DATEDIFF(' in expr.upper():
            match = re.match(r'DATEDIFF\s*\(\s*(\w+)\s*,\s*(\w+)\s*\)', expr, re.IGNORECASE)
            if match:
                date1 = row.get(match.group(1))
                date2 = row.get(match.group(2))
                if date1 and date2:
                    return DateTimeFunctions.datediff(date1, date2)
        
        # String functions
        elif 'CONCAT(' in expr.upper():
            # Implémentation simplifiée de CONCAT
            parts = expr[7:-1].split(',')  # Extraire les parties entre CONCAT( et )
            values = []
            for part in parts:
                part = part.strip().strip("'\"")
                values.append(row.get(part, part))
            return ''.join(str(v) for v in values)
        
        # NOW() function
        elif expr.upper() == 'NOW()':
            return DateTimeFunctions.now()
        
        # CURDATE() function  
        elif expr.upper() == 'CURDATE()':
            return DateTimeFunctions.curdate()
        
        # Colonne normale
        else:
            return row.get(expr)
        
        return row.get(expr)  # Fallback

    def _print_result(self, result: List[Dict]):
        """
        Affiche le résultat avec des bordures Unicode doubles élégantes
        Format: ╔══╦══╗ (top), ╠══╬══╣ (middle), ╚══╩══╝ (bottom)
        """
        if not result:
            print("\n╔════════════════════════════════════════════╗")
            print("║            EMPTY SET                       ║")
            print("║       0 row in set (0.000 sec)             ║")
            print("╚════════════════════════════════════════════╝")
            return
        
        columns = list(result[0].keys())
        
        # ========================================
        # 1. Calculer les largeurs de colonnes
        # ========================================
        col_widths = {}
        for col in columns:
            # Largeur de l'en-tête
            header_width = len(str(col))
            
            # Largeur du contenu (échantillon des 100 premières lignes)
            content_width = 0
            for row in result[:100]:
                value = row.get(col)
                display_value = self._format_display_value(value)
                content_width = max(content_width, len(display_value))
            
            # Largeur finale (min 8, max 50)
            col_widths[col] = min(max(header_width, content_width, 8), 50)
        
        # ========================================
        # 2. Construire les bordures
        # ========================================
        # Top border: ╔══════╦══════╦══════╗
        top_border = "╔" + "╦".join("═" * (col_widths[col] + 2) for col in columns) + "╗"
        
        # Middle border: ╠══════╬══════╬══════╣
        middle_border = "╠" + "╬".join("═" * (col_widths[col] + 2) for col in columns) + "╣"
        
        # Bottom border: ╚══════╩══════╩══════╝
        bottom_border = "╚" + "╩".join("═" * (col_widths[col] + 2) for col in columns) + "╝"
        
        # Header line: ║ col1 ║ col2 ║ col3 ║
        header_line = "║ " + " ║ ".join(f"{col:<{col_widths[col]}}" for col in columns) + " ║"
        
        # ========================================
        # 3. Afficher le tableau
        # ========================================
        print(f"\n{top_border}")
        print(header_line)
        print(middle_border)
        
        # Données
        rows_displayed = 0
        for row in result:
            values = []
            for col in columns:
                value = row.get(col)
                display_value = self._format_display_value(value)
                
                # Tronquer si nécessaire
                if len(display_value) > col_widths[col]:
                    display_value = display_value[:col_widths[col] - 3] + "..."
                
                values.append(f"{display_value:<{col_widths[col]}}")
            
            data_line = "║ " + " ║ ".join(values) + " ║"
            print(data_line)
            
            rows_displayed += 1
            
            # Limiter l'affichage à 1000 lignes
            if rows_displayed >= 1000:
                remaining = len(result) - 1000
                if remaining > 0:
                    # Afficher une ligne de continuation
                    continuation = "║ " + " ║ ".join("..." + " " * (col_widths[col] - 3) for col in columns) + " ║"
                    print(continuation)
                    print(f"║ ... {remaining} more row(s) ...{' ' * (sum(col_widths.values()) + len(columns) * 3 - 25)}║")
                break
        
        print(bottom_border)
        
        # ========================================
        # 4. Informations sur le résultat
        # ========================================
        total_rows = len(result)
        row_word = "row" if total_rows == 1 else "rows"
        
        # Temps d'exécution (simulé)
        time_str = "0.000 sec"
        if hasattr(self, 'last_query_info'):
            exec_time = getattr(self, 'last_query_info', {}).get('execution_time', 0)
            time_str = f"{exec_time:.3f} sec" if exec_time > 0 else "0.000 sec"
        
        print(f"{total_rows} {row_word} in set ({time_str})\n")

    def _format_display_value(self, value: Any) -> str:
        """
        Formate une valeur pour l'affichage (méthode existante, pas besoin de modification)
        """
        if value is None:
            return "NULL"
        elif isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, str):
            return value
        elif isinstance(value, (list, dict)):
            # Pour JSON, afficher une version compacte
            import json
            try:
                return json.dumps(value, ensure_ascii=False)
            except:
                return str(value)
        elif hasattr(value, '__class__'):
            # Pour les types personnalisés (MatrixType, EmailType, etc.)
            class_name = value.__class__.__name__
            if hasattr(value, 'shape'):
                return f"{class_name}{getattr(value, 'shape', '')}"
            elif hasattr(value, '__str__'):
                return str(value)
            else:
                return class_name
        else:
            return str(value)


    def _print_result_stats(self, result: List[Dict], columns: List[str]):
        """Affiche des statistiques sur le résultat"""
        if not result or len(result) < 10:
            return
        
        print("\n📊 Result Statistics:")
        print("-" * 40)
        
        for col in columns[:6]:  # Limiter à 6 colonnes pour éviter le spam
            values = [row.get(col) for row in result if row.get(col) is not None]
            
            if not values:
                continue
                
            # Statistiques pour les nombres
            if all(isinstance(v, (int, float)) for v in values):
                stats = {
                    'Min': min(values),
                    'Max': max(values),
                    'Avg': sum(values) / len(values),
                    'Non-NULL': f"{len(values)}/{len(result)}"
                }
                stats_str = ", ".join(f"{k}: {v:.2f}" if isinstance(v, float) else f"{k}: {v}" 
                                    for k, v in stats.items())
                print(f"  {col:<15}: {stats_str}")
            
            # Statistiques pour les strings
            elif all(isinstance(v, str) for v in values):
                unique_count = len(set(values))
                stats_str = f"Unique: {unique_count}/{len(values)}"
                if unique_count <= 10 and len(values) > 10:
                    # Afficher les valeurs uniques si peu nombreuses
                    samples = list(set(values))[:5]
                    samples_str = ", ".join(str(s) for s in samples)
                    if len(set(values)) > 5:
                        samples_str += "..."
                    stats_str += f" [{samples_str}]"
                print(f"  {col:<15}: {stats_str}")
            
def main():
    """Point d'entrée principal"""
    import sys
    
    if len(sys.argv) > 1:
        from dmonSQL.cli.commands import CommandHandler
        handler = CommandHandler()
        handler.handle()
    else:
        from dmonSQL.cli.shell import DmonSQLShell
        shell = DmonSQLShell()
        shell.run()


if __name__ == "__main__":
    main()