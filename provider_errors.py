class ProviderError(Exception):
    retryable:bool=False
    status_category:str="unknown_error"

class ProviderTimeoutError(ProviderError):
    retryable:bool=True
    status_category:str="timeout"

class ProviderConnectionError(ProviderError):
    retryable:bool=True
    status_category:str="connection_error"

class ProviderServerError(ProviderError):
    retryable:bool=True
    status_category:str="provider_error"

class ProviderAuthenticationError(ProviderError):
    retryable:bool=False
    status_category:str="auth_error"

class ProviderInvalidRequestError(ProviderError):
    retryable:bool=False
    status_category:str="invalid_request"

class ProviderRateLimitError(ProviderError):
    retryable:bool=True
    status_category:str="rate_limited"

    def __init__(self,message:str,*,retry_after:float|None=None):
        super().__init__(message)
        self.retry_after = retry_after