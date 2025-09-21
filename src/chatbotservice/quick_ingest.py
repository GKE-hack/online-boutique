#!/usr/bin/env python3
"""
Quick RAG Ingestion Script
Simple script to create corpus and ingest products.json using Vertex AI SDK
"""

import os
import sys
import logging
from rag_manager import VertexRAGManager

def setup_logging():
    """Configure logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def main():
    """Main function"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Get project ID
    project_id = os.getenv('PROJECT_ID')
    if not project_id:
        logger.error("PROJECT_ID environment variable is required")
        print("Usage: export PROJECT_ID=your-project-id && python quick_ingest.py")
        sys.exit(1)
    
    # Find products.json file
    possible_paths = [
        "src/productcatalogservice/products.json",
        "products.json",
        "../productcatalogservice/products.json"
    ]
    
    products_file = None
    for path in possible_paths:
        if os.path.exists(path):
            products_file = path
            break
    
    if not products_file:
        logger.error("products.json file not found in any of these locations:")
        for path in possible_paths:
            logger.error(f"  - {path}")
        sys.exit(1)
    
    logger.info(f"Found products file: {products_file}")
    
    try:
        # Initialize RAG manager
        logger.info(f"Initializing Vertex RAG manager for project: {project_id}")
        manager = VertexRAGManager(project_id=project_id)
        
        # Ingest products (creates corpus automatically)
        # logger.info("Starting product ingestion...")
        # result = manager.ingest_products_from_json(products_file)
        
        # if result['status'] == 'import_completed':
        #     logger.info("✅ Ingestion completed successfully!")
        #     logger.info(f"📄 Documents: {result['document_count']}")
        #     logger.info(f"🏛️  Corpus: {result['corpus_name']}")
            
        #     print("\n" + "="*60)
        #     print("🚀 RAG CORPUS INGESTION COMPLETED")
        #     print("="*60)
        #     print(f"Project ID: {project_id}")
        #     print(f"Corpus: {result['corpus_name']}")
        #     print(f"Documents: {result['document_count']}")
        #     print("\n📍 You can view your corpus in Google Cloud Console:")
        #     print("   Vertex AI → RAG → Corpora")
        #     print("\n✨ Your chatbot now has RAG capabilities!")
            
        # Test the RAG functionality
        print("\n🧪 Testing RAG search...")
        search_results = manager.search_products("sunglasses", top_k=3)
        print(f"Search test: Found {len(search_results)} results for 'sunglasses'")
        
        print("\n🤖 Testing RAG generation...")
        response = manager.generate_response("I need something for winter")
        print(f"Generation test: {response}...")
            
        # else:
        #     logger.warning(f"Unexpected result: {result}")
            
    except Exception as e:
        logger.error(f"❌ Failed to ingest products: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
