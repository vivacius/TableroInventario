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
pedidos_ws = pd.DataFrame(sheet.worksheet("pedidos").get_all_records())


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
    
# --- PESTAÑA 5: Generar pedido ---
elif pestana == "Generar Pedido":
    st.subheader("📝 Generar Pedido")

    pedido_id = st.text_input("Identificador del pedido")
    cliente = st.text_input("Nombre del cliente")

    st.markdown("### Buscar y agregar productos")

    with st.form("form_pedido"):
        cod_o_nombre = st.text_input("Buscar por código o nombre")
        cantidad = st.number_input("Cantidad solicitada", min_value=1, step=1)
        agregar = st.form_submit_button("Agregar al pedido")

    if 'pedido_actual' not in st.session_state:
        st.session_state.pedido_actual = []

    if agregar and cod_o_nombre:
        # Buscar producto
        filtro = productos_df[
            productos_df['Codigo_Barras'].astype(str).str.contains(cod_o_nombre, case=False) |
            productos_df['Detalle'].str.contains(cod_o_nombre, case=False)
        ]
        if not filtro.empty:
            producto = filtro.iloc[0]
            st.session_state.pedido_actual.append({
                "Codigo_Barras": producto["Codigo_Barras"],
                "Detalle": producto["Detalle"],
                "Cantidad": cantidad
            })
        else:
            st.warning("Producto no encontrado.")

    # Mostrar productos del pedido actual
    if st.session_state.pedido_actual:
        st.markdown("### Productos del pedido")
        st.dataframe(pd.DataFrame(st.session_state.pedido_actual))

        if st.button("Finalizar pedido"):
            orden_pintado = []
            orden_fabricacion = []

            for item in st.session_state.pedido_actual:
                cod = item["Codigo_Barras"]
                detalle = item["Detalle"]
                cantidad_solicitada = item["Cantidad"]

                disponible_b2 = bodega2_df.loc[bodega2_df['Codigo_Barras'] == cod, 'Cantidad'].sum()
                restante = cantidad_solicitada - disponible_b2

                if restante <= 0:
                    st.success(f"{detalle}: Pedido cubierto completamente con Bodega 2.")
                    continue

                disponible_b1 = bodega1_df.loc[bodega1_df['Codigo_Barras'] == cod, 'Cantidad'].sum()

                if disponible_b1 >= restante:
                    orden_pintado.append({
                        "Codigo_Barras": cod,
                        "Detalle": detalle,
                        "Cantidad": restante
                    })
                    st.warning(f"{detalle}: Se debe pintar {restante} unidad(es).")
                else:
                    if disponible_b1 > 0:
                        orden_pintado.append({
                            "Codigo_Barras": cod,
                            "Detalle": detalle,
                            "Cantidad": disponible_b1
                        })
                        restante -= disponible_b1
                        st.warning(f"{detalle}: Se debe pintar {disponible_b1} unidad(es).")

                    orden_fabricacion.append({
                        "Codigo_Barras": cod,
                        "Detalle": detalle,
                        "Cantidad": restante
                    })
                    st.error(f"{detalle}: Se debe fabricar {restante} unidad(es).")

            # Mostrar resumen de órdenes
            if orden_pintado:
                st.markdown("### 🖌️ Orden de Pintado")
                st.dataframe(pd.DataFrame(orden_pintado))

            if orden_fabricacion:
                st.markdown("### 🏗️ Orden de Fabricación")
                st.dataframe(pd.DataFrame(orden_fabricacion))

                        pedidos_ws = sheet.worksheet("pedidos")
            fecha_pedido = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            for item in st.session_state.pedido_actual:
                cod = item["Codigo_Barras"]
                detalle = item["Detalle"]
                cantidad_solicitada = item["Cantidad"]

                disponible_b2 = bodega2_df.loc[bodega2_df['Codigo_Barras'] == cod, 'Cantidad'].sum()
                restante = cantidad_solicitada - disponible_b2

                # Si todo se puede cubrir desde Bodega 2
                if restante <= 0:
                    pedidos_sheet.append_row([
                        fecha_pedido, pedido_id, cliente, cod, detalle, cantidad_solicitada, "Bodega 2"
                    ])
                    continue

                # Si se requiere pintar
                disponible_b1 = bodega1_df.loc[bodega1_df['Codigo_Barras'] == cod, 'Cantidad'].sum()
                pintar = min(restante, disponible_b1)
                fabricar = max(restante - disponible_b1, 0)

                if disponible_b2 > 0:
                    pedidos_ws.append_row([
                        fecha_pedido, pedido_id, cliente, cod, detalle, disponible_b2, "Bodega 2"
                    ])
                if pintar > 0:
                    pedidos_ws.append_row([
                        fecha_pedido, pedido_id, cliente, cod, detalle, pintar, "Pintado"
                    ])
                if fabricar > 0:
                    pedidos_ws.append_row([
                        fecha_pedido, pedido_id, cliente, cod, detalle, fabricar, "Fabricación"
                    ])


            # Resetear sesión
            st.session_state.pedido_actual = []

#python -m streamlit run c:/Users/sacor/Downloads/Tablero_Inventario.py
