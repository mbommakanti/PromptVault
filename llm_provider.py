from functools import lru_cache

from openai import OpenAI

from config import get_settings
from schemas import AdapterResponse


@lru_cache
def get_openai_client():
    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key.get_secret_value())
    return client


def open_ai_adapter(*,input:str,instructions:str,model:str |None = None,
                    max_tokens:int|None=None,temperature:float|None=None,
                    timeout:float|None=None):
    
    open_ai_client = get_openai_client() 
    settings = get_settings()
    response = open_ai_client.responses.create(
    model = settings.openai_default_model if model is None else model,
    instructions=instructions,
    input = input,
    temperature = settings.openai_default_temperature if temperature is None else temperature,
    max_output_tokens = settings.openai_default_max_tokens if max_tokens is None else max_tokens,
    timeout=settings.openai_timeout_seconds if timeout is None else timeout,
    store=False
    )


    openai_adapter_output = AdapterResponse (
        model_response = response.output_text,
        model_name=response.model,
        response_status=response.status,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        total_tokens=response.usage.total_tokens,
        incomplete_reason=response.incomplete_details.reason if response.incomplete_details else None,
        response_id=response.id
    )

    return openai_adapter_output
    

