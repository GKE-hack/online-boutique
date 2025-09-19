# Online Boutique Microservices

This document provides an overview of the microservices that make up the Online Boutique application.

---

## Ad Service

This microservice provides advertisements to be displayed on the website.

### Service Description

The Ad Service is a gRPC service that serves ads based on the context of the page where the ad is displayed. The ads are chosen based on a list of context keywords (categories) provided in the request. If no relevant ads are found for the given context, a random selection of ads is returned.

The ads themselves and their associated categories are currently hardcoded within the service. Each ad consists of a redirect URL (linking to a product) and a short text description.

### gRPC Interface

The service is defined by the `AdService` interface in the `demo.proto` protobuf file.

```protobuf
service AdService {
    rpc GetAds(AdRequest) returns (AdResponse) {}
}

message AdRequest {
    repeated string context_keys = 1;
}

message AdResponse {
    repeated Ad ads = 1;
}

message Ad {
    string redirect_url = 1;
    string text = 2;
}
```

### `GetAds` RPC Call

-   **Request**: `AdRequest`
    -   `context_keys`: A list of strings representing keywords or categories from the page.
-   **Response**: `AdResponse`
    -   `ads`: A list of `Ad` messages to be displayed.

### How to Use

To get ads from this service, a client needs to make a gRPC call to the `GetAds` method, providing a list of context keywords in the `AdRequest`. The service will respond with a list of ads in the `AdResponse`.

If the `context_keys` list is empty, the service will return a random set of ads.

### Dependencies

This service does not have any external dependencies like databases or other microservices. All ad data is self-contained.

---

## Cart Service

This microservice provides shopping cart management functionality.

### Service Description

The Cart Service is a gRPC service responsible for managing user shopping carts. It allows adding items to a user's cart, retrieving the contents of the cart, and clearing the cart.

This service is written in C# and uses a persistent storage backend to maintain cart data across user sessions.

### gRPC Interface

The service is defined by the `CartService` interface in the `demo.proto` protobuf file.

```protobuf
service CartService {
    rpc AddItem(AddItemRequest) returns (Empty) {}
    rpc GetCart(GetCartRequest) returns (Cart) {}
    rpc EmptyCart(EmptyCartRequest) returns (Empty) {}
}

message CartItem {
    string product_id = 1;
    int32  quantity = 2;
}

message AddItemRequest {
    string user_id = 1;
    CartItem item = 2;
}

message EmptyCartRequest {
    string user_id = 1;
}

message GetCartRequest {
    string user_id = 1;
}

message Cart {
    string user_id = 1;
    repeated CartItem items = 2;
}
```

### `AddItem` RPC Call

-   **Request**: `AddItemRequest`
    -   `user_id`: The ID of the user.
    -   `item`: The `CartItem` to add to the cart.
-   **Response**: `Empty`

### `GetCart` RPC Call

-   **Request**: `GetCartRequest`
    -   `user_id`: The ID of the user whose cart is to be retrieved.
-   **Response**: `Cart`
    -   `user_id`: The user's ID.
    -   `items`: A list of `CartItem`s in the user's cart.

### `EmptyCart` RPC Call

-   **Request**: `EmptyCartRequest`
    -   `user_id`: The ID of the user whose cart is to be emptied.
-   **Response**: `Empty`

### How to Use

Clients can interact with the service by making gRPC calls to its methods. A `user_id` is required for all operations to identify the user's cart.

### Dependencies

The Cart Service depends on a database for storing cart data. The implementation provides support for the following backends:
-   Redis (default)
-   AlloyDB
-   Spanner

The choice of backend can be configured during deployment.

---

## Checkout Service

This microservice handles the checkout process by orchestrating calls to other microservices.

### Service Description

The Checkout Service is a gRPC service that manages the entire checkout flow. It is responsible for processing a user's order by coordinating with various other services to perform tasks such as calculating costs, processing payments, shipping the order, and sending confirmations.

This service is written in Go. It does not have its own persistent storage; it is a stateless orchestrator that relies on other services to manage state.

### gRPC Interface

The service is defined by the `CheckoutService` interface in the `demo.proto` protobuf file.

```protobuf
service CheckoutService {
    rpc PlaceOrder(PlaceOrderRequest) returns (PlaceOrderResponse) {}
}

message PlaceOrderRequest {
    string user_id = 1;
    string user_currency = 2;
    Address address = 3;
    string email = 5;
    CreditCardInfo credit_card = 6;
}

message PlaceOrderResponse {
    OrderResult order = 1;
}
```

### `PlaceOrder` RPC Call

-   **Request**: `PlaceOrderRequest`
    -   `user_id`: The ID of the user placing the order.
    -   `user_currency`: The currency the user has selected for the transaction.
    -   `address`: The shipping address for the order.
    -   `email`: The user's email address for the order confirmation.
    -   `credit_card`: The user's credit card information for payment.
-   **Response**: `PlaceOrderResponse`
    -   `order`: An `OrderResult` message containing the details of the completed order.

### How to Use

To place an order, a client must call the `PlaceOrder` method with all the required information in the `PlaceOrderRequest`. The service will then handle the entire checkout process.

### Orchestration Flow

Upon receiving a `PlaceOrder` request, the Checkout Service performs the following steps:

1.  **Get Cart**: Retrieves the user's cart from the `CartService`.
2.  **Prepare Items**: Fetches product details from the `ProductCatalogService` for each item in the cart.
3.  **Quote Shipping**: Obtains a shipping quote from the `ShippingService`.
4.  **Convert Currency**: Converts product prices and shipping costs to the user's currency using the `CurrencyService`.
5.  **Charge Card**: Processes the payment by calling the `PaymentService`.
6.  **Ship Order**: Finalizes the shipment by calling the `ShippingService`.
7.  **Empty Cart**: Clears the user's cart via the `CartService`.
8.  **Send Confirmation**: Sends an order confirmation email through the `EmailService`.

### Dependencies

The Checkout Service is dependent on the following microservices:
-   `CartService`
-   `ProductCatalogService`
-   `ShippingService`
-   `CurrencyService`
-   `PaymentService`
-   `EmailService`

---

## Currency Service

This microservice provides currency conversion and a list of supported currencies.

### Service Description

The Currency Service is a gRPC service that handles currency-related operations. It can convert an amount from one currency to another and provides a list of all supported currencies.

This service is written in Node.js. All currency conversion rates are loaded from a local JSON file (`data/currency_conversion.json`), which is based on data from the European Central Bank. The service uses Euros (EUR) as a base for all conversions.

### gRPC Interface

The service is defined by the `CurrencyService` interface in the `demo.proto` protobuf file.

```protobuf
service CurrencyService {
    rpc GetSupportedCurrencies(Empty) returns (GetSupportedCurrenciesResponse) {}
    rpc Convert(CurrencyConversionRequest) returns (Money) {}
}

message Money {
    string currency_code = 1;
    int64 units = 2;
    int32 nanos = 3;
}

message GetSupportedCurrenciesResponse {
    repeated string currency_codes = 1;
}

message CurrencyConversionRequest {
    Money from = 1;
    string to_code = 2;
}
```

### `GetSupportedCurrencies` RPC Call

-   **Request**: `Empty`
-   **Response**: `GetSupportedCurrenciesResponse`
    -   `currency_codes`: A list of strings representing the 3-letter currency codes (ISO 4217) of all supported currencies.

### `Convert` RPC Call

-   **Request**: `CurrencyConversionRequest`
    -   `from`: A `Money` message representing the amount and currency to be converted.
    -   `to_code`: The 3-letter currency code to convert to.
-   **Response**: `Money`
    -   A `Money` message representing the converted amount in the target currency.

### How to Use

-   To get a list of all supported currencies, call the `GetSupportedCurrencies` method.
-   To perform a currency conversion, call the `Convert` method with the source amount and target currency code.

### Dependencies

This service has no external dependencies on other microservices or databases. All necessary data is included in the service's own data file.

---

## Email Service

This microservice is responsible for sending emails to users, specifically for order confirmations.

### Service Description

The Email Service is a gRPC service that handles sending order confirmation emails. It receives the order details and the recipient's email address, and (in a non-dummy implementation) would send a formatted HTML email.

This service is written in Python. It uses a Jinja2 template (`templates/confirmation.html`) to render the email content.

**Note:** The current implementation runs in a "dummy mode" where it only logs that an email would have been sent, without actually sending one. A full implementation would require integration with an email sending service (e.g., SendGrid, Mailgun, or a cloud provider's email service).

### gRPC Interface

The service is defined by the `EmailService` interface in the `demo.proto` protobuf file.

```protobuf
service EmailService {
    rpc SendOrderConfirmation(SendOrderConfirmationRequest) returns (Empty) {}
}

message OrderItem {
    CartItem item = 1;
    Money cost = 2;
}

message OrderResult {
    string   order_id = 1;
    string   shipping_tracking_id = 2;
    Money shipping_cost = 3;
    Address  shipping_address = 4;
    repeated OrderItem items = 5;
}

message SendOrderConfirmationRequest {
    string email = 1;
    OrderResult order = 2;
}
```

### `SendOrderConfirmation` RPC Call

-   **Request**: `SendOrderConfirmationRequest`
    -   `email`: The recipient's email address.
    -   `order`: An `OrderResult` message containing all the details of the order to be included in the confirmation email.
-   **Response**: `Empty`

### How to Use

To send an order confirmation, a client needs to call the `SendOrderConfirmation` method with the user's email and the order details.

### Dependencies

This service has no external dependencies on other microservices or databases.

---

## Frontend Service

This service is the web frontend for the online boutique, serving the user interface and handling all user interactions.

### Service Description

The Frontend is an HTTP web server that acts as the main entry point for users of the application. It is responsible for rendering the website's pages, handling user requests, and communicating with the backend microservices to fetch data and perform actions.

This service is written in Go and uses standard Go libraries for its web server and templating. It is the only service that is directly exposed to the public internet.

### Responsibilities

-   **Serves Web Pages**: Renders HTML templates for all pages of the website, including the home page, product pages, cart, and checkout.
-   **User Session Management**: Manages user sessions using cookies.
-   **Backend Communication**: Acts as a client to all the backend gRPC microservices. It makes requests to these services to:
    -   List products (`ProductCatalogService`)
    -   Manage the shopping cart (`CartService`)
    -   Perform currency conversions (`CurrencyService`)
    -   Get product recommendations (`RecommendationService`)
    -   Display ads (`AdService`)
    -   Process checkouts (`CheckoutService`)
-   **Handles User Input**: Processes user actions such as adding items to the cart, changing currency, and placing orders.

### How it Works

When a user visits the website, the Frontend service receives the HTTP request. It then:
1.  Identifies the user's session or creates a new one.
2.  Based on the requested page, it makes one or more gRPC calls to the appropriate backend services to get the necessary data.
3.  It renders an HTML template, populating it with the data received from the backend.
4.  The final HTML is sent back to the user's browser.

### Dependencies

The Frontend service is dependent on nearly all of the other microservices in the application:
-   `ProductCatalogService`
-   `CurrencyService`
-   `CartService`
-   `RecommendationService`
-   `CheckoutService`
-   `ShippingService`
-   `AdService`
-   `ShoppingAssistantService`

---

## Load Generator

This component is a load generator used for simulating user traffic to the application.

### Service Description

The Load Generator is a tool designed to simulate the behavior of users interacting with the online boutique. It creates realistic traffic patterns to help with performance testing, stress testing, and identifying potential bottlenecks in the system.

This service is built using [Locust](https://locust.io/), a popular open-source load testing tool written in Python. It is not a user-facing service and is typically only run in development or testing environments.

### Simulated User Behavior

The `locustfile.py` script defines a set of tasks that simulate a typical user's journey through the website. The tasks are weighted to create a realistic distribution of traffic. The simulated behaviors include:

-   **Visiting the home page**
-   **Browsing products**
-   **Changing currency**
-   **Adding items to the cart**
-   **Viewing the cart**
-   **Checking out**
-   **Emptying the cart**
-   **Logging out**

The checkout process uses fake data generated by the [Faker](https://faker.readthedocs.io/) library to simulate filling out the checkout form.

### How to Use

To run the load generator, you would typically start the Locust process, pointing it at the frontend service's URL. You can then use the Locust web interface to control the number of simulated users and the rate at which they are spawned.

Example of running Locust locally:
```bash
locust -f src/loadgenerator/locustfile.py --host=http://localhost:8080
```

### Dependencies

The Load Generator directly interacts only with the `Frontend` service, as a real user would. It has no knowledge of the backend microservices.

---

## Payment Service

This microservice handles payment processing, simulating a transaction with a credit card.

### Service Description

The Payment Service is a gRPC service responsible for processing payments. It takes the payment amount and credit card details, validates the card, and simulates a charge.

This service is written in Node.js. It does not connect to any real payment gateway; instead, it performs basic validation on the credit card number (checking for valid format and accepted types) and expiration date. If the validation passes, it returns a unique transaction ID.

### gRPC Interface

The service is defined by the `PaymentService` interface in the `demo.proto` protobuf file.

```protobuf
service PaymentService {
    rpc Charge(ChargeRequest) returns (ChargeResponse) {}
}

message CreditCardInfo {
    string credit_card_number = 1;
    int32 credit_card_cvv = 2;
    int32 credit_card_expiration_year = 3;
    int32 credit_card_expiration_month = 4;
}

message ChargeRequest {
    Money amount = 1;
    CreditCardInfo credit_card = 2;
}

message ChargeResponse {
    string transaction_id = 1;
}
```

### `Charge` RPC Call

-   **Request**: `ChargeRequest`
    -   `amount`: A `Money` message representing the total amount to be charged.
    -   `credit_card`: The user's credit card information.
-   **Response**: `ChargeResponse`
    -   `transaction_id`: A unique string representing the transaction ID if the charge is successful.

### Validation Logic

The service performs the following checks on the credit card information:
-   The card number must be a valid format.
-   Only VISA and MasterCard are accepted.
-   The expiration date must not be in the past.

If any of these checks fail, the service will return an error.

### Dependencies

This service has no external dependencies on other microservices or databases.

---

## Product Catalog Service

This microservice manages the list of products available in the online boutique.

### Service Description

The Product Catalog Service is a gRPC service that provides information about the products for sale. It allows clients to list all available products, retrieve details for a specific product, and search for products.

This service is written in Go. The product catalog is loaded from a local JSON file (`products.json`) into memory when the service starts. This file contains all the product information, including ID, name, description, picture, price, and categories.

The service also supports the ability to artificially inject latency for testing purposes, which can be configured via the `EXTRA_LATENCY` environment variable.

### gRPC Interface

The service is defined by the `ProductCatalogService` interface in the `demo.proto` protobuf file.

```protobuf
service ProductCatalogService {
    rpc ListProducts(Empty) returns (ListProductsResponse) {}
    rpc GetProduct(GetProductRequest) returns (Product) {}
    rpc SearchProducts(SearchProductsRequest) returns (SearchProductsResponse) {}
}

message Product {
    string id = 1;
    string name = 2;
    string description = 3;
    string picture = 4;
    Money price_usd = 5;
    repeated string categories = 6;
}

message ListProductsResponse {
    repeated Product products = 1;
}

message GetProductRequest {
    string id = 1;
}

message SearchProductsRequest {
    string query = 1;
}

message SearchProductsResponse {
    repeated Product results = 1;
}
```

### `ListProducts` RPC Call

-   **Request**: `Empty`
-   **Response**: `ListProductsResponse` containing a list of all `Product`s.

### `GetProduct` RPC Call

-   **Request**: `GetProductRequest` with a product `id`.
-   **Response**: The requested `Product`.

### `SearchProducts` RPC Call

-   **Request**: `SearchProductsRequest` with a search `query`.
-   **Response**: `SearchProductsResponse` with a list of `Product`s that match the query in their name or description.

### Dependencies

This service has no external dependencies on other microservices or databases. All product data is self-contained.

---

## Recommendation Service

This microservice provides product recommendations to users.

### Service Description

The Recommendation Service is a gRPC service that suggests products to users based on the items they are currently viewing or have in their cart. It works by fetching the entire product catalog and then offering a random selection of products, excluding any that the user has already interacted with in the current context.

This service is written in Python. It is a simple recommendation engine that does not use any machine learning or collaborative filtering.

### gRPC Interface

The service is defined by the `RecommendationService` interface in the `demo.proto` protobuf file.

```protobuf
service RecommendationService {
  rpc ListRecommendations(ListRecommendationsRequest) returns (ListRecommendationsResponse){}
}

message ListRecommendationsRequest {
    string user_id = 1;
    repeated string product_ids = 2;
}

message ListRecommendationsResponse {
    repeated string product_ids = 1;
}
```

### `ListRecommendations` RPC Call

-   **Request**: `ListRecommendationsRequest`
    -   `user_id`: The ID of the user.
    -   `product_ids`: A list of product IDs to be excluded from the recommendations (e.g., items in the cart or the product being viewed).
-   **Response**: `ListRecommendationsResponse`
    -   `product_ids`: A list of recommended product IDs.

### How it Works

1.  The service receives a `ListRecommendations` request, which includes a list of product IDs to exclude.
2.  It makes a gRPC call to the `ProductCatalogService` to get a list of all available products.
3.  It filters out the excluded product IDs from the full list.
4.  It then randomly selects up to 5 products from the remaining list to return as recommendations.

### Dependencies

The Recommendation Service has a dependency on the following microservice:
-   `ProductCatalogService`: to get the list of all products.

---

## Shipping Service

This microservice handles shipping quotes and order shipments.

### Service Description

The Shipping Service is a gRPC service responsible for two main functions: providing a shipping cost estimate for an order and processing the shipment of an order once it has been placed.

This service is written in Go. The current implementation is a mock that provides static responses.

### gRPC Interface

The service is defined by the `ShippingService` interface in the `demo.proto` protobuf file.

```protobuf
service ShippingService {
    rpc GetQuote(GetQuoteRequest) returns (GetQuoteResponse) {}
    rpc ShipOrder(ShipOrderRequest) returns (ShipOrderResponse) {}
}

message GetQuoteRequest {
    Address address = 1;
    repeated CartItem items = 2;
}

message GetQuoteResponse {
    Money cost_usd = 1;
}

message ShipOrderRequest {
    Address address = 1;
    repeated CartItem items = 2;
}

message ShipOrderResponse {
    string tracking_id = 1;
}
```

### `GetQuote` RPC Call

-   **Request**: `GetQuoteRequest`
    -   `address`: The shipping address.
    -   `items`: A list of cart items to be shipped.
-   **Response**: `GetQuoteResponse`
    -   `cost_usd`: The estimated shipping cost in USD. In the current implementation, this is a fixed value and does not depend on the address or the items.

### `ShipOrder` RPC Call

-   **Request**: `ShipOrderRequest`
    -   `address`: The shipping address.
    -   `items`: The list of items to be shipped.
-   **Response**: `ShipOrderResponse`
    -   `tracking_id`: A generated tracking ID for the shipment. The ID is created based on the shipping address but does not correspond to a real shipment.

### How it Works

-   **Quoting**: When a `GetQuote` request is received, the service returns a hardcoded shipping cost.
-   **Shipping**: For a `ShipOrder` request, the service generates a mock tracking ID based on the provided address details.

### Dependencies

This service has no external dependencies on other microservices or databases.

---

## Shopping Assistant Service

This microservice provides an AI-powered shopping assistant that gives product recommendations based on an image of a room and a user's prompt.

### Service Description

The Shopping Assistant Service is an HTTP service that leverages a multimodal Large Language Model (LLM) to provide interior design recommendations. Users can submit an image of a room and a text prompt describing what they are looking for, and the service will return product suggestions from the store's catalog that match the room's style and the user's request.

This service is written in Python and uses the Flask web framework. It integrates with Google's Gemini models for vision and language processing, and with an AlloyDB database for vector-based similarity search.

### How it Works

The service follows a three-step process to generate recommendations:

1.  **Image Analysis**: The service sends the user-provided image to the `gemini-1.5-flash` model with a prompt asking for a detailed description of the room's style. This step effectively translates the visual information into a textual description.

2.  **Similarity Search**: It then combines the room style description with the user's text prompt to create a detailed search query. This query is used to perform a similarity search against a vector database of product embeddings stored in AlloyDB. The database returns a list of products from the catalog that are most relevant to the query.

3.  **Final Recommendation**: The service then constructs a final prompt for the `gemini-1.5-flash` model. This prompt includes the room's style description, the list of relevant products retrieved from the database, and the user's original request. The LLM is instructed to act as an interior designer, providing recommendations based on the provided context and products. The final output is a natural language response with product suggestions, along with a list of the top 3 recommended product IDs.

### API Endpoint

The service exposes a single HTTP POST endpoint at `/`.

-   **Request Body**: A JSON object containing:
    -   `message`: The user's text prompt.
    -   `image`: A URL to the image of the room.
-   **Response Body**: A JSON object with a `content` field containing the LLM's response.

### Dependencies

The Shopping Assistant Service is dependent on several external services and infrastructure components:

-   **Google Gemini LLM**: For image analysis and final recommendation generation.
-   **AlloyDB**: As a vector database to store and search for product embeddings.
-   **Google Secret Manager**: To securely access the AlloyDB database credentials. 