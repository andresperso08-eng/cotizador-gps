import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import uuid
from fpdf import FPDF
from PIL import Image, ExifTags
import tempfile
import os

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Sistema GPS LEDAC", layout="wide", page_icon="🛰️")

# --- CONEXIÓN A GOOGLE SHEETS ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"🚨 Error de conexión. Revisa tu archivo secrets.toml: {e}")
    st.stop()

# --- FUNCIONES DE IMAGEN Y PDF ---

def corregir_orientacion(image):
    """Corrige la rotación automática de fotos tomadas con celular (Samsung/iPhone)"""
    try:
        for orientation in ExifTags.TAGS.keys():
            if ExifTags.TAGS[orientation] == 'Orientation':
                break
        
        exif = image._getexif()
        if exif is not None:
            orientation = exif.get(orientation)
            if orientation == 3:
                image = image.rotate(180, expand=True)
            elif orientation == 6:
                image = image.rotate(270, expand=True)
            elif orientation == 8:
                image = image.rotate(90, expand=True)
    except:
        pass # Si falla, devolvemos la imagen tal cual
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
    
    # Datos Texto
    for key, value in datos.items():
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(50, 8, f"{key}:", 0, 0)
        pdf.set_font('Arial', '', 11)
        # Limpiar texto de caracteres raros
        texto_limpio = str(value).encode('latin-1', 'ignore').decode('latin-1')
        pdf.cell(0, 8, texto_limpio, 0, 1)
    
    pdf.ln(5)
    
    # Grid de Fotos
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, "EVIDENCIA FOTOGRÁFICA:", 0, 1)
    
    x_start = 10
    y_start = pdf.get_y()
    x, y = x_start, y_start
    
    for nombre_foto, ruta in fotos.items():
        if ruta:
            pdf.set_font('Arial', 'B', 10) 
            pdf.set_xy(x, y)
            pdf.cell(90, 5, nombre_foto, 0, 1)
            try:
                pdf.image(ruta, x=x, y=y+6, w=85, h=60)
            except: pass
            
            if x == x_start:
                x = 110 
            else:
                x = x_start
                y += 75 
                
            if y > 240:
                pdf.add_page()
                y = 20
                x = x_start

    return pdf.output(dest='S').encode('latin-1')

def procesar_imagen_subida(uploaded_file):
    """Recibe el archivo de streamlit, corrige rotación y guarda temporal"""
    if uploaded_file is not None:
        try:
            image = Image.open(uploaded_file)
            image = corregir_orientacion(image)
            image = image.convert('RGB') # Convertir a JPG compatible
            
            temp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
            image.save(temp.name, quality=70) # Calidad 70 para que no pese tanto
            return temp.name
        except Exception as e:
            st.error(f"Error procesando imagen: {e}")
            return None
    return None

# --- VISTA 1: ADMINISTRADOR ---
def vista_admin():
    st.title("👨‍💼 Panel de Control (Admin)")
    
    with st.expander("📅 Agendar Nuevo Servicio", expanded=True):
        with st.form("form_alta"):
            c1, c2 = st.columns(2)
            cliente = c1.text_input("Nombre del Cliente")
            tel = c1.text_input("Teléfono / WhatsApp")
            ubi = c2.text_input("Ubicación (Link Maps)")
            
            c3, c4 = st.columns(2)
            fecha_prog = c3.date_input("Fecha Programada")
            hora_prog = c4.time_input("Hora Programada")
            
            vehiculos_desc = st.text_area("Descripción Vehículos")
            notas = st.text_area("Notas para Técnico")
            
            if st.form_submit_button("💾 Guardar Orden"):
                try:
                    try:
                        df = conn.read(worksheet="Agenda_Servicios", ttl=0)
                    except:
                        df = pd.DataFrame(columns=["ID", "Fecha_Prog", "Hora_Prog", "Cliente", "Telefono", "Ubicacion", "Vehiculos_Desc", "Notas", "Estatus", "Cobro_Final"])

                    id_serv = str(uuid.uuid4())[:6].upper()
                    
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
                    
                    if df.empty:
                        df_final = nuevo
                    else:
                        df_final = pd.concat([df, nuevo], ignore_index=True)
                    
                    conn.update(worksheet="Agenda_Servicios", data=df_final)
                    st.success(f"✅ Servicio ID: {id_serv} agendado.")
                except Exception as e:
                    st.error(f"Error: {e}")

    st.divider()
    st.markdown("### 📋 Servicios Pendientes")
    try:
        df_ver = conn.read(worksheet="Agenda_Servicios", ttl=0)
        if not df_ver.empty and "Estatus" in df_ver.columns:
            pendientes = df_ver[df_ver["Estatus"] == "PENDIENTE"]
            if not pendientes.empty:
                st.dataframe(pendientes[["Fecha_Prog", "Hora_Prog", "Cliente", "Vehiculos_Desc"]])
            else:
                st.info("No hay pendientes.")
    except:
        st.warning("No se pudo leer la agenda.")

# --- VISTA 2: TÉCNICO ---
def vista_tecnico():
    st.title("🔧 App Técnico")
    
    # 1. Cargar Datos
    try:
        df_agenda = conn.read(worksheet="Agenda_Servicios", ttl=0)
        if "Estatus" not in df_agenda.columns:
            st.error("Falta columna 'Estatus' en Sheet.")
            return
        mis_servicios = df_agenda[df_agenda["Estatus"] == "PENDIENTE"]
    except Exception as e:
        st.error("Error de conexión.")
        return

    if mis_servicios.empty:
        st.success("🎉 No tienes trabajos pendientes.")
        return

    # 2. Selector
    lista_opciones = mis_servicios.apply(lambda x: f"{x['Cliente']} ({x['Vehiculos_Desc']})", axis=1)
    seleccion = st.selectbox("📍 Selecciona la Orden:", lista_opciones)
    
    index_serv = lista_opciones[lista_opciones == seleccion].index[0]
    orden = mis_servicios.loc[index_serv]
    id_orden = orden['ID']

    # 3. Detalles
    st.info(f"""
    **Cliente:** {orden['Cliente']} | **Tel:** {orden['Telefono']}
    **Ubicación:** {orden['Ubicacion']}
    **Notas:** {orden['Notas']}
    """)

    st.divider()

    # 4. Formulario de Instalación
    st.subheader("📸 Registro de Unidad")
    st.caption("Usa 'Tomar Foto' para usar la cámara trasera con mejor calidad.")

    with st.form("form_tecnico", clear_on_submit=True):
        nombre_unidad = st.text_input("🚙 Vehículo / Placas", placeholder="Ej: Nissan Versa - Placas SRX-99")
        
        # CAMBIO CLAVE: Usamos file_uploader para permitir cámara nativa trasera
        c1, c2 = st.columns(2)
        foto_chip = c1.file_uploader("Foto CHIP", type=['png', 'jpg', 'jpeg'], key="up_chip")
        foto_gps = c2.file_uploader("Foto GPS Instalado", type=['png', 'jpg', 'jpeg'], key="up_gps")
        
        c3, c4 = st.columns(2)
        foto_carro = c3.file_uploader("Foto AUTO (Exterior)", type=['png', 'jpg', 'jpeg'], key="up_carro")
        foto_placas = c4.file_uploader("Foto PLACAS / VIN", type=['png', 'jpg', 'jpeg'], key="up_placas")
        
        foto_tablero = st.file_uploader("Foto TABLERO (Km)", type=['png', 'jpg', 'jpeg'], key="up_tablero")
        
        btn_guardar = st.form_submit_button("💾 Guardar Unidad", type="primary", use_container_width=True)

        if btn_guardar:
            if not nombre_unidad:
                st.warning("⚠️ Escribe el nombre o placas del vehículo.")
            else:
                # Procesar imágenes
                fotos_paths = {
                    "CHIP": procesar_imagen_subida(foto_chip),
                    "GPS UBICACION": procesar_imagen_subida(foto_gps),
                    "EXTERIOR": procesar_imagen_subida(foto_carro),
                    "PLACAS/VIN": procesar_imagen_subida(foto_placas),
                    "TABLERO": procesar_imagen_subida(foto_tablero)
                }
                
                # Crear PDF
                datos_pdf = {
                    "Orden ID": id_orden,
                    "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "Cliente": orden['Cliente'],
                    "Unidad": nombre_unidad
                }
                
                pdf_bytes = generar_pdf_evidencia(datos_pdf, fotos_paths)
                
                # Guardar en Sheet "Instalaciones"
                try:
                    try:
                        df_hist = conn.read(worksheet="Instalaciones", ttl=0)
                    except:
                        df_hist = pd.DataFrame(columns=["ID_Servicio", "Fecha", "Cliente", "Unidad", "Evidencia"])
                    
                    nuevo_reg = pd.DataFrame([{
                        "ID_Servicio": id_orden,
                        "Fecha": datetime.now().strftime("%d/%m/%Y"),
                        "Cliente": orden['Cliente'],
                        "Unidad": nombre_unidad,
                        "Evidencia": "PDF Generado"
                    }])
                    
                    if df_hist.empty:
                        df_final_hist = nuevo_reg
                    else:
                        df_final_hist = pd.concat([df_hist, nuevo_reg], ignore_index=True)

                    conn.update(worksheet="Instalaciones", data=df_final_hist)
                    
                    st.success(f"✅ {nombre_unidad} registrada.")
                    
                    # Botón descarga inmediata
                    st.download_button(
                        label="📥 Descargar Reporte PDF",
                        data=pdf_bytes,
                        file_name=f"Reporte_{nombre_unidad}.pdf",
                        mime="application/pdf"
                    )
                    
                except Exception as e:
                    st.error(f"Error guardando bitácora: {e}")

    st.divider()

    # 5. Cierre
    with st.expander("💰 Finalizar Servicio Completo (Cobro)"):
        tipo_pago = st.selectbox("Método de Pago", ["Efectivo", "Transferencia", "Pendiente"])
        monto = st.number_input("Monto Cobrado", min_value=0.0)
        
        if st.button("🔒 CERRAR ORDEN"):
            try:
                df_agenda.loc[index_serv, "Estatus"] = "FINALIZADO"
                df_agenda.loc[index_serv, "Cobro_Final"] = monto
                conn.update(worksheet="Agenda_Servicios", data=df_agenda)
                st.balloons()
                st.success("Orden finalizada.")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

# --- MAIN ---
def main():
    st.sidebar.title("Navegación")
    modo = st.sidebar.radio("Perfil:", ["🔧 Técnico (Campo)", "👨‍💼 Admin (Oficina)"])
    if modo == "👨‍💼 Admin (Oficina)":
        vista_admin()
    else:
        vista_tecnico()

if __name__ == "__main__":
    main()
