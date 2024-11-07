#######################
# Import libraries
import streamlit as st
import pandas as pd
import altair as alt
import geopandas as gpd
from shapely import wkb
from streamlit import components
import re
import folium
import tempfile

#######################
# Page configuration
st.set_page_config(
    page_title="RM Analysis Dashboard",
    page_icon="🏂",
    layout="wide",
    initial_sidebar_state="expanded")

alt.themes.enable("dark")

#######################
# CSS styling
st.markdown("""
    <style>
        /* 전체 배경과 기본 텍스트 색상 */
        body, [data-testid="stAppViewContainer"], [data-testid="stHeader"], [data-testid="stSidebar"] {
            background-color: #1e1e1e;
            color: white;
        }

        /* 사이드바 배경색을 회색으로 변경 */
        [data-testid="stSidebar"] {
            background-color: #333333; /* 회색 */
            color: white;
            width: 150px; /* 사이드바 너비 조정 */
        }

        /* 헤드 색상 하얀색으로 변경 */
        h1, h2, h3, h4, h5, h6 {
            color: white; /* 모든 헤드 색상 하얀색 */
        }

        /* 메인 컨텐츠 영역 배경과 텍스트 색상 */
        [data-testid="block-container"] {
            background-color: #1e1e1e;
            color: white;
        }

        /* 기본 버튼 스타일 */
        .css-1q8dd3e, .css-1x8cf1d {
            background-color: #333333 !important;
            color: white !important;
            border: none;
        }
        .css-1q8dd3e:hover, .css-1x8cf1d:hover {
            background-color: #555555 !important;
        }

        /* 입력 필드 스타일 */
        .css-1n543e5, .css-1cpxqw2, .css-2trqyj {
            background-color: #333333 !important;
            color: white !important;
            border-color: #555555 !important;
        }

        /* Selectbox, Text Input 등 상호작용 요소 */
        .css-1msv8hy {
            background-color: #333333 !important;
            color: white !important;
        }
        .css-1msv8hy:hover {
            background-color: #555555 !important;
        }

        /* Metric 컴포넌트 배경과 텍스트 */
        [data-testid="stMetric"] {
            background-color: #393939 !important;
            color: white !important;
            text-align: center;
            padding: 15px 0;
            border-radius: 8px;
        }

        [data-testid="stMetricLabel"], [data-testid="stMetricValue"], [data-testid="stMetricDelta"] {
            color: white !important;
        }

        /* Metric Delta Icon 스타일 */
        [data-testid="stMetricDeltaIcon-Up"] {
            color: #9acd32 !important; /* Green for up */
        }

        [data-testid="stMetricDeltaIcon-Down"] {
            color: #ff6347 !important; /* Red for down */
        }

        /* 테이블 스타일 */
        .css-1jqr9d3 {
            background-color: #333333 !important;
            color: white !important;
        }

        /* 기타 텍스트 및 링크 색상 */
        a, a:visited {
            color: #1f77b4; /* 링크 색상 */
        }
        a:hover {
            color: #ff6347; /* 링크 호버 색상 */
        }

    </style>
""", unsafe_allow_html=True)

#######################
# Load data functions
@st.cache_data
def load_rm_data():

    # RM 데이터 로드 (기존 데이터)
    df = pd.read_csv('data/RM-sgg_nm_reshaped.csv', encoding='EUC-KR')

    return df

@st.cache_data
def load_geo_data():
    # 지도 데이터 로드 (새로운 데이터)
    df = pd.read_csv('data/ldong_with_geo.csv')
    
    # geometry 컬럼 처리
    def clean_hex_string(hex_string):
        return re.sub(r'[^0-9A-Fa-f]', '', hex_string)
    
    def safe_wkb_loads(hex_string):
        try:
            return wkb.loads(hex_string, hex=True)
        except Exception as e:
            print(f"Error loading geometry: {e}")
            return None
    
    # geometry 처리
    df['geometry'] = df['geometry'].apply(clean_hex_string)
    df['geometry'] = df['geometry'].apply(safe_wkb_loads)
    df = df.dropna(subset=['geometry'])
    
    return df

#######################
# Visualization functions
def make_heatmap(input_df, input_y, input_x, input_color, input_color_theme):
    heatmap = alt.Chart(input_df).mark_rect().encode(
        y=alt.Y('RM_type:O', axis=alt.Axis(title="RM Type", titleFontSize=16, titlePadding=15, titleFontWeight=900, labelAngle=0)),
        x=alt.X('mcp_nm:O', axis=alt.Axis(title="Region", titleFontSize=16, titlePadding=15, titleFontWeight=900)),
        color=alt.Color('RM_sum:Q',
                        legend=alt.Legend(title="Sum of RM"),
                        scale=alt.Scale(scheme=input_color_theme)),
        tooltip=[
            alt.Tooltip('mcp_nm:O', title='Region'),
            alt.Tooltip('RM_type:O', title='RM Type'),
            alt.Tooltip('RM_sum:Q', title='Sum of RM')
        ]
    ).properties(
        width=800,
        height=300
    ).configure_axis(
        labelFontSize=12,
        titleFontSize=12
    )
    return heatmap

def make_choropleth(input_df, input_id, input_column, input_color_theme):
    try:
        # GeoDataFrame 생성
        gdf = gpd.GeoDataFrame(input_df, geometry='geometry')
        gdf = gdf.set_crs(epsg=4326)
        
        # Tooltip에 표시할 열 목록
        tooltip_fields = ['ldong_nm', 'sgg_nm', 'sum_infu', 'cnt_cbl', 'top', 
                          'cnt_cnpt', 'cnt_cdln', 'cnt_crs', 'cnt_dh', 'cnt_abd', 'cnt_mtso']
        
        # 각 열에서 결측값을 '없음'으로 대체하고, 문자열로 변환
        for col in tooltip_fields:
            if col in gdf.columns:
                gdf[col] = gdf[col].astype(str).replace(['nan', 'None'], '없음')
        
        # 지도 생성 (서울을 중심으로)
        initial_location = [37.5665, 126.9780]  # 서울의 위도와 경도

        m = folium.Map(
            location=initial_location,
            zoom_start=10
        )
        
        # 색상 매핑 정의
        color_map = {
            '50만': '#FF0000',  # 빨강
            '40만': '#FF4500',  # 오렌지레드
            '30만': '#FFA500',  # 오렌지
            '20만': '#FFD700',  # 골드
            '10만': '#FFFF00',  # 노랑
            '5만': '#9ACD32',   # 옐로우그린
            '1만': '#008000',   # 녹색
            '5천': '#4682B4',    # 스틸블루
            '그외': '#A9A9A9'   # 다크그레이
        }

        # GeoJSON 스타일 함수
        def style_function(feature):
            top = feature['properties'].get('top', '그외')
            color = color_map.get(top, color_map['그외'])
            return {
                'fillColor': color,
                'color': 'black',
                'weight': 1,
                'fillOpacity': 0.7,
            }

        # GeoJSON 레이어 추가
        folium.GeoJson(
            data=gdf,
            style_function=style_function,
            tooltip=folium.GeoJsonTooltip(
                fields=tooltip_fields,
                aliases=['동 이름:', '시군구:', '영향력 합계:', '케이블 합계:', '구분:', 
                         '함체:', '관로:', '횡단:', '선로밀집:', 'ABD:', '통합국:'],
                localize=True,
                sticky=True,
                labels=True,
                style="""
                    background-color: black; color: white; font-family: Arial; font-size: 12px;
                """,
                parse_html=True
            )
        ).add_to(m)

        # 범례 추가
        legend_html = '''
        <div style="position: fixed; top: 20px; right: 20px; width: 80px; height: auto; 
                    border:2px solid grey; z-index:9999; font-size:14px; background-color:black; color:white; 
                    opacity: 0.9; padding: 5px;">
            &nbsp;<b>구분</b><br>
        '''
        for label, color in color_map.items():
            legend_html += f'&nbsp;<i class="fa fa-square fa-1x" style="color:{color}"></i> {label}<br>'
        legend_html += '</div>'
        m.get_root().html.add_child(folium.Element(legend_html))

        # Folium 지도를 HTML 문자열로 변환
        return m._repr_html_()

    except Exception as e:
        st.error(f"Error loading map: {str(e)}")
        return None




# Donut chart
def make_donut(input_response, input_text, input_color, label):
    if input_color == 'blue':
        chart_color = ['#29b5e8', '#155F7A']
    if input_color == 'green':
        chart_color = ['#27AE60', '#12783D']
    if input_color == 'orange':
        chart_color = ['#F39C12', '#875A12']
    if input_color == 'red':
        chart_color = ['#E74C3C', '#781F16']

    source = pd.DataFrame({
        "Topic": ['', input_text],
        "% value": [100-input_response, input_response]
    })
    source_bg = pd.DataFrame({
        "Topic": ['', input_text],
        "% value": [100, 0]
    })

    plot = alt.Chart(source).mark_arc(innerRadius=45, cornerRadius=25).encode(
        theta="% value",
        color= alt.Color("Topic:N", scale=alt.Scale(
            domain=[input_text, ''],
            range=chart_color),
            legend=None),
    ).properties(width=130, height=130)

    text = plot.mark_text(align='center', color="#29b5e8", font="Lato", fontSize=32, fontWeight=700, fontStyle="italic").encode(text=alt.value(f'{input_response} %'))
    
    label_text = alt.Chart(pd.DataFrame({'label': [label]})).mark_text(
        align='center', baseline='bottom', dy=-10, fontSize=14, fontWeight=500
    ).encode(text='label:N').properties(width=130, height=20)

    plot_bg = alt.Chart(source_bg).mark_arc(innerRadius=45, cornerRadius=20).encode(
        theta="% value",
        color= alt.Color("Topic:N", scale=alt.Scale(
            domain=[input_text, ''],
            range=chart_color),
            legend=None),
    ).properties(width=130, height=130)

    return (plot_bg + plot + text) & label_text


#######################
# Sidebar
with st.sidebar:
    st.title('🏂 RM Analysis')
    
    # RM 데이터 로드
    df = load_rm_data()
    
    # RM 유형 선택
    # st.header('Filter')
    rm_types = ['전체'] + df['RM_type'].unique().tolist()  # '전체' 옵션 추가
    selected_rm = st.selectbox(
        'Select RM Type',
        rm_types,
        index=0
    )
    
    # 데이터 필터링 수정
    if selected_rm == '전체':
        df_selected_rm = df
    else:
        df_selected_rm = df[df['RM_type'] == selected_rm]
    
    # 색상 마 선택
    color_theme_list = ['blueorange', 'blues', 'cividis', 'greens', 'inferno', 'magma', 
                       'plasma', 'reds', 'rainbow', 'turbo', 'viridis']
    selected_color_theme = st.selectbox(
        'Select Color Theme',
        color_theme_list
    )
    
    # About 섹션
    with st.expander('About', expanded=True):
        st.write('''
            - Data: RM Analysis Dashboard
            - 🔸 Map: Shows geographical distribution of influence
            - 🔸 Heatmap: Shows RM type distribution by region
            ''')

#######################
# Main content
# 데이터 필터링 수정
if selected_rm == '전체':
    df_selected_rm = df  # 전체 데이터 유지
else:
    df_selected_rm = df[(df['RM_type'] == selected_rm) & (df['RM'] > 0)]

# 히트맵을 위한 데이터 그룹핑 수정
if selected_rm == '전체':
    # 각 RM_type과 mcp_nm 조합에 대해 한 번만 합계
    df_grouped = (df.groupby(['RM_type', 'mcp_nm'])
                   .agg({'RM': 'sum'})  # 각 그룹의 첫 번째 값만 사용
                   .reset_index()
                   .rename(columns={'RM': 'RM_sum'}))
else:
    df_grouped = (df_selected_rm.groupby(['RM_type', 'mcp_nm'])
                   .agg({'RM': 'sum'})
                   .reset_index()
                   .rename(columns={'RM': 'RM_sum'}))

# 지도 데이터 로드
geo_df = load_geo_data()

# 레이아웃 설정
col = st.columns([1, 4.7, 1.2], gap='small')


with col[0]:
    st.markdown('#### Top Influence')

    # 가장 영향도가 높은 동 계산 (distinct)
    top_dong = df_selected_rm[['ldong_nm', 'sum_infu']].drop_duplicates(subset=['ldong_nm']).reset_index(drop=True)
    top_dong_sorted = top_dong.sort_values('sum_infu', ascending=False)

    # 가장 RM이 많은 타입 계산 (전체 데이터에서)
    if selected_rm == '전체':
        top_rm = df.groupby('RM_type')['RM'].sum().reset_index()  # 각 RM_type의 총합 사용
    else:
        top_rm = df_selected_rm.groupby('RM_type')['RM'].sum().reset_index()

    top_rm_sorted = top_rm.sort_values('RM', ascending=False)

    # Top Region 표시
    if not top_dong_sorted.empty and pd.notna(top_dong_sorted.sum_infu.iloc[0]):
        first_dong_name = top_dong_sorted.ldong_nm.iloc[0]
        first_dong_infu = int(top_dong_sorted.sum_infu.iloc[0])
        st.metric(label="Top Region", value=first_dong_name, 
                 delta=f"Influence: {first_dong_infu:,}")
    else:
        st.metric(label="Top Region", value="No data", delta="0")

    # Top RM Type 표시
    if not top_rm_sorted.empty and pd.notna(top_rm_sorted.RM.iloc[0]):
        first_rm_type = top_rm_sorted.RM_type.iloc[0]
        first_rm_count = int(top_rm_sorted.RM.iloc[0])
        st.metric(label="(Top)RM Count", value=first_rm_type, 
                 delta=f"Count: {first_rm_count:,}")
    else:
        st.metric(label="Top RM Type", value="No data", delta="0")




###########################################################################

    st.markdown('#### Proportion')

    # MCP_NM 비율 계산
    total_mcp = df_selected_rm.groupby('mcp_nm')['RM'].sum()
    if not total_mcp.empty and total_mcp.sum() != 0:
        top_mcp = total_mcp.idxmax()
        top_mcp_ratio = (total_mcp.max() / total_mcp.sum() * 100)
    else:
        top_mcp = "N/A"
        top_mcp_ratio = 0

    donut_mcp = make_donut(round(top_mcp_ratio), 'Top Province Ratio', 'green', top_mcp)

    # MCP_NM 내에서 가장 영향도가 높은 동 찾기
    top_dong_per_mcp = df_selected_rm.groupby(['mcp_nm', 'ldong_nm'])['RM'].sum().reset_index()

    # 선택된 top_mcp에 해당하는 동만 필터링
    if selected_rm == '전체':
        # 전체 mcp_nm 가져오기
        top_mcp_filtered = [top_mcp]  # top_mcp만 필터링
    else:
        # 선택된 RM type에 해당하는 mcp_nm 가져오기
        top_mcp_filtered = df_selected_rm['mcp_nm'].unique().tolist()

    # top_mcp_filtered에 해당하는 동만 필터링
    top_dong_per_mcp_sorted = top_dong_per_mcp[top_dong_per_mcp['mcp_nm'].isin(top_mcp_filtered)].sort_values(['mcp_nm', 'RM'], ascending=[True, False])

    # 비율 계산
    top_dong_per_mcp_sorted['RM_count'] = top_dong_per_mcp_sorted['RM']  # Assuming 'sum_infu' represents the count of RM

    # 각 mcp_nm 내에서 RM_count의 총합 계산
    total_rm_count_per_mcp = top_dong_per_mcp_sorted.groupby('mcp_nm')['RM_count'].transform('sum')

    # 비율 계산
    top_dong_per_mcp_sorted['ratio'] = (top_dong_per_mcp_sorted['RM_count'] / total_rm_count_per_mcp) * 100

    # 가장 영향도가 높은 동과 그 비율 찾기
    if not top_dong_per_mcp_sorted.empty:
        top_ldong = top_dong_per_mcp_sorted.loc[top_dong_per_mcp_sorted['ratio'].idxmax()]
        top_ldong_name = top_ldong['ldong_nm']
        top_ldong_ratio = top_ldong['ratio']
    else:
        top_ldong_name = "N/A"
        top_ldong_ratio = 0

    # Donut chart 생성
    donut_rm = make_donut(round(top_ldong_ratio), 'Top District Ratio', 'red', top_ldong_name)

    st.write('Top RM Province')
    st.altair_chart(donut_mcp)
    st.write('Top RM District')
    st.altair_chart(donut_rm)



# 시각화 부분
with col[1]:
    st.markdown('#### RM Distribution')
    
    # 지도는 한 번만 로드하고 HTML 컴포넌트로 표시
    if 'choropleth_map' not in st.session_state:
        map_html = make_choropleth(geo_df, 'ldong_nm', 'sum_infu', selected_color_theme)
        if map_html:
            st.session_state.choropleth_map = map_html
            st.components.v1.html(map_html, height=600)
    else:
        st.components.v1.html(st.session_state.choropleth_map, height=600)

    # 히트맵은 RM Type에 따라 업데이트
    heatmap = make_heatmap(df_grouped, 'RM_type', 'mcp_nm', 'RM_sum', selected_color_theme)
    st.altair_chart(heatmap, use_container_width=True)

    # Top Regions 표시 수정 (col[2])
    with col[2]:
        st.markdown('##### Top Regions(inf)')
        
        # 상위 지역 데이터 준비
        if selected_rm == '전체':
            # 전체 데이터에서 각 동별로 첫 번째 값만 사용
            df_top = (df.groupby('ldong_nm')
                       .agg({'sum_infu': 'first'})  # 각 동의 첫 번째 값만 사용
                       .reset_index())
        else:
            # 선택된 RM type에 대해서는 합계 계산
            df_top = (df_selected_rm.groupby('ldong_nm')
                       .agg({'sum_infu': 'sum'})
                       .reset_index())
        
        
        # 영향도 기준으로 정렬
        df_top_sorted = df_top.sort_values('sum_infu', ascending=False).head(10)
        
        if not df_top_sorted.empty:
            # 데이터프레임 표시
            st.dataframe(df_top_sorted,
                        hide_index=True,
                        column_config={
                            "ldong_nm": st.column_config.TextColumn(
                                "Region",
                            ),
                            "sum_infu": st.column_config.ProgressColumn(
                                "Influence",
                                format="%d",
                                min_value=0,
                                max_value=int(df_top_sorted['sum_infu'].max()),
                            )}
                        )
        else:
            st.info("No data available for the selected filter.")


        st.markdown('##### Top Regions(RM cnt)')
        
        # 상위 지역 데이터 준비
        if selected_rm == '전체':
            # 전체 데이터에서 각 동별로 첫 번째 값만 사용
            df_top = (df.groupby('ldong_nm')
                       .agg({'RM': 'sum'})  # 각 동의 첫 번째 값만 사용
                       .reset_index())
        else:
            # 선택된 RM type에 대해서는 합계 계산
            df_top = (df_selected_rm.groupby('ldong_nm')
                       .agg({'RM': 'sum'})
                       .reset_index())
        
        
        # 영향도 기준으로 정렬
        df_top_sorted = df_top.sort_values('RM', ascending=False).head(10)
        
        if not df_top_sorted.empty:
            # 데이터프레임 표시
            st.dataframe(df_top_sorted,
                        hide_index=True,
                        column_config={
                            "ldong_nm": st.column_config.TextColumn(
                                "Region",
                            ),
                            "RM": st.column_config.ProgressColumn(
                                "RM count",
                                format="%d",
                                min_value=0,
                                max_value=int(df_top_sorted['RM'].max()),
                            )}
                        )
        else:
            st.info("No data available for the selected filter.")

