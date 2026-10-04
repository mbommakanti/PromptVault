from decimal import Decimal

from pricing import calculate_cost, normalize_model_name


def test_normalize_model_name_strips_dated_snapshot_suffix():
    assert normalize_model_name("gpt-4o-mini-2024-07-18") == "gpt-4o-mini"


def test_normalize_model_name_leaves_undated_name_unchanged():
    assert normalize_model_name("gpt-4o-mini") == "gpt-4o-mini"
    assert normalize_model_name("gpt-5.6-luna") == "gpt-5.6-luna"


def test_calculate_cost_matches_hand_worked_example():
    # (500 * 0.15 + 120 * 0.60) / 1_000_000 = 147 / 1_000_000 = 0.000147
    assert calculate_cost("gpt-4o-mini-2024-07-18", 500, 120) == Decimal("0.00014700")


def test_calculate_cost_matches_real_billed_execution():
    """Regression lock against the actual execution recorded in the dev DB
    (prompt_id=4, execution id=6): gpt-4.1-nano, 70 input / 39 output tokens,
    persisted cost_usd == 0.00002260. Pins the real end-to-end result, not
    just a hand-picked fixture.
    """
    assert calculate_cost("gpt-4.1-nano-2025-04-14", 70, 39) == Decimal("0.00002260")


def test_calculate_cost_returns_none_for_unpriced_model():
    # gpt-5.6-luna is a real model_name seen in the dev DB with no pricing entry.
    assert calculate_cost("gpt-5.6-luna", 500, 120) is None


def test_calculate_cost_returns_none_when_input_tokens_missing():
    """Regression lock for a real bug: build_execution_object calls
    calculate_cost unconditionally, including on the failure path where
    token counts are None. This used to raise TypeError instead of
    returning None, which would have crashed Step 3's exception handler.
    """
    assert calculate_cost("gpt-4o-mini", None, 120) is None


def test_calculate_cost_returns_none_when_output_tokens_missing():
    assert calculate_cost("gpt-4o-mini", 500, None) is None


def test_calculate_cost_returns_none_when_both_token_counts_missing():
    assert calculate_cost("gpt-4o-mini", None, None) is None


def test_calculate_cost_zero_tokens_is_zero():
    result = calculate_cost("gpt-4o-mini", 0, 0)
    assert result == Decimal(0)


def test_calculate_cost_does_not_swap_input_and_output_rates():
    """gpt-5.2-pro prices input/output asymmetrically ($21 vs $168 per 1M).
    Isolating all tokens to one side catches a swapped input/output rate
    immediately, the same bug class as Step 3's max_tokens/temperature swap.
    """
    all_input = calculate_cost("gpt-5.2-pro", 1_000_000, 0)
    all_output = calculate_cost("gpt-5.2-pro", 0, 1_000_000)
    assert all_input == Decimal("21.00000000")
    assert all_output == Decimal("168.00000000")


def test_calculate_cost_result_is_quantized_to_eight_decimal_places():
    result = calculate_cost("gpt-4o-mini-2024-07-18", 500, 120)
    assert result.as_tuple().exponent == -8
