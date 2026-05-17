FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Ensure data directory exists
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["python", "-c", "import uvicorn; uvicorn.run('app.main:app', host='0.0.0.0', port=8000)"]
