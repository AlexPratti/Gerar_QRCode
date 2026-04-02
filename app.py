import streamlit as st
import segno
from io import BytesIO

# Configuração da página
st.set_page_config(page_title="Gerador QR Turbo", page_icon="⚡")

# Inicializa o estado do campo de URL se não existir
if 'url_input' not in st.session_state:
    st.session_state.url_input = ""

# Função para limpar o campo
def limpar_campo():
    st.session_state.url_input = ""

st.title("🎯 Gerador de QR Code")
st.write("Insira o link abaixo. O sistema gerará o código de alta fidelidade.")

# Campo de entrada vinculado ao session_state
url = st.text_input("Cole a URL aqui:", key="url_input")

col1, col2 = st.columns([1, 5])

with col1:
    btn_gerar = st.button("Gerar QR")

with col2:
    if st.button("Limpar Tudo", on_click=limpar_campo):
        st.rerun()

if btn_gerar and url:
    # 1. Tratamento da URL
    url_final = url.strip()
    if not url_final.startswith(("http://", "https://")):
        url_final = f"https://{url_final}"

    try:
        # 2. Geração do QR Code (Baixa densidade para melhor leitura)
        qr = segno.make_qr(url_final, error='l')
        
        buf = BytesIO()
        # Scale 20 e Border 10 para facilitar o foco no Redmi
        qr.save(buf, kind='png', scale=20, border=10)
        byte_im = buf.getvalue()

        # 3. Exibição e Download
        st.success(f"Link processado: {url_final}")
        st.image(byte_im, caption="QR Code Gerado", width=400)

        st.download_button(
            label="📥 Baixar Imagem (PNG)",
            data=byte_im,
            file_name="qrcode_gerado.png",
            mime="image/png"
        )
        
        st.info("💡 Para gerar um novo, clique em 'Limpar Tudo' acima.")

    except Exception as e:
        st.error("Erro ao gerar o código. Verifique o link inserido.")

elif btn_gerar and not url:
    st.warning("Por favor, insira uma URL antes de gerar.")
