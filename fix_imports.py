#!/usr/bin/env python3
"""
Script pour corriger automatiquement tous les imports dmonSQL -> dmonSQL
"""

import os
import re
from pathlib import Path


def fix_imports_in_file(filepath: Path):
    """Corrige les imports dans un fichier"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Remplacements d'imports
        replacements = {
            'from dmonSQL import': 'from dmonSQL import',
            'import dmonSQL': 'import dmonSQL',
            'from dmonSQL.': 'from dmonSQL.',
            'dmonSQL.': 'dmonSQL.',
            'DmonSQL': 'DmonSQL',
            'dmonSQL': 'dmonSQL',
        }
        
        for old, new in replacements.items():
            content = content.replace(old, new)
        
        # Corrections spécifiques pour les bytes strings
        # Remplacer b"texte avec accents" par b"texte sans accents" ou "texte".encode('utf-8')
        
        # Pattern pour bytes strings avec caractères non-ASCII
        content = re.sub(
            r'b"([^"]*[éèêëàâäùûüôöîïç][^"]*)"',
            lambda m: '"' + m.group(1) + '".encode(\'utf-8\')',
            content,
            flags=re.IGNORECASE
        )
        
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✓ Corrigé: {filepath}")
            return True
        
        return False
    
    except Exception as e:
        print(f"✗ Erreur dans {filepath}: {e}")
        return False


def fix_all_files(root_dir: str = "."):
    """Corrige tous les fichiers Python dans le répertoire"""
    root = Path(root_dir)
    
    # Fichiers à corriger
    patterns = ['**/*.py']
    
    fixed_count = 0
    total_count = 0
    
    for pattern in patterns:
        for filepath in root.glob(pattern):
            # Ignorer venv et __pycache__
            if 'venv' in str(filepath) or '__pycache__' in str(filepath):
                continue
            
            total_count += 1
            if fix_imports_in_file(filepath):
                fixed_count += 1
    
    print(f"\n✓ {fixed_count}/{total_count} fichiers corrigés")


def create_missing_init_files(root_dir: str = "."):
    """Crée les __init__.py manquants"""
    root = Path(root_dir)
    
    # Dossiers qui doivent avoir un __init__.py
    python_dirs = [
        'dmonSQL',
        'dmonSQL/core',
        'dmonSQL/types',
        'dmonSQL/query',
        'dmonSQL/algebra',
        'dmonSQL/storage',
        'dmonSQL/transaction',
        'dmonSQL/procedures',
        'dmonSQL/replication',
        'dmonSQL/network',
        'dmonSQL/security',
        'dmonSQL/utils',
        'dmonSQL/cli',
        'tests',
        'tests/test_core',
        'tests/test_types',
        'tests/test_query',
        'tests/test_algebra',
        'tests/test_transaction',
        'tests/test_procedures',
    ]
    
    created = 0
    for dir_path in python_dirs:
        full_path = root / dir_path
        if full_path.exists():
            init_file = full_path / '__init__.py'
            if not init_file.exists():
                init_file.write_text(f'"""{dir_path} package"""\n')
                print(f"✓ Créé: {init_file}")
                created += 1
    
    print(f"\n✓ {created} fichiers __init__.py créés")


def fix_specific_errors():
    """Corrige des erreurs spécifiques"""
    print("\nCorrection des erreurs spécifiques...")
    
    # 1. Corriger encryption.py ligne 261
    enc_file = Path('dmonSQL/storage/encryption.py')
    if enc_file.exists():
        with open(enc_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        if len(lines) > 260:
            # Corriger la ligne 261 (index 260)
            if 'Données confidentielles' in lines[260]:
                lines[260] = '    secret_data = "Donnees confidentielles: numero de compte 123456789".encode(\'utf-8\')\n'
                
                with open(enc_file, 'w', encoding='utf-8') as f:
                    f.writelines(lines)
                print(f"✓ Corrigé: {enc_file} ligne 261")
    
    # 2. Corriger complete_demo.py
    demo_file = Path('examples/complete_demo.py')
    if demo_file.exists():
        with open(demo_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Remplacer les bytes strings problématiques
        content = content.replace(
            '"DmonSQL est un système',
            '".encode('utf-8')dmonSQL est un systeme'
        )
        
        content = content.replace(
            '"Données ultra-confidentielles".encode('utf-8')',
            '"Donnees ultra-confidentielles".encode(\'utf-8\')'
        )
        
        with open(demo_file, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✓ Corrigé: {demo_file}")


def add_missing_imports():
    """Ajoute les imports manquants dans les fichiers"""
    print("\nAjout des imports manquants...")
    
    # dmonSQL/__init__.py - Ajouter les imports conditionnels
    init_file = Path('dmonSQL/__init__.py')
    if init_file.exists():
        with open(init_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Vérifier si les imports existent
        if 'try:' not in content:
            # Ajouter les imports avec gestion d'erreur
            additional_imports = '''
# Imports conditionnels (modules optionnels)
try:
    from dmonSQL.transaction.transaction_manager import (
        TransactionManager,
        TransactionContext,
        IsolationLevel
    )
except ImportError:
    TransactionManager = None
    TransactionContext = None
    IsolationLevel = None

try:
    from dmonSQL.procedures.procedure import (
        StoredProcedure,
        StoredFunction,
        ProcedureManager
    )
except ImportError:
    StoredProcedure = None
    StoredFunction = None
    ProcedureManager = None

try:
    from dmonSQL.procedures.trigger import (
        Trigger,
        TriggerManager
    )
except ImportError:
    Trigger = None
    TriggerManager = None
'''
            
            # Insérer après les imports existants
            lines = content.split('\n')
            insert_pos = next((i for i, line in enumerate(lines) if line.startswith('# Exports')), len(lines))
            lines.insert(insert_pos, additional_imports)
            
            with open(init_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
            
            print(f"✓ Imports ajoutés: {init_file}")


def main():
    """Fonction principale"""
    print("="*70)
    print(" "*20 + "Correction des erreurs dmonSQL")
    print("="*70 + "\n")
    
    print("1. Création des fichiers __init__.py manquants...")
    create_missing_init_files()
    
    print("\n2. Correction des imports dmonSQL -> dmonSQL...")
    fix_all_files()
    
    print("\n3. Correction des erreurs spécifiques...")
    fix_specific_errors()
    
    print("\n4. Ajout des imports manquants...")
    add_missing_imports()
    
    print("\n" + "="*70)
    print("✅ Toutes les corrections appliquées!")
    print("="*70)
    
    print("""
📋 Prochaines étapes:

1. Vérifier que tous les fichiers sont présents
2. Exécuter: pip install -r requirements.txt
3. Exécuter: pip install -e .
4. Tester: python -m dmonSQL.cli.shell

🔧 Si des erreurs persistent:
   - Vérifier les imports dans les fichiers signalés
   - Vérifier que tous les modules sont dans le bon dossier
   - Relancer ce script avec: python fix_imports.py
""")


if __name__ == "__main__":
    main()