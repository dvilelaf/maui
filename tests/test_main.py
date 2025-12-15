
import pytest
from unittest.mock import MagicMock, call
import sys
from src.main import main, post_init
from src.utils.config import Config

@pytest.mark.asyncio
async def test_post_init():
    app_mock = MagicMock()
    app_mock.bot.set_my_commands = MagicMock()
    # set_my_commands is async, so we need to mock it as an awaitable or AsyncMock
    # If using pytest-mock's mocker?
    # Simple way: app_mock.bot.set_my_commands.return_value = None (if not awaited?)
    # It IS awaited.

    # Let's use AsyncMock
    from unittest.mock import AsyncMock
    from unittest.mock import AsyncMock
    bot_mock = AsyncMock()
    app_mock.bot = bot_mock
    app_mock.bot.set_my_commands = AsyncMock()

    await post_init(app_mock)

    assert app_mock.bot.set_my_commands.called
    args = app_mock.bot.set_my_commands.call_args[0][0]
    assert len(args) == 3
    assert args[0].command == "start"

def test_main_success(mocker):
    mocker.patch.object(Config, "TELEGRAM_TOKEN", "fake_token")
    mocker.patch("src.main.init_db")
    mocker.patch("src.main.create_tables")

    # Chain: Application.builder() -> fluent -> build()
    builder_mock = mocker.patch("telegram.ext.ApplicationBuilder")
    builder_instance = MagicMock()
    app_mock = MagicMock()
    # Make the builder return itself for any attribute access (fluent interface)
    builder_mock.return_value = builder_instance

    # Configure builder instance to return itself for common methods
    builder_instance.token.return_value = builder_instance
    builder_instance.post_init.return_value = builder_instance
    builder_instance.read_timeout.return_value = builder_instance
    builder_instance.write_timeout.return_value = builder_instance
    builder_instance.connect_timeout.return_value = builder_instance

    # Finally build() returns the app mock
    builder_instance.build.return_value = app_mock


    # Run main
    main()

    # Verifications
    # Handlers: start, help, app, handle_message, handle_voice = 5
    assert app_mock.add_handler.call_count >= 1
    app_mock.run_polling.assert_called_once()
    assert app_mock.job_queue.run_daily.call_count == 2
    assert app_mock.job_queue.run_repeating.call_count == 1

def test_main_no_token(mocker, capsys):
    mocker.patch.object(Config, "TELEGRAM_TOKEN", None)
    mocker.patch("src.main.init_db")
    mocker.patch("src.main.create_tables")

    main()

    captured = capsys.readouterr()
    assert "Error: TELEGRAM_TOKEN not found" in captured.out
