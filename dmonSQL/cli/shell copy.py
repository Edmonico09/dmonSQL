# ============================================================================
# dmonSQL/cli/shell.py
# ============================================================================
"""Shell interactif dmonSQL"""

import sys
import os
from pathlib import Path

# Ajouter le chemin parent au PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dmonSQL.dmonsql_main import DmonSQL
from dmonSQL.utils.logger import get_logger


class DmonSQLShell:
    """Shell interactif pour dmonSQL"""
    
    def __init__(self, data_dir: str = "./dmonsql_data"):
        self.db = DmonSQL(data_dir)
        self.logger = get_logger("dmonSQL.shell")
        self.running = True
        self.history = []
    
    def print_banner(self):
        """Affiche la bannière de démarrage"""
        banner = """
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║               ██████╗ ███╗   ███╗ ██████╗ ███╗   ██╗     ║
    ║               ██╔══██╗████╗ ████║██╔═══██╗████╗  ██║     ║
    ║               ██║  ██║██╔████╔██║██║   ██║██╔██╗ ██║     ║
    ║               ██║  ██║██║╚██╔╝██║██║   ██║██║╚██╗██║     ║
    ║               ██████╔╝██║ ╚═╝ ██║╚██████╔╝██║ ╚████║     ║
    ║               ╚═════╝ ╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═══╝     ║
    ║                         SQL                               ║
    ║              Version 2.0.0                                ║
    ║      Système de Gestion de Base de Données Relationnelle ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
        """
        print(banner)
        print("\nBienvenue dans dmonSQL!")
        print("Tapez 'HELP' pour l'aide, 'EXIT' pour quitter\n")
    
    def print_help(self):
        """Affiche l'aide"""
        help_text = """
╔══════════════════════════════════════════════════════════════════════╗
║                        COMMANDES dmonSQL                             ║
╚══════════════════════════════════════════════════════════════════════╝

📁 GESTION DES BASES DE DONNÉES
  CREATE DATABASE <nom>           - Créer une base de données
  DROP DATABASE <nom>             - Supprimer une base de données
  USE <nom>                       - Utiliser une base de données
  SHOW DATABASES                  - Lister les bases de données

📊 GESTION DES TABLES
  CREATE TABLE <nom> (...)        - Créer une table
  DROP TABLE <nom>                - Supprimer une table
  SHOW TABLES                     - Lister les tables
  DESCRIBE <table>                - Afficher la structure d'une table

📝 MANIPULATION DES DONNÉES
  INSERT INTO <table> (...)       - Insérer des données
  SELECT ... FROM <table>         - Interroger
  UPDATE <table> SET ...          - Mettre à jour
  DELETE FROM <table> WHERE ...   - Supprimer

🔍 REQUÊTES AVANCÉES
  SELECT ... WHERE ...            - Filtrage
  SELECT ... ORDER BY ...         - Tri
  SELECT ... LIMIT n              - Limitation
  SELECT ... GROUP BY ...         - Regroupement
  SELECT ... HAVING ...           - Filtrage de groupes

🔧 UTILITAIRES
  CLEAR                           - Effacer l'écran
  HISTORY                         - Afficher l'historique
  HELP                            - Afficher cette aide
  EXIT                            - Quitter

💡 TYPES AVANCÉS
  MATRIX                          - Matrices NumPy
  EMAIL                           - Emails validés
  JSON                            - Documents JSON

╚══════════════════════════════════════════════════════════════════════╝
        """
        print(help_text)
    
    def execute_command(self, command: str):
        """Exécute une commande"""
        command = command.strip()
        
        if not command:
            return
        
        # Ajouter à l'historique
        self.history.append(command)
        
        # Commandes spéciales
        cmd_upper = command.upper()
        
        if cmd_upper == 'EXIT' or cmd_upper == 'QUIT':
            self.running = False
            print("\nAu revoir! 👋")
            return
        
        if cmd_upper == 'HELP':
            self.print_help()
            return
        
        if cmd_upper == 'CLEAR' or cmd_upper == 'CLS':
            os.system('clear' if os.name == 'posix' else 'cls')
            self.print_banner()
            return
        
        if cmd_upper == 'HISTORY':
            print("\n📜 Historique des commandes:")
            for i, cmd in enumerate(self.history[-20:], 1):
                print(f"  {i}. {cmd}")
            return
        
        if cmd_upper == 'SHOW DATABASES':
            self.db.show_databases()
            return
        
        if cmd_upper == 'SHOW TABLES':
            self.db.show_tables()
            return
        
        if cmd_upper.startswith('DESCRIBE '):
            table_name = command.split()[1]
            self.describe_table(table_name)
            return
        
        # Exécuter la commande SQL
        try:
            result = self.db.execute(command)
            
            # Si c'est un SELECT qui retourne un résultat, il est déjà affiché
            # par la méthode execute
            
        except Exception as e:
            print(f"❌ Erreur: {e}")
            self.logger.error(f"Error executing command: {e}")
    
    def describe_table(self, table_name: str):
        """Affiche la structure d'une table"""
        try:
            if not self.db.current_db:
                print("❌ Aucune base de données sélectionnée")
                return
            
            db = self.db.databases[self.db.current_db]
            table = db.get_table(table_name)
            
            print(f"\n📊 Structure de la table '{table_name}':")
            print("-" * 80)
            print(f"{'Colonne':<20} {'Type':<15} {'Null':<8} {'Clé':<10} {'Extra'}")
            print("-" * 80)
            
            for col_name, col in table.columns.items():
                null_str = "OUI" if col.nullable else "NON"
                key_str = "PRI" if col.primary_key else ("UNI" if col.unique else "")
                extra_str = "auto_increment" if col.auto_increment else ""
                
                type_str = col.dtype
                if col.length:
                    type_str += f"({col.length})"
                
                print(f"{col_name:<20} {type_str:<15} {null_str:<8} {key_str:<10} {extra_str}")
            
            print("-" * 80)
            print(f"{len(table.columns)} colonne(s)")
            print(f"{len(table.rows)} ligne(s) de données")
            
            if table.indexes:
                print(f"\n🔍 Index:")
                for idx_name, idx in table.indexes.items():
                    idx_type = "UNIQUE" if idx.unique else "INDEX"
                    print(f"  {idx_type}: {idx_name} sur {', '.join(idx.columns)}")
        
        except Exception as e:
            print(f"❌ Erreur: {e}")
    
    def run(self):
        """Lance le shell interactif"""
        self.print_banner()
        
        while self.running:
            try:
                # Afficher le prompt
                prompt = f"{self.db.current_db or 'dmonSQL'}> "
                command = input(prompt).strip()
                
                if command:
                    self.execute_command(command)
                
            except KeyboardInterrupt:
                print("\n\n💡 Utilisez EXIT pour quitter proprement")
                continue
            
            except EOFError:
                print("\n\nAu revoir! 👋")
                break
