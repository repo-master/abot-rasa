
from sqlalchemy import INTEGER, Column, ForeignKey, String
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property

from .basemodel import BaseModel


class Sensor(BaseModel):
  __tablename__ = "sensor"
  sensor_id = Column(INTEGER())
  value_ = Column("value", String())

  @hybrid_property
  def value(self):
    return self.value_.cast(float)
