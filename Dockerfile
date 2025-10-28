FROM python:3.12-slim

WORKDIR /app

# Copy everything inside the app directory
COPY app/ app/

# Copy requirement list
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose FastAPI default port
EXPOSE 8080

# Command to start the FastAPI app
CMD ["uvicorn", "app.detector_prototype_fastapi:app", "--host", "0.0.0.0", "--port", "8080"]
