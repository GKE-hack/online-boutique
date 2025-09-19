import os
import logging
import re
import json
import time
import asyncio
from typing import List, Dict, Any
import requests # Re-added for MCP client communication

import vertexai
from vertexai.generative_models import GenerativeModel

from google.adk.agents.llm_agent import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
# Removed ADK AgentTool import
# from google.adk.agent_tool import AgentTool

# Removed ADK <-> MCP Client Imports (no longer using MCPToolset directly for client)
# from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
# from google.adk.tools.mcp_tool.mcp_session_manager import TcpConnectionParams # Using TCP for network

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "severity": "%(levelname)s", "message": "%(message)s"}',
    datefmt='%Y-%m-%dT%H:%M:%S.%fZ'
)
logger = logging.getLogger(__name__)


# Re-introducing GenericMCPClient for requests-based communication
class GenericMCPClient:
    """Client for communicating with the generic MCP service to use its exposed tools via HTTP."""
    def __init__(self, mcp_service_addr: str):
        self.mcp_service_addr = mcp_service_addr
        logger.info(f"Initialized GenericMCPClient for {self.mcp_service_addr}")

    def call_tool(self, tool_name: str, **kwargs) -> Any:
        """Calls a specific tool exposed by the generic MCP service via HTTP POST."""
        try:
            response = requests.post(
                f"http://{self.mcp_service_addr}/tools/{tool_name}",
                json=kwargs
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Generic MCP service not reachable at {self.mcp_service_addr}: {e}")
            return {"error": "Generic MCP service unavailable."}
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling generic MCP tool '{tool_name}': {e}")
            return {"error": f"Error from generic MCP service: {e}"}
        except Exception as e:
            logger.error(f"Unexpected error in GenericMCPClient.call_tool: {e}")
            return {"error": f"Unexpected error: {e}"}


# Global MCP client instance for the product search tool
_global_mcp_client = None

def product_search_tool(query: str = "", category: str = "", product_id: str = "", max_results: int = 5) -> dict:
    """Search for products in the Online Boutique catalog using the generic MCP service.
    
    Args:
        query (str): A general search term for products.
        category (str): A specific product category to narrow the search.
        product_id (str): A direct product ID lookup.
        max_results (int): The maximum number of products to return.
        
    Returns:
        dict: status and result or error message.
    """
    if _global_mcp_client is None:
        return {
            "status": "error",
            "error_message": "Product search service not available."
        }
    
    logger.info(f"Calling generic MCP service for product search: query='{query}', category='{category}', product_id='{product_id}'")
    try:
        # Convert empty strings to None for the MCP client
        query_param = query if query else None
        category_param = category if category else None
        product_id_param = product_id if product_id else None
        
        results = _global_mcp_client.call_tool(
            "product_search_tool",
            query=query_param,
            category=category_param,
            product_id=product_id_param,
            max_results=max_results
        )
        if results and isinstance(results, list):
            return {
                "status": "success",
                "products": results
            }
        else:
            return {
                "status": "error", 
                "error_message": "No products found or invalid response from search service."
            }
    except Exception as e:
        logger.error(f"Error calling product search tool: {e}")
        return {
            "status": "error",
            "error_message": f"Product search failed: {str(e)}"
        }


class PEAUAgent:
    """Proactive Engagement & Upselling Agent (PEAU Agent)"""

    def __init__(self, project_id: str, location: str = "us-central1"):
        global _global_mcp_client
        
        self.project_id = project_id
        self.location = location
        self.app_name = "peau_agent"
        self.user_id = "system"
        self.session_id = "main_session"

        try:
            vertexai.init(project=project_id, location=location)
            logger.info("PEAU Agent Vertex AI initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize Vertex AI for PEAU Agent: {e}")
            raise

        # Initialize generic MCP client for tools (requests-based)
        generic_mcp_addr = os.getenv('GENERIC_MCP_SERVICE_ADDR', 'localhost:8080')
        logger.info(f"Connecting to generic MCP service for HTTP at: {generic_mcp_addr}")
        self.generic_mcp_client = GenericMCPClient(generic_mcp_addr)
        _global_mcp_client = self.generic_mcp_client  # Set global for tool function

        # Initialize the ADK LlmAgent with product search tool
        # Vertex AI configuration is handled by vertexai.init() above
        self.adk_agent = LlmAgent(
            model="gemini-2.0-flash",
            name="peau_agent",
            instruction="You are a proactive shopping assistant for Online Boutique. Your goal is to help users find products and make personalized recommendations based on their behavior. Use the product_search_tool to find product information when needed.",
            tools=[product_search_tool]
        )

        logger.info("ADK LlmAgent initialized with product search tool via Generic MCP Service.")

    def _get_product_details(self, product_id: str) -> Dict[str, Any]:
        """Fetches product details using the product_search_tool."""
        # Use the global product search tool
        result = product_search_tool(product_id=product_id or "", max_results=1)
        if result.get("status") == "success" and result.get("products"):
            return result["products"][0]
        return None

    def analyze_user_behavior(self, user_id: str, events: List[Dict[str, Any]]) -> str:
        """Analyzes user behavior events and generates a summary for Gemini."""
        behavior_summary = f"User {user_id} has performed the following actions:\n"
        for event in events:
            event_type = event.get("type", "unknown")
            product_id = event.get("product_id")
            timestamp = event.get("timestamp")

            if event_type == "product_viewed" and product_id:
                product = self._get_product_details(product_id)
                if product:
                    categories = ", ".join(product.get("categories", []))
                    behavior_summary += f"- Viewed product: {product['name']} (ID: {product_id}, Categories: {categories}) at {timestamp}\n"
                else:
                    behavior_summary += f"- Viewed unknown product ID: {product_id} at {timestamp}\n"
            elif event_type == "item_added_to_cart" and product_id:
                product = self._get_product_details(product_id)
                if product:
                    categories = ", ".join(product.get("categories", []))
                    behavior_summary += f"- Added to cart: {product['name']} (ID: {product_id}, Categories: {categories}) at {timestamp}\n"
                else:
                    behavior_summary += f"- Added unknown product ID to cart: {product_id} at {timestamp}\n"
            else:
                behavior_summary += f"- {event_type} event detected at {timestamp}\n"
        logger.info(f"Generated behavior summary for user {user_id}")
        return behavior_summary

    def generate_proactive_suggestion(self, user_id: str, behavior_summary: str) -> Dict[str, Any]:
        """Generates proactive suggestions based on user behavior using ADK LlmAgent."""
        logger.info(f"Generating proactive suggestion for user {user_id}...")
        
        # Run the async method in a new event loop
        try:
            result = asyncio.run(self._generate_suggestion_async(user_id, behavior_summary))
            return result
        except Exception as e:
            logger.error(f"Error in generate_proactive_suggestion: {e}")
            return {
                "suggestion": "I'm sorry, I'm having trouble generating suggestions right now.",
                "recommended_product_ids": []
            }

    async def _generate_suggestion_async(self, user_id: str, behavior_summary: str) -> Dict[str, Any]:
        """Async method to generate suggestions using ADK pattern."""
        prompt = f"""Based on this user behavior, provide a helpful and personalized shopping suggestion:

{behavior_summary}

Please analyze the behavior and:
1. If they viewed products but didn't add to cart, suggest similar or complementary items from the SAME CATEGORIES
2. If they added items to cart, suggest related products for cross-selling from RELATED CATEGORIES
3. IMPORTANT: Use the product_search_tool with the 'category' parameter to find products from the same categories as what the user interacted with
4. If the user viewed/added items from specific categories (e.g., "home & garden", "clothing"), search for other products in those exact categories

STRATEGY: 
- Extract the categories from the user's behavior above
- Use product_search_tool(category="category_name") to find similar products
- Recommend products that match the user's demonstrated interests

Be conversational and helpful. Include product IDs in square brackets [PRODUCT_ID] when recommending specific items."""

        try:
            # Use the correct async pattern from ADK example
            session_service = InMemorySessionService()
            session_id = f"session_{user_id}_{int(time.time())}"
            
            # Create session using await
            await session_service.create_session(
                app_name=self.app_name,
                user_id=user_id,
                session_id=session_id
            )
            
            # Create runner
            runner = Runner(
                agent=self.adk_agent,
                app_name=self.app_name,
                session_service=session_service
            )
            
            # Use run_async with await
            user_content = types.Content(role='user', parts=[types.Part(text=prompt)])
            
            suggestion_text = ""
            async for event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=user_content
            ):
                logger.info(f"ADK Event: {type(event).__name__}")
                if event.is_final_response() and event.content and event.content.parts:
                    suggestion_text = event.content.parts[0].text.strip()
                    break
            
            if not suggestion_text:
                suggestion_text = "I'm sorry, I couldn't generate a suggestion right now."
            
            recommended_product_ids = self._extract_product_ids(suggestion_text)
            
            logger.info(f"Generated proactive suggestion for user {user_id}: {suggestion_text}")
            return {
                "suggestion": suggestion_text,
                "recommended_product_ids": recommended_product_ids
            }
            
        except Exception as e:
            logger.error(f"Error in _generate_suggestion_async for user {user_id}: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return {
                "suggestion": "I'm sorry, I'm having trouble generating suggestions right now.",
                "recommended_product_ids": []
            }

    def _extract_product_ids(self, text: str) -> List[str]:
        """Extracts product IDs from the generated text."""
        product_id_pattern = r'\[([A-Z0-9]+)\]'
        return re.findall(product_id_pattern, text)

if __name__ == "__main__":
    # Example Usage (for local testing)
    import asyncio

    async def main():
        project_id = os.getenv("PROJECT_ID", "your-gcp-project-id")
        agent = PEAUAgent(project_id)

        # Mock user events
        user_events = [
            {"type": "product_viewed", "product_id": "OLJCESPC7Z", "timestamp": "2023-10-27T10:00:00Z"},
            {"type": "product_viewed", "product_id": "LS4PSXUNUM", "timestamp": "2023-10-27T10:05:00Z"},
            {"type": "item_added_to_cart", "product_id": "OLJCESPC7Z", "timestamp": "2023-10-27T10:10:00Z"},
        ]

        summary = agent.analyze_user_behavior("user123", user_events)
        suggestion = await agent.generate_proactive_suggestion("user123", summary)
        print(f"Proactive Suggestion: {suggestion['suggestion']}")
        print(f"Recommended Product IDs: {suggestion['recommended_product_ids']}")

        user_events_2 = [
            {"type": "product_viewed", "product_id": "9SIQT8TOJO", "timestamp": "2023-10-27T11:00:00Z"},
            {"type": "product_viewed", "product_id": "ABC123XYZ", "timestamp": "2023-10-27T11:05:00Z"},
        ]
        summary_2 = agent.analyze_user_behavior("user456", user_events_2)
        suggestion_2 = await agent.generate_proactive_suggestion("user456", summary_2)
        print(f"Proactive Suggestion (User 456): {suggestion_2['suggestion']}")
        print(f"Recommended Product IDs (User 456): {suggestion_2['recommended_product_ids']}")

        user_events_3 = [
            {"type": "product_viewed", "product_id": "INVALID_ID", "timestamp": "2023-10-27T12:00:00Z"},
            {"type": "user_browsing", "timestamp": "2023-10-27T12:05:00Z"},
        ]
        summary_3 = agent.analyze_user_behavior("user789", user_events_3)
        suggestion_3 = await agent.generate_proactive_suggestion("user789", summary_3)
        print(f"Proactive Suggestion (User 789): {suggestion_3['suggestion']}")
        print(f"Recommended Product IDs (User 789): {suggestion_3['recommended_product_ids']}")

    asyncio.run(main())
