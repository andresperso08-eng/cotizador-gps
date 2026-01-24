import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
import uuid
from fpdf import FPDF
from PIL import Image, ExifTags
import tempfile
import os
import io

# Librerías para Google Drive
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

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
# 🧠 LÓGICA INTELIGENTE DE GOOGLE DRIVE
# ==========================================

def subir_a_drive(pdf_bytes, nombre_archivo):
    """Sube el PDF a la carpeta de la semana correspondiente en Drive"""
    try:
        # 1. Autenticación (Usamos los mismos secretos que Sheets)
        # Streamlit guarda los secretos en un diccionario, lo convertimos a credenciales
        secrets_dict = dict(st.secrets["connections"]["gsheets"])
        creds = service_account.Credentials.from_service_account_info(
            secrets_dict,
            scopes=['https://www.googleapis.com/auth/drive']
        )
        service = build('drive', 'v3', credentials=creds)

        # 2. Calcular Nombre de la Carpeta Semanal (Lunes a Sábado)
        hoy = datetime.now()
        inicio_semana = hoy - timedelta(days=hoy.weekday()) # Lunes
        fin_semana = inicio_semana + timedelta(days=5)      # Sábado
        nombre_carpeta_semana = f"Semana {inicio_semana.strftime('%d-%m')} al {fin_semana.strftime('%d-%m-%Y')}"

        # 3. Obtener ID de la Carpeta Maestra (Desde secrets)
        # Si no lo pusiste en secrets, fallará aquí. Asegúrate de configurar [drive] folder_id
        try:
            parent_id = st.secrets["drive"]["folder_id"]
        except:
            st.warning("⚠️ No configuraste [drive] folder_id en secrets. Se guardará en la raíz del Drive del Robot.")
            parent_id = None 

        # 4. Buscar si la carpeta de la semana ya existe
        query = f"mimeType='application/vnd.google-apps.folder' and name='{nombre_carpeta_semana}' and trashed=false"
        if parent_id:
            query += f" and '{parent_id}' in parents"
        
        results = service.files().list(q=query, fields="files(id, name)").execute()
        items = results.get('files', [])

        if not items:
            # No existe, CREAR la carpeta
            metadata_carpeta = {
                'name': nombre_carpeta_semana,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_id] if parent_id else []
            }
            carpeta = service.files().create(body=metadata_carpeta, fields='id').execute()
            folder_id_destino = carpeta.get('id')
            st.toast(f"📁 Carpeta creada: {nombre_carpeta_semana}")
        else:
            # Ya existe, usar esa
            folder_id_destino = items[0]['id']

        # 5. Subir el Archivo PDF
        file_metadata = {
            'name': nombre_archivo,
            'parents': [folder_id_destino]
        }
        
        # Convertir bytes a un objeto leíble para la API
        media = MediaIoBaseUpload(io.BytesIO(pdf_bytes), mimetype='application/pdf')
        
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return True, file.get('id')

    except Exception as e:
        return False, str(e)

# ==========================================
# FUNCIONES DE IMAGEN Y PDF (Tus funciones originales)
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

# --- VISTAS ---

def vista_admin():
    st.title("👨‍💼 Panel Admin")
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
    
    st.divider()
    try:
        df_ver = conn.read(worksheet="Agenda_Servicios", ttl=0)
        if not df_ver.empty and "Estatus" in df_ver.columns:
            st.dataframe(df_ver[df_ver["Estatus"] == "PENDIENTE"][["Fecha_Prog", "Cliente", "Vehiculos_Desc"]])
    except: st.warning("Sin datos.")

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
        
        if st.form_submit_button("💾 Guardar y Subir a Drive", type="primary"):
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
                
                # --- SUBIDA A DRIVE ---
                nombre_archivo = f"Reporte_{unidad.replace(' ', '_')}_{id_orden}.pdf"
                with st.spinner("☁️ Subiendo evidencia a la nube..."):
                    exito, msg = subir_a_drive(pdf_bytes, nombre_archivo)
                
                if exito:
                    st.toast("✅ ¡Archivo guardado en Drive!", icon="☁️")
                    st.session_state.pdf_ultimo = pdf_bytes
                    st.session_state.nombre_pdf_ultimo = nombre_archivo
                    
                    # Guardar bitácora en Sheets
                    try:
                        try: df_h = conn.read(worksheet="Instalaciones", ttl=0)
                        except: df_h = pd.DataFrame(columns=["ID_Servicio", "Fecha", "Cliente", "Unidad", "Evidencia"])
                        
                        nuevo = pd.DataFrame([{
                            "ID_Servicio": id_orden, "Fecha": datetime.now().strftime("%d/%m/%Y"),
                            "Cliente": orden['Cliente'], "Unidad": unidad, "Evidencia": "EN DRIVE"
                        }])
                        conn.update(worksheet="Instalaciones", data=pd.concat([df_h, nuevo], ignore_index=True) if not df_h.empty else nuevo)
                        st.success(f"Unidad {unidad} registrada y respaldada.")
                    except: st.error("Se subió a Drive pero falló el registro en Excel.")
                else:
                    st.error(f"❌ Falló subida a Drive: {msg}")

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
