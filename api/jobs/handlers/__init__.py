"""Job handlers, registered onto the JobRunner at app startup.

One module per job type. As new job types land (evaluate_batch, generate_document,
…) add them here and register in `register_handlers`.
"""

from __future__ import annotations

from api.jobs.handlers import (
    evaluate_batch,
    export_document,
    generate_document,
    import_cv,
    research_company,
    search_run,
    sheets_export,
    upload_drive,
)
from api.models.enums import AsyncJobType


def register_handlers(runner) -> None:
    runner.register(AsyncJobType.SEARCH_RUN.value, search_run.handle)
    runner.register(AsyncJobType.EVALUATE_BATCH.value, evaluate_batch.handle)
    runner.register(AsyncJobType.GENERATE_DOCUMENT.value, generate_document.handle)
    runner.register(AsyncJobType.EXPORT_DOCUMENT.value, export_document.handle)
    runner.register(AsyncJobType.RESEARCH_COMPANY.value, research_company.handle)
    runner.register(AsyncJobType.IMPORT_CV.value, import_cv.handle)
    runner.register(AsyncJobType.SHEETS_EXPORT.value, sheets_export.handle)
    runner.register(AsyncJobType.UPLOAD_DRIVE.value, upload_drive.handle)
