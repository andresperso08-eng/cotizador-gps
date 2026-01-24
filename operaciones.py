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
# 🕒 FUNCIÓN HORA MÉXICO (CORRECCIÓN DE HORA)
# ==========================================
def hora_mexico():
    """Devuelve la fecha y hora ajustada a México (UTC-6)"""
    return datetime.utcnow() - timedelta(hours=6)

# ==========================================
# 📧 FUNCIÓN DE ENVÍO POR CORREO
# ==========================================
def enviar_reporte_email(pdf_bytes, nombre_archivo, asunto, cuerpo):
    try:
        remitente = st.secrets["correo"]["usuario"]
        password = st.secrets["correo"]["password"]
        destinatario = st.secrets["correo"]["destinatario"]

        msg = MIMEMultipart()
        msg['From'] = remitente
        msg['To'] = destinatario
        msg['Subject'] = asunto

        msg.attach(MIMEText(cuerpo, 'plain'))

        # Adjuntar PDF
        adjunto = MIMEApplication(pdf_bytes, Name=nombre_archivo)
        adjunto['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
        msg.attach(adjunto)

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
        self.cell(0, 10, 'REPORTE DE EVIDENCIA', 0, 1, 'C')
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

def generar_pdf_resumen_final(cliente, fecha, unidades_df, total_cobrado, metodo_pago):
    """Genera un PDF con la lista de todas las unidades de la orden"""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, 'RESUMEN FINAL DE ORDEN DE SERVICIO', 0, 1, 'C')
    pdf.ln(10)
    
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 8, f"Cliente: {str(cliente).encode('latin-1', 'ignore').decode('latin-1')}", 0, 1)
    pdf.cell(0, 8, f"Fecha Cierre: {fecha}", 0, 1)
    pdf.ln(10)
    
    # Tabla de Unidades
    pdf.set_font('Arial', 'B', 12)
    pdf.set_fill_color(200, 220, 255)
    pdf.cell(10, 10, "#", 1, 0, 'C', 1)
    pdf.cell(100, 10, "UNIDAD / VEHICULO", 1, 0, 'L', 1)
    pdf.cell(80, 10, "FECHA REGISTRO", 1, 1, 'C', 1)
    
    pdf.set_font('Arial', '', 11)
    count = 1
    for index, row in unidades_df.iterrows():
        unidad_limpia = str(row['Unidad']).encode('latin-1', 'ignore').decode('latin-1')
        pdf.cell(10, 10, str(count), 1, 0, 'C')
        pdf.cell(100, 10, f" {unidad_limpia}", 1, 0, 'L')
        pdf.cell(80, 10, str(row['Fecha']), 1, 1, 'C')
        count += 1
        
    pdf.ln(10)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, "DETALLE DE COBRO (Técnico):", 0, 1)
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 8, f"Metodo de Pago: {metodo_pago}", 0, 1)
    
    if metodo_pago == "Efectivo":
        pdf.set_font('Arial', 'B', 14)
        pdf.cell(0, 10, f"Monto Recibido en Efectivo: ${total_cobrado:,.2f}", 0, 1)
    else:
        pdf.cell(0, 8, "Monto Recibido en Efectivo: $0.00 (Transferencia/Crédito)", 0, 1)

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

    # 2. REPORTE SEMANAL
    with tab2:
        st.subheader("Generar Resumen de Instalaciones")
        try:
            df_hist = conn.read(worksheet="Instalaciones", ttl=0)
            col_d1, col_d2 = st.columns(2)
            # Usar hora_mexico() para las fechas por defecto
            hoy_mx = hora_mexico().date()
            fecha_inicio = col_d1.date_input("Desde", value=hoy_mx - timedelta(days=7))
            fecha_fin = col_d2.date_input("Hasta", value=hoy_mx)
            
            if st.button("🔎 Generar Reporte"):
                df_hist['Fecha_DT'] = pd.to_datetime(df_hist['Fecha'], format="%d/%m/%Y", errors='coerce')
                mask = (df_hist['Fecha_DT'].dt.date >= fecha_inicio) & (df_hist['Fecha_DT'].dt.date <= fecha_fin)
                df_filtrado = df_hist.loc[mask]
                
                if not df_filtrado.empty:
                    st.success(f"Se encontraron {len(df_filtrado)} instalaciones.")
                    st.dataframe(df_filtrado[["Fecha", "Cliente", "Unidad", "Evidencia"]])
                    csv = df_filtrado.to_csv(index=False).encode('utf-8')
                    st.download_button("📥 Descargar Excel", csv, f"Resumen_{fecha_inicio}_{fecha_fin}.csv", "text/csv")
                else:
                    st.warning("No hay instalaciones en esas fechas.")
        except Exception as e:
            st.error(f"Error leyendo historial: {e}")

    # 3. BITÁCORA GLOBAL
    with tab3:
        try: st.dataframe(conn.read(worksheet="Instalaciones", ttl=0))
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

    # --- FORMULARIO DE UNIDAD INDIVIDUAL ---
    with st.form("form_tec", clear_on_submit=True):
        unidad = st.text_input("Unidad / Placas")
        c1, c2 = st.columns(2)
        f_chip = c1.file_uploader("CHIP", key="fc")
        f_gps = c2.file_uploader("GPS", key="fg")
        c3, c4 = st.columns(2)
        f_ext = c3.file_uploader("EXTERIOR", key="fe")
        f_vin = c4.file_uploader("PLACAS/VIN", key="fv")
        f_tab = st.file_uploader("TABLERO", key="ft")
        
        if st.form_submit_button("💾 Guardar y Enviar Evidencia", type="primary"):
            if not unidad: st.warning("Falta nombre unidad.")
            else:
                fotos = {
                    "CHIP": procesar_imagen_subida(f_chip),
                    "GPS": procesar_imagen_subida(f_gps),
                    "EXTERIOR": procesar_imagen_subida(f_ext),
                    "PLACAS": procesar_imagen_subida(f_vin),
                    "TABLERO": procesar_imagen_subida(f_tab)
                }
                
                # Usar hora_mexico()
                fecha_mx = hora_mexico().strftime("%d/%m/%Y %H:%M")
                fecha_corta_mx = hora_mexico().strftime("%d/%m/%Y")

                pdf_bytes = generar_pdf_evidencia({
                    "Orden": id_orden, "Fecha": fecha_mx,
                    "Cliente": orden['Cliente'], "Unidad": unidad
                }, fotos)
                
                nombre_archivo = f"Evidencia_{unidad.replace(' ', '_')}_{id_orden}.pdf"
                
                with st.spinner("📧 Enviando evidencia..."):
                    cuerpo_mail = f"Unidad instalada: {unidad}\nCliente: {orden['Cliente']}\nFecha: {fecha_mx}"
                    exito, msg = enviar_reporte_email(pdf_bytes, nombre_archivo, f"Evidencia: {unidad}", cuerpo_mail)
                
                if exito:
                    st.toast("✅ ¡Evidencia enviada!", icon="📧")
                    st.session_state.pdf_ultimo = pdf_bytes
                    st.session_state.nombre_pdf_ultimo = nombre_archivo
                    
                    try:
                        try: df_h = conn.read(worksheet="Instalaciones", ttl=0)
                        except: df_h = pd.DataFrame(columns=["ID_Servicio", "Fecha", "Cliente", "Unidad", "Evidencia"])
                        
                        nuevo = pd.DataFrame([{
                            "ID_Servicio": id_orden, "Fecha": fecha_corta_mx,
                            "Cliente": orden['Cliente'], "Unidad": unidad, "Evidencia": "ENVIADO"
                        }])
                        conn.update(worksheet="Instalaciones", data=pd.concat([df_h, nuevo], ignore_index=True) if not df_h.empty else nuevo)
                        st.success(f"Unidad {unidad} registrada.")
                    except: st.error("Error Excel.")
                else:
                    st.error(f"❌ Falló mail: {msg}")

    if st.session_state.pdf_ultimo:
        st.download_button("📥 Descargar Copia Local", st.session_state.pdf_ultimo, st.session_state.nombre_pdf_ultimo, "application/pdf")

    st.divider()

    # --- FINALIZAR ORDEN COMPLETA (RESUMEN AGRUPADO) ---
    with st.expander("💰 Finalizar Orden y Generar Reporte Final", expanded=True):
        st.markdown("### Cierre de Servicio")
        
        # 1. Selector de Pago (Lógica nueva)
        tipo_pago = st.selectbox("Método de Pago", ["Transferencia", "Efectivo", "Pendiente/Crédito"])
        
        monto = 0.0
        if tipo_pago == "Efectivo":
            monto = st.number_input("Monto Recibido en Efectivo ($)", min_value=0.0, step=50.0)
        else:
            st.info(f"Pago por {tipo_pago}. No se requiere ingresar monto.")
        
        if st.button("🔒 CERRAR ORDEN Y ENVIAR RESUMEN"):
            with st.spinner("Generando reporte final agrupado..."):
                # 1. Buscar todas las unidades de esta orden
                try:
                    df_inst = conn.read(worksheet="Instalaciones", ttl=0)
                    unidades_orden = df_inst[df_inst['ID_Servicio'] == id_orden]
                except:
                    unidades_orden = pd.DataFrame() # Vacío si falla

                # 2. Generar PDF Resumen
                fecha_cierre = hora_mexico().strftime("%d/%m/%Y %H:%M")
                pdf_resumen = generar_pdf_resumen_final(orden['Cliente'], fecha_cierre, unidades_orden, monto, tipo_pago)
                
                # 3. Enviar Correo Final
                nombre_resumen = f"RESUMEN_FINAL_{orden['Cliente'].replace(' ', '_')}.pdf"
                cuerpo_resumen = f"""
                SERVICIO FINALIZADO
                
                Cliente: {orden['Cliente']}
                Fecha Cierre: {fecha_cierre}
                Total Unidades: {len(unidades_orden)}
                
                Cobro Efectivo: ${monto:,.2f}
                Método: {tipo_pago}
                """
                enviar_reporte_email(pdf_resumen, nombre_resumen, f"🏁 FIN DE ORDEN: {orden['Cliente']}", cuerpo_resumen)

                # 4. Actualizar Agenda
                try:
                    # Recargar agenda por si cambió algo
                    df_agenda_fresh = conn.read(worksheet="Agenda_Servicios", ttl=0)
                    # Buscar el indice correcto de nuevo (seguridad)
                    idx_final = df_agenda_fresh[df_agenda_fresh['ID'] == id_orden].index[0]
                    
                    df_agenda_fresh.at[idx_final, "Estatus"] = "FINALIZADO"
                    df_agenda_fresh.at[idx_final, "Cobro_Final"] = monto
                    
                    conn.update(worksheet="Agenda_Servicios", data=df_agenda_fresh)
                    
                    st.balloons()
                    st.success("✅ Orden Cerrada. El reporte final con todas las unidades se envió a tu correo.")
                    st.session_state.pdf_ultimo = None # Limpiar
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"Error cerrando orden: {e}")

def main():
    st.sidebar.title("Navegación")
    if st.sidebar.radio("Perfil:", ["Técnico", "Admin"]) == "Admin": vista_admin()
    else: vista_tecnico()

if __name__ == "__main__":
    main()
