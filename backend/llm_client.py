# backend/llm_client.py
 
import os
from typing import Optional
import openai
import time
from typing import Any
from dotenv import load_dotenv
 
load_dotenv()  # Load .env variables
 
 
class LLMClient:
    """
    Unified safe wrapper for Azure OpenAI GPT-4o.
    Provides:
      - text generation
      - safe response extraction
    """
 
    def __init__(self, api_key: Optional[str] = None, model_name: str = "gpt-4o"):
        self.api_key = api_key or os.getenv("AZURE_OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("AZURE_OPENAI_API_KEY is not set")
 
        self.azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        if not self.azure_endpoint:
            raise RuntimeError("AZURE_OPENAI_ENDPOINT is not set")
 
        self.api_version = os.getenv("AZURE_OPENAI_API_VERSION") or "2024-02-01"
        self.deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT") or model_name
 
        self.client = openai.AzureOpenAI(
            api_key=self.api_key,
            azure_endpoint=self.azure_endpoint,
            api_version=self.api_version,
        )
 
    # ----------------------------------------------------------
    # HELPER: safely extract text from OpenAI responses
    # ----------------------------------------------------------
    def _safe_extract_text(self, resp):
        """
        OpenAI returns:
        resp.choices[0].message.content
        """
        try:
            if not resp or not resp.choices or len(resp.choices) == 0:
                return ""
 
            choice = resp.choices[0]
            if not choice.message or not choice.message.content:
                return ""
 
            return choice.message.content.strip()
        except Exception:
            return ""
 
    # ----------------------------------------------------------
    # MAIN GENERATION METHOD
    # ----------------------------------------------------------
    def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        max_tokens: int = 10000,
        temperature: float = 0.0,
        # network/retry options
        retries: int = 3,
        backoff_factor: float = 0.8,
        timeout: Optional[float] = None,
    ) -> str:
 
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction.strip()})
 
        messages.append({"role": "user", "content": prompt.strip()})
 
        print(f"Final messages sent to LLM:\n{messages}\n")
 
        # Attempt generation with retries and exponential backoff.
        last_exc: Optional[Exception] = None
        for attempt in range(1, retries + 1):
            try:
                # Note: the underlying openai client may accept additional timeout options
                # in its config; if available in your environment, you can pass them here.
                resp: Any = self.client.chat.completions.create(
                    model=self.deployment,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    timeout=timeout,
                )
 
                print(f"Raw LLM response: {resp}\n")
                text = self._safe_extract_text(resp)
 
                if text:
                    return text
 
                # If no text returned, treat as an error to allow retry
                last_exc = RuntimeError(f"LLM returned empty text on attempt {attempt}")
            except Exception as e:
                last_exc = e
                # brief log to stdout for local debugging
                print(f"LLM attempt {attempt} failed: {e}")
 
            # backoff before next attempt
            if attempt < retries:
                sleep_time = backoff_factor * (2 ** (attempt - 1))
                time.sleep(sleep_time)
 
        # All attempts failed — raise a clear error for the caller to handle
        raise RuntimeError(f"LLM generation failed after {retries} attempts: {last_exc}")
 
 
# Export singleton
llm = LLMClient()