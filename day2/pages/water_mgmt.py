# pages/water_mgmt.py
from datetime import datetime
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QTableWidget, QTableWidgetItem, QFormLayout, QLineEdit, QComboBox, QMessageBox, QAbstractItemView
from models.schema import Station, WaterQuality

class WaterMgmtPage(QWidget):
    def __init__(self, session):
        super().__init__()
        self.session = session
        layout = QHBoxLayout(self)
        
        # 1. 테이블 그리드 설정 (정형화된 7개 컬럼 체계 구성)
        self.w_table = QTableWidget(0, 7)
        self.w_table.setHorizontalHeaderLabels(["ID", "측정일시", "지점코드", "지점명(원본)", "수온(℃)", "탁도(NTU)", "pH"])
        self.w_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.w_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.w_table.cellClicked.connect(self.load_w_form)
        layout.addWidget(self.w_table, 2)
        
        # 2. 입력 폼 레이아웃 구성
        f = QFormLayout()
        self.w_id = QLineEdit()
        self.w_id.setReadOnly(True)
        
        # date/time 문자열 필드 대신 정형화된 일시 입력 폼 구성 (가이드 텍스트 제공)
        self.w_measured_at = QLineEdit()
        self.w_measured_at.setPlaceholderText("YYYY-MM-DD HH:MM:SS")
        
        self.w_code = QComboBox()
        stations = self.session.query(Station).all()
        self.w_code.addItems([s.code for s in stations])
        # 코드가 바뀔 때 원본 지점명도 자동 연동되도록 이벤트 바인딩할 수 있는 마커 확보
        self.code_to_name = {s.code: s.name for s in stations}
        
        self.w_temp = QLineEdit()
        self.w_turb = QLineEdit()
        self.w_ph = QLineEdit()
        
        f.addRow("ID (자동발급):", self.w_id)
        f.addRow("측정 일시:", self.w_measured_at)
        f.addRow("지점 코드:", self.w_code)
        f.addRow("수온 (℃):", self.w_temp)
        f.addRow("탁도 (NTU):", self.w_turb)
        f.addRow("pH 농도:", self.w_ph)
        
        form_w = QWidget()
        form_w.setLayout(f)
        layout.addWidget(form_w, 1)
        
        # 데이터 그리드 로드
        self.refresh_w_grid()

    def refresh_w_grid(self):
        """데이터베이스 내 수질 엔티티를 완전 탐색하여 UI Grid에 동기화화"""
        self.w_table.setRowCount(0)
        # 시간 역순 또는 순차 정렬 조회를 통해 데이터 가독성 확보
        for w in self.session.query(WaterQuality).order_by(WaterQuality.measured_at.desc()).all():
            row = self.w_table.rowCount()
            self.w_table.insertRow(row)
            
            # DateTime 객체를 문자열 포맷으로 안전하게 디코딩 처리
            dt_str = w.measured_at.strftime('%Y-%m-%d %H:%M:%S') if w.measured_at else ""
            
            # 정형화 모델 컬럼 어레이 구성 (AttributeError 근본적 완전 제거)
            data_fields = [
                w.id, 
                dt_str, 
                w.station_code, 
                w.station_name_raw, 
                w.water_temp, 
                w.turbidity, 
                w.ph
            ]
            
            for i, val in enumerate(data_fields): 
                self.w_table.setItem(row, i, QTableWidgetItem(str(val) if val is not None else ""))

    def load_w_form(self, row):
        """그리드 행 클릭 시 우측 폼 UI 컨트롤러로 엔티티 데이터 바인딩"""
        self.w_id.setText(self.w_table.item(row, 0).text())
        self.w_measured_at.setText(self.w_table.item(row, 1).text())
        self.w_code.setCurrentText(self.w_table.item(row, 2).text())
        self.w_temp.setText(self.w_table.item(row, 4).text())
        self.w_turb.setText(self.w_table.item(row, 5).text())
        self.w_ph.setText(self.w_table.item(row, 6).text())

    def save_water(self):
        """main.py 상단 저장 버튼과 바인딩되는 트랜잭션 핵심 비즈니스 로직"""
        wid = self.w_id.text()
        
        # 1. 날짜 데이터 포맷 밸리데이션 검증
        try:
            parsed_datetime = datetime.strptime(self.w_measured_at.text().strip(), '%Y-%m-%d %H:%M:%S')
        except ValueError:
            QMessageBox.critical(self, "오류", "날짜 형식이 올바르지 않습니다.\n(YYYY-MM-DD HH:MM:SS 형태로 입력하세요.)")
            return

        # 2. 영속성 엔티티 신규 생성 또는 병합(Merge) 분기 처리
        w = self.session.query(WaterQuality).filter_by(id=int(wid)).first() if wid else WaterQuality()
        
        w.measured_at = parsed_datetime
        w.station_code = self.w_code.currentText()
        # 데이터 무결성을 보장하기 위해 스테이션 매핑 맵에서 명칭을 역참조하여 원본 필드 보완
        w.station_name_raw = self.code_to_name.get(w.station_code, "미지정지점")
        
        # 3. 수치 데이터 실수 변환 및 예외 예방
        try:
            w.water_temp = float(self.w_temp.text()) if self.w_temp.text() else 0.0
            w.turbidity = float(self.w_turb.text()) if self.w_turb.text() else 0.0
            w.ph = float(self.w_ph.text()) if self.w_ph.text() else 0.0
        except ValueError:
            QMessageBox.critical(self, "오류", "수온, 탁도, pH 항목에는 숫자만 입력 가능합니다.")
            return

        self.session.add(w)
        self.session.commit()
        self.refresh_w_grid()
        self.clear_w_form()
        QMessageBox.information(self, "완료", "성공적으로 저장되었습니다.")

    def delete_water(self):
        """main.py 상단 삭제 버튼과 바인딩되는 트랜잭션 제어 로직"""
        wid = self.w_id.text()
        if wid:
            w = self.session.query(WaterQuality).filter_by(id=int(wid)).first()
            if w and QMessageBox.question(self, '삭제', '선택한 수질 데이터를 영구 삭제하시겠습니까?', 
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
                self.session.delete(w)
                self.session.commit()
                self.refresh_w_grid()
                self.clear_w_form()

    def clear_w_form(self):
        """입력 폼 컴포넌트 전체 초기화 로직"""
        for field in [self.w_id, self.w_measured_at, self.w_temp, self.w_turb, self.w_ph]: 
            field.clear()