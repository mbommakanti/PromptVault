from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProviderSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env",extra="ignore")
    openai_api_key : SecretStr
    openai_timeout_seconds:float = 30.0
    openai_default_model:str="gpt-4o-mini"
    openai_default_temperature:float=0.0
    openai_default_max_tokens:int=300

@lru_cache
def get_settings():
    return ProviderSettings()

