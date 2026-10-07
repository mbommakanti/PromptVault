import re

PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")

def extract_placeholders(template:str)->set[str]:
    variables = PLACEHOLDER_PATTERN.findall(template)
    return set(variables)
