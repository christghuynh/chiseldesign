from fastapi import APIRouter

from app.api import edit, export, generate, health, instructions, parse, projects, templates, voice

api_router = APIRouter()
for module in (health, templates, parse, generate, edit, instructions, voice, projects, export):
    api_router.include_router(module.router)
