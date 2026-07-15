# pages/map_dashboard.py
import os
import logging
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6.QtCore import QUrl
import folium
from sqlalchemy import func

# 모델 구조에 맞춘 임포트
from models.schema import Station, WaterQuality

logger = logging.getLogger("MapDashboardPage")

class MapDashboardPage(QWidget):
    def __init__(self, session):
        """
        :param session: SQLAlchemy 세션 객체
        """
        super().__init__()
        self.session = session
        
        # 메인 UI 구성
        self.init_ui()
        
        # 컴포넌트 렌더링 후 최초 지도 로드
        self.refresh_dashboard()

    def init_ui(self):
        # 전체 수직 레이아웃
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # 1. 상단 인포메이션 바 (헤더)
        header_frame = QFrame()
        header_frame.setFixedHeight(50)
        header_frame.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E0E0E0;
                border-radius: 6px;
            }
        """)
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(15, 0, 15, 0)
        
        title_label = QLabel("📊 실시간 전국 측정소 수질 및 탁도(Turbidity) 진단 지도")
        title_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #1A73E8;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        layout.addWidget(header_frame)
        
        # 2. PyQt6 QWebEngineView 지도 뷰어 영역 설정 [source: 5]
        self.web_view = QWebEngineView()
        
        # 로컬 파일 권한 및 외부 스크립트 실행 허용 설정 적용 [source: 5]
        settings = self.web_view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        
        layout.addWidget(self.web_view)

    def analyze_turbidity(self, turbidity_val: float) -> dict:
        """
        [탁도 진단 알고리즘]
        먹는물 수질 기준치에 근거한 실시간 탁도 판별 로직
        - 0.5 NTU 이하 : 정상 (Good)
        - 0.5 초과 1.0 이하 : 주의 (Caution)
        - 1.0 초과 : 경고 (Warning)
        """
        if turbidity_val is None:
            return {"status": "데이터 미측정", "color": "#7F8C8D", "desc": "계측기 신호 부재 또는 데이터 유실"}
        
        if turbidity_val <= 0.5:
            return {
                "status": "정상",
                "color": "#2ECC71",  # Green
                "desc": f"탁도 {turbidity_val} NTU (수질 기준치 0.5 NTU 충족)"
            }
        elif turbidity_val <= 1.0:
            return {
                "status": "주의",
                "color": "#F39C12",  # Orange
                "desc": f"탁도 {turbidity_val} NTU (정수 처리 효율 저하 우려)"
            }
        else:
            return {
                "status": "경고",
                "color": "#E74C3C",  # Red
                "desc": f"탁도 {turbidity_val} NTU 초과 (긴급 필터 역세척 및 수질 점검 필요)"
            }

    def get_latest_measurements(self):
        """각 측정소별 최신 측정 시각에 부합하는 수질 데이터를 DB에서 일괄 풀링(Pooling)"""
        try:
            # 1. 측정소 FK 컬럼인 'station_code' 기준으로 최근 측정 시각 추출하는 서브쿼리 작성 (컬럼명 수정 반영)
            subquery = self.session.query(
                WaterQuality.station_code,
                func.max(WaterQuality.measured_at).label("latest_time")
            ).group_by(WaterQuality.station_code).subquery()

            # 2. 서브쿼리와 실제 테이블 조인 수행 (컬럼 속성 매핑 전면 수정)
            query_results = self.session.query(Station, WaterQuality).join(
                subquery,
                (WaterQuality.station_code == subquery.c.station_code) &
                (WaterQuality.measured_at == subquery.c.latest_time)
            ).join(Station, Station.code == WaterQuality.station_code).all()
            
            return query_results
        except Exception as e:
            logger.exception("대시보드 최신 수질 데이터베이스 질의 중 오류 발생")
            return []

    def refresh_dashboard(self):
        """데이터베이스 상태를 파악하여 지도를 새로 생성하고 QWebEngineView에 리로드합니다."""
        m = folium.Map(location=[36.5, 127.8], zoom_start=7, tiles="OpenStreetMap")
        
        data_list = self.get_latest_measurements()
        
        if not data_list:
            # DB가 완전히 비었을 때 표출할 더미 홈 마커
            folium.Marker(
                location=[36.5, 127.8],
                popup="시스템 내에 수집된 수질 측정 데이터가 전혀 존재하지 않습니다.",
                icon=folium.Icon(color='gray', icon='info-sign')
            ).add_to(m)
        else:
            # 실시간 계측 데이터 지도 내 마커 빌드
            for station, quality in data_list:
                # 위경도 데이터 결손 처리 예외 방어 (lat, lon 으로 변경)
                if not station.lat or not station.lon:
                    continue
                
                # 탁도 진단 결과 산출
                diagnosis = self.analyze_turbidity(quality.turbidity)
                
                # 가독성을 확보한 반응형 인포 팝업 UI 마크업 작성
                popup_content = f"""
                <div style="font-family: 'Segoe UI', sans-serif; font-size: 12px; width: 230px;">
                    <h5 style="margin: 0 0 5px 0; color: #1A73E8; font-weight: bold; border-bottom: 2px solid #1A73E8; padding-bottom: 3px;">
                        📍 {station.name} 측정소
                    </h5>
                    <table style="width: 100%; border-collapse: collapse; margin-top: 5px;">
                        <tr style="border-bottom: 1px solid #EEE;">
                            <td style="font-weight: bold; padding: 4px 0;">측정소 코드</td>
                            <td style="text-align: right; color: #555;">{station.code}</td>
                        </tr>
                        <tr style="border-bottom: 1px solid #EEE;">
                            <td style="font-weight: bold; padding: 4px 0;">측정 일시</td>
                            <td style="text-align: right; color: #555;">{quality.measured_at.strftime('%Y-%m-%d %H:%M') if quality.measured_at else 'N/A'}</td>
                        </tr>
                        <tr style="border-bottom: 1px solid #EEE;">
                            <td style="font-weight: bold; padding: 4px 0;">탁도 수치</td>
                            <td style="text-align: right; font-weight: bold; color: {diagnosis['color']};">{quality.turbidity if quality.turbidity is not None else 'N/A'} NTU</td>
                        </tr>
                        <tr style="border-bottom: 1px solid #EEE;">
                            <td style="font-weight: bold; padding: 4px 0;">수질 상태</td>
                            <td style="text-align: right; font-weight: bold; color: {diagnosis['color']};">{diagnosis['status']}</td>
                        </tr>
                        <tr style="border-bottom: 1px solid #EEE;">
                            <td style="font-weight: bold; padding: 4px 0;">수온 (℃)</td>
                            <td style="text-align: right; color: #555;">{quality.water_temp if quality.water_temp is not None else 'N/A'} ℃</td>
                        </tr>
                        <tr style="border-bottom: 1px solid #EEE;">
                            <td style="font-weight: bold; padding: 4px 0;">수소 이온(pH)</td>
                            <td style="text-align: right; color: #555;">{quality.ph if quality.ph is not None else 'N/A'}</td>
                        </tr>
                    </table>
                    <div style="margin-top: 8px; padding: 6px; background-color: #F8F9FA; border-left: 3px solid {diagnosis['color']}; font-size: 11px; line-height: 1.4; color: #333;">
                        💡 <b>종합 판정:</b> {diagnosis['desc']}
                    </div>
                </div>
                """
                
                # 반경 9px 스케일의 서클 마커 생성 후 바인딩
                folium.CircleMarker(
                    location=[station.lat, station.lon],
                    radius=9,
                    popup=folium.Popup(popup_content, max_width=260),
                    color=diagnosis['color'],
                    fill=True,
                    fill_color=diagnosis['color'],
                    fill_opacity=0.75,
                    weight=1.5
                ).add_to(m)

        # 3. 로컬 프로젝트 디렉토리에 map.html 저장 후 QWebEngineView 로드 [source: 5]
        map_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "map_dashboard.html"))
        
        try:
            m.save(map_file_path)
            self.web_view.setUrl(QUrl.fromLocalFile(map_file_path))
            logger.info("수질 진단 지도 뷰어 업데이트 완료")
        except Exception as e:
            logger.error(f"Folium 지도 파일 생성 도중 파일 시스템 쓰기 실패: {str(e)}")

    def update_charts(self):
        """
        Main Window 스레드 워커와의 연동 규격 호환을 위한 공용 대리자 메서드
        """
        logger.info("동기화 이벤트 통지 수신: 지도를 실시간으로 리프레시합니다.")
        self.refresh_dashboard()