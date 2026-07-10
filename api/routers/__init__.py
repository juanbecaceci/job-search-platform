"""API routers. `all_routers` is the ordered list wired into the app."""

from api.routers import (
    analytics,
    changes,
    chat,
    companies,
    dashboard,
    documents,
    export,
    jobs,
    memories,
    onboarding,
    positions,
    profile,
    scoring,
    searches,
    settings,
    templates,
)

# Order matters only for docs grouping; path collisions are avoided by prefixes
# and by declaring static sub-paths (e.g. /searches/defaults) before /{id}.
all_routers = [
    onboarding.router,
    dashboard.router,
    analytics.router,
    searches.router,
    positions.router,
    documents.router,
    documents.applications_router,
    profile.router,
    templates.router,
    scoring.router,
    companies.router,
    memories.router,
    settings.router,
    export.router,
    jobs.router,
    chat.router,
    changes.router,
]

__all__ = ["all_routers"]
