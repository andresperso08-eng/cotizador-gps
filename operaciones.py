import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
import uuid
from fpdf import FPDF
from PIL import Image, ExifTags
import tempfile
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import os

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Sistema GPS LEDAC", layout="wide", page_icon="🛰️")

# --- CONEXIÓN A SHEETS ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"🚨 Error secrets.toml: {e}")
    st.stop()

# --- ESTADO DE SESIÓN ---
if 'pdf_ultimo' not in st.session_state:
    st.session_state.pdf_ultimo = None
if 'nombre_pdf_ultimo' not in st.session_state:
    st.session_state.nombre_pdf_ultimo = None

# ==========================================
# 📧 FUNCIÓN DE ENVÍO POR CORREO (NUEVA)
# ==========================================
def enviar_reporte_email(pdf_bytes, nombre_archivo, cliente, unidad):
    try:
        # Cargar credenciales
        remitente = st.secrets["correo"]["usuario"]
        password = st.secrets["correo"]["password"]
        destinatario = st.secrets["correo"]["destinatario"]

        msg = MIMEMultipart()
        msg['From'] = remitente
        msg['To'] = destinatario
        msg['Subject'] = f"🛰️ Evidencia GPS: {cliente} - {unidad}"

        body = f"""
        Nuevo reporte de instalación generado.
        
        📅 Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}
        👤 Cliente: {cliente}
        🚗 Unidad: {unidad}
        
        El PDF con la evidencia fotográfica se adjunta a este correo.
        """
        msg.attach(MIMEText(body, 'plain'))

        # Adjuntar PDF
        adjunto = MIMEApplication(pdf_bytes, Name=nombre_archivo)
        adjunto['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
        msg.attach(adjunto)

        # Enviar
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(remitente, password)
        server.send_message(msg)
        server.quit()
        return True, "Enviado"
    except Exception as e:
        return False, str(e)

# ==========================================
# FUNCIONES DE IMAGEN Y PDF
# ==========================================
def corregir_orientacion(image):
    try:
        for orientation in ExifTags.TAGS.keys():
            if ExifTags.TAGS[orientation] == 'Orientation':
                break
        exif = image._getexif()
        if exif is not None:
            orientation = exif.get(orientation)
            if orientation == 3: image = image.rotate(180, expand=True)
            elif orientation == 6: image = image.rotate(270, expand=True)
            elif orientation == 8: image = image.rotate(90, expand=True)
    except: pass 
    return image

class PDFReporte(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'REPORTE DE INSTALACIÓN - EVIDENCIA', 0, 1, 'C')
        self.ln(5)

def generar_pdf_evidencia(datos, fotos):
    pdf = PDFReporte()
    pdf.add_page()
    pdf.set_font('Arial', '', 11)
    
    for key, value in datos.items():
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(50, 8, f"{key}:", 0, 0)
        pdf.set_font('Arial', '', 11)
        texto_limpio = str(value).encode('latin-1', 'ignore').decode('latin-1')
        pdf.cell(0, 8, texto_limpio, 0, 1)
    
    pdf.ln(5)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, "EVIDENCIA FOTOGRÁFICA:", 0, 1)
    
    x_start, y_start = 10, pdf.get_y()
    x, y = x_start, y_start
    
    for nombre_foto, ruta in fotos.items():
        if ruta:
            pdf.set_font('Arial', 'B', 10) 
            pdf.set_xy(x, y)
            pdf.cell(90, 5, nombre_foto, 0, 1)
            try:
                pdf.image(ruta, x=x, y=y+6, w=85, h=60)
            except: pass
            
            if x == x_start: x = 110 
            else:
                x = x_start
                y += 75 
            if y > 240:
                pdf.add_page()
                y, x = 20, x_start
    return pdf.output(dest='S').encode('latin-1')

def procesar_imagen_subida(uploaded_file):
    if uploaded_file:
        try:
            image = Image.open(uploaded_file)
            image = corregir_orientacion(image)
            image = image.convert('RGB')
            temp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
            image.save(temp.name, quality=70) 
            return temp.name
        except: return None
    return None

# ==========================================
# VISTAS
# ==========================================

def vista_admin():
    st.title("👨‍💼 Panel Admin")
    
    # --- PESTAÑAS PARA ORGANIZAR ---
    tab1, tab2, tab3 = st.tabs(["📅 Agendar", "📊 Reporte Semanal", "📋 Bitácora Completa"])
    
    # 1. AGENDAR
    with tab1:
        with st.form("form_alta"):
            c1, c2 = st.columns(2)
            cliente = c1.text_input("Cliente")
            tel = c1.text_input("Teléfono")
            ubi = c2.text_input("Ubicación")
            c3, c4 = st.columns(2)
            fecha_prog = c3.date_input("Fecha")
            hora_prog = c4.time_input("Hora")
            vehiculos = st.text_area("Vehículos")
            notas = st.text_area("Notas")
            
            if st.form_submit_button("💾 Guardar Orden"):
                try:
                    try: df = conn.read(worksheet="Agenda_Servicios", ttl=0)
                    except: df = pd.DataFrame(columns=["ID", "Fecha_Prog", "Hora_Prog", "Cliente", "Telefono", "Ubicacion", "Vehiculos_Desc", "Notas", "Estatus", "Cobro_Final"])
                    
                    id_serv = str(uuid.uuid4())[:6].upper()
                    nuevo = pd.DataFrame([{
                        "ID": id_serv, "Fecha_Prog": str(fecha_prog), "Hora_Prog": str(hora_prog),
                        "Cliente": cliente, "Telefono": tel, "Ubicacion": ubi,
                        "Vehiculos_Desc": vehiculos, "Notas": notas, "Estatus": "PENDIENTE", "Cobro_Final": 0
                    }])
                    conn.update(worksheet="Agenda_Servicios", data=pd.concat([df, nuevo], ignore_index=True) if not df.empty else nuevo)
                    st.success(f"Servicio {id_serv} agendado.")
                except Exception as e: st.error(f"Error: {e}")

    # 2. REPORTE SEMANAL (LO QUE PEDISTE)
    with tab2:
        st.subheader("Generar Resumen de Instalaciones")
        try:
            df_hist = conn.read(worksheet="Instalaciones", ttl=0)
            
            # Filtros de Fecha
            col_d1, col_d2 = st.columns(2)
            fecha_inicio = col_d1.date_input("Desde", value=datetime.now() - timedelta(days=7))
            fecha_fin = col_d2.date_input("Hasta", value=datetime.now())
            
            if st.button("🔎 Generar Reporte"):
                # Convertir columna Fecha a datetime para filtrar
                df_hist['Fecha_DT'] = pd.to_datetime(df_hist['Fecha'], format="%d/%m/%Y", errors='coerce')
                
                # Filtrar
                mask = (df_hist['Fecha_DT'].dt.date >= fecha_inicio) & (df_hist['Fecha_DT'].dt.date <= fecha_fin)
                df_filtrado = df_hist.loc[mask]
                
                if not df_filtrado.empty:
                    st.success(f"Se encontraron {len(df_filtrado)} instalaciones.")
                    st.dataframe(df_filtrado[["Fecha", "Cliente", "Unidad", "Evidencia"]])
                    
                    # Generar CSV para descargar
                    csv = df_filtrado.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        "📥 Descargar Resumen Semanal (Excel/CSV)",
                        csv,
                        f"Resumen_Semanal_{fecha_inicio}_{fecha_fin}.csv",
                        "text/csv"
                    )
                else:
                    st.warning("No hay instalaciones en esas fechas.")
        except Exception as e:
            st.error(f"Error leyendo historial: {e}")

    # 3. BITÁCORA GLOBAL
    with tab3:
        try:
            st.dataframe(conn.read(worksheet="Instalaciones", ttl=0))
        except: st.write("Sin datos aún.")

def vista_tecnico():
    st.title("🔧 Técnico")
    try:
        df_agenda = conn.read(worksheet="Agenda_Servicios", ttl=0)
        mis_servicios = df_agenda[df_agenda["Estatus"] == "PENDIENTE"]
    except:
        st.error("Error conexión.")
        return

    if mis_servicios.empty:
        st.success("No hay pendientes.")
        return

    lista = mis_servicios.apply(lambda x: f"{x['Cliente']} ({x['Vehiculos_Desc']})", axis=1)
    sel = st.selectbox("Orden:", lista)
    orden = mis_servicios.loc[lista[lista == sel].index[0]]
    id_orden = orden['ID']

    st.info(f"Cliente: {orden['Cliente']} | Notas: {orden['Notas']}")

    with st.form("form_tec", clear_on_submit=True):
        unidad = st.text_input("Unidad / Placas")
        c1, c2 = st.columns(2)
        f_chip = c1.file_uploader("CHIP", key="fc")
        f_gps = c2.file_uploader("GPS", key="fg")
        c3, c4 = st.columns(2)
        f_ext = c3.file_uploader("EXTERIOR", key="fe")
        f_vin = c4.file_uploader("PLACAS/VIN", key="fv")
        f_tab = st.file_uploader("TABLERO", key="ft")
        
        if st.form_submit_button("💾 Guardar y Enviar", type="primary"):
            if not unidad: st.warning("Falta nombre unidad.")
            else:
                fotos = {
                    "CHIP": procesar_imagen_subida(f_chip),
                    "GPS": procesar_imagen_subida(f_gps),
                    "EXTERIOR": procesar_imagen_subida(f_ext),
                    "PLACAS": procesar_imagen_subida(f_vin),
                    "TABLERO": procesar_imagen_subida(f_tab)
                }
                
                pdf_bytes = generar_pdf_evidencia({
                    "Orden": id_orden, "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "Cliente": orden['Cliente'], "Unidad": unidad
                }, fotos)
                
                # --- ENVÍO POR EMAIL (REEMPLAZA DRIVE) ---
                nombre_archivo = f"Reporte_{unidad.replace(' ', '_')}_{id_orden}.pdf"
                
                with st.spinner("📧 Enviando respaldo por correo..."):
                    exito, msg = enviar_reporte_email(pdf_bytes, nombre_archivo, orden['Cliente'], unidad)
                
                if exito:
                    st.toast("✅ ¡Evidencia enviada al correo!", icon="📧")
                    st.session_state.pdf_ultimo = pdf_bytes
                    st.session_state.nombre_pdf_ultimo = nombre_archivo
                    
                    # Guardar bitácora en Sheets
                    try:
                        try: df_h = conn.read(worksheet="Instalaciones", ttl=0)
                        except: df_h = pd.DataFrame(columns=["ID_Servicio", "Fecha", "Cliente", "Unidad", "Evidencia"])
                        
                        nuevo = pd.DataFrame([{
                            "ID_Servicio": id_orden, "Fecha": datetime.now().strftime("%d/%m/%Y"),
                            "Cliente": orden['Cliente'], "Unidad": unidad, "Evidencia": "ENVIADO CORREO"
                        }])
                        conn.update(worksheet="Instalaciones", data=pd.concat([df_h, nuevo], ignore_index=True) if not df_h.empty else nuevo)
                        st.success(f"Unidad {unidad} registrada.")
                    except: st.error("Error actualizando Excel.")
                else:
                    st.error(f"❌ Falló el envío de correo: {msg}. Revisa tu contraseña de aplicación.")

    if st.session_state.pdf_ultimo:
        st.download_button("📥 Descargar Copia Local", st.session_state.pdf_ultimo, st.session_state.nombre_pdf_ultimo, "application/pdf")

    with st.expander("Finalizar Orden"):
        if st.button("Cerrar Orden"):
            df_agenda.loc[lista[lista == sel].index[0], "Estatus"] = "FINALIZADO"
            conn.update(worksheet="Agenda_Servicios", data=df_agenda)
            st.rerun()

def main():
    st.sidebar.title("Navegación")
    if st.sidebar.radio("Perfil:", ["Técnico", "Admin"]) == "Admin": vista_admin()
    else: vista_tecnico()

if __name__ == "__main__":
    main()
