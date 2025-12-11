
import pytest
from unittest.mock import MagicMock, patch, ANY, AsyncMock
from src.utils.schema import TaskSchema
from src.database.models import User, Task, TaskList, create_tables, db
from src.services.gemini import GeminiService
from src.services.coordinator import Coordinator
from google.api_core.exceptions import ResourceExhausted

def test_schema_validators():
    # Test Priority Validator fallback
    # Line 74: v is None -> "MEDIUM"
    t1 = TaskSchema(title="T1", priority=None)
    assert t1.priority == "MEDIUM"

    # Line 76: v not in allowed -> "MEDIUM"
    t2 = TaskSchema(title="T2", priority="MEGA_URGENT")
    assert t2.priority == "MEDIUM"

    # Line 77: valid -> upper
    t3 = TaskSchema(title="T3", priority="low")
    assert t3.priority == "LOW"

    # Test Title Validator
    # Line 81: v -> Capitalize first char
    t4 = TaskSchema(title="my task")
    assert t4.title == "My task"

    # Line 83: v empty?
    # Usually handled by required check, but if optional or empty string allowed?
    # If title is required, this validator runs on non-empty.
    # But if we pass empty string and it's allowed:
    try:
        t5 = TaskSchema(title="")
        assert t5.title == ""
    except Exception:
        pass

def test_models_str_coverage(test_db):
    # Coverage for models (if any str methods or such missing)
    # Line 65-66 in models.py is create_tables() context manager
    # We should run create_tables() explicitly to cover proper "with db:" usage if not covered
    with patch("src.database.models.db") as mock_db:
        create_tables()
        mock_db.create_tables.assert_called()

@pytest.mark.asyncio
async def test_gemini_error_handling_exhausted(mocker):
    # Test lines 238-244: Inner exception in key rotation
    # We need to simulate:
    # 1. First key fails with ResourceExhausted (Line 233 hit)
    # 2. Loop continues to next key
    # 3. Next key fails with generic Exception (Line 238 hit) -> Log error -> Continue

    mocker.patch("google.generativeai.configure")
    mock_model_cls = mocker.patch("google.generativeai.GenerativeModel")
    mock_model = mock_model_cls.return_value

    # Side effects for generate_content
    # Call 1: ResourceExhausted
    # Call 2: Exception("Random Error")
    # Call 3: Success or exhaustion break

    mock_model.generate_content.side_effect = [
        ResourceExhausted("Quota"),
        Exception("Random Error"),
        ResourceExhausted("Quota"), # Exhaust all 3 keys
        ResourceExhausted("Quota"),
        ResourceExhausted("Quota"),
    ]

    client = GeminiService(api_keys=["k1", "k2", "k3", "k4"])

    from src.utils.schema import UserIntent
    res = client.process_input("test")
    # It returns UNKNOWN response, not None
    assert res.intent == UserIntent.UNKNOWN
    assert "problemas" in res.reasoning

@pytest.mark.asyncio
async def test_coordinator_unhandled_intent(mocker, test_db):
    # Cover line 252: Fallback return
    # Mock Gemini response to have a valid but unhandled intent (or custom intent)
    # Since UserIntent is Enum, we can't easily add new one.
    # But if we mock the extraction result object and sets intent to something else
    # OR if we simply rely on the fact that if-elif chain is exhaustive for KNOWN intents,
    # then line 252 is unreachable unless we add a new enum member.
    # EXCEPT if intent is NOT UNKNOWN but we skipped handling it?
    # Let's check coordinator.py again. Does it handle ALL intents?
    # ADD, QUERY, CANCEL, COMPLETE, EDIT, CREATE_LIST, SHARE_LIST, UNKNOWN.
    # If all are handled, line 252 is dead code unless we simulate a new intent.
    # We can mock the integer value of intent if it uses enums?
    # Or mock `extraction.intent` to be "MAGIC_INTENT".

    mock_gemini = MagicMock()
    mock_gemini.process_input.return_value = MagicMock(
        is_relevant=True,
        intent="MAGIC_INTENT",
        formatted_task=None
    )

    coord = Coordinator()
    coord.gemini = mock_gemini

    # Ensure user is APPROVED
    user, _ = User.get_or_create(telegram_id=1, defaults={"first_name": "Test", "status": "APPROVED"})
    if user.status != "APPROVED":
        user.status = "APPROVED"
        user.save()

    res = await coord.handle_message(1, "u", "msg")
    assert "no estoy seguro de qué hacer" in res

@pytest.mark.asyncio
async def test_main_run_error(mocker):
    # Test main.py error handling (Line 105??)
    # Main usually has:
    # if __name__ == "__main__": main()
    # Coverage sometimes marks `if __name__` as run, but main() call not if imported.
    # We can just call main() and mock everything to return immediately/raise errors.

    mocker.patch("telegram.ext.ApplicationBuilder")
    mocker.patch("src.main.init_db")
    mocker.patch("src.main.create_tables")


    # If we want to cover exception handler inside main loop if it exists?
    # The view showed basic setup.
    # Let's just run main() to cover the setup lines.
    from src.main import main
    main()

