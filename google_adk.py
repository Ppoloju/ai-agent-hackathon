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
            # Fallback to a valid 2.5 model if an old one was passed
            model_to_use = "gemini-2.5-flash"
            response = self.client.models.generate_content(
                model=model_to_use,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=self.instructions,
                )
            )
            return response.text
        except Exception as e:
            print(f"Agent {self.name} encountered an error: {e}")
            return "[]"
