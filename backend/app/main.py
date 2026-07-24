from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db
from app.api.v1 import projects, worldviews, characters, chapters, foreshadowings, generation, knowledges, settings as settings_router, story_core, volumes, prompt_templates, search, reviews, events, debts, contracts, pipeline, auto_pipeline, templates, creative, style, init, deconstruction


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router, prefix=settings.API_PREFIX)
app.include_router(worldviews.router, prefix=settings.API_PREFIX)
app.include_router(characters.router, prefix=settings.API_PREFIX)
app.include_router(chapters.router, prefix=settings.API_PREFIX)
app.include_router(foreshadowings.router, prefix=settings.API_PREFIX)
app.include_router(knowledges.router, prefix=settings.API_PREFIX)
app.include_router(settings_router.router, prefix=settings.API_PREFIX)
app.include_router(generation.router, prefix=settings.API_PREFIX)
app.include_router(story_core.router, prefix=settings.API_PREFIX)
app.include_router(volumes.router, prefix=settings.API_PREFIX)
app.include_router(prompt_templates.router, prefix=settings.API_PREFIX)
app.include_router(search.router, prefix=settings.API_PREFIX)
app.include_router(reviews.router, prefix=settings.API_PREFIX)
app.include_router(events.router, prefix=settings.API_PREFIX)
app.include_router(debts.router, prefix=settings.API_PREFIX)
app.include_router(contracts.router, prefix=settings.API_PREFIX)
app.include_router(contracts.project_router, prefix=settings.API_PREFIX)
app.include_router(templates.router, prefix=settings.API_PREFIX)
app.include_router(pipeline.router, prefix=settings.API_PREFIX)
app.include_router(auto_pipeline.router, prefix=settings.API_PREFIX)
app.include_router(creative.router, prefix=settings.API_PREFIX)
app.include_router(style.router, prefix=settings.API_PREFIX)
app.include_router(style.router, prefix=settings.API_PREFIX)
app.include_router(init.router, prefix=settings.API_PREFIX)
app.include_router(deconstruction.router, prefix=settings.API_PREFIX)

@app.get("/health")
async def health_check():
    return {"status": "ok", "app": settings.APP_NAME}