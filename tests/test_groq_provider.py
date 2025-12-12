
import pytest
from unittest.mock import MagicMock, patch
from src.services.groq_provider import GroqProvider
from src.utils.schema import TaskExtractionResponse, UserIntent

@pytest.fixture
def mock_groq_client():
    with patch("src.services.groq_provider.Groq") as MockGroq:
        client_instance = MockGroq.return_value
        yield client_instance

@pytest.fixture
def groq_provider(mock_groq_client):
    return GroqProvider(api_key="fake_key")

def test_init_no_key():
    with pytest.raises(ValueError, match="API key is required"):
        GroqProvider(api_key=None)

def test_process_input_text(groq_provider, mock_groq_client):
    # Setup mock response for chat
    mock_completion = MagicMock()
    mock_completion.choices[0].message.content = '{"intent": "ADD_TASK", "is_relevant": true, "formatted_task": {"title": "Test Task"}}'
    mock_groq_client.chat.completions.create.return_value = mock_completion

    response = groq_provider.process_input("add task", mime_type="text/plain")

    assert response.intent == UserIntent.ADD_TASK
    assert response.formatted_task.title == "Test Task"

    # Verify call
    mock_groq_client.chat.completions.create.assert_called_once()
    args, kwargs = mock_groq_client.chat.completions.create.call_args
    assert kwargs['response_format'] == {"type": "json_object"}
    assert "add task" in kwargs['messages'][1]['content']

def test_process_input_audio(groq_provider, mock_groq_client):
    # Setup mocks
    # 1. Transcription
    mock_transcription = MagicMock()
    mock_transcription.text = "transcribed text"
    mock_groq_client.audio.transcriptions.create.return_value = mock_transcription

    # 2. Chat
    mock_completion = MagicMock()
    mock_completion.choices[0].message.content = '{"intent": "QUERY_TASKS", "is_relevant": true}'
    mock_groq_client.chat.completions.create.return_value = mock_completion

    audio_data = b"fake_audio"
    response = groq_provider.process_input(audio_data, mime_type="audio/ogg")

    assert response.intent == UserIntent.QUERY_TASKS

    # Verify transcription call
    mock_groq_client.audio.transcriptions.create.assert_called_once()
    call_kwargs = mock_groq_client.audio.transcriptions.create.call_args[1]
    assert call_kwargs['model'] == "whisper-large-v3"

    # Verify chat call used transcription
    mock_groq_client.chat.completions.create.assert_called_once()
    chat_kwargs = mock_groq_client.chat.completions.create.call_args[1]
    assert "transcribed text" in chat_kwargs['messages'][1]['content']

def test_process_input_audio_error(groq_provider, mock_groq_client):
    mock_groq_client.audio.transcriptions.create.side_effect = Exception("Transcribe failed")

    response = groq_provider.process_input(b"bad audio", mime_type="audio/ogg")

    assert response.intent == UserIntent.UNKNOWN
    assert response.is_relevant is False
    assert "Error transcribing" in response.reasoning

def test_process_input_chat_error(groq_provider, mock_groq_client):
    mock_groq_client.chat.completions.create.side_effect = Exception("Chat failed")

    response = groq_provider.process_input("hello", mime_type="text/plain")

    assert response.intent == UserIntent.UNKNOWN
    assert "Error processing text" in response.reasoning
