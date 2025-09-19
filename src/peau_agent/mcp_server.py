import os
import logging
import asyncio
import json
import threading
from flask import Flask, request, jsonify
from flask_cors import CORS
from typing import List, Dict, Any

# MCP Server Imports
import mcp.types as mcp_types
from mcp.server.lowlevel import Server, NotificationOptions
from mcp.server.models import InitializationOptions
# ADK Tool Imports for MCP exposure
from google.adk.tools.function_tool import FunctionTool
from google.adk.tools.mcp_tool.conversion_utils import adk_to_mcp_tool_type

from peau_agent import PEAUAgent # Assuming peau_agent.py is in the same directory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "severity": "%(levelname)s", "message": "%(message)s"}',
    datefmt='%Y-%m-%dT%H:%M:%S.%fZ'
)
logger = logging.getLogger(__name__)

# Initialize PEAU Agent (global instance)
project_id = os.getenv("PROJECT_ID", "your-gcp-project-id")
location = os.getenv("LOCATION", "us-central1")
peau_agent_instance = PEAUAgent(project_id, location)

# Initialize Flask app for HTTP endpoint (for behavior tracking simulation and health checks)
flask_app = Flask(__name__)
CORS(flask_app)

@flask_app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'})

@flask_app.route('/track_behavior', methods=['POST'])
def track_behavior():
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        events = data.get("events", [])

        if not user_id or not events:
            return jsonify({"error": "user_id and events are required"}), 400

        behavior_summary = peau_agent_instance.analyze_user_behavior(user_id, events)
        suggestion_data = peau_agent_instance.generate_proactive_suggestion(user_id, behavior_summary)

        return jsonify({
            "status": "success",
            "message": "Behavior tracked and suggestion generated",
            "suggestion_data": suggestion_data
        })
    except Exception as e:
        logger.error(f"Error in /track_behavior: {e}")
        return jsonify({"error": str(e)}), 500


# --- MCP Server Setup ---
print("Creating PEAU Agent MCP Server instance...")
mcp_app = Server("peau-agent-mcp-server")

# The function that will be exposed as an ADK FunctionTool via MCP
async def get_proactive_suggestion_mcp_tool_func(user_id: str, behavior_events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """MCP tool function to get proactive suggestions."""
    logger.info(f"MCP Tool Func: Received request for proactive suggestion for user {user_id}")
    behavior_summary = peau_agent_instance.analyze_user_behavior(user_id, behavior_events)
    suggestion = peau_agent_instance.generate_proactive_suggestion(user_id, behavior_summary)
    return suggestion

# Prepare the ADK Tool to be exposed
print("Initializing ADK FunctionTool for get_proactive_suggestion...")
adk_tool_to_expose = FunctionTool(get_proactive_suggestion_mcp_tool_func)
print(f"ADK tool initialized and ready to be exposed via MCP.")

# Implement the MCP server's handler to list available tools
@mcp_app.list_tools()
async def list_mcp_tools() -> list[mcp_types.Tool]:
    """MCP handler to list tools this server exposes."""
    logger.info("PEAU Agent MCP Server: Received list_tools request.")
    mcp_tool_schema = adk_to_mcp_tool_type(adk_tool_to_expose)
    logger.info(f"PEAU Agent MCP Server: Advertising tool: {mcp_tool_schema.name}")
    return [mcp_tool_schema]

# Implement the MCP server's handler to execute a tool call
@mcp_app.call_tool()
async def call_mcp_tool(name: str, arguments: dict) -> list[mcp_types.Content]:
    """MCP handler to execute a tool call requested by an MCP client."""
    logger.info(f"PEAU Agent MCP Server: Received call_tool request for '{name}' with args: {arguments}")

    if name == adk_tool_to_expose.name:
        try:
            adk_tool_response = await adk_tool_to_expose.run_async(
                args=arguments,
                tool_context=None,
            )
            logger.info(f"PEAU Agent MCP Server: ADK tool '{name}' executed. Response: {adk_tool_response}")
            response_text = json.dumps(adk_tool_response, indent=2)
            return [mcp_types.TextContent(type="text", text=response_text)]
        except Exception as e:
            logger.error(f"PEAU Agent MCP Server: Error executing ADK tool '{name}': {e}")
            error_text = json.dumps({"error": f"Failed to execute tool '{name}': {str(e)}"})
            return [mcp_types.TextContent(type="text", text=error_text)]
    else:
        logger.warning(f"PEAU Agent MCP Server: Tool '{name}' not found/exposed by this server.")
        error_text = json.dumps({"error": f"Tool '{name}' not implemented by this server."})
        return [mcp_types.TextContent(type="text", text=error_text)]


# --- Server Runner ---
async def run_mcp_tcp_server():
    """Runs the MCP server, listening for TCP connections."""
    mcp_port = int(os.getenv('MCP_PORT', 8081)) # MCP server will run on 8081
    host = '0.0.0.0'

    logger.info(f"PEAU Agent MCP TCP Server: Starting on {host}:{mcp_port}")

    async def client_connected_handler(reader, writer):
        peername = writer.get_extra_info('peername')
        logger.info(f"PEAU Agent MCP TCP Server: Client {peername} connected.")
        try:
            await mcp_app.run(reader, writer, InitializationOptions(
                server_name=mcp_app.name,
                server_version="0.1.0",
                capabilities=mcp_app.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ))
        except Exception as e:
            logger.error(f"PEAU Agent MCP TCP Server: Error handling client {peername}: {e}")
        finally:
            logger.info(f"PEAU Agent MCP TCP Server: Client {peername} disconnected.")
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(client_connected_handler, host, mcp_port)
    async with server:
        await server.serve_forever()

def run_flask_app():
    """Runs the Flask health check and behavior tracking app."""
    http_port = int(os.getenv('HTTP_PORT', 8080)) # Flask app will run on 8080
    logger.info(f"Starting PEAU Agent Flask server on port {http_port}")
    flask_app.run(host='0.0.0.0', port=http_port, debug=False)

if __name__ == "__main__":
    # Run Flask app in a separate thread
    flask_thread = threading.Thread(target=run_flask_app, daemon=True)
    flask_thread.start()

    # Run MCP TCP server in the main event loop
    logger.info("Launching PEAU Agent MCP TCP Server to expose proactive suggestion tool.")
    try:
        asyncio.run(run_mcp_tcp_server())
    except KeyboardInterrupt:
        logger.info("PEAU Agent MCP TCP Server stopped by user.")
    except Exception as e:
        logger.error(f"PEAU Agent MCP TCP Server encountered an error: {e}")
    finally:
        logger.info("PEAU Agent MCP TCP Server process exiting.")
