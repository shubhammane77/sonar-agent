"""
Example usage of the Mistral AI client for code completion and chat.
"""

import os
from mistral_client import MistralAIClient, MistralModel


def example_code_completion():
    """Example of using Mistral AI for code completion/improvement."""
    
    # Initialize client (you'll need to set your API key)
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        print("Please set MISTRAL_API_KEY environment variable")
        return
    
    client = MistralAIClient(
        api_key=api_key,
        model=MistralModel.SMALL.value,  # or "mistral-small-latest"
        temperature=0.1
    )
    
    # Example code with code smells
    code_to_improve = """
def calculate_total(items):
    total = 0
    for i in range(len(items)):
        if items[i] > 0:
            total = total + items[i]
        else:
            pass
    return total

def process_data(data):
    result = []
    for item in data:
        if item != None:
            if item > 10:
                result.append(item * 2)
            else:
                result.append(item)
    return result
"""
    
    prompt = f"""
Please analyze and improve the following Python code by fixing code smells and applying best practices:

{code_to_improve}

Focus on:
1. Removing unnecessary code
2. Improving readability
3. Using more Pythonic approaches
4. Fixing any potential issues

Return only the improved code with brief comments explaining the changes.
"""
    
    print("Sending code to Mistral AI for improvement...")
    improved_code, usage = client.code_completion(prompt)
    
    if improved_code:
        print("\n" + "="*50)
        print("IMPROVED CODE:")
        print("="*50)
        print(improved_code)
        print("\n" + "="*50)
        print("USAGE STATISTICS:")
        print("="*50)
        print(f"Prompt tokens: {usage.prompt_tokens}")
        print(f"Completion tokens: {usage.completion_tokens}")
        print(f"Total tokens: {usage.total_tokens}")
        print(f"Cost: ${usage.cost_usd:.4f}")
    else:
        print("Failed to get response from Mistral AI")


def example_chat_completion():
    """Example of using Mistral AI for general chat completion."""
    
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        print("Please set MISTRAL_API_KEY environment variable")
        return
    
    client = MistralAIClient(
        api_key=api_key,
        model=MistralModel.SMALL.value,
        temperature=0.3
    )
    
    messages = [
        {"role": "user", "content": "Explain the SOLID principles in software engineering with brief examples."}
    ]
    
    system_prompt = "You are a helpful software engineering mentor. Provide clear, concise explanations with practical examples."
    
    print("Asking Mistral AI about SOLID principles...")
    response, usage = client.chat_completion(messages, system_prompt)
    
    if response:
        print("\n" + "="*50)
        print("MISTRAL AI RESPONSE:")
        print("="*50)
        print(response)
        print("\n" + "="*50)
        print("USAGE STATISTICS:")
        print("="*50)
        print(f"Prompt tokens: {usage.prompt_tokens}")
        print(f"Completion tokens: {usage.completion_tokens}")
        print(f"Total tokens: {usage.total_tokens}")
        print(f"Cost: ${usage.cost_usd:.4f}")
    else:
        print("Failed to get response from Mistral AI")


def example_model_management():
    """Example of model management features."""
    
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        print("Please set MISTRAL_API_KEY environment variable")
        return
    
    client = MistralAIClient(api_key=api_key)
    
    print("Available Mistral models:")
    for model in client.get_available_models():
        print(f"  - {model}")
    
    print(f"\nCurrent model info:")
    model_info = client.get_model_info()
    for key, value in model_info.items():
        print(f"  {key}: {value}")
    
    # Change model
    print(f"\nChanging to Codestral model...")
    client.set_model(MistralModel.CODESTRAL.value)
    print(f"New model: {client.model}")


if __name__ == "__main__":
    print("Mistral AI Client Examples")
    print("="*30)
    
    # Run examples
    print("\n1. Code Completion Example:")
    example_code_completion()
    
    print("\n\n2. Chat Completion Example:")
    example_chat_completion()
    
    print("\n\n3. Model Management Example:")
    example_model_management()
