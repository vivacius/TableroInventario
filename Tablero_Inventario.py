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

    with st.form("form_pedido"):
        col1, col2 = st.columns(2)
        with col1:
            pedido_id = st.text_input("🔖 ID del Pedido", max_chars=20)
        with col2:
            cliente = st.text_input("👤 Nombre del Cliente")

        st.markdown("### ➕ Agregar productos al pedido")
        search_term = st.text_input("🔍 Buscar producto por código o nombre")

        if search_term:
            resultado = productos_df[
                productos_df.apply(lambda row: search_term.lower() in str(row["Codigo_Barras"]).lower() or
                                               search_term.lower() in str(row["Detalle"]).lower(), axis=1)
            ]
            st.dataframe(resultado[["Codigo_Barras", "Detalle"]])

        cod_barra = st.text_input("Código de Barras del producto a agregar")
        cantidad = st.number_input("Cantidad solicitada", min_value=1, step=1)

        agregar = st.form_submit_button("Agregar Producto")

    if "pedido_actual" not in st.session_state:
        st.session_state["pedido_actual"] = []

    if agregar:
        prod = productos_df[productos_df["Codigo_Barras"] == cod_barra]
        if not prod.empty:
            detalle = prod.iloc[0]["Detalle"]
            st.session_state["pedido_actual"].append({
                "Codigo_Barras": cod_barra,
                "Detalle": detalle,
                "Cantidad": cantidad
            })
            st.success(f"Producto {detalle} agregado al pedido.")
        else:
            st.warning("⚠️ Código de producto no encontrado.")

    # Mostrar resumen del pedido
    if st.session_state["pedido_actual"]:
        st.markdown("### 🧾 Resumen del Pedido")
        resumen_df = pd.DataFrame(st.session_state["pedido_actual"])
        st.dataframe(resumen_df)

        if st.button("Procesar Pedido"):
            orden_pintura = []
            orden_fabricacion = []
            movimientos_generados = []

            for item in st.session_state["pedido_actual"]:
                cod = item["Codigo_Barras"]
                detalle = item["Detalle"]
                cant = item["Cantidad"]

                stock_b2 = bodega2_df.loc[bodega2_df["Codigo_Barras"] == cod, "Cantidad"].sum()
                usar_b2 = min(stock_b2, cant)
                restante = cant - usar_b2

                if usar_b2 > 0:
                    movimientos_generados.append((cod, detalle, usar_b2, "Pedido desde Bodega 2"))

                if restante > 0:
                    stock_b1 = bodega1_df.loc[bodega1_df["Codigo_Barras"] == cod, "Cantidad"].sum()
                    usar_b1 = min(stock_b1, restante)
                    if usar_b1 > 0:
                        orden_pintura.append({"Codigo_Barras": cod, "Detalle": detalle, "Cantidad": usar_b1})
                        restante -= usar_b1

                    if restante > 0:
                        orden_fabricacion.append({"Codigo_Barras": cod, "Detalle": detalle, "Cantidad": restante})

            st.markdown("### 📦 Resultado del Pedido")
            if movimientos_generados:
                st.write("✅ Productos entregados desde Bodega 2:")
                st.dataframe(pd.DataFrame(movimientos_generados, columns=["Codigo_Barras", "Detalle", "Cantidad", "Movimiento"]))

            if orden_pintura:
                st.warning("🎨 Orden de Pintura Generada:")
                st.dataframe(pd.DataFrame(orden_pintura))

            if orden_fabricacion:
                st.error("🏭 Orden de Fabricación Generada:")
                st.dataframe(pd.DataFrame(orden_fabricacion))

            st.success("Pedido procesado correctamente.")
# --- GUARDAR PEDIDO EN GOOGLE SHEETS ---

def guardar_pedido_en_google_sheets(pedido_id, cliente, fuente, lista_items):
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    filas = []
    for item in lista_items:
        filas.append([
            pedido_id,
            cliente,
            ahora,
            item["Codigo_Barras"],
            item["Detalle"],
            item["Cantidad"],
            fuente
        ])
    existing_data = sheet.worksheet("pedidos").get_all_values()
    start_row = len(existing_data) + 1
    sheet.worksheet("pedidos").update(f"A{start_row}", filas)

# Guardar automáticamente el pedido (solo si hay algo que guardar)
if movimientos_generados or orden_pintura or orden_fabricacion:
    try:
        if movimientos_generados:
            guardar_pedido_en_google_sheets(pedido_id, cliente, "Bodega 2", [
                {"Codigo_Barras": cod, "Detalle": det, "Cantidad": cant}
                for cod, det, cant, _ in movimientos_generados
            ])

        if orden_pintura:
            guardar_pedido_en_google_sheets(pedido_id, cliente, "Pintura", orden_pintura)

        if orden_fabricacion:
            guardar_pedido_en_google_sheets(pedido_id, cliente, "Fabricación", orden_fabricacion)

        st.success("✅ Pedido guardado correctamente en la hoja 'pedidos'.")
    except Exception as e:
        st.error(f"❌ Error guardando el pedido: {e}")


#python -m streamlit run c:/Users/sacor/Downloads/Tablero_Inventario.py
