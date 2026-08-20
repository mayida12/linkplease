"""
Keyword matching: "does this comment text contain this rule's keyword,
case-insensitively, anywhere in the string?"
"""
from typing import Optional, Sequence

from app.models.rule import Rule


def find_matching_rule(comment_text: str, rules: Sequence[Rule]) -> Optional[Rule]:
    """
    Returns the first rule whose keyword appears anywhere in comment_text
    (case-insensitive substring match), or None if no rule matches.

    If multiple rules could match the same comment, the first one found
    (in the order `rules` was given) wins. For this assignment that's a
    reasonable, simple tie-break; a real product might need explicit
    priority ordering, which would just mean sorting `rules` before calling
    this function.
    """
    if not comment_text:
        return None

    lowered_comment = comment_text.lower()
    for rule in rules:
        if rule.keyword.lower() in lowered_comment:
            return rule
    return None
