import re
class EmailValidator:
    """Validateur d'emails"""
    EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    
    @staticmethod
    def is_valid(email: str) -> bool:
        if not isinstance(email, str):
            return False
        return EmailValidator.EMAIL_REGEX.match(email) is not None