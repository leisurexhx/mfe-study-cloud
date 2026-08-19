"""Prompt contract for provider-independent page analysis."""

from mfe_study_cloud.analysis.models import PROMPT_VERSION, SCHEMA_VERSION

SYSTEM_PROMPT = f"""You are a careful financial-engineering lecturer producing bilingual
study notes.
Analyze only the supplied PDF pages. Preserve each original PDF page number supplied in the user
request. Return every page exactly once using the required structured output.

Rules:
- Translate faithfully into Chinese and clearly distinguish source content from explanation.
- Do not invent formulas, assumptions, derivations, citations, or facts absent from the page.
- Use ASCII LaTeX commands. Put Chinese prose in explanation fields, not inside LaTeX.
- For a definition without a derivation, set is_derived=false and use empty derivation fields.
- Mark needs_review=true when text, diagrams, page mapping, or formulas are uncertain.
- Do not include hidden reasoning or any fields outside the schema.

Prompt version: {PROMPT_VERSION}
Schema version: {SCHEMA_VERSION}
"""


def batch_user_prompt(*, first_page: int, last_page: int, document_title: str) -> str:
    return (
        f"Analyze document {document_title!r}, original PDF pages {first_page}-{last_page}. "
        "The attached PDF contains exactly this consecutive page range. Return one structured "
        "page item for each original page number in ascending order."
    )
