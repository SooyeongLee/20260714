from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Station(Base):
    __tablename__ = 'stations'
    code = Column(String, primary_key=True)
    name = Column(String)
    lat = Column(Float)
    lon = Column(Float)
    remarks = Column(String)

class WaterQuality(Base):
    __tablename__ = 'water_data'
    id = Column(Integer, primary_key=True)
    date = Column(String)
    time = Column(String)
    station_code = Column(String, ForeignKey('stations.code'))
    discharge = Column(Float)
    turbidity = Column(Float)