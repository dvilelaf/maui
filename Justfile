set dotenv-load

# Build the Docker image
build:
    docker build -t dvilela/maui:latest .

# Start the Docker container
up: build
    docker compose -f docker-compose-dev.yml up -d

# Stop the Docker container
down:
    docker compose -f docker-compose-dev.yml down

# View Docker logs
logs:
    docker compose -f docker-compose-dev.yml logs -f

# Restart the Docker container
restart: down up

# Push the Docker image
push:
    docker push dvilela/maui

# Build and push
ship: format check security build push

# Deploy to Portainer (Requires .env vars)
deploy: ship
    uv run python src/tools/deploy.py

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

# View Remote Database (via SSH)
# Requires REMOTE_HOST in .env (e.g. REMOTE_HOST=user@server)
remote-db:
    ssh -t $REMOTE_HOST "docker exec -it maui-telegram uv run python src/tools/inspect_db.py"

# View Remote Logs (via SSH)
remote-logs:
    ssh -t $REMOTE_HOST "docker logs -f maui-telegram"

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

# Kill dangling processes on port 8123
kill:
    fuser -k 8123/tcp || true
