import asyncio
import logging
import os
import json

from mcp.server import Server
from mcp.types import Resource, Tool, TextContent

from opp import CRMClient
from tools import tool_list
import tools

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("crm_mcp_server")


def get_crm_config():
    """Get CRM configuration from environment variables."""
    config = {
        "client_id": os.getenv("CLIENT_ID"),
        "client_secret": os.getenv("CLIENT_SECRET"),
        "tenant_id": os.getenv("TENANT_ID"),
        "resource": os.getenv("RESOURCE")
    }

    missing_vars = [key for key, value in config.items() if not value]
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars.upper())}")
        raise ValueError(f"Missing required CRM configuration: {', '.join(missing_vars.upper())}")

    return config


# Initialize server
app = Server("crm_mcp_server")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List all available CRM tools."""
    logger.info("Listing available CRM tools...")
    return tool_list


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute CRM tool operation"""
    logger.info(f"Calling tool: {name} with arguments: {arguments}")
    
    try:
        config = get_crm_config()
        client = CRMClient(**config)

        match name:
            case tools.CRMMCP_GET_OPEN_OPPORTUNITIES:
                result = client.get_open_opportunities(**arguments)
            
            case tools.CRMMCP_GET_USERS:
                result = client.get_users()
                
            case tools.CRMMCP_GET_DIVISIONS:
                result = client.get_divisions()

            case _:
                logger.warning(f"Unknown tool name: {name}")
                return [TextContent(type="text", text=f"Error: Unsupported tool operation '{name}'")]

        logger.info(f"Tool {name} executed successfully")
        
        # Convert result to JSON string
        if result is None:
            result_text = "No results found"
        elif isinstance(result, (dict, list)):
            result_text = json.dumps(result, indent=2, default=str, ensure_ascii=False)
        else:
            result_text = str(result)
            
        return [TextContent(type="text", text=result_text)]

    except Exception as e:
        logger.error(f"Error executing tool {name}: {str(e)}", exc_info=True)
        return [TextContent(type="text", text=f"Error executing tool {name}: {str(e)}")]


async def main():
    """Main entry point to run the MCP server."""
    from mcp.server.stdio import stdio_server

    logger.info("Starting CRM MCP server...")
    
    try:
        # Validate config early
        get_crm_config()
        logger.info("CRM configuration validated successfully")
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return

    async with stdio_server() as (read_stream, write_stream):
        try:
            await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options()
            )
        except Exception as e:
            logger.error(f"Server error: {str(e)}", exc_info=True)
            raise


if __name__ == "__main__":
    asyncio.run(main())