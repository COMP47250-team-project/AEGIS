from . import models
from .database import engine, SessionLocal

#the below command is not needed if you are using alembic because it automatically create the table
models.Base.metadata.create_all(bind=engine)
