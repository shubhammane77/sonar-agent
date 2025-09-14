"""
Code smell processor for handling prompt formatting and validation.
"""

import re
from typing import Optional
from .sonar_client import CodeSmell


class CodeSmellProcessor:
    """Handles code smell prompt formatting and validation."""
    
    def __init__(self, max_output_tokens: int = 4000):
        self.max_output_tokens = max_output_tokens
    def create_prompt(self, smell: CodeSmell, file_content: str, prompt_template: str) -> str:
        """Create a formatted prompt for the AI to fix the code smell."""
        prompt = prompt_template.replace(
            "{{replace_code_smell_lines_here}}", smell.message
        ).replace(
            "{{replace_full_code_here}}", file_content
        )
        
        # Replace additional placeholders if they exist in the template
        # prompt = prompt.replace("{rule}", smell.rule)
        # prompt = prompt.replace("{message}", smell.message)
        # prompt = prompt.replace("{severity}", smell.severity)
        # prompt = prompt.replace("{start_line}", str(smell.start_line))
        # prompt = prompt.replace("{end_line}", str(smell.end_line))
        # prompt = prompt.replace("{code}", file_content)
        
        return prompt
    
    def validate_file_size(self, file_content: str, estimate_tokens_func) -> Optional[str]:
        """Validate if file content exceeds token limits."""
        file_tokens = estimate_tokens_func(file_content)
        if file_tokens > self.max_output_tokens:
            return f"File is too large ({file_tokens} tokens) for model output limit ({self.max_output_tokens} tokens)"
        return None
    
    def validate_prompt_size(self, prompt: str, estimate_tokens_func) -> Optional[str]:
        """Validate if prompt exceeds token limits."""
        prompt_tokens = estimate_tokens_func(prompt)
        if prompt_tokens > (self.max_output_tokens * 2):  # Allow 2x for input vs output
            return f"Prompt is too large ({prompt_tokens} tokens)"
        return None
    
    def extract_updated_file(self, ai_response: str) -> Optional[str]:
        """Extract the updated file content from AI response."""
        # Try to extract code from markdown code blocks
        patterns = [
            r'```java(.*?)```',
            r'```python(.*?)```',
            r'```javascript(.*?)```',
            r'```typescript(.*?)```',
            r'```cpp(.*?)```',
            r'```c\+\+(.*?)```',
            r'```csharp(.*?)```',
            r'```go(.*?)```',
            r'```rust(.*?)```',
            r'```php(.*?)```',
            r'```ruby(.*?)```',
            r'```scala(.*?)```',
            r'```kotlin(.*?)```',
            r'```swift(.*?)```',
            r'```(.*?)```'  # Generic code block as fallback
        ]
        
        for pattern in patterns:
            match = re.search(pattern, ai_response, re.DOTALL)
            if match:
                return match.group(1).strip()
        
        # If no code blocks found, return the entire response (might be plain code)
        # But first check if it looks like code vs explanation
        lines = ai_response.strip().split('\n')
        if len(lines) > 1 and not any(line.lower().startswith(('here', 'the', 'i ', 'this')) for line in lines[:3]):
            return ai_response.strip()
        
        return None
    
    def create_mock_response(self, file_content: str, smell: CodeSmell) -> str:
        """Create a mock response for testing purposes."""
        lines = file_content.split('\n')
        
        # Add a comment indicating the smell was "fixed"
        if smell.start_line <= len(lines):
            comment = f"# FIXED: {smell.message} (Rule: {smell.rule})"
            lines.insert(smell.start_line - 1, comment)
        
        return '\n'.join(lines)
