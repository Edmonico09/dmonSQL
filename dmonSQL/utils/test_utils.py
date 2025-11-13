from helpers import (
    generate_id,
    hash_password,
    verify_password,
    format_size,
    format_duration
)
from config import Config
from logger import get_logger

# Exemples d'utilisation
if __name__ == "__main__":
    # Test logger
    logger = get_logger()
    logger.info("Test logging")
    logger.warning("Test warning")
    
    # Test config
    config = Config()
    print(f"Data dir: {config.get('database', 'data_dir')}")
    print(f"Cache size: {config.get_int('performance', 'cache_size')}")
    
    # Test helpers
    print(f"ID: {generate_id()}")
    print(f"Size: {format_size(1024 * 1024 * 50)}")
    print(f"Duration: {format_duration(125.5)}")
    
    # Test password
    password = "secret123"
    hashed, salt = hash_password(password)
    print(f"Password verified: {verify_password(password, hashed, salt)}")
