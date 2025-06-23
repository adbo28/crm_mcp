from mcp.types import Resource, Tool, TextContent


# Core CRM operations
CRMMCP_GET_OPEN_OPPORTUNITIES = "get_open_opportunities"
CRMMCP_GET_USERS = "get_users"
CRMMCP_GET_DIVISIONS = "get_divisions"


tool_list = [
    Tool(
        name=CRMMCP_GET_OPEN_OPPORTUNITIES,
        description="Get open opportunities with optional filtering by Owner and/or Division. Returns opportunities with human-readable names for owners, customers, and divisions.",
        inputSchema={
            "type": "object",
            "properties": {
                "top": {
                    "description": "Maximum number of records to return",
                    "type": "integer",
                    "default": 1000
                },
                "owner": {
                    "description": "Filter by owner name (e.g., 'John Smith'). Will be resolved to ID automatically",
                    "type": "string"
                },
                "division": {
                    "description": "Filter by division name (e.g., 'Sales'). Will be resolved to ID automatically",
                    "type": "string"
                }
            },
            "required": []
        }
    ),
    Tool(
        name=CRMMCP_GET_USERS,
        description="Get all active users who can own opportunities. Returns list of users with their full names, domain names, and system user IDs.",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": []
        }
    ),
    Tool(
        name=CRMMCP_GET_DIVISIONS,
        description="Get all active business units (divisions) from Dynamics 365. Returns list of divisions with names, division names, and business unit IDs.",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": []
        }
    )
]