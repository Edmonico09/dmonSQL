"""
dmonSQL - Système de Gestion de Base de Données Relationnelle
Version 2.0.0 - Architecture modulaire refactorisée
"""

import re
from datetime import datetime
from typing import Any, List, Dict
from pathlib import Path

# Imports des modules dmonSQL core
from dmonSQL.storage.file_manager import FileManager
from dmonSQL.storage.serializer import DatabaseSerializer
from dmonSQL.utils.logger import get_logger
from dmonSQL.utils.helpers import format_size
from dmonSQL.query.parser import QueryParser
from dmonSQL.core.database import Database

# Moteurs de requêtes
from dmonSQL.query.executor import SQLExecutor
from dmonSQL.query.aggregations import AggregationEngine

# Fonctionnalités avancées (P3/P4)
try:
    from dmonSQL.query.p3_p4_features import (
        ViewManager, SequenceManager, QueryExplainer,
        StringFunctions, DateTimeFunctions, JSONFunctions
    )
    P3_P4_AVAILABLE = True
except ImportError:
    P3_P4_AVAILABLE = False

# Transaction manager (optionnel)
try:
    from dmonSQL.core.transaction_manager import TransactionManager
    TRANSACTIONS_AVAILABLE = True
except ImportError:
    TRANSACTIONS_AVAILABLE = False


class DmonSQL:
    """Système de gestion de base de données principal - Version modulaire"""
    
    def __init__(self, data_dir: str = "./dmonsql_data"):
        """
        Initialise le système dmonSQL
        
        Args:
            data_dir: Répertoire de stockage des données
        """
        self.data_dir = Path(data_dir)
        self.databases = {}
        self.current_db = None
        
        # Initialiser les gestionnaires de base
        self.file_manager = FileManager(str(self.data_dir))
        self.serializer = DatabaseSerializer(self.file_manager)
        self.logger = get_logger("dmonSQL")
        self.parser = QueryParser()
        
        # ✨ Gestionnaire d'exécution principal (délégation)
        self.executor = SQLExecutor(self)
        
        # Moteurs avancés
        self.aggregation_engine = AggregationEngine()
        
        # Fonctionnalités P3/P4 (optionnelles)
        if P3_P4_AVAILABLE:
            self.view_manager = ViewManager(self)
            self.sequence_manager = SequenceManager()
            self.query_explainer = QueryExplainer(self)
            self.functions = self._register_functions()
        
        # Transaction manager (optionnel)
        if TRANSACTIONS_AVAILABLE:
            self.transaction_manager = TransactionManager()
            self.logger.info("Transaction manager initialized")
        else:
            self.transaction_manager = None
        
        # Charger les bases de données existantes
        self.load_databases()
        
        self.logger.info(f"dmonSQL initialized with data directory: {self.data_dir}")
    
    def _register_functions(self) -> Dict:
        """Enregistre les fonctions SQL disponibles (P3/P4)"""
        return {
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
    
    # ==================== API PUBLIQUE ====================
    
    def execute(self, sql: str) -> Any:
        """
        Exécute une requête SQL
        
        Args:
            sql: Requête SQL à exécuter
            
        Returns:
            Résultat de la requête
        
        Exemples:
            db.execute("CREATE DATABASE test")
            db.execute("USE test")
            db.execute("CREATE TABLE users (id INT, name VARCHAR(50))")
            db.execute("INSERT INTO users VALUES (1, 'Alice')")
            result = db.execute("SELECT * FROM users")
        """
        return self.executor.execute(sql)
    
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
    
    # ==================== AFFICHAGE ====================
    
    def show_databases(self):
        """Affiche les bases de données"""
        if not self.databases:
            print("\n📭 No databases found")
            return
        
        print(f"\n📚 Databases ({len(self.databases)}):")
        print("-" * 60)
        
        for db_name in sorted(self.databases.keys()):
            current = "◀" if db_name == self.current_db else " "
            db = self.databases[db_name]
            table_count = len(db.tables)
            db_size = self.file_manager.get_database_size(db_name)
            size_str = format_size(db_size) if db_size > 0 else "N/A"
            
            print(f"{current} {db_name:<20} ({table_count} tables, {size_str})")
        
        print("-" * 60 + "\n")
    
    def show_tables(self):
        """Affiche les tables de la base courante"""
        if not self.current_db:
            print("\n⚠️  No database selected")
            return
        
        db = self.databases[self.current_db]
        
        if not db.tables:
            print(f"\n📭 No tables in database '{self.current_db}'")
            return
        
        print(f"\n📊 Tables in '{self.current_db}' ({len(db.tables)}):")
        print("-" * 80)
        print(f"{'Table':<20} {'Rows':<10} {'Columns':<10} {'Indexes':<10} {'Size'}")
        print("-" * 80)
        
        for table_name in sorted(db.tables.keys()):
            table = db.tables[table_name]
            stats = table.get_statistics()
            size_str = format_size(stats['size_estimate'])
            
            print(f"{table_name:<20} {stats['rows']:<10} {stats['columns']:<10} "
                  f"{stats['indexes']:<10} {size_str}")
        
        print("-" * 80 + "\n")
    
    def _show_statistics(self, db):
        """Affiche les statistiques de la base"""
        stats = db.get_statistics()
        
        print(f"\n📊 Database Statistics: {db.name}")
        print("=" * 60)
        print(f"  Tables:         {stats['tables']}")
        print(f"  Total rows:     {stats['total_rows']:,}")
        print(f"  Total indexes:  {stats['total_indexes']}")
        print(f"  Created:        {stats['created_at'][:19]}")
        print(f"  Last modified:  {stats['last_modified'][:19]}")
        
        db_size = self.file_manager.get_database_size(db.name)
        if db_size > 0:
            print(f"  Size on disk:   {format_size(db_size)}")
        
        print("\n  Tables Overview:")
        print("  " + "-" * 56)
        
        for table_name, table in db.tables.items():
            table_stats = table.get_statistics()
            print(f"    • {table_name:<20} {table_stats['rows']} rows, "
                  f"{table_stats['indexes']} indexes")
        
        print("=" * 60 + "\n")
    
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
        """Formate une valeur pour l'affichage"""
        if value is None:
            return "NULL"
        elif isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, str):
            return value
        elif isinstance(value, (list, dict)):
            import json
            try:
                return json.dumps(value, ensure_ascii=False)
            except:
                return str(value)
        elif hasattr(value, '__class__'):
            class_name = value.__class__.__name__
            if hasattr(value, 'shape'):
                return f"{class_name}{getattr(value, 'shape', '')}"
            elif hasattr(value, '__str__'):
                return str(value)
            else:
                return class_name
        else:
            return str(value)
    
    # ==================== MÉTHODES POUR VUES ET EXPLAIN (P3/P4) ====================
    
    def _execute_create_view(self, sql: str):
        """Exécute CREATE VIEW"""
        if not P3_P4_AVAILABLE:
            raise ValueError("Views not available (p3_p4_features module not found)")
        
        if not self.current_db:
            raise ValueError("No database selected")
        
        pattern = r'CREATE\s+VIEW\s+(\w+)\s+(?:AS\s+)?(.*)'
        match = re.match(pattern, sql, re.IGNORECASE | re.DOTALL)
        
        if not match:
            raise ValueError("Invalid CREATE VIEW syntax")
        
        view_name = match.group(1)
        view_query = match.group(2).strip()
        
        self.view_manager.create_view(view_name, view_query)
        print(f"✓ View '{view_name}' created")
    
    def _execute_drop_view(self, sql: str):
        """Exécute DROP VIEW"""
        if not P3_P4_AVAILABLE:
            raise ValueError("Views not available")
        
        match = re.match(r'DROP\s+VIEW\s+(\w+)', sql, re.IGNORECASE)
        if not match:
            raise ValueError("Invalid DROP VIEW syntax")
        
        view_name = match.group(1)
        self.view_manager.drop_view(view_name)
        print(f"✓ View '{view_name}' dropped")
    
    def _execute_show_views(self):
        """Affiche les vues disponibles"""
        if not P3_P4_AVAILABLE:
            print("\n📭 Views not available")
            return
        
        views = self.view_manager.list_views()
        
        if not views:
            print("\n📭 No views found")
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
        if not P3_P4_AVAILABLE:
            raise ValueError("EXPLAIN not available")
        
        analyze = 'ANALYZE' in sql.upper()
        
        if analyze:
            query = sql.replace('EXPLAIN ANALYZE', '').strip()
        else:
            query = sql.replace('EXPLAIN', '').strip()
        
        plan = self.query_explainer.explain(query, analyze=analyze)
        self.query_explainer.print_plan(plan)
        return plan


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


# if __name__ == "__main__":
#     main()