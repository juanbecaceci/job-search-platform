"""Pydantic response schemas for the read API (PLATFORM_SPEC.md §4).

Kept separate from the ORM models in `api/models/` for clarity: these are the
wire shapes returned to the frontend, with `from_attributes=True` so they build
straight from ORM instances.
"""
