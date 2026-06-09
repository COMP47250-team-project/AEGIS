from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base


SQL_ALCHEMY_DATABASE_URL = ''
engine = create_engine(SQL_ALCHEMY_DATABASE_URL)


Base = declarative_base()