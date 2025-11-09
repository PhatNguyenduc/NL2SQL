"""Prompt templates for LLM"""

from src.prompts.system_prompt import get_system_prompt
from src.prompts.few_shot_examples import get_few_shot_examples

__all__ = ["get_system_prompt", "get_few_shot_examples"]
