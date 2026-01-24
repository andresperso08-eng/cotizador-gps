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

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Sistema GPS LEDAC", layout="wide", page_icon="🛰️")

# --- CONEXIÓN ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"🚨 Error secrets.toml: {e}")
    st.stop()

# --- ESTADO ---
if 'pdf_ultimo' not in st.session_state:
    st.session_state.pdf_ultimo = None
if 'nombre_pdf_ultimo' not in st.session_state:
    st.session_state.nombre_pdf_ultimo = None

# --- HORA MÉXICO ---
def hora_mexico():
    return datetime.utcnow() - timedelta(hours=6)

# --- EMAIL ---
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

        if pdf_bytes:
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

# --- IMÁGENES ---
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

# --- PDFS ---
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
            try: pdf.image(ruta, x=x, y=y+6, w=85, h=60)
            except: pass
            if x == x_start: x = 110 
            else:
                x = x_start
                y += 75 
            if y > 240:
                pdf.add_page()
                y, x = 20, x_start
    return pdf.output(dest='S').encode('latin-1')

def generar_pdf_resumen_final(cliente, fecha, unidades_df, costo_total, metodo_pago, efectivo_recibido, comision_tecnico):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, 'RESUMEN FINAL DE ORDEN', 0, 1, 'C')
    pdf.ln(10)
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 8, f"Cliente: {str(cliente).encode('latin-1', 'ignore').decode('latin-1')}", 0, 1)
    pdf.cell(0, 8, f"Fecha: {fecha}", 0, 1)
    pdf.ln(10)
    
    # Tabla Unidades
    pdf.set_font('Arial', 'B', 12)
    pdf.set_fill_color(200, 220, 255)
    pdf.cell(10, 10, "#", 1, 0, 'C', 1)
    pdf.cell(100, 10, "UNIDAD", 1, 0, 'L', 1)
    pdf.cell(80, 10, "FECHA", 1, 1, 'C', 1)
    pdf.set_font('Arial', '', 11)
    count = 1
    for index, row in unidades_df.iterrows():
        unidad_limpia = str(row['Unidad']).encode('latin-1', 'ignore').decode('latin-1')
        pdf.cell(10, 10, str(count), 1, 0, 'C')
        pdf.cell(100, 10, f" {unidad_limpia}", 1, 0, 'L')
        pdf.cell(80, 10, str(row['Fecha']), 1, 1, 'C')
        count += 1
    pdf.ln(15)
    
    # Finanzas
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, "DETALLE FINANCIERO:", 0, 1)
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 8, f"Costo Total Cliente: ${costo_total:,.2f}", 0, 1)
    pdf.cell(0, 8, f"Metodo: {metodo_pago}", 0, 1)
    
    if metodo_pago == "Efectivo":
        pdf.set_font('Arial', 'B', 12)
        pdf.set_text_color(0, 100, 0)
        pdf.cell(0, 8, f"Efectivo Recibido: ${efectivo_recibido:,.2f}", 0, 1)
    else:
        pdf.set_font('Arial', 'I', 11)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 8, "Cobro via Transferencia/Credito", 0, 1)
    
    pdf.set_text_color(0, 0, 0)
    pdf.ln(5)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, f"Comision Tecnico Reportada: ${comision_tecnico:,.2f}", 0, 1)

    return pdf.output(dest='S').encode('latin-1')

def generar_pdf_cierre_dia(fecha_hoy, df_instalaciones, df_agenda_hoy):
    """Genera el reporte diario con la suma real de comisiones"""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 18)
    pdf.cell(0, 10, f'REPORTE DIARIO - {fecha_hoy}', 0, 1, 'C')
    pdf.ln(5)

    # 1. RESUMEN DE ACTIVIDAD
    clientes = df_instalaciones['Cliente'].unique()
    total_unidades_dia = 0

    for cliente in clientes:
        pdf.set_font('Arial', 'B', 14)
        pdf.set_fill_color(230, 230, 230)
        cli_str = str(cliente).encode('latin-1', 'ignore').decode('latin-1')
        pdf.cell(0, 10, f"Cliente: {cli_str}", 1, 1, 'L', 1)
        
        unidades = df_instalaciones[df_instalaciones['Cliente'] == cliente]
        pdf.set_font('Arial', '', 11)
        for _, row in unidades.iterrows():
            uni_str = str(row['Unidad']).encode('latin-1', 'ignore').decode('latin-1')
            pdf.cell(10, 8, "-", 0, 0)
            pdf.cell(0, 8, f"{uni_str}", 0, 1)
            total_unidades_dia += 1
        pdf.ln(3)

    pdf.ln(10)
    
    # 2. CÁLCULOS FINANCIEROS REALES
    efectivo_mano = 0.0
    total_comision_tecnico = 0.0
    
    if not df_agenda_hoy.empty:
        # Limpieza de datos numéricos
        df_agenda_hoy['Cobro_Final'] = pd.to_numeric(df_agenda_hoy['Cobro_Final'], errors='coerce').fillna(0)
        
        # Ojo: Columna nueva Pago_Tecnico
        if 'Pago_Tecnico' in df_agenda_hoy.columns:
             df_agenda_hoy['Pago_Tecnico'] = pd.to_numeric(df_agenda_hoy['Pago_Tecnico'], errors='coerce').fillna(0)
             total_comision_tecnico = df_agenda_hoy['Pago_Tecnico'].sum()
        else:
             total_comision_tecnico = 0.0

        # Efectivo solo si el tipo de pago fue Efectivo
        pagos_efectivo = df_agenda_hoy[df_agenda_hoy['Tipo_Pago'] == 'Efectivo']
        efectivo_mano = pagos_efectivo['Cobro_Final'].sum()

    # 3. TABLA DE TOTALES
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, "RESUMEN FINANCIERO DEL DÍA", 0, 1, 'C')
    pdf.ln(5)

    pdf.set_font('Arial', '', 12)
    pdf.cell(100, 10, "Total Servicios Realizados:", 1, 0)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, f"{total_unidades_dia}", 1, 1, 'C')
    
    pdf.set_font('Arial', '', 12)
    pdf.cell(100, 10, "Efectivo en manos del Técnico:", 1, 0)
    pdf.set_font('Arial', 'B', 12)
    pdf.set_text_color(0, 150, 0) # Verde
    pdf.cell(0, 10, f"${efectivo_mano:,.2f}", 1, 1, 'C')
    pdf.set_text_color(0, 0, 0)
    
    pdf.set_font('Arial', '', 12)
    pdf.cell(100, 10, "Total a Pagar al Técnico:", 1, 0)
    pdf.set_font('Arial', 'B', 12)
    pdf.set_text_color(200, 0, 0) # Rojo
    pdf.cell(0, 10, f"${total_comision_tecnico:,.2f}", 1, 1, 'C')
    pdf.set_text_color(0, 0, 0)

    pdf.ln(5)
    
    # Balance
    balance = efectivo_mano - total_comision_tecnico
    pdf.set_font('Arial', 'B', 14)
    if balance > 0:
        pdf.cell(0, 15, f"El técnico debe entregar a Oficina: ${balance:,.2f}", 0, 1, 'C')
    elif balance < 0:
        pdf.cell(0, 15, f"Oficina debe pagar al técnico: ${abs(balance):,.2f}", 0, 1, 'C')
    else:
        pdf.cell(0, 15, "Cuentas saldadas ($0.00)", 0, 1, 'C')

    return pdf.output(dest='S').encode('latin-1')

# --- VISTAS ---

def vista_admin():
    st.title("👨‍💼 Panel Admin")
    
    tab1, tab2, tab3 = st.tabs(["📅 Agendar", "🌙 Cierre del Día", "📊 Historial"])
    
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
                    except: df = pd.DataFrame(columns=["ID", "Fecha_Prog", "Hora_Prog", "Cliente", "Telefono", "Ubicacion", "Vehiculos_Desc", "Notas", "Estatus", "Cobro_Final", "Tipo_Pago", "Pago_Tecnico"])
                    
                    id_serv = str(uuid.uuid4())[:6].upper()
                    nuevo = pd.DataFrame([{
                        "ID": id_serv, "Fecha_Prog": str(fecha_prog), "Hora_Prog": str(hora_prog),
                        "Cliente": cliente, "Telefono": tel, "Ubicacion": ubi,
                        "Vehiculos_Desc": vehiculos, "Notas": notas, "Estatus": "PENDIENTE", 
                        "Cobro_Final": 0, "Tipo_Pago": "", "Pago_Tecnico": 0
                    }])
                    conn.update(worksheet="Agenda_Servicios", data=pd.concat([df, nuevo], ignore_index=True) if not df.empty else nuevo)
                    st.success(f"Servicio {id_serv} agendado.")
                except Exception as e: st.error(f"Error: {e}")

    with tab2:
        st.subheader("🌙 Generar Reporte Diario (Cierre)")
        st.info("Esto calcula cuánto efectivo trae el técnico vs cuánto le debes de sus comisiones.")
        
        if st.button("📩 GENERAR Y ENVIAR CIERRE", type="primary", use_container_width=True):
            hoy_str = hora_mexico().strftime("%d/%m/%Y")
            
            # 1. Instalaciones de HOY
            try:
                df_inst = conn.read(worksheet="Instalaciones", ttl=0)
                df_inst['Fecha_DT'] = pd.to_datetime(df_inst['Fecha'], format="%d/%m/%Y", errors='coerce')
                inst_hoy = df_inst[df_inst['Fecha_DT'].dt.date == hora_mexico().date()]
            except: inst_hoy = pd.DataFrame()

            # 2. Agenda de HOY (Finanzas)
            try:
                df_ag = conn.read(worksheet="Agenda_Servicios", ttl=0)
                # La fecha de cierre real es cuando cambió el estatus, pero usaremos fecha prog por simplicidad o ID
                # Lo mejor es filtrar las ordenes que esten FINALIZADAS y cuya instalacion haya sido hoy
                # Para simplificar, buscamos los IDs de las instalaciones de hoy en la agenda
                ids_hoy = inst_hoy['ID_Servicio'].unique()
                ag_hoy = df_ag[df_ag['ID'].isin(ids_hoy)]
                ag_hoy = ag_hoy[ag_hoy['Estatus'] == "FINALIZADO"]
            except: ag_hoy = pd.DataFrame()

            if inst_hoy.empty:
                st.warning("No se registraron instalaciones hoy.")
            else:
                pdf_cierre = generar_pdf_cierre_dia(hoy_str, inst_hoy, ag_hoy)
                
                nombre_rep = f"REPORTE_DIARIO_{hoy_str.replace('/','-')}.pdf"
                cuerpo = f"Adjunto encontrarás el reporte de operaciones del día {hoy_str}.\n\nSe incluyen las comisiones reportadas por el técnico."
                
                with st.spinner("Enviando reporte a Gerencia..."):
                    ok, msg = enviar_reporte_email(pdf_cierre, nombre_rep, f"🌙 Cierre del Día: {hoy_str}", cuerpo)
                
                if ok:
                    st.balloons()
                    st.success("✅ Reporte enviado correctamente.")
                else: st.error(f"Error enviando correo: {msg}")

    with tab3:
        try: st.dataframe(conn.read(worksheet="Instalaciones", ttl=0))
        except: st.write("Sin datos.")

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

    # --- UNIDAD INDIVIDUAL ---
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
                
                fecha_mx = hora_mexico().strftime("%d/%m/%Y %H:%M")
                fecha_corta_mx = hora_mexico().strftime("%d/%m/%Y")

                pdf_bytes = generar_pdf_evidencia({
                    "Orden": id_orden, "Fecha": fecha_mx,
                    "Cliente": orden['Cliente'], "Unidad": unidad
                }, fotos)
                
                nombre_archivo = f"Evidencia_{unidad.replace(' ', '_')}_{id_orden}.pdf"
                
                with st.spinner("📧 Enviando..."):
                    cuerpo_mail = f"Unidad: {unidad}\nCliente: {orden['Cliente']}\nFecha: {fecha_mx}"
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
                else: st.error(f"❌ Error mail: {msg}")

    if st.session_state.pdf_ultimo:
        st.download_button("📥 Descargar Copia Local", st.session_state.pdf_ultimo, st.session_state.nombre_pdf_ultimo, "application/pdf")

    st.divider()

    # --- CIERRE DE ORDEN (CON COMISIÓN DEL TÉCNICO) ---
    with st.expander("💰 Finalizar Orden (Cobro y Cierre)", expanded=True):
        st.markdown("### Datos Financieros")
        
        col_costo, col_comision = st.columns(2)
        costo_servicio = col_costo.number_input("💵 Costo Total Cliente ($)", min_value=0.0, step=50.0)
        comision_tecnico = col_comision.number_input("💰 Tu Comisión / Mano de Obra ($)", min_value=0.0, step=50.0, help="Lo que te toca a ti por este trabajo")
        
        tipo_pago = st.selectbox("Método de Pago", ["Transferencia", "Efectivo", "Pendiente/Crédito"])
        
        efectivo_recibido = 0.0
        if tipo_pago == "Efectivo":
            st.info(f"El técnico debe recolectar: ${costo_servicio:,.2f}")
            efectivo_recibido = st.number_input("Efectivo Recibido ($)", min_value=0.0, value=costo_servicio, step=50.0)
        elif tipo_pago == "Transferencia":
            st.caption("ℹ️ El técnico NO recibe dinero.")
        
        if st.button("🔒 CERRAR ORDEN Y ENVIAR RESUMEN"):
            if costo_servicio == 0 and tipo_pago != "Pendiente/Crédito":
                st.warning("⚠️ ¿El costo es $0? Verifica.")
            
            with st.spinner("Generando reporte final..."):
                try:
                    df_inst = conn.read(worksheet="Instalaciones", ttl=0)
                    unidades_orden = df_inst[df_inst['ID_Servicio'] == id_orden]
                except: unidades_orden = pd.DataFrame()

                fecha_cierre = hora_mexico().strftime("%d/%m/%Y %H:%M")
                pdf_resumen = generar_pdf_resumen_final(orden['Cliente'], fecha_cierre, unidades_orden, costo_servicio, tipo_pago, efectivo_recibido, comision_tecnico)
                
                cuerpo_resumen = f"""
                SERVICIO FINALIZADO
                Cliente: {orden['Cliente']}
                Total Unidades: {len(unidades_orden)}
                
                --- FINANZAS ---
                Costo Total Cliente: ${costo_servicio:,.2f}
                Método: {tipo_pago}
                Efectivo Recibido: ${efectivo_recibido:,.2f}
                
                --- NOMINA ---
                Comisión Técnico: ${comision_tecnico:,.2f}
                """
                enviar_reporte_email(pdf_resumen, f"RESUMEN_{orden['Cliente']}.pdf", f"🏁 FIN DE ORDEN: {orden['Cliente']}", cuerpo_resumen)

                try:
                    df_agenda_fresh = conn.read(worksheet="Agenda_Servicios", ttl=0)
                    if "Tipo_Pago" not in df_agenda_fresh.columns: df_agenda_fresh["Tipo_Pago"] = ""
                    if "Pago_Tecnico" not in df_agenda_fresh.columns: df_agenda_fresh["Pago_Tecnico"] = 0.0
                    
                    idx_final = df_agenda_fresh[df_agenda_fresh['ID'] == id_orden].index[0]
                    
                    df_agenda_fresh.at[idx_final, "Estatus"] = "FINALIZADO"
                    df_agenda_fresh.at[idx_final, "Cobro_Final"] = efectivo_recibido 
                    df_agenda_fresh.at[idx_final, "Tipo_Pago"] = tipo_pago
                    df_agenda_fresh.at[idx_final, "Pago_Tecnico"] = comision_tecnico # Guardamos la comisión
                    
                    conn.update(worksheet="Agenda_Servicios", data=df_agenda_fresh)
                    st.balloons()
                    st.success("✅ Orden Cerrada.")
                    st.session_state.pdf_ultimo = None 
                    st.rerun()
                except Exception as e: st.error(f"Error cerrando: {e}")

def main():
    st.sidebar.title("Navegación")
    if st.sidebar.radio("Perfil:", ["Técnico", "Admin"]) == "Admin": vista_admin()
    else: vista_tecnico()

if __name__ == "__main__":
    main()
