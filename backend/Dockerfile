FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
# Install torch CPU version first (avoids pulling CUDA, saves ~1.5GB)
RUN pip install --no-cache-dir torch==2.1.2+cpu --index-url https://download.pytorch.org/whl/cpu
# Install remaining dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port (Railway will set $PORT)
ENV PORT=8000
EXPOSE $PORT

# Run with uvicorn
CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT
