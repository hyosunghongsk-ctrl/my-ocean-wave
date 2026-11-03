import os
import requests
import pandas as pd
import folium
from urllib.parse import unquote
from datetime import datetime, timedelta

# ==========================================
# 1. API 설정 및 키 준비
# ==========================================
encoding_key = "l7bVtvGzEkSAJeXtrvF5K5LIfYiKKIpdCY7JuRMjk03vx44ukIjjT3KCRtISBOAZk6R3WzWUkMzxuLOdhFYZEg%3D%3D"
decoding_key = unquote(encoding_key)
today = datetime.now()
today_str = today.strftime("%Y%m%d")

# A. 국립해양조사원 실측 API URL
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

# B. 기상청 해상예보 API URL (경북북부앞바다: 12C10102)
url_fcst = "http://apis.data.go.kr/1360000/VilageFcstMsgService/getSeaFcst"
params_fcst = {
    "serviceKey": decoding_key,
    "pageNo": "1",
    "numOfRows": "10",
    "dataType": "JSON",
    "regId": "12C10102"
}

# ==========================================
# 2. 파도 사진 매칭 함수 (.png 적용 & 1.5배 확대)
# ==========================================
def get_wave_image_html(wave_str):
    if not wave_str or wave_str == '-':
        return '-'
    
    try:
        val_part = wave_str.replace('m', '').strip()
        if '~' in val_part:
            min_val = float(val_part.split('~')[0].strip())
        else:
            min_val = float(val_part)
            
        # PNG 확장자 적용
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
            
        img_path = f"wave/{file_name}"
        
        # 파일 미존재 시 기본 04파도.png 사용
        if not os.path.exists(img_path):
            img_path = "wave/04파도.png"
            
        # 이미지 크기 1.5배 확대 (width: 68px, height: 45px)
        if os.path.exists(img_path):
            return f'<a href="{img_path}" target="_blank"><img src="{img_path}" width="68" height="45" style="object-fit:cover; border-radius:4px; vertical-align:middle;"/></a>'
        else:
            return '-'
            
    except Exception:
        return '-'

# ==========================================
# 3. 복합 날씨 이모티콘 변환 함수
# ==========================================
def add_weather_emoji(wf_text):
    if not wf_text or wf_text == '-':
        return '-'
    
    emojis = []
    if '맑' in wf_text:
        emojis.append("☀️")
    if '구름' in wf_text:
        emojis.append("⛅")
    if '흐' in wf_text:
        emojis.append("☁️")
    if '비' in wf_text or '소나기' in wf_text:
        emojis.append("🌧️")
    if '눈' in wf_text:
        emojis.append("❄️")
        
    if len(emojis) >= 2:
        emoji_str = " & ".join(emojis) + " "
    elif len(emojis) == 1:
        emoji_str = emojis[0] + " "
    else:
        emoji_str = ""
    
    return f"{emoji_str}{wf_text}"

# ==========================================
# 4. 실측 데이터 가져오기 및 최근 2행 처리
# ==========================================
res_real = requests.get(url_real, params=params_real)
items_real = res_real.json()["body"]["items"]["item"]
df_real = pd.DataFrame(items_real)

df_real['datetime'] = pd.to_datetime(df_real['obsrvnDt'])
filtered_real = df_real[df_real['datetime'].dt.minute.isin([0, 30])].sort_values('datetime')
recent_real = filtered_real.tail(2).copy()

# ==========================================
# 5. 해상예보 데이터 처리
# ==========================================
res_fcst = requests.get(url_fcst, params=params_fcst)
fcst_rows = []

if res_fcst.status_code == 200 and 'response' in res_fcst.json():
    items_fcst = res_fcst.json()['response']['body']['items']['item']
    
    for item in items_fcst:
        num_ef = int(item.get('numEf', 0))
        day_offset = (num_ef + 1) // 2
        target_date = today + timedelta(days=day_offset)
        mm_dd = target_date.strftime("%m_%d")
        
        ampm = "오후" if num_ef % 2 == 0 else "오전"
        time_label = f"{mm_dd} {ampm}(예측)"
        
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

# ==========================================
# 6. 데이터 통합
# ==========================================
combined_rows = []

# 1) 실측 데이터 2행 추가
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

# 2) 예보 데이터 추가
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

table_html = final_df.to_html(
    index=False,
    escape=False,
    classes='table table-striped table-hover',
    justify='center'
)

# ==========================================
# 7. Folium 지도 생성 (1.5배 폰트 및 레이아웃 확장)
# ==========================================
FIXED_LAT = 36.3446379315253
FIXED_LOT = 129.386231597459
obs_name = df_real['obsvtrNm'].iloc[0]

# 팝업 가로 너비 확장(680px), 높이 확장(580px)
popup_html = f"""
<div style="width: 680px; max-height: 580px; overflow-y: auto;">
    <h3 style="margin-bottom: 6px; font-size: 21px;"><b>🏡 우리집 앞 바다 (TW_0095)</b></h3>
    <p style="margin-top: 0; color: #555; font-size: 16px;">📍 위치: {FIXED_LAT:.6f}, {FIXED_LOT:.6f}</p>
    <p style="margin-top: 0; color: #0066cc; font-size: 16px;">📊 최근 실측 2건 + 기상청 해상예보</p>
    <style>
        /* 표 폰트 및 패딩 1.5배 확대 */
        table {{ border-collapse: collapse; width: 100%; font-size: 16px; text-align: center; }}
        th {{ background-color: #e9ecef; position: sticky; top: 0; padding: 10px; border-bottom: 2px solid #dee2e6; z-index: 10; font-size: 16px; }}
        td {{ padding: 8px 10px; border-bottom: 1px solid #ddd; vertical-align: middle; white-space: nowrap; font-size: 16px; }}
        tr:nth-child(n+{len(recent_real)+1}) {{ background-color: #f0f7ff; font-weight: bold; }}

        .leaflet-popup-tip-container {{
            top: 240px !important;
            left: 8px !important;
            right: auto !important;
            width: 12px !important;
            height: 16px !important;
            overflow: visible !important;
        }}

        .leaflet-popup-tip {{
            width: 0 !important;
            height: 0 !important;
            padding: 0 !important;
            margin: 0 !important;
            background: transparent !important;
            box-shadow: none !important;
            transform: none !important;
            
            border-top: 8px solid transparent !important;
            border-bottom: 8px solid transparent !important;
            border-right: 12px solid white !important;
            border-left: none !important;
        }}
    </style>
    {table_html}
</div>
"""

popup = folium.Popup(popup_html, max_width=700, show=True, offset=(400, 400))

m = folium.Map(
    location=[FIXED_LAT, FIXED_LOT],
    zoom_start=15,
    tiles="https://xdworld.vworld.kr/2d/Base/service/{z}/{x}/{y}.png",
    attr="Vworld Space"
)

folium.Marker(
    location=[FIXED_LAT, FIXED_LOT],
    popup=popup,
    tooltip="우리집 앞 바다 실측 및 예보 정보",
    icon=folium.Icon(color='red', icon='home')
).add_to(m)

m.save("ocean_wave_map.html")
print("1.5배 확대 및 .png 확장자가 반영된 지도 파일(ocean_wave_map.html)이 생성되었습니다.")