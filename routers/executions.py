from fastapi import APIRouter, Depends, HTTPException, Path
from starlette import status

from auth import db_dependency, get_current_user
from llm_provider import open_ai_adapter
from models import Prompt, PromptVersion, User
from schemas import AdapterResponse, ExecutionRequest

router = APIRouter(prefix="/api/v1/prompts", tags=["executions"])

@router.post("/{prompt_id}/versions/{version_number}/execute",response_model=AdapterResponse,status_code=status.HTTP_200_OK)
def execute_llm_provider(db:db_dependency,execution_request:ExecutionRequest,current_user:User=Depends(get_current_user),prompt_id:int=Path(gt=0),version_number:int=Path(gt=0)):
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
    
    adapter_response = open_ai_adapter(input=execution_request.input,instructions=prompt_version.content,model=execution_request.model,
                                           max_tokens = execution_request.max_tokens,temperature=execution_request.temperature
                                           )
    return adapter_response


