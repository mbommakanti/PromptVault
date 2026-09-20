import time

from fastapi import APIRouter, Depends, HTTPException, Path
from starlette import status

from auth import db_dependency, get_current_user
from llm_provider import execute_with_retry, resolve_execution_config
from models import Execution, Prompt, PromptVersion, User
from provider_errors import ProviderError
from schemas import ExecutionOut, ExecutionRequest

http_status_mapping = {
    "timeout":(504,"the model provider took too long to respond"),
    "connection_error":(503, "could not reach the model provider"),
    "rate_limited":(503, "the model provider is temporarily rate-limiting requests"),
    "auth_error":(503, "the model provider is currently unavailable"),
    "provider_error":(502,"the model provider is currently unavailable"),
    "invalid_request":(422, "the request was rejected by the model provider"),
    "unknown_error":(502, "an unexpected error occurred contacting the model provider")
}

def build_execution_object(*,user_id,prompt_id,prompt_version_id,model_name,temperature,max_tokens,input,output,status,incomplete_reason,
                           input_tokens,output_tokens,total_tokens,provider_response_id,latency_ms,retry_attempts:int=1,error_message):
     execution_object = Execution(
        user_id = user_id,
        prompt_id = prompt_id,
        prompt_version_id=prompt_version_id,
        model_name=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
        input=input,
        output=output,
        status=status,
        incomplete_reason=incomplete_reason,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        provider_response_id=provider_response_id,
        retry_attempts=retry_attempts,
        latency_ms=latency_ms,
        error_message=error_message
     )
     return execution_object

router = APIRouter(prefix="/api/v1/prompts", tags=["executions"])
execution_router = APIRouter(prefix="/api/v1/executions",tags=["executions"])

@router.post("/{prompt_id}/versions/{version_number}/execute",response_model=ExecutionOut,status_code=status.HTTP_201_CREATED)
def execute_llm_provider(db:db_dependency,execution_request:ExecutionRequest,current_user:User=Depends(get_current_user),
                         prompt_id:int=Path(gt=0),version_number:int=Path(gt=0)):
    print("Inside execute_llm_provider")
    owner_exception = HTTPException(
                status_code=403,
                detail="Unauthorized access, the prompt you are trying to retrieve belongs to a different owner or is not published"
            )
    prompt_not_found_exception = HTTPException(
            status_code=404,
            detail="There is no prompt that exists in the Database with the ID provided"
        )
    prompt = db.query(Prompt).filter(
            (Prompt.id==prompt_id) & (Prompt.deleted_at.is_(None))
    ).first()
    if not prompt:
        raise prompt_not_found_exception
   
    if prompt.owner_id!=current_user.id and prompt.is_published==False:
           raise owner_exception
   
    prompt_version = db.query(PromptVersion).filter(
           (PromptVersion.prompt_id == prompt_id) & (PromptVersion.version_number == version_number)
    ).first()
    
    if not prompt_version:
           raise HTTPException(status_code=404,detail="The prompt version you are trying to fetch does not exist")

    latency_ms=0
    try:
        start = time.perf_counter()
        adapter_response, number_of_attempts = execute_with_retry(input=execution_request.input,instructions=prompt_version.content,model=execution_request.model,
                                           max_tokens = execution_request.max_tokens,temperature=execution_request.temperature
                                         )
        elapsed_time = time.perf_counter()-start
        latency_ms = round(elapsed_time*1000)
    except ProviderError as exc:
         model_config = resolve_execution_config(model=execution_request.model,max_tokens=execution_request.max_tokens,temperature=execution_request.temperature)
         status_category = exc.status_category
         attempts = exc.attempts
         failed_execution_object = build_execution_object(
              user_id=current_user.id,prompt_id=prompt_id,prompt_version_id=prompt_version.id,model_name=model_config[0],temperature=model_config[1],max_tokens=model_config[2],
              input=execution_request.input,output=None,status=status_category,
              incomplete_reason=None,input_tokens=None,output_tokens=None,total_tokens=None,provider_response_id=None,retry_attempts=attempts,latency_ms=latency_ms,error_message=str(exc)
         )
         db.add(failed_execution_object)
         db.commit()
         db.refresh(failed_execution_object)
         http_status_code, detail_message = http_status_mapping.get(status_category,(502, "an unexpected error occurred contacting the model provider"))
         raise HTTPException(status_code=http_status_code,detail=detail_message)
    else:
        execution_request_to_create= build_execution_object(user_id=current_user.id,prompt_id=prompt_id,prompt_version_id=prompt_version.id,model_name=adapter_response.model_name,
                                                            temperature=adapter_response.temperature,max_tokens=adapter_response.max_tokens,input=execution_request.input,
                                                            output=adapter_response.model_response,status=adapter_response.response_status,
                                                            incomplete_reason=adapter_response.incomplete_reason,input_tokens=adapter_response.input_tokens,
                                                            output_tokens=adapter_response.output_tokens,total_tokens=adapter_response.total_tokens,provider_response_id=adapter_response.response_id,
                                                            latency_ms=latency_ms,retry_attempts=number_of_attempts,error_message=None)
        db.add(execution_request_to_create)
        db.commit()
        db.refresh(execution_request_to_create)  
           
    return execution_request_to_create

@execution_router.get("/{execution_id}",response_model=ExecutionOut,status_code=status.HTTP_200_OK)
def get_execution_details(db:db_dependency,execution_id:int=Path(gt=0),current_user:User=Depends(get_current_user)):
    owner_exception = HTTPException(
        status_code=403,
        detail="Unauthorized access, the prompt you are trying to retrieve belongs to a different owner or is not published"
    )
    execution_not_found_exception = HTTPException(
        status_code=404,
        detail="There is no execution that exists in the Database with the ID provided"
    )
    execution = db.query(Execution).filter(
         Execution.id==execution_id
    ).first()

    if not execution:
         raise execution_not_found_exception

    if execution.user_id!=current_user.id:
         raise owner_exception

    return execution


      


