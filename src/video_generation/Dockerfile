FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY src/video_generation/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy protobuf generation script and run it
COPY protos/ /protos/
COPY src/video_generation/genproto.sh .
RUN chmod +x genproto.sh && ./genproto.sh

# Copy application code
COPY src/video_generation/main.py .
COPY src/video_generation/video_generator.py .

# Create directory for generated videos
RUN mkdir -p /app/videos

# Set environment variables
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

EXPOSE ${PORT}

CMD exec python main.py
