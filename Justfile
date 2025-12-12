set dotenv-load

# Build the Docker image
build:
    docker build -t dvilela/maui:latest .

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
    docker push dvilela/maui

# Build and push
ship: format check security build push

# Formatter & Linter
check:
    uv run ruff check src

security:
    gitleaks detect --source . -v

format:
    uv run ruff format src

# Run locally without Docker
run:
    uv sync
    uv run python src/tools/run_dev.py

# Run the tests
test:
    uv run pytest --cov=src --cov-report=term-missing

# View Database contents
db:
    uv run python src/tools/inspect_db.py

# Whitelist a user
# Whitelist a user (ID, @username, or 'all')
whitelist target:
    uv run python src/tools/admin_tools.py whitelist {{target}}

# Blacklist a user (ID, @username, or 'all')
blacklist target:
    uv run python src/tools/admin_tools.py blacklist {{target}}


# Kick a user (ID or @username)
kick target:
    uv run python src/tools/admin_tools.py kick {{target}}

# Kill dangling processes on port 8000
kill:
    fuser -k 8000/tcp || true
