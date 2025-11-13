import zlib
import bz2
import lz4.frame
from enum import Enum


# ============================================================================
# COMPRESSION
# ============================================================================

class CompressionAlgorithm(Enum):
    """Algorithmes de compression disponibles"""
    NONE = "NONE"
    ZLIB = "ZLIB"  # Rapide, bon ratio
    BZ2 = "BZ2"    # Lent, excellent ratio
    LZ4 = "LZ4"    # Très rapide, bon ratio


class Compressor:
    """Gestionnaire de compression"""
    
    @staticmethod
    def compress(data: bytes, algorithm: CompressionAlgorithm = CompressionAlgorithm.ZLIB,
                 level: int = 6) -> bytes:
        """
        Compresse des données
        
        Args:
            data: Données à compresser
            algorithm: Algorithme de compression
            level: Niveau de compression (1-9 pour ZLIB/BZ2)
        
        Returns:
            Données compressées
        """
        if algorithm == CompressionAlgorithm.NONE:
            return data
        elif algorithm == CompressionAlgorithm.ZLIB:
            return zlib.compress(data, level)
        elif algorithm == CompressionAlgorithm.BZ2:
            return bz2.compress(data, compresslevel=level)
        elif algorithm == CompressionAlgorithm.LZ4:
            return lz4.frame.compress(data)
        else:
            raise ValueError(f"Unknown compression algorithm: {algorithm}")
    
    @staticmethod
    def decompress(data: bytes, algorithm: CompressionAlgorithm = CompressionAlgorithm.ZLIB) -> bytes:
        """
        Décompresse des données
        
        Args:
            data: Données compressées
            algorithm: Algorithme utilisé
        
        Returns:
            Données décompressées
        """
        if algorithm == CompressionAlgorithm.NONE:
            return data
        elif algorithm == CompressionAlgorithm.ZLIB:
            return zlib.decompress(data)
        elif algorithm == CompressionAlgorithm.BZ2:
            return bz2.decompress(data)
        elif algorithm == CompressionAlgorithm.LZ4:
            return lz4.frame.decompress(data)
        else:
            raise ValueError(f"Unknown compression algorithm: {algorithm}")
    
    @staticmethod
    def get_compression_ratio(original_size: int, compressed_size: int) -> float:
        """Calcule le ratio de compression"""
        if original_size == 0:
            return 0.0
        return (1 - compressed_size / original_size) * 100
    
    @staticmethod
    def benchmark_algorithms(data: bytes) -> dict:
        """Compare les performances des algorithmes"""
        import time
        
        results = {}
        
        for algo in CompressionAlgorithm:
            if algo == CompressionAlgorithm.NONE:
                continue
            
            try:
                # Compression
                start = time.time()
                compressed = Compressor.compress(data, algo)
                compress_time = time.time() - start
                
                # Décompression
                start = time.time()
                Compressor.decompress(compressed, algo)
                decompress_time = time.time() - start
                
                ratio = Compressor.get_compression_ratio(len(data), len(compressed))
                
                results[algo.value] = {
                    'compressed_size': len(compressed),
                    'ratio': f"{ratio:.2f}%",
                    'compress_time': f"{compress_time*1000:.2f}ms",
                    'decompress_time': f"{decompress_time*1000:.2f}ms"
                }
            except Exception as e:
                results[algo.value] = {'error': str(e)}
        
        return results