#!/usr/bin/env python3
"""
Auto RAG Update Script
Automatically detects and syncs new/updated products to RAG corpus using Vertex AI SDK
"""

import os
import json
import hashlib
import logging
import time
from typing import Set, Dict, Any, List
from rag_manager import VertexRAGManager

class RAGAutoUpdater:
    """Automatically updates RAG corpus when products.json changes"""
    
    def __init__(self, project_id: str, products_file: str):
        self.project_id = project_id
        self.products_file = products_file
        self.manager = VertexRAGManager(project_id)
        self.state_file = "rag_sync_state.json"
        
        self.logger = logging.getLogger(__name__)
        
        # Load previous state
        self.previous_state = self._load_state()
    
    def _load_state(self) -> Dict[str, Any]:
        """Load previous sync state"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            return {"product_hashes": {}, "last_sync": None}
        except Exception as e:
            self.logger.warning(f"Failed to load state: {e}")
            return {"product_hashes": {}, "last_sync": None}
    
    def _save_state(self, state: Dict[str, Any]):
        """Save current sync state"""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save state: {e}")
    
    def _get_product_hash(self, product: Dict[str, Any]) -> str:
        """Generate hash for product to detect changes"""
        # Create deterministic hash from product data
        product_str = json.dumps(product, sort_keys=True)
        return hashlib.md5(product_str.encode()).hexdigest()
    
    def _load_current_products(self) -> List[Dict[str, Any]]:
        """Load current products from JSON file"""
        try:
            with open(self.products_file, 'r') as f:
                catalog = json.load(f)
            return catalog.get('products', [])
        except Exception as e:
            self.logger.error(f"Failed to load products: {e}")
            return []
    
    def detect_changes(self) -> Dict[str, List[Dict[str, Any]]]:
        """Detect new, updated, and deleted products"""
        current_products = self._load_current_products()
        previous_hashes = self.previous_state.get("product_hashes", {})
        
        # Calculate current hashes
        current_hashes = {}
        current_products_by_id = {}
        
        for product in current_products:
            product_id = product['id']
            product_hash = self._get_product_hash(product)
            current_hashes[product_id] = product_hash
            current_products_by_id[product_id] = product
        
        # Detect changes
        new_products = []
        updated_products = []
        deleted_product_ids = []
        
        # Find new and updated products
        for product_id, current_hash in current_hashes.items():
            if product_id not in previous_hashes:
                # New product
                new_products.append(current_products_by_id[product_id])
                self.logger.info(f"New product detected: {product_id}")
            elif previous_hashes[product_id] != current_hash:
                # Updated product
                updated_products.append(current_products_by_id[product_id])
                self.logger.info(f"Updated product detected: {product_id}")
        
        # Find deleted products
        for product_id in previous_hashes:
            if product_id not in current_hashes:
                deleted_product_ids.append(product_id)
                self.logger.info(f"Deleted product detected: {product_id}")
        
        return {
            "new": new_products,
            "updated": updated_products,
            "deleted": deleted_product_ids,
            "current_hashes": current_hashes
        }
    
    def sync_changes(self, force_full_sync: bool = False) -> Dict[str, Any]:
        """Sync detected changes to RAG corpus"""
        if force_full_sync:
            self.logger.info("Performing full sync...")
            result = self.manager.ingest_products_from_json(self.products_file)
            
            # Update state
            current_products = self._load_current_products()
            current_hashes = {
                product['id']: self._get_product_hash(product) 
                for product in current_products
            }
            
            new_state = {
                "product_hashes": current_hashes,
                "last_sync": time.time(),
                "last_operation": result.get('corpus_name')
            }
            self._save_state(new_state)
            
            return {
                "type": "full_sync",
                "total_products": len(current_products),
                **result
            }
        
        # Detect changes
        changes = self.detect_changes()
        
        if not any([changes["new"], changes["updated"], changes["deleted"]]):
            self.logger.info("No changes detected")
            return {"type": "no_changes", "status": "up_to_date"}
        
        # Process changes
        results = []
        
        # Add/update new and modified products
        products_to_update = changes["new"] + changes["updated"]
        if products_to_update:
            self.logger.info(f"Updating {len(products_to_update)} products in RAG corpus")
            result = self.manager.add_products(products_to_update)
            results.append({
                "action": "add_update",
                "count": len(products_to_update),
                "products": [p['id'] for p in products_to_update],
                "status": result.get('status'),
                "corpus_name": result.get('corpus_name')
            })
        
        # Note: Vertex AI Agent Builder doesn't support easy document deletion
        # Deleted products will remain in corpus but won't appear in new syncs
        if changes["deleted"]:
            self.logger.warning(f"Deleted products detected but cannot be removed from corpus: {changes['deleted']}")
            self.logger.warning("Consider doing a full re-sync if you need to remove deleted products")
        
        # Update state
        new_state = {
            "product_hashes": changes["current_hashes"],
            "last_sync": time.time(),
            "last_operations": [r.get('corpus_name') for r in results if r.get('corpus_name')]
        }
        self._save_state(new_state)
        
        return {
            "type": "incremental_sync",
            "changes_detected": {
                "new": len(changes["new"]),
                "updated": len(changes["updated"]),
                "deleted": len(changes["deleted"])
            },
            "results": results
        }
    

def main():
    """Main function"""
    import argparse
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    # Parse arguments
    parser = argparse.ArgumentParser(description='Auto-update RAG corpus with product changes')
    parser.add_argument('--project-id', help='Google Cloud Project ID (or use PROJECT_ID env var)')
    parser.add_argument('--products-file', default='src/productcatalogservice/products.json', 
                       help='Path to products.json file')
    parser.add_argument('--full-sync', action='store_true', 
                       help='Force full sync instead of incremental')
    
    args = parser.parse_args()
    
    # Get project ID
    project_id = args.project_id or os.getenv('PROJECT_ID')
    if not project_id:
        logger.error("Project ID required (use --project-id or PROJECT_ID env var)")
        return 1
    
    # Check products file
    if not os.path.exists(args.products_file):
        logger.error(f"Products file not found: {args.products_file}")
        return 1
    
    try:
        # Initialize updater
        updater = RAGAutoUpdater(project_id, args.products_file)
        
        # One-time sync
        result = updater.sync_changes(force_full_sync=args.full_sync)
        
        print("\n" + "="*60)
        print("🔄 RAG SYNC COMPLETED")
        print("="*60)
        
        if result['type'] == 'no_changes':
            print("✅ No changes detected - corpus is up to date")
        elif result['type'] == 'full_sync':
            print(f"✅ Full sync completed - {result['total_products']} products")
            if result.get('last_operation'):
                print(f"📋 Corpus: {result['last_operation']}")
        elif result['type'] == 'incremental_sync':
            changes = result['changes_detected']
            print(f"✅ Incremental sync completed:")
            print(f"   📄 New products: {changes['new']}")
            print(f"   🔄 Updated products: {changes['updated']}")
            if changes['deleted'] > 0:
                print(f"   ⚠️  Deleted products: {changes['deleted']} (not removed from corpus)")
            
            for r in result['results']:
                if r.get('corpus_name'):
                    print(f"📋 Corpus: {r['corpus_name']}")
        
        logger.info("Sync completed successfully")
            
    except Exception as e:
        logger.error(f"Failed to sync: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
