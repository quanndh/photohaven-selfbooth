# Preset Encryption Guide

## Overview

To protect your intellectual property (presets), you can encrypt your `.xmp` preset files. Encrypted presets cannot be easily read or copied by staff/clients.

## Quick Start

### 1. Generate Encryption Key

```bash
python preset_encryption.py generate-key
```

This will output a key like:
```
Generated encryption key (save this securely):
gAAAAABh... (long base64 string)
```

### 2. Set Environment Variable

**macOS/Linux:**
```bash
export PRESET_ENCRYPTION_KEY='your_generated_key_here'
```

**Windows (Command Prompt):**
```cmd
set PRESET_ENCRYPTION_KEY=your_generated_key_here
```

**Windows (PowerShell):**
```powershell
$env:PRESET_ENCRYPTION_KEY='your_generated_key_here'
```

**Permanent (macOS/Linux):**
Add to `~/.bashrc` or `~/.zshrc`:
```bash
export PRESET_ENCRYPTION_KEY='your_generated_key_here'
```

### 3. Encrypt Your Preset

```bash
python preset_encryption.py encrypt vista.xmp vista.xmp.encrypted
```

This creates `vista.xmp.encrypted` - the encrypted version of your preset.

### 4. Update Config

In `config.yaml`, point to the encrypted preset:
```yaml
preset_path: "../vista.xmp.encrypted"
```

The application will automatically detect and decrypt it during processing.

### 5. Deploy

**On client machines:**
- Deploy the encrypted preset file (`.encrypted`)
- Set the `PRESET_ENCRYPTION_KEY` environment variable
- The application will decrypt and use it automatically
- Staff cannot easily extract the preset values

## Security Notes

1. **Keep the key secret** - Never commit it to version control
2. **Use different keys per client** - If one key is compromised, others remain safe
3. **Rotate keys periodically** - Re-encrypt presets with new keys
4. **Store keys securely** - Use password managers or secure key management services

## How It Works

1. **Encryption Process:**
   - Original `.xmp` file is compressed (zlib)
   - Compressed data is encrypted (Fernet symmetric encryption)
   - Encrypted data is base64 encoded for safe storage

2. **Decryption Process:**
   - Application detects `.encrypted` extension
   - Reads encrypted file
   - Decrypts using key from environment variable
   - Decompresses to original `.xmp` format
   - Parses as normal preset

3. **Protection Level:**
   - Without the key, the preset is unreadable
   - Even if someone copies the `.encrypted` file, they cannot extract the preset
   - The key is never stored in code or config files

## Troubleshooting

### "preset_encryption module required"
Install cryptography:
```bash
pip install cryptography
```

### "Failed to decrypt preset"
- Check that `PRESET_ENCRYPTION_KEY` is set correctly
- Ensure you're using the same key that was used to encrypt
- Verify the encrypted file wasn't corrupted

### "Preset file not found"
- Check the path in `config.yaml`
- Ensure the `.encrypted` file exists
- Verify file permissions

## Advanced: Per-Client Keys

For maximum security, use different encryption keys for different clients:

1. Generate unique key per client
2. Encrypt preset with client-specific key
3. Deploy encrypted preset + key to client
4. If one client's key is compromised, others remain safe

Example:
```bash
# Client A
export PRESET_ENCRYPTION_KEY='key_for_client_a'
python preset_encryption.py encrypt vista.xmp vista_client_a.xmp.encrypted

# Client B
export PRESET_ENCRYPTION_KEY='key_for_client_b'
python preset_encryption.py encrypt vista.xmp vista_client_b.xmp.encrypted
```

