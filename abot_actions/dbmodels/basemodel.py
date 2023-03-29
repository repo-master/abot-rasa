
from sqlalchemy.orm import declarative_base

from sqlalchemy import INTEGER, Column


Base = declarative_base()

class BaseModel(Base):
    __abstract__ = True
    id = Column(INTEGER(), primary_key=True)

__all__ = [
    'BaseModel'
]
