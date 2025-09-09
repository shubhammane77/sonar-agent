"""
AI client for code smell fixing using LangChain with Mistral AI and cost tracking.
"""

import re
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


class AICodeFixer:
    """Handles AI API integration for fixing code smells with cost tracking."""
    
    # Default API endpoints
    DEFAULT_ENDPOINTS = {
        AIProvider.MISTRAL: "https://api.mistral.ai/v1",
        AIProvider.GEMINI: "https://generativelanguage.googleapis.com/v1"
    }
    
    def __init__(self, provider: str = "mistral", api_key: str = None, model: str = None, custom_url: str = None):
        self.provider = AIProvider(provider.lower())
        self.api_key = api_key
        self.mock_mode = self.provider == AIProvider.MOCK or not api_key
        self.custom_url = custom_url
        
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
                    max_tokens=4000,
                    mistral_api_url=api_url
                )
            elif self.provider == AIProvider.GEMINI:
                # For Gemini, handle custom URL if provided and not empty
                if self.custom_url and self.custom_url.strip():
                    print(f"Using custom Gemini API URL: {self.custom_url}")
                    return ChatGoogleGenerativeAI(
                        google_api_key=self.api_key,
                        model=self.model,
                        temperature=0.1,
                        max_output_tokens=4000,
                        endpoint=self.custom_url
                    )
                else:
                    print(f"Using default Gemini API URL: {self.DEFAULT_ENDPOINTS[AIProvider.GEMINI]}")
                    return ChatGoogleGenerativeAI(
                        google_api_key=self.api_key,
                        model=self.model,
                        temperature=0.1,
                        max_output_tokens=4000
                    )
        except Exception as e:
            print(f"Error initializing AI client: {e}")
            print("Falling back to mock mode")
            self.mock_mode = True
            return None
        
        return None
    
    def fix_code_smell(self, smell, file_content: str, prompt_template: str) -> tuple[Optional[str], TokenUsage]:
        """Send code smell to AI and get fixed version with usage tracking."""
        if self.mock_mode:
            return self._mock_ai_response(file_content, smell), TokenUsage()
        
        try:
            prompt = self._create_prompt(smell, file_content, prompt_template)
            return self._call_ai(prompt)
            
        except Exception as e:
            print(f"Error calling AI API: {e}")
            return None, TokenUsage()
    
    def _call_ai(self, prompt: str) -> tuple[Optional[str], TokenUsage]:
        """Call AI via LangChain."""
        messages = [
            SystemMessage(content="You are an expert software engineer specializing in code quality improvements. Fix code smells while maintaining functionality."),
            HumanMessage(content=prompt)
        ]
        
        # Estimate token usage (rough approximation)
        prompt_tokens = self._estimate_tokens(prompt)
        
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
    

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        try:
            # Use tiktoken for rough estimation (GPT-style tokenization)
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except:
            # Fallback: rough approximation (4 chars per token)
            return len(text) // 4
    
    def _create_prompt(self, smell, file_content: str, prompt_template: str) -> str:
        """Create a prompt for the AI to fix the code smell."""
        print('prompt', smell.message)
        print('prompt', file_content)
        print('prompt', prompt_template)
        prompt = prompt_template.format(
            replace_code_smell_lines_here=smell.message,
            replace_full_code_here=file_content
            )
        print('prompt', prompt)
        return prompt
#         return f"""
# Please fix the following code smell in this file:

# **Issue Description:** {smell.message}

# **Current File line to change:**
# ```
# {line_content}
# ```

# **Current File Content:**

# ```
# {file_content}
# ```

# Instructions:
# 1. Fix the code smell while preserving all existing functionality
# 2. Follow best practices for the programming language
# 3. Add comments if the fix needs explanation
# 4. Return the ENTIRE updated file content
# 5. Only send code
# """
    
    def _extract_updated_file(self, ai_response: str) -> Optional[str]:
        """Extract the updated file content from AI response."""
        pattern = r'```java(.*?)```'
        match = re.search(pattern, ai_response, re.DOTALL)
        
        if match:
            return match.group(1).strip()
        else:
            print("Warning: Could not extract updated file from AI response")
            return None
    
    def _mock_ai_response(self, file_content: str, smell) -> str:
        """Mock AI response for demonstration purposes."""
        lines = file_content.split('\n')
        
        # Add a comment indicating the smell was "fixed"
        if smell.start_line <= len(lines):
            comment = f"# FIXED: {smell.message} (Rule: {smell.rule})"
            lines.insert(smell.start_line - 1, comment)
        
        return '\n'.join(lines)
    
    def get_total_usage(self) -> TokenUsage:
        """Get total token usage and cost for the session."""
        return self.total_usage
    
    def reset_usage(self):
        """Reset usage tracking."""
        self.total_usage = TokenUsage()
