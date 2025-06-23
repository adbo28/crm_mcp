import os, json, requests
import msal
from datetime import datetime, timedelta
import logging
from pathlib import Path

CACHE_FILE = "C:\\dev\\crm_mcp\\crm_mcp\\crm_entity_cache.json"
CACHE_EXPIRY_HOURS = 176  # ~1 week


class EntityCache:
    """Lazy-loading entity cache for CRM lookups"""
    
    def __init__(self, access_token, api_url):
        self.access_token = access_token
        self.api_url = api_url
        self.cache_data = self._load_cache()
        
    def _load_cache(self):
        """Load cache from file"""
        if Path(CACHE_FILE).exists():
            try:
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logging.warning(f"Failed to load cache file: {e}")
        return {}
    
    def _save_cache(self):
        """Save cache to file"""
        try:
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.cache_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.warning(f"Failed to save cache file: {e}")
    
    def _is_cache_entry_valid(self, cache_entry):
        """Check if cache entry is still valid"""
        if not cache_entry or 'timestamp' not in cache_entry:
            return False
        
        try:
            saved_time = datetime.fromisoformat(cache_entry['timestamp'])
            expiry_time = datetime.now() - timedelta(hours=CACHE_EXPIRY_HOURS)
            return saved_time > expiry_time
        except Exception:
            return False
    
    def _fetch_from_crm(self, entity_type, entity_id):
        """Fetch entity name from CRM API"""
        entity_configs = {
            'account': {'endpoint': 'accounts', 'name_field': 'name'},
            'contact': {'endpoint': 'contacts', 'name_field': 'fullname'},
            'user': {'endpoint': 'systemusers', 'name_field': 'fullname'},
            'division': {'endpoint': 'businessunits', 'name_field': 'name'},
            'service': {'endpoint': 'actum_proposedservices', 'name_field': 'actum_name'}
        }
        
        if entity_type not in entity_configs:
            return f"Unknown type ({entity_type})"
        
        config = entity_configs[entity_type]
        url = f"{self.api_url}/{config['endpoint']}({entity_id})"
        headers = {'Authorization': f'Bearer {self.access_token}', 'Accept': 'application/json'}
        params = {'$select': config['name_field']}
        
        try:
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                return data.get(config['name_field'], f"No name ({entity_id[:8]}...)")
            elif response.status_code == 404:
                return f"Not found ({entity_id[:8]}...)"
            else:
                return f"Error {response.status_code} ({entity_id[:8]}...)"
                
        except Exception as e:
            logging.warning(f"Error fetching {entity_type} {entity_id}: {e}")
            return f"Error ({entity_id[:8]}...)"
    
    def entity_lookup(self, entity_type, entity_id):
        """Main lookup method with lazy caching"""
        if not entity_id:
            return 'N/A'
        
        cache_key = f"{entity_type}_{entity_id}"
        
        # Check cache first
        if cache_key in self.cache_data:
            cache_entry = self.cache_data[cache_key]
            if self._is_cache_entry_valid(cache_entry):
                return cache_entry['name']
            else:
                del self.cache_data[cache_key]
                logging.info(f"Cache expired for {entity_type} {entity_id[:8]}...")
        
        # Fetch from CRM
        logging.info(f"Fetching {entity_type} {entity_id[:8]}... from CRM")
        name = self._fetch_from_crm(entity_type, entity_id)
        
        # Store in cache
        self.cache_data[cache_key] = {
            'name': name,
            'timestamp': datetime.now().isoformat()
        }
        self._save_cache()
        return name
    
    def get_customer_name(self, customer_id):
        """Get customer name (try account first, then contact)"""
        if not customer_id:
            return 'N/A'
        
        # Try account first
        name = self.entity_lookup('account', customer_id)
        if name and not name.startswith(('Unknown', 'Not found', 'Error')):
            return name
        
        # If account lookup failed, try contact
        return self.entity_lookup('contact', customer_id)
    
    def reverse_lookup(self, entity_type, search_name):
        """Find entity ID by name (reverse lookup)"""
        if not search_name:
            return None
        
        entity_configs = {
            'user': {'endpoint': 'systemusers', 'name_field': 'fullname', 'id_field': 'systemuserid'},
            'division': {'endpoint': 'businessunits', 'name_field': 'name', 'id_field': 'businessunitid'}
        }
        
        if entity_type not in entity_configs:
            logging.warning(f"Reverse lookup not supported for entity type: {entity_type}")
            return None
        
        config = entity_configs[entity_type]
        headers = {'Authorization': f'Bearer {self.access_token}', 'Accept': 'application/json'}
        url = f"{self.api_url}/{config['endpoint']}"
        
        # Try exact match first, then partial match
        for filter_type, filter_expr in [
            ('exact', f"{config['name_field']} eq '{search_name}'"),
            ('partial', f"contains({config['name_field']}, '{search_name}')")
        ]:
            params = {
                '$filter': filter_expr,
                '$select': f"{config['id_field']},{config['name_field']}",
                '$top': 1
            }
            
            try:
                response = requests.get(url, headers=headers, params=params)
                if response.status_code == 200:
                    results = response.json().get('value', [])
                    if results:
                        result = results[0]
                        entity_id = result.get(config['id_field'])
                        entity_name = result.get(config['name_field'])
                        
                        if entity_id:
                            # Cache the result
                            cache_key = f"{entity_type}_{entity_id}"
                            self.cache_data[cache_key] = {
                                'name': entity_name,
                                'timestamp': datetime.now().isoformat()
                            }
                            self._save_cache()
                            
                            match_type = "exact" if filter_type == 'exact' else f"partial: '{entity_name}'"
                            logging.info(f"Found {entity_type} ({match_type}): '{search_name}' -> {entity_id}")
                            return entity_id
            except Exception as e:
                logging.error(f"Error in reverse lookup for {entity_type} '{search_name}': {e}")
                break
        
        logging.warning(f"No {entity_type} found matching: '{search_name}'")
        return None


class CRMClient:
    def __init__(self, client_id, client_secret, tenant_id, resource):
        self.CLIENT_ID = client_id
        self.CLIENT_SECRET = client_secret
        self.TENANT_ID = tenant_id
        self.RESOURCE = resource
        self.API_URL = f'{resource}/api/data/v9.1'
        self.access_token = self._get_access_token()
        self.user_id = self._get_current_user_id()
        self.entity_cache = EntityCache(self.access_token, self.API_URL)
        logging.info(f'Current user ID: {self.user_id}')

    def _get_access_token(self):
        """Get Dynamics 365 access token"""
        authority = f'https://login.microsoftonline.com/{self.TENANT_ID}'
        app = msal.ConfidentialClientApplication(
            self.CLIENT_ID,
            authority=authority,
            client_credential=self.CLIENT_SECRET
        )
        result = app.acquire_token_for_client(scopes=[f'{self.RESOURCE}/.default'])

        if 'access_token' not in result:
            error_msg = f"Failed to acquire access token: {result.get('error')} - {result.get('error_description')}"
            raise ConnectionError(error_msg)

        return result['access_token']

    def _get_headers(self):
        """Get standard request headers"""
        return {
            'Authorization': f'Bearer {self.access_token}',
            'OData-MaxVersion': '4.0',
            'OData-Version': '4.0',
            'Accept': 'application/json',
            'Content-Type': 'application/json; charset=utf-8'
        }

    def _get_current_user_id(self):
        """Get the user ID associated with the current token"""
        response = requests.get(f'{self.API_URL}/WhoAmI', headers=self._get_headers())
        
        if response.status_code == 200:
            result = response.json()
            return result.get('UserId')
        else:
            raise ValueError(f"Unable to get current user ID: HTTP {response.status_code}")

    def _clean_opportunity_data(self, opportunity):
        """Clean up opportunity data by removing non-human-readable fields"""
        fields_to_remove = [
            '_ownerid_value', '_customerid_value', '_actum_divisionid_value',
            '_transactioncurrencyid_value', '@odata.etag', 'opportunityid'
        ]
        
        for field in fields_to_remove:
            opportunity.pop(field, None)

    def get_open_opportunities(self, top=1000, owner=None, division=None):
        """
        Get only open opportunities (status = Open) with optional filtering
        
        Args:
            top (int): Maximum number of records to return
            owner (str): Filter by owner name - will be resolved to ID
            division (str): Filter by division name - will be resolved to ID
        """
        # Build filter conditions
        filter_conditions = ['statecode eq 0']  # 0 = Open
        
        # Resolve owner name to ID if provided
        if owner:
            owner_id = self.entity_cache.reverse_lookup('user', owner)
            if owner_id:
                filter_conditions.append(f"_ownerid_value eq '{owner_id}'")
                logging.info(f"Filtered by owner: '{owner}' -> {owner_id}")
            else:
                logging.warning(f"Owner '{owner}' not found - ignoring filter")
        
        # Resolve division name to ID if provided
        if division:
            division_id = self.entity_cache.reverse_lookup('division', division)
            if division_id:
                filter_conditions.append(f"_actum_divisionid_value eq '{division_id}'")
                logging.info(f"Filtered by division: '{division}' -> {division_id}")
            else:
                logging.warning(f"Division '{division}' not found - ignoring filter")
        
        params = {
            '$filter': ' and '.join(filter_conditions),
            '$select': 'createdon,name,stepname,modifiedon,_actum_divisionid_value,_ownerid_value,estimatedvalue_base,estimatedclosedate,_customerid_value',
            '$orderby': 'createdon desc',
            '$top': top
        }

        response = requests.get(f'{self.API_URL}/opportunities', headers=self._get_headers(), params=params)
        
        if response.status_code != 200:
            return {
                "status": "error",
                "status_code": response.status_code,
                "message": "Failed to fetch opportunities",
                "response": response.text
            }

        result = response.json()

        # Enrich data with human-readable names and clean up
        for opportunity in result.get('value', []):
            opportunity['owner_name'] = self.entity_cache.entity_lookup('user', opportunity.get('_ownerid_value', ''))
            opportunity['customer_name'] = self.entity_cache.get_customer_name(opportunity.get('_customerid_value', ''))
            opportunity['division_name'] = self.entity_cache.entity_lookup('division', opportunity.get('_actum_divisionid_value', ''))
            self._clean_opportunity_data(opportunity)

        return result

    def get_divisions(self):
        """Get all active business units (divisions)"""
        params = {
            '$select': 'businessunitid,name,divisionname,createdon,modifiedon,isdisabled,description',
            '$filter': 'isdisabled eq false',
            '$orderby': 'name',
            '$top': 500
        }
        
        response = requests.get(f"{self.API_URL}/businessunits", headers=self._get_headers(), params=params)
        
        if response.status_code != 200:
            logging.error(f"Error getting business units: HTTP {response.status_code}")
            return []
        
        data = response.json()
        return [
            {
                'name': d.get('name', 'N/A'),
                'divisionname': d.get('divisionname', 'N/A'),
                'businessunitid': d.get('businessunitid', 'N/A'),
            }
            for d in data.get('value', [])
        ]

    def get_users(self):
        """Get all active users who can own opportunities"""
        params = {
            '$filter': 'isdisabled eq false',
            '$select': 'systemuserid,fullname,domainname,firstname,lastname',
            '$orderby': 'fullname',
            '$top': 500
        }
        
        response = requests.get(f"{self.API_URL}/systemusers", headers=self._get_headers(), params=params)
        
        if response.status_code != 200:
            logging.error(f"Error getting users: HTTP {response.status_code}")
            return []
        
        data = response.json()
        return [
            {
                'fullname': u.get('fullname', 'N/A'),
                'domainname': u.get('domainname', 'N/A'),
                'systemuserid': u.get('systemuserid', 'N/A'),
            }
            for u in data.get('value', [])
        ]

### example usage #########################################

if __name__ == '__main__':
    # Helper function to format API responses for display
    def format_response(response, max_length=500):
        """Format API response for pretty printing"""
        try:
            if isinstance(response, bytes):
                # Parse bytes to JSON
                data = json.loads(response.decode('utf-8'))
                formatted = json.dumps(data, indent=2)
            elif isinstance(response, dict):
                formatted = json.dumps(response, indent=2)
            else:
                formatted = str(response)
            
            # Truncate if too long
            return formatted[:max_length] + "..." if len(formatted) > max_length else formatted
        except Exception as e:
            return f"Error formatting response: {e}\nRaw response: {str(response)[:max_length]}"
    
    # Configure logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    # Get configuration from environment variables
    config = {
        "client_id": os.getenv("CLIENT_ID"),
        "client_secret": os.getenv("CLIENT_SECRET"),
        "tenant_id": os.getenv("TENANT_ID"),
        "resource": os.getenv("RESOURCE")
    }
    
    # Check if all required environment variables are set
    if not all(config.values()):
        print("Error: Missing required environment variables:")
        print("CLIENT_ID, CLIENT_SECRET, TENANT_ID, and RESOURCE must be set")
        exit(1)
    
    # Example usage
    try:
        # Initialize the CRM client
        print("=" * 60)
        print("Initializing CRM Client...")
        print("=" * 60)
        
        crm_client = CRMClient(
            client_id=config["client_id"],
            client_secret=config["client_secret"], 
            tenant_id=config["tenant_id"],
            resource=config["resource"]
        )

        ###################################################

        print("=" * 60)
        print("Testing Enhanced get_open_opportunities")
        print("=" * 60)
        
        # Test 1: Filter by owner name
        print("Test 1: Filter by owner name 'John Brown'")
        result1 = crm_client.get_open_opportunities(top=3, owner="John Brown")
        print("Result:")
        print(format_response(result1, max_length=1000))
        print()
        
        # Test 2: Filter by division name (you'll need to replace with actual division name)
        print("Test 2: Filter by division name 'Actum Digital' (adjust as needed)")
        result2 = crm_client.get_open_opportunities(top=3, division="Division1")
        print("Result:")
        print(format_response(result2, max_length=1000))
        print()
        
        # Test 3: Filter by both owner and division
        print("Test 3: Filter by both owner and division")
        result3 = crm_client.get_open_opportunities(top=3, owner="John Brown", division="Division1")
        print("Result:")
        print(format_response(result3, max_length=1000))
        print()

        
    except ConnectionError as e:
        print(f"Connection Error: {e}")
        print("Please check your credentials and network connection.")
    except ValueError as e:
        print(f"Value Error: {e}")
        print("Please check your configuration and API responses.")
    except Exception as e:
        print(f"Unexpected Error: {e}")
        print("Please check the error details and try again.")