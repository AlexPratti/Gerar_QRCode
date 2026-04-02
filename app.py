import streamlit as st
import segno
import requests
from io import BytesIO

st.set_page_config(page_title="Gerador QR Infallible", page_icon="📲")

st.title("🎯 Gerador de QR Code: Link Direto")
st.write("Esta versão resolve o bloqueio de segurança do seu Redmi usando redirecionamento limpo.")

# Entrada de link
url_input = st.text_input("Cole o link do seu jogo aqui:", value="https://streamlit.app").strip()

if url_input:
    try:
        # 1. O PULO DO GATO: Encurtamento via API Silenciosa
        # Isso remove a "má reputação" do subdomínio longo no sensor da Xiaomi
        api_url = f"http://tinyurl.com{url_input}"
        response = requests.get(api_url, timeout=10)
        short_url = response.text
        
        st.success(f"Link otimizado para abertura imediata: {short_url}")

        # 2. GERAÇÃO DO QR CODE (BAIXA DENSIDADE)
        # O link curto gera poucos pontos, o que o Redmi adora ler
        qr = segno.make_qr(short_url, error='l')
        
        buf = BytesIO()
        # Scale 20 e Border 10 para nitidez máxima
        qr.save(buf, kind='png', scale=20, border=10)
        byte_im = buf.getvalue()

        # EXIBIÇÃO
        st.image(byte_im, caption="APONTE A CÂMERA E CLIQUE NO ÍCONE DE GLOBO/LINK NO CANTO", width=450)

        st.download_button(
            label="📥 Baixar QR Code Blindado",
            data=byte_im,
            file_name="qrcode_direto_final.png",
            mime="image/png"
        )

    except Exception as e:
        st.error("Erro ao processar o link. Verifique sua conexão.")

st.divider()
st.info("💡 **Por que este funciona?** A Xiaomi confia no domínio 'tinyurl.com'. Ao ler este código, o seu Redmi Note 11 mostrará o botão 'Ir para o site' instantaneamente, sem passar por páginas de propaganda.")
