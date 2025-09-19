import os
import time
import uuid
import logging
import io
import requests
from typing import Dict, Any, Optional
from google import genai
from google.genai import types
import grpc
try:
    from PIL import Image
except ImportError:
    import PIL.Image as Image

# Import generated protobuf classes
import demo_pb2
import demo_pb2_grpc

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
    
    def get_product(self, product_id: str) -> Optional[Dict[str, Any]]:
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

    def search_products(self, query: str) -> list:
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

    def list_products(self) -> list:
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


class VideoGenerator:
    """Video generation service using Veo3 API"""
    
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        
        self.client = genai.Client(api_key=api_key)
        self.veo_model_id = os.getenv("VEO_MODEL_ID", "veo-3.0-fast-generate-001")
        self.jobs = {}  # In-memory job storage: {job_id: job_info}
        self.videos_dir = "/app/videos"
        os.makedirs(self.videos_dir, exist_ok=True)
        
        # Initialize Product Catalog client
        catalog_addr = os.getenv('PRODUCT_CATALOG_SERVICE_ADDR', 'productcatalogservice:3550')
        self.catalog_client = ProductCatalogClient(catalog_addr)

        # Get frontend service address for relative image URLs
        self.frontend_service_addr = os.getenv('FRONTEND_SERVICE_ADDR', 'frontend:80')
        
        logger.info("Video Generator initialized with Veo3 API")
    
    def generate_ad_prompt(self, product: Dict[str, Any]) -> str:
        """Generate cinematic advertisement prompt from product details"""
        name = product.get('name', 'Product')
        description = product.get('description', '')
        categories = product.get('categories', [])
        price = product.get('price_usd', {})
        price_text = f"${price.get('units', 0)}.{price.get('nanos', 0):02d}" if price else "affordable price"
        
        # Determine product type and setting
        product_type = self._categorize_product(categories, name)
        setting = self._get_appropriate_setting(product_type)
        
        # Build cinematic prompt structure
#         prompt = f"""{{
#   "metadata": {{
#     "prompt_name": "{name} Cinematic Advertisement",
#     "base_style": "cinematic, photorealistic, 4K, commercial-grade lighting",
#     "aspect_ratio": "16:9"
#   }},
#   "room_description": "{setting['description']}",
#   "camera_setup": "Professional commercial cinematography with smooth camera movements. Multiple angles showcasing the product. 8-second duration.",
#   "key_elements": [
#     "Featured product: {name}",
#     "Professional lighting setup",
#     "Clean, modern aesthetic",
#     "{setting['atmosphere']}"
#   ],
#   "product_showcase": [
#     "Product prominently displayed in center frame",
#     "Close-up shots highlighting key features",
#     "Lifestyle integration showing real-world use",
#     "Premium presentation emphasizing quality",
#     "Elegant product rotation or movement",
#     "Final hero shot with brand presence"
#   ],
#   "environmental_elements": {setting['elements']},
#   "negative_prompts": [
#     "no low quality",
#     "no amateur lighting",
#     "no cluttered backgrounds", 
#     "no distracting elements",
#     "no poor composition",
#     "no oversaturated colors",
#     "no human voiceover"
#   ],
#   "timeline": [
#     {{
#       "sequence": 1,
#       "timestamp": "00:00–00:02",
#       "action": "Establishing shot of the premium setting. Soft ambient lighting creates anticipation.",
#       "audio": "Subtle ambient background. Professional commercial tone."
#     }},
#     {{
#       "sequence": 2, 
#       "timestamp": "00:02–00:05",
#       "action": "Product reveal and close-up showcase. Highlight key features: {description[:100]}...",
#       "audio": "Smooth transition sound. Focus on product presentation."
#     }},
#     {{
#       "sequence": 3,
#       "timestamp": "00:05–00:07", 
#       "action": "Lifestyle demonstration showing product in use. Emphasize benefits and premium quality.",
#       "audio": "Engaging demonstration sounds natural to product use."
#     }},
#     {{
#       "sequence": 4,
#       "timestamp": "00:07–00:08",
#       "action": "Final hero shot with elegant presentation. Product positioned for maximum appeal.",
#       "audio": "Confident conclusion emphasizing desirability."
#     }}
#   ]
# }}

# Generate a premium, cinematic advertisement for {name} priced at {price_text}. Focus on luxury presentation, lifestyle integration, and compelling visual storytelling that makes viewers desire the product."""

        prompt = f"""{{
            You are an expert cinematic ad director. 
            Use the following metadata as the complete creative brief to generate a premium advertisement. 
            Do not treat the product image as a static opening frame — instead, stage a cinematic reveal. 
            Follow the timeline as the storyboard, and use the room description, key elements, and environmental details to guide the visual style.
            Audio must include continuous, premium-quality background music throughout the ad, seamlessly blending with the specific sound design described in each frame.

            Here is the structured metadata to use:

            "metadata": {{
                "prompt_name": "{name} Cinematic Advertisement",
                "base_style": "cinematic, photorealistic, 4K, commercial-grade lighting",
                "aspect_ratio": "16:9"
            }},
            "room_description": "{setting['description']}",
            "camera_setup": "High-end commercial cinematography with smooth motion. Use dolly-ins, pans, and dramatic lighting reveals. Avoid static product stills.",
            "key_elements": [
                "Featured product: {name}",
                "Dynamic and premium opening (not a freeze-frame)",
                "Professional lighting setup",
                "Clean, modern aesthetic",
                "{setting['atmosphere']}"
            ],
            "product_showcase": [
                "Product highlighted through cinematic lighting reveals",
                "Slow-motion close-ups emphasizing textures and key features",
                "Lifestyle integration showing product in real-world use",
                "Premium angles: overhead, rotating pedestal, and elegant framing",
                "Final hero shot with brand presence and tagline placement"
            ],
            "environmental_elements": {setting['elements']},
            "negative_prompts": [
                "no static freeze-frames",
                "no low quality",
                "no amateur lighting",
                "no cluttered backgrounds", 
                "no distracting elements",
                "no poor composition",
                "no oversaturated colors",
                "no human voiceover"
            ],
            "timeline": [
                {{
                    "sequence": 1,
                    "timestamp": "00:00–00:02",
                    "action": "Cinematic establishing shot of the {setting['description'].split('.')[0].lower()}. Product silhouette or outline revealed gradually through light sweep or camera motion. No still freeze-frame.",
                    "audio": "Subtle cinematic build-up layered over engaging background music (luxury, modern, ambient)."
                }},
                {{
                    "sequence": 2, 
                    "timestamp": "00:02–00:05",
                    "action": "Product comes fully into focus with close-up glamour shots. Showcase signature details and textures. Highlight key features: {description[:100]}...",
                    "audio": "Background music continues seamlessly. Smooth audio transition with subtle product accent sounds."
                }},
                {{
                    "sequence": 3,
                    "timestamp": "00:05–00:07", 
                    "action": "Lifestyle demonstration: product naturally in use in a {setting['atmosphere'].lower()}. Camera follows motion fluidly, showcasing benefits and premium feel.",
                    "audio": "Music maintains rhythm. Ambient lifestyle sounds blend naturally with the score."
                }},
                {{
                    "sequence": 4,
                    "timestamp": "00:07–00:08",
                    "action": "Final hero shot with elegant framing. Product rotates or sits center-stage with dramatic lighting. Brand or logo subtly integrated.",
                    "audio": "Music swells to a confident, premium climax. Concludes on a strong, memorable note."
                }}
            ]
            }}
            
            Task: Generate a cinematic, premium-quality advertisement for {name}. 
            Focus on luxury presentation, lifestyle integration, and compelling storytelling that makes viewers desire the product. 
            Always interpret the metadata as the creative brief.
            """

        return prompt
    
    def _categorize_product(self, categories: list, name: str) -> str:
        """Determine product category for appropriate cinematic treatment"""
        name_lower = name.lower()
        categories_lower = [cat.lower() for cat in categories]
        
        if any(cat in ['clothing', 'apparel'] for cat in categories_lower) or any(word in name_lower for word in ['shirt', 'dress', 'jacket', 'pants']):
            return 'fashion'
        elif any(cat in ['accessories'] for cat in categories_lower) or any(word in name_lower for word in ['watch', 'jewelry', 'bag', 'sunglasses']):
            return 'accessories'
        elif any(cat in ['home', 'decor'] for cat in categories_lower) or any(word in name_lower for word in ['mug', 'candle', 'pillow']):
            return 'home'
        elif any(cat in ['tech', 'electronics'] for cat in categories_lower) or any(word in name_lower for word in ['camera', 'phone', 'headphones']):
            return 'tech'
        else:
            return 'lifestyle'
    
    def _get_appropriate_setting(self, product_type: str) -> dict:
        """Get cinematic setting based on product type"""
        settings = {
            'fashion': {
                'description': 'A modern, minimalist studio with soft natural lighting from large windows. Clean white backdrop with subtle texture. Professional fashion photography setup.',
                'atmosphere': 'Elegant fashion studio ambiance with premium feeling',
                'elements': '["Professional photography lights with softboxes", "Seamless white backdrop", "Elegant wooden flooring", "Large windows with diffused daylight", "Minimalist furniture pieces", "Subtle shadows for depth"]'
            },
            'accessories': {
                'description': 'A luxurious, contemporary display space with marble surfaces and golden hour lighting. Premium materials and sophisticated ambiance.',
                'atmosphere': 'Upscale boutique environment with luxury appeal',
                'elements': '["Polished marble or granite surfaces", "Warm golden hour lighting", "Elegant display pedestals", "Soft fabric textures in background", "Metallic accent pieces", "Subtle reflective surfaces"]'
            },
            'home': {
                'description': 'A beautiful, modern home interior with natural lighting and cozy atmosphere. Clean design with warm, inviting elements.',
                'atmosphere': 'Comfortable home environment showcasing lifestyle',
                'elements': '["Natural wood surfaces", "Soft textiles and cushions", "Plants and natural elements", "Warm ambient lighting", "Modern furniture pieces", "Lifestyle props that complement the product"]'
            },
            'tech': {
                'description': 'A sleek, futuristic environment with clean lines and modern lighting. High-tech aesthetic with subtle digital elements.',
                'atmosphere': 'Modern tech showcase with innovation feel',
                'elements': '["Clean geometric surfaces", "LED accent lighting", "Metallic and glass materials", "Subtle digital displays", "Modern minimalist furniture", "Professional studio lighting"]'
            },
            'lifestyle': {
                'description': 'A versatile, contemporary space that adapts to showcase the product in its best light. Professional commercial setting.',
                'atmosphere': 'Premium commercial environment with broad appeal',
                'elements': '["Adaptable backdrop system", "Professional commercial lighting", "Clean, uncluttered surfaces", "Neutral color palette", "High-quality materials", "Flexible styling elements"]'
            }
        }
        return settings.get(product_type, settings['lifestyle'])
    
    def _fetch_product_image(self, product: Dict[str, Any]) -> Optional[tuple]:
        """
        Fetch and process product image for video generation
        
        Returns:
            tuple: (image_bytes, mime_type) or None if failed
        """
        picture_url = product.get('picture', '')
        if not picture_url:
            logger.warning(f"No picture URL found for product {product.get('id')}")
            return None
            
        try:
            # Handle relative URLs - add base URL if needed
            if picture_url.startswith('/static/'):
                full_picture_url = f"http://{self.frontend_service_addr}{picture_url}"
                logger.info(f"Relative URL detected, constructing full URL: {full_picture_url}")
            else:
                full_picture_url = picture_url
            
            # Fetch the image
            response = requests.get(full_picture_url, timeout=10)
            response.raise_for_status()
            
            # Open and process image with PIL
            image_bytes_data = response.content
            image_io = io.BytesIO(image_bytes_data)
            im = Image.open(image_io)
            
            # Convert to RGB if necessary (for JPEG compatibility)
            if im.mode != 'RGB':
                im = im.convert('RGB')
            
            # Prepare image for Veo3 API
            image_bytes_io = io.BytesIO()
            im.save(image_bytes_io, format='JPEG')
            image_bytes = image_bytes_io.getvalue()
            
            logger.info(f"Successfully processed product image: {len(image_bytes)} bytes")
            return (image_bytes, 'image/jpeg')
            
        except Exception as e:
            logger.error(f"Failed to fetch/process product image from {picture_url}: {e}")
            return None
    
    def get_video_path(self, video_filename: str) -> Optional[str]:
        """Get the full path to a video file if it exists"""
        video_path = os.path.join(self.videos_dir, video_filename)
        if os.path.exists(video_path):
            return video_path
        return None
    
    def start_video_generation(self, product_id: str) -> str:
        """Start video generation for a product"""
        # Generate unique job ID
        job_id = str(uuid.uuid4())
        
        # Get product details
        product = self.catalog_client.get_product(product_id)
        if not product:
            raise ValueError(f"Product {product_id} not found")
        
        # Generate prompt
        prompt = self.generate_ad_prompt(product)
        
        # Log the prompt
        logger.info(f"Prompt: {prompt}")
        
        # Initialize job
        self.jobs[job_id] = {
            'status': 'starting',
            'product_id': product_id,
            'product': product,
            'prompt': prompt,
            'operation': None,
            'video_path': None,
            'error': None,
            'created_at': time.time()
        }
        
        try:
            # Fetch product image
            image_data = self._fetch_product_image(product)
            
            # Start Veo3 generation
            logger.info(f"Starting video generation for product {product_id} with job {job_id}")
            
            if image_data:
                # Generate with product image
                image_bytes, mime_type = image_data
                logger.info(f"Including product image in video generation ({len(image_bytes)} bytes, {mime_type})")
                
                operation = self.client.models.generate_videos(
                    model=self.veo_model_id,
                    prompt=prompt,
                    image=types.Image(image_bytes=image_bytes, mime_type=mime_type),
                    config=types.GenerateVideosConfig(
                        aspect_ratio="16:9",
                        resolution="720p",
                        number_of_videos=1
                    ),
                )
            else:
                # Generate without image (fallback)
                logger.info("No product image available, generating video with prompt only")
                operation = self.client.models.generate_videos(
                    model=self.veo_model_id,
                    prompt=prompt,
                    config=types.GenerateVideosConfig(
                        aspect_ratio="16:9",
                        resolution="720p", 
                        number_of_videos=1
                    ),
                )
            
            self.jobs[job_id]['operation'] = operation
            self.jobs[job_id]['status'] = 'generating'
            
            logger.info(f"Video generation started for job {job_id}")
            return job_id
            
        except Exception as e:
            logger.error(f"Error starting video generation for job {job_id}: {e}")
            self.jobs[job_id]['status'] = 'failed'
            self.jobs[job_id]['error'] = str(e)
            raise
    
    def check_job_status(self, job_id: str) -> Dict[str, Any]:
        """Check the status of a video generation job"""
        if job_id not in self.jobs:
            return {'status': 'not_found', 'error': 'Job not found'}
        
        job = self.jobs[job_id]
        
        try:
            if job['status'] == 'generating' and job['operation']:
                # Check if operation is complete
                operation = self.client.operations.get(job['operation'])
                
                if operation.done:
                    # Check if operation completed successfully with videos
                    if (hasattr(operation, 'response') and operation.response and 
                        hasattr(operation.response, 'generated_videos') and 
                        operation.response.generated_videos and 
                        len(operation.response.generated_videos) > 0):
                        
                        # Download the generated video
                        generated_video = operation.response.generated_videos[0]
                        video_filename = f"{job_id}.mp4"
                        video_path = os.path.join(self.videos_dir, video_filename)
                        
                        # Download and save video
                        self.client.files.download(file=generated_video.video)
                        generated_video.video.save(video_path)
                        
                        job['status'] = 'completed'
                        job['video_path'] = video_path
                        job['video_filename'] = video_filename
                        
                        logger.info(f"Video generation completed for job {job_id}. Video saved to {video_path}")
                    else:
                        # Operation completed but no videos generated
                        job['status'] = 'failed'
                        job['error'] = 'Video generation completed but no videos were generated'
                        logger.error(f"Video generation failed for job {job_id}: No videos generated. Full operation response: {operation.response}")
                    
                    logger.info(f"Video generation completed for job {job_id}")
                else:
                    logger.info(f"Video generation still in progress for job {job_id}")
            
            return {
                'status': job['status'],
                'product': job['product'],
                'video_filename': job.get('video_filename'),
                'error': job.get('error')
            }
            
        except Exception as e:
            logger.error(f"Error checking job status for {job_id}: {e}")
            job['status'] = 'failed'
            job['error'] = str(e)
            return {'status': 'failed', 'error': str(e)}
    
    def get_video_path(self, video_filename: str) -> Optional[str]:
        """Get the full path to a generated video file"""
        video_path = os.path.join(self.videos_dir, video_filename)
        if os.path.exists(video_path):
            return video_path
        return None
