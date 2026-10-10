import re

import pytest
from pydantic import TypeAdapter, ValidationError

from prompt_rendering import extract_placeholders
from schemas import PromptVariableSpec, VariableSpecList

VALID_NAMES = ["name", "_private", "item_2", "A", "a" * 64]

INVALID_NAMES = [
    "",
    "first name",
    "1abc",
    "my-var",
    "namé",
    "x;y",
    "name\n",   # $ must mean true end-of-string, not "before a trailing newline"
    "\nname",
]


def error_types(exc_info):
    return [error["type"] for error in exc_info.value.errors()]


# ---------------------------------------------------------------------------
# PromptVariableSpec: name rules
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", VALID_NAMES)
def test_spec_accepts_valid_names(name):
    assert PromptVariableSpec(name=name).name == name


@pytest.mark.parametrize("name", INVALID_NAMES)
def test_spec_rejects_invalid_names(name):
    with pytest.raises(ValidationError) as exc_info:
        PromptVariableSpec(name=name)
    assert error_types(exc_info) == ["string_pattern_mismatch"]


def test_spec_rejects_name_over_64_chars():
    with pytest.raises(ValidationError) as exc_info:
        PromptVariableSpec(name="a" * 65)
    assert error_types(exc_info) == ["string_too_long"]


def test_spec_requires_name():
    with pytest.raises(ValidationError) as exc_info:
        PromptVariableSpec.model_validate({"required": False})
    assert error_types(exc_info) == ["missing"]


@pytest.mark.parametrize("name", VALID_NAMES)
def test_every_valid_spec_name_is_matchable_as_a_placeholder(name):
    # Parity lock: the validation rule and PLACEHOLDER_PATTERN share one
    # definition of "name". If they ever drift, a declared variable could pass
    # validation yet never be fillable in a template.
    assert extract_placeholders("{{" + name + "}}") == {name}


@pytest.mark.parametrize("name", [n for n in INVALID_NAMES if n.strip() == n])
def test_no_invalid_spec_name_is_matchable_as_a_placeholder(name):
    # Leading/trailing whitespace is excluded on purpose: "{{name\n}}" is a
    # legitimate placeholder for `name`, because whitespace around the name is
    # allowed inside the braces. Only the name itself must be invalid here.
    assert extract_placeholders("{{" + name + "}}") == set()


# ---------------------------------------------------------------------------
# PromptVariableSpec: defaults and extra fields
# ---------------------------------------------------------------------------

def test_spec_defaults_to_required_with_no_default():
    spec = PromptVariableSpec(name="x")
    assert spec.required is True
    assert spec.default is None


def test_spec_rejects_unknown_fields():
    # A typo like "requird" must not be silently dropped (which would leave
    # the variable required when the author meant optional).
    with pytest.raises(ValidationError) as exc_info:
        PromptVariableSpec.model_validate({"name": "language", "requird": False})
    assert error_types(exc_info) == ["extra_forbidden"]


# ---------------------------------------------------------------------------
# PromptVariableSpec: required + default contradiction
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "fields",
    [
        {"name": "x", "default": "y"},                    # required is True by default
        {"name": "x", "required": True, "default": "y"},
        {"name": "x", "required": True, "default": ""},   # "" is still a default
    ],
)
def test_spec_rejects_required_with_default(fields):
    with pytest.raises(ValidationError) as exc_info:
        PromptVariableSpec.model_validate(fields)
    assert error_types(exc_info) == ["value_error"]
    assert "'x'" in str(exc_info.value)


@pytest.mark.parametrize(
    "fields",
    [
        {"name": "x", "required": False, "default": "y"},
        {"name": "x", "required": False, "default": ""},
        {"name": "x", "required": False},
        {"name": "x", "required": True},
    ],
)
def test_spec_accepts_consistent_required_and_default(fields):
    spec = PromptVariableSpec.model_validate(fields)
    assert spec.required == fields["required"]
    assert spec.default == fields.get("default")


def test_spec_field_errors_are_reported_before_model_rule():
    # Field validation runs first; the "after" model validator only ever sees a
    # spec whose fields are already valid.
    with pytest.raises(ValidationError) as exc_info:
        PromptVariableSpec.model_validate({"name": "bad name", "default": "y"})
    assert error_types(exc_info) == ["string_pattern_mismatch"]


# ---------------------------------------------------------------------------
# VariableSpecList: list-level rules
# ---------------------------------------------------------------------------

spec_list = TypeAdapter(VariableSpecList)


def test_spec_list_accepts_unique_names_and_returns_specs():
    specs = spec_list.validate_python([{"name": "a"}, {"name": "b", "required": False}])
    # Regression lock: the AfterValidator must return the list, not None.
    assert [spec.name for spec in specs] == ["a", "b"]
    assert all(isinstance(spec, PromptVariableSpec) for spec in specs)


def test_spec_list_accepts_empty_list():
    # Legacy / variable-free versions.
    assert spec_list.validate_python([]) == []


@pytest.mark.parametrize(
    "names, expected_duplicates",
    [
        (["a", "b", "a"], ["a"]),
        (["a", "a", "a"], ["a"]),
        (["b", "a", "b", "a"], ["a", "b"]),
        # Five names so an unsorted set can't come out alphabetical by luck
        # (set order of strings varies per process; 2 names = 50% false pass).
        (["e", "d", "c", "b", "a"] * 2, ["a", "b", "c", "d", "e"]),
    ],
)
def test_spec_list_rejects_duplicate_names(names, expected_duplicates):
    with pytest.raises(ValidationError) as exc_info:
        spec_list.validate_python([{"name": name} for name in names])
    [error] = exc_info.value.errors()
    assert error["type"] == "value_error"
    assert "duplicate variable names:" in error["msg"]
    # Every duplicate reported at once, each exactly once, in sorted order.
    # (Tolerant of "a, b" vs "['a', 'b']" formatting; only names and order matter.)
    reported = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", error["msg"].split("duplicate variable names:")[1])
    assert reported == expected_duplicates


def test_spec_list_duplicates_compare_by_name_only():
    # Same name, different settings: still ambiguous, still rejected.
    with pytest.raises(ValidationError):
        spec_list.validate_python([
            {"name": "language", "required": False},
            {"name": "language"},
        ])


def test_spec_list_runs_per_spec_rules_before_duplicate_check():
    with pytest.raises(ValidationError) as exc_info:
        spec_list.validate_python([{"name": "bad name"}, {"name": "bad name"}])
    assert set(error_types(exc_info)) == {"string_pattern_mismatch"}


def test_spec_list_rejects_non_list():
    with pytest.raises(ValidationError):
        spec_list.validate_python({"name": "a"})
