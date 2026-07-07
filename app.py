import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, time
import time as time_sleep # أداة برمجية لإجبار السيرفر على الانتظار

# 1. إعدادات الصفحة الأساسية
st.set_page_config(page_title="نظام التداول الأوتوماتيكي المطور v3.3", layout="wide")
st.title("📊 لوحة الفحص الآلي الذكية (خوارزمية السيولة + الفلتر الثلاثي السريع)")
st.subheader("تحليل سريع ومتكامل مصمم خصيصاً لاقتناص فرص الأوبشن اللحظية")

# --- الشريط الجانبي لإدخال البيانات والتحكم ---
st.sidebar.header("إعدادات الفحص والتصفية")

if "tickers" in st.query_params:
    default_tickers = st.query_params["tickers"]
else:
    default_tickers = "SPY, QQQ, AAPL, TSLA, AMZN, MSFT, META, BTC-USD"

tickers_input = st.sidebar.text_input("أدخل رموز الأسهم أو المؤشرات (افصل بفاصلة):", default_tickers)
st.query_params["tickers"] = tickers_input
tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

ltf_period = st.sidebar.selectbox("إطار الدخول والتنفيذ الحالي (LTF):", ['1h', '15m'], index=1)

# --- دالة حساب قمم وقيعان جلسات آسيا ولندن ---
def calculate_session_high_low(df_1h):
    try:
        df = df_1h.copy()
        df.index = df.index.tz_convert('America/New_York')
        recent_df = df.tail(24)
        
        asia_session = recent_df.between_time('19:00', '02:00')
        london_session = recent_df.between_time('03:00', '11:00')
        
        asia_high = asia_session['High'].max() if not asia_session.empty else None
        asia_low = asia_session['Low'].min() if not asia_session.empty else None
        
        london_high = london_session['High'].max() if not london_session.empty else None
        london_low = london_session['Low'].min() if not london_session.empty else None
        
        return asia_high, asia_low, london_high, london_low
    except:
        return None, None, None, None

# --- خوارزمية الحساب الفني السريعة ---
def analyze_stock(ticker):
    try:
        stock = yf.Ticker(ticker)
        
        df_week = stock.history(period="max", interval="1wk")   
        df_day = stock.history(period="60d", interval="1d")    
        df_ltf = stock.history(period="10d", interval=ltf_period, prepost=True) 
        df_raw_1h = stock.history(period="60d", interval="1h", prepost=True)

        if df_week.empty or df_day.empty or df_ltf.empty or df_raw_1h.empty:
            return None

        asia_high, asia_low, london_high, london_low = calculate_session_high_low(df_raw_1h)

        df_4h = df_raw_1h.resample('4h').agg({
            'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
        }).dropna()
        df_4h['SMA50'] = df_4h['Close'].rolling(window=50).mean()
        trend_4h = "صاعد ▲" if df_4h['Close'].iloc[-1] > df_4h['SMA50'].iloc[-1] else "هابط ▼"

        df_week['SMA10'] = df_week['Close'].rolling(window=10).mean()
        week_trend = "صاعد ▲" if df_week['Close'].iloc[-1] > df_week['SMA10'].iloc[-1] else "هابط ▼"
        
        df_day['SMA20'] = df_day['Close'].rolling(window=20).mean()
        day_trend = "صاعد ▲" if df_day['Close'].iloc[-1] > df_day['SMA20'].iloc[-1] else "هابط ▼"

        current_low = df_ltf['Low'].iloc[-1]
        current_high = df_ltf['High'].iloc[-1]
        current_close = df_ltf['Close'].iloc[-1]
        
        recent_low_target = df_ltf['Low'].iloc[-7:-2].min()
        recent_high_target = df_ltf['High'].iloc[-7:-2].max()
        
        sweep_call = False
        sweep_put = False
        
        if current_low < recent_low_target and current_close > recent_low_target:
            sweep_call = True
        elif asia_low and current_low < asia_low and current_close > asia_low:
            sweep_call = True
        elif london_low and current_low < london_low and current_close > london_low:
            sweep_call = True
            
        if current_high > recent_high_target and current_close < recent_high_target:
            sweep_put = True
        elif asia_high and current_high > asia_high and current_close < asia_high:
            sweep_put = True
        elif london_high and current_high > london_high and current_close < london_high:
            sweep_put = True

        sweep_status = "لا يوجد ✗"
        if sweep_call:
            sweep_status = "سحب قيعان ✓"
        elif sweep_put:
            sweep_status = "سحب قمم ✓"

        if week_trend == "صاعد ▲" and day_trend == "صاعد ▲" and trend_4h == "صاعد ▲" and sweep_call:
            decision = "شراء قوي (CALL) 🔥"
            rr = "1 : 3.0"
        elif day_trend == "صاعد ▲" and trend_4h == "صاعد ▲" and sweep_call:
            decision = "دخول شراء (CALL) 🚀"
            rr = "1 : 2.0"
        elif week_trend == "هابط ▼" and day_trend == "هابط ▼" and trend_4h == "هابط ▼" and sweep_put:
            decision = "دخول بيع (PUT) 📉"
            rr = "1 : 3.0"
        else:
            decision = "انتظار الشروط ⏳"
            rr = "غير محدد"

        return {
            "الرمز": ticker, 
            "الأسبوعي (SMA 10)": week_trend,
            "اليومي (SMA 20)": day_trend,
            "اللحظي (4H - SMA 50)": trend_4h,
            "سحب السيولة": sweep_status, 
            "العائد (RR)": rr,
            "القرار النهائي": decision
        }
    except Exception as e:
        return None

# --- دالة التلوين المخصصة للصفوف ---
def style_table_rows(df):
    styles = pd.DataFrame('', index=df.index, columns=df.columns)
    for col in df.columns:
        for idx in df.index:
            val = df.loc[idx, col]
            if val == "صاعد ▲":
                styles.loc[idx, col] = 'background-color: #1e4620; color: white;'
            elif val == "هابط ▼":
                styles.loc[idx, col] = 'background-color: #5c1d1d; color: white;'
            elif val == "شراء قوي (CALL) 🔥":
                styles.loc[idx, col] = 'background-color: #0d47a1; color: white; font-weight: bold;'
            elif val == "دخول شراء (CALL) 🚀":
                styles.loc[idx, col] = 'background-color: #1565c0; color: white;'
            elif val == "دخول بيع (PUT) 📉":
                styles.loc[idx, col] = 'background-color: #b71c1c; color: white; font-weight: bold;'
            elif val == "سحب قيعان ✓" or val == "سحب قمم ✓":
                styles.loc[idx, col] = 'background-color: #333333; color: #00ff00; font-weight: bold;'
            elif val == "انتظار الشروط ⏳":
                styles.loc[idx, col] = 'color: #888888;'
    return styles

# --- معالجة البيانات وعرضها ---
results = []
for t in tickers:
    res = analyze_stock(t)
    if res:
        results.append(res)

if results:
    df_results = pd.DataFrame(results)
    try:
        styled_df = df_results.style.apply(style_table_rows, axis=None).set_properties(**{'text-align': 'center'})
        st.dataframe(styled_df, width="stretch")
    except:
        st.dataframe(df_results, width="stretch")
else:
    st.warning("الرجاء التأكد من كتابة الرموز بشكل صحيح وجاهزية الاتصال بالإنترنت لفحص السوق.")

# --- آلية التحديث الإجبارية والمضمونة من داخل السيرفر ---
st.write(f"⏱️ آخر تحديث آلي تم في: {datetime.now().strftime('%H:%M:%S')}")
time_sleep.sleep(120) # انتظر 120 ثانية (دقيقتين)
st.rerun() # أعد تشغيل السيرفر إجبارياً
