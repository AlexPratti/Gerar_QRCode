import streamlit as st
import qrcode
from io import BytesIO

# Configuração da página
st.set_page_config(page_title="Gerador QR Link Direto", page_icon="🌐")

st.title("🔗 Gerador de QR Code para Redmi/Xiaomi")
st.write("Este código força o celular a reconhecer o link como uma ação de abrir navegador.")

# Entrada do usuário
url_input = st.text_input("Digite o site (ex: google.com):").strip()

if url_input:
    # 1. TRATAMENTO DE STRING (O SEGREDO PARA XIAOMI)
    # Remove protocolos existentes para reconstruir do zero e evitar erro de sintaxe
    clean_url = url_input.replace("https://", "").replace("http://", "").strip()
    
    # Montamos a URL garantindo que NÃO hajam espaços ou caracteres invisíveis
    # O protocolo https:// é OBRIGATÓRIO para o Android não achar que é texto
    final_link = f"https://{clean_url}"

    # 2. CONFIGURAÇÃO DO QR CODE
    # Aumentamos o Box Size e usamos Error Correction 'H' (High) 
    # Isso torna o código mais "robusto" para o sensor da câmera do Redmi
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=15,
        border=4,
    )
    
    qr.add_data(final_link)
    qr.make(fit=True)

    # Criar a imagem em alta definição
    img = qr.make_image(fill_color="black", back_color="white")

    # 3. PREPARAÇÃO PARA O STREAMLIT
    buf = BytesIO()
    img.save(buf, format="PNG")
    byte_im = buf.getvalue()

    # EXIBIÇÃO
    st.success(f"Link Gerado: {final_link}")
    st.image(byte_im, caption="Aponte a câmera do seu Redmi", width=400)

    # BOTÃO DE DOWNLOAD
    st.download_button(
        label="📥 Baixar QR Code para Celular",
        data=byte_im,
        file_name="qrcode_direto.png",
        mime="image/png"
    )

st.divider()
st.warning("⚠️ **Nota para usuários Redmi Note 11:** Ao apontar a câmera, um pequeno ícone de 'globo' ou 'link' aparecerá no canto inferior direito da tela da câmera. Você **PRECISA TOCAR NESSE ÍCONE** para abrir o site. Se você apenas esperar, o sistema mostrará a opção de copiar texto por padrão.")
