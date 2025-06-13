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

# --- PESTAÑA 1: INVENTARIO POR BODEGA ---
if pestana == "Generar Pedido":
# --- Cargar datos ---
df_productos = pd.DataFrame(productos_ws.get_all_records())
df_b1 = pd.DataFrame(b1_ws.get_all_records())
df_b2 = pd.DataFrame(b2_ws.get_all_records())
df_pedidos = pd.DataFrame(pedidos_ws.get_all_records())
data = ordenes_ws.get_all_values()
df_ordenes = pd.DataFrame(data[1:], columns=[col.strip() for col in data[0]])
# Añadir columna 'Base' a df_ordenes
  
# --- Mapas para autocompletado ---
codigo_to_detalle = dict(zip(df_productos["Codigo_Barras"], df_productos["Detalle"]))
detalle_to_codigo = dict(zip(df_productos["Detalle"], df_productos["Codigo_Barras"]))

# --- Funciones ---
def extraer_base_con_tamano(detalle):
    detalle = detalle.upper()
    detalle = re.sub(r"UNIDAD.*", "", detalle)
    match = re.search(r"(\d+\s*CM|\d+\s*cm)", detalle)
    if match:
        tamano = match.group(1).upper()
        base = detalle[:match.end()].strip()
        base = re.sub(r"(MADERA|VERDE|AZUL|BEIGE|ROJO|NEGRO|DORADO|PLATA|\s+)+(?=\d+\s*CM)", "", base)
        return base
    else:
        return detalle.strip()

# --- Interfaz ---
st.set_page_config(page_title="Gestión de Pedidos", layout="wide")
tabs = st.tabs(["📥 Registrar Pedido", "📊 Seguimiento Producción"])

# =============================
# 📥 TAB 1: Registrar Pedido
# =============================
with tabs[0]:
    st.title("📦 Registro de Pedidos")
    usuario = st.text_input("👤 Usuario responsable")
    cliente = st.text_input("🏢 Cliente destino")

    st.markdown("### 🧾 Lista de productos a pedir")

    with st.form("pedido_formulario"):
        codigos, detalles, cantidades = [], [], []
        num_filas = st.number_input("Número de líneas", min_value=1, value=2, step=1)

        for i in range(num_filas):
            c1, c2, c3 = st.columns([1.5, 4, 1.2])

            # Selección del detalle
            detalle = c2.selectbox(f"📝 Detalle #{i+1}", [""] + sorted(df_productos["Detalle"].unique()), key=f"detalle_{i}")

            # Mostrar el código automáticamente
            codigo = detalle_to_codigo.get(detalle, "")
            c1.markdown(f"**🔢 Código:** `{codigo}`")

            # Cantidad
            cantidad = c3.number_input(f"📦 Cantidad #{i+1}", min_value=1, step=1, key=f"cantidad_{i}")

            # Guardar valores
            codigos.append(codigo)
            detalles.append(detalle)
            cantidades.append(cantidad)

        submit = st.form_submit_button("📥 Registrar pedido")

    if submit:
        if not usuario or not cliente:
            st.error("Debes completar el usuario y el cliente.")
        else:
            pedido_id = f"PED{datetime.now().strftime('%Y%m%d%H%M%S')}"
            ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            resumen_resultados = []
            usados_b1 = {}
            ordenes_pintura = []
            ordenes_fabricacion = []

            for codigo, detalle, cantidad in zip(codigos, detalles, cantidades):
                cant_original = cantidad
                base = extraer_base_con_tamano(detalle)

                b2_disp = df_b2.loc[df_b2["Codigo_Barras"] == codigo, "Cantidad"].sum()
                b1_opciones = df_b1[df_b1["Detalle"].apply(lambda x: extraer_base_con_tamano(x) == base)].copy()
                b1_disp = b1_opciones["Cantidad"].astype(int).sum()
                b1_disp -= usados_b1.get(base, 0)

                desde_b2 = min(cantidad, b2_disp)
                cantidad -= desde_b2
                desde_b1 = min(cantidad, b1_disp)
                cantidad -= desde_b1
                fab = cantidad
                usados_b1[base] = usados_b1.get(base, 0) + desde_b1

                acciones = []
                if desde_b2 > 0: acciones.append("Parcial B2")
                if desde_b1 > 0: acciones.append("Parcial B1")
                if fab > 0: acciones.append("Fabricar")

                resumen_resultados.append({
                    "Código": codigo, "Detalle": detalle, "Cantidad": cant_original,
                    "B2": desde_b2, "B1": desde_b1, "Fabrica": fab,
                    "Resultado": " + ".join(acciones)
                })

                pedidos_ws.append_row([pedido_id, cliente, ahora, codigo, detalle, cant_original, "Pendiente"])

                if desde_b2 > 0:
                    movs_ws.append_row([ahora, codigo, "Salida", int(desde_b2), "Bodega 2", usuario, f"Pedido {pedido_id}"])
                    fila_b2 = df_b2[df_b2["Codigo_Barras"] == codigo].index
                    if not fila_b2.empty:
                        i = fila_b2[0] + 2
                        nueva_cant = int(df_b2.iloc[fila_b2[0]]["Cantidad"]) - int(desde_b2)
                        b2_ws.update_cell(i, 4, int(nueva_cant))

                if desde_b1 > 0:
                    for idx, row in b1_opciones.iterrows():
                        if desde_b1 == 0: break
                        disp = int(row["Cantidad"])
                        usar = min(disp, desde_b1)
                        desde_b1 -= usar
                        nueva_cant = disp - usar
                        i = idx + 2
                        b1_ws.update_cell(i, 4, int(nueva_cant))
                        movs_ws.append_row([ahora, row["Codigo_Barras"], "Salida", int(usar), "Bodega 1", usuario, f"Pedido {pedido_id}"])
                        ordenes_pintura.append([ahora, row["Codigo_Barras"], detalle, usar, usuario, f"Pedido {pedido_id}"])

                if fab > 0:
                    ordenes_fabricacion.append([ahora, codigo, detalle, fab, usuario, f"Pedido {pedido_id}"])

            for orden in ordenes_pintura:
                 ordenes_ws.append_row([str(x) for x in orden] + ["Pintura", "Pendiente"])

            for orden in ordenes_fabricacion:
                ordenes_ws.append_row([str(x) for x in orden] + ["Fabricacion", "Pendiente"])


            st.success("Pedido registrado correctamente.")
            st.markdown("### 🧾 Resultado del pedido")
            st.dataframe(pd.DataFrame(resumen_resultados))

# =============================
# 📊 TAB 2: Seguimiento Producción
# =============================
# 📊 TAB 2: Seguimiento Producción
# =============================
with tabs[1]:
    st.title("📋 Seguimiento a la Producción")

    filtro_estado = st.selectbox("Filtrar por estado", ["Todos", "Pendiente", "En Proceso", "Completado"])

    def detectar_color(detalle):
        colores = ["MADERA", "VERDE", "AZUL", "BEIGE", "ROJO", "NEGRO", "DORADO", "PLATA"]
        for color in colores:
            if color in detalle.upper():
                return color
        return "SIN COLOR"

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 🎨 Órdenes de Pintura")
        # === ÓRDENES DE PINTURA ===
        df_pintura = df_ordenes[df_ordenes["Tipo"] == "Pintura"]
        if filtro_estado != "Todos":
            df_pintura = df_pintura[df_pintura["Estado"] == filtro_estado]

        df_pintura["Cantidad"] = pd.to_numeric(df_pintura["Cantidad"], errors="coerce")
        resumen_pintura = df_pintura.groupby("Detalle")["Cantidad"].sum().reset_index()
        resumen_pintura = resumen_pintura.sort_values("Cantidad", ascending=False)
        resumen_pintura.columns = ["Producto a Pintar", "Cantidad Total"]

        st.dataframe(resumen_pintura)

    with col2:
        st.markdown("### 🏭 Órdenes de Fabricación")
        # === ÓRDENES DE FABRICACIÓN ===
        df_fab = df_ordenes[df_ordenes["Tipo"] == "Fabricacion"].copy()
        if filtro_estado != "Todos":
            df_fab = df_fab[df_fab["Estado"] == filtro_estado]
        df_fab["Cantidad"] = pd.to_numeric(df_fab["Cantidad"], errors="coerce")
        resumen_fab = df_fab.groupby("Detalle")["Cantidad"].sum().reset_index()
        resumen_fab = resumen_fab.sort_values("Cantidad", ascending=False)
        resumen_fab.columns = ["Producto a Fabricar", "Cantidad Total"]
        st.dataframe(resumen_fab)


    st.markdown("### 📦 Pedidos")
    df_ped = df_pedidos.copy()
    if filtro_estado != "Todos":
        df_ped = df_ped[df_ped["Estado"] == filtro_estado]
    st.dataframe(df_ped)

    st.markdown("#### ✏️ Cambiar estado de pedido u orden")
    tipo_cambio = st.selectbox("¿Qué deseas actualizar?", ["Pedido", "Orden"])

    if tipo_cambio == "Pedido":
        pedido_sel = st.text_input("ID del pedido a actualizar")
        nuevo_estado = st.selectbox("Nuevo estado", ["Pendiente", "En Proceso", "Completado"])
        if st.button("Actualizar pedido"):
            celda = pedidos_ws.find(pedido_sel)
            if celda:
                fila = celda.row
                pedidos_ws.update_cell(fila, 7, nuevo_estado)
                st.success("Estado de pedido actualizado.")
            else:
                st.error("No se encontró ese ID de pedido.")
    else:
        orden_sel = st.text_input("Código de producto de la orden")
        nuevo_estado = st.selectbox("Nuevo estado", ["Pendiente", "En Proceso", "Completado"], key="estado_orden")
        if st.button("Actualizar orden"):
            coincidencias = ordenes_ws.findall(orden_sel)
            if coincidencias:
                for celda in coincidencias:
                    fila = celda.row
                    ordenes_ws.update_cell(fila, 8, nuevo_estado)
                st.success("Estado de orden(es) actualizado.")
            else:
                st.error("No se encontró esa orden.")


#python -m streamlit run c:/Users/sacor/Downloads/Tablero_Inventario.py
