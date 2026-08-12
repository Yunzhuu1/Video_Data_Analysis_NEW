from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.graph import graph_builder
from app.graph.checkpoints import create_checkpointer
from app.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    checkpointer = await create_checkpointer(settings.checkpoint_db_path)
    graph_builder.init_graph(checkpointer)
    yield


app = FastAPI(title=settings.service_name, lifespan=lifespan)
app.include_router(router)
