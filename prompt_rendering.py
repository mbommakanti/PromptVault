import re

from schemas import PromptVariableSpec


class PromptRenderError(Exception):
    status_category:str="invalid_variables"

    def __init__(self,*,missing:list[str],unknown:list[str]):
        self.missing = sorted(missing)
        self.unknown = sorted(unknown)
        message = f"missing variables: {', '.join(self.missing)}; unknown variables: {', '.join(self.unknown)}"
        super().__init__(message)
        

PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")

def extract_placeholders(template:str)->set[str]:
    variables = PLACEHOLDER_PATTERN.findall(template)
    return set(variables)


def render_template(template:str,declared_specs:list[PromptVariableSpec],values:dict[str,str])->str:
    unknown_names = []
    missing_names = []
    spec_names = {spec.name for spec in declared_specs}
    for spec in declared_specs:
        if spec.required and spec.name not in values:
            missing_names.append(spec.name)
    for name in values:
        if name not in spec_names:
            unknown_names.append(name)
    if unknown_names or missing_names:
        raise PromptRenderError(missing=missing_names,unknown=unknown_names)
    resolved = {}
    for spec in declared_specs:
        if spec.name in values:
            resolved[spec.name]=values[spec.name]
        elif spec.default is not None and spec.name not in values:
            resolved[spec.name]=spec.default
        else:
            resolved[spec.name]=""
    

