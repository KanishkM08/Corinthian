# Use your Python version
FROM python:3.12.4-slim

# Set working directory inside the container
WORKDIR /app

# Install system dependencies for dlib, opencv, and build tools
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    g++ \
    wget \
    unzip \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
 && rm -rf /var/lib/apt/lists/*

# Copy dependencies first for caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code
COPY . .

# Expose Streamlit port
EXPOSE 8501

# Default command to run your dashboard
CMD ["streamlit", "run", "dashboard/app.py", "--server.enableXsrfProtection=false", "--server.port=8501"]
