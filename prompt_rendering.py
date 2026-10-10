import re

from schemas import VARIABLE_NAME_PATTERN, PromptVariableSpec


class PromptRenderError(Exception):
    status_category:str="renderer_error"


class InvalidVariablesError(PromptRenderError):
    status_category:str="invalid_variables"

    def __init__(self,*,missing:list[str],unknown:list[str]):
        self.missing = sorted(missing)
        self.unknown = sorted(unknown)
        message = f"missing variables: {', '.join(self.missing)}; unknown variables: {', '.join(self.unknown)}"
        super().__init__(message)


class UndeclaredPlaceholderError(PromptRenderError):
    status_category:str="undeclared_placeholder"

    def __init__(self,*,undeclared:set[str]):
        self.undeclared = sorted(undeclared)
        message = f"undeclared variables: {', '.join(self.undeclared)}"
        super().__init__(message)


class RenderedPromptTooLarge(PromptRenderError):
    status_category:str="rendered_too_large"

    def __init__(self,*,length:int,limit:int):
        self.length =length
        self.limit = limit
        message = f"Rendered Prompt is too large, length of provided prompt is: {length}; limit is: {limit}"
        super().__init__(message)
        

PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*("+VARIABLE_NAME_PATTERN+r")\s*\}\}")

def extract_placeholders(template:str)->set[str]:
    variables = PLACEHOLDER_PATTERN.findall(template)
    return set(variables)


def render_template(template:str,declared_specs:list[PromptVariableSpec],values:dict[str,str])->str:
    unknown_names = []
    missing_names = []
    spec_names = {spec.name for spec in declared_specs}
    placeholders = extract_placeholders(template)
    undeclared = placeholders - spec_names
    if undeclared:
        raise UndeclaredPlaceholderError(undeclared=undeclared)
    for spec in declared_specs:
        if spec.required and spec.name not in values:
            missing_names.append(spec.name)
    for name in values:
        if name not in spec_names:
            unknown_names.append(name)
    if unknown_names or missing_names:
        raise InvalidVariablesError(missing=missing_names,unknown=unknown_names)
    resolved = {}
    for spec in declared_specs:
        if spec.name in values:
            resolved[spec.name]=values[spec.name]
        elif spec.default is not None:
            resolved[spec.name]=spec.default
        else:
            resolved[spec.name]=""

    def replacement_function(match):
        return resolved[match.group(1)]

    resolved_template = PLACEHOLDER_PATTERN.sub(replacement_function,template)
    if len(resolved_template)>20000:
        raise RenderedPromptTooLarge(length=len(resolved_template),limit=20000)
    
    return resolved_template
