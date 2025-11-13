"""
dmonSQL - Système de Gestion de Base de Données Relationnelle
Version 2.0.0 - Améliorée avec intégration complète des modules
"""
import re
from datetime import datetime
from typing import Any, List, Dict, Tuple
from pathlib import Path

# Imports des modules dmonSQL
from dmonSQL.types.matrixType import MatrixType
from dmonSQL.types.email_type import EmailType
from dmonSQL.types.json_type import JSONType
from dmonSQL.core.column import Column
from dmonSQL.core.index import Index

from dmonSQL.core.table import Table                     # <-- Import propre
from dmonSQL.core.constraint import ConstraintManager, NotNullConstraint
from dmonSQL.storage.file_manager import FileManager
from dmonSQL.storage.serializer import DatabaseSerializer
from dmonSQL.utils.logger import get_logger
from dmonSQL.utils.helpers import format_size, format_duration
from dmonSQL.query.parser import QueryParser

# Imports optionnels (avec gestion d'erreur)
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


class Database:
    """Base de données améliorée"""
    def __init__(self, name: str):
        self.name = name
        self.tables = {}
        self.created_at = datetime.now()
        self.last_modified = datetime.now()

        # Gestionnaires optionnels
        if PROCEDURES_AVAILABLE:
            self.procedure_manager = ProcedureManager()
        if TRIGGERS_AVAILABLE:
            self.trigger_manager = TriggerManager()

    def create_table(self, table: Table):
        """Crée une table"""
        if table.name in self.tables:
            raise ValueError(f"Table {table.name} already exists")
        self.tables[table.name] = table
        self.last_modified = datetime.now()
        get_logger().info(f"Table '{table.name}' created in database '{self.name}'")

    def drop_table(self, table_name: str):
        """Supprime une table"""
        if table_name not in self.tables:
            raise ValueError(f"Table {table_name} does not exist")
        del self.tables[table_name]
        self.last_modified = datetime.now()
        get_logger().info(f"Table '{table_name}' dropped from database '{self.name}'")

    def get_table(self, table_name: str) -> Table:
        """Récupère une table"""
        if table_name not in self.tables:
            raise ValueError(f"Table {table_name} does not exist")
        return self.tables[table_name]

    def get_statistics(self) -> Dict:
        """Retourne les statistiques de la base"""
        total_rows = sum(len(table.rows) for table in self.tables.values())
        total_indexes = sum(len(table.indexes) for table in self.tables.values())
        return {
            'name': self.name,
            'tables': len(self.tables),
            'total_rows': total_rows,
            'total_indexes': total_indexes,
            'created_at': self.created_at.isoformat(),
            'last_modified': self.last_modified.isoformat()
        }


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
        print(f"Database '{name}' created successfully")

    def drop_database(self, name: str):
        """Supprime une base de données"""
        if name not in self.databases:
            raise ValueError(f"Database {name} does not exist")
        del self.databases[name]
        self.file_manager.delete_database(name)
        self.logger.info(f"Database '{name}' dropped")
        print(f"Database '{name}' dropped successfully")

    def use_database(self, name: str):
        """Sélectionne une base de données"""
        if name not in self.databases:
            raise ValueError(f"Database {name} does not exist")
        self.current_db = name
        self.logger.info(f"Using database '{name}'")
        print(f"Using database '{name}'")

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

        # CREATE TABLE
        if sql_upper.startswith('CREATE TABLE'):
            table_name, columns = self.parser.parse_create_table(sql)
            table = Table(table_name, columns)
            db.create_table(table)
            self.save_database(self.current_db)
            print(f"Table '{table_name}' created successfully")
            return

        # DROP TABLE
        if sql_upper.startswith('DROP TABLE'):
            match = re.match(r'DROP\s+TABLE\s+(\w+)', sql, re.IGNORECASE)
            if match:
                table_name = match.group(1)
                db.drop_table(table_name)
                self.save_database(self.current_db)
                print(f"Table '{table_name}' dropped successfully")
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
                print(f"Index '{index_name}' created successfully")
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

            # SAUVEGARDE + AFFICHAGE UNIQUEMENT APRÈS TOUTES LES INSERTIONS
            self.save_database(self.current_db)
            print(f"Inserted {inserted_count} row(s)")
            return inserted_count

        # SELECT
        if sql_upper.startswith('SELECT'):
            return self._execute_select(sql, db)

        # UPDATE
        if sql_upper.startswith('UPDATE'):
            return self._execute_update(sql, db)

        # DELETE
        if sql_upper.startswith('DELETE'):
            match = re.match(r'DELETE\s+FROM\s+(\w+)(?:\s+WHERE\s+(.*))?', sql, re.IGNORECASE)
            if not match:
                raise ValueError("Invalid DELETE syntax. Use: DELETE FROM table WHERE condition")
            table_name = match.group(1)
            where_clause = match.group(2)
            table = db.get_table(table_name)
            where_func = self._parse_where(where_clause) if where_clause else None
            count = table.delete(where=where_func)
            self.save_database(self.current_db)
            print(f"Deleted {count} row(s)")
            return count

        # SHOW STATS
        if sql_upper == 'SHOW STATS':
            self._show_statistics(db)
            return

        raise ValueError(f"Unsupported SQL statement: {sql}")

    def _execute_select(self, sql: str, db: Database):
        """Exécute un SELECT"""
        match = re.match(r'SELECT\s+(.*?)\s+FROM\s+(\w+)(?:\s+WHERE\s+(.*))?',
                         sql, re.IGNORECASE)
        if not match:
            raise ValueError("Invalid SELECT syntax")
        columns_str = match.group(1).strip()
        table_name = match.group(2)
        where_clause = match.group(3)
        table = db.get_table(table_name)
        columns = None if columns_str == '*' else [c.strip() for c in columns_str.split(',')]
        where_func = self._parse_where(where_clause) if where_clause else None
        result = table.select(columns=columns, where=where_func)
        self._print_result(result)
        return result

    def _execute_update(self, sql: str, db: Database):
        """Exécute un UPDATE"""
        match = re.match(r'UPDATE\s+(\w+)\s+SET\s+(.*?)(?:\s+WHERE\s+(.*))?',
                         sql, re.IGNORECASE)
        if not match:
            raise ValueError("Invalid UPDATE syntax")
        table_name = match.group(1)
        set_clause = match.group(2)
        where_clause = match.group(3)
        table = db.get_table(table_name)

        values = {}
        for assignment in set_clause.split(','):
            col, val = assignment.split('=')
            col = col.strip()
            val = val.strip().strip("'")
            values[col] = val

        where_func = self._parse_where(where_clause) if where_clause else None
        count = table.update(values, where=where_func)
        self.save_database(self.current_db)
        print(f"{count} row(s) updated")
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
        where_func = self._parse_where(where_clause) if where_clause else None
        count = table.delete(where=where_func)
        self.save_database(self.current_db)
        print(f"{count} row(s) deleted")
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
            print("\nEmpty set (0 rows)")
            return

        columns = list(result[0].keys())
        col_widths = {col: max(len(col), 15) for col in columns}
        for row in result[:10]:
            for col in columns:
                val = str(row.get(col, ''))[:50]
                col_widths[col] = max(col_widths[col], len(val))

        header = " | ".join(f"{col:<{col_widths[col]}}" for col in columns)
        print(f"\n{header}")
        print("-" * len(header))

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

        print(f"\n{len(result)} row(s)) in set\n")

    def _show_statistics(self, db: Database):
        """Affiche les statistiques de la base"""
        stats = db.get_statistics()
        print(f"\nDatabase Statistics: {db.name}")
        print("=" * 60)
        print(f"Tables: {stats['tables']}")
        print(f"Total rows: {stats['total_rows']:,}")
        print(f"Total indexes: {stats['total_indexes']}")
        print(f"Created: {stats['created_at']}")
        print(f"Last modified: {stats['last_modified']}")

        db_size = self.file_manager.get_database_size(db.name)
        if db_size > 0:
            print(f"Size on disk: {format_size(db_size)}")

        print("\nTables:")
        for table_name, table in db.tables.items():
            table_stats = table.get_statistics()
            print(f" • {table_name}: {table_stats['rows']} rows, "
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
                self.databases[db_name] = self.serializer.load_database(db_name)
                self.logger.debug(f"Database '{db_name}' loaded")
            except Exception as e:
                self.logger.warning(f"Could not load database '{db_name}': {e}")

    def show_databases(self):
        """Affiche les bases de données"""
        if not self.databases:
            print("\nNo databases found")
            return
        print(f"\nDatabases ({len(self.databases)}):")
        print("-" * 60)
        for db_name in sorted(self.databases.keys()):
            current = "current" if db_name == self.current_db else " "
            db_size = self.file_manager.get_database_size(db_name)
            size_str = format_size(db_size) if db_size > 0 else "N/A"
            db = self.databases[db_name]
            table_count = len(db.tables)
            print(f" {current} {db_name:<20} ({table_count} tables, {size_str})")
        print("-" * 60 + "\n")

    def show_tables(self):
        """Affiche les tables de la base courante"""
        if not self.current_db:
            print("\nNo database selected")
            return
        db = self.databases[self.current_db]
        if not db.tables:
            print(f"\nNo tables in database '{self.current_db}'")
            return
        print(f"\nTables in '{self.current_db}' ({len(db.tables)}):")
        print("-" * 80)
        print(f"{'Table':<20} {'Rows':<12} {'Columns':<12} {'Indexes':<12} {'Size (est.)'}")
        print("-" * 80)
        for table_name in sorted(db.tables.keys()):
            table = db.tables[table_name]
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
                row_export = {}
                for col, val in row.items():
                    if isinstance(val, (MatrixType, EmailType, JSONType)):
                        row_export[col] = str(val)
                    else:
                        row_export[col] = val
                writer.writerow(row_export)
        print(f"Table '{table_name}' exported to '{output_file}'")
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
                filtered_row = {k: v for k, v in row.items() if k in table.columns}
                table.insert(filtered_row)
                count += 1
        self.save_database(self.current_db)
        print(f"{count} row(s) imported into '{table_name}'")
        self.logger.info(f"{count} rows imported from CSV: {input_file}")

    def backup_database(self, db_name: str, backup_path: str = None):
        """Crée une sauvegarde d'une base de données"""
        if db_name not in self.databases:
            raise ValueError(f"Database {db_name} does not exist")
        if backup_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{db_name}_backup_{timestamp}.dmon"
        import shutil
        self.save_database(db_name)
        source = self.file_manager.get_database_path(db_name)
        shutil.copy2(source, backup_path)
        print(f"Database '{db_name}' backed up to '{backup_path}'")
        self.logger.info(f"Database '{db_name}' backed up to: {backup_path}")

    def restore_database(self, backup_path: str, db_name: str = None):
        """Restaure une base de données depuis une sauvegarde"""
        import shutil
        if db_name is None:
            db_name = Path(backup_path).stem.split('_backup_')[0]
        dest = self.file_manager.get_database_path(db_name)
        shutil.copy2(backup_path, dest)
        try:
            self.databases[db_name] = self.serializer.load_database(db_name)
            print(f"Database '{db_name}' restored from '{backup_path}'")
            self.logger.info(f"Database '{db_name}' restored from: {backup_path}")
        except Exception as e:
            self.logger.error(f"Failed to restore database: {e}")
            raise

    def analyze_query(self, sql: str):
        """Analyse une requête SQL et affiche le plan d'exécution"""
        if not OPTIMIZER_AVAILABLE:
            print("Query optimizer not available")
            return
        print(f"\nQuery Analysis:")
        print("=" * 60)
        print(f"Query: {sql}")
        print("-" * 60)
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
        print("\nOptimization Suggestions:")
        if 'SELECT *' in sql_upper:
            print(" • Consider selecting only needed columns instead of SELECT *")
        if 'WHERE' in sql_upper and 'INDEX' not in sql_upper:
            print(" • Consider creating an index on WHERE clause columns")
        if 'ORDER BY' in sql_upper:
            print(" • Consider creating an index on ORDER BY columns")
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
            'constraints': 0  # À implémenter si besoin
        }
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
        print(f"\nExecuting batch of {len(sql_statements)} statements...")
        print("-" * 60)
        for i, sql in enumerate(sql_statements, 1):
            try:
                result = self.execute(sql)
                results.append((i, sql, result, None))
                print(f"Statement {i}/{len(sql_statements)} completed")
            except Exception as e:
                errors.append((i, sql, str(e)))
                print(f"Statement {i}/{len(sql_statements)} failed: {e}")
                if stop_on_error:
                    print("\nBatch execution stopped due to error")
                    break
        print("-" * 60)
        print(f"\nBatch Summary:")
        print(f" Total: {len(sql_statements)}")
        print(f" Successful: {len(results)}")
        print(f" Failed: {len(errors)}")
        if errors:
            print(f"\nErrors:")
            for i, sql, error in errors:
                print(f" Statement {i}: {error}")
        return results, errors

    def vacuum(self):
        """Optimise et compacte la base de données courante"""
        if not self.current_db:
            raise ValueError("No database selected")
        print(f"\nVacuuming database '{self.current_db}'...")
        db = self.databases[self.current_db]
        total_indexes = 0
        for table in db.tables.values():
            for index in table.indexes.values():
                index.build(table.rows)
                total_indexes += 1
        self.save_database(self.current_db)
        print(f"Database vacuumed: {total_indexes} index(es) rebuilt")
        self.logger.info(f"Database '{self.current_db}' vacuumed")

    def explain_table(self, table_name: str):
        """Explique la structure d'une table"""
        info = self.get_table_info(table_name)
        print(f"\nTable: {info['name']}")
        print("=" * 80)
        print(f"\nColumns ({len(info['columns'])}):")
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
            print(f"\nIndexes ({len(info['indexes'])}):")
            print("-" * 80)
            for idx_name, idx_info in info['indexes'].items():
                idx_type = "UNIQUE" if idx_info['unique'] else "INDEX"
                cols = ", ".join(idx_info['columns'])
                print(f" {idx_type}: {idx_name} ON ({cols})")
        stats = info['statistics']
        print(f"\nStatistics:")
        print("-" * 80)
        print(f" Rows: {stats['rows']}")
        print(f" Columns: {stats['columns']}")
        print(f" Indexes: {stats['indexes']}")
        print(f" Estimated size: {format_size(stats['size_estimate'])}")
        print(f" Created: {stats['created_at']}")
        print("=" * 80 + "\n")


# Point d'entrée pour utilisation en ligne de commande
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