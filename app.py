import streamlit as st
from fpdf import FPDF
from datetime import datetime, timedelta
import re
import os

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Cotizador GPS", page_icon="🛰️", layout="centered")

# --- ESTILOS VISUALES ---
COLOR_PRIMARIO = (18, 52, 89)      # Azul Marino
COLOR_SECUNDARIO = (255, 195, 0)   # Amarillo
COLOR_GRIS_CLARO = (245, 245, 245)

# --- TU CATÁLOGO MAESTRO ---
CATALOGO = {
    1: {"nombre": "GPS RASTREADOR 4G PRO\n   + Instalación Oculta y Profesional\n   + Bloqueo de Motor a Distancia\n   + Batería de Respaldo Interna\n   + Conectividad Híbrida 4G-2G", "precio": 2200, "alias": "GPS"},
    2: {"nombre": "PLAN MENSUAL DE SERVICIO\n   + Plataforma Web y App (Android/iOS)\n   + Ubicación en Tiempo Real (30s)\n   + Historial de Rutas (3 Meses)\n   + Alertas de Seguridad", "precio": 300, "alias": "SvcMes"},
    3: {"nombre": "PLAN ANUAL (¡PROMOCIÓN: PAGA 6 Y RECIBE 12!)\n   + 12 Meses de Servicio Premium\n   + Plataforma Web y App (Android/iOS)\n   + Ubicación en Tiempo Real (30s)\n   + Historial de Rutas (3 Meses)", "precio": 1800, "alias": "Anual"},
    4: {"nombre": "DASHCAM DUAL JC400\n   + Cámara Frontal + Interior\n   + Transmisión en Vivo", "precio": 9000, "alias": "DashDual"},
    5: {"nombre": "Renta Mensual Dashcam", "precio": 600, "alias": "SvcDash"},
    6: {"nombre": "DASHCAM FULL HUB 5 CANALES\n   + Soporta 5 cámaras + IA\n   + Grabación Disco Duro", "precio": 9600, "alias": "DashFull"},
    7: {"nombre": "Cámara Extra (Lateral/Trasera)", "precio": 1800, "alias": "CamExtra"},
    8: {"nombre": "Renta Mensual Dashcam Full", "precio": 600, "alias": "MensDash"},
    9: {"nombre": "Sensor de Combustible (Varilla)\n   + Detección de Ordeña\n   + Litros Exactos", "precio": 7000, "alias": "Sensor"},
    10: {"nombre": "GPS Magnético (Portátil)\n   + Cero Instalación\n   + Inc. 1 año servicio", "precio": 5500, "alias": "GPSMag"}
}

# --- CLASE PDF ---
class PDF(FPDF):
    def header(self):
        # 1. LOGO (Capa inferior)
        if os.path.exists("logo.png"):
            self.image("logo.png", 10, 8, 33)
        
        # 2. FRANJA AZUL DE FONDO
        self.set_fill_color(*COLOR_PRIMARIO)
        self.rect(0, 0, 210, 42, 'F')
        
        # Volver a poner el logo (Capa superior)
        if os.path.exists("logo.png"):
            self.image("logo.png", 10, 5, 30)

        # 3. TÍTULO
        # Usamos w=0 para que ocupe todo el ancho hasta el margen derecho
        self.set_font('Arial', 'B', 20)
        self.set_text_color(255, 255, 255)
        self.set_xy(0, 8)
        self.cell(0, 10, 'COTIZACIÓN', 0, 1, 'R')
        
        # Subtítulo
        self.set_font('Arial', '', 9)
        self.set_xy(0, 16)
        self.cell(0, 4, 'Soluciones Tecnológicas en Rastreo', 0, 1, 'R')

        # 4. DIRECCIÓN ALINEADA
        self.set_font('Arial', '', 7)
        self.set_text_color(230, 230, 230)
        
        # Línea 1
        self.set_xy(0, 23)
        self.cell(0, 3, 'Benito Juarez 1818, Local 3', 0, 1, 'R')
        
        # Línea 2
        self.set_xy(0, 27)
        self.cell(0, 3, 'Col. Sin nombre, Guadalupe N.L, CP. 67188', 0, 1, 'R')
        
        # Línea 3 (Teléfono en negrita)
        self.set_xy(0, 31)
        self.set_font('Arial', 'B', 8)
        self.cell(0, 3, 'Tel. 811-075-4372', 0, 1, 'R')
        
        self.ln(15)

    def footer(self):
        self.set_y(-35)
        self.set_font('Arial', '', 7)
        self.set_text_color(100, 100, 100)
        self.set_draw_color(200, 200, 200)
        self.line(10, 260, 200, 260)
        terminos = "VIGENCIA: 15 días. GARANTÍA: 1 año. PAGOS: 50% anticipo. INSTALACIÓN: Incluida en zona metropolitana."
        self.multi_cell(0, 4, terminos, 0, 'C')
        self.set_y(-15)
        self.cell(0, 10, f'Pág {self.page_no()}/{{nb}}', 0, 0, 'C')

def generar_pdf(cliente, folio, carrito, lleva_iva):
    pdf = PDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    
    hoy = datetime.now()
    fecha_emision = hoy.strftime("%d/%m/%Y")
    fecha_vence = (hoy + timedelta(days=15)).strftime("%d/%m/%Y")
    
    # DATOS CLIENTE
    pdf.set_y(50)
    pdf.set_font('Arial', 'B', 10)
    pdf.set_text_color(*COLOR_PRIMARIO)
    pdf.cell(100, 6, "DATOS DEL CLIENTE:", 0, 1)
    pdf.set_font('Arial', '', 10)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(100, 6, cliente.upper(), 0, 0)

    pdf.set_xy(140, 50)
    pdf.set_font('Arial', 'B', 10)
    pdf.set_text_color(*COLOR_PRIMARIO)
    pdf.cell(60, 6, f"FOLIO: #{folio}", 0, 1, 'R')
    pdf.set_xy(140, 56)
    pdf.set_text_color(0,0,0)
    pdf.set_font('Arial', '', 10)
    pdf.cell(60, 6, f"Fecha: {fecha_emision}", 0, 1, 'R')
    pdf.set_xy(140, 62)
    pdf.set_text_color(200, 0, 0)
    pdf.cell(60, 6, f"Vence: {fecha_vence}", 0, 1, 'R')
    
    pdf.set_y(80)
    
    # TABLA
    pdf.set_fill_color(*COLOR_PRIMARIO)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Arial', 'B', 9)
    pdf.cell(15, 8, 'CANT.', 0, 0, 'C', 1)
    pdf.cell(120, 8, 'DESCRIPCIÓN', 0, 0, 'L', 1)
    pdf.cell(30, 8, 'P. UNIT.', 0, 0, 'R', 1)
    pdf.cell(30, 8, 'IMPORTE', 0, 1, 'R', 1)

    pdf.set_text_color(0, 0, 0)
    pdf.set_font('Arial', '', 8)
    
    gran_total = 0
    fill = False
    
    for item in carrito:
        lineas = item['desc'].count('\n') + 1
        h = max(lineas * 5, 10)
        
        if fill: pdf.set_fill_color(245, 245, 245)
        else: pdf.set_fill_color(255, 255, 255)
        
        pdf.cell(15, h, str(item['cant']), 0, 0, 'C', 1)
        
        x, y = pdf.get_x(), pdf.get_y()
        pdf.multi_cell(120, 5, item['desc'], 0, 'L', 1)
        pdf.set_xy(x + 120, y)
        
        # PRECIOS
        x_precio = pdf.get_x()
        pdf.rect(x_precio, y, 30, h, 'F')
        
        if item.get('original') and item['original'] > item['unitario']:
            pdf.set_font('Arial', '', 7)
            pdf.set_text_color(150, 150, 150)
            pdf.set_xy(x_precio, y+2)
            pdf.cell(30, 4, f"${item['original']:,.2f}", 0, 0, 'R')
            
            ancho = pdf.get_string_width(f"${item['original']:,.2f}")
            pdf.set_draw_color(150, 50, 50)
            pdf.line(x_precio+30-1-ancho, y+4, x_precio+29, y+4)
            
            pdf.set_xy(x_precio, y+6)
            pdf.set_font('Arial', 'B', 8)
            pdf.set_text_color(0,0,0)
            pdf.cell(30, 4, f"${item['unitario']:,.2f}", 0, 0, 'R')
            pdf.set_xy(x_precio+30, y)
        else:
            pdf.set_text_color(0,0,0)
            pdf.cell(30, h, f"${item['unitario']:,.2f}", 0, 0, 'R')

        pdf.cell(30, h, f"${item['total']:,.2f}", 0, 1, 'R', 1)
        gran_total += item['total']
        fill = not fill

    # TOTALES
    pdf.set_draw_color(*COLOR_PRIMARIO)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)
    
    iva = gran_total * 0.16 if lleva_iva else 0
    total = gran_total + iva
    
    x_start = 130
    if lleva_iva:
        pdf.set_x(x_start)
        pdf.cell(35, 6, "SUBTOTAL:", 0, 0, 'R')
        pdf.cell(30, 6, f"${gran_total:,.2f}", 0, 1, 'R')
        pdf.set_x(x_start)
        pdf.cell(35, 6, "IVA (16%):", 0, 0, 'R')
        pdf.cell(30, 6, f"${iva:,.2f}", 0, 1, 'R')

    pdf.ln(2)
    pdf.set_x(x_start)
    pdf.set_fill_color(*COLOR_SECUNDARIO)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(35, 10, "TOTAL NETO:", 1, 0, 'R', 1)
    pdf.cell(30, 10, f"${total:,.2f}", 1, 1, 'R', 1)

    return pdf.output(dest='S').encode('latin-1')

# --- INTERFAZ WEB ---
def main():
    if os.path.exists("logo.png"):
        st.image("logo.png", width=150)
    else:
        st.warning("⚠️ No encuentro 'logo.png'. Sube el archivo a GitHub.")
        st.caption(f"Archivos encontrados: {os.listdir('.')}")

    st.title("Cotizador GPS 🛰️")
    st.markdown("Genera cotizaciones profesionales en segundos.")

    # 1. CLIENTE
    st.markdown("### 👤 Datos del Cliente")
    col1, col2 = st.columns([3, 1])
    with col1:
        cliente = st.text_input("Nombre / Empresa")
    with col2:
        folio = st.number_input("Folio", value=100)

    # 2. EL CONFIGURADOR DE GPS
    st.markdown("### 🛰️ GPS + Planes")
    with st.container():
        st.info("Configurador Rápido de Flotillas")
        col_cant, col_plan = st.columns(2)
        
        with col_cant:
            cant_gps = st.number_input("Cantidad de GPS", min_value=0, value=0)
            desc_flotilla = st.toggle("¿Aplicar Descuento Flotilla?", value=False)
            if desc_flotilla:
                st.caption("✅ Precio baja a $1,700")
            else:
                st.caption("Precio normal: $2,200")
        
        with col_plan:
            tipo_plan = st.radio("Plan de Servicio", ["Anual ($1,800)", "Mensual ($300)"])

    # 3. OTROS PRODUCTOS
    with st.expander("📷 Dashcams, Sensores y Accesorios"):
        carrito_extra = []
        for k, v in CATALOGO.items():
            if k in [1, 2, 3]: continue
            titulo = v['nombre'].split('\n')[0]
            c = st.number_input(f"{titulo} (${v['precio']})", min_value=0, key=k)
            if c > 0:
                carrito_extra.append({"cant": c, "item": v})

    # 4. EXTRAS
    st.markdown("### 🚚 Extras")
    costo_envio = st.number_input("Costo Viáticos / Domicilio ($)", min_value=0.0, step=50.0)
    lleva_iva = st.checkbox("¿Agregar 16% IVA al final?")

    # --- BOTÓN MÁGICO ---
    if st.button("📄 GENERAR PDF AHORA", type="primary", use_container_width=True):
        carrito = []
        
        if cant_gps > 0:
            precio_gps = 1700 if desc_flotilla else 2200
            orig_gps = 2200 if desc_flotilla else None
            nom_gps = CATALOGO[1]['nombre']
            if desc_flotilla: nom_gps += "\n   >> PRECIO ESPECIAL FLOTILLAS (Desc. Aplicado)"
            
            carrito.append({"cant": cant_gps, "desc": nom_gps, "unitario": precio_gps, "total": precio_gps*cant_gps, "original": orig_gps})
            
            id_plan = 3 if "Anual" in tipo_plan else 2
            prod_plan = CATALOGO[id_plan]
            carrito.append({"cant": cant_gps, "desc": prod_plan['nombre'], "unitario": prod_plan['precio'], "total": prod_plan['precio']*cant_gps, "original": None})

        for extra in carrito_extra:
            carrito.append({"cant": extra['cant'], "desc": extra['item']['nombre'], "unitario": extra['item']['precio'], "total": extra['item']['precio']*extra['cant'], "original": None})

        if costo_envio > 0:
            carrito.append({"cant": 1, "desc": "SERVICIO A DOMICILIO / VIÁTICOS", "unitario": costo_envio, "total": costo_envio, "original": None})

        if not carrito:
            st.error("⚠️ El carrito está vacío.")
        elif not cliente:
            st.warning("⚠️ Escribe el nombre del cliente.")
        else:
            pdf_bytes = generar_pdf(cliente, folio, carrito, lleva_iva)
            nombre_clean = re.sub(r'[^a-zA-Z0-9]', '', cliente.split()[0])
            nombre_archivo = f"Cotizacion-{nombre_clean}-{folio}.pdf"
            
            st.success("✅ ¡Cotización Creada!")
            st.download_button(
                label="📥 DESCARGAR PDF",
                data=pdf_bytes,
                file_name=nombre_archivo,
                mime="application/pdf",
                type="primary",
                use_container_width=True
            )

if __name__ == "__main__":
    main()
