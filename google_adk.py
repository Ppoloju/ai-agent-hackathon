import os
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

class Agent:
    def __init__(self, name: str, instructions: str, model: str, tools: list = None):
        self.name = name
        self.instructions = instructions
        self.model = model
        self.tools = tools or []
        
        api_key = os.environ.get("GEMINI_API_KEY")
        if genai and api_key and api_key != "your_gemini_api_key_here":
            # Initialize the modern google-genai client
            self.client = genai.Client(api_key=api_key)
        else:
            self.client = None

    def run(self, prompt: str) -> str:
        if not self.client:
            print("Running in MOCK mode (no API key or google-genai library).")
            if "Parse this syllabus" in prompt:
                return '[{"topic": "Mock Topic", "hours_needed": 2, "exam_date": "2026-10-15"}]'
            return "[]"
            
        try:
            # Use the specified model
            model_to_use = self.model if self.model else "gemini-3.5-flash"
            
            # Prepare configuration
            config_args = {
                "system_instruction": self.instructions,
            }
            if self.tools:
                config_args["tools"] = self.tools
                
            config = types.GenerateContentConfig(**config_args)
            
            # Create a chat session to enable automatic function calling (AFC)
            chat = self.client.chats.create(
                model=model_to_use,
                config=config
            )
            response = chat.send_message(prompt)
            return response.text
        except Exception as e:
            print(f"Agent {self.name} encountered an error: {e}")
            return "[]"
