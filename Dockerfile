# Use a standard Python 3.11 image (Debian-based)
FROM python:3.11-slim

# --- THE FIXES ARE HERE ---
# 1. Install system dependencies needed for RDKit and Matplotlib graphics
# 2. Replaced the missing 'libgl1-mesa-glx' with the canonical 'libgl1'
RUN apt-get update && apt-get install -y \
    build-essential \
    libxrender1 \
    libxext6 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
# Install all our Python libraries
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render/DigitalOcean will connect to this port
EXPOSE 10000

# Start the API server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
