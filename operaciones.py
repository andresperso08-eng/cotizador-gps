import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import uuid
from fpdf import FPDF
from PIL import Image
import tempfile
import os

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Sistema de Operaciones GPS", layout="wide", page_icon="🛠️")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- CLASE PDF PARA EVIDENCIA ---
class PDFReporte(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'REPORTE DE INSTALACIÓN - EVIDENCIA', 0, 1, 'C')
        self.ln(5)

def generar_pdf_evidencia(datos, fotos):
    pdf = PDFReporte()
    pdf.add_page()
    pdf.set_font('Arial', '', 11)
    
    # Datos Texto
    for key, value in datos.items():
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(50, 8, f"{key}:", 0, 0)
        pdf.set_font('Arial', '', 11)
        pdf.cell(0, 8, str(value), 0, 1)
    
    pdf.ln(5)
    
    # Grid de Fotos
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, "EVIDENCIA FOTOGRÁFICA:", 0, 1)
    
    x_start = 10
    y_start = pdf.get_y()
    x, y = x_start, y_start
    
    for nombre_foto, ruta in fotos.items():
        if ruta:
            pdf.set_font('Arial', 'B', 10) # Nombre de la foto en negrita
            pdf.set_xy(x, y)
            pdf.cell(90, 5, nombre_foto, 0, 1)
            try:
                # Ajustamos la imagen
                pdf.image(ruta, x=x, y=y+6, w=85, h=60)
            except: pass
            
            # Mover cursor (Lógica de 2 columnas)
            if x == x_start:
                x = 110 
            else:
                x = x_start
                y += 75 # Bajar a siguiente fila
                
            if y > 240: # Si se acaba la hoja
                pdf.add_page()
                y = 20
                x = x_start

    return pdf.output(dest='S').encode('latin-1')

# --- VISTA 1: ADMINISTRADOR (TÚ) ---
def vista_admin():
    st.title("👨‍💼 Panel de Control (Admin)")
    st.markdown("### 📅 Cargar Nuevo Servicio")
    
    with st.form("form_alta"):
        c1, c2 = st.columns(2)
        cliente = c1.text_input("Nombre del Cliente")
        tel = c1.text_input("Teléfono / WhatsApp")
        ubi = c1.text_input("Ubicación (Link de Google Maps)")
        
        c3, c4 = st.columns(2)
        fecha_prog = c3.date_input("Fecha Programada")
        hora_prog = c4.time_input("Hora Programada")
        
        vehiculos_desc = st.text_area("Descripción de Vehículos", placeholder="Ej: 3 Unidades (1 Versa Rojo, 1 NP300 Blanca, 1 Moto)")
        notas = st.text_area("Notas para el Técnico", placeholder="Ej: Cobrar $200 de viáticos extra. Preguntar por Sr. Juan.")
        
        if st.form_submit_button("💾 Guardar y Asignar"):
            try:
                # Leemos la hoja (si no existe, Pandas creará un DF vacío)
                try:
                    df = conn.read(worksheet="Agenda_Servicios", ttl=0)
                except:
                    df = pd.DataFrame(columns=["ID", "Fecha_Prog", "Hora_Prog", "Cliente", "Telefono", "Ubicacion", "Vehiculos_Desc", "Notas", "Estatus", "Cobro_Final"])

                id_serv = str(uuid.uuid4())[:6].upper() # ID Corto
                
                nuevo = pd.DataFrame([{
                    "ID": id_serv,
                    "Fecha_Prog": str(fecha_prog),
                    "Hora_Prog": str(hora_prog),
                    "Cliente": cliente,
                    "Telefono": tel,
                    "Ubicacion": ubi,
                    "Vehiculos_Desc": vehiculos_desc,
                    "Notas": notas,
                    "Estatus": "PENDIENTE",
                    "Cobro_Final": 0
                }])
                
                df_new = pd.concat([df, nuevo], ignore_index=True)
                conn.update(worksheet="Agenda_Servicios", data=df_new)
                st.success(f"✅ Servicio agendado con ID: {id_serv}")
            except Exception as e:
                st.error(f"Error al conectar con Google Sheets: {e}")

    st.divider()
    st.markdown("### 📋 Tablero de Pendientes")
    try:
        df_ver = conn.read(worksheet="Agenda_Servicios", ttl=0)
        pendientes = df_ver[df_ver["Estatus"] == "PENDIENTE"]
        if not pendientes.empty:
            st.dataframe(pendientes[["Fecha_Prog", "Hora_Prog", "Cliente", "Vehiculos_Desc", "Ubicacion"]])
        else:
            st.info("No hay servicios pendientes.")
    except:
        pass

# --- VISTA 2: TÉCNICO (CAMPO) ---
def vista_tecnico():
    st.title("🔧 App Técnico")
    st.markdown("Selecciona un servicio para trabajar:")

    # 1. Cargar Agenda
    try:
        df_agenda = conn.read(worksheet="Agenda_Servicios", ttl=0)
        mis_servicios = df_agenda[df_agenda["Estatus"] == "PENDIENTE"]
    except:
        st.error("Error conectando a la base de datos.")
        return

    if mis_servicios.empty:
        st.success("🎉 Todo limpio. No hay servicios pendientes.")
        return

    # 2. Selector Inteligente
    lista_opciones = mis_servicios.apply(lambda x: f"{x['Fecha_Prog']} {x['Hora_Prog']} - {x['Cliente']}", axis=1)
    seleccion = st.selectbox("📍 Órdenes de Trabajo:", lista_opciones)
    
    # Recuperar datos del servicio seleccionado
    index_serv = lista_opciones[lista_opciones == seleccion].index[0]
    orden = mis_servicios.loc[index_serv]
    id_orden = orden['ID']

    # 3. Mostrar Detalles
    with st.container():
        st.info(f"""
        **👤 Cliente:** {orden['Cliente']}
        **📞 Tel:** {orden['Telefono']}
        **📍 Ubicación:** {orden['Ubicacion']}
        **🚗 Vehículos:** {orden['Vehiculos_Desc']}
        **📝 Notas:** {orden['Notas']}
        """)

    st.divider()

    # 4. Módulo de Instalación (Bucle)
    st.subheader(f"🛠️ Instalación - Orden #{id_orden}")
    st.caption("Llena este formulario por CADA vehículo. Al guardar, se limpiará para el siguiente.")

    with st.form("form_tecnico", clear_on_submit=True):
        nombre_unidad = st.text_input("🚙 Nombre / Placas de la Unidad", placeholder="Ej: Nissan Versa 2024 - Placas SRX-99")
        
        st.write("📸 **Evidencia Fotográfica**")
        c1, c2 = st.columns(2)
        foto_chip = c1.camera_input("Foto del CHIP", key="f_chip")
        foto_gps = c2.camera_input("Foto del GPS", key="f_gps")
        
        c3, c4 = st.columns(2)
        foto_carro = c3.camera_input("Foto del CARRO (Exterior)", key="f_carro")
        foto_placas = c4.camera_input("Foto de las PLACAS", key="f_placas")
        
        foto_tablero = st.camera_input("Foto del TABLERO (Km/Gas)", key="f_tablero")
        
        btn_guardar_unidad = st.form_submit_button("💾 Guardar Unidad y Generar PDF")

        if btn_guardar_unidad:
            if not nombre_unidad:
                st.warning("⚠️ Falta el nombre de la unidad.")
            else:
                # Procesar fotos
                fotos = {"CHIP": None, "GPS": None, "CARRO": None, "PLACAS": None, "TABLERO": None}
                
                def guardar_temp(upload_file):
                    if upload_file:
                        temp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
                        img = Image.open(upload_file)
                        img.save(temp.name)
                        return temp.name
                    return None

                fotos["CHIP"] = guardar_temp(foto_chip)
                fotos["GPS"] = guardar_temp(foto_gps)
                fotos["CARRO"] = guardar_temp(foto_carro)
                fotos["PLACAS"] = guardar_temp(foto_placas)
                fotos["TABLERO"] = guardar_temp(foto_tablero)

                # Generar PDF
                datos_pdf = {
                    "Orden ID": id_orden,
                    "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "Técnico": "En Sitio",
                    "Cliente": orden['Cliente'],
                    "Unidad": nombre_unidad
                }
                
                pdf_bytes = generar_pdf_evidencia(datos_pdf, fotos)
                
                # Guardar en Sheet "Instalaciones" (Bitácora Histórica)
                try:
                    df_hist = conn.read(worksheet="Instalaciones", ttl=0)
                except:
                    df_hist = pd.DataFrame()
                
                nuevo_reg = pd.DataFrame([{
                    "ID_Servicio": id_orden,
                    "Fecha": datetime.now().strftime("%d/%m/%Y"),
                    "Cliente": orden['Cliente'],
                    "Unidad": nombre_unidad,
                    "Evidencia": "PDF Generado"
                }])
                conn.update(worksheet="Instalaciones", data=pd.concat([df_hist, nuevo_reg], ignore_index=True))
                
                st.success(f"✅ Unidad '{nombre_unidad}' guardada correctamente.")
                st.download_button("📥 Descargar PDF Evidencia", pdf_bytes, f"Evidencia_{nombre_unidad}.pdf", "application/pdf")

    st.divider()

    # 5. Cierre de Orden (Cobranza)
    st.markdown("### 💰 Finalizar Servicio")
    with st.expander("Clic aquí cuando acabes TODOS los carros", expanded=False):
        st.write("Solo llena esto si ya terminaste todo el trabajo con este cliente.")
        
        tipo_pago = st.selectbox("Forma de Pago", ["Efectivo", "Transferencia", "Pendiente / Crédito"])
        monto_cobrado = st.number_input("Monto Recibido ($)", min_value=0.0, step=50.0)
        
        if st.button("🔒 CERRAR ORDEN DEFINITIVAMENTE"):
            try:
                # Actualizar estatus a FINALIZADO
                df_agenda.loc[index_serv, "Estatus"] = "FINALIZADO"
                df_agenda.loc[index_serv, "Cobro_Final"] = monto_cobrado
                conn.update(worksheet="Agenda_Servicios", data=df_agenda)
                
                st.balloons()
                st.success("Orden Cerrada. ¡Buen trabajo!")
                st.rerun()
            except Exception as e:
                st.error(f"Error al cerrar: {e}")

# --- MENU PRINCIPAL (SIDEBAR) ---
def main():
    st.sidebar.title("Navegación")
    modo = st.sidebar.radio("Ir a:", ["🔧 Técnico (App Móvil)", "👨‍💼 Administrador (Oficina)"])

    if modo == "👨‍💼 Administrador (Oficina)":
        vista_admin()
    else:
        vista_tecnico()

if __name__ == "__main__":
    main()
