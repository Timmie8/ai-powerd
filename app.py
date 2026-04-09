import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import google.generativeai as genai
import json
from datetime import datetime, timedelta

# 1. CONFIGURATIE & VEILIGHEID
# Zorg dat je in Streamlit Cloud bij 'Settings' -> 'Secrets' je sleutel toevoegt:
# GOOGLE_API_KEY = "jouw_sleutel_hier"
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY)
except Exception:
    st.error("Fout: Geen Google API Key gevonden in Streamlit Secrets.")
    st.stop()

MODEL_NAME = 'gemini-2.0-flash'
gen_model = genai.GenerativeModel(MODEL_NAME)

# 2. STREAMLIT INTERFACE
st.set_page_config(layout="wide", page_title="AI Stock Analyzer")
st.title("📈 AI-Powered Technical Stock Analysis")
st.sidebar.header("Instellingen")

tickers_input = st.sidebar.text_input("Voer tickers in (komma-gescheiden):", "AAPL, MSFT, TSLA")
tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

end_date = datetime.today()
start_date_default = end_date - timedelta(days=365)
start_date = st.sidebar.date_input("Startdatum", value=start_date_default)

st.sidebar.subheader("Indicatoren")
indicators = st.sidebar.multiselect(
    "Kies indicatoren:",
    ["20-Day SMA", "20-Day EMA", "Bollinger Bands", "VWAP"],
    default=["20-Day SMA"]
)

# 3. DATA OPHALEN
if st.sidebar.button("Gegevens ophalen"):
    with st.spinner('Beursdata ophalen...'):
        stock_data = {}
        for ticker in tickers:
            data = yf.download(ticker, start=start_date, end=end_date)
            if not data.empty:
                stock_data[ticker] = data
            else:
                st.warning(f"Geen data gevonden voor {ticker}.")
        st.session_state["stock_data"] = stock_data

# 4. ANALYSE FUNCTIE
def analyze_ticker(ticker, data):
    # Maak de grafiek
    fig = go.Figure(data=[go.Candlestick(
        x=data.index, open=data['Open'], high=data['High'],
        low=data['Low'], close=data['Close'], name="Koers"
    )])

    # Voeg indicatoren toe
    if "20-Day SMA" in indicators:
        fig.add_trace(go.Scatter(x=data.index, y=data['Close'].rolling(window=20).mean(), name='SMA 20'))
    if "20-Day EMA" in indicators:
        fig.add_trace(go.Scatter(x=data.index, y=data['Close'].ewm(span=20).mean(), name='EMA 20'))
    if "Bollinger Bands" in indicators:
        sma = data['Close'].rolling(window=20).mean()
        std = data['Close'].rolling(window=20).std()
        fig.add_trace(go.Scatter(x=data.index, y=sma + 2*std, name='BB Upper', line=dict(dash='dash')))
        fig.add_trace(go.Scatter(x=data.index, y=sma - 2*std, name='BB Lower', line=dict(dash='dash')))
    
    fig.update_layout(xaxis_rangeslider_visible=False, height=500)

    # VOORBEREIDEN VOOR GEMINI
    # We sturen de laatste 30 dagen aan data als tekst mee voor extra precisie
    recent_data = data.tail(30).to_string()
    
    prompt = (
        f"Je bent een expert in Technische Analyse. Analyseer het aandeel {ticker}.\n"
        f"Hieronder staan de meest recente koersgegevens:\n{recent_data}\n\n"
        f"Geef een uitgebreide onderbouwing van de trends en patronen die je ziet."
        f"Eindig met een aanbeveling: 'Strong Buy', 'Buy', 'Hold', 'Sell', of 'Strong Sell'."
        f"REAGEER ALTIJD IN HET VOLGENDE JSON FORMAAT:\n"
        f"{{\"action\": \"jouw_advies\", \"justification\": \"jouw_uitleg_hier\"}}"
    )

    # Aanroep naar Gemini
    try:
        response = gen_model.generate_content(prompt)
        # JSON opschonen van eventuele markdown blokken
        clean_json = response.text.replace("```json", "").replace("```", "").strip()
        result = json.loads(clean_json)
    except Exception as e:
        result = {"action": "Fout", "justification": f"AI kon geen analyse maken: {str(e)}"}

    return fig, result

# 5. RESULTATEN TONEN
if "stock_data" in st.session_state:
    tabs = st.tabs(["Overzicht"] + list(st.session_state["stock_data"].keys()))
    
    summary_list = []

    for i, ticker in enumerate(st.session_state["stock_data"]):
        data = st.session_state["stock_data"][ticker]
        with st.spinner(f"AI analyseert {ticker}..."):
            fig, result = analyze_ticker(ticker, data)
        
        summary_list.append({"Aandeel": ticker, "Advies": result.get("action")})
        
        with tabs[i+1]:
            st.plotly_chart(fig, use_container_width=True)
            st.subheader(f"AI Analyse voor {ticker}")
            st.info(result.get("justification"))

    with tabs[0]:
        st.subheader("Alle aanbevelingen")
        st.table(pd.DataFrame(summary_list))
