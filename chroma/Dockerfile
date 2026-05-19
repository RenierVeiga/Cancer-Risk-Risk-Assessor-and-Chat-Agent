FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies needed for PyMuPDF and other C-extensions
RUN apt-get update && apt-get install -y \
    build-essential \
    libmupdf-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose the port
EXPOSE 8001

# Download PDF and build the ChromaDB store on container startup, then launch FastAPI
CMD ["sh", "-c", "python ingest.py && uvicorn main:app --host 0.0.0.0 --port 8001"]
