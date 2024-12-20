import requests
from datetime import datetime, timezone
import time
import json
from typing import Dict, List, Optional
from tokenmanager import SecureTokenManager

class EcoTwinAPIClient:
    """Client for interacting with the ecoTwin™ API v2."""
    
    def __init__(self, token_manager: Optional[SecureTokenManager] = None):
        """
        Initialize the API client.
        
        Args:
            token_manager: Optional SecureTokenManager instance. If not provided,
                         a new instance will be created.
        """
        self.token_manager = token_manager or SecureTokenManager()
        self._load_credentials()
        
    def _load_credentials(self):
        """Load credentials from the token manager."""
        credentials = self.token_manager.get_credentials()
        self.client_id = credentials['client_id']
        self.client_secret = credentials['client_secret']
        self.resource = credentials['resource']

    def _get_access_token(self) -> str:
        """
        Get a new access token from Azure AAD.
        
        Returns:
            str: The access token
        """
        # First check if we have a valid stored token
        token_data = self.token_manager.get_token()
        if token_data:
            return token_data['access_token']

        # If not, get a new token
        url = "https://login.microsoftonline.com/privagroup.onmicrosoft.com/oauth2/token"
        
        payload = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'resource': self.resource
        }
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        response = requests.post(url, headers=headers, data=payload)
        response.raise_for_status()
        
        token_data = response.json()
        # Convert expires_in to int before adding to current time
        expires_in = int(token_data.get('expires_in', '3600'))
        token_data['expires_at'] = time.time() + expires_in
        
        # Store the token securely
        self.token_manager.store_token(token_data)
        
        return token_data['access_token']
    
    def _ensure_valid_token(self):
        """Ensure we have a valid access token, refreshing if necessary."""
        token_data = self.token_manager.get_token()
        if not token_data:
            self._get_access_token()
            token_data = self.token_manager.get_token()
        return token_data['access_token']
    
    def create_eco_forecast(self, project_id: str, virtual_io_values: Dict[str, List[float]], 
                          interval: int = 300) -> dict:
        """
        Create an ECO Forecast JSON object.
        
        Args:
            project_id: The ecoTwin™ Identifier
            virtual_io_values: Dictionary mapping VirtualIO names to lists of values
            interval: Number of seconds between setpoints (default: 300)
            
        Returns:
            dict: The ECO Forecast JSON object
        """
        # Ensure each array has at least 288 values (24 hours worth of data)
        min_length = 86400 // interval  # 24 hours in seconds divided by interval
        
        for io_name, values in virtual_io_values.items():
            if len(values) < min_length:
                raise ValueError(f"VirtualIO {io_name} must have at least {min_length} values")
        
        forecast = {
            "header": {
                "projectId": project_id,
                "interval": interval,
                "start_t": int(datetime.now(timezone.utc).timestamp())
            },
            "timeseries": {
                "y": virtual_io_values,
                "n": {}
            }
        }
        
        return forecast
    
    def put_forecast(self, eco_twin_id: str, forecast: dict, check: bool = True) -> requests.Response:
        """
        Send an ECO Forecast to the API.
        
        Args:
            eco_twin_id: The ecoTwin identifier
            forecast: The forecast JSON object
            check: Whether to perform validation checks
            
        Returns:
            requests.Response: The API response
        """
        access_token = self._ensure_valid_token()
        
        url = f"https://energyoptimizer.azure-api.net/eco/v2/twins/{eco_twin_id}/forecast/external"
        if check:
            url += "?check"
            
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.put(url, headers=headers, json=forecast)
        response.raise_for_status()
        return response
    
    def get_twin_status(self, eco_twin_id: str) -> dict:
        """
        Get the status for a specific ecoTwin.
        
        Args:
            eco_twin_id: The ecoTwin identifier
            
        Returns:
            dict: The status information
        """
        access_token = self._ensure_valid_token()
        
        url = f"https://energyoptimizer.azure-api.net/eco/v2/twins/{eco_twin_id}/status"
        headers = {
            'Authorization': f'Bearer {access_token}'
        }
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    
    def get_all_twins_status(self) -> List[dict]:
        """
        Get status for all authorized ecoTwins.
        
        Returns:
            List[dict]: List of status information for all authorized twins
        """
        access_token = self._ensure_valid_token()
        
        url = "https://energyoptimizer.azure-api.net/eco/v2/status"
        headers = {
            'Authorization': f'Bearer {access_token}'
        }
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
