from fastapi import FastAPI

from app.api.routes import router
from app.settings import settings

app = FastAPI(title=settings.service_name)
app.include_router(router)
