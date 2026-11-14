from fastapi import APIRouter

from app.api.v1 import assistant, contracts, projects, reports, users

router = APIRouter(prefix="/api/v1")
router.include_router(users.router)
router.include_router(projects.router)
router.include_router(contracts.router)
router.include_router(assistant.router)
router.include_router(reports.router)
