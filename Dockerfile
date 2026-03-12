# Use the official PyTorch image to avoid complex CUDA and Python installations
FROM pytorch/pytorch:2.0.1-cuda11.7-cudnn8-runtime

# Set the working directory to /app
WORKDIR /app

# Set environment variables to prevent Python from writing pyc files and to disable pip cache
ENV PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1

# Install required system dependencies (e.g., libGL for OpenCV/image processing)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements to cache them in docker layer
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy the rest of the application code
COPY . .

# Default command to run when starting the container
CMD ["/bin/bash"]
