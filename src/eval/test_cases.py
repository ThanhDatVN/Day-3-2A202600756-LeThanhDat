"""
Test suite for the Chatbot-vs-Agent comparison.

Each case carries the expected substring(s) so the runner can auto-score a
response as pass/fail (used to compute the Success Rate in the group report).
`kind` distinguishes simple Q&A from multi-step reasoning - the whole point is
that the chatbot should win/tie on 'simple' and lose on 'multi'.
"""

TEST_CASES = [
    {
        "id": "T1",
        "kind": "simple",
        "prompt": "What is the price of an iPad?",
        "expect_any": ["600"],
    },
    {
        "id": "T2",
        "kind": "multi",
        "prompt": ("I want to buy 2 iPhones using code 'WINNER' and ship to Hanoi. "
                   "What is the total price?"),
        "expect_any": ["1607"],
    },
    {
        "id": "T3",
        "kind": "multi",
        "prompt": "Is the Samsung Galaxy in stock so I can order it?",
        "expect_any": ["out of stock", "0 units", "cannot"],
    },
    {
        "id": "T4",
        "kind": "multi",
        "prompt": "What is the 10% tax on a MacBook?",
        "expect_any": ["200"],
    },
]


def is_correct(answer: str, case: dict) -> bool:
    text = (answer or "").lower()
    return any(token.lower() in text for token in case.get("expect_any", []))
