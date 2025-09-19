#!/usr/bin/env python3
"""
Modern RAG Corpus Manager using Vertex AI SDK
Handles creation, ingestion, and querying using vertexai.rag
"""

import os
import json
import hashlib
import tempfile
import time
from typing import List, Dict, Any, Optional
import logging
import vertexai
from vertexai import rag
from vertexai.generative_models import GenerativeModel, Tool

logger = logging.getLogger(__name__)

class VertexRAGManager:
    """Modern RAG manager using Vertex AI SDK"""
    
    def __init__(self, project_id: str, location: str = "us-east4"):
        self.project_id = project_id
        self.location = location
        self.corpus_name = "online-boutique-products"
        self.corpus_display_name = "Online Boutique Product Catalog"
        
        # Initialize Vertex AI
        vertexai.init(project=project_id, location=location)
        
        # Store corpus reference
        self._corpus = None
        self._rag_model = None
        
        logger.info(f"VertexRAG Manager initialized for project: {project_id}")
    
    def _get_or_create_corpus(self) -> Any:
        """Get existing corpus or create new one"""
        if self._corpus is not None:
            return self._corpus
        
        try:
            # Try to find existing corpus
            corpora = rag.list_corpora()
            for corpus in corpora:
                if corpus.display_name == self.corpus_display_name:
                    logger.info(f"Found existing corpus: {corpus.name}")
                    self._corpus = corpus
                    return self._corpus
            
            # Create new corpus if not found
            logger.info("Creating new RAG corpus...")
            
            # Configure embedding model
            embedding_model_config = rag.RagEmbeddingModelConfig(
                vertex_prediction_endpoint=rag.VertexPredictionEndpoint(
                    publisher_model="publishers/google/models/text-embedding-005"
                )
            )
            
            # Create corpus with vector DB backend
            self._corpus = rag.create_corpus(
                display_name=self.corpus_display_name,
                backend_config=rag.RagVectorDbConfig(
                    rag_embedding_model_config=embedding_model_config
                ),
            )
            
            logger.info(f"Created new corpus: {self._corpus.name}")
            return self._corpus
            
        except Exception as e:
            logger.error(f"Failed to get/create corpus: {e}")
            raise
    
    
    def ingest_products_from_json(self, json_file_path: str) -> Dict[str, Any]:
        """Ingest products from JSON file into RAG corpus"""
        logger.info(f"Starting RAG ingestion from: {json_file_path}")
        
        try:
            # Load products from JSON
            with open(json_file_path, 'r', encoding='utf-8') as f:
                catalog = json.load(f)
            
            products = catalog.get('products', [])
            logger.info(f"Found {len(products)} products to ingest")
            
            if not products:
                logger.warning("No products found in JSON file")
                return {"status": "no_products", "count": 0}
            
            # Get or create corpus
            corpus = self._get_or_create_corpus()
            
            # Upload each product as individual file
            logger.info("Starting individual file uploads to RAG corpus...")
            uploaded_files = []
            
            for product in products:
                try:
                    # Calculate price in dollars
                    price_dollars = product['priceUsd']['units'] + (product['priceUsd']['nanos'] / 1_000_000_000)
                    price_str = f"${price_dollars:.2f}"
                    
                    # Create rich document content
                    content = f"""Product: {product['name']}
Product ID: {product['id']}
Description: {product['description']}
Price: {price_str}
Categories: {', '.join(product['categories'])}
Image: {product['picture']}

Detailed Information:
This {product['name']} is available in our {', '.join(product['categories'])} section. 
{product['description']}

Perfect for customers looking for:
{' • '.join(product['categories'])} items

Key features:
- High quality {product['name'].lower()}
- Competitive price at {price_str}
- Available with fast shipping
- Part of our {', '.join(product['categories'])} collection

Product specifications:
- Product ID: {product['id']}
- Price: {price_str} ({product['priceUsd']['currencyCode']})
- Categories: {', '.join(product['categories'])}
- Image available at: {product['picture']}

This product is ideal for customers seeking {product['name'].lower()} in the {', '.join(product['categories'])} category.
"""
                    
                    # Create temporary file for this product
                    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8')
                    temp_file.write(content)
                    temp_file.close()
                    
                    # Upload individual file to RAG corpus
                    logger.info(f"Uploading product {product['id']}: {product['name']}")
                    
                    rag_file = rag.upload_file(
                        corpus_name=corpus.name,
                        path=temp_file.name,
                        display_name=f"{product['name']} ({product['id']})",
                        description=f"Product information for {product['name']} - {product['description'][:100]}{'...' if len(product['description']) > 100 else ''}"
                    )
                    
                    uploaded_files.append({
                        "product_id": product['id'],
                        "product_name": product['name'],
                        "rag_file_name": rag_file.name,
                        "display_name": rag_file.display_name
                    })
                    
                    # Clean up temp file
                    os.unlink(temp_file.name)
                    logger.debug(f"Uploaded and cleaned up: {product['id']}")
                    
                except Exception as e:
                    logger.error(f"Failed to upload product {product.get('id', 'unknown')}: {e}")
                    # Clean up temp file on error
                    try:
                        os.unlink(temp_file.name)
                    except:
                        pass
                    continue
            
            logger.info(f"File upload completed successfully: {len(uploaded_files)}/{len(products)} products uploaded")
            
            return {
                "status": "import_completed",
                "corpus_name": corpus.name,
                "document_count": len(uploaded_files),
                "uploaded_files": uploaded_files
            }
            
        except Exception as e:
            logger.error(f"Failed to ingest products: {e}")
            raise
    
    def add_products(self, products: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Add new products to the RAG corpus"""
        logger.info(f"Adding {len(products)} products to RAG corpus")
        
        try:
            # Get or create corpus
            corpus = self._get_or_create_corpus()
            
            # Upload each product as individual file
            uploaded_files = []
            
            for product in products:
                try:
                    # Calculate price in dollars
                    price_dollars = product['priceUsd']['units'] + (product['priceUsd']['nanos'] / 1_000_000_000)
                    price_str = f"${price_dollars:.2f}"
                    
                    # Create rich document content
                    content = f"""Product: {product['name']}
Product ID: {product['id']}
Description: {product['description']}
Price: {price_str}
Categories: {', '.join(product['categories'])}
Image: {product['picture']}

Detailed Information:
This {product['name']} is available in our {', '.join(product['categories'])} section. 
{product['description']}

Perfect for customers looking for:
{' • '.join(product['categories'])} items

Key features:
- High quality {product['name'].lower()}
- Competitive price at {price_str}
- Available with fast shipping
- Part of our {', '.join(product['categories'])} collection

Product specifications:
- Product ID: {product['id']}
- Price: {price_str} ({product['priceUsd']['currencyCode']})
- Categories: {', '.join(product['categories'])}
- Image available at: {product['picture']}

This product is ideal for customers seeking {product['name'].lower()} in the {', '.join(product['categories'])} category.
"""
                    
                    # Create temporary file for this product
                    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8')
                    temp_file.write(content)
                    temp_file.close()
                    
                    # Upload individual file to RAG corpus
                    logger.info(f"Uploading product {product['id']}: {product['name']}")
                    
                    rag_file = rag.upload_file(
                        corpus_name=corpus.name,
                        path=temp_file.name,
                        display_name=f"{product['name']} ({product['id']})",
                        description=f"Product information for {product['name']} - {product['description'][:100]}{'...' if len(product['description']) > 100 else ''}"
                    )
                    
                    uploaded_files.append({
                        "product_id": product['id'],
                        "product_name": product['name'],
                        "rag_file_name": rag_file.name,
                        "display_name": rag_file.display_name
                    })
                    
                    # Clean up temp file
                    os.unlink(temp_file.name)
                    logger.debug(f"Uploaded and cleaned up: {product['id']}")
                    
                except Exception as e:
                    logger.error(f"Failed to upload product {product.get('id', 'unknown')}: {e}")
                    # Clean up temp file on error
                    try:
                        os.unlink(temp_file.name)
                    except:
                        pass
                    continue
            
            logger.info(f"Successfully added {len(uploaded_files)}/{len(products)} products")
            
            return {
                "status": "products_added",
                "corpus_name": corpus.name,
                "product_count": len(uploaded_files),
                "uploaded_files": uploaded_files
            }
            
        except Exception as e:
            logger.error(f"Failed to add products: {e}")
            raise
    
    def search_products(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search products using RAG retrieval"""
        try:
            corpus = self._get_or_create_corpus()
            
            # Configure retrieval
            rag_retrieval_config = rag.RagRetrievalConfig(
                top_k=top_k,
                filter=rag.Filter(vector_distance_threshold=0.5),
            )
            
            # Perform retrieval query
            response = rag.retrieval_query(
                rag_resources=[
                    rag.RagResource(
                        rag_corpus=corpus.name,
                    )
                ],
                text=query,
                rag_retrieval_config=rag_retrieval_config,
            )
            
            # Extract relevant information from response
            results = []
            if hasattr(response, 'contexts') and response.contexts:
                for context in response.contexts.contexts:
                    # Parse product information from context text
                    text = context.text
                    
                    # Extract product ID using simple parsing
                    product_id = None
                    for line in text.split('\n'):
                        if 'Product ID:' in line:
                            product_id = line.split('Product ID:')[1].strip()
                            break
                    
                    if product_id:
                        results.append({
                            "product_id": product_id,
                            "text": text,
                            "source": context.source_uri if hasattr(context, 'source_uri') else None
                        })
            
            logger.info(f"Search for '{query}' returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    def get_rag_model(self) -> GenerativeModel:
        """Get RAG-enhanced Gemini model"""
        if self._rag_model is not None:
            return self._rag_model
        
        try:
            corpus = self._get_or_create_corpus()
            
            # Configure RAG retrieval
            rag_retrieval_config = rag.RagRetrievalConfig(
                top_k=5,
                filter=rag.Filter(vector_distance_threshold=0.5),
            )
            
            # Create RAG retrieval tool
            rag_retrieval_tool = Tool.from_retrieval(
                retrieval=rag.Retrieval(
                    source=rag.VertexRagStore(
                        rag_resources=[
                            rag.RagResource(
                                rag_corpus=corpus.name,
                            )
                        ],
                        rag_retrieval_config=rag_retrieval_config,
                    ),
                )
            )
            
            # Create RAG-enhanced Gemini model
            self._rag_model = GenerativeModel(
                model_name="gemini-2.0-flash-001", 
                tools=[rag_retrieval_tool]
            )
            
            logger.info("RAG-enhanced model created successfully")
            return self._rag_model
            
        except Exception as e:
            logger.error(f"Failed to create RAG model: {e}")
            raise
    
    def generate_response(self, query: str) -> str:
        """Generate response using RAG-enhanced model"""
        try:
            rag_model = self.get_rag_model()
            
            # Enhanced prompt for shopping assistant
            enhanced_query = f"""You are a helpful shopping assistant for Online Boutique. 
            Based on the product catalog information, please help with this customer query: {query}
            
            Provide helpful recommendations and include specific product details when relevant.
            Be conversational and friendly while being informative.
            
            Do not hallucinate. Do not make up information apart from the product catalog and the customer query. 
            If the customer query is not related to the product catalog, say that we dont have that product in our catalog politely.
            
            """
            # handle response properly if user asks junk queries
            response = rag_model.generate_content(enhanced_query)
            return response.text
            
        except Exception as e:
            logger.error(f"Failed to generate response: {e}")
            return f"I'm sorry, I'm having trouble processing your request: {str(e)}"
    
    def get_corpus_info(self) -> Dict[str, Any]:
        """Get information about the current corpus"""
        try:
            corpus = self._get_or_create_corpus()
            
            # List files in corpus
            files = rag.list_files(corpus.name)
            
            return {
                "corpus_name": corpus.name,
                "display_name": corpus.display_name,
                "file_count": len(files),
                "files": [{"name": f.name, "display_name": f.display_name} for f in files]
            }
            
        except Exception as e:
            logger.error(f"Failed to get corpus info: {e}")
            return {"error": str(e)}

def main():
    """Main function for testing"""
    import sys
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Get project ID from environment or command line
    project_id = os.getenv('PROJECT_ID')
    if not project_id and len(sys.argv) > 1:
        project_id = sys.argv[1]
    
    if not project_id:
        print("Error: PROJECT_ID environment variable or command line argument required")
        sys.exit(1)
    
    # Initialize manager
    manager = VertexRAGManager(project_id)
    
    # Find products.json
    products_file = "src/productcatalogservice/products.json"
    if not os.path.exists(products_file):
        products_file = "products.json"
        if not os.path.exists(products_file):
            print("Error: products.json not found")
            sys.exit(1)
    
    # Ingest products
    print(f"Ingesting products from: {products_file}")
    result = manager.ingest_products_from_json(products_file)
    print(f"Ingestion result: {result}")
    
    # Test search
    print("\nTesting search...")
    search_results = manager.search_products("sunglasses")
    print(f"Search results: {len(search_results)} found")
    
    # Test RAG generation
    print("\nTesting RAG generation...")
    response = manager.generate_response("I'm looking for accessories")
    print(f"RAG response: {response}")

if __name__ == "__main__":
    main()
