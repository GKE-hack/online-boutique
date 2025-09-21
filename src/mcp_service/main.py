import os
import logging
import asyncio
import json
from typing import List, Dict, Any
import grpc
from flask import Flask, jsonify, request
import threading # For running Flask and MCP server concurrently

# MCP Server Imports
import mcp.types as mcp_types
from mcp.server.lowlevel import Server, NotificationOptions
from mcp.server.models import InitializationOptions
# ADK Tool Imports for MCP exposure
from google.adk.tools.function_tool import FunctionTool
from google.adk.tools.mcp_tool.conversion_utils import adk_to_mcp_tool_type

# Import generated protobuf classes
import demo_pb2
import demo_pb2_grpc

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "severity": "%(levelname)s", "message": "%(message)s"}',
    datefmt='%Y-%m-%dT%H:%M:%S.%fZ'
)
logger = logging.getLogger(__name__)


class ProductCatalogClient:
    """Client for communicating with the Product Catalog Service via gRPC"""
    
    def __init__(self, catalog_service_addr: str):
        self.catalog_service_addr = catalog_service_addr
        self.channel = None
        self.stub = None
        self._connect()
    
    def _connect(self):
        """Establish gRPC connection to product catalog service"""
        try:
            self.channel = grpc.insecure_channel(self.catalog_service_addr)
            self.stub = demo_pb2_grpc.ProductCatalogServiceStub(self.channel)
            logger.info(f"Connected to product catalog service at {self.catalog_service_addr}")
        except Exception as e:
            logger.error(f"Failed to connect to product catalog service: {e}")
            raise
    
    def list_products(self) -> List[Dict[str, Any]]:
        """Get all products from the catalog"""
        try:
            request = demo_pb2.Empty()
            response = self.stub.ListProducts(request)
            products = []
            for product in response.products:
                products.append({
                    'id': product.id,
                    'name': product.name,
                    'description': product.description,
                    'picture': product.picture,
                    'price_usd': {
                        'currency_code': product.price_usd.currency_code,
                        'units': product.price_usd.units,
                        'nanos': product.price_usd.nanos
                    },
                    'categories': list(product.categories)
                })
            logger.info(f"Retrieved {len(products)} products from catalog")
            return products
        except Exception as e:
            logger.error(f"Error listing products: {e}")
            return []
    
    def get_product(self, product_id: str) -> Dict[str, Any]:
        """Get a specific product by ID"""
        try:
            request = demo_pb2.GetProductRequest(id=product_id)
            product = self.stub.GetProduct(request)
            return {
                'id': product.id,
                'name': product.name,
                'description': product.description,
                'picture': product.picture,
                'price_usd': {
                    'currency_code': product.price_usd.currency_code,
                    'units': product.price_usd.units,
                    'nanos': product.price_usd.nanos
                },
                'categories': list(product.categories)
            }
        except Exception as e:
            logger.error(f"Error getting product {product_id}: {e}")
            return None
    
    def search_products(self, query: str) -> List[Dict[str, Any]]:
        """Search for products based on query"""
        try:
            request = demo_pb2.SearchProductsRequest(query=query)
            response = self.stub.SearchProducts(request)
            products = []
            for product in response.results:
                products.append({
                    'id': product.id,
                    'name': product.name,
                    'description': product.description,
                    'picture': product.picture,
                    'price_usd': {
                        'currency_code': product.price_usd.currency_code,
                        'units': product.price_usd.units,
                        'nanos': product.price_usd.nanos
                    },
                    'categories': list(product.categories)
                })
            logger.info(f"Found {len(products)} products for query '{query}'")
            return products
        except Exception as e:
            logger.error(f"Error searching products with query '{query}': {e}")
            return []

# Initialize ProductCatalogClient globally for the MCP service
catalog_service_addr = os.getenv('PRODUCT_CATALOG_SERVICE_ADDR', 'productcatalogservice:3550')
product_catalog_client = ProductCatalogClient(catalog_service_addr)

def format_product_details(product: Dict[str, Any]) -> Dict[str, Any]:
    """Formats product details for consistent output."""
    # This is a simplified formatting; adjust as needed for agent consumption
    return {
        "id": product.get("id"),
        "name": product.get("name"),
        "description": product.get("description"),
        "price": f"${product['price_usd']['units'] + product['price_usd']['nanos'] / 1_000_000_000:.2f}",
        "categories": product.get("categories"),
    }

# The function that will be exposed as an ADK FunctionTool via MCP
async def product_search_tool_func(query: str = None, category: str = None, product_id: str = None, max_results: int = 5) -> List[Dict[str, Any]]:
    """Search for products in the Online Boutique catalog using the real ProductCatalogClient."""
    products = []
    if product_id:
        product = product_catalog_client.get_product(product_id)
        if product: products.append(product)
    elif query:
        products = product_catalog_client.search_products(query)
    elif category:
        all_products = product_catalog_client.list_products()
        products = [p for p in all_products if category.lower() in [c.lower() for c in p.get("categories", [])]]
    
    return [format_product_details(p) for p in products[:max_results]]


# --- MCP Server Setup ---
print("Creating MCP Server instance...")
# Create a named MCP Server instance using the mcp.server library
mcp_app = Server("generic-mcp-server")

# Prepare the ADK Tool to be exposed
print("Initializing ADK FunctionTool for product_search_tool_func...")
adk_tool_to_expose = FunctionTool(product_search_tool_func)
print(f"ADK tool initialized and ready to be exposed via MCP.")

# Implement the MCP server's handler to list available tools
@mcp_app.list_tools()
async def list_mcp_tools() -> list[mcp_types.Tool]:
    """Lists tools exposed by this MCP server."""
    logger.info("MCP Server: Received list_tools request.")
    # Convert the ADK tool's definition to the MCP Tool schema format
    mcp_tool_schema = adk_to_mcp_tool_type(adk_tool_to_expose)
    logger.info(f"MCP Server: Advertising tool: {mcp_tool_schema.name}")
    return [mcp_tool_schema]

# Implement the MCP server's handler to execute a tool call
@mcp_app.call_tool()
async def call_mcp_tool(name: str, arguments: dict) -> list[mcp_types.Content]:
    """Executes a tool call requested by an MCP client."""
    logger.info(f"MCP Server: Received call_tool request for '{name}' with args: {arguments}")

    if name == adk_tool_to_expose.name:
        try:
            adk_tool_response = await adk_tool_to_expose.run_async(
                args=arguments,
                tool_context=None,
            )
            logger.info(f"MCP Server: ADK tool '{name}' executed. Response: {adk_tool_response}")

            response_text = json.dumps(adk_tool_response, indent=2)
            return [mcp_types.TextContent(type="text", text=response_text)]

        except Exception as e:
            logger.error(f"MCP Server: Error executing ADK tool '{name}': {e}")
            error_text = json.dumps({"error": f"Failed to execute tool '{name}': {str(e)}"})
            return [mcp_types.TextContent(type="text", text=error_text)]
    else:
        logger.warning(f"MCP Server: Tool '{name}' not found/exposed by this server.")
        error_text = json.dumps({"error": f"Tool '{name}' not implemented by this server."})
        return [mcp_types.TextContent(type="text", text=error_text)]


# --- Flask App for Health Check ---
# Initialize Flask app for health check on HTTP_PORT (8080)
flask_app = Flask(__name__)

@flask_app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'})

@flask_app.route('/tools/product_search_tool', methods=['POST'])
def product_search_tool_http_endpoint():
    """HTTP endpoint for product search tool (for requests-based clients)."""
    try:
        data = request.get_json()
        query = data.get("query")
        category = data.get("category")
        product_id = data.get("product_id")
        max_results = data.get("max_results", 5)

        logger.info(f"HTTP: Received request for product search: query='{query}', category='{category}', product_id='{product_id}'")
        
        products = []
        if product_id:
            product = product_catalog_client.get_product(product_id)
            if product: products.append(product)
        elif query:
            products = product_catalog_client.search_products(query)
        elif category:
            all_products = product_catalog_client.list_products()
            products = [p for p in all_products if category.lower() in [c.lower() for c in p.get("categories", [])]]
        
        result = [format_product_details(p) for p in products[:max_results]]
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in /tools/product_search_tool HTTP endpoint: {e}")
        return jsonify({"error": str(e)}), 500


# --- Server Runner ---
async def run_mcp_tcp_server():
    """Runs the MCP server, listening for TCP connections."""
    mcp_port = int(os.getenv('MCP_PORT', 8081)) # MCP server will run on 8081
    host = '0.0.0.0'

    logger.info(f"MCP TCP Server: Starting on {host}:{mcp_port}")

    # The low-level MCP server needs a transport implementation.
    # For TCP, we'll implement a simple handler for asyncio.start_server.
    async def client_connected_handler(reader, writer):
        peername = writer.get_extra_info('peername')
        logger.info(f"MCP TCP Server: Client {peername} connected.")
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
            logger.error(f"MCP TCP Server: Error handling client {peername}: {e}")
        finally:
            logger.info(f"MCP TCP Server: Client {peername} disconnected.")
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(client_connected_handler, host, mcp_port)
    async with server:
        await server.serve_forever()

def run_flask_app():
    """Runs the Flask health check app."""
    http_port = int(os.getenv('HTTP_PORT', 8080)) # Flask app will run on 8080
    logger.info(f"Starting Generic MCP Flask health check server on port {http_port}")
    flask_app.run(host='0.0.0.0', port=http_port, debug=False)

if __name__ == "__main__":
    # Run Flask app in a separate thread
    flask_thread = threading.Thread(target=run_flask_app, daemon=True)
    flask_thread.start()

    # Run MCP TCP server in the main event loop
    logger.info("Launching MCP TCP Server to expose Product Catalog tool.")
    try:
        asyncio.run(run_mcp_tcp_server())
    except KeyboardInterrupt:
        logger.info("MCP TCP Server stopped by user.")
    except Exception as e:
        logger.error(f"MCP TCP Server encountered an error: {e}")
    finally:
        logger.info("MCP TCP Server process exiting.")
