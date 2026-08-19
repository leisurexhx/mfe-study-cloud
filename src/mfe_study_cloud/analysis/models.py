"""Versioned structured output accepted from every analysis provider."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "page-analysis-v1"
PROMPT_VERSION = "financial-engineering-v1"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FormulaVariable(StrictModel):
    symbol: str = Field(min_length=1, max_length=100)
    meaning: str = Field(min_length=1, max_length=2000)


class FormulaDerivation(StrictModel):
    is_derived: bool
    idea: str = Field(max_length=30_000)
    steps: list[str] = Field(max_length=100)
    result_check: str = Field(max_length=30_000)

    @model_validator(mode="after")
    def validate_derived_content(self) -> FormulaDerivation:
        if self.is_derived and (
            not self.idea.strip()
            or len(self.steps) < 2
            or not self.result_check.strip()
        ):
            raise ValueError("derived formulas require idea, two steps, and result_check")
        return self


class Formula(StrictModel):
    name: str = Field(min_length=1, max_length=500)
    latex: str = Field(min_length=1, max_length=10_000)
    variables: list[FormulaVariable] = Field(max_length=100)
    assumptions: list[str] = Field(max_length=100)
    explanation: str = Field(max_length=30_000)
    applications: list[str] = Field(max_length=100)
    derivation: FormulaDerivation


class FormulaExplanation(StrictModel):
    has_formula: bool
    formulas: list[Formula] = Field(max_length=100)


class BilingualTerm(StrictModel):
    term_en: str = Field(min_length=1, max_length=500)
    term_zh: str = Field(min_length=1, max_length=500)
    definition: str = Field(max_length=20_000)
    context: str = Field(max_length=20_000)


class Connections(StrictModel):
    previous: list[str] = Field(max_length=100)
    next: list[str] = Field(max_length=100)


class PageAnalysisOutput(StrictModel):
    page_number: int = Field(ge=1, le=100_000)
    original_text: str = Field(max_length=200_000)
    chinese_translation: str = Field(max_length=300_000)
    page_overview: str = Field(max_length=30_000)
    detailed_explanation: str = Field(max_length=300_000)
    formula_explanation: FormulaExplanation
    key_points: list[str] = Field(max_length=100)
    common_mistakes: list[str] = Field(max_length=100)
    bilingual_terms: list[BilingualTerm] = Field(max_length=500)
    connections: Connections
    extensions: list[str] = Field(max_length=100)
    confidence: float = Field(ge=0.0, le=1.0)
    needs_review: bool


class BatchAnalysisOutput(StrictModel):
    pages: list[PageAnalysisOutput] = Field(min_length=1, max_length=20)

