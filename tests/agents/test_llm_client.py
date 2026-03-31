"""Tests for llm_client provider detection."""

from unittest.mock import patch

from artifactforge.agents import llm_client


class TestGetProvider:
    """Test get_provider() returns the correct provider based on env config."""

    def test_ollama_takes_priority(self):
        with patch.object(llm_client, "OLLAMA_BASE_URL", "http://localhost:11434"), \
             patch.object(llm_client, "MLX_SERVER_URL", "http://localhost:8080"), \
             patch.object(llm_client, "OPENAI_API_KEY", "sk-test"), \
             patch.object(llm_client, "ANTHROPIC_API_KEY", "sk-ant-test"):
            assert llm_client.get_provider() == "ollama"

    def test_mlx_over_openai(self):
        with patch.object(llm_client, "OLLAMA_BASE_URL", ""), \
             patch.object(llm_client, "MLX_SERVER_URL", "http://localhost:8080"), \
             patch.object(llm_client, "OPENAI_API_KEY", "sk-test"), \
             patch.object(llm_client, "ANTHROPIC_API_KEY", "sk-ant-test"):
            assert llm_client.get_provider() == "mlx"

    def test_openrouter_when_base_url_is_openrouter(self):
        with patch.object(llm_client, "OLLAMA_BASE_URL", ""), \
             patch.object(llm_client, "MLX_SERVER_URL", ""), \
             patch.object(llm_client, "OPENAI_API_KEY", "sk-or-test"), \
             patch.object(llm_client, "OPENAI_API_BASE", "https://openrouter.ai/api/v1"):
            assert llm_client.get_provider() == "openrouter"

    def test_openai_when_base_url_is_openai(self):
        with patch.object(llm_client, "OLLAMA_BASE_URL", ""), \
             patch.object(llm_client, "MLX_SERVER_URL", ""), \
             patch.object(llm_client, "OPENAI_API_KEY", "sk-test"), \
             patch.object(llm_client, "OPENAI_API_BASE", "https://api.openai.com/v1"):
            assert llm_client.get_provider() == "openai"

    def test_openai_when_base_url_is_custom(self):
        with patch.object(llm_client, "OLLAMA_BASE_URL", ""), \
             patch.object(llm_client, "MLX_SERVER_URL", ""), \
             patch.object(llm_client, "OPENAI_API_KEY", "sk-test"), \
             patch.object(llm_client, "OPENAI_API_BASE", "https://my-proxy.example.com/v1"):
            assert llm_client.get_provider() == "openai"

    def test_anthropic_fallback(self):
        with patch.object(llm_client, "OLLAMA_BASE_URL", ""), \
             patch.object(llm_client, "MLX_SERVER_URL", ""), \
             patch.object(llm_client, "OPENAI_API_KEY", None), \
             patch.object(llm_client, "ANTHROPIC_API_KEY", "sk-ant-test"):
            assert llm_client.get_provider() == "anthropic"

    def test_mock_when_nothing_configured(self):
        with patch.object(llm_client, "OLLAMA_BASE_URL", ""), \
             patch.object(llm_client, "MLX_SERVER_URL", ""), \
             patch.object(llm_client, "OPENAI_API_KEY", None), \
             patch.object(llm_client, "ANTHROPIC_API_KEY", None):
            assert llm_client.get_provider() == "mock"
