FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv
RUN pip install uv

COPY pyproject.toml ./

# Install dependencies using uv
RUN uv venv && uv pip install -r pyproject.toml

# Copy application code
COPY . .

# Run the bot using the virtual environment
CMD ["/app/.venv/bin/python", "src/main.py"]
