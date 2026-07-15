import random
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
# 기존에 분리 선언한 models.schema 스펙을 그대로 유지하여 임포트합니다.
from models.schema import Base, Station, WaterQuality

class DBService:
    def __init__(self, db_url='sqlite:///water_system.db'):
        self.engine = create_engine(db_url)
        # 테이블 구조 변경이 완전히 반영된 최신 스키마 메타데이터 기반으로 DDL을 실행합니다.
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def get_session(self):
        return self.Session()

    def populate_dummy_data(self):
        session = self.get_session()
        
        # 1. Station 테이블 더미 데이터 정형화 적재
        if session.query(Station).count() == 0:
            stations = []
            for i in range(1, 6):
                station = Station(
                    code=f"S00{i}",
                    name=f"댐지점 {i}",
                    lat=36.0 + i * 0.01,
                    lon=127.0 + i * 0.01,
                    river_basin="한강",  # 신규 추가된 '하천유역' 물리 필드 반영
                    remarks="자동생성"
                )
                stations.append(station)
            session.add_all(stations)
            session.commit()
            
        # 2. WaterQuality 테이블 더미 데이터 적재 (DateTime 결합 및 컬럼 매칭 완료)
        if session.query(WaterQuality).count() == 0:
            # 관계형 무결성을 유지하기 위해 데이터베이스 내에 등록된 실제 Station 매핑 딕셔너리를 구축합니다.
            station_records = session.query(Station).all()
            codes = [s.code for s in station_records]
            
            # code를 기반으로 원본 지점명(name)을 즉시 역조회할 수 있는 맵 구조 선언
            code_to_name = {s.code: s.name for s in station_records}
            
            data = []
            for _ in range(10):
                random_hour = random.randint(0, 23)
                # date와 time 문자열을 제거하고 정형화된 파이썬 내장 datetime 객체로 변환 통합
                measured_datetime = datetime(2026, 7, 14, random_hour, 0, 0)
                selected_code = random.choice(codes)
                
                wq_entry = WaterQuality(
                    measured_at=measured_datetime,
                    station_code=selected_code,
                    station_name_raw=code_to_name.get(selected_code, "미지정지점"), # 무결성 방어 필드 추가
                    water_temp=round(random.uniform(15.0, 25.0), 1),              # 신규 수온 필드 (기존 discharge 대체)
                    turbidity=round(random.uniform(0.1, 5.0), 2),
                    ph=round(random.uniform(6.5, 8.5), 2)                         # 신규 pH 필드 반영
                )
                data.append(wq_entry)
                
            session.add_all(data)
            session.commit()
            
        session.close()