"""
AI client for code smell fixing using LangChain with Mistral AI and cost tracking.
"""

import re
import time
import random
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

from langchain_mistralai import ChatMistralAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import HumanMessage, SystemMessage
import tiktoken


@dataclass
class TokenUsage:
    """Token usage and cost information."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0


class AIProvider(Enum):
    """Supported AI providers."""
    MISTRAL = "mistral"
    GEMINI = "gemini"
    MOCK = "mock"


class CostCalculator:
    """Calculate costs for different AI models."""
    
    # Mistral AI pricing (per 1K tokens) as of 2024
    MISTRAL_PRICING = {
        "mistral-tiny": {"input": 0.00025, "output": 0.00025},
        "mistral-small": {"input": 0.002, "output": 0.006},
        "mistral-medium": {"input": 0.0027, "output": 0.0081},
        "mistral-large": {"input": 0.008, "output": 0.024},
    }
    
    # Google Gemini pricing (per 1K tokens) as of 2024
    GEMINI_PRICING = {
        "gemini-1.5-pro": {"input": 0.00125, "output": 0.005},
        "gemini-1.5-flash": {"input": 0.000075, "output": 0.0003},
        "gemini-2.0-flash": {"input": 0.000075, "output": 0.0003},
    }
    
    @classmethod
    def calculate_cost(cls, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate cost based on token usage."""
        # Check Mistral models first
        if model in cls.MISTRAL_PRICING:
            pricing = cls.MISTRAL_PRICING[model]
        # Check Gemini models
        elif model in cls.GEMINI_PRICING:
            pricing = cls.GEMINI_PRICING[model]
        else:
            # Default to mistral-small pricing if model not found
            pricing = cls.MISTRAL_PRICING["mistral-small"]
        
        input_cost = (prompt_tokens / 1000) * pricing["input"]
        output_cost = (completion_tokens / 1000) * pricing["output"]
        return input_cost + output_cost


class AIClient:
    """Handles AI API integration with cost tracking and retry logic."""
    
    # Default API endpoints
    DEFAULT_ENDPOINTS = {
        AIProvider.MISTRAL: "https://api.mistral.ai/v1",
        AIProvider.GEMINI: "https://generativelanguage.googleapis.com/v1"
    }
    
    def __init__(self, provider: str = "mistral", api_key: str = None, model: str = None, custom_url: str = None, max_retries: int = 3, base_delay: float = 1.0, max_output_tokens: int = 4000):
        self.provider = AIProvider(provider.lower())
        self.api_key = api_key
        self.mock_mode = self.provider == AIProvider.MOCK or not api_key
        self.custom_url = custom_url
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_output_tokens = max_output_tokens
        
        # Set default models based on provider
        if self.provider == AIProvider.MISTRAL:
            self.model = model or "mistral-small"
        elif self.provider == AIProvider.GEMINI:
            self.model = model or "gemini-2.0-flash"
        else:
            self.model = "mock-model"
        
        self.client = self._initialize_client()
        self.cost_calculator = CostCalculator()
        self.total_usage = TokenUsage()
    
    def _initialize_client(self):
        """Initialize the appropriate AI client."""
        if self.mock_mode:
            return None
        
        try:
            if self.provider == AIProvider.MISTRAL:
                # Use custom URL if provided and not empty, otherwise use default
                api_url = self.custom_url if self.custom_url and self.custom_url.strip() else self.DEFAULT_ENDPOINTS[AIProvider.MISTRAL]
                print(f"Using Mistral API URL: {api_url}")
                return ChatMistralAI(
                    api_key=self.api_key,
                    model=self.model,
                    temperature=0.1,
                    max_tokens=self.max_output_tokens,
                    endpoint=api_url
                )
            elif self.provider == AIProvider.GEMINI:
                # For Gemini, handle custom URL if provided and not empty
                if self.custom_url and self.custom_url.strip():
                    print(f"Using custom Gemini API URL: {self.custom_url}")
                    return ChatGoogleGenerativeAI(
                        google_api_key=self.api_key,
                        model=self.model,
                        temperature=0.1,
                        max_output_tokens=self.max_output_tokens,
                        endpoint=self.custom_url
                    )
                else:
                    print(f"Using default Gemini API URL: {self.DEFAULT_ENDPOINTS[AIProvider.GEMINI]}")
                    return ChatGoogleGenerativeAI(
                        google_api_key=self.api_key,
                        model=self.model,
                        temperature=0.1,
                        max_output_tokens=self.max_output_tokens
                    )
        except Exception as e:
            print(f"Error initializing AI client: {e}")
            print("Falling back to mock mode")
            self.mock_mode = True
            return None
        
        return None
    
    def generate_completion(self, prompt: str) -> tuple[Optional[str], TokenUsage]:
        """Generate AI completion for the given prompt with usage tracking."""
        if self.mock_mode:
            return "Mock AI response", TokenUsage()
        
        try:
            return self._call_ai(prompt)
        except Exception as e:
            print(f"Error calling AI API: {e}")
            return None, TokenUsage()
    
    def _call_ai(self, prompt: str) -> tuple[Optional[str], TokenUsage]:
        """Call AI via LangChain with retry logic and exponential backoff."""
        messages = [
            SystemMessage(content="You are an expert software engineer specializing in code quality improvements. Fix code smells while maintaining functionality."),
            HumanMessage(content=prompt)
        ]
        
        # Estimate token usage (rough approximation)
        prompt_tokens = self._estimate_tokens(prompt)
        
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                response = self.client.invoke(messages)
                print('ai response', response)
                completion_tokens = self._estimate_tokens(response.content)
                
                # Calculate cost
                cost = self.cost_calculator.calculate_cost(
                    self.model, prompt_tokens, completion_tokens
                )
                
                usage = TokenUsage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                    cost_usd=cost
                )
                
                # Update total usage
                self.total_usage.prompt_tokens += usage.prompt_tokens
                self.total_usage.completion_tokens += usage.completion_tokens
                self.total_usage.total_tokens += usage.total_tokens
                self.total_usage.cost_usd += usage.cost_usd
                
                fixed_content = self._extract_updated_file(response.content)
                return fixed_content, usage
                
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries:
                    # Calculate delay with exponential backoff and jitter
                    delay = self.base_delay * (2 ** attempt) + random.uniform(0, 1)
                    print(f"AI API call failed (attempt {attempt + 1}/{self.max_retries + 1}): {e}")
                    print(f"Retrying in {delay:.2f} seconds...")
                    time.sleep(delay)
                else:
                    print(f"AI API call failed after {self.max_retries + 1} attempts: {e}")
        
        # If all retries failed, return None with empty usage
        return None, TokenUsage()
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text (public method)."""
        return self._estimate_tokens(text)

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        try:
            # Use tiktoken for rough estimation (GPT-style tokenization)
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except:
            # Fallback: rough approximation (4 chars per token)
            return len(text) // 4
    
    def get_total_usage(self) -> TokenUsage:
        """Get total token usage and cost for the session."""
        return self.total_usage
    
    def reset_usage(self):
        """Reset usage tracking."""
        self.total_usage = TokenUsage()
