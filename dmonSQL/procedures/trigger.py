"""
dmonSQL/procedures/trigger.py
Gestionnaire de déclencheurs (triggers)
"""

from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
from enum import Enum


class TriggerEvent(Enum):
    """Événements déclencheurs"""
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class TriggerTiming(Enum):
    """Timing d'exécution"""
    BEFORE = "BEFORE"
    AFTER = "AFTER"
    INSTEAD_OF = "INSTEAD_OF"


class TriggerLevel(Enum):
    """Niveau d'exécution"""
    ROW = "ROW"          # Pour chaque ligne
    STATEMENT = "STATEMENT"  # Une fois par statement


class Trigger:
    """Déclencheur"""
    
    def __init__(self, name: str, table: str, event: TriggerEvent,
                 timing: TriggerTiming, body: str, 
                 level: TriggerLevel = TriggerLevel.ROW,
                 condition: Optional[str] = None):
        """
        Initialise un trigger
        
        Args:
            name: Nom du trigger
            table: Table associée
            event: Événement déclencheur
            timing: Timing (BEFORE/AFTER/INSTEAD_OF)
            body: Corps du trigger
            level: Niveau d'exécution (ROW/STATEMENT)
            condition: Condition WHEN (optionnel)
        """
        self.name = name
        self.table = table
        self.event = event
        self.timing = timing
        self.body = body
        self.level = level
        self.condition = condition
        self.created_at = datetime.now()
        self.execution_count = 0
        self.last_executed = None
        self.enabled = True
    
    def should_execute(self, old_row: Optional[Dict] = None, 
                      new_row: Optional[Dict] = None) -> bool:
        """Vérifie si le trigger doit s'exécuter"""
        if not self.enabled:
            return False
        
        # Vérifier la condition WHEN si présente
        if self.condition:
            return self._evaluate_condition(old_row, new_row)
        
        return True
    
    def _evaluate_condition(self, old_row: Optional[Dict], 
                           new_row: Optional[Dict]) -> bool:
        """Évalue la condition WHEN"""
        # Implémentation basique
        # En production, utiliser un parser d'expressions
        try:
            context = {
                'OLD': old_row or {},
                'NEW': new_row or {}
            }
            return eval(self.condition, {}, context)
        except:
            return True
    
    def execute(self, db_system, old_row: Optional[Dict] = None,
                new_row: Optional[Dict] = None) -> Any:
        """
        Exécute le trigger
        
        Args:
            db_system: Instance de DmonSQL
            old_row: Ancienne ligne (UPDATE/DELETE)
            new_row: Nouvelle ligne (INSERT/UPDATE)
        
        Returns:
            Résultat de l'exécution
        """
        if not self.should_execute(old_row, new_row):
            return None
        
        self.execution_count += 1
        self.last_executed = datetime.now()
        
        # Remplacer OLD et NEW dans le corps
        body = self.body
        
        if old_row:
            for key, value in old_row.items():
                placeholder = f"OLD.{key}"
                if isinstance(value, str):
                    body = body.replace(placeholder, f"'{value}'")
                else:
                    body = body.replace(placeholder, str(value))
        
        if new_row:
            for key, value in new_row.items():
                placeholder = f"NEW.{key}"
                if isinstance(value, str):
                    body = body.replace(placeholder, f"'{value}'")
                else:
                    body = body.replace(placeholder, str(value))
        
        # Exécuter les statements
        statements = [s.strip() for s in body.split(';') if s.strip()]
        last_result = None
        
        for statement in statements:
            try:
                last_result = db_system.execute(statement)
            except Exception as e:
                raise RuntimeError(f"Trigger {self.name} execution failed: {e}")
        
        return last_result
    
    def enable(self):
        """Active le trigger"""
        self.enabled = True
    
    def disable(self):
        """Désactive le trigger"""
        self.enabled = False
    
    def get_info(self) -> Dict:
        """Retourne les informations sur le trigger"""
        return {
            'name': self.name,
            'table': self.table,
            'event': self.event.value,
            'timing': self.timing.value,
            'level': self.level.value,
            'enabled': self.enabled,
            'condition': self.condition,
            'created_at': self.created_at.isoformat(),
            'last_executed': self.last_executed.isoformat() if self.last_executed else None,
            'execution_count': self.execution_count
        }
    
    def __repr__(self):
        return (f"Trigger({self.name} {self.timing.value} {self.event.value} "
                f"ON {self.table})")


class TriggerManager:
    """Gestionnaire de triggers"""
    
    def __init__(self):
        self.triggers: Dict[str, Trigger] = {}
        # Index par table et événement pour performance
        self.trigger_index: Dict[str, Dict[TriggerEvent, List[Trigger]]] = {}
    
    def create_trigger(self, name: str, table: str, event: TriggerEvent,
                      timing: TriggerTiming, body: str,
                      level: TriggerLevel = TriggerLevel.ROW,
                      condition: Optional[str] = None) -> Trigger:
        """Crée un trigger"""
        if name in self.triggers:
            raise ValueError(f"Trigger {name} already exists")
        
        trigger = Trigger(name, table, event, timing, body, level, condition)
        self.triggers[name] = trigger
        
        # Indexer
        if table not in self.trigger_index:
            self.trigger_index[table] = {}
        if event not in self.trigger_index[table]:
            self.trigger_index[table][event] = []
        
        self.trigger_index[table][event].append(trigger)
        
        return trigger
    
    def drop_trigger(self, name: str):
        """Supprime un trigger"""
        if name not in self.triggers:
            raise ValueError(f"Trigger {name} does not exist")
        
        trigger = self.triggers[name]
        
        # Retirer de l'index
        if trigger.table in self.trigger_index:
            if trigger.event in self.trigger_index[trigger.table]:
                self.trigger_index[trigger.table][trigger.event].remove(trigger)
        
        del self.triggers[name]
    
    def enable_trigger(self, name: str):
        """Active un trigger"""
        if name not in self.triggers:
            raise ValueError(f"Trigger {name} does not exist")
        self.triggers[name].enable()
    
    def disable_trigger(self, name: str):
        """Désactive un trigger"""
        if name not in self.triggers:
            raise ValueError(f"Trigger {name} does not exist")
        self.triggers[name].disable()
    
    def get_triggers_for_table(self, table: str, event: TriggerEvent,
                              timing: TriggerTiming) -> List[Trigger]:
        """Retourne les triggers pour une table/événement/timing"""
        if table not in self.trigger_index:
            return []
        
        if event not in self.trigger_index[table]:
            return []
        
        # Filtrer par timing
        triggers = [
            t for t in self.trigger_index[table][event]
            if t.timing == timing and t.enabled
        ]
        
        return triggers
    
    def execute_triggers(self, table: str, event: TriggerEvent,
                        timing: TriggerTiming, db_system,
                        old_row: Optional[Dict] = None,
                        new_row: Optional[Dict] = None):
        """
        Exécute tous les triggers pour un événement
        
        Args:
            table: Nom de la table
            event: Événement
            timing: Timing
            db_system: Instance de DmonSQL
            old_row: Ancienne ligne
            new_row: Nouvelle ligne
        """
        triggers = self.get_triggers_for_table(table, event, timing)
        
        for trigger in triggers:
            try:
                trigger.execute(db_system, old_row, new_row)
            except Exception as e:
                # Logger l'erreur mais continuer
                print(f"Warning: Trigger {trigger.name} failed: {e}")
    
    def list_triggers(self, table: Optional[str] = None) -> List[str]:
        """Liste les triggers (filtrés par table si spécifié)"""
        if table:
            return [
                name for name, trigger in self.triggers.items()
                if trigger.table == table
            ]
        return list(self.triggers.keys())
    
    def get_trigger_info(self, name: str) -> Dict:
        """Retourne les informations sur un trigger"""
        if name not in self.triggers:
            raise ValueError(f"Trigger {name} does not exist")
        return self.triggers[name].get_info()
    
    def __repr__(self):
        return f"TriggerManager({len(self.triggers)} triggers)"


# ============================================================================
# EXEMPLES
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("TRIGGER MANAGER DEMO")
    print("=" * 60)
    
    manager = TriggerManager()
    
    # Créer un trigger BEFORE INSERT
    print("\n1. Creating BEFORE INSERT trigger...")
    manager.create_trigger(
        name="validate_user_before_insert",
        table="users",
        event=TriggerEvent.INSERT,
        timing=TriggerTiming.BEFORE,
        body="""
            SELECT * FROM users WHERE email = NEW.email;
        """,
        level=TriggerLevel.ROW
    )
    print("✓ Trigger 'validate_user_before_insert' created")
    
    # Créer un trigger AFTER UPDATE
    print("\n2. Creating AFTER UPDATE trigger...")
    manager.create_trigger(
        name="log_user_update",
        table="users",
        event=TriggerEvent.UPDATE,
        timing=TriggerTiming.AFTER,
        body="""
            INSERT INTO audit_log (table_name, action, old_value, new_value)
            VALUES ('users', 'UPDATE', 'OLD.email', 'NEW.email');
        """,
        level=TriggerLevel.ROW
    )
    print("✓ Trigger 'log_user_update' created")
    
    # Créer un trigger avec condition
    print("\n3. Creating trigger with WHEN condition...")
    manager.create_trigger(
        name="check_price_increase",
        table="products",
        event=TriggerEvent.UPDATE,
        timing=TriggerTiming.BEFORE,
        body="""
            SELECT 'Price increase too high!';
        """,
        condition="NEW['price'] > OLD['price'] * 1.5"
    )
    print("✓ Trigger 'check_price_increase' created")
    
    # Lister les triggers
    print("\n4. Listing triggers...")
    print(f"All triggers: {manager.list_triggers()}")
    print(f"Triggers on 'users': {manager.list_triggers('users')}")
    
    # Désactiver/Activer un trigger
    print("\n5. Disabling and enabling trigger...")
    manager.disable_trigger("log_user_update")
    print("✓ Trigger disabled")
    manager.enable_trigger("log_user_update")
    print("✓ Trigger enabled")
    
    # Afficher les informations sur un trigger
    print("\n6. Trigger information...")
    info = manager.get_trigger_info("validate_user_before_insert")
    print(f"Name: {info['name']}")
    print(f"Table: {info['table']}")
    print(f"Event: {info['event']}")
    print(f"Timing: {info['timing']}")
    print(f"Enabled: {info['enabled']}")
    print(f"Execution count: {info['execution_count']}")
    
    # Tester l'exécution (avec mock)
    print("\n7. Testing trigger execution...")
    class MockDB:
        def execute(self, sql):
            print(f"  Executing: {sql[:50]}...")
            return None
    
    mock_db = MockDB()
    trigger = manager.triggers["log_user_update"]
    
    old_row = {'id': 1, 'name': 'Alice', 'email': 'alice@old.com'}
    new_row = {'id': 1, 'name': 'Alice', 'email': 'alice@new.com'}
    
    trigger.execute(mock_db, old_row, new_row)
    print("✓ Trigger executed successfully")
    
    print("\n" + "=" * 60)
    print("✓ All demos completed!")
    print("=" * 60)