import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel, QPushButton,
    QLineEdit, QComboBox, QFormLayout, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

class DamWaterQualityApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("댐 수질 통합 관리 시스템")
        self.setGeometry(100, 100, 1300, 850)
        
        # 데이터 관리 상태 변수 (현재 선택된 테이블 행의 인덱스 저장)
        self.selected_row_idx = -1
        
        # UI 초기화
        self.init_ui()
        
        # 초기 목업 데이터 로드 (이미지 상의 23개 행 완전 구현)
        self.load_initial_data()

    def init_ui(self):
        # 중앙 기본 위젯 설정
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 메인 레이아웃 (수직 구조: 상단 바 + 본문 영역)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)
        
        # -------------------------------------------------------------
        # 1. 상단 바 (Header Bar) 영역
        # -------------------------------------------------------------
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 5)
        
        # 상단 좌측: 햄버거 메뉴 아이콘 및 타이틀
        title_layout = QHBoxLayout()
        title_layout.setSpacing(10)
        
        menu_btn = QLabel("☰")
        menu_btn.setStyleSheet("font-size: 18px; color: #333333; font-weight: bold;")
        
        title_label = QLabel("댐 수질 통합 관리 시스템")
        title_font = QFont("맑은 고딕", 13)
        title_font.setBold(True)
        title_label.setFont(title_font)
        
        title_layout.addWidget(menu_btn)
        title_layout.addWidget(title_label)
        header_layout.addLayout(title_layout)
        
        header_layout.addStretch() # 중간 공백 생성
        
        # 상단 우측: 기능 제어 버튼군
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)
        
        self.btn_new = QPushButton("📄 신규")
        self.btn_save = QPushButton("💾 저장")
        self.btn_delete = QPushButton("🗑️ 삭제")
        self.btn_exit = QPushButton("❌ 종료")
        
        # 버튼 시그널 연결
        self.btn_new.clicked.connect(self.on_new_clicked)
        self.btn_save.clicked.connect(self.on_save_clicked)
        self.btn_delete.clicked.connect(self.on_delete_clicked)
        self.btn_exit.clicked.connect(self.close)
        
        for btn in [self.btn_new, self.btn_save, self.btn_delete, self.btn_exit]:
            btn_layout.addWidget(btn)
            
        header_layout.addLayout(btn_layout)
        main_layout.addWidget(header_widget)
        
        # 구분선 추가
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("color: #e0e0e0;")
        main_layout.addWidget(divider)
        
        # -------------------------------------------------------------
        # 2. 본문 영역 (좌측 메뉴 + 중앙 테이블 + 우측 수정 폼)
        # -------------------------------------------------------------
        content_layout = QHBoxLayout()
        content_layout.setSpacing(15)
        
        # 2-1. 좌측 사이드바 네비게이션
        sidebar_widget = QWidget()
        sidebar_widget.setFixedWidth(150)
        sidebar_layout = QVBoxLayout(sidebar_widget)
        sidebar_layout.setContentsMargins(0, 10, 0, 10)
        sidebar_layout.setSpacing(15)
        
        # 사이드바 메뉴 버튼 목록
        menus = ["대시보드", "지점 관리", "수질 데이터 관리", "환경 설정"]
        self.menu_buttons = []
        for menu_name in menus:
            btn = QPushButton(menu_name)
            btn.setObjectName("sidebarBtn")
            # "수질 데이터 관리"가 현재 활성화된 탭이므로 스타일 강조를 위해 동적 속성 부여
            if menu_name == "수질 데이터 관리":
                btn.setProperty("active", True)
            else:
                btn.setProperty("active", False)
            sidebar_layout.addWidget(btn)
            self.menu_buttons.append(btn)
            
        sidebar_layout.addStretch() # 메뉴 하단 공백 처리
        content_layout.addWidget(sidebar_widget)
        
        # 수직 구분선
        v_divider_1 = QFrame()
        v_divider_1.setFrameShape(QFrame.Shape.VLine)
        v_divider_1.setStyleSheet("color: #e0e0e0;")
        content_layout.addWidget(v_divider_1)
        
        # 2-2. 중앙 수질 데이터 테이블 영역
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["ID", "날짜", "시간", "코드", "유량", "탁도"])
        
        # 테이블 헤더 속성 조정 (균등 배분 및 정렬 설정)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.cellClicked.connect(self.on_table_cell_clicked) # 데이터 클릭 바인딩
        
        content_layout.addWidget(self.table, stretch=3)
        
        # 2-3. 우측 상세 정보 입력/편집 폼 레이아웃
        right_panel = QWidget()
        right_panel.setFixedWidth(300)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(15, 10, 10, 10)
        
        form_layout = QFormLayout()
        form_layout.setSpacing(12)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        
        # 입력 필드 위젯 선언
        self.input_id = QLineEdit()
        self.input_id.setReadOnly(True) # ID는 기본 키(PK) 성격을 띠므로 임의 편집 불가 처리
        self.input_id.setPlaceholderText("자동 생성")
        
        self.input_date = QLineEdit()
        self.input_time = QLineEdit()
        
        self.combo_code = QComboBox()
        self.combo_code.addItems(["S001", "S002", "S003", "S004", "S005"])
        
        self.input_flow = QLineEdit()
        self.input_turbidity = QLineEdit()
        
        # 폼 레이아웃에 위젯 등록
        form_layout.addRow("ID:", self.input_id)
        form_layout.addRow("날짜:", self.input_date)
        form_layout.addRow("시간:", self.input_time)
        form_layout.addRow("코드:", self.combo_code)
        form_layout.addRow("유량:", self.input_flow)
        form_layout.addRow("탁도:", self.input_turbidity)
        
        right_layout.addLayout(form_layout)
        right_layout.addStretch() # 폼 하단 여백 채우기
        
        content_layout.addWidget(right_panel, stretch=1)
        main_layout.addLayout(content_layout)
        
        # -------------------------------------------------------------
        # 3. 전역 스타일시트 디자인 정의 (QSS)
        # -------------------------------------------------------------
        self.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
                color: #333333;
                font-family: '맑은 고딕', 'Segoe UI', sans-serif;
            }
            /* 상단 및 제어 버튼 스타일 */
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #dcdcdc;
                border-radius: 4px;
                padding: 6px 14px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f5f5f5;
                border-color: #cccccc;
            }
            QPushButton:pressed {
                background-color: #e9e9e9;
            }
            /* 좌측 사이드바 전용 스타일 */
            QPushButton#sidebarBtn {
                border: none;
                background-color: transparent;
                text-align: left;
                padding: 10px 15px;
                font-size: 14px;
                font-weight: normal;
                border-radius: 4px;
            }
            QPushButton#sidebarBtn:hover {
                background-color: #f0f0f0;
            }
            QPushButton#sidebarBtn[active="true"] {
                color: #0056b3;
                font-weight: bold;
                background-color: #f0f7ff;
            }
            /* 테이블 스타일 정의 */
            QTableWidget {
                border: 1px solid #e0e0e0;
                gridline-color: #f1f1f1;
                font-size: 12px;
                selection-background-color: #e8f0fe;
                selection-color: #000000;
            }
            QHeaderView::section {
                background-color: #ffffff;
                padding: 8px;
                border: 1px solid #e0e0e0;
                font-weight: bold;
                color: #555555;
            }
            /* 입력 편집 폼 스타일 */
            QLineEdit, QComboBox {
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 6px;
                font-size: 13px;
                background-color: #ffffff;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #0056b3;
            }
            QLineEdit:read-only {
                background-color: #f5f5f5;
                color: #888888;
            }
        """)

    def load_initial_data(self):
        """실제 이미지 내부의 23개 행 데이터를 그대로 복원하여 로드"""
        raw_data = [
            ["1", "2026-07-14", "08:00", "S001", "114.72", "2.69"],
            ["2", "2026-07-14", "18:00", "S005", "198.02", "0.87"],
            ["3", "2026-07-14", "12:00", "S005", "90.25", "0.25"],
            ["4", "2026-07-14", "18:00", "S001", "137.36", "4.53"],
            ["5", "2026-07-14", "22:00", "S001", "165.75", "1.4"],
            ["6", "2026-07-14", "09:00", "S002", "72.74", "3.21"],
            ["7", "2026-07-14", "12:00", "S005", "167.59", "0.96"],
            ["8", "2026-07-14", "01:00", "S004", "192.64", "4.15"],
            ["9", "2026-07-14", "01:00", "S003", "41.7", "1.29"],
            ["10", "2026-07-14", "18:00", "S003", "93.43", "2.31"],
            ["11", "2026-07-14", "19:00", "S002", "165.72", "1.34"],
            ["12", "2026-07-14", "10:00", "S004", "156.31", "1.13"],
            ["13", "2026-07-14", "06:00", "S005", "71.32", "3.62"],
            ["14", "2026-07-14", "20:00", "S005", "174.69", "3.37"],
            ["15", "2026-07-14", "06:00", "S002", "24.89", "2.54"],
            ["16", "2026-07-14", "20:00", "S001", "185.04", "0.57"],
            ["17", "2026-07-14", "12:00", "S005", "54.99", "4.52"],
            ["18", "2026-07-14", "21:00", "S004", "62.93", "0.29"],
            ["19", "2026-07-14", "11:00", "S005", "132.87", "3.11"],
            ["20", "2026-07-14", "19:00", "S001", "38.16", "3.64"],
            ["21", "2026-07-14", "10:00", "S005", "109.45", "4.84"],
            ["22", "2026-07-14", "14:00", "S002", "32.57", "4.05"],
            ["23", "2026-07-14", "08:00", "S005", "122.53", "3.27"]
        ]
        
        self.table.setRowCount(len(raw_data))
        for row_idx, row_values in enumerate(raw_data):
            for col_idx, value in enumerate(row_values):
                item = QTableWidgetItem(value)
                # 데이터 가시성을 극대화하기 위한 셀 중앙 정렬
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row_idx, col_idx, item)

    def on_table_cell_clicked(self, row, column):
        """테이블 레코드 선택 시 우측 상세 패널 정보 자동 바인딩"""
        self.selected_row_idx = row
        
        self.input_id.setText(self.table.item(row, 0).text())
        self.input_date.setText(self.table.item(row, 1).text())
        self.input_time.setText(self.table.item(row, 2).text())
        
        # 콤보박스 선택 인덱스 추적
        code_text = self.table.item(row, 3).text()
        combo_index = self.combo_code.findText(code_text)
        if combo_index >= 0:
            self.combo_code.setCurrentIndex(combo_index)
            
        self.input_flow.setText(self.table.item(row, 4).text())
        self.input_turbidity.setText(self.table.item(row, 5).text())

    def on_new_clicked(self):
        """'신규' 레코드 준비 프로세스"""
        # 최대 ID 계산 및 새로운 ID 임시 생성
        max_id = 0
        for r in range(self.table.rowCount()):
            try:
                item_id = int(self.table.item(r, 0).text())
                if item_id > max_id:
                    max_id = item_id
            except (ValueError, AttributeError):
                pass
                
        self.input_id.setText(str(max_id + 1))
        self.input_date.setText("2026-07-14") # 현재 런타임 환경 날짜 디폴트
        self.input_time.setText("00:00")
        self.combo_code.setCurrentIndex(0)
        self.input_flow.clear()
        self.input_turbidity.clear()
        
        self.selected_row_idx = -1
        self.table.clearSelection()

    def on_save_clicked(self):
        """유효성 검증 기반 저장 프로세스 (Update & Create 분기 처리)"""
        id_str = self.input_id.text().strip()
        date_str = self.input_date.text().strip()
        time_str = self.input_time.text().strip()
        code_str = self.combo_code.currentText()
        flow_str = self.input_flow.text().strip()
        turb_str = self.input_turbidity.text().strip()
        
        # 1차 공백 유효성 검증
        if not id_str or not date_str or not time_str or not flow_str or not turb_str:
            QMessageBox.critical(self, "입력 검증 오류", "모든 입력 필드는 비워둘 수 없습니다.")
            return
            
        # 2차 형식 유효성 검증 (수치 데이터 유효성 판단)
        try:
            float(flow_str)
            float(turb_str)
        except ValueError:
            QMessageBox.critical(self, "형식 오류", "유량과 탁도는 반드시 정밀한 부동소수점(Float) 수치여야 합니다.")
            return

        if self.selected_row_idx != -1:
            # 기존 레코드 업데이트 (Update)
            row = self.selected_row_idx
            self.table.item(row, 0).setText(id_str)
            self.table.item(row, 1).setText(date_str)
            self.table.item(row, 2).setText(time_str)
            self.table.item(row, 3).setText(code_str)
            self.table.item(row, 4).setText(flow_str)
            self.table.item(row, 5).setText(turb_str)
            QMessageBox.information(self, "완료", f"ID {id_str}번 데이터가 성공적으로 업데이트되었습니다.")
        else:
            # 새로운 레코드 추가 (Create)
            new_row_idx = self.table.rowCount()
            self.table.insertRow(new_row_idx)
            
            data_fields = [id_str, date_str, time_str, code_str, flow_str, turb_str]
            for col_idx, data_value in enumerate(data_fields):
                new_item = QTableWidgetItem(data_value)
                new_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(new_row_idx, col_idx, new_item)
                
            self.table.selectRow(new_row_idx)
            self.selected_row_idx = new_row_idx
            QMessageBox.information(self, "완료", f"ID {id_str}번 신규 레코드가 정상적으로 등록되었습니다.")

    def on_delete_clicked(self):
        """선택된 레코드 삭제 프로세스"""
        if self.selected_row_idx == -1:
            QMessageBox.warning(self, "삭제 유효성 경고", "삭제 작업을 수행할 행을 선택하십시오.")
            return
            
        target_id = self.table.item(self.selected_row_idx, 0).text()
        
        # 데이터 유실 경고 모달 처리
        confirm = QMessageBox.question(
            self, '삭제 경고', 
            f"선택하신 ID {target_id}번 레코드를 DB에서 영구 삭제하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
            QMessageBox.StandardButton.No
        )
        
        if confirm == QMessageBox.StandardButton.Yes:
            self.table.removeRow(self.selected_row_idx)
            self.on_new_clicked() # 우측 폼 초기화
            QMessageBox.information(self, "성공", "레코드가 안전하게 삭제 처리되었습니다.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 세련된 기본 폰트 적용
    app_font = QFont("맑은 고딕", 9)
    app.setFont(app_font)
    
    window = DamWaterQualityApp()
    window.show()
    sys.exit(app.exec())