import os
import json
from cryptography.fernet import Fernet
from logger import logger

# Cross-platform credential storage
APP_DATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "AEP_DataExplorer")
CREDENTIALS_FILE = os.path.join(APP_DATA_DIR, "credentials.enc")

# Encryption key for local credential storage
APP_KEY = b'wX0GaaqYgW-jWj5Lh_5hJqUqfT8b_X9X9X9X9X9X9X8=' 

cipher_suite = Fernet(APP_KEY)

def save_credentials(client_id, client_secret, org_id, sandbox_name, query_service=None, segment_query_template=None):
    """Saves encrypted credentials to disk."""
    try:
        if not os.path.exists(APP_DATA_DIR):
            os.makedirs(APP_DATA_DIR)
            
        data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "org_id": org_id,
            "sandbox_name": sandbox_name,
            "scopes": ["openid", "AdobeID", "session", "read_organizations", "additional_info.projectedProductContext"]
        }
        
        # Add Query Service credentials if provided
        if query_service:
            data["query_service"] = query_service
        
        # Add Segment Query Template if provided
        if segment_query_template:
            data["segment_query_template"] = segment_query_template
        
        json_bytes = json.dumps(data).encode('utf-8')
        encrypted_data = cipher_suite.encrypt(json_bytes)
        
        with open(CREDENTIALS_FILE, 'wb') as f:
            f.write(encrypted_data)
            
        logger.info(f"Credentials saved securely to {CREDENTIALS_FILE}")
        return True
    except Exception as e:
        logger.error(f"Failed to save credentials: {e}")
        return False

def load_credentials():
    """Loads and decrypts credentials from disk."""
    try:
        if not os.path.exists(CREDENTIALS_FILE):
            return None
            
        with open(CREDENTIALS_FILE, 'rb') as f:
            encrypted_data = f.read()
            
        decrypted_data = cipher_suite.decrypt(encrypted_data)
        return json.loads(decrypted_data.decode('utf-8'))
        
    except Exception as e:
        logger.error(f"Failed to load credentials: {e}")
        return None

def has_credentials():
    """Checks if credentials exist."""
    return os.path.exists(CREDENTIALS_FILE)

def delete_credentials():
    """Deletes credentials file."""
    try:
        if os.path.exists(CREDENTIALS_FILE):
            os.remove(CREDENTIALS_FILE)
            logger.info("Credentials deleted")
            return True
        return False
    except Exception as e:
        logger.error(f"Failed to delete credentials: {e}")
        return False

