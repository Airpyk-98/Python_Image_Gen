# Use a standard Python 3.11 image (Debian-based)
FROM python:3.11-slim

# Install system dependencies needed for libraries
RUN apt-get update && apt-get install -y build-essential

WORKDIR /app

COPY requirements.txt .
# Install all our Python libraries
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render will connect to this port
EXPOSE 10000

# Start the API server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
