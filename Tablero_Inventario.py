import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import json

# --- CONFIGURACION DE GOOGLE SHEETS ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# Leer credenciales desde Streamlit Secrets
creds_dict = st.secrets["GOOGLE_CREDENTIALS"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

# --- CARGA DE DATOS ---
try:
    sheet = client.open_by_key("12SNgRgSuoTjVx0EergC4BeDOipRUmCWptiz66MVZb_w")
except Exception as e:
    st.error("❌ Error accediendo al archivo de Google Sheets. Verifica que el ID sea correcto y que esté compartido con el correo del servicio.")
    st.stop()


productos_df = pd.DataFrame(sheet.worksheet("productos").get_all_records())
bodega1_df = pd.DataFrame(sheet.worksheet("inventario_bodega1").get_all_records())
bodega2_df = pd.DataFrame(sheet.worksheet("inventario_bodega2").get_all_records())
movimientos_df = pd.DataFrame(sheet.worksheet("movimientos").get_all_records())
#pedidos_df = pd.DataFrame(sheet.worksheet("pedidos").get_all_records())
#pedidos_sheet = sheet.worksheet("pedidos")

# --- FORMATO DE FECHA ---
movimientos_df["Fecha y Hora"] = pd.to_datetime(movimientos_df["Fecha y Hora"], errors='coerce')

# --- ESTILO GLOBAL ---
st.set_page_config(page_title="Dashboard de Inventario", layout="wide")
st.markdown("""
    <style>
    .main {background-color: #f5f7fa;}
    .stButton>button {background-color: #0066cc; color: white;}
    .stSelectbox, .stTextInput {background-color: white !important;}
    </style>
""", unsafe_allow_html=True)

st.title("📦 Aplicación de Inventario General")

# --- MENU DE NAVEGACIÓN ---
pestana = st.sidebar.radio("Selecciona una sección:", ["Inventario por Bodega", "Historial de Movimientos", "Dashboard","Alertas", "Generar Pedido"])

# --- PESTAÑA 1: INVENTARIO POR BODEGA ---
if pestana == "Inventario por Bodega":
    st.subheader("📦 Inventario por Bodega")
    bodega = st.selectbox("Selecciona la bodega:", ["Bodega 1", "Bodega 2"])
    
    inventario_df = bodega1_df if bodega == "Bodega 1" else bodega2_df

    search = st.text_input("🔍 Buscar por código o nombre del producto")

    if search:
        inventario_df = inventario_df[
            inventario_df.apply(
                lambda row: search.lower() in str(row['Codigo_Barras']).lower() or
                        search.lower() in str(row['Detalle']).lower(),
                axis=1
        )
    ]

    cantidad_min = st.slider("Filtrar por cantidad mínima", 0, 100, 0)
    inventario_df = inventario_df[inventario_df['Cantidad'] >= cantidad_min]

    st.dataframe(inventario_df[['Codigo_Barras', 'Detalle', 'Cantidad']].sort_values(by='Detalle'))

# --- PESTAÑA 2: HISTORIAL DE MOVIMIENTOS ---
elif pestana == "Historial de Movimientos":
    st.subheader("📈 Historial de Movimientos")

    col1, col2 = st.columns(2)
    with col1:
        fecha_ini = st.date_input("Fecha inicio", datetime.now() - timedelta(days=30))
    with col2:
        fecha_fin = st.date_input("Fecha fin", datetime.now())

    filtro_df = movimientos_df[(movimientos_df["Fecha y Hora"] >= pd.to_datetime(fecha_ini)) & (movimientos_df["Fecha y Hora"] <= pd.to_datetime(fecha_fin))]

    tipo_mov = st.multiselect("Tipo de movimiento", options=filtro_df['Movimiento'].unique(), default=filtro_df['Movimiento'].unique())
    filtro_df = filtro_df[filtro_df['Movimiento'].isin(tipo_mov)]

    usuarios = st.multiselect("Filtrar por usuario", options=filtro_df['Usuario'].unique(), default=filtro_df['Usuario'].unique())
    filtro_df = filtro_df[filtro_df['Usuario'].isin(usuarios)]

    st.dataframe(filtro_df[['Fecha y Hora', 'Codigo_Barras', 'Movimiento', 'Cantidad', 'Bodega', 'Usuario']].sort_values(by='Fecha y Hora', ascending=False))

    graf = px.histogram(filtro_df, x="Fecha y Hora", color="Movimiento", barmode="group",
                        title="Frecuencia de movimientos por fecha")
    graf.update_layout(xaxis_title="Fecha", yaxis_title="Cantidad de movimientos")
    st.plotly_chart(graf, use_container_width=True)

# --- PESTAÑA 3: DASHBOARD ---
elif pestana == "Dashboard":
    st.subheader("📊 Dashboard de Inventario")

    total_productos_1 = bodega1_df.shape[0]
    total_productos_2 = bodega2_df.shape[0]
    total_stock_1 = bodega1_df['Cantidad'].sum()
    total_stock_2 = bodega2_df['Cantidad'].sum()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Productos en Bodega 1", total_productos_1)
    col2.metric("Productos en Bodega 2", total_productos_2)
    col3.metric("Stock Total Bodega 1", total_stock_1)
    col4.metric("Stock Total Bodega 2", total_stock_2)

    top_bodega1 = bodega1_df.sort_values(by="Cantidad", ascending=False).head(10)
    graf1 = px.bar(top_bodega1, x='Detalle', y='Cantidad', title='Top 10 productos por cantidad - Bodega 1',
                   color='Cantidad', text='Cantidad')
    graf1.update_layout(xaxis_title="Producto", yaxis_title="Cantidad")
    st.plotly_chart(graf1, use_container_width=True)

    top_bodega2 = bodega2_df.sort_values(by="Cantidad", ascending=False).head(10)
    graf2 = px.bar(top_bodega2, x='Detalle', y='Cantidad', title='Top 10 productos por cantidad - Bodega 2',
                   color='Cantidad', text='Cantidad')
    graf2.update_layout(xaxis_title="Producto", yaxis_title="Cantidad")
    st.plotly_chart(graf2, use_container_width=True)

# --- PESTAÑA 4: ALERTAS ---
elif pestana == "Alertas":
    st.subheader("🚨 Alertas de Inventario")

    umbral = st.slider("Selecciona el umbral de alerta por bajo stock", 1, 20, 5)

    criticos1 = bodega1_df[bodega1_df['Cantidad'] <= umbral]
    criticos2 = bodega2_df[bodega2_df['Cantidad'] <= umbral]

    st.write("**Productos críticos en Bodega 1:**")
    st.dataframe(criticos1[['Codigo_Barras', 'Detalle', 'Cantidad']])

    st.write("**Productos críticos en Bodega 2:**")
    st.dataframe(criticos2[['Codigo_Barras', 'Detalle', 'Cantidad']])

    dias = st.slider("Productos sin movimiento en los últimos X días", 1, 90, 30)
    fecha_limite = datetime.now() - timedelta(days=dias)
    recientes = movimientos_df[movimientos_df['Fecha y Hora'] >= fecha_limite]['Codigo_Barras'].unique()

    sin_mov1 = bodega1_df[~bodega1_df['Codigo_Barras'].isin(recientes)]
    sin_mov2 = bodega2_df[~bodega2_df['Codigo_Barras'].isin(recientes)]

    st.write("**Sin movimiento reciente - Bodega 1:**")
    st.dataframe(sin_mov1[['Codigo_Barras', 'Detalle', 'Cantidad']])

    st.write("**Sin movimiento reciente - Bodega 2:**")
    st.dataframe(sin_mov2[['Codigo_Barras', 'Detalle', 'Cantidad']])
    

#python -m streamlit run c:/Users/sacor/Downloads/Tablero_Inventario.py
