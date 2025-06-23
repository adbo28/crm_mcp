# CRM MCP Server

A Model Context Protocol (MCP) server that provides read-only access to Microsoft Dynamics 365 CRM data. Enables AI assistants to query opportunities, users, and divisions through natural language.

## Features

- **Open Opportunities**: Query active opportunities with filtering by owner/division
- **Smart Caching**: Automatic entity name resolution with 1-week cache
- **Human-Readable**: Converts IDs to names (owners, customers, divisions)
- **Secure**: Authentication via Azure AD

## Quick Start

1. **Install dependencies:**
```bash
pip install msal requests
```

2. **Set environment variables:**
```bash
export CLIENT_ID="your-azure-app-client-id"
export CLIENT_SECRET="your-azure-app-client-secret"
export TENANT_ID="your-azure-tenant-id"
export RESOURCE="https://your-crm-instance.crm.dynamics.com"
```

3. **Run standalone:**
```python
from crm_client import CRMClient

crm = CRMClient(client_id, client_secret, tenant_id, resource)
opportunities = crm.get_open_opportunities(owner="John Smith", top=10)
```

## MCP Tools

### `get_open_opportunities`
Get active opportunities with optional filtering.
- `owner` (string): Filter by owner name
- `division` (string): Filter by division name  
- `top` (integer): Max records (default: 1000)

### `get_users`
List all active CRM users with names and IDs.

### `get_divisions` 
List all active business units/divisions.

## Example Queries

```python
# Filter by owner
my_opps = crm.get_open_opportunities(owner="Jane Doe")

# Filter by division
sales_opps = crm.get_open_opportunities(division="Sales")

# Get team info
users = crm.get_users()
divisions = crm.get_divisions()
```

## Use Cases

- **AI Assistant Integration**: "Show me John's open opportunities"
- **Sales Standups**: Quick pipeline reviews
- **Reporting**: Export opportunity data for analysis

## Architecture

- **CRMClient**: Main API interface with OAuth2 auth
- **EntityCache**: Smart caching for name lookups (1-week TTL)
- **MCP Integration**: Standard tool definitions for AI assistants

Cache stored in `crm_entity_cache.json` - delete to force refresh.

## License

MIT License