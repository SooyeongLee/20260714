# services/water_sync_service.py
import logging
import requests
import urllib.parse
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError

# 실제 정의되어 있는 유저 스키마 모델 임포트 적용
from models.schema import Station, WaterQuality  

# 1. 시스템 전역 로깅 파이프라인 구성
logger = logging.getLogger("WaterSyncSystem")
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s')

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

file_handler = logging.FileHandler("app.log", encoding="utf-8")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


class WaterDataSyncService:
    """
    공공데이터포털 수질 데이터 Open API(JSON 규격)와 연동하여 
    로컬 SQLite 데이터베이스에 데이터를 동기화하는 백그라운드 서비스 클래스
    """
    def __init__(self, db_service, service_key: str):
        self.db_service = db_service
        self.service_key = service_key
        self.api_url = "https://apis.data.go.kr/1480523/WaterQualityService/getRealTimeWaterQualityList"

    def fetch_and_sync(self, start_date: str, end_date: str, num_of_rows: int = 9990, progress_callback=None) -> dict:
        """
        성공 데이터 템플릿(SITE_NAME, SITE_ID, MSR_DATE, M02, M73, M70) 구조를 파싱하여
        지점명과 지점코드를 완벽히 바인딩한 후 WaterQuality 테이블 스키마에 적재합니다.
        """
        logger.info(f"동기화 작업 개시 (기간: {start_date} ~ {end_date}, 요청 제한 행수: {num_of_rows})")
        
        if progress_callback:
            progress_callback(10)

        try:
            decoded_key = urllib.parse.unquote(self.service_key)
        except Exception:
            decoded_key = self.service_key

        params = {
            "serviceKey": decoded_key,
            "pageNo": 1,
            "numOfRows": num_of_rows,
            "resultType": "JSON",
            "startDate": start_date,
            "endDate": end_date
        }

        try:
            logger.debug(f"API 요청 송신 (JSON 규격) - URL: {self.api_url}")
            
            response = requests.get(self.api_url, params=params, timeout=30)
            response.raise_for_status()
            
            logger.debug(f"API 응답 수신 성공 (HTTP 상태 코드: {response.status_code})")

            if progress_callback:
                progress_callback(40)

            data = response.json()
            raw_items = data.get('getRealTimeWaterQualityList', {}).get('item', [])
            
            # API 반환 포맷 표준 방어 코드
            if not raw_items and 'response' in data:
                body_node = data.get('response', {}).get('body', {})
                items_container = body_node.get('items', [])
                if isinstance(items_container, dict) and 'item' in items_container:
                    raw_items = items_container['item']
                elif isinstance(items_container, list):
                    raw_items = items_container

            if not isinstance(raw_items, list):
                raw_items = [raw_items] if raw_items else []

            logger.info(f"데이터 파싱 성공. 최종 추출 건수: {len(raw_items)}건")
            
            if not raw_items:
                logger.info("조회 기간 내에 연동할 유효 데이터가 전혀 존재하지 않습니다.")
                if progress_callback:
                    progress_callback(100)
                return {"status": "SUCCESS", "inserted": 0, "skipped": 0}

            # 2. 데이터베이스 적재 및 트랜잭션 수립 단계 (45% ~ 95%)
            if progress_callback:
                progress_callback(45)

            session = self.db_service.get_session()
            
            # FK 정합성 유지 및 동적 갱신을 위해 DB에 등록되어 있는 기존 측정소 코드 캐싱 {code: name}
            existing_stations = set()
            try:
                station_records = session.query(Station.code).all()
                existing_stations = {row.code for row in station_records}
            except Exception as st_err:
                logger.warning(f"측정소 마스터 테이블 사전 조회 실패: {st_err}")

            inserted_count = 0
            skipped_count = 0
            total_items = len(raw_items)

            for idx, item in enumerate(raw_items):
                try:
                    site_name = item.get("SITE_NAME")
                    site_id = item.get("SITE_ID")  # API 원본 데이터에 제공되는 지점코드 직접 획득
                    msr_date_str = item.get("MSR_DATE")
                    
                    if not site_name or not msr_date_str:
                        continue

                    # 지점코드가 없을 경우 방어 처리 및 지점명 정제
                    site_name = site_name.strip()
                    site_id = str(site_id).strip() if site_id is not None else None

                    # 날짜 문자열 데이터타입 포맷 파싱 (유저의 '%Y-%m-%d' 형태를 최우선 순위로 파싱)
                    msr_date_str = msr_date_str.strip()
                    try:
                        measured_at_dt = datetime.strptime(msr_date_str, '%Y-%m-%d')
                    except ValueError:
                        try:
                            measured_at_dt = datetime.strptime(msr_date_str, '%Y-%m-%d %H:%M')
                        except ValueError:
                            try:
                                measured_at_dt = datetime.strptime(msr_date_str, '%Y%m%d%H%M%S')
                            except ValueError:
                                measured_at_dt = datetime.strptime(msr_date_str, '%Y%m%d%H%M')

                    # 데이터 타입 캐스팅 및 정제 (M70: pH, M73: 탁도, M02: 수온)
                    ph_val = float(item.get("M70")) if item.get("M70") is not None else None
                    turbidity_val = float(item.get("M73")) if item.get("M73") is not None else None
                    temp_val = float(item.get("M02")) if item.get("M02") is not None else None

                    # 💡 [핵심 교정부] 동적 측정소 마스터 생성 기능
                    # 가져온 데이터의 지점코드(site_id)가 마스터 테이블에 없다면 자동으로 추가하여 FK 에러를 원천 차단합니다.
                    if site_id and site_id not in existing_stations:
                        try:
                            # 세션 내부 존재 유무 한 번 더 체크 (루프 도중 중복 세션 인젝션 에러 차단)
                            db_station = session.query(Station).filter_by(code=site_id).first()
                            if not db_station:
                                new_station = Station(
                                    code=site_id,
                                    name=site_name,
                                    remarks="API 연동 시 자동 동기화 생성됨"
                                )
                                session.add(new_station)
                                session.flush()  # ID 충돌 방지를 위해 캐시 동기화
                                existing_stations.add(site_id)
                                logger.info(f"신규 측정소 자동 마스터 등록 완료: [{site_id}] {site_name}")
                        except Exception as station_ins_err:
                            logger.warning(f"신규 측정소 자동 등록 중 일시적 무시: {station_ins_err}")

                    # 3. 멱등성 보장을 위한 DB 내 중복 측정값 조회 수행
                    # (지점명 원본 및 측정 일시 기준 복합 인덱스 타겟 질의)
                    existing_record = session.query(WaterQuality).filter_by(
                        station_name_raw=site_name, 
                        measured_at=measured_at_dt
                    ).first()
                    
                    if existing_record:
                        # 이미 존재하는 레코드의 경우, 지점코드 매핑이 누락되어 있었다면 보정 처리 수행
                        if site_id and not existing_record.station_code:
                            existing_record.station_code = site_id
                        skipped_count += 1
                    else:
                        # 4. 유저 스키마 구조인 WaterQuality 테이블에 완벽히 매핑하여 인젝션
                        new_record = WaterQuality(
                            station_name_raw=site_name,
                            station_code=site_id,  # API에서 획득한 코드를 직접 다이렉트 매핑하여 저장
                            measured_at=measured_at_dt,
                            ph=ph_val,
                            turbidity=turbidity_val,
                            water_temp=temp_val
                        )
                        session.add(new_record)
                        inserted_count += 1

                except (ValueError, KeyError) as parse_err:
                    logger.warning(f"개별 데이터 파싱 실패로 스킵 - 데이터: {item} / 사유: {parse_err}")
                    skipped_count += 1
                    continue

                if progress_callback and total_items > 0:
                    current_percent = int(45 + (idx / total_items) * 50)
                    progress_callback(min(95, current_percent))

            # 최종 DB Commit 반영
            session.commit()
            logger.info(f"데이터베이스 원격 적재 최종 완료 (커밋 반영: {inserted_count}건, 자동 생성된 마스터 포함 / 중복 스킵: {skipped_count}건)")

            if progress_callback:
                progress_callback(100)

            return {
                "status": "SUCCESS",
                "inserted": inserted_count,
                "skipped": skipped_count
            }

        except requests.exceptions.RequestException as net_err:
            logger.exception("API 서버 통신 중 네트워크 연결 오류 발생")
            return {"status": "FAIL", "inserted": 0, "skipped": 0, "error": f"Network Error: {net_err}"}
        except SQLAlchemyError as db_err:
            logger.exception("데이터베이스 트랜잭션 커밋 중 오류 발생 (Rollback 수행)")
            if 'session' in locals():
                session.rollback()
            return {"status": "FAIL", "inserted": 0, "skipped": 0, "error": f"DB Error: {db_err}"}
        except Exception as general_err:
            logger.exception("예상치 못한 시스템 레벨 예외 발생")
            if 'session' in locals():
                session.rollback()
            return {"status": "FAIL", "inserted": 0, "skipped": 0, "error": f"System Crash: {general_err}"}
        
    def reset_water_data_only(self) -> bool:
        """
        수질 시계열 데이터(water_data)만 전체 삭제합니다. (측정소 마스터는 유지)
        """
        session = self.db_service.get_session()
        try:
            logger.warning("데이터베이스 수질 시계열 데이터(WaterQuality) 초기화 프로세스 개시")
            session.query(WaterQuality).delete()
            session.commit()
            logger.info("수질 시계열 데이터 초기화 완료")
            return True
        except SQLAlchemyError as db_err:
            session.rollback()
            logger.exception(f"수질 시계열 데이터 초기화 중 에러 발생: {db_err}")
            return False

    def reset_all_data(self) -> bool:
        """
        수질 시계열 데이터와 측정소 마스터(Station)를 포함한 전체 데이터를 완전 삭제합니다.
        """
        session = self.db_service.get_session()
        try:
            logger.warning("데이터베이스 전체 데이터(WaterQuality, Station) 공장 초기화 프로세스 개시")
            # 외래키 제약조건(CASCADE)에 의해 연결된 수질 데이터가 함께 처리되거나 
            # 무결성 에러를 방지하기 위해 자식 테이블인 WaterQuality부터 먼저 삭제합니다.
            session.query(WaterQuality).delete()
            session.query(Station).delete()
            session.commit()
            logger.info("전체 데이터 공장 초기화 완료")
            return True
        except SQLAlchemyError as db_err:
            session.rollback()
            logger.exception(f"전체 데이터 초기화 중 에러 발생: {db_err}")
            return False       