import decimal
import re

pricing = {
    "gpt-5.4-mini": {"input_per_1m": 0.75, "output_per_1m": 4.50},
    "gpt-5.4-nano": {"input_per_1m": 0.20, "output_per_1m": 1.25},
    "gpt-5.2": {"input_per_1m": 1.75, "output_per_1m": 14.00},
    "gpt-5.2-pro": {"input_per_1m": 21.00, "output_per_1m": 168.00},
    "gpt-5.1": {"input_per_1m": 1.25, "output_per_1m": 10.00},
    "gpt-5": {"input_per_1m": 1.25, "output_per_1m": 10.00},
    "gpt-5-mini": {"input_per_1m": 0.25, "output_per_1m": 2.00},
    "gpt-5-nano": {"input_per_1m": 0.05, "output_per_1m": 0.40},
    "gpt-4.1": {"input_per_1m": 2.00, "output_per_1m": 8.00},
    "gpt-4.1-mini": {"input_per_1m": 0.40, "output_per_1m": 1.60},
    "gpt-4.1-nano": {"input_per_1m": 0.10, "output_per_1m": 0.40},
    "gpt-4o": {"input_per_1m": 2.50, "output_per_1m": 10.00},
    "gpt-4o-mini": {"input_per_1m": 0.15, "output_per_1m": 0.60},
    "gpt-5.4": {"input_per_1m": 2.50, "output_per_1m": 15.00},
}


def normalize_model_name(model_name):
    return re.sub(r"-\d{4}-\d{2}-\d{2}$","",model_name)

def calculate_cost(model_name,input_tokens,output_tokens):
    if input_tokens is None or output_tokens is None:
        return None
    normalized_model_name = normalize_model_name(model_name)
    model_price = pricing.get(normalized_model_name)
    if model_price is not None:
        input_price_per_1m = decimal.Decimal(str(model_price.get("input_per_1m")))
        output_price_per_1m = decimal.Decimal(str(model_price.get("output_per_1m")))
        total_cost = (input_tokens * input_price_per_1m + output_tokens * output_price_per_1m) / 1000000
        return total_cost.quantize(decimal.Decimal("0.00000001"), rounding=decimal.ROUND_HALF_UP)
    else:
        return None
    