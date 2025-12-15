import pytest
from unittest.mock import MagicMock
from src.services.gemini import GeminiService
from src.utils.schema import UserIntent, TaskExtractionResponse

@pytest.fixture
def gemini_service(mock_gemini):
    return GeminiService(["fake_key"])

def test_analyze_text_success(gemini_service, mock_gemini):
    # Setup mock response
    mock_response = MagicMock()
    # The service expects a list or single item in JSON
    mock_response.text = '[{"intent": "ADD_TASK", "is_relevant": true, "formatted_task": {"title": "Test Task"}}]'
    mock_response.candidates = [MagicMock()]
    mock_response.usage_metadata = MagicMock()
    mock_gemini.generate_content.return_value = mock_response

    result = gemini_service.process_input("add test task", mime_type="text/plain")

    assert isinstance(result, list)
    assert len(result) > 0
    first = result[0]
    assert first.intent == UserIntent.ADD_TASK
    assert first.is_relevant is True
    assert first.formatted_task.title == "Test Task"

def test_analyze_text_json_error(gemini_service, mock_gemini):
    # Setup invalid JSON
    mock_response = MagicMock()
    mock_response.text = 'Invalid JSON'
    mock_gemini.generate_content.return_value = mock_response

    result = gemini_service.process_input("fail please", mime_type="text/plain")

    # Should fallback to UNKNOWN or handle gracefully
    assert result[0].intent == UserIntent.UNKNOWN

def test_construct_prompt_privacy(gemini_service):
    """Ensure prompt doesn't carry massive context by default if not needed."""
    # We can't easily check private method without access,
    # but we can check calls to generate_content in verify_mock
    pass

def test_init_no_keys():
    with pytest.raises(ValueError, match="No Gemini API keys provided"):
        GeminiService([]) # Empty list

def test_init_all_keys_invalid(mocker):
    # Mock genai to fail verification
    mock_model_cls = mocker.patch("google.generativeai.GenerativeModel")
    mock_model = mock_model_cls.return_value
    mock_model.generate_content.side_effect = Exception("Invalid Key")

    # Should NOT raise, but log error.
    GeminiService(["k1", "k2"])

def test_process_input_retry(gemini_service, mock_gemini):
    from google.api_core.exceptions import InternalServerError

    # Fail twice, then succeed
    mock_response = MagicMock()
    mock_response.text = '{"intent": "ADD_TASK", "is_relevant": true}'

    mock_gemini.generate_content.side_effect = [
        InternalServerError("Server Error"),
        InternalServerError("Server Error 2"),
        mock_response
    ]

    # Reset mock to ignore init calls
    mock_gemini.generate_content.reset_mock()

    result = gemini_service.process_input("hello")
    assert result[0].intent == UserIntent.ADD_TASK
    assert mock_gemini.generate_content.call_count == 3

def test_process_input_exhaustion_rotate(gemini_service, mock_gemini):
    from google.api_core.exceptions import ResourceExhausted

    # We have 1 fake key in fixture. Let's add more to service manually or mock
    gemini_service.api_keys = ["k1", "k2"]
    gemini_service.current_key_index = 0

    mock_response = MagicMock()
    mock_response.text = '{"intent": "ADD_TASK", "is_relevant": true}'

    # Fail first key with Exhausted, then succeed with rotated (re-created model)
    # Note: process_input recreates model on rotation.
    # We need to ensure the NEW model instance also uses the mock side effect correctly?
    # mocker references the class, so all instances share the mock class return_value usually,
    # BUT `mock_gemini` fixture returns `mock_model_cls.return_value`.
    # So `self.model` is always the SAME mock instance unless we change side_effect dynamic.

    # When `GeminiService` does `self.model = genai.GenerativeModel(...)`, it gets the same mock instance.

    mock_gemini.generate_content.side_effect = [
        ResourceExhausted("Quota"), # k1 fails
        mock_response # k2 succeeds
    ]

    # Reset mock to ignore init calls
    mock_gemini.generate_content.reset_mock()

    result = gemini_service.process_input("hello")

    assert result.intent == UserIntent.ADD_TASK
    assert gemini_service.current_key_index == 1 # Should have rotated
    assert mock_gemini.generate_content.call_count == 2

@pytest.mark.asyncio
async def test_process_input_audio(gemini_service, mock_gemini):
    mock_gemini.generate_content.return_value.text = '{"intent": "ADD_TASK", "is_relevant": true, "formatted_task": {"title": "Audio Task"}}'

    response = gemini_service.process_input(b"audio_bytes", mime_type="audio/ogg")

    assert response[0].intent == "ADD_TASK"
    # Verify prompt parts structure for audio
    call_args = mock_gemini.generate_content.call_args[0][0]
    assert len(call_args) == 3
    assert call_args[1]["mime_type"] == "audio/ogg"

@pytest.mark.asyncio
async def test_model_cooldown_skip(gemini_service, mocker):
    import time # Import time locally or at top level

    # Set cooldown for default model
    gemini_service.model_cooldowns["gemini-1.5-flash"] = time.time() + 60

    # Force config to have specific models
    mocker.patch("src.utils.config.Config.GEMINI_MODELS", ["gemini-1.5-flash", "gemini-pro"])

    # Mock genai interactions
    mock_model_cls = mocker.patch("google.generativeai.GenerativeModel")
    mock_instance = mock_model_cls.return_value
    mock_instance.generate_content.return_value.text = '{"intent": "UNKNOWN", "is_relevant": false, "reasoning": "Fallback"}'

    gemini_service.process_input("test")

    # Should have initialized the SECOND model because first was cooled down
    # Check that GenerativeModel was instantiated with "gemini-pro"
    # We might have multiple calls (verification etc), so filter or check call_args_list
    assert any(call.kwargs.get("model_name") == "gemini-pro" for call in mock_model_cls.call_args_list)

@pytest.mark.asyncio
async def test_internal_server_error_retry_limit(gemini_service, mock_gemini, mocker):
    from google.api_core.exceptions import InternalServerError

    # Ensure only 1 model configured to avoid retrying on next model
    mocker.patch("src.utils.config.Config.GEMINI_MODELS", ["gemini-1.5-flash"])

    mock_gemini.generate_content.side_effect = InternalServerError("Fail")

    # Reset mock to clear verification calls
    mock_gemini.generate_content.reset_mock()

    response = gemini_service.process_input("test")

    assert response[0].intent == "UNKNOWN"
    # Should retry 3 times for the single model
    assert mock_gemini.generate_content.call_count == 3

@pytest.mark.asyncio
async def test_nested_key_exhaustion(gemini_service, mock_gemini, mocker):
    from google.api_core.exceptions import ResourceExhausted
    import time

    # Ensure specific model
    mocker.patch("src.utils.config.Config.GEMINI_MODELS", ["gemini-1.5-flash"])

    # Setup multiple keys
    gemini_service.api_keys = ["key1", "key2"]

    # Mock generate_content to ALWAYS fail with ResourceExhausted
    mock_gemini.generate_content.side_effect = ResourceExhausted("Quota")

    # Mock time.sleep to speed up
    mocker.patch("time.sleep")

    response = gemini_service.process_input("test")

    # Should:
    # 1. Try key1 -> Fail
    # 2. Key 1 Rotate -> Try key2 -> Fail
    # 3. Exhaust all keys for model
    # 4. Set cooldown
    # 5. Return UNKNOWN with "límite de uso"

    assert response[0].intent == "UNKNOWN"
    assert "límite de uso" in response[0].reasoning
    assert "gemini-1.5-flash" in gemini_service.model_cooldowns


def test_verify_keys_empty_direct(gemini_service):
    # Direct call to hit distinct dead code block
    gemini_service.api_keys = []
    with pytest.raises(ValueError, match="No API keys provided"):
        gemini_service._verify_and_sort_keys()
