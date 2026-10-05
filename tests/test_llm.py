"""Unit and integration tests for Gemini Flash LLM client and RAG Generator."""
from unittest.mock import MagicMock

import pytest

from equity_research.config import get_settings
from equity_research.llm.client import GeminiClient
from equity_research.llm.generator import RAGGenerator


def test_client_initialization():
    settings = get_settings()
    client = GeminiClient()
    assert client.model_name == settings.gemini_model
    if settings.gemini_api_key:
        assert client.is_available is True
    else:
        assert client.is_available is False


def test_format_context():
    generator = RAGGenerator(client=MagicMock())
    retrieved_chunks = [
        {
            "text": "Reliance quarterly revenue grew 12% YoY driven by O2C and Digital Services.",
            "metadata": {
                "title": "Reliance Q3 Earnings Release",
                "source_type": "pdf_deck",
                "published": "2024-01-15",
                "url": "https://example.com/deck.pdf",
            },
            "distance": 0.15,
        }
    ]
    fundamentals = {"market_cap": 20000000000000, "trailing_pe": 25.4}
    price_summary = {"start_close": 2400.0, "end_close": 2900.0}

    context = generator.format_context(
        ticker="RELIANCE",
        retrieved_chunks=retrieved_chunks,
        fundamentals=fundamentals,
        price_summary=price_summary,
    )

    assert "RELIANCE" in context
    assert "Reliance Q3 Earnings Release" in context
    assert "25.4" in context
    assert "2900.0" in context


def test_generate_answer_mocked():
    mock_client = MagicMock()
    mock_client.generate.return_value = (
        "Reliance's revenue grew 12% YoY [Reliance Q3 Earnings Release]."
    )
    generator = RAGGenerator(client=mock_client)

    retrieved_chunks = [
        {
            "text": "Reliance quarterly revenue grew 12% YoY.",
            "metadata": {"title": "Reliance Q3 Earnings Release", "source_type": "pdf_deck"},
        }
    ]

    answer = generator.generate_answer(
        ticker="RELIANCE",
        user_query="What is Reliance's revenue growth?",
        retrieved_chunks=retrieved_chunks,
    )

    assert "12% YoY" in answer
    mock_client.generate.assert_called_once()
    call_kwargs = mock_client.generate.call_args[1]
    assert "What is Reliance's revenue growth?" in call_kwargs["prompt"]


@pytest.mark.integration
def test_live_gemini_integration():
    settings = get_settings()
    if not settings.gemini_api_key:
        pytest.skip("GEMINI_API_KEY not configured, skipping live API test.")

    client = GeminiClient()
    response = client.generate(
        prompt="Explain what PE ratio means in equity research in 15 words or less.",
        temperature=0.1,
    )
    assert isinstance(response, str)
    assert len(response.strip()) > 0
