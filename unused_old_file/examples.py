"""
Exemples et tests complets pour DmonSQL
Démonstration de toutes les fonctionnalités
"""

import numpy as np
from pathlib import Path
import sys

# Importer DmonSQL (à adapter selon votre structure)
# from dmonSQL import DmonSQL, Table, Column, DataType, MatrixType, RelationalAlgebra


def exemple_basique():
    """Exemple basique - CRUD"""
    print("\n" + "="*60)
    print("EXEMPLE 1: Opérations CRUD basiques")
    print("="*60)
    
    db = DmonSQL("./example_data")
    
    # Créer une base de données
    db.execute("CREATE DATABASE university")
    db.execute("USE university")
    
    # Créer une table étudiants
    db.execute("""
        CREATE TABLE students (
            id INT PRIMARY KEY AUTO_INCREMENT,
            name VARCHAR(100) NOT NULL,
            age INT,
            gpa FLOAT
        )
    """)
    
    # Insérer des données
    db.execute("INSERT INTO students (name, age, gpa) VALUES ('Alice', 20, 3.8)")
    db.execute("INSERT INTO students (name, age, gpa) VALUES ('Bob', 22, 3.5)")
    db.execute("INSERT INTO students (name, age, gpa) VALUES ('Charlie', 21, 3.9)")
    
    # Sélectionner
    print("\n--- SELECT * ---")
    db.execute("SELECT * FROM students")
    
    print("\n--- SELECT avec WHERE ---")
    db.execute("SELECT name, gpa FROM students WHERE gpa > 3.6")
    
    # Mettre à jour
    print("\n--- UPDATE ---")
    db.execute("UPDATE students SET gpa = 4.0 WHERE name = 'Alice'")
    db.execute("SELECT * FROM students WHERE name = 'Alice'")
    
    # Supprimer
    print("\n--- DELETE ---")
    db.execute("DELETE FROM students WHERE age < 21")
    db.execute("SELECT * FROM students")


def exemple_email():
    """Exemple avec le type EMAIL"""
    print("\n" + "="*60)
    print("EXEMPLE 2: Type EMAIL avec validation")
    print("="*60)
    
    db = DmonSQL("./example_data")
    
    if 'university' not in db.databases:
        db.execute("CREATE DATABASE university")
    db.execute("USE university")
    
    # Créer une table avec EMAIL
    db.execute("""
        CREATE TABLE users (
            id INT PRIMARY KEY AUTO_INCREMENT,
            name VARCHAR(100),
            email EMAIL UNIQUE NOT NULL
        )
    """)
    
    # Insérer des emails valides
    print("\n--- Insertion d'emails valides ---")
    db.execute("INSERT INTO users (name, email) VALUES ('Alice', 'alice@example.com')")
    db.execute("INSERT INTO users (name, email) VALUES ('Bob', 'bob.smith@company.org')")
    
    # Tenter d'insérer un email invalide
    print("\n--- Tentative d'email invalide ---")
    try:
        db.execute("INSERT INTO users (name, email) VALUES ('Charlie', 'invalid-email')")
    except Exception as e:
        print(f"Erreur attendue: {e}")
    
    # Afficher les utilisateurs
    print("\n--- Utilisateurs enregistrés ---")
    db.execute("SELECT * FROM users")


def exemple_matrix():
    """Exemple avec le type MATRIX"""
    print("\n" + "="*60)
    print("EXEMPLE 3: Type MATRIX avec NumPy")
    print("="*60)
    
    from dmonSQL_main import DmonSQL, Table, Column, DataType, MatrixType
    
    db = DmonSQL("./example_data")
    
    if 'ml_models' not in db.databases:
        db.execute("CREATE DATABASE ml_models")
    db.execute("USE ml_models")
    
    # Créer une table pour stocker des matrices
    table = Table('neural_weights', [
        Column('layer_id', DataType.INT, primary_key=True, auto_increment=True),
        Column('layer_name', DataType.VARCHAR, length=50),
        Column('weights', DataType.MATRIX),
        Column('bias', DataType.MATRIX)
    ])
    
    db.databases['ml_models'].create_table(table)
    
    # Insérer des matrices
    print("\n--- Insertion de matrices ---")
    weights1 = MatrixType(np.random.randn(3, 4))
    bias1 = MatrixType(np.random.randn(4))
    
    table.insert({
        'layer_name': 'hidden_layer_1',
        'weights': weights1,
        'bias': bias1
    })
    
    weights2 = MatrixType(np.array([[1, 2], [3, 4], [5, 6]]))
    bias2 = MatrixType(np.array([0.1, 0.2]))
    
    table.insert({
        'layer_name': 'hidden_layer_2',
        'weights': weights2,
        'bias': bias2
    })
    
    # Sélectionner et afficher
    print("\n--- Matrices stockées ---")
    result = table.select()
    for row in result:
        print(f"\nLayer: {row['layer_name']}")
        print(f"Weights shape: {row['weights'].matrix.shape}")
        print(f"Weights:\n{row['weights'].matrix}")
        print(f"Bias: {row['bias'].matrix}")
    
    db.save_database('ml_models')


def exemple_division_relationnelle():
    """Exemple de division relationnelle"""
    print("\n" + "="*60)
    print("EXEMPLE 4: Division Relationnelle")
    print("="*60)
    
    from dmonSQL_main import DmonSQL, Table, Column, DataType, RelationalAlgebra
    
    db = DmonSQL("./example_data")
    
    if 'school' not in db.databases:
        db.execute("CREATE DATABASE school")
    db.execute("USE school")
    
    # Créer la table des inscriptions (étudiants et cours)
    enrollments = Table('enrollments', [
        Column('student', DataType.VARCHAR, length=50),
        Column('course', DataType.VARCHAR, length=50)
    ])
    
    # Créer la table des cours requis
    required_courses = Table('required_courses', [
        Column('course', DataType.VARCHAR, length=50)
    ])
    
    db.databases['school'].create_table(enrollments)
    db.databases['school'].create_table(required_courses)
    
    # Insérer des inscriptions
    print("\n--- Inscriptions des étudiants ---")
    enrollments.insert({'student': 'Alice', 'course': 'Math'})
    enrollments.insert({'student': 'Alice', 'course': 'Physics'})
    enrollments.insert({'student': 'Alice', 'course': 'Chemistry'})
    enrollments.insert({'student': 'Bob', 'course': 'Math'})
    enrollments.insert({'student': 'Bob', 'course': 'Physics'})
    enrollments.insert({'student': 'Charlie', 'course': 'Math'})
    enrollments.insert({'student': 'Charlie', 'course': 'Physics'})
    enrollments.insert({'student': 'Charlie', 'course': 'Chemistry'})
    enrollments.insert({'student': 'Charlie', 'course': 'Biology'})
    
    print("Inscriptions:")
    for row in enrollments.rows:
        print(f"  {row['student']:10} -> {row['course']}")
    
    # Définir les cours requis
    print("\n--- Cours requis ---")
    required_courses.insert({'course': 'Math'})
    required_courses.insert({'course': 'Physics'})
    required_courses.insert({'course': 'Chemistry'})
    
    print("Cours requis:")
    for row in required_courses.rows:
        print(f"  - {row['course']}")
    
    # Appliquer la division: Trouver les étudiants inscrits à TOUS les cours requis
    print("\n--- DIVISION: Étudiants ayant TOUS les cours requis ---")
    result = RelationalAlgebra.division(
        enrollments,
        required_courses,
        common_attrs=['course'],
        dividend_attrs=['student']
    )
    
    print("Résultat de la division:")
    for row in result:
        print(f"  ✓ {row['student']} a tous les cours requis")
    
    # Vérification manuelle
    print("\n--- Vérification ---")
    print("Alice: Math, Physics, Chemistry ✓ (tous les cours)")
    print("Bob: Math, Physics ✗ (manque Chemistry)")
    print("Charlie: Math, Physics, Chemistry, Biology ✓ (tous les cours + extra)")
    
    db.save_database('school')


def exemple_jointures():
    """Exemple de jointures"""
    print("\n" + "="*60)
    print("EXEMPLE 5: Jointures et Algèbre Relationnelle")
    print("="*60)
    
    from dmonSQL_main import DmonSQL, Table, Column, DataType, RelationalAlgebra
    
    db = DmonSQL("./example_data")
    
    if 'company' not in db.databases:
        db.execute("CREATE DATABASE company")
    db.execute("USE company")
    
    # Créer tables
    employees = Table('employees', [
        Column('emp_id', DataType.INT, primary_key=True),
        Column('name', DataType.VARCHAR, length=50),
        Column('dept_id', DataType.INT)
    ])
    
    departments = Table('departments', [
        Column('dept_id', DataType.INT, primary_key=True),
        Column('dept_name', DataType.VARCHAR, length=50)
    ])
    
    db.databases['company'].create_table(employees)
    db.databases['company'].create_table(departments)
    
    # Insérer des données
    employees.insert({'emp_id': 1, 'name': 'Alice', 'dept_id': 10})
    employees.insert({'emp_id': 2, 'name': 'Bob', 'dept_id': 20})
    employees.insert({'emp_id': 3, 'name': 'Charlie', 'dept_id': 10})
    
    departments.insert({'dept_id': 10, 'dept_name': 'Engineering'})
    departments.insert({'dept_id': 20, 'dept_name': 'Sales'})
    
    # Jointure
    print("\n--- JOINTURE: Employés avec leurs départements ---")
    result = RelationalAlgebra.join(employees, departments, on=('dept_id', 'dept_id'))
    
    for row in result:
        print(f"  {row['name']:10} -> {row['dept_name']}")
    
    # Produit cartésien
    print("\n--- PRODUIT CARTÉSIEN (limité à 3 lignes) ---")
    cartesian = RelationalAlgebra.cross_product(employees, departments)
    for i, row in enumerate(cartesian[:3]):
        print(f"  {row}")
    print(f"  ... ({len(cartesian)} combinaisons totales)")
    
    db.save_database('company')


def exemple_index():
    """Exemple d'index pour performances"""
    print("\n" + "="*60)
    print("EXEMPLE 6: Index pour optimisation")
    print("="*60)
    
    from dmonSQL_main import DmonSQL, Table, Column, DataType
    import time
    
    db = DmonSQL("./example_data")
    
    if 'performance' not in db.databases:
        db.execute("CREATE DATABASE performance")
    db.execute("USE performance")
    
    # Créer une grande table
    large_table = Table('large_data', [
        Column('id', DataType.INT, primary_key=True),
        Column('value', DataType.INT),
        Column('category', DataType.VARCHAR, length=10)
    ])
    
    db.databases['performance'].create_table(large_table)
    
    # Insérer beaucoup de données
    print("\n--- Insertion de 1000 lignes ---")
    for i in range(1000):
        large_table.insert({
            'id': i,
            'value': i * 2,
            'category': f"cat_{i % 10}"
        })
    
    # Recherche sans index
    print("\n--- Recherche SANS index ---")
    start = time.time()
    result = large_table.select(where=lambda row: row['category'] == 'cat_5')
    time_without_index = time.time() - start
    print(f"Trouvé {len(result)} lignes en {time_without_index:.4f}s")
    
    # Créer un index
    print("\n--- Création d'un index sur 'category' ---")
    large_table.create_index('idx_category', ['category'])
    
    # Recherche avec index
    print("\n--- Recherche AVEC index ---")
    start = time.time()
    indices = large_table.indexes['idx_category'].search(('cat_5',))
    result_with_index = [large_table.rows[i] for i in indices]
    time_with_index = time.time() - start
    print(f"Trouvé {len(result_with_index)} lignes en {time_with_index:.4f}s")
    
    if time_without_index > 0:
        speedup = time_without_index / time_with_index
        print(f"\nAccélération: {speedup:.2f}x plus rapide avec index")
    
    db.save_database('performance')


def exemple_transactions_avancees():
    """Exemple d'opérations avancées"""
    print("\n" + "="*60)
    print("EXEMPLE 7: Opérations avancées")
    print("="*60)
    
    from dmonSQL_main import DmonSQL, Table, Column, DataType, RelationalAlgebra
    
    db = DmonSQL("./example_data")
    
    if 'advanced' not in db.databases:
        db.execute("CREATE DATABASE advanced")
    db.execute("USE advanced")
    
    # Créer des tables pour les opérations ensemblistes
    table_a = Table('set_a', [
        Column('id', DataType.INT),
        Column('value', DataType.VARCHAR, length=20)
    ])
    
    table_b = Table('set_b', [
        Column('id', DataType.INT),
        Column('value', DataType.VARCHAR, length=20)
    ])
    
    db.databases['advanced'].create_table(table_a)
    db.databases['advanced'].create_table(table_b)
    
    # Données pour set A
    table_a.insert({'id': 1, 'value': 'apple'})
    table_a.insert({'id': 2, 'value': 'banana'})
    table_a.insert({'id': 3, 'value': 'cherry'})
    
    # Données pour set B
    table_b.insert({'id': 2, 'value': 'banana'})
    table_b.insert({'id': 3, 'value': 'cherry'})
    table_b.insert({'id': 4, 'value': 'date'})
    
    print("\n--- Set A ---")
    for row in table_a.rows:
        print(f"  {row}")
    
    print("\n--- Set B ---")
    for row in table_b.rows:
        print(f"  {row}")
    
    # Union
    print("\n--- UNION (A ∪ B) ---")
    union_result = RelationalAlgebra.union(table_a.rows, table_b.rows)
    for row in union_result:
        print(f"  {row}")
    
    # Différence
    print("\n--- DIFFÉRENCE (A - B) ---")
    diff_result = RelationalAlgebra.difference(table_a.rows, table_b.rows)
    for row in diff_result:
        print(f"  {row}")
    
    db.save_database('advanced')


def run_all_examples():
    """Exécute tous les exemples"""
    print("\n" + "="*80)
    print(" "*20 + "DmonSQL - DÉMONSTRATION COMPLÈTE")
    print("="*80)
    
    try:
        exemple_basique()
        input("\nAppuyez sur Entrée pour continuer...")
        
        exemple_email()
        input("\nAppuyez sur Entrée pour continuer...")
        
        exemple_matrix()
        input("\nAppuyez sur Entrée pour continuer...")
        
        exemple_division_relationnelle()
        input("\nAppuyez sur Entrée pour continuer...")
        
        exemple_jointures()
        input("\nAppuyez sur Entrée pour continuer...")
        
        exemple_index()
        input("\nAppuyez sur Entrée pour continuer...")
        
        exemple_transactions_avancees()
        
        print("\n" + "="*80)
        print(" "*20 + "DÉMONSTRATION TERMINÉE")
        print("="*80)
        
    except KeyboardInterrupt:
        print("\n\nDémonstration interrompue.")
    except Exception as e:
        print(f"\n\nErreur: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_all_examples()