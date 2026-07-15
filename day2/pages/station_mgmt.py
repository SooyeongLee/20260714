import os
import logging
import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QTableWidget, QTableWidgetItem, 
    QFormLayout, QLineEdit, QMessageBox, QAbstractItemView, QPushButton, QFileDialog
)
from sqlalchemy.exc import SQLAlchemyError
from models.schema import Station

logger = logging.getLogger("StationMgmt")

class StationMgmtPage(QWidget):
    def __init__(self, session):
        super().__init__()
        self.session = session
        
        # 전체 레이아웃 (수직 구조: 상단 버튼 바 + 하단 데이터 영역)
        main_layout = QVBoxLayout(self)
        
        # 1. 엑셀 업로드 / 내보내기 상단 버튼 바 영역
        button_bar_layout = QHBoxLayout()
        
        self.btn_excel_upload = QPushButton("엑셀 업로드")
        self.btn_excel_upload.clicked.connect(self.upload_excel)
        button_bar_layout.addWidget(self.btn_excel_upload)
        
        self.btn_excel_export = QPushButton("엑셀 내보내기")
        self.btn_excel_export.clicked.connect(self.export_excel)
        button_bar_layout.addWidget(self.btn_excel_export)
        
        # 버튼 바를 전체 레이아웃 상단에 정렬하여 배치
        button_bar_layout.addStretch()
        main_layout.addLayout(button_bar_layout)
        
        # 2. 하단 데이터 콘텐츠 영역 (기존 QWidget 구조 유지)
        content_layout = QHBoxLayout()
        
        # 테이블 그리드 생성 및 초기화
        self.st_table = QTableWidget(0, 5)
        self.st_table.setHorizontalHeaderLabels(["코드", "명칭", "위도", "경도", "비고"])
        self.st_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.st_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.st_table.cellClicked.connect(self.load_st_form)
        content_layout.addWidget(self.st_table, 2)
        
        # 입력 폼 구성
        f = QFormLayout()
        self.st_code = QLineEdit()
        self.st_name = QLineEdit()
        self.st_lat = QLineEdit()
        self.st_lon = QLineEdit()
        self.st_rem = QLineEdit()
        
        f.addRow("코드:", self.st_code)
        f.addRow("명칭:", self.st_name)
        f.addRow("위도:", self.st_lat)
        f.addRow("경도:", self.st_lon)
        f.addRow("비고:", self.st_rem)
        
        form_w = QWidget()
        form_w.setLayout(f)
        content_layout.addWidget(form_w, 1)
        
        main_layout.addLayout(content_layout)
        
        # 초기 그리드 리프레시
        self.refresh_st_grid()

    def refresh_st_grid(self):
        self.st_table.setRowCount(0)
        for s in self.session.query(Station).all():
            row = self.st_table.rowCount()
            self.st_table.insertRow(row)
            for i, val in enumerate([s.code, s.name, s.lat, s.lon, s.remarks]): 
                # None 데이터에 대해 빈 문자열 방어 처리
                display_val = "" if val is None else str(val)
                self.st_table.setItem(row, i, QTableWidgetItem(display_val))

    def load_st_form(self, row):
        # 빈 셀 클릭 시 발생할 수 있는 NoneType 에러 방어 적용
        self.st_code.setText(self.st_table.item(row, 0).text() if self.st_table.item(row, 0) else "")
        self.st_name.setText(self.st_table.item(row, 1).text() if self.st_table.item(row, 1) else "")
        self.st_lat.setText(self.st_table.item(row, 2).text() if self.st_table.item(row, 2) else "")
        self.st_lon.setText(self.st_table.item(row, 3).text() if self.st_table.item(row, 3) else "")
        self.st_rem.setText(self.st_table.item(row, 4).text() if self.st_table.item(row, 4) else "")

    def save_station(self):
        code = self.st_code.text().strip()
        if not code: 
            return
        
        # 중복 검사 후 신규 생성 혹은 기존 인스턴스 업데이트
        st = self.session.query(Station).filter_by(code=code).first() or Station(code=code)
        st.name = self.st_name.text().strip()
        
        # 수치형 변환 예외 안전 처리
        try:
            st.lat = float(self.st_lat.text()) if self.st_lat.text().strip() else None
            st.lon = float(self.st_lon.text()) if self.st_lon.text().strip() else None
        except ValueError:
            QMessageBox.warning(self, "오류", "위도와 경도는 유효한 숫자여야 합니다.")
            return
            
        st.remarks = self.st_rem.text().strip()
        
        self.session.add(st)
        self.session.commit()
        self.refresh_st_grid()
        self.clear_st_form()
        QMessageBox.information(self, "완료", "저장되었습니다.")

    def delete_station(self):
        code = self.st_code.text().strip()
        st = self.session.query(Station).filter_by(code=code).first()
        if st and QMessageBox.question(self, '삭제', '삭제하시겠습니까?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.session.delete(st)
            self.session.commit()
            self.refresh_st_grid()
            self.clear_st_form()

    def clear_st_form(self):
        for w in [self.st_code, self.st_name, self.st_lat, self.st_lon, self.st_rem]: 
            w.clear()

    # ==========================================
    # 💡 신규 구현: 엑셀 업로드 및 처리 비즈니스 로직
    # ==========================================
    def upload_excel(self):
        """
        xlsx, xls, csv 파일을 다이렉트로 분석 및 파싱하여 
        측정소(Station) 데이터를 유실 없이 DB에 병합(Upsert)합니다.
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "엑셀 파일 선택", 
            "", 
            "엑셀/CSV 파일 (*.xlsx *.xls *.csv);;Excel Files (*.xlsx *.xls);;CSV Files (*.csv)"
        )
        
        if not file_path:
            return  # 파일 선택 취소 시 조기 반환

        try:
            # 1. 확장자 분류별 판다스 엔진 다중 인스턴스 기동
            _, ext = os.path.splitext(file_path.lower())
            
            if ext == '.csv':
                # 인코딩 포맷 기본값 UTF-8 처리 및 실패 시 한글 완성형(EUC-KR/CP949) 폴백 방어
                try:
                    df = pd.read_csv(file_path, encoding='utf-8')
                except UnicodeDecodeError:
                    df = pd.read_csv(file_path, encoding='cp949')
            else:
                # Excel(.xlsx, .xls) 엔진 기동 (openpyxl 또는 xlrd 의존성 필요)
                df = pd.read_excel(file_path)

            # 2. 유저 정의 템플릿(river_stations) 표준 컬럼명 매핑 처리
            # 한글 컬럼 명칭 및 스키마 명칭을 유연하게 수용하기 위해 상호 매핑 딕셔너리 구축
            column_mapping = {
                "코드": "code", "측정소코드": "code", "station_code": "code", "code": "code",
                "명칭": "name", "측정소명칭": "name", "측정소명": "name", "station_name": "name", "name": "name",
                "위도": "lat", "latitude": "lat", "lat": "lat",
                "경도": "lon", "longitude": "lon", "lon": "lon",
                "비고": "remarks", "remarks": "remarks", "description": "remarks"
            }
            
            # 읽어 들인 데이터프레임 컬럼 표준 규격으로 일괄 변환
            df.columns = [col.strip() for col in df.columns]
            rename_dict = {col: column_mapping[col] for col in df.columns if col in column_mapping}
            df = df.rename(columns=rename_dict)

            # 필수 매핑 검사
            if 'code' not in df.columns or 'name' not in df.columns:
                QMessageBox.critical(
                    self, "오류", 
                    "템플릿 필수 헤더인 '코드(code)' 및 '명칭(name)' 필드가 누락되었습니다."
                )
                return

            inserted = 0
            updated = 0
            
            # 3. 트랜잭션 수립 및 Upsert 루프 실행
            for _, row in df.iterrows():
                # NaN 값을 포함하여 빈 공간 데이터 정제
                code_val = str(row['code']).strip() if pd.notna(row['code']) else ""
                
                # 코드값이 비어있을 경우 스킵 방어 처리
                if not code_val or code_val == "nan":
                    continue
                
                name_val = str(row['name']).strip() if pd.notna(row['name']) else ""
                
                lat_val = float(row['lat']) if 'lat' in df.columns and pd.notna(row['lat']) else None
                lon_val = float(row['lon']) if 'lon' in df.columns and pd.notna(row['lon']) else None
                remarks_val = str(row['remarks']).strip() if 'remarks' in df.columns and pd.notna(row['remarks']) else None

                # 중복 검사 후 신규 생성 또는 기존 데이터 오버라이트(Upsert)
                station = self.session.query(Station).filter_by(code=code_val).first()
                if station:
                    station.name = name_val
                    station.lat = lat_val
                    station.lon = lon_val
                    station.remarks = remarks_val
                    updated += 1
                else:
                    new_station = Station(
                        code=code_val,
                        name=name_val,
                        lat=lat_val,
                        lon=lon_val,
                        remarks=remarks_val
                    )
                    self.session.add(new_station)
                    inserted += 1

            # 최종 DB 반영 및 UI 동기화
            self.session.commit()
            self.refresh_st_grid()
            
            QMessageBox.information(
                self, "업로드 성공", 
                f"정상적으로 업로드가 완료되었습니다.\n(신규 추가: {inserted}건, 기존 변경: {updated}건)"
            )

        except SQLAlchemyError as db_err:
            self.session.rollback()
            logger.exception("엑셀 업로드 중 데이터베이스 트랜잭션 에러 발생")
            QMessageBox.critical(self, "DB 오류", f"데이터베이스 영속 처리 실패: {db_err}")
        except Exception as e:
            logger.exception("엑셀 임포트 중 시스템 에러 발생")
            QMessageBox.critical(self, "시스템 오류", f"파일을 분석하지 못했습니다.\n사유: {e}")

    # ==========================================
    # 💡 신규 구현: 엑셀 내보내기 비즈니스 로직
    # ==========================================
    def export_excel(self):
        """
        현재 DB 상의 모든 측정소 데이터를 정렬하여 xlsx 규격으로 로컬 디스크에 내보냅니다.
        """
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "엑셀 파일 저장", 
            "river_stations_export.xlsx", 
            "Excel Files (*.xlsx)"
        )
        
        if not file_path:
            return  # 파일 저장 취소 시 조기 반환

        try:
            # 1. 전체 측정소 마스터 데이터 조회
            stations = self.session.query(Station).order_by(Station.code).all()
            
            # 2. 판다스 변환용 데이터 구조 구축 (템플릿 컬럼 기준)
            export_data = []
            for s in stations:
                export_data.append({
                    "코드": s.code,
                    "명칭": s.name,
                    "위도": s.lat,
                    "경도": s.lon,
                    "비고": s.remarks
                })

            # 3. DataFrame 변환 및 파일 세이브 실행
            df = pd.DataFrame(export_data)
            
            # 판다스 내부 엑셀 저장기 실행 (openpyxl 필요)
            df.to_excel(file_path, index=False, sheet_name="측정소 리스트")
            
            QMessageBox.information(self, "내보내기 성공", f"성공적으로 엑셀 파일이 저장되었습니다.\n저장 경로: {file_path}")
            
        except Exception as e:
            logger.exception("엑셀 내보내기 수행 중 치명적 에러 발생")
            QMessageBox.critical(self, "오류", f"엑셀 파일을 내보낼 수 없습니다.\n사유: {e}")