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
        self.filter_combo.addItems([s.code for s in self.session.query(Station).all()])
        btn_refresh = QPushButton("조회")
        btn_refresh.clicked.connect(self.update_charts)
        filter_bar.addWidget(QLabel("지점 선택:")); filter_bar.addWidget(self.filter_combo); filter_bar.addWidget(btn_refresh)
        
        layout.addLayout(filter_bar)
        self.chart_view_line = QChartView(); self.chart_view_bar = QChartView()
        chart_layout = QHBoxLayout()
        chart_layout.addWidget(self.chart_view_line); chart_layout.addWidget(self.chart_view_bar)
        layout.addLayout(chart_layout)
        self.update_charts()

    def update_charts(self):
        code = self.filter_combo.currentText()
        data = self.session.query(WaterQuality).filter_by(station_code=code).limit(10).all()
        line_series = QLineSeries(); bar_set = QBarSet("유량")
        for i, d in enumerate(data): line_series.append(i, d.turbidity or 0); bar_set.append(d.discharge or 0)
        chart_l = QChart(); chart_l.addSeries(line_series); chart_l.createDefaultAxes(); chart_l.setTitle("탁도")
        self.chart_view_line.setChart(chart_l)
        bar_series = QBarSeries(); bar_series.append(bar_set)
        chart_b = QChart(); chart_b.addSeries(bar_series); chart_b.createDefaultAxes(); chart_b.setTitle("유량")
        self.chart_view_bar.setChart(chart_b)