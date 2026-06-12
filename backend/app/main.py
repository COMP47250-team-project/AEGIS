from fastapi import FastAPI

from . import models
from .database import engine
from .routers import courses

# the below command is not needed if you are using alembic
# because it automatically creates the table
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="AEGIS — Anti-Cheat Exam Portal")

# Register routers
app.include_router(courses.router)