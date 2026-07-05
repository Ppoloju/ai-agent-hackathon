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
        print(f"[AGENT INIT] genai imported: {genai is not None}")
        print(f"[AGENT INIT] API key present: {api_key is not None}")
        if api_key:
            print(f"[AGENT INIT] API key value: {api_key[:10]}...")
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
            import traceback
            error_details = traceback.format_exc()
            try:
                with open("agent_error.log", "w", encoding="utf-8") as f:
                    f.write(error_details)
            except Exception as write_err:
                print(f"Failed to write log: {write_err}")
            print(f"Agent {self.name} encountered an error: {e}")
            return f"Error running agent: {e}"
