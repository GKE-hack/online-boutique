#!/usr/bin/env python
# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import logging
import json
import traceback
import sys
from concurrent import futures
from typing import List, Dict, Any
import grpc
from grpc_health.v1 import health_pb2_grpc, health_pb2
import vertexai
from vertexai.generative_models import GenerativeModel
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.serving import run_simple
import threading

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

class ChatbotService:
    """Main chatbot service using Gemini 2.0 Flash"""
    
    def __init__(self, project_id: str, location: str):
        self.project_id = project_id
        self.location = location
        
        try:
            logger.info(f"Initializing Vertex AI with project_id='{project_id}', location='{location}'")
            
            # Check environment variables for debugging
            logger.info(f"Environment variables:")
            logger.info(f"  GOOGLE_APPLICATION_CREDENTIALS: {os.getenv('GOOGLE_APPLICATION_CREDENTIALS', 'Not set')}")
            logger.info(f"  GOOGLE_CLOUD_PROJECT: {os.getenv('GOOGLE_CLOUD_PROJECT', 'Not set')}")
            
            # Initialize Vertex AI
            vertexai.init(project=project_id, location=location)
            logger.info("Vertex AI initialized successfully")
            
            # Initialize Gemini 2.0 Flash model
            logger.info("Initializing Gemini 2.0 Flash model...")
            self.model = GenerativeModel("gemini-2.0-flash")
            logger.info("Gemini model initialized successfully")
            
            # Initialize product catalog client
            catalog_addr = os.getenv('PRODUCT_CATALOG_SERVICE_ADDR', 'productcatalogservice:3550')
            logger.info(f"Connecting to product catalog at: {catalog_addr}")
            self.catalog_client = ProductCatalogClient(catalog_addr)
            
            # Initialize RAG manager (optional - graceful fallback)
            try:
                from rag_manager import VertexRAGManager
                self.rag_manager = VertexRAGManager(project_id, 'us-east4')
                logger.info("RAG manager initialized successfully")
                self.rag_enabled = True
            except Exception as e:
                logger.warning(f"RAG manager initialization failed, using fallback: {e}")
                self.rag_manager = None
                self.rag_enabled = False
            
            logger.info("Chatbot service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize ChatbotService: {str(e)}")
            logger.error(f"Full traceback:\n{traceback.format_exc()}")
            raise
    
    def format_price(self, price_usd: Dict[str, Any]) -> str:
        """Format price from protobuf format to readable string"""
        units = price_usd.get('units', 0)
        nanos = price_usd.get('nanos', 0)
        total = units + (nanos / 1_000_000_000)
        return f"${total:.2f}"
    
    def generate_product_context(self, products: List[Dict[str, Any]]) -> str:
        """Generate context about products for the AI model"""
        if not products:
            return "No products found."
        
        context = "Available products:\n"
        for product in products:
            price = self.format_price(product['price_usd'])
            categories = ', '.join(product['categories'])
            context += f"- {product['name']} ({product['id']}): {product['description']} | Price: {price} | Categories: {categories}\n"
        
        return context
    
    def generate_response(self, user_message: str, conversation_history: List[str] = None) -> Dict[str, Any]:
        """Generate chatbot response using RAG-enhanced Gemini or fallback"""
        try:
            # Try RAG-enhanced response first
            if self.rag_enabled and self.rag_manager:
                try:
                    logger.info(f"Generating RAG-enhanced response for: '{user_message[:100]}...'")
                    
                    # Create enhanced prompt with conversation history
                    enhanced_message = user_message
                    if conversation_history:
                        history_text = "\n".join(conversation_history[-5:])  # Keep last 5 messages
                        enhanced_message = f"Conversation history:\n{history_text}\n\nCurrent message: {user_message}"
                    
                    # Generate RAG-enhanced response
                    rag_response = self.rag_manager.generate_response(enhanced_message)
                    
                    # Extract product IDs from RAG response (simple extraction)
                    recommended_products = self._extract_product_ids_from_text(rag_response)
                    
                    logger.info(f"RAG-enhanced response: {rag_response}")
                    
                    return {
                        'response': rag_response,
                        'recommended_products': recommended_products,
                        'total_products_considered': 'RAG-based',
                        'rag_enhanced': True
                    }
                    
                except Exception as e:
                    logger.warning(f"RAG generation failed, falling back to catalog-based: {e}")
                    # Fall through to catalog-based approach
            
            # Fallback: Catalog-based response (original approach)
            logger.info(f"Generating catalog-based response for: '{user_message[:100]}...'")
            
            # Determine if we need to search for specific products
            search_keywords = self._extract_search_keywords(user_message)
            
            if search_keywords:
                # Search for products based on keywords
                products = []
                for keyword in search_keywords:
                    results = self.catalog_client.search_products(keyword)
                    products.extend(results)
                
                # Remove duplicates
                unique_products = {p['id']: p for p in products}.values()
                products = list(unique_products)
            else:
                # If no specific search, get all products for general queries
                products = self.catalog_client.list_products()
            
            # Generate context about products
            product_context = self.generate_product_context(products)
            
            # Create the conversation history
            history_text = ""
            if conversation_history:
                history_text = "\n".join(conversation_history[-10:])  # Keep last 10 messages
            
            # Create the prompt for Gemini
            prompt = f"""You are a helpful shopping assistant for Online Boutique, an e-commerce store. 
Your role is to help customers find products, answer questions about products, and provide shopping recommendations.

{product_context}

Conversation history:
{history_text}

Customer message: {user_message}

Please provide a helpful, friendly response. If the customer is asking about specific products, include relevant product details like name, price, and description. If they're looking for recommendations, suggest appropriate products from the catalog. Keep your responses concise but informative.

If you recommend specific products, include their product IDs in square brackets like [PRODUCT_ID] at the end of your response."""

            # Generate response using Gemini 2.0 Flash
            response = self.model.generate_content(prompt)
            logger.info("Catalog-based response generated successfully")
            
            # Extract recommended product IDs from response
            recommended_products = self._extract_product_ids(response.text, products)
            
            return {
                'response': response.text,
                'recommended_products': recommended_products,
                'total_products_considered': len(products),
                'rag_enhanced': False
            }
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Full traceback:\n{traceback.format_exc()}")
            
            # Include more details in the error response for debugging
            error_details = {
                'error_type': type(e).__name__,
                'error_message': str(e),
                'project_id': self.project_id,
                'location': self.location
            }
            logger.error(f"Error details: {json.dumps(error_details, indent=2)}")
            
            return {
                'response': f"I'm sorry, I'm having trouble processing your request. Error: {str(e)}",
                'recommended_products': [],
                'total_products_considered': 0,
                'error_details': error_details  # Include for debugging
            }
    
    def _extract_search_keywords(self, message: str) -> List[str]:
        """Extract potential search keywords from user message"""
        # Simple keyword extraction - look for product-related terms
        keywords = []
        message_lower = message.lower()
        
        # Common product categories and terms
        product_terms = [
            'sunglasses', 'tank top', 'watch', 'loafers', 'hairdryer', 
            'candle holder', 'salt', 'pepper', 'bamboo', 'glass jar', 'mug',
            'clothing', 'accessories', 'footwear', 'hair', 'beauty', 
            'decor', 'home', 'kitchen'
        ]
        
        for term in product_terms:
            if term in message_lower:
                keywords.append(term)
        
        # If no specific terms found, use the entire message as search query
        if not keywords:
            keywords.append(message.strip())
        
        return keywords
    
    def _extract_product_ids(self, response_text: str, products: List[Dict[str, Any]]) -> List[str]:
        """Extract product IDs mentioned in the response"""
        product_ids = []
        for product in products:
            if f"[{product['id']}]" in response_text:
                product_ids.append(product['id'])
        return product_ids
    
    def _extract_product_ids_from_text(self, response_text: str) -> List[str]:
        """Extract product IDs from RAG response text using pattern matching"""
        import re
        # Look for patterns like [PRODUCT_ID] or mentions of known product IDs
        product_id_pattern = r'\[([A-Z0-9]+)\]'
        matches = re.findall(product_id_pattern, response_text)
        
        # Also look for mentions of known product IDs (common ones from catalog)
        known_ids = ['OLJCESPC7Z', '66VCHSJNUP', '1YMWWN1N4O', 'L9ECAV7KIM', '2ZYFJ3GM2N', 
                     '0PUK6V6EV0', 'LS4PSXUNUM', '9SIQT8TOJO', '6E92ZMYYFZ']
        
        for product_id in known_ids:
            if product_id in response_text and product_id not in matches:
                matches.append(product_id)
        
        return matches

class HealthServicer(health_pb2_grpc.HealthServicer):
    """Health check service for gRPC"""
    
    def Check(self, request, context):
        return health_pb2.HealthCheckResponse(
            status=health_pb2.HealthCheckResponse.SERVING
        )
    
    def Watch(self, request, context):
        return health_pb2.HealthCheckResponse(
            status=health_pb2.HealthCheckResponse.SERVING
        )

def create_flask_app(chatbot_service: ChatbotService) -> Flask:
    """Create Flask app for HTTP API"""
    app = Flask(__name__)
    CORS(app)  # Enable CORS for all routes
    
    @app.route('/health', methods=['GET'])
    def health_check():
        return jsonify({'status': 'healthy'})
    
    @app.route('/chat', methods=['POST'])
    @app.route('/bot', methods=['POST'])  # Add back for frontend compatibility
    def chat():
        try:
            logger.info(f"Received chat request from {request.remote_addr}")
            
            data = request.get_json()
            
            if not data or 'message' not in data:
                logger.warning("Invalid request: missing message field")
                return jsonify({'error': 'Message is required'}), 400
            
            user_message = data['message']
            conversation_history = data.get('history', [])
            
            logger.info(f"Processing message: '{user_message[:100]}...'")
            
            response = chatbot_service.generate_response(user_message, conversation_history)
            
            logger.info("Chat response generated successfully")
            
            # Prepare response data with safe serialization
            total_products = response.get('total_products_considered', 0)
            # Convert to int if it's a string like "RAG-based", otherwise use the number
            if isinstance(total_products, str):
                total_products_int = 1 if total_products else 0  # Use 1 for RAG-based responses
            else:
                total_products_int = int(total_products) if total_products else 0
                
            response_data = {
                'success': True,
                'response': str(response.get('response', '')),
                'recommended_products': response.get('recommended_products', []),
                'total_products_considered': total_products_int,
                'rag_enhanced': response.get('rag_enhanced', False)
            }
            
            # Add error details if present (for debugging)
            if response.get('error_details'):
                response_data['error_details'] = str(response.get('error_details'))
            
            logger.info(f"Returning response with {len(response_data.get('recommended_products', []))} recommended products")
            
            try:
                response_obj = jsonify(response_data)
                logger.info(f"Successfully created JSON response, status: 200")
                return response_obj
            except Exception as json_error:
                logger.error(f"JSON serialization error: {json_error}")
                logger.error(f"Response data that failed: {response_data}")
                # Return a safe fallback response
                return jsonify({
                    'success': True,
                    'response': str(response.get('response', 'Response generated but serialization failed')),
                    'recommended_products': [],
                    'total_products_considered': 0,
                    'rag_enhanced': False,
                    'serialization_error': str(json_error)
                })
            
        except Exception as e:
            logger.error(f"Error in chat endpoint: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Full traceback:\n{traceback.format_exc()}")
            
            return jsonify({
                'success': False,
                'error': f'Internal server error: {str(e)}',
                'error_type': type(e).__name__
            }), 500
    
    return app

def serve_grpc(port: int = 8080):
    """Serve gRPC health checks"""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    health_pb2_grpc.add_HealthServicer_to_server(HealthServicer(), server)
    
    listen_addr = f'[::]:{port}'
    server.add_insecure_port(listen_addr)
    server.start()
    logger.info(f"gRPC server started on {listen_addr}")
    
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        server.stop(0)

def main():
    """Main function to start the chatbot service"""
    # Get configuration from environment variables
    project_id = os.getenv('PROJECT_ID', 'your-project-id')
    location = os.getenv('LOCATION', 'us-central1')
    http_port = int(os.getenv('HTTP_PORT', '8080'))
    grpc_port = int(os.getenv('GRPC_PORT', '8081'))
    
    # Initialize chatbot service
    chatbot_service = ChatbotService(project_id, location)
    
    # Create Flask app
    app = create_flask_app(chatbot_service)
    
    # Start gRPC server in a separate thread
    grpc_thread = threading.Thread(target=serve_grpc, args=(grpc_port,))
    grpc_thread.daemon = True
    grpc_thread.start()
    
    # Start Flask server
    logger.info(f"Starting HTTP server on port {http_port}")
    run_simple('0.0.0.0', http_port, app, use_reloader=False, use_debugger=False)

if __name__ == '__main__':
    main()