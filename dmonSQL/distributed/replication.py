"""
dmonSQL/distributed/replication.py
Système de réplication Master-Slave et Sharding
"""

import socket
import threading
import pickle
import hashlib
import json
import time
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from enum import Enum
from pathlib import Path
from queue import Queue, Empty


class ReplicaRole(Enum):
    """Rôle d'un nœud dans la réplication"""
    MASTER = "MASTER"
    SLAVE = "SLAVE"
    STANDALONE = "STANDALONE"


class ReplicationState(Enum):
    """État de la réplication"""
    SYNCING = "SYNCING"
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    ERROR = "ERROR"


class ShardingStrategy(Enum):
    """Stratégies de sharding"""
    HASH = "HASH"           # Hash du shard key
    RANGE = "RANGE"         # Plages de valeurs
    MODULO = "MODULO"       # Modulo du shard key
    CONSISTENT_HASH = "CONSISTENT_HASH"  # Consistent hashing


class Operation:
    """Opération à répliquer"""
    
    def __init__(self, op_type: str, sql: str, database: str = None,
                 timestamp: float = None):
        self.op_type = op_type  # INSERT, UPDATE, DELETE, etc.
        self.sql = sql
        self.database = database
        self.timestamp = timestamp or time.time()
        self.id = self._generate_id()
    
    def _generate_id(self) -> str:
        """Génère un ID unique pour l'opération"""
        data = f"{self.timestamp}{self.sql}".encode()
        return hashlib.sha256(data).hexdigest()[:16]
    
    def to_dict(self) -> dict:
        """Convertit en dictionnaire"""
        return {
            'id': self.id,
            'op_type': self.op_type,
            'sql': self.sql,
            'database': self.database,
            'timestamp': self.timestamp
        }
    
    @staticmethod
    def from_dict(data: dict) -> 'Operation':
        """Crée une opération depuis un dictionnaire"""
        op = Operation(
            data['op_type'],
            data['sql'],
            data.get('database'),
            data['timestamp']
        )
        op.id = data['id']
        return op


class ReplicationLog:
    """Journal de réplication"""
    
    def __init__(self, log_file: Path):
        self.log_file = log_file
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.operations: List[Operation] = []
        self.position = 0  # Position de lecture
        self.load()
    
    def append(self, operation: Operation):
        """Ajoute une opération au journal"""
        self.operations.append(operation)
        self._write_operation(operation)
    
    def _write_operation(self, operation: Operation):
        """Écrit une opération sur disque"""
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(operation.to_dict()) + '\n')
    
    def load(self):
        """Charge le journal depuis le disque"""
        if not self.log_file.exists():
            return
        
        with open(self.log_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    self.operations.append(Operation.from_dict(data))
    
    def get_operations_since(self, position: int) -> List[Operation]:
        """Retourne les opérations depuis une position"""
        return self.operations[position:]
    
    def truncate(self, position: int):
        """Tronque le journal jusqu'à une position"""
        self.operations = self.operations[:position]
        self._rewrite_log()
    
    def _rewrite_log(self):
        """Réécrit complètement le journal"""
        with open(self.log_file, 'w', encoding='utf-8') as f:
            for op in self.operations:
                f.write(json.dumps(op.to_dict()) + '\n')
    
    def __len__(self):
        return len(self.operations)


class Replica:
    """Représente un réplica (slave)"""
    
    def __init__(self, host: str, port: int, name: str = None):
        self.host = host
        self.port = port
        self.name = name or f"{host}:{port}"
        self.state = ReplicationState.OFFLINE
        self.lag_position = 0  # Position dans le log
        self.last_sync = None
        self.last_heartbeat = None
        self.error_count = 0
    
    def is_healthy(self, max_lag_seconds: int = 60) -> bool:
        """Vérifie si le réplica est en bonne santé"""
        if self.state != ReplicationState.ONLINE:
            return False
        
        if not self.last_heartbeat:
            return False
        
        lag = time.time() - self.last_heartbeat
        return lag < max_lag_seconds
    
    def update_heartbeat(self):
        """Met à jour le heartbeat"""
        self.last_heartbeat = time.time()
    
    def __repr__(self):
        return f"Replica({self.name}, {self.state.value}, lag={self.lag_position})"


class ReplicationManager:
    """Gestionnaire de réplication Master-Slave"""
    
    def __init__(self, role: ReplicaRole = ReplicaRole.STANDALONE,
                 host: str = "localhost", port: int = 5433,
                 log_dir: str = "./dmonsql_data/replication"):
        self.role = role
        self.host = host
        self.port = port
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Journal de réplication
        self.replication_log = ReplicationLog(self.log_dir / "replication.log")
        
        # Liste des réplicas (pour le master)
        self.replicas: Dict[str, Replica] = {}
        
        # Master info (pour les slaves)
        self.master_host: Optional[str] = None
        self.master_port: Optional[int] = None
        
        # Threads
        self.running = False
        self.threads: List[threading.Thread] = []
        
        # Queue d'opérations à répliquer
        self.operation_queue: Queue = Queue()
        
        # Callbacks
        self.on_operation: Optional[Callable] = None
    
    # ==================== MASTER ====================
    
    def start_as_master(self):
        """Démarre en mode master"""
        if self.role != ReplicaRole.MASTER:
            self.role = ReplicaRole.MASTER
        
        self.running = True
        
        # Thread pour accepter les connexions des slaves
        acceptor_thread = threading.Thread(
            target=self._accept_slaves,
            daemon=True
        )
        acceptor_thread.start()
        self.threads.append(acceptor_thread)
        
        # Thread pour envoyer les opérations aux slaves
        replicator_thread = threading.Thread(
            target=self._replicate_to_slaves,
            daemon=True
        )
        replicator_thread.start()
        self.threads.append(replicator_thread)
        
        print(f"✓ Replication master started on {self.host}:{self.port}")
    
    def log_operation(self, op_type: str, sql: str, database: str = None):
        """Enregistre une opération pour réplication"""
        if self.role != ReplicaRole.MASTER:
            return
        
        operation = Operation(op_type, sql, database)
        self.replication_log.append(operation)
        self.operation_queue.put(operation)
    
    def _accept_slaves(self):
        """Accepte les connexions des slaves"""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(5)
        server_socket.settimeout(1.0)
        
        while self.running:
            try:
                client_socket, address = server_socket.accept()
                # Gérer la connexion slave dans un thread séparé
                thread = threading.Thread(
                    target=self._handle_slave,
                    args=(client_socket, address),
                    daemon=True
                )
                thread.start()
            except socket.timeout:
                continue
            except Exception as e:
                print(f"Error accepting slave connection: {e}")
        
        server_socket.close()
    
    def _handle_slave(self, client_socket: socket.socket, address):
        """Gère la connexion avec un slave"""
        try:
            # Recevoir les informations du slave
            data = self._receive_data(client_socket)
            if not data:
                return
            
            slave_info = pickle.loads(data)
            slave_name = slave_info.get('name', f"{address[0]}:{address[1]}")
            
            # Enregistrer le réplica
            replica = Replica(address[0], address[1], slave_name)
            replica.state = ReplicationState.SYNCING
            replica.lag_position = slave_info.get('position', 0)
            self.replicas[slave_name] = replica
            
            print(f"✓ Slave connected: {slave_name}")
            
            # Envoyer les opérations manquantes
            self._sync_slave(client_socket, replica)
            
            # Marquer comme en ligne
            replica.state = ReplicationState.ONLINE
            replica.update_heartbeat()
            
        except Exception as e:
            print(f"Error handling slave {address}: {e}")
        finally:
            client_socket.close()
    
    def _sync_slave(self, client_socket: socket.socket, replica: Replica):
        """Synchronise un slave avec le master"""
        # Récupérer les opérations depuis la position du slave
        operations = self.replication_log.get_operations_since(replica.lag_position)
        
        # Envoyer les opérations
        for op in operations:
            try:
                self._send_data(client_socket, pickle.dumps(op.to_dict()))
                replica.lag_position += 1
            except Exception as e:
                print(f"Error syncing operation to {replica.name}: {e}")
                replica.state = ReplicationState.ERROR
                break
    
    def _replicate_to_slaves(self):
        """Envoie les opérations aux slaves en temps réel"""
        while self.running:
            try:
                # Attendre une nouvelle opération
                operation = self.operation_queue.get(timeout=1.0)
                
                # Envoyer à tous les slaves en ligne
                for replica in list(self.replicas.values()):
                    if replica.state == ReplicationState.ONLINE:
                        try:
                            self._send_operation_to_slave(replica, operation)
                        except Exception as e:
                            print(f"Error replicating to {replica.name}: {e}")
                            replica.error_count += 1
                            if replica.error_count > 3:
                                replica.state = ReplicationState.ERROR
                
            except Empty:
                continue
            except Exception as e:
                print(f"Error in replication thread: {e}")
    
    def _send_operation_to_slave(self, replica: Replica, operation: Operation):
        """Envoie une opération à un slave"""
        # Établir une connexion temporaire
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        
        try:
            sock.connect((replica.host, replica.port))
            self._send_data(sock, pickle.dumps(operation.to_dict()))
            replica.lag_position += 1
            replica.update_heartbeat()
            replica.error_count = 0
        finally:
            sock.close()
    
    # ==================== SLAVE ====================
    
    def start_as_slave(self, master_host: str, master_port: int):
        """Démarre en mode slave"""
        self.role = ReplicaRole.SLAVE
        self.master_host = master_host
        self.master_port = master_port
        self.running = True
        
        # Thread pour synchronisation initiale
        sync_thread = threading.Thread(
            target=self._initial_sync,
            daemon=True
        )
        sync_thread.start()
        self.threads.append(sync_thread)
        
        # Thread pour recevoir les opérations du master
        receiver_thread = threading.Thread(
            target=self._receive_operations,
            daemon=True
        )
        receiver_thread.start()
        self.threads.append(receiver_thread)
        
        print(f"✓ Replication slave started, connecting to {master_host}:{master_port}")
    
    def _initial_sync(self):
        """Synchronisation initiale avec le master"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self.master_host, self.master_port))
            
            # Envoyer nos informations
            info = {
                'name': f"{self.host}:{self.port}",
                'position': len(self.replication_log)
            }
            self._send_data(sock, pickle.dumps(info))
            
            # Recevoir les opérations manquantes
            while True:
                data = self._receive_data(sock)
                if not data:
                    break
                
                op_dict = pickle.loads(data)
                operation = Operation.from_dict(op_dict)
                self._apply_operation(operation)
            
            print("✓ Initial sync completed")
            
        except Exception as e:
            print(f"Error during initial sync: {e}")
        finally:
            sock.close()
    
    def _receive_operations(self):
        """Reçoit les opérations du master"""
        # Écouter les connexions du master
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(5)
        server_socket.settimeout(1.0)
        
        while self.running:
            try:
                client_socket, address = server_socket.accept()
                
                # Recevoir l'opération
                data = self._receive_data(client_socket)
                if data:
                    op_dict = pickle.loads(data)
                    operation = Operation.from_dict(op_dict)
                    self._apply_operation(operation)
                
                client_socket.close()
                
            except socket.timeout:
                continue
            except Exception as e:
                print(f"Error receiving operation: {e}")
        
        server_socket.close()
    
    def _apply_operation(self, operation: Operation):
        """Applique une opération reçue du master"""
        # Ajouter au journal local
        self.replication_log.append(operation)
        
        # Exécuter le callback si défini
        if self.on_operation:
            try:
                self.on_operation(operation)
            except Exception as e:
                print(f"Error applying operation: {e}")
    
    # ==================== UTILITAIRES ====================
    
    def _send_data(self, sock: socket.socket, data: bytes):
        """Envoie des données avec préfixe de longueur"""
        length = len(data)
        sock.sendall(length.to_bytes(4, 'big'))
        sock.sendall(data)
    
    def _receive_data(self, sock: socket.socket) -> Optional[bytes]:
        """Reçoit des données avec préfixe de longueur"""
        try:
            # Recevoir la longueur
            length_bytes = sock.recv(4)
            if not length_bytes:
                return None
            
            length = int.from_bytes(length_bytes, 'big')
            
            # Recevoir les données
            data = b''
            while len(data) < length:
                chunk = sock.recv(min(4096, length - len(data)))
                if not chunk:
                    return None
                data += chunk
            
            return data
        except Exception:
            return None
    
    def stop(self):
        """Arrête la réplication"""
        self.running = False
        for thread in self.threads:
            thread.join(timeout=5.0)
        print("✓ Replication stopped")
    
    def get_status(self) -> dict:
        """Retourne le statut de la réplication"""
        if self.role == ReplicaRole.MASTER:
            return {
                'role': 'MASTER',
                'log_position': len(self.replication_log),
                'replicas': {
                    name: {
                        'state': replica.state.value,
                        'lag': len(self.replication_log) - replica.lag_position,
                        'healthy': replica.is_healthy()
                    }
                    for name, replica in self.replicas.items()
                }
            }
        elif self.role == ReplicaRole.SLAVE:
            return {
                'role': 'SLAVE',
                'master': f"{self.master_host}:{self.master_port}",
                'log_position': len(self.replication_log)
            }
        else:
            return {'role': 'STANDALONE'}


class ShardManager:
    """Gestionnaire de sharding"""
    
    def __init__(self, strategy: ShardingStrategy = ShardingStrategy.HASH,
                 num_shards: int = 4):
        self.strategy = strategy
        self.num_shards = num_shards
        self.shards: Dict[int, Dict] = {}
        
        # Initialiser les shards
        for i in range(num_shards):
            self.shards[i] = {
                'id': i,
                'host': 'localhost',
                'port': 5433 + i,
                'databases': set(),
                'size': 0
            }
    
    def get_shard(self, key: Any) -> int:
        """Détermine le shard pour une clé donnée"""
        if self.strategy == ShardingStrategy.HASH:
            return self._hash_shard(key)
        elif self.strategy == ShardingStrategy.MODULO:
            return self._modulo_shard(key)
        elif self.strategy == ShardingStrategy.CONSISTENT_HASH:
            return self._consistent_hash_shard(key)
        else:
            raise ValueError(f"Unknown sharding strategy: {self.strategy}")
    
    def _hash_shard(self, key: Any) -> int:
        """Sharding par hash"""
        key_str = str(key)
        hash_value = int(hashlib.md5(key_str.encode()).hexdigest(), 16)
        return hash_value % self.num_shards
    
    def _modulo_shard(self, key: Any) -> int:
        """Sharding par modulo (clé doit être numérique)"""
        if isinstance(key, (int, float)):
            return int(key) % self.num_shards
        return self._hash_shard(key)
    
    def _consistent_hash_shard(self, key: Any) -> int:
        """Consistent hashing (simplifié)"""
        # Dans une vraie implémentation, utiliser un ring hash
        return self._hash_shard(key)
    
    def add_shard(self, host: str, port: int) -> int:
        """Ajoute un nouveau shard"""
        shard_id = self.num_shards
        self.shards[shard_id] = {
            'id': shard_id,
            'host': host,
            'port': port,
            'databases': set(),
            'size': 0
        }
        self.num_shards += 1
        print(f"✓ Shard {shard_id} added at {host}:{port}")
        return shard_id
    
    def remove_shard(self, shard_id: int):
        """Retire un shard (nécessite une redistribution des données)"""
        if shard_id not in self.shards:
            raise ValueError(f"Shard {shard_id} does not exist")
        
        # Dans une vraie implémentation, redistribuer les données
        del self.shards[shard_id]
        self.num_shards -= 1
        print(f"✓ Shard {shard_id} removed (data should be redistributed)")
    
    def get_shard_info(self, shard_id: int) -> dict:
        """Retourne les informations d'un shard"""
        if shard_id not in self.shards:
            raise ValueError(f"Shard {shard_id} does not exist")
        return self.shards[shard_id]
    
    def list_shards(self) -> List[int]:
        """Liste tous les shards"""
        return list(self.shards.keys())
    
    def get_statistics(self) -> dict:
        """Retourne les statistiques de sharding"""
        total_size = sum(s['size'] for s in self.shards.values())
        
        return {
            'num_shards': self.num_shards,
            'strategy': self.strategy.value,
            'total_size': total_size,
            'shards': {
                sid: {
                    'size': shard['size'],
                    'databases': len(shard['databases']),
                    'host': f"{shard['host']}:{shard['port']}"
                }
                for sid, shard in self.shards.items()
            }
        }


# ==================== EXEMPLES D'UTILISATION ====================

if __name__ == "__main__":
    print("=" * 60)
    print("REPLICATION & SHARDING DEMO")
    print("=" * 60)
    
    # Démonstration du Sharding
    print("\n📊 SHARDING DEMO")
    print("-" * 60)
    
    shard_manager = ShardManager(
        strategy=ShardingStrategy.HASH,
        num_shards=4
    )
    
    # Tester la distribution des clés
    print("\n1. Testing key distribution...")
    keys = ['user1', 'user2', 'user3', 'user4', 'user5', 'user6', 'user7', 'user8']
    distribution = {}
    
    for key in keys:
        shard = shard_manager.get_shard(key)
        distribution[shard] = distribution.get(shard, 0) + 1
        print(f"  {key} -> Shard {shard}")
    
    print(f"\nDistribution: {distribution}")
    
    # Ajouter un shard
    print("\n2. Adding a new shard...")
    shard_manager.add_shard('localhost', 5437)
    
    # Statistiques
    print("\n3. Shard statistics...")
    stats = shard_manager.get_statistics()
    print(f"Total shards: {stats['num_shards']}")
    print(f"Strategy: {stats['strategy']}")
    
    # Démonstration de la Réplication
    print("\n\n🔄 REPLICATION DEMO")
    print("-" * 60)
    
    # Note: La démo complète nécessiterait plusieurs processus
    print("\n1. Creating replication manager as MASTER...")
    replication_manager = ReplicationManager(
        role=ReplicaRole.MASTER,
        host='localhost',
        port=5433
    )
    
    print(f"Role: {replication_manager.role.value}")
    print(f"Log position: {len(replication_manager.replication_log)}")
    
    # Enregistrer des opérations
    print("\n2. Logging operations...")
    replication_manager.log_operation("INSERT", "INSERT INTO users VALUES (1, 'Alice')", "testdb")
    replication_manager.log_operation("UPDATE", "UPDATE users SET name='Bob' WHERE id=1", "testdb")
    
    print(f"Operations logged: {len(replication_manager.replication_log)}")
    
    # Statut
    print("\n3. Replication status...")
    status = replication_manager.get_status()
    print(f"Role: {status['role']}")
    print(f"Log position: {status['log_position']}")
    print(f"Connected replicas: {len(status['replicas'])}")
    
    print("\n" + "=" * 60)
    print("✓ All demos completed!")
    print("=" * 60)
    print("\nNote: Full replication demo requires running multiple processes:")
    print("  Terminal 1: python replication.py --master")
    print("  Terminal 2: python replication.py --slave --master-host localhost --master-port 5433")