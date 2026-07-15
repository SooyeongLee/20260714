from PyQt6.QtWidgets import QWidget, QHBoxLayout, QTableWidget, QTableWidgetItem, QFormLayout, QLineEdit, QMessageBox, QAbstractItemView
from models.schema import Station

class StationMgmtPage(QWidget):
    def __init__(self, session):
        super().__init__()
        self.session = session
        layout = QHBoxLayout(self)
        
        # 테이블
        self.st_table = QTableWidget(0, 5)
        self.st_table.setHorizontalHeaderLabels(["코드", "명칭", "위도", "경도", "비고"])
        self.st_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.st_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.st_table.cellClicked.connect(self.load_st_form)
        layout.addWidget(self.st_table, 2)
        
        # 입력 폼
        f = QFormLayout()
        self.st_code, self.st_name, self.st_lat, self.st_lon, self.st_rem = QLineEdit(), QLineEdit(), QLineEdit(), QLineEdit(), QLineEdit()
        f.addRow("코드:", self.st_code); f.addRow("명칭:", self.st_name); f.addRow("위도:", self.st_lat); f.addRow("경도:", self.st_lon); f.addRow("비고:", self.st_rem)
        
        form_w = QWidget(); form_w.setLayout(f); layout.addWidget(form_w, 1)
        self.refresh_st_grid()

    def refresh_st_grid(self):
        self.st_table.setRowCount(0)
        for s in self.session.query(Station).all():
            row = self.st_table.rowCount(); self.st_table.insertRow(row)
            for i, val in enumerate([s.code, s.name, s.lat, s.lon, s.remarks]): 
                self.st_table.setItem(row, i, QTableWidgetItem(str(val)))

    def load_st_form(self, row):
        self.st_code.setText(self.st_table.item(row, 0).text())
        self.st_name.setText(self.st_table.item(row, 1).text())
        self.st_lat.setText(self.st_table.item(row, 2).text())
        self.st_lon.setText(self.st_table.item(row, 3).text())
        self.st_rem.setText(self.st_table.item(row, 4).text())

    def save_station(self):
        code = self.st_code.text()
        if not code: return
        st = self.session.query(Station).filter_by(code=code).first() or Station(code=code)
        st.name = self.st_name.text(); st.lat = float(self.st_lat.text()); st.lon = float(self.st_lon.text()); st.remarks = self.st_rem.text()
        self.session.add(st); self.session.commit(); self.refresh_st_grid(); self.clear_st_form()
        QMessageBox.information(self, "완료", "저장되었습니다.")

    def delete_station(self):
        code = self.st_code.text()
        st = self.session.query(Station).filter_by(code=code).first()
        if st and QMessageBox.question(self, '삭제', '삭제하시겠습니까?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.session.delete(st); self.session.commit(); self.refresh_st_grid(); self.clear_st_form()

    def clear_st_form(self):
        for w in [self.st_code, self.st_name, self.st_lat, self.st_lon, self.st_rem]: w.clear()