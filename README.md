<div align="center">
  <img src="assets/maui.png" alt="Maui Logo" width="50%"/>
  <h1>Maui</h1>
  <p><strong>Your Intelligent Telegram Task Assistant</strong></p>
</div>

---

**Maui** is a smart Telegram bot designed to help you organize your life using natural language. Powered by **Google Gemini**, Maui understands your requests, allowing you to create, edit, and query tasks as if you were talking to a human assistant.

## Features

- **Natural Language Processing**: Add tasks like "Buy milk tomorrow at 5pm" or "Remind me to call Mom on Friday".
- **Intelligent Updates**: Modify existing tasks effortlessly (e.g., "Change the deadline for the bread task to next Monday").
- **Duplicate Prevention**: Automatically detects and warns you if you try to add a duplicate task.
- **Smart Queries**: Ask "What do I have to do today?" or "Show me high priority tasks".
- **Reminders**: Get notified when your tasks are due.
- **Dockerized**: Easy to deploy and manage using Docker Compose.

## Getting Started

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/)
- A Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- A Google Gemini API Key (from [Google AI Studio](https://aistudio.google.com/))
- [Just](https://github.com/casey/just) (Optional, for handy shortcuts)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/dvilela/maui.git
   cd maui
   ```

2. **Configure Environment Variables:**
   Copy the example environment file and fill in your credentials.
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and provide your keys:
   ```conf
   TELEGRAM_TOKEN=your_telegram_bot_token
   GEMINI_API_KEYS=your_gemini_api_key1,your_gemini_api_key2
   DATABASE_URL=maui.db
   LOG_LEVEL=INFO
   ```
   > **Note**: `GEMINI_API_KEYS` accepts a comma-separated list of keys for automatic rotation.

3. **Deploy with Docker:**
   ```bash
   # Using Just
   just up

   # OR using Docker directly
   docker compose up -d
   ```

## Usage

Start a chat with your bot on Telegram and try these commands:

- **Add a task**: "Remind me to submit the report by Friday noon"
- **Query tasks**: "What tasks do I have for this week?"
- **Update a task**: "Mark the report task as done" or "Change priority of buying milk to high"
- **Cancel a task**: "/cancel <task_id>" (or just ask naturally)

## Docker Management

This project includes a `Justfile` to simplify common operations:

| Command | Description |
|---------|-------------|
| `just up` | Start the container in detached mode |
| `just down` | Stop the container |
| `just logs` | View live logs |
| `just build` | Build the Docker image |
| `just push` | Push image to Docker Hub (`dvilela/maui`) |
| `just restart` | Restart the bot |

## Security

- **Secrets**: Environment variables are explicitly passed to the container. The `.env` file is excluded from the build via `.dockerignore`.
- **User Management**: Includes whitelist/blacklist functionality to control who can use the bot.
