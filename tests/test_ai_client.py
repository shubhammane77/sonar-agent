"""Tests for AI client functionality."""

import pytest
from unittest.mock import Mock, patch
from sonar_agent.ai_client import AICodeFixer, TokenUsage, CostCalculator
from sonar_agent.main import CodeSmell


def test_cost_calculator():
    """Test cost calculation for different models."""
    # Test mistral-small pricing
    cost = CostCalculator.calculate_cost("mistral-small", 1000, 500)
    expected = (1000/1000 * 0.002) + (500/1000 * 0.006)
    assert cost == expected
    
    # Test unknown model defaults to mistral-small
    cost_unknown = CostCalculator.calculate_cost("unknown-model", 1000, 500)
    assert cost_unknown == cost


def test_token_estimation():
    """Test token estimation."""
    fixer = AICodeFixer("mock")
    
    # Test basic estimation
    tokens = fixer._estimate_tokens("Hello world")
    assert tokens > 0
    
    # Longer text should have more tokens
    long_text = "This is a much longer text that should result in more tokens"
    long_tokens = fixer._estimate_tokens(long_text)
    assert long_tokens > tokens


def test_mock_ai_response():
    """Test mock AI response generation."""
    fixer = AICodeFixer("mock")
    
    smell = CodeSmell(
        key="test",
        file_path="test.py",
        message="Test smell",
        start_line=5,
        end_line=5,
        effort="5min",
        debt_minutes=5,
        rule="test-rule",
        severity="MAJOR"
    )
    
    original_content = "line1\nline2\nline3\nline4\nline5\nline6"
    result = fixer._mock_ai_response(original_content, smell)
    
    assert "FIXED: Test smell" in result
    assert "line5" in result


def test_extract_updated_file():
    """Test extraction of updated file from AI response."""
    fixer = AICodeFixer("mock")
    
    ai_response = """
    Here's the fixed code:
    
    <UPDATED_FILE>
    def fixed_function():
        return "fixed"
    </UPDATED_FILE>
    
    This should work better.
    """
    
    result = fixer._extract_updated_file(ai_response)
    assert result == 'def fixed_function():\n        return "fixed"'
    
    # Test case where tags are missing
    bad_response = "No tags here"
    result = fixer._extract_updated_file(bad_response)
    assert result is None


def test_usage_tracking():
    """Test token usage tracking."""
    fixer = AICodeFixer("mock")
    
    # Initial usage should be zero
    usage = fixer.get_total_usage()
    assert usage.total_tokens == 0
    assert usage.cost_usd == 0.0
    
    # Reset should work
    fixer.reset_usage()
    usage = fixer.get_total_usage()
    assert usage.total_tokens == 0
