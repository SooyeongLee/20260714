# services/mapping_service.py
import logging
import pandas as pd
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError
from models.schema import StationWeatherMapping

logger = logging.getLogger("WaterSyncSystem")

class MappingDataService:
    def __init__(self, db_session):
        self.session = db_session

    def get_all_mappings(self) -> list:
        """모든 매핑 데이터를 조회하여 반환합니다. (요약 없음)"""
        try:
            return self.session.query(StationWeatherMapping)\
                               .order_by(StationWeatherMapping.river_station_code.asc())\
                               .all()
        except SQLAlchemyError as e:
            logger.error(f"[매핑 서비스] 전체 조회 실패: {str(e)}")
            return []

    def save_mapping_record(self, data: dict) -> bool:
        """단건 매핑 데이터를 저장하거나 수정합니다."""
        try:
            # 기존 레코드 존재 여부 검증 (수질관측소 코드를 Primary Key 또는 고유 식별자로 가정)
            record = self.session.query(StationWeatherMapping)\
                                 .filter(StationWeatherMapping.river_station_code == data['river_station_code'])\
                                 .first()
            
            if record:
                # 수정 (Update)
                record.river_station_name = data['river_station_name']
                record.weather_station_code = int(data['weather_station_code'])
                record.weather_station_name = data['weather_station_name']
                record.distance_km = float(data['distance_km'])
                record.updated_at = datetime.now()
            else:
                # 신규 추가 (Insert)
                record = StationWeatherMapping(
                    river_station_code=data['river_station_code'],
                    river_station_name=data['river_station_name'],
                    weather_station_code=int(data['weather_station_code']),
                    weather_station_name=data['weather_station_name'],
                    distance_km=float(data['distance_km']),
                    updated_at=datetime.now()
                )
                self.session.add(record)
                
            self.session.commit()
            return True
        except Exception as e:
            self.session.rollback()
            logger.error(f"[매핑 서비스] 단건 저장 실패: {str(e)}")
            return False

    def delete_mapping_record(self, river_station_code: str) -> bool:
        """특정 수질관측소의 매핑 레코드를 삭제합니다."""
        try:
            record = self.session.query(StationWeatherMapping)\
                                 .filter(StationWeatherMapping.river_station_code == river_station_code)\
                                 .first()
            if record:
                self.session.delete(record)
                self.session.commit()
                return True
            return False
        except Exception as e:
            self.session.rollback()
            logger.error(f"[매핑 서비스] 삭제 실패: {str(e)}")
            return False

    def import_csv_mapping(self, file_path: str) -> dict:
        """
        제시된 csv 양식을 파싱하여 데이터 유실 없이 DB에 일괄 반영합니다 (Upsert).
        양식 스키마: river_station_code, river_station_name, weather_station_code, weather_station_name, distance_km
        """
        try:
            df = pd.read_csv(file_path, encoding='utf-8')
        except UnicodeDecodeError:
            try:
                df = pd.read_csv(file_path, encoding='cp949')
            except Exception as e:
                return {"status": "FAIL", "message": f"CSV 파일 인코딩 오류: {str(e)}"}
        
        # 1. 스키마 정합성 필수 검증
        required_cols = ['river_station_code', 'river_station_name', 'weather_station_code', 'weather_station_name', 'distance_km']
        if not all(col in df.columns for col in required_cols):
            return {"status": "FAIL", "message": "CSV 파일 양식이 일치하지 않습니다. 필수 컬럼을 확인하세요."}
        
        success_count = 0
        try:
            for _, row in df.iterrows():
                # 데이터 유효성 정제 및 업서트 데이터 바인딩
                mapping_data = {
                    'river_station_code': str(row['river_station_code']).strip(),
                    'river_station_name': str(row['river_station_name']).strip(),
                    'weather_station_code': int(row['weather_station_code']),
                    'weather_station_name': str(row['weather_station_name']).strip(),
                    'distance_km': float(row['distance_km'])
                }
                
                # 내부 저장 로직 호출을 통한 무결성 처리
                record = self.session.query(StationWeatherMapping)\
                                     .filter(StationWeatherMapping.river_station_code == mapping_data['river_station_code'])\
                                     .first()
                if record:
                    record.river_station_name = mapping_data['river_station_name']
                    record.weather_station_code = mapping_data['weather_station_code']
                    record.weather_station_name = mapping_data['weather_station_name']
                    record.distance_km = mapping_data['distance_km']
                    record.updated_at = datetime.now()
                else:
                    new_rec = StationWeatherMapping(
                        river_station_code=mapping_data['river_station_code'],
                        river_station_name=mapping_data['river_station_name'],
                        weather_station_code=mapping_data['weather_station_code'],
                        weather_station_name=mapping_data['weather_station_name'],
                        distance_km=mapping_data['distance_km'],
                        updated_at=datetime.now()
                    )
                    self.session.add(new_rec)
                success_count += 1
                
            self.session.commit()
            return {"status": "SUCCESS", "count": success_count}
        except Exception as e:
            self.session.rollback()
            logger.error(f"[매핑 서비스] CSV 일괄 파싱 및 적재 중 예외 발생: {str(e)}")
            return {"status": "FAIL", "message": f"데이터 적재 중 오류 발생: {str(e)}"}

    def export_mapping_to_excel(self, file_path: str) -> dict:
        """(기존 기능 유지) 모든 매핑 내역을 엑셀 파일로 출력"""
        try:
            records = self.get_all_mappings()
            if not records:
                return {"status": "EMPTY", "count": 0, "message": "내보낼 매핑 데이터가 없습니다."}
            
            export_data = [{
                "수질관측소 코드": r.river_station_code,
                "수질관측소 명": r.river_station_name,
                "기상관측소 코드": r.weather_station_code,
                "기상관측소 명": r.weather_station_name,
                "거리 (km)": r.distance_km,
                "최종 갱신일시": r.updated_at.strftime('%Y-%m-%d %H:%M:%S') if r.updated_at else "N/A"
            } for r in records]
            
            df = pd.DataFrame(export_data)
            df.to_excel(file_path, index=False, sheet_name="관측소 매핑 내역")
            return {"status": "SUCCESS", "count": len(export_data)}
        except Exception as e:
            logger.error(f"[매핑 서비스] 엑셀 내보내기 실패: {str(e)}")
            return {"status": "FAIL", "error": str(e)}