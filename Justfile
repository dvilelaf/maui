set dotenv-load

# Build the Docker image
build:
    docker compose build

# Start the Docker container
up:
    docker compose up -d

# Stop the Docker container
down:
    docker compose down

# View Docker logs
logs:
    docker compose logs -f

# Restart the Docker container
restart: down up

# Push the Docker image
push:
    docker compose push

# Build and push
ship: build push

# Run locally without Docker
run:
    uv sync
    uv run python src/main.py

# Run the tests
test:
    uv run pytest

# View Database contents
db:
    uv run python src/tools/inspect_db.py
