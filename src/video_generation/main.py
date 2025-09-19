import os
import logging
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from video_generator import VideoGenerator

logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "severity": "%(levelname)s", "message": "%(message)s"}',
    datefmt='%Y-%m-%dT%H:%M:%S.%fZ'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Initialize video generator
try:
    video_generator = VideoGenerator()
    logger.info("Video generation service initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize video generator: {e}")
    video_generator = None

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'})

@app.route('/products/search', methods=['GET'])
def search_products():
    """Search products for video generation"""
    try:
        query = request.args.get('q', '')
        if not video_generator:
            return jsonify({'error': 'Video generator not initialized'}), 500
        
        if query:
            products = video_generator.catalog_client.search_products(query)
        else:
            products = video_generator.catalog_client.list_products()
        
        # Format products for frontend
        formatted_products = []
        for product in products:
            price = product.get('price_usd', {})
            price_display = f"${price.get('units', 0)}.{price.get('nanos', 0):02d}" if price else "N/A"
            
            formatted_products.append({
                'id': product['id'],
                'name': product['name'],
                'description': product['description'],
                'price': price_display,
                'categories': product.get('categories', []),
                'picture': product.get('picture', '')
            })
        
        return jsonify({'products': formatted_products})
    
    except Exception as e:
        logger.error(f"Error searching products: {e}")
        return jsonify({'error': 'Failed to search products'}), 500

@app.route('/generate-ad', methods=['POST'])
def generate_ad():
    """Start video advertisement generation for a product"""
    try:
        data = request.get_json()
        product_id = data.get('product_id')
        
        if not product_id:
            return jsonify({'error': 'product_id is required'}), 400
        
        if not video_generator:
            return jsonify({'error': 'Video generator not initialized'}), 500
        
        # Start video generation
        job_id = video_generator.start_video_generation(product_id)
        
        return jsonify({
            'status': 'success',
            'job_id': job_id,
            'message': 'Video generation started'
        })
    
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Error starting video generation: {e}")
        return jsonify({'error': 'Failed to start video generation'}), 500

@app.route('/video-status/<job_id>', methods=['GET'])
def video_status(job_id):
    """Check the status of video generation"""
    try:
        if not video_generator:
            return jsonify({'error': 'Video generator not initialized'}), 500
        
        status = video_generator.check_job_status(job_id)
        return jsonify(status)
    
    except Exception as e:
        logger.error(f"Error checking video status: {e}")
        return jsonify({'error': 'Failed to check video status'}), 500

@app.route('/video/<video_filename>', methods=['GET'])
def serve_video(video_filename):
    """Serve generated video file"""
    try:
        if not video_generator:
            return jsonify({'error': 'Video generator not initialized'}), 500
        
        video_path = video_generator.get_video_path(video_filename)
        if not video_path:
            return jsonify({'error': 'Video not found'}), 404
        
        return send_file(video_path, as_attachment=False, mimetype='video/mp4')
    
    except Exception as e:
        logger.error(f"Error serving video: {e}")
        return jsonify({'error': 'Failed to serve video'}), 500

@app.route('/validate-video', methods=['POST'])
def validate_video():
    """Validate generated video (approve/reject)"""
    try:
        data = request.get_json()
        job_id = data.get('job_id')
        approved = data.get('approved', False)
        
        if not job_id:
            return jsonify({'error': 'job_id is required'}), 400
        
        # For now, just log the validation
        # In a real system, you might update the job status or move files
        logger.info(f"Video validation for job {job_id}: {'approved' if approved else 'rejected'}")
        
        return jsonify({
            'status': 'success',
            'message': f"Video {'approved' if approved else 'rejected'} successfully"
        })
    
    except Exception as e:
        logger.error(f"Error validating video: {e}")
        return jsonify({'error': 'Failed to validate video'}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
