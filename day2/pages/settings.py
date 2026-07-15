# pages/settings.py
import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QMessageBox, 
    QPushButton, QProgressBar, QGroupBox, QFrame, QHBoxLayout
)
from PyQt6.QtCore import pyqtSignal
from sqlalchemy import text  # 💡 원시 SQL 실행을 위해 추가
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger("SettingsPage")

class SettingsPage(QWidget):
    # 1. 실시간 수집 On/Off 시그널
    sync_toggled = pyqtSignal(bool)
    # 2. 특정 기간 과거 데이터 동기화 요청 시그널 (시작일, 종료일 전달)
    sync_range_requested = pyqtSignal(str, str)

    def __init__(self, session, sync_service=None):
        """
        :param session: SQLAlchemy 세션 객체
        :param sync_service: 초기화 비즈니스 로직 처리를 위한 WaterDataSyncService 인스턴스 (선택)
        """
        super().__init__()
        self.session = session
        self.sync_service = sync_service
        self.is_sync_active = False  
        
        # 메인 수직 레이아웃
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # ----------------------------------------------------
        # [기존 기능 영역] 폼 레이아웃 설정
        # ----------------------------------------------------
        f = QFormLayout()
        
        self.db_path = QLineEdit('sqlite:///water_system.db')
        f.addRow("DB Path:", self.db_path)
        
        # [기존] 실시간 자동 수집 컨트롤
        self.btn_toggle_sync = QPushButton("자동 수집 시작 (Off)")
        self.btn_toggle_sync.setStyleSheet("background-color: #EA4335; color: white; padding: 10px; font-weight: bold;")
        self.btn_toggle_sync.clicked.connect(self.handle_sync_toggle)
        f.addRow("실시간 데이터 연동:", self.btn_toggle_sync)
        
        # [기존] 과거 특정 기간 (1~4월) 데이터 수동 동기화 컨트롤
        self.btn_sync_history = QPushButton("1월~4월 수질 데이터 수동 동기화")
        self.btn_sync_history.setStyleSheet("background-color: #1A73E8; color: white; padding: 10px; font-weight: bold;")
        self.btn_sync_history.clicked.connect(self.handle_history_sync)
        f.addRow("과거 데이터 동기화:", self.btn_sync_history)

        # [기존] 실시간 진행 상태 프로그레스 바 배치
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)  # 초기에는 숨김 처리
        f.addRow("동기화 진행률:", self.progress_bar)
        
        main_layout.addLayout(f)

        # ----------------------------------------------------
        # 💡 [신규 살붙임 영역] 데이터베이스 관리 그룹박스
        # ----------------------------------------------------
        data_group = QGroupBox("데이터베이스 관리")
        data_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 13px;
                border: 1px solid #DCDCDC;
                border-radius: 6px;
                margin-top: 15px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        group_layout = QVBoxLayout(data_group)
        group_layout.setSpacing(12)

        # 안내 경고 메시지 라벨
        warning_info = QPushButton("⚠️ 데이터 초기화 작업은 복구가 불가능하므로 실행 시 각별히 유의하시기 바랍니다.")
        warning_info.setFlat(True)
        warning_info.setStyleSheet("color: #D32F2F; font-weight: bold; text-align: left; border: none; padding: 0;")
        group_layout.addWidget(warning_info)

        # 구분선 (Separator)
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("background-color: #E0E0E0;")
        group_layout.addWidget(line)

        # 가로 배치용 초기화 버튼 레이아웃 구성
        btn_layout = QHBoxLayout()
        
        # A. 수질 데이터만 초기화 버튼
        self.btn_reset_water = QPushButton("수질 데이터 비우기")
        self.btn_reset_water.setToolTip("측정소 마스터 테이블을 제외한 수질 계측 이력 데이터만 일괄 삭제합니다.")
        self.btn_reset_water.setStyleSheet("""
            QPushButton {
                background-color: #F57C00; 
                color: white; 
                font-weight: bold; 
                padding: 10px 18px; 
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #E65100; }
        """)
        self.btn_reset_water.clicked.connect(self.handle_reset_water_only)
        btn_layout.addWidget(self.btn_reset_water)

        # B. 전체 데이터 공장 초기화 버튼
        self.btn_reset_all = QPushButton("전체 데이터 공장 초기화")
        self.btn_reset_all.setToolTip("수질 시계열 이력 및 등록된 모든 측정소 마스터 정보를 완전 청소합니다.")
        self.btn_reset_all.setStyleSheet("""
            QPushButton {
                background-color: #D32F2F; 
                color: white; 
                font-weight: bold; 
                padding: 10px 18px; 
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #C62828; }
        """)
        self.btn_reset_all.clicked.connect(self.handle_reset_all)
        btn_layout.addWidget(self.btn_reset_all)
        
        btn_layout.addStretch()  # 우측 여백 정렬
        group_layout.addLayout(btn_layout)
        
        main_layout.addWidget(data_group)
        main_layout.addStretch()

    # ----------------------------------------------------
    # [기존 로직] 자동 수집 토글 제어
    # ----------------------------------------------------
    def handle_sync_toggle(self):
        """On/Off 버튼 상태 스위칭 및 시그널 전송 제어 로직"""
        self.is_sync_active = not self.is_sync_active
        
        if self.is_sync_active:
            self.btn_toggle_sync.setText("자동 수집 중 (On)")
            self.btn_toggle_sync.setStyleSheet("background-color: #34A853; color: white; padding: 10px; font-weight: bold;")
            QMessageBox.information(self, "알림", "실시간 수질 데이터 백그라운드 수집이 활성화되었습니다.\n(1분 주기로 데이터를 갱신합니다.)")
        else:
            self.btn_toggle_sync.setText("자동 수집 시작 (Off)")
            self.btn_toggle_sync.setStyleSheet("background-color: #EA4335; color: white; padding: 10px; font-weight: bold;")
            QMessageBox.information(self, "알림", "실시간 백그라운드 데이터 수집이 중지되었습니다.")
            
        self.sync_toggled.emit(self.is_sync_active)

    # ----------------------------------------------------
    # [기존 로직] 과거 1~4월 동기화 처리
    # ----------------------------------------------------
    def handle_history_sync(self):
        """1월~4월 데이터 수동 동기화 버튼 이벤트"""
        reply = QMessageBox.question(
            self, "과거 데이터 동기화",
            "공공데이터포털로부터 2026년 1월 1일 ~ 4월 30일까지의 데이터를 가져옵니다.\n진행하시겠습니까?\n(데이터 량이 많아 약간의 시간이 소요될 수 있습니다.)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # 동기화 진행 중 상태로 버튼 비활성화 및 프로그레스바 초기화 노출
            self.btn_sync_history.setEnabled(False)
            self.btn_sync_history.setText("1월~4월 데이터 가져오는 중...")
            self.btn_sync_history.setStyleSheet("background-color: #A0A0A0; color: white; padding: 10px; font-weight: bold;")
            
            self.progress_bar.setValue(0)
            self.progress_bar.setVisible(True)  # 수동 수집 시작 시 프로그레스바 노출
            
            # 메인 윈도우로 20260101 ~ 20260430 범위 동기화 요청 송신
            self.sync_range_requested.emit("20260101", "20260430")

    # ----------------------------------------------------
    # [기존 로직] 동기화 프로그레스바 헬퍼
    # ----------------------------------------------------
    def set_progress_value(self, value: int):
        """메인 스레드로부터 백그라운드 스레드의 진행률을 전달받아 UI에 반영"""
        self.progress_bar.setValue(value)

    def reset_history_button(self):
        """동기화 완료 후 버튼과 프로그레스바를 원래대로 원복하는 헬퍼 메서드"""
        self.btn_sync_history.setEnabled(True)
        self.btn_sync_history.setText("1월~4월 수질 데이터 수동 동기화")
        self.btn_sync_history.setStyleSheet("background-color: #1A73E8; color: white; padding: 10px; font-weight: bold;")
        self.progress_bar.setVisible(False)  # 완료 후 프로그레스바 다시 숨김
        self.progress_bar.setValue(0)

    def save_settings(self):
        QMessageBox.information(self, "완료", "설정이 저장되었습니다.")

    # ----------------------------------------------------
    # 💡 [초강력 개선] Raw SQL 직접 실행 방식으로 확실하게 테이블 비우기
    # ----------------------------------------------------
    def handle_reset_water_only(self):
        """수질 측정 데이터만 비우기 (Raw SQL + Cache Eviction 적용)"""
        reply = QMessageBox.question(
            self, 
            "데이터 삭제 경고", 
            "수집된 모든 수질 측정 시계열 데이터가 영구적으로 삭제됩니다.\n(측정소 정보는 유지됩니다)\n\n정말로 삭제하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # 1. 미완료된 트랜잭션 수동 롤백 및 캐시 비우기 (락 방지 및 상태 동기화)
                self.session.rollback()
                self.session.expire_all()  # ORM 메모리 내 저장된 데이터 캐시를 강제 만료시켜 비움

                # 2. 강력한 Raw SQL로 테이블 내 데이터 일괄 제거
                # 데이터베이스 내 실제 테이블명이 다를 수 있으므로 소문자/대문자 동시 대비
                try:
                    self.session.execute(text("DELETE FROM water_quality"))
                except SQLAlchemyError:
                    self.session.execute(text("DELETE FROM WaterQuality"))
                
                # 3. 변경사항 즉시 영구 반영(Commit)
                self.session.commit()
                
                QMessageBox.information(self, "완료", "수질 데이터 비우기 작업이 성공적으로 수행되었습니다.")
            except Exception as e:
                self.session.rollback()
                logger.exception("수질 데이터 비우기 처리 에러 발생")
                QMessageBox.critical(self, "오류", f"데이터 초기화 실패:\n{e}")

    def handle_reset_all(self):
        """측정소 정보까지 일괄 삭제하는 전체 데이터 공장 초기화 (Raw SQL 실행)"""
        first_reply = QMessageBox.warning(
            self, 
            "최고 권한 공장 초기화 경고", 
            "수질 이력뿐만 아니라 연계된 모든 [측정소 마스터 정보]까지 완전히 삭제됩니다.\n그래도 초기화를 강행하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if first_reply == QMessageBox.StandardButton.Yes:
            second_reply = QMessageBox.critical(
                self, 
                "돌이킬 수 없는 최종 확인", 
                "이 작업은 복구가 불가능하며 모든 로컬 테이블 구조가 완전히 초기화됩니다.\n정말로 최종 삭제를 진행하시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if second_reply == QMessageBox.StandardButton.Yes:
                try:
                    # 1. 안전조치 트랜잭션 리셋 및 캐시 만료
                    self.session.rollback()
                    self.session.expire_all()

                    # 2. 외래키 제약조건 순서를 고려해 자식(수질) -> 부모(측정소) 순으로 삭제
                    try:
                        self.session.execute(text("DELETE FROM water_quality"))
                        self.session.execute(text("DELETE FROM station"))
                    except SQLAlchemyError:
                        self.session.execute(text("DELETE FROM WaterQuality"))
                        self.session.execute(text("DELETE FROM Station"))
                    
                    # 3. 물리 파일 적용 및 세션 동기화
                    self.session.commit()
                    
                    QMessageBox.information(self, "공장 초기화 완료", "시스템 내 모든 로컬 데이터베이스 정보가 리셋되었습니다.")
                except Exception as e:
                    self.session.rollback()
                    logger.exception("전체 공장 초기화 처리 에러 발생")
                    QMessageBox.critical(self, "오류", f"공장 초기화 실패:\n{e}")