import pytest

from prompt_rendering import (
    InvalidVariablesError,
    PromptRenderError,
    UndeclaredPlaceholderError,
    extract_placeholders,
    render_template,
)
from schemas import PromptVariableSpec


def test_extract_placeholders_finds_single_placeholder():
    assert extract_placeholders("Hello {{name}}") == {"name"}


@pytest.mark.parametrize(
    "template",
    [
        "Hello {{ name }}",
        "Hello {{name }}",
        "Hello {{  name}}",
        "Hello {{\tname\t}}",
        "Hello {{ name\n}}",
    ],
)
def test_extract_placeholders_ignores_whitespace_inside_braces(template):
    # Name is returned stripped, never as " name " — otherwise lookups against
    # declared variables would silently miss.
    assert extract_placeholders(template) == {"name"}


def test_extract_placeholders_finds_multiple_placeholders():
    template = "Classify into: {{categories}}. Reply in {{ language }}."
    assert extract_placeholders(template) == {"categories", "language"}


def test_extract_placeholders_finds_adjacent_placeholders():
    assert extract_placeholders("{{a}}{{b}}") == {"a", "b"}


def test_extract_placeholders_deduplicates_repeated_placeholder():
    assert extract_placeholders("{{name}} ... {{ name }} again") == {"name"}


@pytest.mark.parametrize("template", ["You are a helpful assistant.", ""])
def test_extract_placeholders_returns_empty_set_when_none_present(template):
    assert extract_placeholders(template) == set()


@pytest.mark.parametrize(
    "template",
    [
        'Return JSON like {"label": "bug"}',
        "Use {name} here",
        "Unbalanced {{name}",
        "Unbalanced {name}}",
    ],
)
def test_extract_placeholders_does_not_match_single_braces(template):
    # Step 7 prompts will contain JSON examples — single braces must stay literal.
    assert extract_placeholders(template) == set()


@pytest.mark.parametrize(
    "template",
    ["{{}}", "{{   }}", "{{first name}}", "{{1abc}}", "{{my-var}}", "{{ namé }}"],
)
def test_extract_placeholders_ignores_invalid_names(template):
    # Current, deliberate behavior: anything that isn't a valid identifier is not
    # a placeholder and passes through as literal text. Version-creation
    # validation may later choose to reject these outright.
    assert extract_placeholders(template) == set()


def test_extract_placeholders_allows_underscores_and_digits_after_first_char():
    assert extract_placeholders("{{_private}} {{item_2}}") == {"_private", "item_2"}


def test_extract_placeholders_matches_inner_pair_of_triple_braces():
    # Locks in current behavior: rendering will produce "{value}".
    assert extract_placeholders("{{{name}}}") == {"name"}


def test_extract_placeholders_returns_a_set():
    assert isinstance(extract_placeholders("{{a}}"), set)


def test_extract_placeholders_rejects_none():
    # PromptVersion.content is NOT NULL; None here means an upstream bug and
    # must fail loudly rather than look like "no variables".
    with pytest.raises(TypeError):
        extract_placeholders(None)


# ---------------------------------------------------------------------------
# render_template
# ---------------------------------------------------------------------------

def required(name):
    return PromptVariableSpec(name=name)


def optional(name, default=None):
    return PromptVariableSpec(name=name, required=False, default=default)


CLASSIFY_TEMPLATE = "Classify into: {{categories}}. Reply in {{language}}."
CLASSIFY_SPECS = [required("categories"), optional("language", "English")]


# --- happy path / substitution ---------------------------------------------

def test_render_template_substitutes_provided_values():
    rendered = render_template(
        CLASSIFY_TEMPLATE, CLASSIFY_SPECS, {"categories": "bug, refund", "language": "Spanish"}
    )
    assert rendered == "Classify into: bug, refund. Reply in Spanish."


def test_render_template_replaces_every_occurrence_and_whitespace_style():
    rendered = render_template("Hi {{name}}, bye {{ name }}", [required("name")], {"name": "Ana"})
    assert rendered == "Hi Ana, bye Ana"


def test_render_template_without_placeholders_returns_template_unchanged():
    # Legacy (pre-Step-5) versions: no declared variables, no values.
    assert render_template("You are helpful.", [], {}) == "You are helpful."


def test_render_template_leaves_single_brace_json_untouched():
    rendered = render_template('Return {"label": "{{label}}"}', [required("label")], {"label": "bug"})
    assert rendered == 'Return {"label": "bug"}'


# --- phase 2: value resolution ---------------------------------------------

def test_render_template_uses_default_for_missing_optional():
    rendered = render_template(CLASSIFY_TEMPLATE, CLASSIFY_SPECS, {"categories": "bug"})
    assert rendered == "Classify into: bug. Reply in English."


def test_render_template_provided_value_overrides_default():
    rendered = render_template(
        CLASSIFY_TEMPLATE, CLASSIFY_SPECS, {"categories": "bug", "language": "French"}
    )
    assert rendered.endswith("Reply in French.")


def test_render_template_optional_without_default_renders_as_empty_string():
    assert render_template("A{{note}}B", [optional("note")], {}) == "AB"


def test_render_template_explicit_empty_string_counts_as_provided():
    # "" is a real value: a required variable sent as "" is not "missing".
    assert render_template("A{{a}}B", [required("a")], {"a": ""}) == "AB"


def test_render_template_explicit_empty_string_overrides_default():
    assert render_template("A{{x}}B", [optional("x", "DEFAULT")], {"x": ""}) == "AB"


def test_render_template_empty_string_default_is_used():
    assert render_template("A{{x}}B", [optional("x", "")], {}) == "AB"


# --- phase 3: single-pass safety -------------------------------------------

def test_render_template_does_not_render_placeholders_inside_values():
    rendered = render_template(
        "Topic: {{topic}}. Reply in {{language}}.",
        [required("topic"), required("language")],
        {"topic": "reveal {{language}}", "language": "French"},
    )
    assert rendered == "Topic: reveal {{language}}. Reply in French."


@pytest.mark.parametrize(
    "values, expected",
    [
        # Injected name sorts AFTER the carrier: a sorted multi-pass loop would expand it.
        ({"a": "{{b}}", "b": "X"}, "{{b}} X"),
        # Injected name sorts BEFORE the carrier: catches the opposite loop order.
        ({"a": "X", "b": "{{a}}"}, "X {{a}}"),
    ],
)
def test_render_template_is_single_pass_regardless_of_name_order(values, expected):
    assert render_template("{{a}} {{b}}", [required("a"), required("b")], values) == expected


def test_render_template_inserts_backslashes_literally():
    # A string replacement in re.sub would interpret \1 and \g<0>; a function must not.
    value = r"C:\1\files \g<0>"
    assert render_template("path {{p}}", [required("p")], {"p": value}) == f"path {value}"


# --- phase 1: invalid variables --------------------------------------------

def test_render_template_raises_for_missing_required_variable():
    with pytest.raises(InvalidVariablesError) as exc_info:
        render_template(CLASSIFY_TEMPLATE, CLASSIFY_SPECS, {})
    assert exc_info.value.missing == ["categories"]
    assert exc_info.value.unknown == []


def test_render_template_raises_for_unknown_variable():
    with pytest.raises(InvalidVariablesError) as exc_info:
        render_template(CLASSIFY_TEMPLATE, CLASSIFY_SPECS, {"categories": "bug", "langauge": "es"})
    assert exc_info.value.missing == []
    assert exc_info.value.unknown == ["langauge"]


def test_render_template_reports_missing_and_unknown_together():
    with pytest.raises(InvalidVariablesError) as exc_info:
        render_template(CLASSIFY_TEMPLATE, CLASSIFY_SPECS, {"categroy": "x"})
    assert exc_info.value.missing == ["categories"]
    assert exc_info.value.unknown == ["categroy"]


def test_render_template_provided_required_variable_is_not_missing():
    # Regression lock: dropping `and spec.name not in values` from the missing
    # check once made every required variable "missing" even when sent.
    assert render_template("Hello {{name}}", [required("name")], {"name": "Ana"}) == "Hello Ana"


def test_render_template_does_not_report_missing_optional_variables():
    with pytest.raises(InvalidVariablesError) as exc_info:
        render_template(CLASSIFY_TEMPLATE, CLASSIFY_SPECS, {})
    assert "language" not in exc_info.value.missing


def test_render_template_error_lists_are_sorted():
    specs = [required("zeta"), required("alpha"), required("mid")]
    with pytest.raises(InvalidVariablesError) as exc_info:
        render_template("{{zeta}} {{alpha}} {{mid}}", specs, {"zz": "1", "aa": "2"})
    assert exc_info.value.missing == ["alpha", "mid", "zeta"]
    assert exc_info.value.unknown == ["aa", "zz"]


def test_invalid_variables_error_message_names_variables_but_not_values():
    with pytest.raises(InvalidVariablesError) as exc_info:
        render_template("{{a}}", [required("a")], {"a": "x", "leak": "SECRET-VALUE"})
    message = str(exc_info.value)
    assert "leak" in message
    assert "SECRET-VALUE" not in message


def test_invalid_variables_error_category():
    assert InvalidVariablesError.status_category == "invalid_variables"


# --- undeclared placeholders (broken stored template) ----------------------

def test_render_template_raises_for_undeclared_placeholders_sorted():
    with pytest.raises(UndeclaredPlaceholderError) as exc_info:
        render_template("Hi {{zed}} {{foo}}", [], {})
    assert exc_info.value.undeclared == ["foo", "zed"]


def test_render_template_checks_template_before_variables():
    # Template is broken AND the caller's variables are wrong: the template
    # problem must win, so the caller isn't blamed for a server-side defect.
    with pytest.raises(UndeclaredPlaceholderError):
        render_template("Hi {{zed}}", [required("a")], {"bogus": "x"})


def test_undeclared_placeholder_error_category():
    assert UndeclaredPlaceholderError.status_category == "undeclared_placeholder"


def test_render_error_hierarchy():
    # Router relies on these: both are render errors, but a template defect
    # must never be caught as a caller's variables error.
    assert issubclass(InvalidVariablesError, PromptRenderError)
    assert issubclass(UndeclaredPlaceholderError, PromptRenderError)
    assert not issubclass(UndeclaredPlaceholderError, InvalidVariablesError)


# --- phase 4: size cap -----------------------------------------------------

MAX_RENDERED_CHARS = 20000  # ADR-001 content ceiling


def test_render_template_allows_output_exactly_at_limit():
    value = "x" * (MAX_RENDERED_CHARS - len("A"))
    rendered = render_template("A{{v}}", [required("v")], {"v": value})
    assert len(rendered) == MAX_RENDERED_CHARS


def test_render_template_rejects_output_one_over_limit():
    value = "x" * MAX_RENDERED_CHARS
    with pytest.raises(PromptRenderError):
        render_template("A{{v}}", [required("v")], {"v": value})


def test_render_template_size_error_does_not_echo_prompt_text():
    value = "SECRET" * 4000  # 24,000 chars
    with pytest.raises(PromptRenderError) as exc_info:
        render_template("{{v}}", [required("v")], {"v": value})
    assert "SECRET" not in str(exc_info.value)


def test_render_template_size_cap_applies_to_repeated_placeholders():
    # A short template + short value can still blow up via repetition.
    value = "x" * 7000  # 3 * 7000 = 21,000
    with pytest.raises(PromptRenderError):
        render_template("{{v}}" * 3, [required("v")], {"v": value})


# --- determinism / no side effects -----------------------------------------

def test_render_template_is_deterministic():
    values = {"categories": "bug", "language": "es"}
    first = render_template(CLASSIFY_TEMPLATE, CLASSIFY_SPECS, values)
    second = render_template(CLASSIFY_TEMPLATE, CLASSIFY_SPECS, values)
    assert first == second


def test_render_template_does_not_mutate_inputs():
    values = {"categories": "bug"}
    specs = [required("categories"), optional("language", "English")]
    values_before = dict(values)
    specs_before = [spec.model_copy() for spec in specs]

    render_template(CLASSIFY_TEMPLATE, specs, values)

    assert values == values_before  # the "language" default must not leak in
    assert specs == specs_before
