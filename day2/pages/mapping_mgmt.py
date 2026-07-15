# pages/mapping_mgmt.py
import logging
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QFormLayout, QLineEdit, 
                             QMessageBox, QFileDialog, QLabel)
from PyQt6.QtCore import Qt
from services.mapping_service import MappingDataService

logger = logging.getLogger("MappingMgmt")

class MappingManagementPage(QWidget):
    def __init__(self, session):
        super().__init__()
        self.session = session
        self.mapping_service = MappingDataService(self.session)
        self.init_ui()
        self.load_mapping_grid() # 초기 구동 시 전체 조회 실행

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # ----------------------------------------------------------------------
        # Left Section: 그리드 데이터 리스트 뷰
        # ----------------------------------------------------------------------
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # 상단 유틸리티 버튼 컨트롤 바 (조회, 업로드, 다운로드만 유지)
        btn_bar = QHBoxLayout()
        self.btn_refresh = QPushButton("🔄 조회")
        self.btn_csv_import = QPushButton("📤 CSV 업로드")
        self.btn_excel_export = QPushButton("📥 엑셀 다운로드")
        
        self.btn_refresh.clicked.connect(self.load_mapping_grid)
        self.btn_csv_import.clicked.connect(self.handle_csv_import)
        self.btn_excel_export.clicked.connect(self.handle_excel_export)

        btn_bar.addWidget(self.btn_refresh)
        btn_bar.addWidget(self.btn_csv_import)
        btn_bar.addWidget(self.btn_excel_export)
        btn_bar.addStretch()
        left_layout.addLayout(btn_bar)

        # 데이터 세부 표출용 QTableWidget 구성
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["수질코드", "수질관측소명", "기상코드", "기상관측소명", "거리 (km)"])
        
        # PyQt6 네임스페이스 규칙 준수
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self.handle_row_selection)
        left_layout.addWidget(self.table)
        
        main_layout.addWidget(left_widget, stretch=7)

        # ----------------------------------------------------------------------
        # Right Section: 수정/입력 세부 폼 (Detail Form)
        # ----------------------------------------------------------------------
        right_widget = QWidget()
        right_widget.setStyleSheet("background-color: #F8F9FA; border: 1px solid #E0E0E0; border-radius: 6px;")
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(15, 15, 15, 15)

        right_layout.addWidget(QLabel("<h3>관측소 매핑 정보 편집</h3>"))
        
        form_layout = QFormLayout()
        self.txt_river_code = QLineEdit()
        self.txt_river_name = QLineEdit()
        self.txt_weather_code = QLineEdit()
        self.txt_weather_name = QLineEdit()
        self.txt_distance = QLineEdit()
        
        form_layout.addRow("수질관측소 코드:", self.txt_river_code)
        form_layout.addRow("수질관측소 명:", self.txt_river_name)
        form_layout.addRow("기상관측소 코드:", self.txt_weather_code)
        form_layout.addRow("기상관측소 명:", self.txt_weather_name)
        form_layout.addRow("연계 거리 (km):", self.txt_distance)
        right_layout.addLayout(form_layout)
        
        # 💡 [요청 반영] 기존에 존재하던 하단 버튼셋(초기화, 저장, 삭제)을 완벽히 제거했습니다.
        right_layout.addStretch()

        main_layout.addWidget(right_widget, stretch=3)

    def load_mapping_grid(self):
        """DB 내부 전체 매핑 세부 내역을 완전히 리로드하여 그리드에 바인딩합니다."""
        self.table.setRowCount(0)
        records = self.mapping_service.get_all_mappings()
        
        for row_idx, r in enumerate(records):
            self.table.insertRow(row_idx)
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(r.river_station_code)))
            self.table.setItem(row_idx, 1, QTableWidgetItem(str(r.river_station_name)))
            self.table.setItem(row_idx, 2, QTableWidgetItem(str(r.weather_station_code)))
            self.table.setItem(row_idx, 3, QTableWidgetItem(str(r.weather_station_name)))
            self.table.setItem(row_idx, 4, QTableWidgetItem(f"{r.distance_km:.4f}"))

    def handle_row_selection(self):
        """그리드 행 선택 시 디테일 폼 필드로 데이터를 정형화하여 이관합니다."""
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return
        row = selected_rows[0].row()
        
        self.txt_river_code.setText(self.table.item(row, 0).text())
        self.txt_river_code.setReadOnly(True)  # 수정 시 식별 키 잠금 처리
        self.txt_river_name.setText(self.table.item(row, 1).text())
        self.txt_weather_code.setText(self.table.item(row, 2).text())
        self.txt_weather_name.setText(self.table.item(row, 3).text())
        self.txt_distance.setText(self.table.item(row, 4).text())

    def clear_form(self):
        """[main.py 공용 신규 버튼 연동] 입력 필드를 리셋하여 신규 레코드 생성 준비를 합니다."""
        self.txt_river_code.clear()
        self.txt_river_code.setReadOnly(False)
        self.txt_river_name.clear()
        self.txt_weather_code.clear()
        self.txt_weather_name.clear()
        self.txt_distance.clear()
        self.table.clearSelection()

    def save_mapping(self):
        """[main.py 공용 저장 버튼 연동] 화면 입력 정보의 스키마 유효성을 검증하고 저장을 이행합니다."""
        data = {
            'river_station_code': self.txt_river_code.text().strip(),
            'river_station_name': self.txt_river_name.text().strip(),
            'weather_station_code': self.txt_weather_code.text().strip(),
            'weather_station_name': self.txt_weather_name.text().strip(),
            'distance_km': self.txt_distance.text().strip()
        }

        if not all(data.values()):
            QMessageBox.warning(self, "입력 누락", "모든 매핑 세부 필드 항목을 빠짐없이 입력해야 합니다.")
            return

        try:
            int(data['weather_station_code'])
            float(data['distance_km'])
        except ValueError:
            QMessageBox.warning(self, "유형 오류", "기상코드(정수) 및 연계 거리(실수) 형식을 준수하십시오.")
            return

        if self.mapping_service.save_mapping_record(data):
            QMessageBox.information(self, "저장 성공", "관측소 연계 매핑 데이터가 데이터베이스에 반영되었습니다.")
            self.load_mapping_grid()
            self.clear_form()
        else:
            QMessageBox.critical(self, "저장 실패", "데이터베이스 트랜잭션 도중 오류가 발생했습니다.")

    def delete_mapping(self):
        """[main.py 공용 삭제 버튼 연동] 선택된 식별 키 레코드 영구 삭제 로직을 수행합니다."""
        river_code = self.txt_river_code.text().strip()
        if not river_code:
            QMessageBox.warning(self, "선택 누락", "삭제할 대상을 그리드에서 먼저 선택하십시오.")
            return

        confirm = QMessageBox.question(
            self, "삭제 확인", f"수질관측소 코드 [{river_code}] 매핑 내역을 정말 삭제하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirm == QMessageBox.StandardButton.Yes:
            if self.mapping_service.delete_mapping_record(river_code):
                QMessageBox.information(self, "삭제 성공", "매핑 데이터가 성공적으로 파기되었습니다.")
                self.load_mapping_grid()
                self.clear_form()
            else:
                QMessageBox.critical(self, "삭제 실패", "삭제 트랜잭션 처리 중 오류가 발생했습니다.")

    def handle_csv_import(self):
        """제시된 CSV 포맷의 파일을 읽어 대량의 매핑 내역을 안전하게 업서트합니다."""
        file_path, _ = QFileDialog.getOpenFileName(self, "CSV 매핑 양식 파일 오픈", "", "CSV Files (*.csv)")
        if not file_path:
            return

        result = self.mapping_service.import_csv_mapping(file_path)
        if result["status"] == "SUCCESS":
            QMessageBox.information(
                self, "업로드 완료", 
                f"정형 CSV 양식 연동이 완료되었습니다!\n총 {result['count']}건의 세부 데이터 전체가 성공적으로 적재되었습니다."
            )
            self.load_mapping_grid()
        else:
            QMessageBox.critical(self, "업로드 실패", result["message"])

    def handle_excel_export(self):
        """현재 그리드 상태 기준 전체 데이터를 엑셀 파일로 내보냅니다."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "매핑 내역 엑셀 저장", "station_weather_mapping_report.xlsx", "Excel Files (*.xlsx)"
        )
        if not file_path:
            return

        result = self.mapping_service.export_mapping_to_excel(file_path)
        if result["status"] == "SUCCESS":
            QMessageBox.information(self, "내보내기 성공", f"엑셀 파일 저장이 완료되었습니다. (총 {result['count']}건 전체 출력)")
        else:
            QMessageBox.critical(self, "내보내기 실패", f"오류 원인: {result.get('error', 'Unknown Error')}")