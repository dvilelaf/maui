
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

    builder_mock = mocker.patch("telegram.ext.Application.builder")
    app_mock = MagicMock()
    builder_mock.return_value.token.return_value.post_init.return_value.build.return_value = app_mock

    # Run main
    main()

    # Verifications
    # Handlers: start, help, app, handle_message, handle_voice = 5
    assert app_mock.add_handler.call_count >= 5
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
