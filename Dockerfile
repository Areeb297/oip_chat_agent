# Dockerfile for OIP Chat Agent
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Ingest documents at build time (optional - can also do at runtime)
# RUN python scripts/ingest_documents.py

# Expose port
EXPOSE 8080

# Run the API server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
