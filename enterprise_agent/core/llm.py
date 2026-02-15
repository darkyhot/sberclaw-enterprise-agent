"""LLM client setup for the enterprise agent."""

from langchain_gigachat.chat_models import GigaChat


def build_model(credentials: str):
    """Create and return a configured GigaChat model instance."""
    return GigaChat(
        credentials=credentials,
        scope="GIGACHAT_API_PERS",
        model="GigaChat-Pro",
        verify_ssl_certs=False,
    )
