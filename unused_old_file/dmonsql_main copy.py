# """
# dmonSQL - Système de Gestion de Base de Données Relationnelle
# Version 2.0.0 - Améliorée avec intégration complète des modules
# """

# import re
# from datetime import datetime
# from typing import Any, List, Dict, Tuple
# from pathlib import Path

# # Imports des modules dmonSQL
# from dmonSQL.types.matrix_type import MatrixType
# from dmonSQL.types.email_type import EmailType
# from dmonSQL.types.json_type import JSONType
# from dmonSQL.core.column import Column
# from dmonSQL.core.index import Index
# from dmonSQL.core.constraint import ConstraintManager, NotNullConstraint
# from dmonSQL.storage.file_manager import FileManager
# from dmonSQL.storage.serializer import DatabaseSerializer
# from dmonSQL.utils.logger import get_logger
# from dmonSQL.utils.helpers import format_size, format_duration
# from dmonSQL.query.parser import QueryParser

# # Imports optionnels (avec gestion d'erreur)
# try:
#     from dmonSQL.transaction.transaction_manager import TransactionManager
#     TRANSACTIONS_AVAILABLE = True
# except ImportError:
#     TRANSACTIONS_AVAILABLE = False

# try:
#     from dmonSQL.procedures.procedure import ProcedureManager
#     PROCEDURES_AVAILABLE = True
# except ImportError:
#     PROCEDURES_AVAILABLE = False

# try:
#     from dmonSQL.procedures.trigger import TriggerManager
#     TRIGGERS_AVAILABLE = True
# except ImportError:
#     TRIGGERS_AVAILABLE = False

# try:
#     from dmonSQL.query.optimizer import QueryOptimizer
#     OPTIMIZER_AVAILABLE = True
# except ImportError:
#     OPTIMIZER_AVAILABLE = False


# class Table:
#     """Table de base de données améliorée"""
    
#     def __init__(self, name: str, columns: List[Column]):
#         self.name = name
#         self.columns = {col.name: col for col in columns}
#         self.rows = []
#         self.indexes = {}
#         self.auto_increment_counters = {}
#         self.constraint_manager = ConstraintManager()
#         self.created_at = datetime.now()
#         self.row_count_history = []
        
#         # Initialiser les compteurs auto-increment
#         for col_name, col in self.columns.items():
#             if col.auto_increment:
#                 self.auto_increment_counters[col_name] = 0
            
#             # Ajouter contrainte NOT NULL si nécessaire
#             if not col.nullable and not col.primary_key:
#                 constraint = NotNullConstraint(f"nn_{col_name}", col_name)
#                 self.constraint_manager.add_constraint(constraint)
    
#     def get_primary_key_columns(self) -> List[str]:
#         """Retourne les colonnes de clé primaire"""
#         return [name for name, col in self.columns.items() if col.primary_key]
    
#     def create_index(self, name: str, columns: List[str], unique: bool = False):
#         """Crée un index"""
#         for col in columns:
#             if col not in self.columns:
#                 raise ValueError(f"Column {col} does not exist")
        
#         index = Index(name, columns, unique)
#         index.build(self.rows)
#         self.indexes[name] = index
        
#         get_logger().info(f"Index '{name}' created on table '{self.name}'")
    
#     def insert(self, values: Dict[str, Any]) -> int:
#         """Insère une ligne avec validation des contraintes"""
#         row = {}
        
#         # Construire la ligne
#         for col_name, col in self.columns.items():
#             if col.auto_increment:
#                 self.auto_increment_counters[col_name] += 1
#                 row[col_name] = self.auto_increment_counters[col_name]
#             elif col_name in values:
#                 row[col_name] = col.validate(values[col_name])
#             elif col.default is not None:
#                 row[col_name] = col.default
#             elif col.nullable:
#                 row[col_name] = None
#             else:
#                 raise ValueError(f"Missing required column: {col_name}")
        
#         # Valider les contraintes
#         self.constraint_manager.validate_row(row)
        
#         # Vérifier les contraintes unique
#         for col_name, col in self.columns.items():
#             if col.unique or col.primary_key:
#                 for existing_row in self.rows:
#                     if existing_row[col_name] == row[col_name] and row[col_name] is not None:
#                         raise ValueError(f"Duplicate value for unique column {col_name}: {row[col_name]}")
        
#         # Ajouter la ligne
#         self.rows.append(row)
        
#         # Reconstruire les index
#         for index in self.indexes.values():
#             index.build(self.rows)
        
#         # Historique
#         self.row_count_history.append((datetime.now(), len(self.rows)))
        
#         get_logger().debug(f"Row inserted into table '{self.name}'")
#         return len(self.rows) - 1
    
#     def select(self, columns: List[str] = None, where: callable = None, 
#                order_by: List[Tuple[str, str]] = None, limit: int = None) -> List[Dict]:
#         """Sélectionne des lignes"""
#         if columns is None:
#             columns = list(self.columns.keys())
        
#         # Filtrage
#         result = self.rows if where is None else [row for row in self.rows if where(row)]
        
#         # Tri
#         if order_by:
#             for col, direction in reversed(order_by):
#                 reverse = direction.upper() == "DESC"
#                 result = sorted(result, key=lambda x: x.get(col), reverse=reverse)
        
#         # Limite
#         if limit:
#             result = result[:limit]
        
#         # Projection
#         return [{col: row[col] for col in columns if col in row} for row in result]
    
#     def update(self, values: Dict[str, Any], where: callable = None) -> int:
#         """Met à jour des lignes"""
#         count = 0
#         for row in self.rows:
#             if where is None or where(row):
#                 # Appliquer les modifications
#                 for col_name, value in values.items():
#                     if col_name in self.columns:
#                         row[col_name] = self.columns[col_name].validate(value)
                
#                 # Valider les contraintes
#                 self.constraint_manager.validate_row(row)
#                 count += 1
        
#         # Reconstruire les index
#         for index in self.indexes.values():
#             index.build(self.rows)
        
#         get_logger().debug(f"{count} row(s) updated in table '{self.name}'")
#         return count
    
#     def delete(self, where: callable = None) -> int:
#         """Supprime des lignes"""
#         if where is None:
#             count = len(self.rows)
#             self.rows.clear()
#         else:
#             initial_count = len(self.rows)
#             self.rows = [row for row in self.rows if not where(row)]
#             count = initial_count - len(self.rows)
        
#         # Reconstruire les index
#         for index in self.indexes.values():
#             index.build(self.rows)
        
#         get_logger().debug(f"{count} row(s) deleted from table '{self.name}'")
#         return count
    
#     def get_statistics(self) -> Dict:
#         """Retourne les statistiques de la table"""
#         return {
#             'name': self.name,
#             'columns': len(self.columns),
#             'rows': len(self.rows),
#             'indexes': len(self.indexes),
#             'created_at': self.created_at.isoformat(),
#             'size_estimate': len(self.rows) * len(self.columns) * 50  # Estimation
#         }


# class Database:
#     """Base de données améliorée"""
    
#     def __init__(self, name: str):
#         self.name = name
#         self.tables = {}
#         self.created_at = datetime.now()
#         self.last_modified = datetime.now()
        
#         # Gestionnaires optionnels
#         if PROCEDURES_AVAILABLE:
#             self.procedure_manager = ProcedureManager()
        
#         if TRIGGERS_AVAILABLE:
#             self.trigger_manager = TriggerManager()
    
#     def create_table(self, table: Table):
#         """Crée une table"""
#         if table.name in self.tables:
#             raise ValueError(f"Table {table.name} already exists")
        
#         self.tables[table.name] = table
#         self.last_modified = datetime.now()
        
#         get_logger().info(f"Table '{table.name}' created in database '{self.name}'")
    
#     def drop_table(self, table_name: str):
#         """Supprime une table"""
#         if table_name not in self.tables:
#             raise ValueError(f"Table {table_name} does not exist")
        
#         del self.tables[table_name]
#         self.last_modified = datetime.now()
        
#         get_logger().info(f"Table '{table_name}' dropped from database '{self.name}'")
    
#     def get_table(self, table_name: str) -> Table:
#         """Récupère une table"""
#         if table_name not in self.tables:
#             raise ValueError(f"Table {table_name} does not exist")
#         return self.tables[table_name]
    
#     def get_statistics(self) -> Dict:
#         """Retourne les statistiques de la base"""
#         total_rows = sum(len(table.rows) for table in self.tables.values())
#         total_indexes = sum(len(table.indexes) for table in self.tables.values())
        
#         return {
#             'name': self.name,
#             'tables': len(self.tables),
#             'total_rows': total_rows,
#             'total_indexes': total_indexes,
#             'created_at': self.created_at.isoformat(),
#             'last_modified': self.last_modified.isoformat()
#         }


# class RelationalAlgebra:
#     """Opérations d'algèbre relationnelle"""
    
#     @staticmethod
#     def projection(table: Table, columns: List[str]) -> List[Dict]:
#         """Projection (SELECT colonnes)"""
#         return table.select(columns=columns)
    
#     @staticmethod
#     def selection(table: Table, condition: callable) -> List[Dict]:
#         """Sélection (WHERE)"""
#         return table.select(where=condition)
    
#     @staticmethod
#     def cross_product(table1: Table, table2: Table) -> List[Dict]:
#         """Produit cartésien"""
#         result = []
#         for row1 in table1.rows:
#             for row2 in table2.rows:
#                 combined = {}
#                 for k, v in row1.items():
#                     combined[f"{table1.name}.{k}"] = v
#                 for k, v in row2.items():
#                     combined[f"{table2.name}.{k}"] = v
#                 result.append(combined)
#         return result
    
#     @staticmethod
#     def join(table1: Table, table2: Table, on: Tuple[str, str]) -> List[Dict]:
#         """Jointure naturelle"""
#         col1, col2 = on
#         result = []
        
#         for row1 in table1.rows:
#             for row2 in table2.rows:
#                 if row1.get(col1) == row2.get(col2):
#                     combined = {}
#                     for k, v in row1.items():
#                         combined[k] = v
#                     for k, v in row2.items():
#                         if k not in combined:
#                             combined[k] = v
#                     result.append(combined)
        
#         return result
    
#     @staticmethod
#     def union(rows1: List[Dict], rows2: List[Dict]) -> List[Dict]:
#         """Union"""
#         result = list(rows1)
#         for row in rows2:
#             if row not in result:
#                 result.append(row)
#         return result
    
#     @staticmethod
#     def difference(rows1: List[Dict], rows2: List[Dict]) -> List[Dict]:
#         """Différence"""
#         return [row for row in rows1 if row not in rows2]
    
#     @staticmethod
#     def division(dividend_table: Table, divisor_table: Table, 
#                  common_attrs: List[str], dividend_attrs: List[str]) -> List[Dict]:
#         """Division relationnelle"""
#         divisor_tuples = []
#         for row in divisor_table.rows:
#             divisor_tuple = tuple(row[attr] for attr in common_attrs)
#             divisor_tuples.append(divisor_tuple)
        
#         if not divisor_tuples:
#             return []
        
#         groups = {}
#         for row in dividend_table.rows:
#             key = tuple(row[attr] for attr in dividend_attrs)
#             if key not in groups:
#                 groups[key] = []
#             value = tuple(row[attr] for attr in common_attrs)
#             if value not in groups[key]:
#                 groups[key].append(value)
        
#         result = []
#         for key, values in groups.items():
#             if all(divisor_tuple in values for divisor_tuple in divisor_tuples):
#                 result_dict = {dividend_attrs[i]: key[i] for i in range(len(dividend_attrs))}
#                 result.append(result_dict)
        
#         return result


# class DmonSQL:
#     """Système de gestion de base de données principal - Version améliorée"""
    
#     def __init__(self, data_dir: str = "./dmonsql_data"):
#         self.data_dir = Path(data_dir)
#         self.databases = {}
#         self.current_db = None
        
#         # Initialiser les gestionnaires
#         self.file_manager = FileManager(str(self.data_dir))
#         self.serializer = DatabaseSerializer(self.file_manager)
#         self.logger = get_logger("dmonSQL")
#         self.parser = QueryParser()
        
#         # Gestionnaires optionnels
#         if TRANSACTIONS_AVAILABLE:
#             self.transaction_manager = TransactionManager()
#             self.logger.info("Transaction manager initialized")
        
#         if OPTIMIZER_AVAILABLE:
#             self.query_optimizer = QueryOptimizer()
#             self.logger.info("Query optimizer initialized")
        
#         # Charger les bases de données existantes
#         self.load_databases()
        
#         self.logger.info(f"dmonSQL initialized with data directory: {self.data_dir}")
    
#     def create_database(self, name: str):
#         """Crée une base de données"""
#         if name in self.databases:
#             raise ValueError(f"Database {name} already exists")
        
#         db = Database(name)
#         self.databases[name] = db
#         self.save_database(name)
        
#         self.logger.info(f"Database '{name}' created")
#         print(f"✓ Database '{name}' created successfully")
    
#     def drop_database(self, name: str):
#         """Supprime une base de données"""
#         if name not in self.databases:
#             raise ValueError(f"Database {name} does not exist")
        
#         del self.databases[name]
#         self.file_manager.delete_database(name)
        
#         self.logger.info(f"Database '{name}' dropped")
#         print(f"✓ Database '{name}' dropped successfully")
    
#     def use_database(self, name: str):
#         """Sélectionne une base de données"""
#         if name not in self.databases:
#             raise ValueError(f"Database {name} does not exist")
        
#         self.current_db = name
        
#         self.logger.info(f"Using database '{name}'")
#         print(f"✓ Using database '{name}'")
    
#     def execute(self, sql: str) -> Any:
#         """Exécute une requête SQL avec logging"""
#         sql = sql.strip()
#         start_time = datetime.now()
        
#         try:
#             result = self._execute_internal(sql)
            
#             # Logger les performances
#             duration = (datetime.now() - start_time).total_seconds()
#             self.logger.debug(f"Query executed in {format_duration(duration)}: {sql[:50]}...")
            
#             return result
            
#         except Exception as e:
#             self.logger.error(f"Query failed: {sql[:50]}... - Error: {e}")
#             raise
    
#     def _execute_internal(self, sql: str) -> Any:
#         """Exécution interne des requêtes"""
#         sql_upper = sql.upper()
        
#         # CREATE DATABASE
#         if sql_upper.startswith('CREATE DATABASE'):
#             match = re.match(r'CREATE\s+DATABASE\s+(\w+)', sql, re.IGNORECASE)
#             if match:
#                 self.create_database(match.group(1))
#                 return
        
#         # DROP DATABASE
#         if sql_upper.startswith('DROP DATABASE'):
#             match = re.match(r'DROP\s+DATABASE\s+(\w+)', sql, re.IGNORECASE)
#             if match:
#                 self.drop_database(match.group(1))
#                 return
        
#         # USE DATABASE
#         if sql_upper.startswith('USE'):
#             match = re.match(r'USE\s+(\w+)', sql, re.IGNORECASE)
#             if match:
#                 self.use_database(match.group(1))
#                 return
        
#         # Vérifier qu'une base est sélectionnée
#         if not self.current_db:
#             raise ValueError("No database selected. Use 'USE database_name'")
        
#         db = self.databases[self.current_db]
        
#         # CREATE TABLE
#         if sql_upper.startswith('CREATE TABLE'):
#             table_name, columns = self.parser.parse_create_table(sql)
#             table = Table(table_name, columns)
#             db.create_table(table)
#             self.save_database(self.current_db)
#             print(f"✓ Table '{table_name}' created successfully")
#             return
        
#         # CREATE INDEX
#         if sql_upper.startswith('CREATE INDEX'):
#             match = re.match(r'CREATE\s+(?:UNIQUE\s+)?INDEX\s+(\w+)\s+ON\s+(\w+)\s*\((.*?)\)', 
#                            sql, re.IGNORECASE)
#             if match:
#                 index_name = match.group(1)
#                 table_name = match.group(2)
#                 columns = [c.strip() for c in match.group(3).split(',')]
#                 unique = 'UNIQUE' in sql_upper
                
#                 table = db.get_table(table_name)
#                 table.create_index(index_name, columns, unique)
#                 self.save_database(self.current_db)
#                 print(f"✓ Index '{index_name}' created successfully")
#                 return
        
#         # INSERT
#         if sql_upper.startswith('INSERT'):
#             match = re.match(r'INSERT\s+INTO\s+(\w+)\s*\((.*?)\)\s*VALUES\s*\((.*?)\)', 
#                            sql, re.IGNORECASE)
#             if match:
#                 table_name = match.group(1)
#                 columns = [c.strip() for c in match.group(2).split(',')]
#                 values_str = match.group(3)
                
#                 # Parser les valeurs
#                 values = []
#                 for val in re.findall(r"'[^']*'|[^,]+", values_str):
#                     val = val.strip()
#                     if val.startswith("'") and val.endswith("'"):
#                         values.append(val[1:-1])
#                     elif val.upper() == 'NULL':
#                         values.append(None)
#                     else:
#                         try:
#                             values.append(int(val))
#                         except:
#                             try:
#                                 values.append(float(val))
#                             except:
#                                 values.append(val)
                
#                 values_dict = dict(zip(columns, values))
#                 table = db.get_table(table_name)
                
#                 # Exécuter les triggers BEFORE si disponibles
#                 if TRIGGERS_AVAILABLE and hasattr(db, 'trigger_manager'):
#                     try:
#                         from dmonSQL.procedures.trigger import TriggerEvent, TriggerTiming
#                         db.trigger_manager.execute_triggers(
#                             table_name, TriggerEvent.INSERT, TriggerTiming.BEFORE,
#                             self, new_row=values_dict
#                         )
#                     except:
#                         pass
                
#                 table.insert(values_dict)
                
#                 # Exécuter les triggers AFTER
#                 if TRIGGERS_AVAILABLE and hasattr(db, 'trigger_manager'):
#                     try:
#                         db.trigger_manager.execute_triggers(
#                             table_name, TriggerEvent.INSERT, TriggerTiming.AFTER,
#                             self, new_row=values_dict
#                         )
#                     except:
#                         pass
                
#                 self.save_database(self.current_db)
#                 print("✓ 1 row inserted")
#                 return
        
#         # SELECT
#         if sql_upper.startswith('SELECT'):
#             return self._execute_select(sql, db)
        
#         # UPDATE
#         if sql_upper.startswith('UPDATE'):
#             return self._execute_update(sql, db)
        
#         # DELETE
#         if sql_upper.startswith('DELETE'):
#             return self._execute_delete(sql, db)
        
#         # SHOW STATS
#         if sql_upper == 'SHOW STATS':
#             self._show_statistics(db)
#             return
        
#         raise ValueError(f"Unsupported SQL statement: {sql}")
    
#     def _execute_select(self, sql: str, db: Database):
#         """Exécute un SELECT"""
#         match = re.match(r'SELECT\s+(.*?)\s+FROM\s+(\w+)(?:\s+WHERE\s+(.*))?', 
#                         sql, re.IGNORECASE)
#         if not match:
#             raise ValueError("Invalid SELECT syntax")
        
#         columns_str = match.group(1).strip()
#         table_name = match.group(2)
#         where_clause = match.group(3)
        
#         table = db.get_table(table_name)
        
#         columns = None if columns_str == '*' else [c.strip() for c in columns_str.split(',')]
        
#         where_func = None
#         if where_clause:
#             where_func = self._parse_where(where_clause)
        
#         result = table.select(columns=columns, where=where_func)
#         self._print_result(result)
#         return result
    
#     def _execute_update(self, sql: str, db: Database):
#         """Exécute un UPDATE"""
#         match = re.match(r'UPDATE\s+(\w+)\s+SET\s+(.*?)(?:\s+WHERE\s+(.*))?', 
#                         sql, re.IGNORECASE)
#         if not match:
#             raise ValueError("Invalid UPDATE syntax")
        
#         table_name = match.group(1)
#         set_clause = match.group(2)
#         where_clause = match.group(3)
        
#         table = db.get_table(table_name)
        
#         # Parser SET
#         values = {}
#         for assignment in set_clause.split(','):
#             col, val = assignment.split('=')
#             col = col.strip()
#             val = val.strip().strip("'")
#             values[col] = val
        
#         where_func = None
#         if where_clause:
#             where_func = self._parse_where(where_clause)
        
#         count = table.update(values, where=where_func)
#         self.save_database(self.current_db)
#         print(f"✓ {count} row(s) updated")
#         return count
    
#     def _execute_delete(self, sql: str, db: Database):
#         """Exécute un DELETE"""
#         match = re.match(r'DELETE\s+FROM\s+(\w+)(?:\s+WHERE\s+(.*))?', 
#                         sql, re.IGNORECASE)
#         if not match:
#             raise ValueError("Invalid DELETE syntax")
        
#         table_name = match.group(1)
#         where_clause = match.group(2)
        
#         table = db.get_table(table_name)
        
#         where_func = None
#         if where_clause:
#             where_func = self._parse_where(where_clause)
        
#         count = table.delete(where=where_func)
#         self.save_database(self.current_db)
#         print(f"✓ {count} row(s) deleted")
#         return count
    
#     def _parse_where(self, where_clause: str) -> callable:
#         """Parse une clause WHERE simple"""
#         match = re.match(r'(\w+)\s*(=|>|<|>=|<=|!=)\s*(.+)', where_clause.strip())
#         if not match:
#             raise ValueError("Invalid WHERE clause")
        
#         col = match.group(1)
#         op = match.group(2)
#         val = match.group(3).strip().strip("'")
        
#         try:
#             val = int(val)
#         except:
#             try:
#                 val = float(val)
#             except:
#                 pass
        
#         if op == '=':
#             return lambda row: row.get(col) == val
#         elif op == '>':
#             return lambda row: row.get(col) > val
#         elif op == '<':
#             return lambda row: row.get(col) < val
#         elif op == '>=':
#             return lambda row: row.get(col) >= val
#         elif op == '<=':
#             return lambda row: row.get(col) <= val
#         elif op == '!=':
#             return lambda row: row.get(col) != val
    
#     def _print_result(self, result: List[Dict]):
#         """Affiche un résultat formaté"""
#         if not result:
#             print("\n📭 Empty set (0 rows)")
#             return
        
#         # Afficher les colonnes
#         columns = list(result[0].keys())
#         col_widths = {col: max(len(col), 15) for col in columns}
        
#         # Ajuster les largeurs selon les données
#         for row in result[:10]:  # Échantillon
#             for col in columns:
#                 val = str(row.get(col, ''))[:50]
#                 col_widths[col] = max(col_widths[col], len(val))
        
#         # Header
#         header = " | ".join(f"{col:<{col_widths[col]}}" for col in columns)
#         print(f"\n{header}")
#         print("-" * len(header))
        
#         # Lignes
#         for row in result:
#             values = []
#             for col in columns:
#                 val = row.get(col)
#                 if isinstance(val, MatrixType):
#                     val_str = f"Matrix{val.shape}"
#                 elif isinstance(val, JSONType):
#                     val_str = str(val)[:50]
#                 elif isinstance(val, EmailType):
#                     val_str = str(val)
#                 else:
#                     val_str = str(val) if val is not None else "NULL"
                
#                 values.append(val_str[:col_widths[col]])
            
#             print(" | ".join(f"{val:<{col_widths[col]}}" for val in values))
        
#         print(f"\n✓ {len(result)} row(s) in set\n")
    
#     def _show_statistics(self, db: Database):
#         """Affiche les statistiques de la base"""
#         stats = db.get_statistics()
        
#         print(f"\n📊 Database Statistics: {db.name}")
#         print("=" * 60)
#         print(f"Tables: {stats['tables']}")
#         print(f"Total rows: {stats['total_rows']:,}")
#         print(f"Total indexes: {stats['total_indexes']}")
#         print(f"Created: {stats['created_at']}")
#         print(f"Last modified: {stats['last_modified']}")
        
#         # Taille estimée
#         db_size = self.file_manager.get_database_size(db.name)
#         if db_size > 0:
#             print(f"Size on disk: {format_size(db_size)}")
        
#         print("\nTables:")
#         for table_name, table in db.tables.items():
#             table_stats = table.get_statistics()
#             print(f"  • {table_name}: {table_stats['rows']} rows, "
#                   f"{table_stats['indexes']} indexes")
        
#         print("=" * 60 + "\n")
    
#     def save_database(self, db_name: str):
#         """Sauvegarde une base de données"""
#         if db_name not in self.databases:
#             return
        
#         try:
#             self.serializer.save_database(db_name, self.databases[db_name])
#             self.logger.debug(f"Database '{db_name}' saved")
#         except Exception as e:
#             self.logger.error(f"Failed to save database '{db_name}': {e}")
#             raise
    
#     def load_databases(self):
#         """Charge toutes les bases de données"""
#         db_names = self.file_manager.list_databases()
        
#         for db_name in db_names:
#             try:
#                 self.databases[db_name] = self.serializer.load_database(db_name)
#                 self.logger.debug(f"Database '{db_name}' loaded")
#             except Exception as e:
#                 self.logger.warning(f"Could not load database '{db_name}': {e}")
    
#     def show_databases(self):
#         """Affiche les bases de données"""
#         if not self.databases:
#             print("\n📭 No databases found")
#             return
        
#         print(f"\n📚 Databases ({len(self.databases)}):")
#         print("-" * 60)
        
#         for db_name in sorted(self.databases.keys()):
#             current = "◀" if db_name == self.current_db else " "
#             db_size = self.file_manager.get_database_size(db_name)
#             size_str = format_size(db_size) if db_size > 0 else "N/A"
            
#             db = self.databases[db_name]
#             table_count = len(db.tables)
            
#             print(f"  {current} {db_name:<20} ({table_count} tables, {size_str})")
        
#         print("-" * 60 + "\n")
    
#     def show_tables(self):
#         """Affiche les tables de la base courante"""
#         if not self.current_db:
#             print("\n⚠️  No database selected")
#             return
        
#         # db = self.databases[self.
