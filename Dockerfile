# Lightweight official Python base image
FROM python:3.11-slim

# All subsequent commands run relative to /app inside the container
WORKDIR /app

# Copy dependency list first so Docker can cache this layer
# (rebuilds are fast unless requirements.txt actually changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Now copy the rest of the project
COPY . .

# FastAPI/uvicorn will listen on this port inside the container
EXPOSE 8000

# 0.0.0.0, not 127.0.0.1 - must be reachable from outside the container
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]