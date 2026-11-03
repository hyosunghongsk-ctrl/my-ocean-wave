import os
import base64
import requests
import pandas as pd
import folium
import streamlit as st
from streamlit_folium import st_folium
from urllib.parse import unquote
from datetime import datetime, timedelta

# 페이지 레이아웃 및 제목 설정
st.set_page_config(page_title="우리집 앞 바다 파도 정보", layout="wide")
st.title("🌊 우리집 앞 바다 실측 및 해상예보")

# ==========================================
# 1. API 설정 및 키 준비
# ==========================================
encoding_key = "l7bVtvGzEkSAJeXtrvF5K5LIfYiKKIpdCY7JuRMjk03vx44ukIjjT3KCRtISBOAZk6R3WzWUkMzxuLOdhFYZEg%3D%3D"
decoding_key = unquote(encoding_key)
today = datetime.now()
today_str = today.strftime("%Y%m%d")

# A. 국립해양조사원 실측 API
url_real = "https://apis.data.go.kr/1192136/noonWave/GetNoonWaveApiService"
params_real = {
    "serviceKey": decoding_key,
    "reqDate": today_str,
    "obsCode": "TW_0095",
    "type": "json",
    "pageNo": "1",
    "numOfRows": "300",
    "min": "30"
}

# B. 기상청 해상예보 API
url_fcst = "http://apis.data.go.kr/1360000/VilageFcstMsgService/getSeaFcst"
params_fcst = {
    "serviceKey": decoding_key,
    "pageNo": "1",
    "numOfRows": "10",
    "dataType": "JSON",
    "regId": "12C10102"
}

# ==========================================
# 2. 파도 사진 매칭 및 Base64 변환 함수
# ==========================================
def get_wave_image_html(wave_str):
    if not wave_str or wave_str == '-':
        return '-'
    try:
        val_part = wave_str.replace('m', '').strip()
        min_val = float(val_part.split('~')[0].strip()) if '~' in val_part else float(val_part)
            
        if 0.2 <= min_val <= 0.39:
            file_name = "02파도.png"
        elif 0.4 <= min_val <= 0.59:
            file_name = "04파도.png"
        elif 0.6 <= min_val <= 0.79:
            file_name = "06파도.png"
        elif 0.8 <= min_val <= 0.99:
            file_name = "08파도.png"
        elif 1.0 <= min_val <= 1.99:
            file_name = "10파도.png"    
        else:
            file_name = f"{int(min_val):02d}파도.png"
            
        img_path = os.path.join("wave", file_name)
        if not os.path.exists(img_path):
            img_path = os.path.join("wave", "04파도.png")
            
        if os.path.exists(img_path):
            with open(img_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode()
            img_src = f"data:image/png;base64,{encoded_string}"
            return f'<img src="{img_src}" width="68" height="45" style="object-fit:cover; border-radius:4px; vertical-align:middle;"/>'
        return '-'
    except Exception:
        return '-'

# ==========================================
# 3. 날씨 이모티콘 변환 함수
# ==========================================
def add_weather_emoji(wf_text):
    if not wf_text or wf_text == '-':
        return '-'
    emojis = []
    if '맑' in wf_text: emojis.append("☀️")
    if '구름' in wf_text: emojis.append("⛅")
    if '흐' in wf_text: emojis.append("☁️")
    if '비' in wf_text or '소나기' in wf_text: emojis.append("🌧️")
    if '눈' in wf_text: emojis.append("❄️")
    
    emoji_str = (" & ".join(emojis) + " ") if len(emojis) >= 2 else ((emojis[0] + " ") if len(emojis) == 1 else "")
    return f"{emoji_str}{wf_text}"

# ==========================================
# 4. 실시간 데이터 가져오기 및 통합
# ==========================================
try:
    # 실측 데이터
    res_real = requests.get(url_real, params=params_real)
    items_real = res_real.json()["body"]["items"]["item"]
    df_real = pd.DataFrame(items_real)
    df_real['datetime'] = pd.to_datetime(df_real['obsrvnDt'])
    recent_real = df_real[df_real['datetime'].dt.minute.isin([0, 30])].sort_values('datetime').tail(2).copy()

    # 예보 데이터
    res_fcst = requests.get(url_fcst, params=params_fcst)
    fcst_rows = []
    if res_fcst.status_code == 200 and 'response' in res_fcst.json():
        items_fcst = res_fcst.json()['response']['body']['items']['item']
        for item in items_fcst:
            num_ef = int(item.get('numEf', 0))
            target_date = today + timedelta(days=(num_ef + 1) // 2)
            time_label = f"{target_date.strftime('%m_%d')} {'오후' if num_ef % 2 == 0 else '오전'}(예측)"
            wh1, wh2 = item.get('wh1'), item.get('wh2')
            wave_fcst_str = f"{wh1} ~ {wh2}m" if wh1 and wh2 else f"{wh1 or wh2 or '-'}m"
            
            fcst_rows.append({
                '일시': time_label,
                '날씨': add_weather_emoji(item.get('wf', '-')),
                '파고_통합': wave_fcst_str,
                '파주기': '-',
                '풍속': f"{item.get('ws1', '-')} ~ {item.get('ws2', '-')}m/s"
            })
    df_fcst_summary = pd.DataFrame(fcst_rows)

    combined_rows = []
    for _, row in recent_real.iterrows():
        wave_val = f"{float(row['wvhgt']):.1f}m"
        combined_rows.append({
            '일시': row['datetime'].strftime('%m_%d %H:%M'),
            '날씨': '-',
            '파고/예측(m)': wave_val,
            '파주기(s)': f"{float(row['wvpd']):.1f}",
            '풍속': '-',
            '파도 사진': get_wave_image_html(wave_val)
        })

    for _, row in df_fcst_summary.iterrows():
        wave_val = row['파고_통합']
        combined_rows.append({
            '일시': row['일시'],
            '날씨': row['날씨'],
            '파고/예측(m)': wave_val,
            '파주기(s)': row['파주기'],
            '풍속': row['풍속'],
            '파도 사진': get_wave_image_html(wave_val)
        })

    final_df = pd.DataFrame(combined_rows)
    table_html = final_df.to_html(index=False, escape=False, classes='table table-striped table-hover', justify='center')

    # ==========================================
    # 5. Esri 타일을 적용한 Folium 지도 생성
    # ==========================================
    FIXED_LAT, FIXED_LOT = 36.3446379315253, 129.386231597459

    popup_html = f"""
    <div style="width: 500px; max-height: 400px; overflow-y: auto;">
        <h4 style="margin-bottom: 6px;"><b>🏡 우리집 앞 바다 (TW_0095)</b></h4>
        <p style="margin-top: 0; color: #555;">📍 위치: {FIXED_LAT:.6f}, {FIXED_LOT:.6f}</p>
        <style>
            table {{ border-collapse: collapse; width: 100%; font-size: 13px; text-align: center; }}
            th {{ background-color: #e9ecef; position: sticky; top: 0; padding: 6px; }}
            td {{ padding: 6px; border-bottom: 1px solid #ddd; vertical-align: middle; }}
        </style>
        {table_html}
    </div>
    """

    popup = folium.Popup(popup_html, max_width=520, show=False)

    # Esri 타일 사용 (OSM/CartoDB 차단 및 키 요구 우회)
    m = folium.Map(
        location=[FIXED_LAT, FIXED_LOT],
        zoom_start=15,
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
        attr="Esri"
    )

    folium.Marker(
        location=[FIXED_LAT, FIXED_LOT],
        popup=popup,
        tooltip="우리집 앞 바다 실측 및 예보 정보",
        icon=folium.Icon(color='red', icon='home')
    ).add_to(m)

    # Streamlit 화면에 지도 띄우기
    st_folium(m, width=1200, height=600)

except Exception as e:
    st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
