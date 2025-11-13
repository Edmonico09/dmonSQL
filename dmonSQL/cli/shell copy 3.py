# ============================================================================
# dmonSQL/cli/shell.py
# ============================================================================
"""Shell interactif dmonSQL avec support DELIMITER"""

import sys
import os
from pathlib import Path

# Ajouter le chemin parent au PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dmonSQL.dmonsql_main import DmonSQL
from dmonSQL.utils.logger import get_logger

try:
    import readline
    READLINE_AVAILABLE = True
except ImportError:
    READLINE_AVAILABLE = False

print(f'READLINE : {READLINE_AVAILABLE}')

class DmonSQLCompleter:
    """Autocomplétion pour le shell dmonSQL"""
    
    def __init__(self, db_system):
        self.db_system = db_system
        
        # Mots-clés SQL
        self.keywords = [
            'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'ALTER',
            'FROM', 'WHERE', 'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER',
            'ON', 'GROUP', 'BY', 'ORDER', 'HAVING', 'LIMIT', 'OFFSET',
            'INTO', 'VALUES', 'SET', 'TABLE', 'DATABASE', 'INDEX',
            'PRIMARY', 'KEY', 'FOREIGN', 'REFERENCES', 'UNIQUE',
            'NOT', 'NULL', 'DEFAULT', 'AUTO_INCREMENT',
            'INT', 'FLOAT', 'VARCHAR', 'TEXT', 'DATE', 'DATETIME', 'BOOLEAN',
            'AND', 'OR', 'IN', 'LIKE', 'BETWEEN', 'IS',
            'COUNT', 'SUM', 'AVG', 'MIN', 'MAX',
            'ASC', 'DESC', 'DISTINCT', 'AS', 'DELIMITER',
            'BEGIN', 'END', 'IF', 'THEN', 'ELSE', 'ELSEIF', 'WHILE', 'LOOP',
            'PROCEDURE', 'FUNCTION', 'TRIGGER', 'BEFORE', 'AFTER'
        ]
        
        # Commandes spéciales
        self.commands = [
            'help', 'exit', 'quit', 'clear', 'cls',
            'show databases', 'show tables', 'show indexes',
            'use', 'desc', 'describe', 'status', 'source',
            '.help', '.exit', '.quit', '.clear', '.tables', '.databases'
        ]
        
        self.matches = []
    
    def complete(self, text, state):
        """Fonction de complétion pour readline"""
        if state == 0:
            # Première fois, générer les correspondances
            if text:
                # Complétion des mots-clés SQL
                self.matches = [
                    kw for kw in self.keywords 
                    if kw.startswith(text.upper())
                ]
                
                # Complétion des commandes
                self.matches.extend([
                    cmd for cmd in self.commands 
                    if cmd.startswith(text.lower())
                ])
                
                # Complétion des noms de tables
                if self.db_system.current_db:
                    db = self.db_system.databases[self.db_system.current_db]
                    tables = list(db.tables.keys())
                    self.matches.extend([
                        table for table in tables 
                        if table.startswith(text.lower())
                    ])
                
                # Complétion des noms de bases
                databases = list(self.db_system.databases.keys())
                self.matches.extend([
                    db for db in databases 
                    if db.startswith(text.lower())
                ])
            else:
                self.matches = []
        
        try:
            return self.matches[state]
        except IndexError:
            return None

class DmonSQLShell:
    """Shell interactif pour dmonSQL avec support DELIMITER"""
    
    def __init__(self, data_dir: str = "./dmonsql_data"):
        self.db = DmonSQL(data_dir)
        self.logger = get_logger("dmonSQL.shell")
        self.running = True
        self.history = []
        
        self.history_file = Path.home() / '.dmonsql_history'
        self.multiline_buffer = []
        self.in_multiline = False
        
        # Support DELIMITER
        self.delimiter = ";"
        self.statement_buffer = []
        
        if READLINE_AVAILABLE:
            self.setup_readline()
            
    def setup_readline(self):
        """Configure readline pour l'autocomplétion et l'historique"""
        # Autocomplétion
        completer = DmonSQLCompleter(self.db)
        readline.set_completer(completer.complete)
        
        # Touches pour complétion (Tab)
        if sys.platform == 'win32':
            readline.parse_and_bind('tab: complete')
        else:
            readline.parse_and_bind('tab: complete')
            readline.parse_and_bind('set editing-mode emacs')
        
        # Charger l'historique
        if self.history_file.exists():
            try:
                readline.read_history_file(str(self.history_file))
            except:
                pass
        
        # Limiter la taille de l'historique
        readline.set_history_length(1000)
        
        print("✓ Autocomplétion activée (utilisez Tab)")
        print("✓ Historique activé (utilisez ↑ et ↓)")
    
    def save_history(self):
        """Sauvegarde l'historique"""
        if READLINE_AVAILABLE:
            try:
                readline.write_history_file(str(self.history_file))
            except:
                pass   
    
    def print_banner(self):
        """Affiche la bannière de démarrage"""
        banner = """
    ╔═══════════════════════════════════════════════════════════╗
   ╔╠═══════════════════════════════════════════════════════════╣╗
   ║╚╗                                                              ╚║╗
   ║╔╝                                                               ╚╗║
   ╚║╗                                                                ║║
    ║║             ╔█▌ ███▌   ███╗     ███╗  ███ ███╗  ███╗    ██╗    ║║
    ║║             ╚╗█ █╔══██  ████╗  ████║ ██╔═══ ██▌ ████╗   ██║    ║║
    ║║               █ █║  ██  ██╔█▌ ██╔██║ ██║    ██▌ ██╔█▌ ╗ ██║    ║║
    ║║               █ █║  ██  ██║╚█ █╔═██║ ██║    ██▌ ██║╚█ ╗ ██║    ║║
    ║║            ╔██▌ ████▌   ██║ ╚ ╚═ ██║ ╚██▌ ███▌  ██║ ╚██▌██║    ║║
    ║║            ╚══╝ ╚═══╝   ╚═╝      ╚═╝  ╚═╝ ╚══╝  ╚═╝   ╚═══╝    ║║
    ║║                         SQL                                    ║║
    ║║              Version 1.0.0                                     ║║
    ║║      Système de Gestion de Base de Données Relationnelle       ║║
    ╚╠═╗                                                              ║║
     ╚╗╚══════════════════════════════════════════════════════════════╝║
      ╚═════════════════════════════════════════════════════════════════
        
    """
        print(banner)
        print("\nBienvenue dans dmonSQL!")
        print("Tapez 'HELP' pour l'aide, 'EXIT' pour quitter")
        print(f"Délimiteur actuel : {self.delimiter}\n")
    
    def print_help(self):
        """Affiche l'aide"""
        help_text = """
╔══════════════════════════════════════════════════════════════════════╗
║                        COMMANDES dmonSQL                             ║
╚══════════════════════════════════════════════════════════════════════╝

📚 GESTION DES BASES DE DONNÉES
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
  DELIMITER <delim>               - Changer le délimiteur (ex: DELIMITER $$)
  CLEAR                           - Effacer l'écran
  HISTORY                         - Afficher l'historique
  HELP                            - Afficher cette aide
  EXIT                            - Quitter

💡 TYPES AVANCÉS
  MATRIX                          - Matrices NumPy
  EMAIL                           - Emails validés
  JSON                            - Documents JSON

📌 EXEMPLE AVEC DELIMITER :
  DELIMITER $$
  CREATE PROCEDURE ma_proc()
  BEGIN
    SELECT * FROM users;
  END$$
  DELIMITER ;

╚══════════════════════════════════════════════════════════════════════╝
        """
        print(help_text)
    
    def change_delimiter(self, new_delimiter: str):
        """Change le délimiteur"""
        if not new_delimiter or len(new_delimiter) > 10:
            print("❌ Délimiteur invalide (max 10 caractères)")
            return
        
        old_delimiter = self.delimiter
        self.delimiter = new_delimiter
        print(f"✓ Délimiteur changé : '{old_delimiter}' → '{self.delimiter}'")
        self.logger.info(f"Delimiter changed to '{self.delimiter}'")
    
    def process_input(self, line: str) -> bool:
        """
        Traite une ligne d'entrée et retourne True si une commande complète doit être exécutée
        """
        line = line.rstrip()
        
        # Vérifier si c'est une commande DELIMITER
        if line.upper().startswith('DELIMITER '):
            new_delim = line.split(None, 1)[1].strip()
            self.change_delimiter(new_delim)
            return False
        
        # Ajouter la ligne au buffer
        self.statement_buffer.append(line)
        
        # Vérifier si la ligne se termine par le délimiteur
        if line.endswith(self.delimiter):
            return True
        
        return False
    
    def get_complete_statement(self) -> str:
        """
        Récupère la commande complète depuis le buffer et le vide
        """
        # Joindre toutes les lignes
        statement = '\n'.join(self.statement_buffer)
        
        # Retirer le délimiteur à la fin
        if statement.endswith(self.delimiter):
            statement = statement[:-len(self.delimiter)].strip()
        
        # Vider le buffer
        self.statement_buffer = []
        
        return statement
    
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
                print(f"  {i}. {cmd[:80]}{'...' if len(cmd) > 80 else ''}")
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
            
        except Exception as e:
            print(f"❌ Error: {e}")
            self.logger.error(f"Error executing command: {e}")
    
    def describe_table(self, table_name: str):
        """Display a table's structure"""
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
            print(f"❌ Error: {e}")
    
    def get_prompt(self) -> str:
        """Retourne le prompt approprié"""
        db_name = self.db.current_db or 'None'
        
        if self.statement_buffer:
            # Mode multi-ligne
            return f"    {'-> ':>len(db_name)+13}"
        else:
            # Prompt normal
            return f"dmonSQL[({db_name})]> "
    
    def run(self):
        """Lance le shell interactif"""
        self.print_banner()
        
        while self.running:
            try:
                # Afficher le prompt approprié
                prompt = self.get_prompt()
                line = input(prompt).strip()
                
                if not line:
                    continue
                
                # Traiter l'entrée
                is_complete = self.process_input(line)
                
                # Si la commande est complète, l'exécuter
                if is_complete:
                    statement = self.get_complete_statement()
                    if statement:
                        self.execute_command(statement)
                
            except KeyboardInterrupt:
                # Annuler la commande en cours
                if self.statement_buffer:
                    print("\n⚠️  Commande annulée")
                    self.statement_buffer = []
                else:
                    print("\n\n💡 Utilisez EXIT pour quitter proprement")
                continue
            
            except EOFError:
                print("\n\nAu revoir! 👋")
                break
        
        # Sauvegarder l'historique à la sortie
        self.save_history()


if __name__ == "__main__":
    shell = DmonSQLShell()
    shell.run()