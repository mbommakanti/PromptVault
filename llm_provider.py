import random
import time
from functools import lru_cache

from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)

from config import get_settings
from provider_errors import (
    ProviderAuthenticationError,
    ProviderConnectionError,
    ProviderError,
    ProviderInvalidRequestError,
    ProviderRateLimitError,
    ProviderServerError,
    ProviderTimeoutError,
)
from schemas import AdapterResponse


@lru_cache
def get_openai_client():
    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key.get_secret_value(),max_retries=0)
    return client

def _compute_backoff_delay(attempt:int,base:float,cap:float):
    delay = random.uniform(0, min(cap, base * 2 ** (attempt - 1)))
    return delay

def resolve_execution_config(*,model:str|None=None,max_tokens:int|None=None,temperature:float|None=None):
    settings = get_settings()
    model = settings.openai_default_model if model is None else model
    temperature = settings.openai_default_temperature if temperature is None else temperature
    max_tokens = settings.openai_default_max_tokens if max_tokens is None else max_tokens
    resultant_config = (model,temperature,max_tokens)
    return resultant_config

def open_ai_adapter(*,input:str,instructions:str,model:str |None = None,
                    max_tokens:int|None=None,temperature:float|None=None,
                    timeout:float|None=None):
    execution_config = resolve_execution_config(model=model,max_tokens=max_tokens,temperature=temperature)
    open_ai_client = get_openai_client() 
    settings = get_settings()
    try:
        response = open_ai_client.responses.create(
        model = execution_config[0],
        instructions=instructions,
        input = input,
        temperature = execution_config[1],
        max_output_tokens = execution_config[2],
        timeout=settings.openai_timeout_seconds if timeout is None else timeout,
        store=False
        )
    except APITimeoutError as exc:
        raise ProviderTimeoutError(str(exc)) from exc
    except APIConnectionError as exc:
        raise ProviderConnectionError(str(exc)) from exc
    except RateLimitError as exc:
        value = exc.response.headers.get("retry-after")
        if value is None:
            retry_after = None
        else:
            try:
                retry_after = float(value)
            except ValueError:
                retry_after = None
        raise ProviderRateLimitError(message=str(exc),retry_after=retry_after) from exc
    except AuthenticationError as exc:
        raise ProviderAuthenticationError(str(exc)) from exc
    except InternalServerError as exc:
        raise ProviderServerError(str(exc)) from exc
    except APIStatusError as exc:
        raise ProviderInvalidRequestError(str(exc)) from exc
    except APIError as exc:
        raise ProviderError(str(exc)) from exc

    openai_adapter_output = AdapterResponse (
        model_response = response.output_text,
        model_name=response.model,
        response_status=response.status,
        max_tokens=response.max_output_tokens,
        temperature=response.temperature,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        total_tokens=response.usage.total_tokens,
        incomplete_reason=response.incomplete_details.reason if response.incomplete_details else None,
        response_id=response.id
    )

    return openai_adapter_output


def execute_with_retry(*, input, instructions, model=None, max_tokens=None, temperature=None, timeout=None):
    attempt=1
    settings = get_settings()
    max_attempts = settings.openai_retry_max_attempts
    while(attempt<=max_attempts):
        try:
            response = open_ai_adapter(input=input,instructions=instructions,model=model,max_tokens=max_tokens,temperature=temperature,timeout=timeout)
            return response, attempt
        except ProviderError as exc:
            if not exc.retryable or attempt>=max_attempts:
                exc.attempts = attempt
                raise
            else:
                if isinstance(exc,ProviderRateLimitError):
                    if exc.retry_after:
                        delay = min(exc.retry_after,settings.openai_retry_backoff_max_seconds)
                    else:
                        delay = _compute_backoff_delay(attempt,settings.openai_retry_backoff_base_seconds,settings.openai_retry_backoff_max_seconds)
                else:
                    delay = _compute_backoff_delay(attempt,settings.openai_retry_backoff_base_seconds,settings.openai_retry_backoff_max_seconds)
                time.sleep(delay)
                attempt+=1


