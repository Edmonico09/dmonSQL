"""
dmonSQL - Système de Gestion de Base de Données Relationnelle
Version 1.0.0 - Améliorée avec intégration complète des modules
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
from dmonSQL.storage.file_manager import FileManager
from dmonSQL.storage.serializer import DatabaseSerializer
from dmonSQL.utils.logger import get_logger
from dmonSQL.utils.helpers import format_size, format_duration
from dmonSQL.query.parser import QueryParser
from dmonSQL.core.table import Table 
from dmonSQL.core.database import Database
    
try:
    from dmonSQL.core.transaction_manager import TransactionManager
    # from dmonSQL.transaction.transaction_manager import TransactionManager
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
        
        # Gestionnaires optionnels
        if TRANSACTIONS_AVAILABLE:
            self.transaction_manager = TransactionManager()
            self.logger.info("Transaction manager initialized")
        
        if OPTIMIZER_AVAILABLE:
            self.query_optimizer = QueryOptimizer()
            self.logger.info("Query optimizer initialized")
        
        # Charger les bases de données existantes
        self.load_databases()
        
        self.logger.info(f"dmonSQL initialized with data directory: {self.data_dir}")
    
    def create_database(self, name: str):
        """Crée une base de données"""
        if name in self.databases:
            raise ValueError(f"Database {name} already exists")
        
        db = Database(name)
        self.databases[name] = db
        self.save_database(name)
        
        self.logger.info(f"Database '{name}' created")
        print(f"✓ Database '{name}' created successfully")
    
    def drop_database(self, name: str):
        """Supprime une base de données"""
        if name not in self.databases:
            raise ValueError(f"Database {name} does not exist")
        
        del self.databases[name]
        self.file_manager.delete_database(name)
        
        self.logger.info(f"Database '{name}' dropped")
        print(f"✓ Database '{name}' dropped successfully")
    
    def use_database(self, name: str):
        """Sélectionne une base de données"""
        if name not in self.databases:
            raise ValueError(f"Database {name} does not exist")
        
        self.current_db = name
        
        self.logger.info(f"Using database '{name}'")
        print(f"✓ Using database '{name}'")
    
    def execute(self, sql: str) -> Any:
        """Exécute une requête SQL avec logging"""
        sql = sql.strip()
        start_time = datetime.now()
        
        try:
            result = self._execute_internal(sql)
            if result is not None:
                print(f'command result {result}')
            # Logger les performances
            duration = (datetime.now() - start_time).total_seconds()
            self.logger.debug(f"Query executed in {format_duration(duration)}: {sql[:50]}...")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Query failed: {sql[:50]}... - Error: {e}")
            raise
    
    def _execute_internal(self, sql: str) -> Any:
        """Exécution interne des requêtes"""
        sql_upper = sql.upper()
        
        # ⭐ BEGIN TRANSACTION
        if sql_upper in ('BEGIN TRANSACTION', 'BEGIN', 'START TRANSACTION'):
            if not self.current_db:
                raise ValueError("No database selected")
            db = self.databases[self.current_db]
            self.transaction_manager.begin_transaction(db)
            print("✓ Transaction started")
            return
        
        # ⭐ COMMIT
        if sql_upper == 'COMMIT':
            if not self.transaction_manager.is_in_transaction():
                raise ValueError("No active transaction")
            db = self.databases[self.current_db]
            self.transaction_manager.commit_transaction(db)
            # Sauvegarder après COMMIT
            self.save_database(self.current_db)
            print("✓ Transaction committed")
            return
        
        # ⭐ ROLLBACK
        if sql_upper == 'ROLLBACK':
            if not self.transaction_manager.is_in_transaction():
                raise ValueError("No active transaction")
            db = self.databases[self.current_db]
            self.transaction_manager.rollback_transaction(db)
            print("✓ Transaction rolled back")
            return
        
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
        
        # Vérifier qu'une base est sélectionnée
        if not self.current_db:
            raise ValueError("No database selected. Use 'USE database_name'")
        
        db = self.databases[self.current_db]
        
        if sql_upper.startswith('CREATE TABLE'):
            result = self.parser.parse_create_table(sql)
            
            # Le parser retourne maintenant (table_name, columns, foreign_keys)
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
            
            # Lier la table à la base de données (pour validation FK)
            table.database = db
            
            db.create_table(table)
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
                self.save_database(self.current_db)
                print(f"✓ Index '{index_name}' created successfully")
                return
        
        # INSERT avec support multiple VALUES
        if sql_upper.startswith('INSERT'):
            insert_pattern = r"INSERT\s+INTO\s+(\w+)\s*\(([^)]+)\)\s*VALUES\s*((?:\([^)]*\)(?:\s*,\s*\([^)]*\))*)\s*)"
            match = re.match(insert_pattern, sql, re.IGNORECASE | re.DOTALL)
            if not match:
                raise ValueError("Invalid INSERT syntax. Use: INSERT INTO table (col1, col2) VALUES (val1, val2), (val3, val4)")

            table_name = match.group(1).strip()
            columns_str = match.group(2)
            values_str = match.group(3)

            if not self.current_db:
                raise ValueError("No database selected")
            db = self.databases[self.current_db]
            if table_name not in db.tables:
                raise ValueError(f"Table {table_name} does not exist")

            table = db.get_table(table_name)
            columns = [c.strip() for c in columns_str.split(",")]
            value_tuples = re.findall(r"\(([^)]*)\)", values_str)
            
            get_logger().info('Values in tuples {value_tuples}')
            
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
                            print('VALL', val)
                        except ValueError:
                            try:
                                values.append(float(val))
                            except ValueError:
                                values.append(val)

                values_dict = dict(zip(columns, values))

                # BEFORE INSERT
                if TRIGGERS_AVAILABLE and hasattr(db, 'trigger_manager'):
                    try:
                        from dmonSQL.procedures.trigger import TriggerEvent, TriggerTiming
                        db.trigger_manager.execute_triggers(
                            table_name, TriggerEvent.INSERT, TriggerTiming.BEFORE,
                            self, new_row=values_dict
                        )
                    except Exception as e:
                        self.logger.warning(f"BEFORE INSERT trigger failed: {e}")

                # INSERTION
                print(value_tuples)
                print(values_dict)
                table.insert(values_dict)
                inserted_count += 1

                # AFTER INSERT
                if TRIGGERS_AVAILABLE and hasattr(db, 'trigger_manager'):
                    try:
                        db.trigger_manager.execute_triggers(
                            table_name, TriggerEvent.INSERT, TriggerTiming.AFTER,
                            self, new_row=values_dict
                        )
                    except Exception as e:
                        self.logger.warning(f"AFTER INSERT trigger failed: {e}")

            # Logger dans la transaction si active
            if self.transaction_manager.is_in_transaction():
                self.transaction_manager.log_operation('INSERT', table_name, values_dict)

            # SAUVEGARDE + AFFICHAGE UNIQUEMENT APRÈS TOUTES LES INSERTIONS
            self.save_database(self.current_db)
            print(f"Inserted {inserted_count} row(s)")
            return inserted_count

        # SELECT
        if sql_upper.startswith('SELECT'):
            return self._execute_select(sql, db)
        
        # UPDATE
        if sql_upper.startswith('UPDATE'):
            
            # Logger dans la transaction si active
            if self.transaction_manager.is_in_transaction():
                self.transaction_manager.log_operation('UPDATE', table_name, values)
        
            return self._execute_update(sql, db)
        
        # DELETE
        if sql_upper.startswith('DELETE'):
            # CORRIGÉ : 'FROM' au lieu de 'fom'
            match = re.match(r'DELETE\s+FROM\s+(\w+)(?:\s+WHERE\s+(.*))?', sql, re.IGNORECASE)
            if not match:
                raise ValueError("Invalid DELETE syntax. Use: DELETE FROM table WHERE condition")
            table_name = match.group(1)
            where_clause = match.group(2)
            table = db.get_table(table_name)
            where_func = self._parse_where(where_clause) if where_clause else None
            count = table.delete(where=where_func)
            # self.save_database(self.current_db)
            if not self.transaction_manager.is_in_transaction():
                self.save_database(self.current_db)
            
            print(f"Deleted {count} row(s)")

            # Logger dans la transaction si active
            if self.transaction_manager.is_in_transaction():
                self.transaction_manager.log_operation('DELETE', table_name, where_clause)

            return count
        
        # SHOW STATS
        if sql_upper == 'SHOW STATS':
            self._show_statistics(db)
            return
        
        raise ValueError(f"Unsupported SQL statement: {sql}")
    
    def _execute_select(self, sql: str, db: Database):
        """Exécute un SELECT (avec ou sans JOIN)"""
        sql_upper = sql.upper()
    
        # Vérifier s'il y a un JOIN
        if ' JOIN ' in sql_upper:
            return self._execute_select_with_join(sql, db)
        
        # SELECT simple sans JOIN
        match = re.match(r'SELECT\s+(.*?)\s+FROM\s+(\w+)(?:\s+WHERE\s+(.*))?', 
                        sql, re.IGNORECASE)
        if not match:
            raise ValueError("Invalid SELECT syntax")
        
        columns_str = match.group(1).strip()
        table_name = match.group(2)
        where_clause = match.group(3)
        
        table = db.get_table(table_name)
        
        columns = None if columns_str == '*' else [c.strip() for c in columns_str.split(',')]
        
        where_func = None
        if where_clause:
            where_func = self._parse_where(where_clause)
        
        result = table.select(columns=columns, where=where_func)
        self._print_result(result)
        return result

    def _execute_select_with_join(self, sql: str, db: Database):
        """Exécute un SELECT avec JOIN"""
        pattern = r'SELECT\s+(.*?)\s+FROM\s+(\w+)(?:\s+(?:AS\s+)?(\w+))?\s+(INNER\s+JOIN|LEFT\s+JOIN|RIGHT\s+JOIN|JOIN)\s+(\w+)(?:\s+(?:AS\s+)?(\w+))?\s+ON\s+([\w.]+)\s*=\s*([\w.]+)(?:\s+WHERE\s+(.*))?'
        
        match = re.match(pattern, sql, re.IGNORECASE | re.DOTALL)
        if not match:
            raise ValueError(
                "Invalid JOIN syntax.\n"
                "Use: SELECT cols FROM table1 JOIN table2 ON table1.col = table2.col"
            )
        
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
        
        # Extraire les noms de colonnes (sans le préfixe table.)
        col1 = join_col1.split('.')[-1] if '.' in join_col1 else join_col1
        col2 = join_col2.split('.')[-1] if '.' in join_col2 else join_col2
        
        # Effectuer la jointure
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
        
        # Projeter les colonnes demandées
        if columns_str.strip() != '*':
            requested_cols = [c.strip() for c in columns_str.split(',')]
            result = self._project_columns(result, requested_cols)
        
        self._print_result(result)
        return result

    def _inner_join(self, table1: Table, table2: Table, col1: str, col2: str, 
                    alias1: str, alias2: str) -> List[Dict]:
        """Effectue un INNER JOIN"""
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
        """Effectue un LEFT JOIN"""
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
        """Effectue un RIGHT JOIN"""
        return self._left_join(table2, table1, col2, col1, alias2, alias1)

    def _parse_where_join(self, where_clause: str) -> callable:
        """Parse WHERE pour les jointures"""
        match = re.match(r'([\w.]+)\s*(=|>|<|>=|<=|!=|<>)\s*(.+)', where_clause.strip())
        if not match:
            raise ValueError("Invalid WHERE clause in JOIN")
        
        col = match.group(1).strip()
        op = match.group(2)
        val = match.group(3).strip()
        
        # Retirer les quotes
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
        """Projette les colonnes demandées depuis le résultat du JOIN"""
        if not rows:
            return []
        
        result = []
        for row in rows:
            projected = {}
            for col in columns:
                col = col.strip()
                value = None
                
                # 1. Chercher exactement (ex: "user.email")
                if col in row:
                    value = row[col]
                else:
                    # 2. Chercher par suffixe (ex: "email" -> "user.email")
                    for key in row.keys():
                        if key == col or key.endswith(f".{col}"):
                            value = row[key]
                            break
                        # 3. Si col = "table.col", chercher "col" dans les clés
                        if '.' in col:
                            _, col_name = col.rsplit('.', 1)
                            if key.endswith(f".{col_name}"):
                                value = row[key]
                                break
                
                projected[col] = value
            result.append(projected)
        
        return result
    
    def _execute_update(self, sql: str, db: Database):
        """Exécute un UPDATE"""
        match = re.match(r'UPDATE\s+(\w+)\s+SET\s+(.*?)(?:\s+WHERE\s+(.*))?$', 
                        sql, re.IGNORECASE)
        if not match:
            raise ValueError("Invalid UPDATE syntax")
        
        table_name = match.group(1)
        set_clause = match.group(2)
        where_clause = match.group(3)
        
        table = db.get_table(table_name)
        
        # Parser SET - CORRECTION: utiliser split('=', 1) pour limiter à 1 split
        values = {}
        # Gérer plusieurs assignments séparés par des virgules
        # Pattern pour matcher: col = 'value' ou col = "value" ou col = value
        assignments = re.findall(r"(\w+)\s*=\s*('[^']*'|\"[^\"]*\"|\S+)", set_clause)
        
        for col, val in assignments:
            col = col.strip()
            val = val.strip()
            # Retirer les quotes si présentes
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
        self.save_database(self.current_db)
        print(f"✓ {count} row(s) updated")
        return count   
    
    def _execute_delete(self, sql: str, db: Database):
        """Exécute un DELETE"""
        match = re.match(r'DELETE\s+FROM\s+(\w+)(?:\s+WHERE\s+(.*))?', 
                        sql, re.IGNORECASE)
        if not match:
            raise ValueError("Invalid DELETE syntax")
        
        table_name = match.group(1)
        where_clause = match.group(2)
        
        table = db.get_table(table_name)
        
        where_func = None
        if where_clause:
            where_func = self._parse_where(where_clause)
        
        count = table.delete(where=where_func)
        self.save_database(self.current_db)
        print(f"✓ {count} row(s) deleted")
        return count
    
    def _parse_where(self, where_clause: str) -> callable:
        """Parse une clause WHERE simple"""
        match = re.match(r'(\w+)\s*(=|>|<|>=|<=|!=)\s*(.+)', where_clause.strip())
        if not match:
            raise ValueError("Invalid WHERE clause")
        
        col = match.group(1)
        op = match.group(2)
        val = match.group(3).strip().strip("'")
        
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
    
    def _print_result(self, result: List[Dict]):
        """Affiche un résultat formaté"""
        if not result:
            print("\n🔭 Empty set (0 rows)")
            return
        
        # Afficher les colonnes
        columns = list(result[0].keys())
        col_widths = {col: max(len(col), 15) for col in columns}
        
        # Ajuster les largeurs selon les données
        for row in result[:10]:  # Échantillon
            for col in columns:
                val = str(row.get(col, ''))[:50]
                col_widths[col] = max(col_widths[col], len(val))
        
        # Header
        header = " | ".join(f"{col:<{col_widths[col]}}" for col in columns)
        print(f"\n{header}")
        print("-" * len(header))
        
        # Lignes
        for row in result:
            values = []
            for col in columns:
                val = row.get(col)
                if isinstance(val, MatrixType):
                    val_str = f"Matrix{val.shape}"
                elif isinstance(val, JSONType):
                    val_str = str(val)[:50]
                elif isinstance(val, EmailType):
                    val_str = str(val)
                else:
                    val_str = str(val) if val is not None else "NULL"
                
                values.append(val_str[:col_widths[col]])
            
            print(" | ".join(f"{val:<{col_widths[col]}}" for val in values))
        
        print(f"\n✓ {len(result)} row(s) in set\n")
    
    def _show_statistics(self, db: Database):
        """Affiche les statistiques de la base"""
        stats = db.get_statistics()
        
        print(f"\n📊 Database Statistics: {db.name}")
        print("=" * 60)
        print(f"Tables: {stats['tables']}")
        print(f"Total rows: {stats['total_rows']:,}")
        print(f"Total indexes: {stats['total_indexes']}")
        print(f"Created: {stats['created_at']}")
        print(f"Last modified: {stats['last_modified']}")
        
        # Taille estimée
        db_size = self.file_manager.get_database_size(db.name)
        if db_size > 0:
            print(f"Size on disk: {format_size(db_size)}")
        
        print("\nTables:")
        for table_name, table in db.tables.items():
            table_stats = table.get_statistics()
            print(f"  • {table_name}: {table_stats['rows']} rows, "
                  f"{table_stats['indexes']} indexes")
        
        print("=" * 60 + "\n")
    
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
                
                # ⭐ CORRECTION : Restaurer la référence database pour chaque table
                for table_name, table in db.tables.items():
                    table.database = db
                
                self.logger.debug(f"Database '{db_name}' loaded")
            except Exception as e:
                self.logger.warning(f"Could not load database '{db_name}': {e}")

    def show_databases(self):
        """Affiche les bases de données"""
        if not self.databases:
            print("\n🔭 No databases found")
            return
        
        print(f"\n📚 Databases ({len(self.databases)}):")
        print("-" * 60)
        
        for db_name in sorted(self.databases.keys()):
            current = "◀" if db_name == self.current_db else " "
            db_size = self.file_manager.get_database_size(db_name)
            size_str = format_size(db_size) if db_size > 0 else "N/A"
            
            db = self.databases[db_name]
            table_count = len(db.tables)
            
            print(f"  {current} {db_name:<20} ({table_count} tables, {size_str})")
        
        print("-" * 60 + "\n")
    
    def show_tables(self):
        """Affiche les tables de la base courante"""
        if not self.current_db:
            print("\n⚠️  No database selected")
            return
        
        db = self.databases[self.current_db]
        
        if not db.tables:
            print(f"\n🔭 No tables in database '{self.current_db}'")
            return
        
        print(f"\n📊 Tables in '{self.current_db}' ({len(db.tables)}):")
        print("-" * 80)
        print(f"{'Table':<20} {'Rows':<12} {'Columns':<12} {'Indexes':<12} {'Size (est.)'}")
        print("-" * 80)
        
        for table_name in sorted(db.tables.keys()):
            table = db.tables[table_name]
            tb = Table(table_name, {})

            stats = table.get_statistics()
            
            size_str = format_size(stats['size_estimate'])
            print(f"{table_name:<20} {stats['rows']:<12} {stats['columns']:<12} "
                  f"{stats['indexes']:<12} {size_str}")
        
        print("-" * 80 + "\n")
    
    def export_to_csv(self, table_name: str, output_file: str):
        """Exporte une table vers un fichier CSV"""
        if not self.current_db:
            raise ValueError("No database selected")
        
        db = self.databases[self.current_db]
        table = db.get_table(table_name)
        
        import csv
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            if not table.rows:
                return
            
            writer = csv.DictWriter(f, fieldnames=list(table.columns.keys()))
            writer.writeheader()
            
            for row in table.rows:
                # Convertir les types spéciaux en chaînes
                row_export = {}
                for col, val in row.items():
                    if isinstance(val, (MatrixType, EmailType, JSONType)):
                        row_export[col] = str(val)
                    else:
                        row_export[col] = val
                writer.writerow(row_export)
        
        print(f"✓ Table '{table_name}' exported to '{output_file}'")
        self.logger.info(f"Table '{table_name}' exported to CSV: {output_file}")
    
    def import_from_csv(self, table_name: str, input_file: str):
        """Importe des données depuis un fichier CSV"""
        if not self.current_db:
            raise ValueError("No database selected")
        
        db = self.databases[self.current_db]
        table = db.get_table(table_name)
        
        import csv
        
        count = 0
        with open(input_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                # Filtrer seulement les colonnes qui existent dans la table
                filtered_row = {k: v for k, v in row.items() if k in table.columns}
                table.insert(filtered_row)
                count += 1
        
        self.save_database(self.current_db)
        print(f"✓ {count} row(s) imported into '{table_name}'")
        self.logger.info(f"{count} rows imported from CSV: {input_file}")
    
    def backup_database(self, db_name: str, backup_path: str = None):
        """Crée une sauvegarde d'une base de données"""
        if db_name not in self.databases:
            raise ValueError(f"Database {db_name} does not exist")
        
        if backup_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{db_name}_backup_{timestamp}.dmon"
        
        import shutil
        
        # Sauvegarder d'abord la base
        self.save_database(db_name)
        
        # Copier le fichier
        source = self.file_manager.get_database_path(db_name)
        shutil.copy2(source, backup_path)
        
        print(f"✓ Database '{db_name}' backed up to '{backup_path}'")
        self.logger.info(f"Database '{db_name}' backed up to: {backup_path}")
    
    def restore_database(self, backup_path: str, db_name: str = None):
        """Restaure une base de données depuis une sauvegarde"""
        import shutil
        
        if db_name is None:
            # Extraire le nom depuis le fichier de backup
            db_name = Path(backup_path).stem.split('_backup_')[0]
        
        # Copier le fichier de backup
        dest = self.file_manager.get_database_path(db_name)
        shutil.copy2(backup_path, dest)
        
        # Recharger la base
        try:
            self.databases[db_name] = self.serializer.load_database(db_name)
            print(f"✓ Database '{db_name}' restored from '{backup_path}'")
            self.logger.info(f"Database '{db_name}' restored from: {backup_path}")
        except Exception as e:
            self.logger.error(f"Failed to restore database: {e}")
            raise
    
    def analyze_query(self, sql: str):
        """Analyse une requête SQL et affiche le plan d'exécution"""
        if not OPTIMIZER_AVAILABLE:
            print("⚠️  Query optimizer not available")
            return
        
        print(f"\n🔍 Query Analysis:")
        print("=" * 60)
        print(f"Query: {sql}")
        print("-" * 60)
        
        # Analyse basique
        sql_upper = sql.upper()
        
        if 'SELECT' in sql_upper:
            print("Query Type: SELECT")
            if 'WHERE' in sql_upper:
                print("Has WHERE clause: Yes")
            if 'ORDER BY' in sql_upper:
                print("Has ORDER BY: Yes")
            if 'LIMIT' in sql_upper:
                print("Has LIMIT: Yes")
        elif 'INSERT' in sql_upper:
            print("Query Type: INSERT")
        elif 'UPDATE' in sql_upper:
            print("Query Type: UPDATE")
        elif 'DELETE' in sql_upper:
            print("Query Type: DELETE")
        
        print("\n💡 Optimization Suggestions:")
        
        # Suggestions basiques
        if 'SELECT *' in sql_upper:
            print("  • Consider selecting only needed columns instead of SELECT *")
        
        if 'WHERE' in sql_upper and 'INDEX' not in sql_upper:
            print("  • Consider creating an index on WHERE clause columns")
        
        if 'ORDER BY' in sql_upper:
            print("  • Consider creating an index on ORDER BY columns")
        
        print("=" * 60 + "\n")
    
    def get_table_info(self, table_name: str) -> Dict:
        """Retourne les informations détaillées d'une table"""
        if not self.current_db:
            raise ValueError("No database selected")
        
        db = self.databases[self.current_db]
        table = db.get_table(table_name)
        
        info = {
            'name': table.name,
            'columns': {},
            'indexes': {},
            'statistics': table.get_statistics(),
            'primary_keys': table.get_primary_key_columns(),
            'constraints': len(table.constraint_manager.constraints)
        }
        
        # Informations des colonnes
        for col_name, col in table.columns.items():
            info['columns'][col_name] = {
                'type': col.dtype,
                'length': col.length,
                'nullable': col.nullable,
                'primary_key': col.primary_key,
                'unique': col.unique,
                'auto_increment': col.auto_increment,
                'default': col.default
            }
        
        # Informations des index
        for idx_name, idx in table.indexes.items():
            info['indexes'][idx_name] = {
                'columns': idx.columns,
                'unique': idx.unique
            }
        
        return info
    
    def execute_batch(self, sql_statements: List[str], stop_on_error: bool = False):
        """Exécute plusieurs requêtes SQL en batch"""
        results = []
        errors = []
        
        print(f"\n🔄 Executing batch of {len(sql_statements)} statements...")
        print("-" * 60)
        
        for i, sql in enumerate(sql_statements, 1):
            try:
                result = self.execute(sql)
                results.append((i, sql, result, None))
                print(f"✓ Statement {i}/{len(sql_statements)} completed")
            except Exception as e:
                errors.append((i, sql, str(e)))
                print(f"✗ Statement {i}/{len(sql_statements)} failed: {e}")
                
                if stop_on_error:
                    print("\n❌ Batch execution stopped due to error")
                    break
        
        print("-" * 60)
        print(f"\n📊 Batch Summary:")
        print(f"  Total: {len(sql_statements)}")
        print(f"  Successful: {len(results)}")
        print(f"  Failed: {len(errors)}")
        
        if errors:
            print(f"\n❌ Errors:")
            for i, sql, error in errors:
                print(f"  Statement {i}: {error}")
        
        return results, errors
    
    def vacuum(self):
        """Optimise et compacte la base de données courante"""
        if not self.current_db:
            raise ValueError("No database selected")
        
        print(f"\n🧹 Vacuuming database '{self.current_db}'...")
        
        db = self.databases[self.current_db]
        
        # Reconstruire tous les index
        total_indexes = 0
        for table in db.tables.values():
            for index in table.indexes.values():
                index.build(table.rows)
                total_indexes += 1
        
        # Sauvegarder
        self.save_database(self.current_db)
        
        print(f"✓ Database vacuumed: {total_indexes} index(es) rebuilt")
        self.logger.info(f"Database '{self.current_db}' vacuumed")
    
    def explain_table(self, table_name: str):
        """Explique la structure d'une table (alias pour get_table_info)"""
        info = self.get_table_info(table_name)
        
        print(f"\n📊 Table: {info['name']}")
        print("=" * 80)
        
        print(f"\n📝 Columns ({len(info['columns'])}):")
        print("-" * 80)
        print(f"{'Column':<20} {'Type':<15} {'Null':<8} {'Key':<10} {'Extra'}")
        print("-" * 80)
        
        for col_name, col_info in info['columns'].items():
            null_str = "YES" if col_info['nullable'] else "NO"
            key_str = "PRI" if col_info['primary_key'] else ("UNI" if col_info['unique'] else "")
            extra = []
            if col_info['auto_increment']:
                extra.append("auto_increment")
            if col_info['default'] is not None:
                extra.append(f"default={col_info['default']}")
            extra_str = ", ".join(extra)
            
            type_str = col_info['type']
            if col_info['length']:
                type_str += f"({col_info['length']})"
            
            print(f"{col_name:<20} {type_str:<15} {null_str:<8} {key_str:<10} {extra_str}")
        
        if info['indexes']:
            print(f"\n🔍 Indexes ({len(info['indexes'])}):")
            print("-" * 80)
            for idx_name, idx_info in info['indexes'].items():
                idx_type = "UNIQUE" if idx_info['unique'] else "INDEX"
                cols = ", ".join(idx_info['columns'])
                print(f"  {idx_type}: {idx_name} ON ({cols})")
        
        stats = info['statistics']
        print(f"\n📈 Statistics:")
        print("-" * 80)
        print(f"  Rows: {stats['rows']}")
        print(f"  Columns: {stats['columns']}")
        print(f"  Indexes: {stats['indexes']}")
        print(f"  Estimated size: {format_size(stats['size_estimate'])}")
        print(f"  Created: {stats['created_at']}")
        
        print("=" * 80 + "\n")

def main():
    """Point d'entrée principal"""
    import sys
    
    if len(sys.argv) > 1:
        # Mode commande
        from dmonSQL.cli.commands import CommandHandler
        handler = CommandHandler()
        handler.handle()
    else:
        # Mode shell par défaut
        from dmonSQL.cli.shell import DmonSQLShell
        shell = DmonSQLShell()
        shell.run()


if __name__ == "__main__":
    main()