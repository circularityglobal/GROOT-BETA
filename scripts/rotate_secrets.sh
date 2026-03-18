#!/bin/bash
# =============================================================================
# REFINET Cloud — Secret Rotation Helper
# Generates new secrets and displays them for manual .env update
# =============================================================================

echo "REFINET Cloud — Secret Rotation"
echo "================================"
echo ""
echo "New values (copy to .env and restart services):"
echo ""
echo "SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(64))')"
echo "REFRESH_SECRET=$(python3 -c 'import secrets; print(secrets.token_hex(64))')"
echo "SERVER_PEPPER=$(python3 -c 'import secrets; print(secrets.token_hex(64))')"
echo "WEBHOOK_SIGNING_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
echo "INTERNAL_DB_ENCRYPTION_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
echo "ADMIN_API_SECRET=$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
echo ""
echo "WARNING: Rotating SECRET_KEY will invalidate all JWTs."
echo "WARNING: Rotating SERVER_PEPPER will break all password hashes."
echo "WARNING: Rotating INTERNAL_DB_ENCRYPTION_KEY will break internal secret decryption."
echo ""
echo "After updating .env, run: sudo systemctl restart refinet-api"
