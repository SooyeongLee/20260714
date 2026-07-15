from PyQt6.QtWidgets import QWidget, QVBoxLayout, QFormLayout, QLineEdit, QMessageBox

class SettingsPage(QWidget):
    def __init__(self, session):
        super().__init__()
        self.session = session
        layout = QVBoxLayout(self)
        f = QFormLayout()
        self.db_path = QLineEdit('sqlite:///water_system.db')
        f.addRow("DB Path:", self.db_path)
        layout.addLayout(f); layout.addStretch()

    def save_settings(self):
        # 설정 저장 로직 추가 가능
        QMessageBox.information(self, "완료", "설정이 저장되었습니다.")