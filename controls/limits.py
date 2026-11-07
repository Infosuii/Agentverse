"""Hard limits. ONE place for every threshold; the team agrees changes. Owner: agent-4."""

CLOSE_MAX_PROBABILITY = 0.20  # agent may not close an alert scored above this
HUMAN_REVIEW_AMOUNT_GBP = 10_000.0  # any alert with a payment this large needs a human

# Instruction-like text in memos is flagged; it can never change an outcome.
INJECTION_PATTERNS = [
    r"ignore (all )?(previous|prior|above) instructions",
    r"\bclose (this|the) alert\b",
    r"\bsystem prompt\b",
    r"\byou are now\b",
    r"\bdisregard\b",
]
