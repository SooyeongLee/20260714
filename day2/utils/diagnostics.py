def analyze_turbidity(turbidity_val: float) -> dict:
    """
    먹는물 수질기준 및 실시간 계측 특성을 고려한 탁도 진단 알고리즘
    :param turbidity_val: 탁도 측정값 (NTU)
    :return: { "status": "정상"|"주의"|"경고", "color": "green"|"orange"|"red", "desc": "설명" }
    """
    if turbidity_val is None:
        return {"status": "데이터 없음", "color": "gray", "desc": "계측 장비 미연결 또는 데이터 유실"}
    
    # 1. 법적 정수 기준치 (0.5 NTU 이하: 정상)
    if turbidity_val <= 0.5:
        return {
            "status": "정상",
            "color": "green",
            "desc": f"탁도 {turbidity_val} NTU (법적 정수 기준치 0.5 NTU 만족)"
        }
    # 2. 일반 정수장 운영 관리 기준치 (0.5 ~ 1.0 NTU: 주의 단계 및 모니터링 강화)
    elif turbidity_val <= 1.0:
        return {
            "status": "주의",
            "color": "orange",
            "desc": f"탁도 {turbidity_val} NTU (기준치 초과 우려, 응집제 투여량 조절 검토 권장)"
        }
    # 3. 공급 제한 및 긴급 점검 기준치 (1.0 NTU 초과: 즉시 조치 필요)
    else:
        return {
            "status": "경고",
            "color": "red",
            "desc": f"탁도 {turbidity_val} NTU (심각한 수질 저하 발생, 바이패스 및 필터 역세척 즉시 실행 필요)"
        }