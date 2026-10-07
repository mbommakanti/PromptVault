import pytest

from prompt_rendering import extract_placeholders


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
