"""
EmailType - Type de données pour emails validés
Validation RFC 5322 compliant
"""

import re
from typing import Optional


class EmailValidator:
    """Validateur d'adresses email RFC 5322"""
    
    # Pattern RFC 5322 simplifié mais robuste
    EMAIL_PATTERN = re.compile(
        r'^[a-zA-Z0-9][a-zA-Z0-9._%+-]*@[a-zA-Z0-9][a-zA-Z0-9.-]*\.[a-zA-Z]{2,}$'
    )
    
    # Pattern strict pour validation complète
    EMAIL_STRICT_PATTERN = re.compile(
        r'^(?:[a-zA-Z0-9!#$%&\'*+/=?^_`{|}~-]+(?:\.[a-zA-Z0-9!#$%&\'*+/=?^_`{|}~-]+)*'
        r'|"(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])*")'
        r'@(?:(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?'
        r'|\[(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?|[a-zA-Z0-9-]*[a-zA-Z0-9]:(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21-\x5a\x53-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])+)\])$'
    )
    
    # Domaines jetables connus (liste partielle)
    DISPOSABLE_DOMAINS = {
        '10minutemail.com', 'guerrillamail.com', 'mailinator.com',
        'tempmail.com', 'throwaway.email', 'fakeinbox.com',
        'yopmail.com', 'maildrop.cc', 'temp-mail.org'
    }
    
    # TLDs invalides
    INVALID_TLDS = {'test', 'example', 'invalid', 'localhost'}
    
    @classmethod
    def is_valid(cls, email: str, strict: bool = False) -> bool:
        """
        Valide une adresse email
        
        Args:
            email: Adresse email à valider
            strict: Si True, utilise la validation RFC 5322 stricte
            
        Returns:
            True si l'email est valide
        """
        if not isinstance(email, str):
            return False
        
        email = email.strip().lower()
        
        if not email:
            return False
        
        # Longueur maximale
        if len(email) > 254:  # RFC 5321
            return False
        
        # Pattern matching
        pattern = cls.EMAIL_STRICT_PATTERN if strict else cls.EMAIL_PATTERN
        if not pattern.match(email):
            return False
        
        # Vérifications supplémentaires
        local_part, domain = email.rsplit('@', 1)
        
        # Longueur de la partie locale (avant @)
        if len(local_part) > 64:  # RFC 5321
            return False
        
        # Vérifier le TLD
        if '.' not in domain:
            return False
        
        tld = domain.split('.')[-1]
        if tld in cls.INVALID_TLDS:
            return False
        
        return True
    
    @classmethod
    def is_disposable(cls, email: str) -> bool:
        """
        Vérifie si l'email utilise un domaine jetable
        
        Args:
            email: Adresse email
            
        Returns:
            True si le domaine est jetable
        """
        if not cls.is_valid(email):
            return False
        
        domain = email.split('@')[1].lower()
        return domain in cls.DISPOSABLE_DOMAINS
    
    @classmethod
    def normalize(cls, email: str) -> Optional[str]:
        """
        Normalise une adresse email
        
        Args:
            email: Adresse email
            
        Returns:
            Email normalisé ou None si invalide
        """
        if not cls.is_valid(email):
            return None
        
        email = email.strip().lower()
        local_part, domain = email.rsplit('@', 1)
        
        # Normaliser certains domaines (ex: gmail)
        if domain in ['gmail.com', 'googlemail.com']:
            # Retirer les points et le +alias
            local_part = local_part.replace('.', '')
            if '+' in local_part:
                local_part = local_part.split('+')[0]
            domain = 'gmail.com'
        
        return f"{local_part}@{domain}"
    
    @classmethod
    def extract_domain(cls, email: str) -> Optional[str]:
        """Extrait le domaine d'un email"""
        if not cls.is_valid(email):
            return None
        return email.split('@')[1].lower()
    
    @classmethod
    def extract_local_part(cls, email: str) -> Optional[str]:
        """Extrait la partie locale d'un email"""
        if not cls.is_valid(email):
            return None
        return email.split('@')[0].lower()
    
    @classmethod
    def validate_with_details(cls, email: str) -> dict:
        """
        Validation détaillée avec informations
        
        Returns:
            Dictionnaire avec les détails de validation
        """
        result = {
            'valid': False,
            'email': email,
            'normalized': None,
            'local_part': None,
            'domain': None,
            'disposable': False,
            'errors': []
        }
        
        if not isinstance(email, str):
            result['errors'].append('Email must be a string')
            return result
        
        email = email.strip()
        
        if not email:
            result['errors'].append('Email is empty')
            return result
        
        if len(email) > 254:
            result['errors'].append('Email too long (max 254 chars)')
            return result
        
        if '@' not in email:
            result['errors'].append('Missing @ symbol')
            return result
        
        if email.count('@') > 1:
            result['errors'].append('Multiple @ symbols')
            return result
        
        local_part, domain = email.rsplit('@', 1)
        
        if len(local_part) > 64:
            result['errors'].append('Local part too long (max 64 chars)')
            return result
        
        if not cls.EMAIL_PATTERN.match(email.lower()):
            result['errors'].append('Invalid email format')
            return result
        
        # Validation réussie
        result['valid'] = True
        result['normalized'] = cls.normalize(email)
        result['local_part'] = local_part.lower()
        result['domain'] = domain.lower()
        result['disposable'] = cls.is_disposable(email)
        
        return result


class EmailType:
    """Type de données EMAIL avec validation"""
    
    def __init__(self, email: str, strict: bool = False):
        """
        Initialise un EmailType
        
        Args:
            email: Adresse email
            strict: Validation stricte
            
        Raises:
            ValueError: Si l'email est invalide
        """
        if not EmailValidator.is_valid(email, strict=strict):
            raise ValueError(f"Invalid email address: {email}")
        
        self.original = email.strip()
        self.normalized = EmailValidator.normalize(email)
        self.local_part = EmailValidator.extract_local_part(email)
        self.domain = EmailValidator.extract_domain(email)
        self.is_disposable = EmailValidator.is_disposable(email)
    
    def __str__(self) -> str:
        return self.normalized or self.original
    
    def __repr__(self) -> str:
        return f"Email('{self.normalized or self.original}')"
    
    def __eq__(self, other) -> bool:
        if isinstance(other, EmailType):
            return self.normalized == other.normalized
        if isinstance(other, str):
            return self.normalized == EmailValidator.normalize(other)
        return False
    
    def __hash__(self) -> int:
        return hash(self.normalized)
    
    def to_dict(self) -> dict:
        """Convertit en dictionnaire"""
        return {
            'original': self.original,
            'normalized': self.normalized,
            'local_part': self.local_part,
            'domain': self.domain,
            'is_disposable': self.is_disposable
        }


if __name__ == "__main__":
    print("=== Test EmailValidator ===\n")
    
    # Tests de validation
    test_emails = [
        "user@example.com",
        "john.doe@company.co.uk",
        "test+filter@gmail.com",
        "invalid@",
        "@invalid.com",
        "no-at-sign.com",
        "spaces in@email.com",
        "user@domain",
        "user@.com",
        "user@domain..com",
        "a" * 65 + "@example.com",  # Trop long
        "user@10minutemail.com",  # Jetable
        "user@test.invalid",  # TLD invalide
    ]
    
    print("1. Tests de validation:")
    for email in test_emails:
        is_valid = EmailValidator.is_valid(email)
        status = "✓" if is_valid else "✗"
        print(f"  {status} {email:40} -> {is_valid}")
    
    # Validation détaillée
    print("\n2. Validation détaillée:")
    email = "John.Doe+filter@Gmail.COM"
    details = EmailValidator.validate_with_details(email)
    print(f"Email: {email}")
    print(f"  Valid: {details['valid']}")
    print(f"  Normalized: {details['normalized']}")
    print(f"  Local part: {details['local_part']}")
    print(f"  Domain: {details['domain']}")
    print(f"  Disposable: {details['disposable']}")
    if details['errors']:
        print(f"  Errors: {details['errors']}")
    
    # Test EmailType
    print("\n3. Test EmailType:")
    try:
        email1 = EmailType("alice@example.com")
        print(f"✓ EmailType créé: {email1}")
        print(f"  Domain: {email1.domain}")
        print(f"  Local part: {email1.local_part}")
        print(f"  Disposable: {email1.is_disposable}")
        
        email2 = EmailType("alice@example.com")
        print(f"\nÉgalité: {email1 == email2}")
        
        # Email invalide
        try:
            invalid_email = EmailType("invalid@")
        except ValueError as e:
            print(f"\n✓ Erreur attendue: {e}")
        
    except Exception as e:
        print(f"✗ Erreur: {e}")
    
    # Normalisation Gmail
    print("\n4. Normalisation Gmail:")
    gmail_tests = [
        "john.doe@gmail.com",
        "johndoe@gmail.com",
        "john.doe+filter@gmail.com",
        "JOHN.DOE@GMAIL.COM",
    ]
    
    for email in gmail_tests:
        normalized = EmailValidator.normalize(email)
        print(f"  {email:35} -> {normalized}")
    
    # Détection de domaines jetables
    print("\n5. Détection de domaines jetables:")
    disposable_tests = [
        "user@gmail.com",
        "user@10minutemail.com",
        "user@guerrillamail.com",
        "user@company.com",
    ]
    
    for email in disposable_tests:
        is_disp = EmailValidator.is_disposable(email)
        status = "⚠️ JETABLE" if is_disp else "✓ Normal"
        print(f"  {status:15} {email}")