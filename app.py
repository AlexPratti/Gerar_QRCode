import streamlit as st
import segno
import requests
import urllib.parse
from io import BytesIO

st.set_page_config(page_title="Gerador QR Oficial", page_icon="📲")

st.title("🎯 Gerador de QR Code (Link Direto)")
st.write("Esta versão corrige o erro de conexão e garante compatibilidade com seu Redmi.")

# Entrada de link
url_input = st.text_input("Cole o link aqui (ex: seusite.streamlit.app):").strip()

if url_input:
    try:
        # 1. TRATAMENTO DA URL PARA A API
        # Remove espaços e garante que a URL esteja codificada corretamente para a web
        if not url_input.startswith(("http://", "https://")):
            full_url = f"https://{url_input}"
        else:
            full_url = url_input
            
        encoded_url = urllib.parse.quote(full_url)
        
        # 2. ENCURTAMENTO VIA API (CORRIGIDO)
        api_endpoint = f"http://tinyurl.com{encoded_url}"
        response = requests.get(api_endpoint, timeout=10)
        
        if response.status_code == 200:
            short_url = response.text
            st.success(f"Link otimizado: {short_url}")

            # 3. GERAÇÃO DO QR CODE DE BAIXA DENSIDADE
            # Com o link curto, o QR Code fica com poucos pontos (Fácil para o Redmi ler)
            qr = segno.make_qr(short_url, error='l')
            
            buf = BytesIO()
            qr.save(buf, kind='png', scale=20, border=4)
            byte_im = buf.getvalue()

            # EXIBIÇÃO
            st.image(byte_im, caption="APONTE A CÂMERA E CLIQUE NO BOTÃO 'IR PARA O SITE'", width=450)

            st.download_button(
                label="📥 Baixar QR Code para Impressão",
                data=byte_im,
                file_name="qrcode_direto.png",
                mime="image/png"
            )
        else:
            st.error("Não foi possível encurtar o link. Tente novamente em instantes.")

    except Exception as e:
        st.error(f"Erro ao processar: Certifique-se de que o link é válido.")

st.divider()
st.info("💡 **Dica:** O uso do encurtador é obrigatório para o Redmi Note 11 reconhecer links longos do Streamlit como 'Acesso Direto'.")
