import os
import time
import re
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

class Agent:
    def __init__(self, name: str, instructions: str, model: str = None, tools: list = None):
        self.name = name
        self.instructions = instructions
        self.model = model
        self.tools = tools or []
        
        api_key = os.environ.get("GEMINI_API_KEY")
        self.api_key = api_key
        print(f"[AGENT INIT] genai imported: {genai is not None}")
        print(f"[AGENT INIT] API key present: {api_key is not None}")
        if api_key:
            print(f"[AGENT INIT] API key value: {api_key[:10]}...")
        if genai and api_key and api_key != "your_gemini_api_key_here":
            # Initialize the modern google-genai client
            self.client = genai.Client(api_key=api_key)
        else:
            self.client = None

    def _extract_retry_delay(self, error_message: str) -> float:
        """Extract retry delay from error message in seconds."""
        # Try to match patterns like "Please retry in 27.02510689s" or "retryDelay": "27s"
        match = re.search(r'Please retry in ([\d.]+)s', error_message)
        if match:
            return float(match.group(1))
        match = re.search(r'"retryDelay":\s*"([\d]+)s"', error_message)
        if match:
            return float(match.group(1))
        # Default to 30 seconds if no delay found
        return 30.0

    def run(self, prompt: str) -> str:
        # Check if the API key has changed dynamically (e.g. from Streamlit reload)
        current_api_key = os.environ.get("GEMINI_API_KEY")
        if current_api_key != self.api_key:
            self.api_key = current_api_key
            print(f"[AGENT UPDATE] API key changed to: {current_api_key[:10] if current_api_key else 'None'}...")
            if genai and current_api_key and current_api_key != "your_gemini_api_key_here":
                self.client = genai.Client(api_key=current_api_key)
            else:
                self.client = None

        if not self.client:
            print("Running in MOCK mode (no API key or google-genai library).")
            if "Parse this syllabus" in prompt:
                return '[{"topic": "Mock Topic", "hours_needed": 2, "exam_date": "2026-10-15"}]'
            return "[]"
            
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Use the specified model
                model_to_use = self.model if self.model else os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
                
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
                error_str = str(e)
                error_details = traceback.format_exc()
                
                # Check if it's a quota/rate limit error (429)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "quota" in error_str.lower():
                    retry_delay = self._extract_retry_delay(error_str)
                    retry_count += 1
                    
                    if retry_count < max_retries:
                        print(f"[RETRY] Quota exceeded. Waiting {retry_delay:.1f}s before retry {retry_count}/{max_retries}...")
                        time.sleep(retry_delay)
                        continue
                    else:
                        print(f"[RETRY] Max retries ({max_retries}) exceeded for quota error.")
                        try:
                            with open("agent_error.log", "w", encoding="utf-8") as f:
                                f.write(error_details)
                        except Exception as write_err:
                            print(f"Failed to write log: {write_err}")
                        print(f"Agent {self.name} encountered quota error after {max_retries} retries: {e}")
                        return f"Error: API quota exceeded. Please try again later or upgrade your plan. Details: {e}"
                else:
                    # Non-quota error, don't retry
                    try:
                        with open("agent_error.log", "w", encoding="utf-8") as f:
                            f.write(error_details)
                    except Exception as write_err:
                        print(f"Failed to write log: {write_err}")
                    print(f"Agent {self.name} encountered an error: {e}")
                    return f"Error running agent: {e}"
        
        return "Error: Max retries exceeded"
