from __future__ import annotations

from pydantic import BaseModel, Field


class Task(BaseModel):
    mechanic: str = Field(min_length=1, max_length=40)
    instruction: str = Field(min_length=3, max_length=300)
    objects: list[str] = Field(default_factory=list, max_length=4)
    materials: list[str] = Field(default_factory=list, max_length=4)
    minutes: int = Field(ge=1, le=30)


class Mission(BaseModel):
    title: str = Field(min_length=3, max_length=80)
    story_hook: str = Field(min_length=3, max_length=300)
    tasks: list[Task] = Field(min_length=1, max_length=6)
    finale: str = Field(min_length=3, max_length=300)
    achievement_name: str = Field(min_length=3, max_length=60)
