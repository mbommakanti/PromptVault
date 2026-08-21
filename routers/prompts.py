from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import func, text
from starlette import status

from auth import db_dependency, get_current_user
from models import Prompt, PromptVersion, User
from schemas import PromptCreate, PromptOut, PromptUpdate, PromptVersionOut

router = APIRouter(prefix="/api/v1/prompts", tags=["prompts"])

@router.post("",response_model=PromptOut,status_code=status.HTTP_201_CREATED)
def create_prompt(db:db_dependency,prompt_request:PromptCreate,current_user:User=Depends(get_current_user)):
    prompt_to_create = Prompt(
        owner_id = current_user.id,
        title = prompt_request.title,
        description = prompt_request.description,
        tags = prompt_request.tags,
        model_target = prompt_request.model_target,
        current_version = 1
    )

    db.add(prompt_to_create)
    db.flush()
    db.refresh(prompt_to_create)

    prompt_version_to_create = PromptVersion(
        prompt_id = prompt_to_create.id,
        version_number = 1,
        content = prompt_request.content,
    )

    db.add(prompt_version_to_create)
    db.commit()
    db.refresh(prompt_to_create)
    return prompt_to_create


@router.get("",response_model=list[PromptOut],status_code=status.HTTP_200_OK)
def get_all_prompts_of_user_plus_published_prompts(db:db_dependency,current_user:User=Depends(get_current_user)):
    prompts = db.query(Prompt).filter(
        ((Prompt.owner_id==current_user.id)| (Prompt.is_published==True)) 
        & (Prompt.deleted_at.is_(None)) 
    ).all()
    return prompts

@router.get("/{prompt_id}",response_model=PromptOut,status_code=status.HTTP_200_OK)
def get_prompts_by_prompt_id(db:db_dependency,current_user:User=Depends(get_current_user),prompt_id:int=Path(gt=0)):
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

    if prompt:
        if prompt.owner_id != current_user.id and prompt.is_published==False:
            raise owner_exception
        return prompt
    else:
        raise prompt_not_found_exception

@router.put("/{prompt_id}",response_model=PromptOut,status_code=status.HTTP_200_OK)
def update_prompt(prompt_update:PromptUpdate,db:db_dependency,current_user:User=Depends(get_current_user),prompt_id:int=Path(gt=0)):
    owner_exception = HTTPException(
        status_code = 403,
        detail = "The prompt you are trying to update belongs to a different owner"
    )
    prompt_not_found_exception = HTTPException(
        status_code=404,
        detail = "No prompts found with the specified prompt id"
    )
    prompt = db.query(Prompt).filter(
        (Prompt.id==prompt_id) & (Prompt.deleted_at.is_(None))
    ).first()

    if not prompt:
        raise prompt_not_found_exception

    if prompt.owner_id!=current_user.id:
        raise owner_exception

    if prompt_update.title is not None:
        prompt.title = prompt_update.title
    if prompt_update.description is not None:
        prompt.description = prompt_update.description
    if prompt_update.tags is not None:
        prompt.tags = prompt_update.tags
    if prompt_update.model_target is not None:
        prompt.model_target = prompt_update.model_target

    if prompt_update.content is not None:
        new_version_number = db.execute(
            text("UPDATE prompts SET current_version = current_version + 1 WHERE id = :prompt_id RETURNING current_version"),
            {"prompt_id": prompt.id},
        ).scalar_one()

        prompt_version_to_create = PromptVersion(
            prompt_id = prompt.id,
            version_number = new_version_number,
            content = prompt_update.content
        )
        prompt.updated_at = func.now()

        db.add(prompt_version_to_create)

    db.commit()
    db.refresh(prompt)

    return prompt


@router.delete("/{prompt_id}",status_code=status.HTTP_204_NO_CONTENT)
def delete_prompt_by_id(db:db_dependency,prompt_id:int=Path(gt=0),current_user:User=Depends(get_current_user)):
    owner_exception = HTTPException(
        status_code = 403,
        detail = "The prompt you are trying to delete belongs to a different owner"
    )
    prompt_not_found_exception = HTTPException(
        status_code=404,
        detail = "No prompts found with the specified prompt id"
    )

    prompt = db.query(Prompt).filter(
        (Prompt.id==prompt_id) & (Prompt.deleted_at.is_(None))
    ).first()

    if not prompt:
        raise prompt_not_found_exception

    if prompt.owner_id != current_user.id:
        raise owner_exception

    prompt.deleted_at = func.now()

    db.commit()
    db.refresh(prompt)

@router.patch("/{prompt_id}/publish",response_model=PromptOut,status_code=status.HTTP_200_OK)
def toggle_publish_status(db:db_dependency,prompt_id:int=Path(gt=0),current_user:User=Depends(get_current_user)):
    owner_exception = HTTPException(
        status_code = 403,
        detail = "The prompt you are trying to publish belongs to a different owner"
    )
    prompt_not_found_exception = HTTPException(
        status_code=404,
        detail = "No prompts found with the specified prompt id"
    )

    prompt = db.query(Prompt).filter(
        (Prompt.id==prompt_id) & (Prompt.deleted_at.is_(None)) 
    ).first()

    if not prompt:
        raise prompt_not_found_exception

    if prompt.owner_id != current_user.id:
        raise owner_exception

    prompt.is_published = not prompt.is_published

    db.commit()
    db.refresh(prompt)
    return prompt

@router.get("/{prompt_id}/versions",response_model=list[PromptVersionOut],status_code=status.HTTP_200_OK)
def get_prompt_versions_by_prompt_id(db:db_dependency,prompt_id:int=Path(gt=0),current_user:User=Depends(get_current_user)):
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

    prompt_versions = db.query(PromptVersion).filter(
        PromptVersion.prompt_id == prompt_id
    ).order_by(PromptVersion.version_number).all()

    return prompt_versions

@router.get("/{prompt_id}/versions/{version_number}",response_model=PromptVersionOut,status_code=status.HTTP_200_OK)
def get_prompt_version_by_prompt_id_and_version_number(db:db_dependency,prompt_id:int=Path(gt=0),version_number:int=Path(gt=0),current_user:User=Depends(get_current_user)):
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

    return prompt_version
    

