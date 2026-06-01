"""
E-commerce tools for the "Smart Shopping Assistant" scenario.

Design note (Phase 1 - Tool Design):
Each tool returns a *string* Observation. The string is what the LLM "sees"
on the next ReAct step, so it must be self-describing and unambiguous.
A good Observation tells the agent both the value AND the unit/context.
"""

# --- Mock back-end data (simulates a product DB / pricing service) ---
PRODUCTS = {
    "iphone": {"display": "iPhone 15", "price": 1000.0, "stock": 5, "weight": 0.5},
    "ipad": {"display": "iPad Air", "price": 600.0, "stock": 10, "weight": 0.7},
    "macbook": {"display": "MacBook Air", "price": 2000.0, "stock": 2, "weight": 2.0},
    "samsung": {"display": "Samsung Galaxy S24", "price": 800.0, "stock": 0, "weight": 0.5},
}

# Coupon code -> discount percentage
COUPONS = {
    "WINNER": 20,
    "SUMMER": 10,
    "VIP": 30,
}

# Destination -> base shipping fee (USD); total = base + weight * 2.0
SHIPPING_BASE = {
    "hanoi": 5.0,
    "ho chi minh": 7.0,
    "danang": 6.0,
}


def _find_product(item_name: str):
    """Fuzzy-match a free-text item name to our product catalogue."""
    key = (item_name or "").strip().lower()
    if key in PRODUCTS:
        return PRODUCTS[key]
    for k, v in PRODUCTS.items():
        if k in key or key in k:
            return v
    return None


def check_stock(item_name: str) -> str:
    """How many units of an item are available."""
    product = _find_product(item_name)
    if product is None:
        return f"ERROR: Product '{item_name}' does not exist in the catalogue."
    if product["stock"] <= 0:
        return f"'{product['display']}' is OUT OF STOCK (0 units available)."
    return f"'{product['display']}' is in stock: {product['stock']} units available."


def get_price(item_name: str) -> str:
    """Unit price of an item in USD."""
    product = _find_product(item_name)
    if product is None:
        return f"ERROR: Product '{item_name}' does not exist in the catalogue."
    return f"Unit price of '{product['display']}' is {product['price']} USD."


def get_discount(coupon_code: str) -> str:
    """Discount percentage granted by a coupon code."""
    code = (coupon_code or "").strip().upper()
    if code not in COUPONS:
        return f"ERROR: Coupon '{coupon_code}' is invalid or expired."
    return f"Coupon '{code}' grants a {COUPONS[code]}% discount."


def calc_shipping(weight: float, destination: str) -> str:
    """Shipping cost given total weight (kg) and a destination city."""
    try:
        weight = float(weight)
    except (TypeError, ValueError):
        return f"ERROR: weight must be a number, got '{weight}'."
    dest = (destination or "").strip().lower()
    if dest not in SHIPPING_BASE:
        return (f"ERROR: Unknown destination '{destination}'. "
                f"Supported: {', '.join(SHIPPING_BASE)}.")
    cost = SHIPPING_BASE[dest] + weight * 2.0
    return f"Shipping {weight}kg to {destination} costs {round(cost, 2)} USD."


# --- Tool specifications exposed to the agent ---
# The 'description' is the ONLY thing the LLM knows about a tool, so it must
# state the arguments and units precisely (Instructor Guide, Phase 1).
ECOMMERCE_TOOLS = [
    {
        "name": "check_stock",
        "description": (
            "Check inventory availability for a product. "
            "Args: item_name (string, e.g. 'iPhone'). "
            "Returns the number of units in stock."
        ),
        "func": check_stock,
    },
    {
        "name": "get_price",
        "description": (
            "Get the unit price of a product in USD. "
            "Args: item_name (string, e.g. 'iPad'). "
            "Returns the price per single unit."
        ),
        "func": get_price,
    },
    {
        "name": "get_discount",
        "description": (
            "Look up the discount percentage for a coupon code. "
            "Args: coupon_code (string, UPPERCASE, e.g. 'WINNER'). "
            "Returns the discount percent, or an error if invalid."
        ),
        "func": get_discount,
    },
    {
        "name": "calc_shipping",
        "description": (
            "Compute shipping cost. "
            "Args: weight (float kilograms), destination (string city, one of "
            "'Hanoi', 'Ho Chi Minh', 'Danang'). Returns the shipping fee in USD."
        ),
        "func": calc_shipping,
    },
]
