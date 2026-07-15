import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QStackedWidget, QToolButton, QLabel, QPushButton, QStyle)
from services.db_service import DBService
from pages.dashboard import DashboardPage
from pages.station_mgmt import StationMgmtPage
from pages.water_mgmt import WaterMgmtPage
from pages.settings import SettingsPage

GOOGLE_STYLE = """
    QMainWindow { background-color: #FFFFFF; }
    QWidget { font-family: 'Segoe UI', sans-serif; font-size: 13px; }
    #Sidebar { background-color: #F8F9FA; border-right: 1px solid #E0E0E0; }
    QPushButton { background-color: #F8F9FA; color: #3C4043; border: 1px solid #DADCE0; border-radius: 4px; padding: 6px 12px; font-weight: bold; }
    QPushButton:hover { background-color: #E8F0FE; border: 1px solid #4285F4; color: #1967D2; }
    QTableWidget { border: 1px solid #E0E0E0; alternate-background-color: #F8F9FA; }
    QLineEdit, QComboBox { border: 1px solid #DADCE0; border-radius: 4px; padding: 5px; }
"""

class WaterMonitoringApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db_service = DBService()
        self.db_service.populate_dummy_data()
        self.session = self.db_service.get_session()
        
        self.setWindowTitle("댐 수질 통합 관리 시스템")
        self.resize(1200, 800)
        self.init_ui()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)

        top_bar = QWidget()
        top_bar.setFixedHeight(65)
        top_bar.setStyleSheet("background-color: #FFFFFF; border-bottom: 1px solid #E0E0E0;")
        top_layout = QHBoxLayout(top_bar)
        
        btn_menu = QToolButton()
        btn_menu.setText("☰")
        btn_menu.clicked.connect(self.toggle_sidebar)
        top_layout.addWidget(btn_menu)
        top_layout.addWidget(QLabel("<b>댐 수질 통합 관리 시스템</b>"))
        top_layout.addStretch()

        btn_new = QPushButton("신규")
        btn_new.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
        btn_new.clicked.connect(self.cmd_new)
        
        btn_save = QPushButton("저장")
        btn_save.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        btn_save.clicked.connect(self.cmd_save)
        
        btn_del = QPushButton("삭제")
        btn_del.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        btn_del.clicked.connect(self.cmd_delete)
        
        btn_exit = QPushButton("종료")
        btn_exit.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarCloseButton))
        btn_exit.clicked.connect(self.close)
        
        top_layout.addWidget(btn_new)
        top_layout.addWidget(btn_save)
        top_layout.addWidget(btn_del)
        top_layout.addWidget(btn_exit)
        main_layout.addWidget(top_bar)

        content_box = QHBoxLayout()
        self.sidebar = QWidget()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(180)
        s_layout = QVBoxLayout(self.sidebar)
        
        self.stack = QStackedWidget()
        self.p_dash = DashboardPage(self.session)
        self.p_st = StationMgmtPage(self.session)
        self.p_w = WaterMgmtPage(self.session)
        self.p_set = SettingsPage(self.session)
        
        self.stack.addWidget(self.p_dash)
        self.stack.addWidget(self.p_st)
        self.stack.addWidget(self.p_w)
        self.stack.addWidget(self.p_set)
        
        menu_items = [("대시보드", 0), ("지점 관리", 1), ("수질 데이터 관리", 2), ("환경 설정", 3)]
        for text, idx in menu_items:
            btn = QPushButton(text)
            btn.setStyleSheet("background: transparent; border: none; color: #5F6368; text-align: left; padding: 10px;")
            btn.clicked.connect(lambda _, i=idx: self.stack.setCurrentIndex(i))
            s_layout.addWidget(btn)
        s_layout.addStretch()

        content_box.addWidget(self.sidebar)
        content_box.addWidget(self.stack)
        main_layout.addLayout(content_box)

    def toggle_sidebar(self):
        self.sidebar.setVisible(not self.sidebar.isVisible())

    def cmd_new(self):
        current = self.stack.currentWidget()
        if hasattr(current, 'clear_st_form'): current.clear_st_form()
        elif hasattr(current, 'clear_w_form'): current.clear_w_form()

    def cmd_save(self):
        current = self.stack.currentWidget()
        if isinstance(current, StationMgmtPage): current.save_station()
        elif isinstance(current, WaterMgmtPage): current.save_water()
        elif isinstance(current, SettingsPage): current.save_settings()

    def cmd_delete(self):
        current = self.stack.currentWidget()
        if isinstance(current, StationMgmtPage): current.delete_station()
        elif isinstance(current, WaterMgmtPage): current.delete_water()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(GOOGLE_STYLE)
    window = WaterMonitoringApp()
    window.show()
    sys.exit(app.exec())