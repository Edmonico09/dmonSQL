# ============================================================================
# dmonSQL/cli/commands.py
# ============================================================================
"""Commandes CLI pour dmonSQL"""

import argparse
import sys
from pathlib import Path

# Ajouter le chemin parent au PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# from dmonSQL.core.dmonsql_main import DmonSQL
from dmonSQL.dmonsql_main import DmonSQL
from dmonSQL import print_banner, get_version


class CommandHandler:
    """Gestionnaire de commandes CLI"""
    
    def __init__(self):
        self.parser = self.create_parser()
    
    def create_parser(self) -> argparse.ArgumentParser:
        """Crée le parseur d'arguments"""
        parser = argparse.ArgumentParser(
            prog='dmonsql',
            description='dmonSQL - Système de Gestion de Base de Données Relationnelle',
            epilog='Pour plus d\'informations: https://github.com/dmonsql/dmonsql'
        )
        
        parser.add_argument(
            '--version',
            action='version',
            version=f'dmonSQL {get_version()}'
        )
        
        parser.add_argument(
            '--data-dir',
            type=str,
            default='./dmonsql_data',
            help='Répertoire des données (défaut: ./dmonsql_data)'
        )
        
        subparsers = parser.add_subparsers(dest='command', help='Commandes disponibles')
        
        # Commande: shell
        subparsers.add_parser('shell', help='Lancer le shell interactif')
        
        # Commande: execute
        exec_parser = subparsers.add_parser('execute', help='Exécuter une requête SQL')
        exec_parser.add_argument('sql', type=str, help='Requête SQL à exécuter')
        exec_parser.add_argument('--database', type=str, help='Base de données à utiliser')
        
        # Commande: create-db
        create_parser = subparsers.add_parser('create-db', help='Créer une base de données')
        create_parser.add_argument('name', type=str, help='Nom de la base de données')
        
        # Commande: drop-db
        drop_parser = subparsers.add_parser('drop-db', help='Supprimer une base de données')
        drop_parser.add_argument('name', type=str, help='Nom de la base de données')
        
        # Commande: list-db
        subparsers.add_parser('list-db', help='Lister les bases de données')
        
        # Commande: backup
        backup_parser = subparsers.add_parser('backup', help='Sauvegarder une base de données')
        backup_parser.add_argument('name', type=str, help='Nom de la base de données')
        backup_parser.add_argument('--output', type=str, help='Fichier de sortie')
        
        # Commande: import
        import_parser = subparsers.add_parser('import', help='Importer des données depuis un fichier')
        import_parser.add_argument('file', type=str, help='Fichier à importer')
        import_parser.add_argument('--database', type=str, required=True, help='Base de données cible')
        import_parser.add_argument('--table', type=str, required=True, help='Table cible')
        
        return parser
    
    def handle(self, args=None):
        """Traite les arguments de la ligne de commande"""
        parsed_args = self.parser.parse_args(args)
        
        if not parsed_args.command:
            # Pas de commande spécifiée, lancer le shell par défaut
            from dmonSQL.cli.shell import DmonSQLShell
            shell = DmonSQLShell(parsed_args.data_dir)
            shell.run()
            return
        
        # Créer l'instance dmonSQL
        db = DmonSQL(parsed_args.data_dir)
        
        # Traiter la commande
        if parsed_args.command == 'shell':
            from dmonSQL.cli.shell import DmonSQLShell
            shell = DmonSQLShell(parsed_args.data_dir)
            shell.run()
        
        elif parsed_args.command == 'execute':
            if parsed_args.database:
                db.execute(f"USE {parsed_args.database}")
            result = db.execute(parsed_args.sql)
            if result:
                print(result)
        
        elif parsed_args.command == 'create-db':
            db.execute(f"CREATE DATABASE {parsed_args.name}")
        
        elif parsed_args.command == 'drop-db':
            db.execute(f"DROP DATABASE {parsed_args.name}")
        
        elif parsed_args.command == 'list-db':
            db.show_databases()
        
        elif parsed_args.command == 'backup':
            print(f"Backup de '{parsed_args.name}' en cours...")
            # À implémenter
            print("✓ Backup terminé")
        
        elif parsed_args.command == 'import':
            print(f"Import de '{parsed_args.file}' dans {parsed_args.database}.{parsed_args.table}...")
            # À implémenter
            print("✓ Import terminé")
