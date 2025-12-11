from telegram import Update
from telegram.ext import ContextTypes
from src.services.coordinator import Coordinator
from src.utils.schema import TaskStatus, UserStatus
import logging

logger = logging.getLogger(__name__)

# Initialize coordinator
coordinator = Coordinator()


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message when the command /start is issued."""
    user = update.effective_user
    # Ensure user is in DB
    user_db = coordinator.user_manager.get_or_create_user(
        user.id, user.username, user.first_name, user.last_name
    )

    if user_db.status == UserStatus.PENDING:
        await update.message.reply_text(
            f"¡Hola {user.first_name}! 👋\n\n"
            "Gracias por registrarte. Tu solicitud de acceso ha sido enviada a los administradores. "
            "Recibirás una notificación cuando tu cuenta sea aprobada."
        )
        return
    elif user_db.status == UserStatus.BLACKLISTED:
        return  # Ignore

    await update.message.reply_html(
        f"¡Hola {user.mention_html()}! Soy Maui, tu asistente de tareas inteligente. 🌴\n"
        f"Simplemente envíame un mensaje (texto o voz) describiendo lo que necesitas hacer, "
        f"y yo lo organizaré por ti."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a help message when the command /help is issued."""
    await update.message.reply_text(
        "¡Puedo ayudarte a gestionar tus tareas!\n\n"
        "Envía un mensaje como:\n"
        "- 'Comprar leche mañana a las 5pm'\n"
        "- 'Llamar a mamá el domingo'\n\n"
        "Comandos:\n"
        "/tasks - Ver tareas pendientes\n"
        "/done <id> - Marcar tarea como completada\n"
        "/cancel <id> - Cancelar una tarea\n"
        "/help - Mostrar este mensaje"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming text messages."""
    user = update.effective_user
    text = update.message.text

    if not text:
        return

    await update.message.reply_chat_action(action="typing")

    response = await coordinator.handle_message(
        user_id=user.id,
        username=user.username,
        content=text,
        is_voice=False,
        first_name=user.first_name,
        last_name=user.last_name,
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

    response = await coordinator.handle_message(
        user_id=user.id,
        username=user.username,
        content=bytes(file_bytes),
        is_voice=True,
    )

    await update.message.reply_markdown(response)


async def list_tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    summary = coordinator.get_task_summary(user.id)
    await update.message.reply_markdown(summary)


async def complete_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        task_id = int(context.args[0])
        if coordinator.task_manager.update_task_status(task_id, TaskStatus.COMPLETED):
            await update.message.reply_text(
                f"✅ ¡Tarea {task_id} marcada como completada!"
            )
        else:
            await update.message.reply_text(
                f"❌ Tarea {task_id} no encontrada o no se pudo actualizar."
            )
    except (IndexError, ValueError):
        await update.message.reply_text("Uso: /done <id_tarea>")


async def cancel_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        task_id = int(context.args[0])
        success = coordinator.task_manager.update_task_status(task_id, "CANCELLED")
        if success:
            await update.message.reply_text(f"🗑️ Tarea {task_id} cancelada.")
        else:
            await update.message.reply_text("❌ Tarea no encontrada.")
    except (IndexError, ValueError):
        await update.message.reply_text("Uso: /cancel <id_tarea>")


async def add_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /add command to create a task directly."""
    user = update.effective_user
    text = " ".join(context.args)

    if not text:
        await update.message.reply_text("Uso: /add <descripción de la tarea>")
        return

    await update.message.reply_chat_action(action="typing")

    response = await coordinator.handle_message(
        user_id=user.id,
        username=user.username,
        content=text,
        is_voice=False,
        first_name=user.first_name,
        last_name=user.last_name,
    )

    await update.message.reply_markdown(response)
