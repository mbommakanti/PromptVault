import time

from fastapi import APIRouter, Depends, HTTPException, Path
from starlette import status

from auth import db_dependency, get_current_user
from llm_provider import open_ai_adapter
from models import Execution, Prompt, PromptVersion, User
from schemas import ExecutionOut, ExecutionRequest

router = APIRouter(prefix="/api/v1/prompts", tags=["executions"])
execution_router = APIRouter(prefix="/api/v1/executions",tags=["executions"])

@router.post("/{prompt_id}/versions/{version_number}/execute",response_model=ExecutionOut,status_code=status.HTTP_201_CREATED)
def execute_llm_provider(db:db_dependency,execution_request:ExecutionRequest,current_user:User=Depends(get_current_user),
                         prompt_id:int=Path(gt=0),version_number:int=Path(gt=0)):
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

    start = time.perf_counter()
    adapter_response = open_ai_adapter(input=execution_request.input,instructions=prompt_version.content,model=execution_request.model,
                                           max_tokens = execution_request.max_tokens,temperature=execution_request.temperature
                                           )
    elapsed_time = time.perf_counter()-start
    latency_ms = round(elapsed_time*1000)

    execution_request_to_create = Execution(
          user_id = current_user.id,
          prompt_id = prompt_id,
          prompt_version_id=prompt_version.id,
          model_name=adapter_response.model_name,
          temperature=adapter_response.temperature,
          max_tokens=adapter_response.max_tokens,
          input=execution_request.input,
          output=adapter_response.model_response,
          status=adapter_response.response_status,
          incomplete_reason=adapter_response.incomplete_reason,
          input_tokens=adapter_response.input_tokens,
          output_tokens=adapter_response.output_tokens,
          total_tokens=adapter_response.total_tokens,
          provider_response_id=adapter_response.response_id,
          latency_ms=latency_ms
    )

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


      


