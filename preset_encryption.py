"""
Preset Encryption/Protection Module
Encrypts and obfuscates Lightroom preset files to protect intellectual property
"""

import base64
import zlib
from pathlib import Path
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import os


class PresetEncryption:
    """Encrypt and decrypt preset files to protect IP"""
    
    def __init__(self, key: Optional[bytes] = None):
        """
        Initialize encryption with a key
        
        Args:
            key: Encryption key (bytes). If None, generates a key from environment variable
        """
        if key is None:
            # Try to get key from environment variable
            key_str = os.environ.get('PRESET_ENCRYPTION_KEY')
            if key_str:
                key = key_str.encode()
            else:
                # Generate a default key (in production, this should be set via environment)
                # This is just for development - production should use a secure key
                key = b'default_key_change_in_production_32_bytes_long!!'
        
        # Derive a Fernet key from the provided key
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'preset_salt_12345678',  # In production, use random salt per preset
            iterations=100000,
        )
        key_derived = base64.urlsafe_b64encode(kdf.derive(key))
        self.cipher = Fernet(key_derived)
    
    def encrypt_preset(self, preset_path: str, output_path: Optional[str] = None) -> str:
        """
        Encrypt a preset file
        
        Args:
            preset_path: Path to original .xmp preset file
            output_path: Path to save encrypted preset (default: adds .encrypted extension)
            
        Returns:
            Path to encrypted preset file
        """
        preset_path = Path(preset_path)
        
        if not preset_path.exists():
            raise FileNotFoundError(f"Preset file not found: {preset_path}")
        
        # Read original preset
        with open(preset_path, 'rb') as f:
            preset_data = f.read()
        
        # Compress first (saves space and adds obfuscation)
        compressed = zlib.compress(preset_data, level=9)
        
        # Encrypt
        encrypted = self.cipher.encrypt(compressed)
        
        # Encode as base64 for safe storage
        encoded = base64.b64encode(encrypted)
        
        # Determine output path
        if output_path is None:
            output_path = preset_path.with_suffix('.xmp.encrypted')
        else:
            output_path = Path(output_path)
        
        # Write encrypted preset
        with open(output_path, 'wb') as f:
            f.write(encoded)
        
        return str(output_path)
    
    def decrypt_preset(self, encrypted_path: str, output_path: Optional[str] = None) -> str:
        """
        Decrypt a preset file
        
        Args:
            encrypted_path: Path to encrypted preset file
            output_path: Path to save decrypted preset (default: removes .encrypted extension)
            
        Returns:
            Path to decrypted preset file
        """
        encrypted_path = Path(encrypted_path)
        
        if not encrypted_path.exists():
            raise FileNotFoundError(f"Encrypted preset file not found: {encrypted_path}")
        
        # Read encrypted preset
        with open(encrypted_path, 'rb') as f:
            encoded = f.read()
        
        # Decode from base64
        encrypted = base64.b64decode(encoded)
        
        # Decrypt
        compressed = self.cipher.decrypt(encrypted)
        
        # Decompress
        preset_data = zlib.decompress(compressed)
        
        # Determine output path
        if output_path is None:
            if encrypted_path.suffix == '.encrypted':
                output_path = encrypted_path.with_suffix('')
            else:
                output_path = encrypted_path.with_suffix('.xmp')
        else:
            output_path = Path(output_path)
        
        # Write decrypted preset
        with open(output_path, 'wb') as f:
            f.write(preset_data)
        
        return str(output_path)
    
    def decrypt_to_memory(self, encrypted_path: str) -> bytes:
        """
        Decrypt a preset file to memory (for processing without writing to disk)
        
        Args:
            encrypted_path: Path to encrypted preset file
            
        Returns:
            Decrypted preset data as bytes
        """
        encrypted_path = Path(encrypted_path)
        
        if not encrypted_path.exists():
            raise FileNotFoundError(f"Encrypted preset file not found: {encrypted_path}")
        
        # Read encrypted preset
        with open(encrypted_path, 'rb') as f:
            encoded = f.read()
        
        # Decode from base64
        encrypted = base64.b64decode(encoded)
        
        # Decrypt
        compressed = self.cipher.decrypt(encrypted)
        
        # Decompress
        preset_data = zlib.decompress(compressed)
        
        return preset_data


def generate_key() -> bytes:
    """Generate a secure random encryption key"""
    return Fernet.generate_key()


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 3:
        print("Usage:")
        print("  Encrypt: python preset_encryption.py encrypt <preset.xmp> [output.encrypted]")
        print("  Decrypt: python preset_encryption.py decrypt <preset.encrypted> [output.xmp]")
        print("  Generate key: python preset_encryption.py generate-key")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'generate-key':
        key = generate_key()
        print(f"Generated encryption key (save this securely):")
        print(key.decode())
        print("\nSet it as environment variable:")
        print(f"export PRESET_ENCRYPTION_KEY='{key.decode()}'")
        sys.exit(0)
    
    # Get key from environment or use default
    key_str = os.environ.get('PRESET_ENCRYPTION_KEY')
    if key_str:
        encryption = PresetEncryption(key_str.encode())
    else:
        print("Warning: Using default key. Set PRESET_ENCRYPTION_KEY environment variable for production.")
        encryption = PresetEncryption()
    
    if command == 'encrypt':
        preset_path = sys.argv[2]
        output_path = sys.argv[3] if len(sys.argv) > 3 else None
        result = encryption.encrypt_preset(preset_path, output_path)
        print(f"Encrypted preset saved to: {result}")
    
    elif command == 'decrypt':
        encrypted_path = sys.argv[2]
        output_path = sys.argv[3] if len(sys.argv) > 3 else None
        result = encryption.decrypt_preset(encrypted_path, output_path)
        print(f"Decrypted preset saved to: {result}")
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

