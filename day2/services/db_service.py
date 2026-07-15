import random
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.schema import Base, Station, WaterQuality

class DBService:
    def __init__(self, db_url='sqlite:///water_system.db'):
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def get_session(self):
        return self.Session()

    def populate_dummy_data(self):
        session = self.get_session()
        if session.query(Station).count() == 0:
            stations = [Station(code=f"S00{i}", name=f"댐지점 {i}", lat=36.0+i*0.01, lon=127.0+i*0.01, remarks="자동생성") for i in range(1, 6)]
            session.add_all(stations)
            session.commit()
        if session.query(WaterQuality).count() == 0:
            codes = [s.code for s in session.query(Station).all()]
            data = [WaterQuality(date="2026-07-14", time=f"{random.randint(0, 23):02d}:00", station_code=random.choice(codes), discharge=round(random.uniform(10.0, 200.0), 2), turbidity=round(random.uniform(0.1, 5.0), 2)) for _ in range(10)]
            session.add_all(data)
            session.commit()
        session.close()