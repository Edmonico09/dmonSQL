"""Module de gestion des contraintes (FK, CHECK, etc.)"""

from typing import List, Dict, Any, Optional, Callable
from enum import Enum


class ConstraintType(Enum):
    """Types de contraintes"""
    PRIMARY_KEY = "PRIMARY_KEY"
    FOREIGN_KEY = "FOREIGN_KEY"
    UNIQUE = "UNIQUE"
    CHECK = "CHECK"
    NOT_NULL = "NOT_NULL"
    DEFAULT = "DEFAULT"


class Constraint:
    """Classe de base pour les contraintes"""
    
    def __init__(self, name: str, constraint_type: ConstraintType):
        self.name = name
        self.constraint_type = constraint_type
    
    def validate(self, value: Any, row: Dict = None) -> bool:
        """Valide une valeur selon la contrainte"""
        raise NotImplementedError
    
    def __repr__(self):
        return f"Constraint({self.name}, {self.constraint_type.value})"


class PrimaryKeyConstraint(Constraint):
    """Contrainte de clé primaire"""
    
    def __init__(self, name: str, columns: List[str]):
        super().__init__(name, ConstraintType.PRIMARY_KEY)
        self.columns = columns
    
    def validate(self, value: Any, row: Dict = None) -> bool:
        """La clé primaire ne peut pas être NULL"""
        if value is None:
            raise ValueError(f"Primary key {self.columns} cannot be NULL")
        return True


class ForeignKeyConstraint(Constraint):
    """Contrainte de clé étrangère"""
    
    def __init__(self, name: str, columns: List[str], 
                 ref_table: str, ref_columns: List[str],
                 on_delete: str = "RESTRICT", on_update: str = "RESTRICT"):
        super().__init__(name, ConstraintType.FOREIGN_KEY)
        self.columns = columns
        self.ref_table = ref_table
        self.ref_columns = ref_columns
        self.on_delete = on_delete  # RESTRICT, CASCADE, SET NULL, NO ACTION
        self.on_update = on_update
    
    def validate(self, value: Any, row: Dict = None) -> bool:
        """Valide que la valeur existe dans la table référencée"""
        # À implémenter avec accès à la base de données
        return True
    
    def __repr__(self):
        return f"ForeignKey({self.columns} -> {self.ref_table}.{self.ref_columns})"


class UniqueConstraint(Constraint):
    """Contrainte d'unicité"""
    
    def __init__(self, name: str, columns: List[str]):
        super().__init__(name, ConstraintType.UNIQUE)
        self.columns = columns
        self.values_seen = set()
    
    def validate(self, value: Any, row: Dict = None) -> bool:
        """Valide que la valeur est unique"""
        if value in self.values_seen:
            raise ValueError(f"Duplicate value for unique constraint: {value}")
        self.values_seen.add(value)
        return True
    
    def reset(self):
        """Réinitialise les valeurs vues"""
        self.values_seen.clear()


class CheckConstraint(Constraint):
    """Contrainte CHECK (condition personnalisée)"""
    
    def __init__(self, name: str, condition: Callable[[Dict], bool], 
                 condition_str: str = ""):
        super().__init__(name, ConstraintType.CHECK)
        self.condition = condition
        self.condition_str = condition_str
    
    def validate(self, value: Any, row: Dict = None) -> bool:
        """Valide selon la condition"""
        if row is None:
            return True
        
        if not self.condition(row):
            raise ValueError(f"CHECK constraint {self.name} violated: {self.condition_str}")
        return True
    
    def __repr__(self):
        return f"CheckConstraint({self.name}, {self.condition_str})"


class NotNullConstraint(Constraint):
    """Contrainte NOT NULL"""
    
    def __init__(self, name: str, column: str):
        super().__init__(name, ConstraintType.NOT_NULL)
        self.column = column
    
    def validate(self, value: Any, row: Dict = None) -> bool:
        """Valide que la valeur n'est pas NULL"""
        if value is None:
            raise ValueError(f"Column {self.column} cannot be NULL")
        return True


class DefaultConstraint(Constraint):
    """Contrainte DEFAULT (valeur par défaut)"""
    
    def __init__(self, name: str, column: str, default_value: Any):
        super().__init__(name, ConstraintType.DEFAULT)
        self.column = column
        self.default_value = default_value
    
    def get_default(self) -> Any:
        """Retourne la valeur par défaut"""
        if callable(self.default_value):
            return self.default_value()
        return self.default_value
    
    def validate(self, value: Any, row: Dict = None) -> bool:
        """Toujours valide (applique juste la valeur par défaut)"""
        return True


class ConstraintManager:
    """Gestionnaire de contraintes pour une table"""
    
    def __init__(self):
        self.constraints: Dict[str, Constraint] = {}
    
    def add_constraint(self, constraint: Constraint):
        """Ajoute une contrainte"""
        self.constraints[constraint.name] = constraint
    
    def remove_constraint(self, name: str):
        """Supprime une contrainte"""
        if name in self.constraints:
            del self.constraints[name]
    
    def validate_row(self, row: Dict) -> bool:
        """Valide une ligne contre toutes les contraintes"""
        for constraint in self.constraints.values():
            # Valider selon le type de contrainte
            if isinstance(constraint, CheckConstraint):
                constraint.validate(None, row)
            elif isinstance(constraint, NotNullConstraint):
                value = row.get(constraint.column)
                constraint.validate(value, row)
        return True
    
    def get_constraints_by_type(self, constraint_type: ConstraintType) -> List[Constraint]:
        """Retourne les contraintes d'un type donné"""
        return [c for c in self.constraints.values() 
                if c.constraint_type == constraint_type]
    
    def __repr__(self):
        return f"ConstraintManager({len(self.constraints)} constraints)"


# Exemple d'utilisation
if __name__ == "__main__":
    # Créer un gestionnaire de contraintes
    manager = ConstraintManager()
    
    # Ajouter une contrainte CHECK
    check = CheckConstraint(
        "check_age",
        lambda row: row.get('age', 0) >= 18,
        "age >= 18"
    )
    manager.add_constraint(check)
    
    # Ajouter une contrainte NOT NULL
    not_null = NotNullConstraint("not_null_email", "email")
    manager.add_constraint(not_null)
    
    # Tester
    try:
        manager.validate_row({'age': 25, 'email': 'test@example.com'})
        print("✓ Ligne valide")
    except ValueError as e:
        print(f"✗ Erreur: {e}")
    
    try:
        manager.validate_row({'age': 15, 'email': 'test@example.com'})
        print("✓ Ligne valide")
    except ValueError as e:
        print(f"✗ Erreur attendue: {e}")