from PyQt6.QtWidgets import QWidget, QHBoxLayout, QTableWidget, QTableWidgetItem, QFormLayout, QLineEdit, QComboBox, QMessageBox, QAbstractItemView
from models.schema import Station, WaterQuality

class WaterMgmtPage(QWidget):
    def __init__(self, session):
        super().__init__()
        self.session = session
        layout = QHBoxLayout(self)
        
        # 테이블
        self.w_table = QTableWidget(0, 6)
        self.w_table.setHorizontalHeaderLabels(["ID", "날짜", "시간", "코드", "유량", "탁도"])
        self.w_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.w_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.w_table.cellClicked.connect(self.load_w_form)
        layout.addWidget(self.w_table, 2)
        
        # 입력 폼
        f = QFormLayout()
        self.w_id = QLineEdit(); self.w_id.setReadOnly(True)
        self.w_date, self.w_time = QLineEdit(), QLineEdit()
        self.w_code = QComboBox()
        self.w_code.addItems([s.code for s in self.session.query(Station).all()])
        self.w_flow, self.w_turb = QLineEdit(), QLineEdit()
        f.addRow("ID:", self.w_id); f.addRow("날짜:", self.w_date); f.addRow("시간:", self.w_time)
        f.addRow("코드:", self.w_code); f.addRow("유량:", self.w_flow); f.addRow("탁도:", self.w_turb)
        
        form_w = QWidget(); form_w.setLayout(f); layout.addWidget(form_w, 1)
        self.refresh_w_grid()

    def refresh_w_grid(self):
        self.w_table.setRowCount(0)
        for w in self.session.query(WaterQuality).all():
            row = self.w_table.rowCount(); self.w_table.insertRow(row)
            for i, val in enumerate([w.id, w.date, w.time, w.station_code, w.discharge, w.turbidity]): 
                self.w_table.setItem(row, i, QTableWidgetItem(str(val)))

    def load_w_form(self, row):
        self.w_id.setText(self.w_table.item(row, 0).text())
        self.w_date.setText(self.w_table.item(row, 1).text())
        self.w_time.setText(self.w_table.item(row, 2).text())
        self.w_code.setCurrentText(self.w_table.item(row, 3).text())
        self.w_flow.setText(self.w_table.item(row, 4).text())
        self.w_turb.setText(self.w_table.item(row, 5).text())

    def save_water(self):
        wid = self.w_id.text()
        w = self.session.query(WaterQuality).filter_by(id=int(wid)).first() if wid else WaterQuality()
        w.date, w.time = self.w_date.text(), self.w_time.text()
        w.station_code = self.w_code.currentText()
        w.discharge, w.turbidity = float(self.w_flow.text()), float(self.w_turb.text())
        self.session.add(w); self.session.commit(); self.refresh_w_grid(); self.clear_w_form()
        QMessageBox.information(self, "완료", "저장되었습니다.")

    def delete_water(self):
        wid = self.w_id.text()
        if wid:
            w = self.session.query(WaterQuality).filter_by(id=int(wid)).first()
            if w and QMessageBox.question(self, '삭제', '삭제하시겠습니까?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
                self.session.delete(w); self.session.commit(); self.refresh_w_grid(); self.clear_w_form()

    def clear_w_form(self):
        for w in [self.w_id, self.w_date, self.w_time, self.w_flow, self.w_turb]: w.clear()