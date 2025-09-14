"""
Dedicated Mistral AI client for code completion using the Mistral AI API.
"""

import time
import random
import requests
import json
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
import tiktoken


@dataclass
class MistralTokenUsage:
    """Token usage and cost information for Mistral AI."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0


class MistralModel(Enum):
    """Available Mistral AI models."""
    TINY = "mistral-tiny"
    SMALL = "mistral-small-latest"
    MEDIUM = "mistral-medium-latest"
    LARGE = "mistral-large-latest"
    CODESTRAL = "codestral-latest"


class MistralCostCalculator:
    """Calculate costs for Mistral AI models."""
    
    # Mistral AI pricing (per 1K tokens) as of 2024
    PRICING = {
        "mistral-tiny": {"input": 0.00025, "output": 0.00025},
        "mistral-small-latest": {"input": 0.002, "output": 0.006},
        "mistral-medium-latest": {"input": 0.0027, "output": 0.0081},
        "mistral-large-latest": {"input": 0.008, "output": 0.024},
        "codestral-latest": {"input": 0.001, "output": 0.003},
    }
    
    @classmethod
    def calculate_cost(cls, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate cost based on token usage."""
        pricing = cls.PRICING.get(model, cls.PRICING["mistral-small-latest"])
        input_cost = (prompt_tokens / 1000) * pricing["input"]
        output_cost = (completion_tokens / 1000) * pricing["output"]
        return input_cost + output_cost


class MistralAIClient:
    """Dedicated Mistral AI client for code completion and chat."""
    
    def __init__(
        self,
        api_key: str,
        model: str = "mistral-small-latest",
        base_url: str = "https://api.mistral.ai/v1",
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_tokens: int = 4000,
        temperature: float = 0.1
    ):
        """
        Initialize Mistral AI client.
        
        Args:
            api_key: Mistral AI API key
            model: Model to use (default: mistral-small-latest)
            base_url: Mistral AI API base URL
            max_retries: Maximum number of retry attempts
            base_delay: Base delay for exponential backoff
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0.0 to 1.0)
        """
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip('/')
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_tokens = max_tokens
        self.temperature = temperature
        
        self.cost_calculator = MistralCostCalculator()
        self.total_usage = MistralTokenUsage()
        
        # Validate API key
        if not api_key:
            raise ValueError("API key is required for Mistral AI client")
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None
    ) -> tuple[Optional[str], MistralTokenUsage]:
        """
        Generate chat completion using Mistral AI.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            system_prompt: Optional system prompt to prepend
            
        Returns:
            Tuple of (response_content, token_usage)
        """
        # Prepare messages
        formatted_messages = []
        
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})
        
        formatted_messages.extend(messages)
        
        # Estimate input tokens
        prompt_text = " ".join([msg["content"] for msg in formatted_messages])
        prompt_tokens = self._estimate_tokens(prompt_text)
        
        payload = {
            "model": self.model,
            "messages": formatted_messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "stream": False
        }
        
        return self._make_request(payload, prompt_tokens)
    
    def code_completion(
        self,
        code_prompt: str,
        instruction: str = "Fix code smells and improve code quality while maintaining functionality."
    ) -> tuple[Optional[str], MistralTokenUsage]:
        """
        Generate code completion/improvement using Mistral AI.
        
        Args:
            code_prompt: Code to analyze and improve
            instruction: Instruction for the AI
            
        Returns:
            Tuple of (improved_code, token_usage)
        """
        messages = [
            {
                "role": "system",
                "content": "You are an expert software engineer specializing in code quality improvements. " + instruction
            },
            {
                "role": "user",
                "content": code_prompt
            }
        ]
        
        return self.chat_completion(messages)
    
    def _make_request(self, payload: Dict[str, Any], prompt_tokens: int) -> tuple[Optional[str], MistralTokenUsage]:
        """Make API request with retry logic and exponential backoff."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        url = f"{self.base_url}/chat/completions"
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=60
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return self._process_response(data, prompt_tokens)
                else:
                    error_msg = f"API request failed with status {response.status_code}: {response.text}"
                    raise Exception(error_msg)
                    
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries:
                    # Calculate delay with exponential backoff and jitter
                    delay = self.base_delay * (2 ** attempt) + random.uniform(0, 1)
                    print(f"Mistral AI API call failed (attempt {attempt + 1}/{self.max_retries + 1}): {e}")
                    print(f"Retrying in {delay:.2f} seconds...")
                    time.sleep(delay)
                else:
                    print(f"Mistral AI API call failed after {self.max_retries + 1} attempts: {e}")
        
        return None, MistralTokenUsage()
    
    def _process_response(self, data: Dict[str, Any], prompt_tokens: int) -> tuple[str, MistralTokenUsage]:
        """Process API response and extract content and usage."""
        try:
            content = data["choices"][0]["message"]["content"]
            
            # Extract token usage if available
            usage_data = data.get("usage", {})
            completion_tokens = usage_data.get("completion_tokens", self._estimate_tokens(content))
            actual_prompt_tokens = usage_data.get("prompt_tokens", prompt_tokens)
            total_tokens = usage_data.get("total_tokens", actual_prompt_tokens + completion_tokens)
            
            # Calculate cost
            cost = self.cost_calculator.calculate_cost(
                self.model, actual_prompt_tokens, completion_tokens
            )
            
            usage = MistralTokenUsage(
                prompt_tokens=actual_prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost_usd=cost
            )
            
            # Update total usage
            self.total_usage.prompt_tokens += usage.prompt_tokens
            self.total_usage.completion_tokens += usage.completion_tokens
            self.total_usage.total_tokens += usage.total_tokens
            self.total_usage.cost_usd += usage.cost_usd
            
            return content, usage
            
        except (KeyError, IndexError) as e:
            raise Exception(f"Failed to parse API response: {e}")
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        try:
            # Use tiktoken for rough estimation
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except:
            # Fallback: rough approximation (4 chars per token)
            return len(text) // 4
    
    def get_total_usage(self) -> MistralTokenUsage:
        """Get total token usage and cost for the session."""
        return self.total_usage
    
    def reset_usage(self):
        """Reset usage tracking."""
        self.total_usage = MistralTokenUsage()
    
    def get_available_models(self) -> List[str]:
        """Get list of available Mistral models."""
        return [model.value for model in MistralModel]
    
    def set_model(self, model: str):
        """Change the model being used."""
        if model not in self.get_available_models():
            raise ValueError(f"Model {model} not supported. Available models: {self.get_available_models()}")
        self.model = model
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model."""
        pricing = self.cost_calculator.PRICING.get(self.model, {})
        return {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "pricing": pricing,
            "total_usage": self.total_usage
        }
