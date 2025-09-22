<!-- <p align="center">
<img src="/src/frontend/static/icons/Hipster_HeroLogoMaroon.svg" width="300" alt="Online Boutique" />
</p> -->


**Online Boutique** is a cloud-first microservices demo application.  The application is a
web-based e-commerce app where users can browse items, add them to the cart, and purchase them.

Google uses this application to demonstrate how developers can modernize enterprise applications using Google Cloud products, including: [Google Kubernetes Engine (GKE)](https://cloud.google.com/kubernetes-engine), [Cloud Service Mesh (CSM)](https://cloud.google.com/service-mesh), [gRPC](https://grpc.io/), [Cloud Operations](https://cloud.google.com/products/operations), [Spanner](https://cloud.google.com/spanner), [Memorystore](https://cloud.google.com/memorystore), [AlloyDB](https://cloud.google.com/alloydb), and [Gemini](https://ai.google.dev/). This application works on any Kubernetes cluster.


## Architecture

[![Architecture of
microservices](/docs/img/architecture-diagram.png)](/docs/img/architecture-diagram.png)


## AI Services Added

The Online Boutique has been enhanced with several AI-powered services to improve the customer experience and streamline operations:

### 1. Chatbot Service
Integrates Google Gemini (2.5 Flash model) with Retrieval Augmented Generation (RAG) capabilities to provide a smart shopping assistant. It answers product-related queries, offers recommendations, and interacts with the Product Catalog Service to fetch real-time product information.

**User Flow:**
*   **User to Frontend**: A user interacts with the Frontend by sending chat messages.
*   **Frontend to Chatbot Service**: The Frontend sends these messages (either in a single request or as a stream) to the Chatbot Service via HTTP.
*   **Chatbot Service Processing**: The Chatbot Server receives the message. It uses the Vertex AI RAG Manager to generate an RAG-enhanced response by querying the Vertex AI RAG Corpus for relevant product information and then feeds that context to the Gemini 2.0 Flash Model. 
*   **Chatbot Service to Frontend**: The Chatbot Service sends the generated response back to the Frontend.
*   **Frontend to User**: The Frontend displays the response to the user.
*   **RAG Corpus Updates**: Separately, `quick_ingest.py` is used for initial population, and `auto_update_rag.py` runs periodically to ensure the Vertex AI RAG Corpus is synchronized with the `products.json` file, thus reflecting the latest product catalog.

### 2. Try-On Service
Leverages Google Gemini's multimodal capabilities (2.5 Flash Image Preview model aka NanoBanana) to enable virtual product try-on. Users can navigate to the product and can upload a base image (e.g., themselves), and the service generates a realistic image of the product integrated into the base image.

**User Flow:**
*   **User Initiates Try-On**: The user, interacting with a frontend application, selects a product and uploads a base image (e.g., a photo of themselves).
*   **Frontend to Try-On Service**: The Frontend sends an HTTP POST request with `multipart/form-data` (base image, product image, category) to the Try-On Service's `/tryon` endpoint.
*   **Try-On Service to Gemini API**: The Try-On Service converts images and a category-specific prompt, then sends an HTTPS request to the NanoBanana model.
*   **Try-On Service to Frontend**: The Try-On Service returns the generated image as an HTTP Response with `media_type="image/png"` to the Frontend.
*   **Frontend to User**: The Frontend displays the virtual try-on image to the user.

### 3. Video Generation Service
Utilizes Google Gemini (2.5 Flash model) to generate ad scripts and the Veo3 API for video generation. This service creates AI-powered video advertisements for products, fetching product details and images from the Product Catalog Service to produce cinematic, photorealistic advertisements. **It includes RBAC capabilities, restricting video generation to admin users only.**

**User Flow:**
*   **Admin Browses**: An admin user interacts with the Frontend to discover products for which they want to generate ads using the endpoint("/admin").
*   **Product Search**: The Frontend queries the Video Generation Service via HTTP/JSON to search/list products.
*   **Generate Ad Request**: The admin user selects a product, and the Frontend requests video ad generation from the Video Generation Service via HTTP POST/JSON.
*   **Ad Scripting & Video Synthesis**: The Video Generation Service uses HTTPS to call the Google Gemini API for an ad script, then the Veo3 API (also via HTTPS) to create the video. It fetches product details from the Product Catalog Service via gRPC.
*   **Status Check**: The Frontend polls the Video Generation Service for video generation status.
*   **Video Retrieval**: Once complete, the Frontend retrieves the video file from the Video Generation Service.
*   **Validation**: The admin user can approve/reject the video, and the Frontend sends feedback to the Video Generation Service.

### 4. PEAU (Proactive Engagement & Upselling) Agent
Tracks user behavior (e.g., product views, items added to cart) to generate proactive, personalized suggestions and recommendations. It uses LlmAgent built using ADK powered by Gemini 2.0 Flash, interacting with the Product Catalog Service to fetch product details and leveraging a MCP server to expose its capabilities to other microservices.

**User Flow:**
*   **Event Ingestion**: Frontend (or services) send user behavior events (e.g., `product_viewed`, `item_added_to_cart`) to the PEAU Agent.
*   **Hesitation Case**: If the same product is viewed 5+ (can relax the threshold) times without being added to cart, PEAU generates a short, playful hesitation message as a notification in the frontend urging the user to buy it.
*   **Add-to-Cart Case**: When a product is added to cart, PEAU searches related products (via MCP tool → Product Catalog) and returns a brief upsell message with 1–2 recommended product IDs in brackets.
*   **Suggestion Delivery**: Suggestions can be consumed by the user by clicking on the notification bell in the header.

## Screenshots

| Home Page                                                                                                         | Checkout Screen                                                                                                    |
| ----------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| [![Screenshot of store homepage](/docs/img/online-boutique-frontend-1.png)](/docs/img/online-boutique-frontend-1.png) | [![Screenshot of checkout screen](/docs/img/online-boutique-frontend-2.png)](/docs/img/online-boutique-frontend-2.png) |

