from telegram import (
    Update,
    WebAppInfo,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from telegram.ext import ContextTypes
from src.services.coordinator import Coordinator
from src.utils.schema import UserStatus
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
        # Notify Admin if configured
        if Config.ADMIN_USER:
            admin_msg = (
                f"🔔 <b>Nueva Solicitud de Acceso</b>\n\n"
                f"Usuario: {user.mention_html()} (ID: {user.id})\n"
                f"Nombre: {user.full_name}\n"
                f"Username: @{user.username if user.username else 'N/A'}"
            )
            kb = [
                [
                    InlineKeyboardButton(
                        "✅ Aprobar", callback_data=f"ADMIN_APPROVE_{user.id}"
                    ),
                    InlineKeyboardButton(
                        "❌ Rechazar", callback_data=f"ADMIN_REJECT_{user.id}"
                    ),
                ]
            ]
            try:
                await context.bot.send_message(
                    chat_id=Config.ADMIN_USER,
                    text=admin_msg,
                    reply_markup=InlineKeyboardMarkup(kb),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error(f"Failed to notify admin: {e}")

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
        [
            KeyboardButton(
                "Abrir App de Tareas 🌴", web_app=WebAppInfo(url=Config.WEBAPP_URL)
            )
        ]
    ]
    reply_markup = ReplyKeyboardMarkup(kb, resize_keyboard=True)

    await update.message.reply_html(
        f"¡Hola {user.mention_html()}! Soy Maui, tu asistente de tareas inteligente. 🌴\n"
        f"Para gestionar tus tareas y listas, por favor utiliza la <b>Mini App</b> pulsando el botón de abajo.\n\n"
        f"También puedes enviarme mensajes de voz o texto y yo los procesaré.",
        reply_markup=reply_markup,
    )


async def webapp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send button to launch the Web App."""
    kb = [
        [
            InlineKeyboardButton(
                "Abrir App 🚀", web_app=WebAppInfo(url=Config.WEBAPP_URL)
            )
        ]
    ]
    await update.message.reply_text(
        "Haz clic abajo para abrir la aplicación web:",
        reply_markup=InlineKeyboardMarkup(kb),
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


async def handle_invite_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Accept/Reject invite callbacks."""
    query = update.callback_query
    await query.answer()

    data = query.data
    # data format: INVITE_ACCEPT_123 or INVITE_REJECT_123

    if not data.startswith("INVITE_"):
        return

    parts = data.split("_")
    action = parts[1]  # ACCEPT or REJECT
    list_id = int(parts[2])
    user_id = update.effective_user.id

    accept = action == "ACCEPT"

    # Process logic
    success, msg = await get_coordinator().task_manager.respond_to_invite(
        user_id, list_id, accept
    )

    # Update the message to remove buttons and show result
    emoji = "✅" if success else "❌"

    new_text = f"{query.message.text}\n\n{emoji} {msg}"
    await query.edit_message_text(text=new_text)


async def handle_admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Admin Accept/Reject callbacks."""
    query = update.callback_query
    await query.answer()

    if update.effective_user.id != Config.ADMIN_USER:
        await query.edit_message_text("No tienes permisos de administrador.")
        return

    data = query.data
    # data format: ADMIN_APPROVE_123 or ADMIN_REJECT_123

    parts = data.split("_")
    action = parts[1]  # APPROVE or REJECT
    target_user_id = int(parts[2])

    user_mgr = get_coordinator().user_manager

    if action == "APPROVE":
        user_mgr.update_status(target_user_id, UserStatus.WHITELISTED)
        result_text = f"Usuario {target_user_id} aprobado ✅"
        # Notify user
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text="🎉 ¡Tu cuenta ha sido aprobada! Ya puedes usar Maui. Envía /start para comenzar.",
            )
        except Exception as e:
            logger.warning(f"Could not notify user {target_user_id}: {e}")

    else:
        user_mgr.update_status(target_user_id, UserStatus.BLACKLISTED)
        result_text = f"Usuario {target_user_id} rechazado ❌"

    await query.edit_message_text(text=f"{query.message.text}\n\n{result_text}")


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List pending users for admin review."""
    user = update.effective_user
    if user.id != Config.ADMIN_USER:
        # Silently ignore or say unauthorized
        await update.message.reply_text("⛔ No tienes permisos de administrador.")
        return

    pending_users = get_coordinator().user_manager.get_pending_users()

    if not pending_users:
        await update.message.reply_text("✅ No hay solicitudes pendientes.")
        return

    await update.message.reply_text(
        f"📋 <b>Solicitudes Pendientes ({len(pending_users)})</b>", parse_mode="HTML"
    )

    for u in pending_users:
        msg = (
            f"👤 <b>Usuario</b>\n"
            f"ID: <code>{u.telegram_id}</code>\n"
            f"Nombre: {u.first_name} {u.last_name or ''}\n"
            f"User: @{u.username or 'N/A'}"
        )
        kb = [
            [
                InlineKeyboardButton(
                    "✅ Aprobar", callback_data=f"ADMIN_APPROVE_{u.telegram_id}"
                ),
                InlineKeyboardButton(
                    "❌ Rechazar", callback_data=f"ADMIN_REJECT_{u.telegram_id}"
                ),
            ]
        ]
        await update.message.reply_text(
            msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML"
        )
