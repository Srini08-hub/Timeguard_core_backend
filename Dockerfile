FROM python:3.13-slim

# Install uv package manager
RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy pyproject.toml
COPY pyproject.toml .

# Install dependencies using uv
RUN uv pip install --system --no-cache .

# for production
# RUN uv pip install --system --no-cache .

# Copy application code
COPY . .

# Expose port 8001
EXPOSE 8001

# Run the application with uvicorn
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8001"]