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

# Note: The vector database (chroma_db) needs to be built either during build, 
# at runtime startup, or mapped as a volume.
# To build during image creation, uncomment the following line (will download PDF and build DB):
# RUN python ingest.py

# Expose the port
EXPOSE 8000

# Run the FastAPI application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
