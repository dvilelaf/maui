from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from src.services.coordinator import Coordinator
import logging

logger = logging.getLogger(__name__)

# Initialize coordinator
coordinator = Coordinator()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        f"Hi {user.mention_html()}! I am Maui, your intelligent task assistant. 🌴\n"
        f"Just send me a message (text or voice) describing what you need to do, "
        f"and I'll organize it for you."
    )
    # Ensure user is in DB
    coordinator.user_manager.get_or_create_user(user.id, user.username)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a help message when the command /help is issued."""
    await update.message.reply_text(
        "I can help you manage your tasks!\n\n"
        "Simply send me a message like:\n"
        "- 'Buy milk tomorrow at 5pm'\n"
        "- 'Call mom on Sunday'\n\n"
        "Commands:\n"
        "/tasks - Show pending tasks\n"
        "/done <id> - Mark a task as completed\n"
        "/cancel <id> - Cancel a task\n"
        "/help - Show this message"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming text messages."""
    user = update.effective_user
    text = update.message.text

    if not text:
        return

    await update.message.reply_chat_action(action="typing")

    response = coordinator.handle_message(
        user_id=user.id,
        username=user.username,
        content=text,
        is_voice=False
    )

    await update.message.reply_markdown(response)

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming voice messages."""
    user = update.effective_user
    voice = update.message.voice or update.message.audio

    if not voice:
        return

    await update.message.reply_chat_action(action="typing")

    # Download voice file
    new_file = await context.bot.get_file(voice.file_id)
    file_bytes = await new_file.download_as_bytearray()

    response = coordinator.handle_message(
        user_id=user.id,
        username=user.username,
        content=bytes(file_bytes),
        is_voice=True
    )

    await update.message.reply_markdown(response)

async def list_tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    summary = coordinator.get_weekly_summary(user.id)
    await update.message.reply_markdown(summary)

async def complete_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        task_id = int(context.args[0])
        if coordinator.task_manager.update_task_status(task_id, "COMPLETED"):
            await update.message.reply_text(f"✅ Task {task_id} marked as completed!")
        else:
            await update.message.reply_text(f"❌ Product not found or could not be updated.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /done <task_id>")

async def cancel_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        task_id = int(context.args[0])
        if coordinator.task_manager.update_task_status(task_id, "CANCELLED"):
            await update.message.reply_text(f"🗑️ Task {task_id} cancelled.")
        else:
            await update.message.reply_text(f"❌ Task not found.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /cancel <task_id>")
