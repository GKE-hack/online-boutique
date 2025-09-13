/**
 * Copyright 2024 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

/**
 * Example JavaScript code for integrating the chatbot service with the frontend
 * This code can be added to the frontend application to enable chatbot functionality
 */

class ChatbotClient {
    constructor(chatbotServiceUrl = '/api/chatbot') {
        this.serviceUrl = chatbotServiceUrl;
        this.conversationHistory = [];
    }

    /**
     * Send a message to the chatbot and get a response
     * @param {string} message - The user's message
     * @returns {Promise<Object>} - The chatbot's response
     */
    async sendMessage(message) {
        try {
            const response = await fetch(`${this.serviceUrl}/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: message,
                    history: this.conversationHistory.slice(-10) // Keep last 10 messages
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            
            // Update conversation history
            this.conversationHistory.push(`User: ${message}`);
            this.conversationHistory.push(`Assistant: ${data.response}`);

            return data;
        } catch (error) {
            console.error('Error communicating with chatbot:', error);
            return {
                success: false,
                response: "I'm sorry, I'm having trouble right now. Please try again later.",
                recommended_products: [],
                total_products_considered: 0
            };
        }
    }

    /**
     * Clear the conversation history
     */
    clearHistory() {
        this.conversationHistory = [];
    }

    /**
     * Get the current conversation history
     * @returns {Array<string>} - The conversation history
     */
    getHistory() {
        return [...this.conversationHistory];
    }
}

/**
 * Example chatbot UI component
 */
class ChatbotUI {
    constructor(containerId, chatbotClient) {
        this.container = document.getElementById(containerId);
        this.chatbot = chatbotClient;
        this.initializeUI();
    }

    initializeUI() {
        this.container.innerHTML = `
            <div class="chatbot-widget">
                <div class="chatbot-header">
                    <h3>Shopping Assistant</h3>
                    <button id="chatbot-minimize">−</button>
                </div>
                <div class="chatbot-messages" id="chatbot-messages">
                    <div class="bot-message">
                        Hi! I'm your shopping assistant. I can help you find products, answer questions about our catalog, and make recommendations. What are you looking for today?
                    </div>
                </div>
                <div class="chatbot-input">
                    <input type="text" id="chatbot-input" placeholder="Ask me about products..." />
                    <button id="chatbot-send">Send</button>
                </div>
            </div>
        `;

        this.setupEventListeners();
    }

    setupEventListeners() {
        const input = document.getElementById('chatbot-input');
        const sendButton = document.getElementById('chatbot-send');
        const minimizeButton = document.getElementById('chatbot-minimize');

        sendButton.addEventListener('click', () => this.sendMessage());
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.sendMessage();
            }
        });

        minimizeButton.addEventListener('click', () => this.toggleMinimize());
    }

    async sendMessage() {
        const input = document.getElementById('chatbot-input');
        const message = input.value.trim();
        
        if (!message) return;

        // Add user message to UI
        this.addMessage(message, 'user');
        input.value = '';

        // Show typing indicator
        this.showTyping();

        try {
            const response = await this.chatbot.sendMessage(message);
            
            // Remove typing indicator
            this.hideTyping();

            // Add bot response to UI
            this.addMessage(response.response, 'bot');

            // If there are recommended products, show them
            if (response.recommended_products && response.recommended_products.length > 0) {
                this.showRecommendedProducts(response.recommended_products);
            }

        } catch (error) {
            this.hideTyping();
            this.addMessage("I'm sorry, I encountered an error. Please try again.", 'bot');
        }
    }

    addMessage(message, sender) {
        const messagesContainer = document.getElementById('chatbot-messages');
        const messageDiv = document.createElement('div');
        messageDiv.className = `${sender}-message`;
        messageDiv.textContent = message;
        messagesContainer.appendChild(messageDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    showTyping() {
        const messagesContainer = document.getElementById('chatbot-messages');
        const typingDiv = document.createElement('div');
        typingDiv.id = 'typing-indicator';
        typingDiv.className = 'bot-message typing';
        typingDiv.innerHTML = 'Thinking... <span class="typing-dots">...</span>';
        messagesContainer.appendChild(typingDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    hideTyping() {
        const typingIndicator = document.getElementById('typing-indicator');
        if (typingIndicator) {
            typingIndicator.remove();
        }
    }

    showRecommendedProducts(productIds) {
        // This would integrate with the existing product display logic
        // For example, highlight these products on the current page
        productIds.forEach(productId => {
            const productElement = document.querySelector(`[data-product-id="${productId}"]`);
            if (productElement) {
                productElement.classList.add('recommended');
                // You could also scroll to the product or open its details
            }
        });

        // Or create a dedicated recommendations section
        this.addMessage(`💡 I recommend checking out these products: ${productIds.join(', ')}`, 'bot');
    }

    toggleMinimize() {
        const widget = this.container.querySelector('.chatbot-widget');
        widget.classList.toggle('minimized');
    }
}

/**
 * Example CSS styles for the chatbot widget
 * Add this to your main CSS file
 */
const chatbotStyles = `
.chatbot-widget {
    position: fixed;
    bottom: 20px;
    right: 20px;
    width: 350px;
    height: 500px;
    background: white;
    border: 1px solid #ddd;
    border-radius: 10px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.15);
    display: flex;
    flex-direction: column;
    z-index: 1000;
}

.chatbot-widget.minimized {
    height: 60px;
}

.chatbot-widget.minimized .chatbot-messages,
.chatbot-widget.minimized .chatbot-input {
    display: none;
}

.chatbot-header {
    background: #4285f4;
    color: white;
    padding: 15px;
    border-radius: 10px 10px 0 0;
    display: flex;
    justify-content: between;
    align-items: center;
}

.chatbot-header h3 {
    margin: 0;
    flex-grow: 1;
}

.chatbot-header button {
    background: none;
    border: none;
    color: white;
    font-size: 20px;
    cursor: pointer;
}

.chatbot-messages {
    flex-grow: 1;
    padding: 15px;
    overflow-y: auto;
    background: #f9f9f9;
}

.user-message, .bot-message {
    margin: 10px 0;
    padding: 10px;
    border-radius: 10px;
    max-width: 80%;
}

.user-message {
    background: #4285f4;
    color: white;
    margin-left: auto;
    text-align: right;
}

.bot-message {
    background: white;
    border: 1px solid #ddd;
}

.bot-message.typing {
    font-style: italic;
    color: #666;
}

.typing-dots {
    animation: typing 1.5s infinite;
}

@keyframes typing {
    0%, 60%, 100% { opacity: 1; }
    30% { opacity: 0.5; }
}

.chatbot-input {
    display: flex;
    padding: 15px;
    border-top: 1px solid #ddd;
}

.chatbot-input input {
    flex-grow: 1;
    padding: 10px;
    border: 1px solid #ddd;
    border-radius: 5px;
    margin-right: 10px;
}

.chatbot-input button {
    background: #4285f4;
    color: white;
    border: none;
    padding: 10px 20px;
    border-radius: 5px;
    cursor: pointer;
}

.recommended {
    border: 2px solid #4285f4 !important;
    box-shadow: 0 0 10px rgba(66, 133, 244, 0.3);
}
`;

/**
 * Initialize the chatbot when the page loads
 */
document.addEventListener('DOMContentLoaded', function() {
    // Add styles to the page
    const styleSheet = document.createElement('style');
    styleSheet.textContent = chatbotStyles;
    document.head.appendChild(styleSheet);

    // Create a container for the chatbot
    const chatbotContainer = document.createElement('div');
    chatbotContainer.id = 'chatbot-container';
    document.body.appendChild(chatbotContainer);

    // Initialize the chatbot
    const chatbotClient = new ChatbotClient('/api/chatbot');
    const chatbotUI = new ChatbotUI('chatbot-container', chatbotClient);

    // Make chatbot globally available for debugging
    window.chatbot = { client: chatbotClient, ui: chatbotUI };
});

/**
 * Example of how to integrate with product pages
 */
function initializeProductPageIntegration() {
    // Add a "Ask about this product" button to product pages
    const productDetails = document.querySelector('.product-details');
    if (productDetails) {
        const askButton = document.createElement('button');
        askButton.textContent = 'Ask about this product';
        askButton.className = 'ask-chatbot-btn';
        askButton.onclick = function() {
            const productName = document.querySelector('.product-name')?.textContent;
            if (productName && window.chatbot) {
                window.chatbot.client.sendMessage(`Tell me more about the ${productName}`);
            }
        };
        productDetails.appendChild(askButton);
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { ChatbotClient, ChatbotUI };
} 