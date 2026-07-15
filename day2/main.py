# main.py
import sys
from datetime import datetime
import logging
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QStackedWidget, QToolButton, QLabel, QPushButton, QStyle, QMessageBox)
from PyQt6.QtCore import QThread, pyqtSignal, QTimer, Qt

# 서비스 레이어 임포트
from services.db_service import DBService
from services.water_sync_service import WaterDataSyncService
from services.mapping_service import MappingDataService

# 페이지 레이아웃 임포트
from pages.map_dashboard import MapDashboardPage
from pages.station_mgmt import StationMgmtPage
from pages.water_mgmt import WaterMgmtPage
from pages.mapping_mgmt import MappingManagementPage
from pages.settings import SettingsPage

# 글로벌 로거 설정
logger = logging.getLogger("WaterSyncSystem")

# 구글 머티리얼 스타일시트 사양 유지
GOOGLE_STYLE = """
    QMainWindow { background-color: #FFFFFF; }
    QWidget { font-family: 'Segoe UI', sans-serif; font-size: 13px; }
    #Sidebar { background-color: #F8F9FA; border-right: 1px solid #E0E0E0; }
    QPushButton { background-color: #F8F9FA; color: #3C4043; border: 1px solid #DADCE0; border-radius: 4px; padding: 6px 12px; font-weight: bold; }
    QPushButton:hover { background-color: #E8F0FE; border: 1px solid #4285F4; color: #1967D2; }
    QTableWidget { border: 1px solid #E0E0E0; alternate-background-color: #F8F9FA; }
    QLineEdit, QComboBox { border: 1px solid #DADCE0; border-radius: 4px; padding: 5px; }
"""

class WaterSyncWorker(QThread):
    """실시간 주기 연동 및 대용량 과거 범위 데이터 통합 연동을 공용 처리하는 백그라운드 스레드"""
    sync_finished = pyqtSignal(dict)
    progress_updated = pyqtSignal(int)

    def __init__(self, db_service, service_key, start_date, end_date, num_of_rows=500):
        super().__init__()
        self.db_service = db_service
        self.service_key = service_key
        self.start_date = start_date
        self.end_date = end_date
        self.num_of_rows = num_of_rows

    def run(self):
        logger.info(f"[스레드 시작] 백그라운드 데이터 수집 워커 기동 완료 (Thread ID: {int(self.currentThreadId())})")
        try:
            sync_service = WaterDataSyncService(self.db_service, self.service_key)
            result = sync_service.fetch_and_sync(
                start_date=self.start_date, 
                end_date=self.end_date, 
                num_of_rows=self.num_of_rows,
                progress_callback=self.emit_progress
            )
            self.sync_finished.emit(result)
        except Exception as e:
            logger.exception("[스레드 크래시] 스레드 실행 도중 치명적인 미처리 예외가 발생했습니다.")
            self.sync_finished.emit({
                "status": "FAIL", 
                "inserted": 0, 
                "skipped": 0, 
                "error": f"Thread Fatal Error: {str(e)}"
            })

    def emit_progress(self, percent_val: int):
        self.progress_updated.emit(percent_val)


class WaterMonitoringApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db_service = DBService()
        self.db_service.populate_dummy_data()
        self.session = self.db_service.get_session()
        
        self.MY_KEY = "fkY+6imS92ORBSxVCHpw9gmGpOAI0lnbrx5pXFJIK1NRaxHClJ2Ksd0wx/06ZPlgwlgXgGrEyHUVUsbiLqvWmg=="
        
        self.sync_worker = None
        self.sync_timer = QTimer(self)
        self.sync_timer.timeout.connect(self.trigger_background_sync)
        
        self.setWindowTitle("댐 수질 및 관측소 통합 관리 시스템")
        self.resize(1300, 850)
        self.init_ui()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 상단 타이틀 바 및 공통 제어 버튼 레이아웃 (Topbar)
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

        # 💡 Topbar 공통 제어 단추 정의
        self.btn_new = QPushButton("신규")
        self.btn_new.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
        self.btn_new.clicked.connect(self.cmd_new)
        
        self.btn_save = QPushButton("저장")
        self.btn_save.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        self.btn_save.clicked.connect(self.cmd_save)
        
        self.btn_del = QPushButton("삭제")
        self.btn_del.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        self.btn_del.clicked.connect(self.cmd_delete)
        
        self.btn_exit = QPushButton("종료")
        self.btn_exit.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarCloseButton))
        self.btn_exit.clicked.connect(self.close)
        
        top_layout.addWidget(self.btn_new)
        top_layout.addWidget(self.btn_save)
        top_layout.addWidget(self.btn_del)
        top_layout.addWidget(self.btn_exit)
        main_layout.addWidget(top_bar)

        # 사이드바 및 컨텐츠 스택 영역 구성
        content_box = QHBoxLayout()
        self.sidebar = QWidget()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(180)
        s_layout = QVBoxLayout(self.sidebar)
        
        self.stack = QStackedWidget()
        
        # 각 페이지 인스턴스 초기화 및 세션 바인딩
        self.p_dash = MapDashboardPage(self.session)
        self.p_st = StationMgmtPage(self.session)
        self.p_w = WaterMgmtPage(self.session)
        self.p_map_mgmt = MappingManagementPage(self.session)
        self.p_set = SettingsPage(self.session)
        
        # 핵심 이벤트 신호선 바인딩
        self.p_set.sync_toggled.connect(self.manage_sync_schedule)
        self.p_set.sync_range_requested.connect(self.trigger_range_sync)
        
        # QStackedWidget 레이어 추가
        self.stack.addWidget(self.p_dash)       # Index 0
        self.stack.addWidget(self.p_st)         # Index 1
        self.stack.addWidget(self.p_w)          # Index 2
        self.stack.addWidget(self.p_map_mgmt)   # Index 3
        self.stack.addWidget(self.p_set)        # Index 4
        
        menu_items = [
            ("대시보드", 0), 
            ("지점 관리", 1), 
            ("수질 데이터 관리", 2), 
            ("관측소 매핑 관리", 3), 
            ("환경 설정", 4)
        ]
        
        for text, idx in menu_items:
            btn = QPushButton(text)
            btn.setStyleSheet("background: transparent; border: none; color: #5F6368; text-align: left; padding: 10px;")
            btn.clicked.connect(lambda _, i=idx: self.on_menu_clicked(i))
            s_layout.addWidget(btn)
        s_layout.addStretch()

        content_box.addWidget(self.sidebar)
        content_box.addWidget(self.stack)
        main_layout.addLayout(content_box)

    def on_menu_clicked(self, index: int):
        """메뉴가 클릭되어 화면이 전환될 때의 제어 핸들러"""
        self.stack.setCurrentIndex(index)
        if index == 0:
            logger.info("메인 지도 화면 전환: 최신 측정값 반영을 시작합니다.")
            self.p_dash.refresh_dashboard()

    def toggle_sidebar(self):
        self.sidebar.setVisible(not self.sidebar.isVisible())

    def manage_sync_schedule(self, start_sync: bool):
        if start_sync:
            self.trigger_background_sync()  
            self.sync_timer.start(60000)    
        else:
            self.sync_timer.stop()

    def trigger_background_sync(self):
        if self.sync_worker and self.sync_worker.isRunning():
            return  
        today_str = datetime.now().strftime('%Y%m%d')
        self.sync_worker = WaterSyncWorker(self.db_service, self.MY_KEY, start_date=today_str, end_date=today_str)
        self.sync_worker.sync_finished.connect(self.handle_sync_complete)
        self.sync_worker.start()

    def trigger_range_sync(self, start_date: str, end_date: str):
        if self.sync_worker and self.sync_worker.isRunning():
            QMessageBox.warning(self, "경고", "현재 수집 스레드가 실행 중입니다. 잠시 후 다시 시도해 주세요.")
            self.p_set.reset_history_button()
            return
        
        self.sync_worker = WaterSyncWorker(self.db_service, self.MY_KEY, start_date=start_date, end_date=end_date, num_of_rows=9990)
        self.sync_worker.progress_updated.connect(self.p_set.set_progress_value)
        self.sync_worker.sync_finished.connect(self.handle_range_sync_complete)
        self.sync_worker.start()

    def handle_sync_complete(self, result: dict):
        if result.get("status") == "SUCCESS" and result.get("inserted", 0) > 0:
            self.p_dash.update_charts()
            self.p_w.refresh_w_grid()
            self.statusBar().showMessage(f"[자동 수집] 신규 데이터 {result['inserted']}건 자동 갱신 완료.", 5000)

    def handle_range_sync_complete(self, result: dict):
        self.p_set.reset_history_button()  
        if result.get("status") == "SUCCESS":
            inserted = result.get("inserted", 0)
            skipped = result.get("skipped", 0)
            self.p_dash.update_charts()
            self.p_w.refresh_w_grid()
            QMessageBox.information(self, "동기화 완료", f"수질 데이터 동기화가 완료되었습니다!\n\n* 신규 적재: {inserted}건\n* 중복 스킵: {skipped}건")
        else:
            error_msg = result.get("error", "알 수 없는 오류")
            QMessageBox.critical(self, "오류", f"과거 데이터 동기화 도중 오류가 발생했습니다.\n상세 사유: {error_msg}")

    # ==========================================
    # 💡 툴바 공통 제어 함수 라우팅 엔진 (핵심)
    # ==========================================
    def cmd_new(self):
        """현재 화면에 맞춤화된 초기화(신규) 기능 대리 처리"""
        current_page = self.stack.currentWidget()
        
        # 1. 관측소 매핑 관리 화면 라우팅
        if isinstance(current_page, MappingManagementPage):
            current_page.clear_form()
        # 2. 지점 관리 화면 라우팅
        elif hasattr(current_page, 'clear_st_form') and callable(current_page.clear_st_form):
            current_page.clear_st_form()
        # 3. 수질 데이터 관리 화면 라우팅
        elif hasattr(current_page, 'clear_w_form') and callable(current_page.clear_w_form):
            current_page.clear_w_form()
        else:
            self.statusBar().showMessage("현재 화면은 '신규' 추가 기능을 지원하지 않습니다.", 3000)

    def cmd_save(self):
        """현재 활성화된 화면의 편집 데이터 영속성 저장 이행"""
        current_page = self.stack.currentWidget()
        
        # 1. 관측소 매핑 관리 화면 라우팅
        if isinstance(current_page, MappingManagementPage):
            current_page.save_mapping()
        # 2. 기존 지점 관리 화면 라우팅
        elif isinstance(current_page, StationMgmtPage) and hasattr(current_page, 'save_station'):
            current_page.save_station()
        # 3. 기존 수질 데이터 관리 화면 라우팅
        elif isinstance(current_page, WaterMgmtPage) and hasattr(current_page, 'save_water'):
            current_page.save_water()
        # 4. 환경 설정 화면 라우팅
        elif isinstance(current_page, SettingsPage) and hasattr(current_page, 'save_settings'):
            current_page.save_settings()
        else:
            self.statusBar().showMessage("현재 화면은 '저장' 기능을 지원하지 않습니다.", 3000)

    def cmd_delete(self):
        """현재 선택된 그리드 식별자의 영구 파기 트랜잭션 라우팅"""
        current_page = self.stack.currentWidget()
        
        # 1. 관측소 매핑 관리 화면 라우팅
        if isinstance(current_page, MappingManagementPage):
            current_page.delete_mapping()
        # 2. 기존 지점 관리 화면 라우팅
        elif isinstance(current_page, StationMgmtPage) and hasattr(current_page, 'delete_station'):
            current_page.delete_station()
        # 3. 기존 수질 데이터 관리 화면 라우팅
        elif isinstance(current_page, WaterMgmtPage) and hasattr(current_page, 'delete_water'):
            current_page.delete_water()
        else:
            self.statusBar().showMessage("현재 화면은 '삭제' 기능을 지원하지 않습니다.", 3000)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    app.setStyleSheet(GOOGLE_STYLE)
    window = WaterMonitoringApp()
    window.show()
    sys.exit(app.exec())