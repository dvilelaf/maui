from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from src.services.coordinator import Coordinator
from src.utils.schema import TaskStatus, UserStatus
from src.utils.config import Config
import logging

logger = logging.getLogger(__name__)

# Initialize coordinator
_coordinator = None

def get_coordinator():
    global _coordinator
    if _coordinator is None:
        _coordinator = Coordinator()
    return _coordinator


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message when the command /start is issued."""
    user = update.effective_user
    # Ensure user is in DB
    user_db = get_coordinator().user_manager.get_or_create_user(
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

    # Create Web App Button
    kb = [
        [KeyboardButton("Abrir App de Tareas 🌴", web_app=WebAppInfo(url=Config.WEBAPP_URL))]
    ]
    reply_markup = ReplyKeyboardMarkup(kb, resize_keyboard=True)

    await update.message.reply_html(
        f"¡Hola {user.mention_html()}! Soy Maui, tu asistente de tareas inteligente. 🌴\n"
        f"Para gestionar tus tareas y listas, por favor utiliza la <b>Mini App</b> pulsando el botón de abajo.\n\n"
        f"También puedes enviarme mensajes de voz o texto y yo los procesaré.",
        reply_markup=reply_markup
    )


async def webapp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send button to launch the Web App."""
    kb = [[InlineKeyboardButton("Abrir App 🚀", web_app=WebAppInfo(url=Config.WEBAPP_URL))]]
    await update.message.reply_text(
        "Haz clic abajo para abrir la aplicación web:",
        reply_markup=InlineKeyboardMarkup(kb)
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a help message when the command /help is issued."""
    await update.message.reply_text(
        "¡Hola! Para usar Maui, por favor utiliza la Mini App.\n\n"
        "Comandos disponibles:\n"
        "/start - Iniciar el bot y mostrar la botonera\n"
        "/app - Botón directo a la Mini App\n"
        "/help - Mostrar este mensaje\n\n"
        "¡Recuerda que también puedes enviarme notas de voz! 🎙️"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming text messages."""
    user = update.effective_user
    text = update.message.text

    if not text:
        return

    await update.message.reply_chat_action(action="typing")

    response = await get_coordinator().handle_message(
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

    try:
        response = await get_coordinator().handle_message(
            user_id=user.id,
            username=user.username,
            content=bytes(file_bytes),
            is_voice=True,
        )

        await update.message.reply_markdown(response)
    except Exception as e:
        logger.error(f"Error handling voice message: {e}")
        await update.message.reply_text(
            "Lo siento, hubo un error al procesar tu audio. Por favor intenta de nuevo."
        )
