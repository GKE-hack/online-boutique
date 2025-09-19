# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install any production dependencies
COPY src/generic_mcp_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy proto files and generate protobuf
COPY protos/ /protos/
COPY src/generic_mcp_service/genproto.sh .
RUN chmod +x genproto.sh && ./genproto.sh

# Copy the application files into the container at /app
COPY src/generic_mcp_service/main.py .

# Expose the port the app runs on
ENV HTTP_PORT 8080
EXPOSE ${HTTP_PORT}

# Run the application
CMD exec python main.py
