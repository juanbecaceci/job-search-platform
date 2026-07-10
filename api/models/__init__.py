"""SQLAlchemy ORM models.

Importing this package registers every table on ``Base.metadata`` (that's what
Alembic autogenerate and ``Base.metadata.create_all`` walk). Import models from
here (``from api.models import Position``) so the whole set is always loaded and
relationship string references resolve.
"""

from api.db.base import Base
from api.models.agent import ChatMessage, ChatThread, ModuleMemory, PendingChange
from api.models.company import Company
from api.models.content import Document, Template, TemplateVersion
from api.models.position import Application, Position, PositionEvent
from api.models.profile import ProfileBasics, ProfileSection
from api.models.scoring import ScoringConfig
from api.models.search import Job, Search, SearchRun, SearchRunPosition
from api.models.settings import Setting

__all__ = [
    "Base",
    # company
    "Company",
    # position
    "Position",
    "PositionEvent",
    "Application",
    # search / jobs
    "Search",
    "SearchRun",
    "SearchRunPosition",
    "Job",
    # profile
    "ProfileBasics",
    "ProfileSection",
    # content
    "Template",
    "TemplateVersion",
    "Document",
    # scoring
    "ScoringConfig",
    # agent
    "ChatThread",
    "ChatMessage",
    "PendingChange",
    "ModuleMemory",
    # settings
    "Setting",
]
