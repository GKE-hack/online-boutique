# Chatbot Service

A conversational AI service that helps customers find and learn about products in the Online Boutique catalog using Google's Gemini 2.0 Flash model through Vertex AI.

## Features

- **Product Discovery**: Helps customers find products based on natural language queries
- **Product Information**: Provides detailed information about products including prices, descriptions, and categories
- **Smart Recommendations**: Uses AI to suggest relevant products based on customer needs
- **gRPC Integration**: Communicates with the Product Catalog Service using gRPC
- **RESTful API**: Provides HTTP endpoints for easy integration with frontend applications

## Architecture

The chatbot service consists of several key components:

1. **ChatbotService**: Main service class that orchestrates AI responses
2. **ProductCatalogClient**: gRPC client for communicating with the product catalog service
3. **Flask API**: HTTP API for frontend integration
4. **Health Checks**: Both HTTP and gRPC health check endpoints

## API Endpoints

### HTTP Endpoints

#### POST /chat
Send a message to the chatbot and get an AI-powered response.

**Request:**
```json
{
  "message": "I'm looking for something to wear for a summer party",
  "history": ["Previous conversation messages (optional)"]
}
```

**Response:**
```json
{
  "success": true,
  "response": "For a summer party, I'd recommend our stylish Tank Top! It's perfectly cropped with a scooped neckline, perfect for warm weather. At $18.99, it's both affordable and fashionable. You might also like our Sunglasses to complete the look - they're sleek aviator style for $19.99.",
  "recommended_products": ["66VCHSJNUP", "OLJCESPC7Z"],
  "total_products_considered": 9
}
```

#### GET /health
Health check endpoint.

**Response:**
```json
{
  "status": "healthy"
}
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PROJECT_ID` | Google Cloud Project ID | `your-project-id` |
| `LOCATION` | Vertex AI location | `us-central1` |
| `PRODUCT_CATALOG_SERVICE_ADDR` | Product catalog service address | `productcatalogservice:3550` |
| `HTTP_PORT` | HTTP server port | `8080` |
| `GRPC_PORT` | gRPC server port | `8081` |

## gRPC Communication

The service communicates with the Product Catalog Service using the following gRPC methods:

- `ListProducts()`: Get all products in the catalog
- `GetProduct(id)`: Get details for a specific product
- `SearchProducts(query)`: Search for products matching a query

## AI Model

The service uses **Gemini 2.0 Flash** (`gemini-2.0-flash-exp`) through Google Vertex AI for:

- Understanding customer queries and intent
- Generating natural, helpful responses
- Making intelligent product recommendations
- Maintaining conversational context

## Development

### Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Generate protobuf files:
```bash
./genproto.sh
```

3. Set environment variables:
```bash
export PROJECT_ID="your-gcp-project-id"
export LOCATION="us-central1"
export PRODUCT_CATALOG_SERVICE_ADDR="localhost:3550"
```

4. Run the service:
```bash
python chatbot_server.py
```

### Building the Docker Image

```bash
docker build -t chatbotservice .
```

### Deploying to Kubernetes

The service is automatically deployed as part of the Online Boutique application. To deploy manually:

```bash
kubectl apply -f ../kubernetes-manifests/chatbotservice.yaml
```

## Security

- Runs as non-root user (UID 1000)
- Read-only root filesystem
- Minimal privileges (drops all capabilities)
- Secure gRPC and HTTP communications

## Monitoring

The service provides:

- HTTP health checks at `/health`
- gRPC health checks via the standard health service
- Structured JSON logging
- Kubernetes readiness and liveness probes

## Example Conversations

**Customer**: "I need something for my kitchen"
**Chatbot**: "Great! I have several kitchen items that might interest you. The Bamboo Glass Jar is perfect for storage at just $5.49, and we have Salt & Pepper Shakers for $18.49 to add some flavor to your cooking. There's also a simple Mug with a mustard interior for $8.99. [9SIQT8TOJO] [LS4PSXUNUM] [6E92ZMYYFZ]"

**Customer**: "What accessories do you have?"
**Chatbot**: "We have some great accessories! Our Sunglasses are sleek aviator style that add a modern touch to any outfit for $19.99. We also have a beautiful gold-tone stainless steel Watch that works with most outfits for $109.99. [OLJCESPC7Z] [1YMWWN1N4O]" 