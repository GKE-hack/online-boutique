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
import vertexai
from vertexai.generative_models import GenerativeModel, Part 
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
        
        # Initialize Gemini 2.0 Flash model
        project_id = os.getenv('PROJECT_ID')
        location = os.getenv('LOCATION')
        if project_id and location:
            vertexai.init(project=project_id, location=location)
            logger.info("Vertex AI initialized successfully")
            self.llm_model = GenerativeModel("gemini-2.5-flash")
            logger.info("Gemini 2.5 Flash model initialized successfully")
        else:
            logger.warning("PROJECT_ID or LOCATION not set, Vertex AI not initialized.")
        
        logger.info("Video Generator initialized with Veo3 API")
    
    def _generate_ad_script_with_llm(self, product: Dict[str, Any], image_data: Optional[tuple] = None) -> str:
        if not hasattr(self, 'llm_model'):
            logger.error("LLM model not initialized. Cannot generate ad script.")
            raise RuntimeError("LLM model not initialized")

        name = product.get('name', 'Product')

        prompt_parts = [
            f"""
            You are a professional script writer for Cinematic Advertisements, 
            I want you to make an advertisment using this Product Image given to you for the Product Name: {name}, write me an 8 second advertisement script detailing the shot, narration, audio, atmosphere, surroundings and explicit details of the advertisement.
            Here are the specifics that you need to follow:
                1. catchy background music
                2. strong tagline at the end with human voiceover
                3. smooth transitions

            Give me a single script with 3 shots including timelines and do not provide any placeholder.
            """
        ]

        if image_data:
            image_bytes, mime_type = image_data
            prompt_parts.append(Part.from_data(image_bytes, mime_type=mime_type))
            logger.info("Including product image in LLM prompt for script generation.")

        logger.info(f"Making LLM call to generate ad script for product: {name}")
        logger.info(f"Prompt for Script Generation: {prompt_parts[0]}")
        try:
            response = self.llm_model.generate_content(prompt_parts)
            if response and response.text:
                logger.info("Successfully generated ad script with LLM.")
                return response.text
            else:
                logger.error("LLM did not return a valid script.")
                raise RuntimeError("LLM did not return a valid script")
        except Exception as e:
            logger.error(f"Error generating ad script with LLM: {e}")
            raise

    
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

        # Fetch product image
        image_data = self._fetch_product_image(product)
        
        # Generate prompt using LLM
        prompt = self._generate_ad_script_with_llm(product, image_data)

        prompt += """\n\n
            Negative Prompts:
                - no low quality
                - no amateur lighting
                - no cluttered backgrounds
                - no distracting elements
                - no poor composition
                - no oversaturated colors

            Using the above given specifications, generate a cinematic, photorealistic, 4K, commercial-grade lighting advertisement.
        """
        
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
