import streamlit as st
import pandas as pd
from fpdf import FPDF
import base64
from datetime import datetime
import matplotlib.pyplot as plt

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Cotizador GPS Profesional", page_icon="🛰️")

# --- CLASE PDF (GENERADOR DE DOCUMENTOS) ---
class PDF(FPDF):
    def header(self):
        # Logo (Intenta cargar logo.png si existe, si no, lo salta)
        try:
            # Ajusta las coordenadas o tamaño según tu logo real
            # self.image('logo.png', 10, 8, 33) 
            pass
        except:
            pass
            
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'COTIZACION DE SERVICIOS', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, 'Gracias por su preferencia - Documento generado digitalmente', 0, 0, 'C')

def create_pdf(cliente, fecha, items, total, notas, tipo_pago):
    pdf = PDF()
    pdf.add_page()
    
    # Datos del Cliente
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 10, f"Cliente: {cliente}", 0, 1)
    pdf.cell(0, 10, f"Fecha: {fecha}", 0, 1)
    pdf.ln(10)
    
    # Encabezados de Tabla
    pdf.set_fill_color(32, 56, 100) # Azul oscuro
    pdf.set_text_color(255, 255, 255) # Blanco
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(100, 10, "Descripción", 1, 0, 'C', True)
    pdf.cell(30, 10, "Cant.", 1, 0, 'C', True)
    pdf.cell(30, 10, "Unitario", 1, 0, 'C', True)
    pdf.cell(30, 10, "Total", 1, 1, 'C', True)
    
    # Filas de Productos
    pdf.set_text_color(0, 0, 0) # Negro
    pdf.set_font('Arial', '', 12)
    
    for item in items:
        # Descripción (Multicell para que no se salga si es larga)
        x_start = pdf.get_x()
        y_start = pdf.get_y()
        
        pdf.multi_cell(100, 10, item['descripcion'], 1)
        
        # Guardamos la posición Y después de la multicell
        y_end = pdf.get_y()
        altura_fila = y_end - y_start
        
        # Volvemos a subir para pintar las otras celdas al lado
        pdf.set_xy(x_start + 100, y_start) 
        
        # Ajustamos la altura de las celdas vecinas para que coincidan
        pdf.cell(30, altura_fila, str(item['cantidad']), 1, 0, 'C')
        pdf.cell(30, altura_fila, f"${item['unitario']:,.2f}", 1, 0, 'C')
        pdf.cell(30, altura_fila, f"${item['total']:,.2f}", 1, 1, 'C')

    pdf.ln(10)
    
    # Totales
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(130, 10, "", 0, 0)
    pdf.cell(30, 10, "TOTAL:", 1, 0, 'R')
    pdf.cell(30, 10, f"${total:,.2f}", 1, 1, 'C')
    
    pdf.ln(10)
    
    # Notas y Condiciones
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, "Condiciones y Notas:", 0, 1)
    pdf.set_font('Arial', '', 10)
    pdf.multi_cell(0, 6, f"Forma de Pago: {tipo_pago}\n{notas}\n\n* Garantía de 1 año en equipos por defectos de fábrica.\n* La renovación incluye plataforma y datos multicarrier.")
    
    return pdf.output(dest='S').encode('latin-1')

# --- LOGICA DE LA APLICACIÓN ---
def main():
    st.title("🛰️ Cotizador Profesional")
    st.markdown("Genera propuestas formales en segundos.")
    
    # --- BARRA LATERAL (INPUTS) ---
    st.sidebar.header("Datos de la Cotización")
    cliente = st.sidebar.text_input("Nombre del Cliente / Empresa", "Cliente Mostrador")
    fecha = datetime.now().strftime("%d/%m/%Y")
    
    st.sidebar.markdown("---")
    
    # --- SELECCIÓN DE PRODUCTO ---
    categoria = st.sidebar.radio(
        "Selecciona el Producto:",
        [
            "Rastreador GPS 4G (Estándar)", 
            "Dashcam JC261 (Video en Vivo)", 
            "Renovación Anual (Solo Servicio)" # <--- NUEVA OPCIÓN
        ]
    )
    
    cantidad = st.sidebar.number_input("Cantidad de Unidades", min_value=1, value=1)
    
    # --- LOGICA DE PRECIOS ---
    precio_unitario = 0
    descripcion_base = ""
    notas_producto = ""
    
    # 1. GPS ESTÁNDAR
    if categoria == "Rastreador GPS 4G (Estándar)":
        # Opción de Descuento Flotilla
        es_flotilla = st.sidebar.checkbox("¿Aplicar Descuento Flotilla?", value=False)
        
        if es_flotilla:
            precio_unitario = 1700
            st.success("✅ Precio Mayorista Activado ($1,700)")
        else:
            precio_unitario = 2200
        
        descripcion_base = "Dispositivo GPS 4G Cortacorriente + Instalación Oculta + Plataforma App"
        notas_producto = "Incluye instalación a domicilio."

    # 2. DASHCAM (JC261)
    elif categoria == "Dashcam JC261 (Video en Vivo)":
        precio_unitario = 9000
        mensualidad_dash = 600
        
        descripcion_base = "Sistema de Video-Telemetría JC261 (Doble Cámara + 4G). Monitoreo en Tiempo Real."
        notas_producto = f"Requiere renta mensual de datos de video: ${mensualidad_dash} MXN/unidad."
        st.info(f"📹 Nota: Este equipo conlleva una renta mensual de ${mensualidad_dash}.")

    # 3. RENOVACIÓN ANUAL (NUEVO)
    elif categoria == "Renovación Anual (Solo Servicio)":
        precio_unitario = 1800
        
        descripcion_base = "Renovación de Anualidad 2026: Servicio de Plataforma, App y Datos Multicarrier (12 Meses)."
        notas_producto = "Cobertura por 1 año completo. Sin costo de instalación (Equipo ya instalado)."
        st.info("🔄 Estás cotizando solo la renovación de servicio (Sin instalación).")

    # --- EXTRAS ---
    viaticos = st.sidebar.number_input("🚚 Extras / Viáticos (Envío)", min_value=0, value=0, step=50)
    
    # --- CÁLCULOS ---
    subtotal_equipos = precio_unitario * cantidad
    total_final = subtotal_equipos + viaticos
    
    # --- VISTA PREVIA ---
    st.markdown("### 📋 Resumen de la Propuesta")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Producto", categoria)
    col2.metric("Cantidad", f"{cantidad} unds")
    col3.metric("Total a Cobrar", f"${total_final:,.2f}")
    
    # Tabla visual
    df_preview = pd.DataFrame({
        "Concepto": [descripcion_base, "Viáticos / Traslado"],
        "Precio Unitario": [f"${precio_unitario:,.2f}", f"${viaticos:,.2f}"],
        "Total Línea": [f"${subtotal_equipos:,.2f}", f"${viaticos:,.2f}"]
    })
    st.table(df_preview)
    
    # Campo de notas extra manuales
    notas_adicionales = st.text_area("Notas Adicionales (Opcional)", value=notas_producto)

    # --- GENERAR PDF ---
    if st.button("📄 Generar PDF Formal"):
        # Construir lista de items para el PDF
        items_pdf = [
            {
                "descripcion": descripcion_base,
                "cantidad": cantidad,
                "unitario": precio_unitario,
                "total": subtotal_equipos
            }
        ]
        
        # Si hay viáticos, los agregamos como item
        if viaticos > 0:
            items_pdf.append({
                "descripcion": "Servicio a Domicilio / Viáticos",
                "cantidad": 1,
                "unitario": viaticos,
                "total": viaticos
            })
            
        pdf_bytes = create_pdf(cliente, fecha, items_pdf, total_final, notas_adicionales, "Contado / Transferencia")
        
        b64 = base64.b64encode(pdf_bytes).decode()
        href = f'<a href="data:application/octet-stream;base64,{b64}" download="Cotizacion_{cliente}.pdf">📥 Descargar PDF</a>'
        st.markdown(href, unsafe_allow_html=True)
        st.success("¡Cotización generada exitosamente!")

    # --- SECCIÓN MARKETING (GENERADOR DE IMAGEN) ---
    st.markdown("---")
    with st.expander("🎨 MARKETING: Generar Imagen Promo $2,200"):
        st.write("Genera la imagen para enviar por WhatsApp:")
        if st.button("🖼️ Crear Imagen"):
            ruta = generar_imagen_promo()
            st.image(ruta, caption="Vista Previa")
            with open(ruta, "rb") as file:
                st.download_button(
                    label="📥 Descargar Imagen PNG",
                    data=file,
                    file_name="Promo_Plan_Flexible.png",
                    mime="image/png"
                )

# --- FUNCIÓN EXTRA: GENERADOR DE IMAGEN PROMO ---
def generar_imagen_promo():
    # Configuración de colores
    fondo = "#123459"   # Azul Marino Oscuro
    amarillo = "#FFC300"
    blanco = "#FFFFFF"
    
    # Crear el lienzo
    fig, ax = plt.subplots(figsize=(6, 6)) 
    fig.patch.set_facecolor(fondo)
    ax.set_facecolor(fondo)
    ax.axis('off') 

    # 1. Título
    plt.text(0.5, 0.90, "PLAN FLEXIBLE 2026", color=amarillo, fontsize=20, ha='center', weight='bold')

    # 2. Precio Gigante
    plt.text(0.5, 0.72, "$2,200", color=blanco, fontsize=55, ha='center', weight='bold')

    # 3. Subtexto
    plt.text(0.5, 0.62, "(Pago Inicial + Instalación)", color=blanco, fontsize=10, ha='center')

    # 4. Lista de Beneficios
    items = [
        "✅ GPS 4G Cortacorriente",
        "✅ App Móvil (Android/iOS)",
        "✅ Batería de Respaldo",
        "✅ Instalación a Domicilio"
    ]
    y_pos = 0.45
    for item in items:
        plt.text(0.15, y_pos, item, color=blanco, fontsize=14, ha='left')
        y_pos -= 0.08

    # 5. Pie de página
    plt.text(0.5, 0.05, "Renta mensual del servicio: $300", color=amarillo, fontsize=10, ha='center', style='italic')

    # Guardar imagen en memoria
    ruta_img = "promo_flexible.png"
    plt.savefig(ruta_img, dpi=300, bbox_inches='tight', facecolor=fondo)
    return ruta_img

if __name__ == "__main__":
    main()
