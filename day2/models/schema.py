from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Index, func
from sqlalchemy.orm import declarative_base, relationship
# schemas.py (Pydantic Validation Schema)
from pydantic import BaseModel, Field, validator
from typing import Optional, List


Base = declarative_base()

class Station(Base):
    """
    측정소 정보 테이블 (river_stations.csv 매핑)
    """
    __tablename__ = 'stations'

    # 측정소 고유 코드 (Primary Key)
    code = Column(String(50), primary_key=True, comment="측정소코드")
    
    # 측정소 이름 (물환경 정보 시스템 연계용 고유 필드 스펙 정의)
    name = Column(String(100), nullable=False, index=True, comment="측정소명칭")
    
    # 지리 정보 데이터 스펙
    lat = Column(Float, nullable=True, comment="위도")
    lon = Column(Float, nullable=True, comment="경도")
    
    # 하천구역 및 추가 메타데이터
    river_basin = Column(String(100), nullable=True, comment="하천유역")
    remarks = Column(String(500), nullable=True, comment="비고")

    # 역방향 참조 관계설정 (1:N)
    water_qualities = relationship("WaterQuality", back_populates="station", cascade="all, delete-orphan")


class WaterQuality(Base):
    """
    수질 측정 시계열 데이터 테이블 (wq.csv 매핑)
    """
    __tablename__ = 'water_data'

    # 영속성 컨텍스트 관리를 위한 고유 PK
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 원본 파일의 '측정시간' 통합 처리를 위한 DateTime 스펙 정의 
    # (SQLite/PostgreSQL 등 DB 이식성을 위해 데이터 가공 시 파싱하여 DateTime으로 저장하는 것을 권장)
    measured_at = Column(DateTime, nullable=False, index=True, comment="측정시간")
    
    # stations 테이블과의 논리적/물리적 FK 연계 (물리 제약이 필요 없을 경우 application level 연계)
    station_code = Column(String(50), ForeignKey('stations.code', ondelete='CASCADE'), nullable=True, comment="측정소코드 연계")
    
    # wq.csv 파일 내 데이터의 이름 매핑 보존을 위한 원본 지점명 컬럼
    station_name_raw = Column(String(100), nullable=False, index=True, comment="지점명(원본)")

    # 측정 수질 통계 필드
    water_temp = Column(Float, nullable=True, comment="수온(℃)")
    turbidity = Column(Float, nullable=True, comment="탁도(NTU)")
    ph = Column(Float, nullable=True, comment="pH")

    # 순방향 참조 관계설정
    station = relationship("Station", back_populates="water_qualities")


class WeatherStation(Base):
    """
    기상청 관측소 정보 테이블 (standardized_weather_stations.csv 매핑)
    """
    __tablename__ = 'weather_stations'

    # 관측소 고유 지점 코드 (Primary Key)
    code = Column(String(50), primary_key=True, comment="관측소지점코드")
    
    # 관측소 명칭
    name = Column(String(100), nullable=False, index=True, comment="관측소명칭")
    
    # 지리 정보 데이터 스펙
    lat = Column(Float, nullable=True, comment="위도")
    lon = Column(Float, nullable=True, comment="경도")
    
    # 상위 관리 조직 또는 소속 지청명
    river_basin = Column(String(100), nullable=True, comment="관리관서/권역")
    
    # 설치 시작일, 지점 주소, 해발고도 등의 복합 메타데이터 보존용 
    remarks = Column(String(500), nullable=True, comment="상세메타데이터(설치일/주소/고도)")

    # 지리적 인덱스 최적화 (위도/경도 기반 쿼리 속도 보장)
    __table_args__ = (
        Index('ix_weather_stations_coordinates', 'lat', 'lon'),
    )

# 시계열 조회 쿼리 최적화를 위한 복합 인덱스(Composite Index) 구성
# 특정 측정소의 특정 기간 데이터 조회 속도를 비약적으로 향상시킵니다.
Index('ix_water_data_station_date', WaterQuality.station_code, WaterQuality.measured_at)
Index('ix_water_data_name_date', WaterQuality.station_name_raw, WaterQuality.measured_at)


class StationWeatherMapping(Base):
    __tablename__ = "station_weather_mapping"

    # 복합 기본키 또는 수질 관측소 코드를 기본키로 지정
    river_station_code = Column(String(50), primary_key=True, index=True, comment="수질관측소 코드")
    river_station_name = Column(String(100), nullable=False, comment="수질관측소 명")
    weather_station_code = Column(Integer, nullable=False, comment="기상관측소 코드")
    weather_station_name = Column(String(100), nullable=False, comment="기상관측소 명")
    distance_km = Column(Float, nullable=False, comment="거리 (km)")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

class MappingBase(BaseModel):
    river_station_code: str = Field(..., description="수질 관측소 코드 (예: S01001)")
    river_station_name: str = Field(..., description="수질 관측소명")
    weather_station_code: int = Field(..., description="기상 관측소 코드")
    weather_station_name: str = Field(..., description="기상 관측소명")
    distance_km: float = Field(..., ge=0.0, description="거리 (km)")

    @validator('river_station_code')
    def validate_river_code(cls, v):
        if not v.strip():
            raise ValueError("수질 관측소 코드는 빈 값일 수 없습니다.")
        return v.strip()

class MappingResponse(MappingBase):
    class Config:
        orm_mode = True

class CommonResponse(BaseModel):
    success: bool
    message: str
    errors: Optional[List[str]] = None
    
    
