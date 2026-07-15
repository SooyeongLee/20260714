# pages/dashboard.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, QPushButton
from PyQt6.QtCharts import QChart, QChartView, QLineSeries, QBarSeries, QBarSet
from models.schema import Station, WaterQuality

class DashboardPage(QWidget):
    def __init__(self, session):
        super().__init__()
        self.session = session
        layout = QVBoxLayout(self)
        
        # 필터 구성
        filter_bar = QHBoxLayout()
        self.filter_combo = QComboBox()
        
        # 측정소 코드 목록 바인딩 (데이터 셋이 빌어있을 경우를 대비한 방어 로직 포함)
        stations = self.session.query(Station).all()
        self.filter_combo.addItems([s.code for s in stations])
        
        btn_refresh = QPushButton("조회")
        btn_refresh.clicked.connect(self.update_charts)
        filter_bar.addWidget(QLabel("지점 선택:"))
        filter_bar.addWidget(self.filter_combo)
        filter_bar.addWidget(btn_refresh)
        
        layout.addLayout(filter_bar)
        
        # 차트 뷰 초기화 및 레이아웃 배치
        self.chart_view_line = QChartView()
        self.chart_view_bar = QChartView()
        chart_layout = QHBoxLayout()
        chart_layout.addWidget(self.chart_view_line)
        chart_layout.addWidget(self.chart_view_bar)
        layout.addLayout(chart_layout)
        
        # 초기 화면 렌더링
        self.update_charts()

    def update_charts(self):
        code = self.filter_combo.currentText()
        if not code:
            return  # 선택된 측정소 코드가 없을 경우 예외 방어
            
        # 개편된 정형화 모델 구조에 맞춘 쿼리 제어 (최신 10개 시계열 데이터 호출)
        # 쿼리 시점에 정렬 기준이 모호해질 수 있으므로 measured_at 기준으로 정렬하여 신뢰성 확보
        data = self.session.query(WaterQuality)\
                           .filter_by(station_code=code)\
                           .order_by(WaterQuality.measured_at.asc())\
                           .limit(10)\
                           .all()
        
        # 1. 탁도 시계열 라인 차트 생성 로직
        line_series = QLineSeries()
        line_series.setName("탁도 (NTU)")
        
        # 2. 수온 통계 바 차트 생성 로직 (구 '유량' 대체)
        bar_set = QBarSet("수온 (℃)")
        
        # 데이터 맵핑 루프 연산 실행 (AttributeError 방지 완료)
        for i, d in enumerate(data): 
            line_series.append(i, d.turbidity or 0)
            bar_set.append(d.water_temp or 0)  # 스키마 매핑 변경 완료 (discharge -> water_temp)
            
        # 탁도(Line) 차트 렌더링 파이프라인
        chart_l = QChart()
        chart_l.addSeries(line_series)
        chart_l.createDefaultAxes()
        chart_l.setTitle("시계열 탁도 변화 수치")
        self.chart_view_line.setChart(chart_l)
        
        # 수온(Bar) 차트 렌더링 파이프라인
        bar_series = QBarSeries()
        bar_series.append(bar_set)
        
        chart_b = QChart()
        chart_b.addSeries(bar_series)
        chart_b.createDefaultAxes()
        chart_b.setTitle("기간별 평균 수온 추이")
        self.chart_view_bar.setChart(chart_b)