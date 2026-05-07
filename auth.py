import json
import time
import requests
from logger import logger

import sys
import os

def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

class AEPAuthHandler:
    def __init__(self, config_path="config.json"):
        # Resolve config path for PyInstaller
        self.config_path = get_resource_path(config_path)
        self.access_token = None
        self.expires_at = 0
        self.config = self._load_config()

    def _load_config(self):
        import secure_store
        
        # 1. Try Loading from Secure Storage (Priority)
        secure_creds = secure_store.load_credentials()
        if secure_creds:
            logger.info("Loaded credentials from secure storage.")
            return secure_creds
            
        # 2. Fallback to bundled config.json (Legacy/Template)
        try:
            with open(self.config_path, 'r') as f:
                logger.info("Loading credentials from config.json (Fallback).")
                return json.load(f)
        except Exception:
            logger.error(f"Config file not found at {self.config_path}")
            return {}

    def reload_config(self):
        """Reloads configuration from secure storage (useful after saving new credentials)."""
        self.config = self._load_config()
        # Clear cached token to force re-authentication
        self.access_token = None
        self.expires_at = 0
        logger.info("Configuration reloaded from storage.")
        return self.config

    def get_access_token(self):
        """Retrieves a valid access token using OAuth Server-to-Server flow."""
        if self.access_token and time.time() < self.expires_at - 30:
            return self.access_token

        logger.info("Retrieving access token (OAuth Server-to-Server)...")
        try:
            url = "https://ims-na1.adobelogin.com/ims/token/v3"
            
            # Prepare scopes
            scopes = self.config.get("scopes", ["openid", "AdobeID", "read_organizations"])
            scope_str = ",".join(scopes)

            data = {
                "grant_type": "client_credentials",
                "client_id": self.config.get("client_id"),
                "client_secret": self.config.get("client_secret"),
                "scope": scope_str
            }

            response = requests.post(url, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data["access_token"]
            
            # Set expiration
            expires_in = token_data.get("expires_in", 86400) 
            # Handle ms vs seconds just in case, though usually seconds for this flow
            if expires_in > 100000000: 
                 self.expires_at = time.time() + (expires_in / 1000)
            else:
                 self.expires_at = time.time() + expires_in

            logger.info("Access token retrieved successfully.")
            return self.access_token

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to retrieve access token: {e}")
            if e.response is not None:
                logger.error(f"Response: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during auth: {e}")
            raise



    def get_headers(self):
        """Returns standard headers for AEP API calls."""
        token = self.get_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "x-api-key": self.config.get("client_id"),
            "x-gw-ims-org-id": self.config.get("org_id"),
            "x-sandbox-name": self.config.get("sandbox_name", "prod"),
            "Accept": "*/*"
        }
