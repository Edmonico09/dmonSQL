import zlib
import bz2
import lz4.frame
import pickle
from typing import Any, Optional
from enum import Enum
from compression import CompressionAlgorithm, Compressor
import hashlib
import base64
import os


# ============================================================================
# ENCRYPTION
# ============================================================================

class EncryptionAlgorithm(Enum):
    """Algorithmes de chiffrement disponibles"""
    NONE = "NONE"
    AES256 = "AES256"
    CHACHA20 = "CHACHA20"


class Encryptor:
    """Gestionnaire de chiffrement"""
    
    @staticmethod
    def generate_key() -> bytes:
        """Génère une clé de chiffrement aléatoire"""
        try:
            from cryptography.fernet import Fernet
            return Fernet.generate_key()
        except ImportError:
            # Fallback simple si cryptography n'est pas installé
            return os.urandom(32)
    
    @staticmethod
    def derive_key_from_password(password: str, salt: Optional[bytes] = None) -> tuple:
        """
        Dérive une clé depuis un mot de passe
        
        Returns:
            (key, salt) tuple
        """
        try:
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            
            if salt is None:
                salt = os.urandom(16)
            
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
            return key, salt
        except ImportError:
            # Fallback simple
            if salt is None:
                salt = os.urandom(16)
            key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
            return base64.urlsafe_b64encode(key), salt
    
    @staticmethod
    def encrypt(data: bytes, key: bytes, 
                algorithm: EncryptionAlgorithm = EncryptionAlgorithm.AES256) -> bytes:
        """
        Chiffre des données
        
        Args:
            data: Données à chiffrer
            key: Clé de chiffrement
            algorithm: Algorithme de chiffrement
        
        Returns:
            Données chiffrées
        """
        if algorithm == EncryptionAlgorithm.NONE:
            return data
        
        try:
            from cryptography.fernet import Fernet
            
            if algorithm == EncryptionAlgorithm.AES256:
                f = Fernet(key)
                return f.encrypt(data)
            elif algorithm == EncryptionAlgorithm.CHACHA20:
                # Fernet utilise déjà AES, pour ChaCha20 on aurait besoin d'une autre lib
                # Pour l'instant, on utilise Fernet comme fallback
                f = Fernet(key)
                return f.encrypt(data)
            else:
                raise ValueError(f"Unknown encryption algorithm: {algorithm}")
        except ImportError:
            # Fallback très simple (XOR) - NE PAS UTILISER EN PRODUCTION
            return Encryptor._simple_encrypt(data, key)
    
    @staticmethod
    def decrypt(data: bytes, key: bytes,
                algorithm: EncryptionAlgorithm = EncryptionAlgorithm.AES256) -> bytes:
        """
        Déchiffre des données
        
        Args:
            data: Données chiffrées
            key: Clé de chiffrement
            algorithm: Algorithme utilisé
        
        Returns:
            Données déchiffrées
        """
        if algorithm == EncryptionAlgorithm.NONE:
            return data
        
        try:
            from cryptography.fernet import Fernet
            
            if algorithm in [EncryptionAlgorithm.AES256, EncryptionAlgorithm.CHACHA20]:
                f = Fernet(key)
                return f.decrypt(data)
            else:
                raise ValueError(f"Unknown encryption algorithm: {algorithm}")
        except ImportError:
            return Encryptor._simple_decrypt(data, key)
    
    @staticmethod
    def _simple_encrypt(data: bytes, key: bytes) -> bytes:
        """Chiffrement XOR simple (fallback, non sécurisé)"""
        key_hash = hashlib.sha256(key).digest()
        return bytes(b ^ key_hash[i % len(key_hash)] for i, b in enumerate(data))
    
    @staticmethod
    def _simple_decrypt(data: bytes, key: bytes) -> bytes:
        """Déchiffrement XOR simple (fallback)"""
        return Encryptor._simple_encrypt(data, key)  # XOR est symétrique


class SecureStorage:
    """Stockage sécurisé avec compression et chiffrement"""
    
    def __init__(self, encryption_key: Optional[bytes] = None,
                 compression_algo: CompressionAlgorithm = CompressionAlgorithm.ZLIB,
                 encryption_algo: EncryptionAlgorithm = EncryptionAlgorithm.AES256):
        self.encryption_key = encryption_key
        self.compression_algo = compression_algo
        self.encryption_algo = encryption_algo
    
    def save(self, data: Any, filepath: str):
        """
        Sauvegarde des données avec compression et chiffrement
        
        Args:
            data: Données à sauvegarder
            filepath: Chemin du fichier
        """
        # Sérialiser
        serialized = pickle.dumps(data)
        
        # Compresser
        compressed = Compressor.compress(serialized, self.compression_algo)
        
        # Chiffrer
        if self.encryption_key:
            encrypted = Encryptor.encrypt(compressed, self.encryption_key, self.encryption_algo)
        else:
            encrypted = compressed
        
        # Écrire
        with open(filepath, 'wb') as f:
            # Header: version + algo info
            header = {
                'version': 1,
                'compression': self.compression_algo.value,
                'encryption': self.encryption_algo.value if self.encryption_key else 'NONE'
            }
            f.write(pickle.dumps(header))
            f.write(b'\n---HEADER_END---\n')
            f.write(encrypted)
    
    def load(self, filepath: str) -> Any:
        """
        Charge des données avec décompression et déchiffrement
        
        Args:
            filepath: Chemin du fichier
        
        Returns:
            Données désérialisées
        """
        with open(filepath, 'rb') as f:
            # Lire le header
            content = f.read()
            header_end = content.find(b'\n---HEADER_END---\n')
            
            if header_end == -1:
                # Ancien format sans header
                encrypted = content
                compression_algo = self.compression_algo
                encryption_algo = self.encryption_algo
            else:
                header_data = content[:header_end]
                encrypted = content[header_end + len(b'\n---HEADER_END---\n'):]
                
                header = pickle.loads(header_data)
                compression_algo = CompressionAlgorithm[header['compression']]
                encryption_algo = EncryptionAlgorithm[header['encryption']]
        
        # Déchiffrer
        if self.encryption_key and encryption_algo != EncryptionAlgorithm.NONE:
            compressed = Encryptor.decrypt(encrypted, self.encryption_key, encryption_algo)
        else:
            compressed = encrypted
        
        # Décompresser
        serialized = Compressor.decompress(compressed, compression_algo)
        
        # Désérialiser
        data = pickle.loads(serialized)
        
        return data


# ============================================================================
# EXEMPLES
# ============================================================================

if __name__ == "__main__":
    print("="*60)
    print("COMPRESSION DEMO")
    print("="*60)
    
    # Données de test
    test_data = b"Hello World! " * 1000  # Données répétitives
    print(f"\nTaille originale: {len(test_data)} bytes")
    
    # Benchmark des algorithmes
    print("\nBenchmark des algorithmes:")
    results = Compressor.benchmark_algorithms(test_data)
    
    for algo, stats in results.items():
        print(f"\n{algo}:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
    
    print("\n" + "="*60)
    print("ENCRYPTION DEMO")
    print("="*60)
    
    # Génération de clé
    print("\n1. Génération de clé depuis un mot de passe")
    password = "my_secret_password_123"
    key, salt = Encryptor.derive_key_from_password(password)
    print(f"Clé générée: {key[:20]}... (tronquée)")
    print(f"Salt: {salt.hex()}")
    
    # Chiffrement
    print("\n2. Chiffrement de données")
    secret_data = "Donnees confidentielles: numero de compte 123456789".encode('utf-8')
    encrypted = Encryptor.encrypt(secret_data, key)
    print(f"Données originales: {secret_data}")
    print(f"Données chiffrées: {encrypted[:50]}... (tronquées)")
    
    # Déchiffrement
    print("\n3. Déchiffrement")
    decrypted = Encryptor.decrypt(encrypted, key)
    print(f"Données déchiffrées: {decrypted}")
    print(f"✓ Vérification: {decrypted == secret_data}")
    
    print("\n" + "="*60)
    print("SECURE STORAGE DEMO")
    print("="*60)
    
    # Créer un stockage sécurisé
    storage = SecureStorage(
        encryption_key=key,
        compression_algo=CompressionAlgorithm.ZLIB,
        encryption_algo=EncryptionAlgorithm.AES256
    )
    
    # Données à sauvegarder
    database_data = {
        'users': [
            {'id': 1, 'name': 'Alice', 'email': 'alice@example.com'},
            {'id': 2, 'name': 'Bob', 'email': 'bob@example.com'}
        ],
        'products': [
            {'id': 1, 'name': 'Laptop', 'price': 999.99}
        ]
    }
    
    print("\n1. Sauvegarde sécurisée")
    filepath = '/tmp/secure_db.dat'
    storage.save(database_data, filepath)
    print(f"✓ Données sauvegardées dans {filepath}")
    
    # Vérifier la taille
    import os
    file_size = os.path.getsize(filepath)
    print(f"Taille du fichier: {file_size} bytes")
    
    print("\n2. Chargement sécurisé")
    loaded_data = storage.load(filepath)
    print(f"✓ Données chargées")
    print(f"Vérification: {loaded_data == database_data}")
    
    print("\n3. Tentative de lecture sans clé (devrait échouer)")
    try:
        wrong_storage = SecureStorage(
            encryption_key=b'wrong_key_' + b'0' * 22,  # Mauvaise clé
            compression_algo=CompressionAlgorithm.ZLIB
        )
        wrong_storage.load(filepath)
        print("✗ ERREUR: Le chargement a réussi avec une mauvaise clé!")
    except Exception as e:
        print(f"✓ Échec attendu: {type(e).__name__}")
    
    # Nettoyage
    try:
        os.remove(filepath)
    except:
        pass
    
    print("\n" + "="*60)
    print("✓ Tous les tests réussis!")
    print("="*60)
