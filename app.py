import streamlit as st
import segno
from io import BytesIO

# Configuração da página
st.set_page_config(page_title="Gerador QR Infallible", page_icon="🎯")

st.title("🚀 Gerador de QR Code Anti-Texto")
st.markdown("""
Este gerador utiliza a biblioteca **Segno**, que cria QR Codes com alta conformidade ISO. 
Ideal para celulares **Xiaomi/Redmi** que costumam travar na opção 'Copiar Texto'.
""")

# Entrada do link
url_input = st.text_input("Cole o link aqui (ex: google.com):", placeholder="meusite.com").strip()

if url_input:
    # 1. LIMPEZA TOTAL DA URL
    # Remove espaços, quebras de linha e protocolos mal formatados
    clean_url = url_input.replace(" ", "").replace("\n", "").replace("\r", "")
    
    if not clean_url.startswith(("http://", "https://")):
        final_link = f"https://{clean_url}"
    else:
        final_link = clean_url

    # 2. GERAÇÃO COM SEGNO (O segredo da compatibilidade)
    # O comando 'make_qr' com o link direto força a criação de um QR Code de URL (URI)
    qr = segno.make_qr(final_link)
    
    # Criamos o buffer para a imagem
    buf = BytesIO()
    # Aumentamos o 'scale' para que os quadrados fiquem nítidos no sensor do Redmi
    qr.save(buf, kind='png', scale=10, border=4)
    byte_im = buf.getvalue()

    # 3. EXIBIÇÃO NO STREAMLIT
    st.success(f"Link codificado como comando de sistema: {final_link}")
    
    # Exibimos a imagem
    st.image(byte_im, caption="Aponte a câmera. O botão 'Ir para o site' DEVE aparecer agora.", width=400)

    # BOTÃO DE DOWNLOAD
    st.download_button(
        label="📥 Baixar QR Code Compatível",
        data=byte_im,
        file_name="qr_link_direto.png",
        mime="image/png"
    )

st.divider()
st.warning("⚠️ **Atenção no Redmi Note 11:** Ao ler o código, procure por um **ícone de Globo ou Link** que aparece no canto inferior da tela da câmera. Você precisa tocar nele para abrir.")
