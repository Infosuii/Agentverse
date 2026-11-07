"""Quote verification (research/quotes.py). Owner: agent-2."""
from __future__ import annotations

import pytest

from jane_avenue.research.quotes import normalise, verify_quote

DOC = (
    "Chapter 3: Receipts\n"
    "Onshore corporation tax receipts totalled £82.3 billion in 2023–24, an increase of "
    "£11.1 billion on the previous year.  The increase was mainly due to the rise in the main rate to 25%.\n"
    "HMRC estimates that a one percentage point decrease in the Corporation Tax rate would lead to an increase "
    "in the size of the tax base. The costings assume a behavioural response to account for changes in the "
    "incentives for multinational companies to shift profits in and out of the UK."
)


def test_normalise_unifies_case_quotes_dashes_and_spaces() -> None:
    assert normalise("  “The Rate” – rose\n\tSHARPLY ") == '"the rate" - rose sharply'


@pytest.mark.parametrize("quote", [
    "The increase was mainly due to the rise in the main rate to 25%.",
    "the increase   was MAINLY due to the rise\nin the main rate to 25%.",  # case and whitespace
    "receipts totalled £82.3 billion in 2023-24",                     # NBSP and en dash in the source
    "“The costings assume a behavioural response”",                # curly quotes in the quote
])
def test_exact_matches_after_normalisation_are_verified(quote: str) -> None:
    assert verify_quote(quote, DOC) == ("verified", None)


def test_small_copying_slip_is_a_fuzzy_verified_match_with_a_note() -> None:
    quote = ("The costings assume a behavioral response to account for changes in the incentives for "
             "multinational companies to shift profit in and out of the UK.")  # US spelling, one plural dropped
    status, note = verify_quote(quote, DOC)
    assert status == "verified"
    assert note is not None and note.startswith("fuzzy match 0.9")


def test_paraphrase_fails() -> None:
    quote = "Multinationals move profits abroad when the tax rate goes up, so the base shrinks considerably."
    status, note = verify_quote(quote, DOC)
    assert status == "failed" and note and "not found" in note


def test_changed_number_fails_even_when_the_words_match() -> None:
    status, note = verify_quote("Onshore corporation tax receipts totalled £92.3 billion in 2023-24, an "
                                "increase of £11.1 billion on the previous year.", DOC)
    assert status == "failed" and note and "92.3" in note
    assert verify_quote("totalled £82.3 billion", DOC) == ("verified", None)


def test_number_at_the_edge_of_a_fuzzy_match_is_still_found() -> None:
    quote = "The increase was mainly due to the rise in the main rate to 25 %."  # stray space before %
    assert verify_quote(quote, DOC)[0] == "verified"


@pytest.mark.parametrize("quote,text", [(None, DOC), ("", DOC), ("   ", DOC), ("some quote", ""), ("q", None)])
def test_missing_quote_or_text_fails(quote: str | None, text: str | None) -> None:
    assert verify_quote(quote, text)[0] == "failed"


def test_short_non_matching_quote_fails_without_fuzzy_anchor() -> None:
    assert verify_quote("rates went down", DOC)[0] == "failed"


def test_elided_quote_verifies_part_by_part() -> None:
    quote = ("HMRC estimates that a one percentage point decrease in the Corporation Tax rate ... "
             "the incentives for multinational companies to shift profits")
    status, note = verify_quote(quote, DOC)
    assert status == "verified" and note and note.startswith("elided quote")


def test_elided_quote_fails_if_any_part_is_invented() -> None:
    quote = ("HMRC estimates that a one percentage point decrease… which would raise twelve billion pounds "
             "every single year without fail")
    assert verify_quote(quote, DOC)[0] == "failed"


def test_long_documents_with_repeated_phrases_still_verify() -> None:
    filler = "The corporation tax rate is discussed in this chapter. " * 3000
    text = filler + DOC + filler
    quote = ("HMRC estimates that a one percentage point decrease in the Corporation Tax rate would lead to an "
             "increase in the size of the tax bass.")  # one typo -> fuzzy
    status, note = verify_quote(quote, text)
    assert status == "verified" and note and "fuzzy" in note
