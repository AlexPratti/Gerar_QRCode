import streamlit as st
import qrcode
from io import BytesIO

st.title("Gerador de QR Code Direto")
url = st.text_input("Cole aqui a URL do seu site:", "https://")

if url:
    # Gera o QR Code
    qr = qrcode.make(url)

    # Converte para um formato que o Streamlit consegue exibir
    buf = BytesIO()
    qr.save(buf, format="PNG")
    byte_im = buf.getvalue()

    st.image(byte_im, caption="Seu QR Code para o site")

    # Botão para baixar
    st.download_button(label="Baixar QR Code", data=byte_im, file_name="qrcode.png", mime="image/png")
