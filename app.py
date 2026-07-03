import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, time

# إعدادات الصفحة الأساسية لتظهر بشكل لوحة تحكم عريضة واحترافية
st.set_page_config(page_title="نظام التداول الأوتوماتيكي المطور v3", layout="wide")
st.title("📊 لوحة الفحص الآلي الذكية (خوارزمية سيولة آسيا ولندن )")
st.subheader("تحليل تلقائي متكامل ")

# --- الشريط الجانبي لإدخل البيانات والتحكم ---
st.sidebar.header("إعدادات الفحص والتصفية")

# 1. التحقق أولاً إذا كان هناك رموز محفوظة في رابط المتصفح (URL)
if "tickers" in st.query_params:
    default_tickers = st.query_params["tickers"]
else:
    default_tickers = "SPY, QQQ, AAPL, TSLA, AMZN, MSFT, META"

# 2. صندوق إدخال الرموز (يأخذ القيمة الافتراضية أو المحفوظة)
tickers_input = st.sidebar.text_input("أدخل رموز الأسهم أو المؤشرات (افصل بفاصلة):", default_tickers)

# 3. تحديث الرابط في المتصفح تلقائياً بالرموز الحالية لتثبيتها عند التحديث
st.query_params["tickers"] = tickers_input

# 4. تنظيف الفراغات ومعالجة الرموز كقائمة
tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]
# إطار الدخول والتنفيذ اللحظي (LTF)
ltf_period = st.sidebar.selectbox("إطار الدخول والتنفيذ الحالي (LTF):", ['1h', '15m'], index=1)

# --- دالة ذكية لحساب قمم وقيعان جلسات آسيا ولندن بتوقيت نيويورك ---
def calculate_session_high_low(df_1h):
    try:
        df = df_1h.copy()
        df.index = df.index.tz_convert('America/New_York')
        
        # تصفية آخر 24 ساعة فقط لحساب الجلسات الأخيرة
        recent_df = df.tail(24)
        
        # تعريف أوقات الجلسات بتوقيت نيويورك
        asia_session = recent_df.between_time('19:00', '02:00')
        london_session = recent_df.between_time('03:00', '11:00')
        
        asia_high = asia_session['High'].max() if not asia_session.empty else None
        asia_low = asia_session['Low'].min() if not asia_session.empty else None
        
        london_high = london_session['High'].max() if not london_session.empty else None
        london_low = london_session['Low'].min() if not london_session.empty else None
        
        return asia_high, asia_low, london_high, london_low
    except:
        return None, None, None, None

# --- خوارزمية الحساب الفني المتعدد الفريمات المحدثة ---
def analyze_stock(ticker):
    try:
        stock = yf.Ticker(ticker)
        
        # 1. سحب البيانات للفريمات المختلفة مع تفعيل prepost=True لحركة خارج السوق
        df_week = stock.history(period="max", interval="1wk")   
        df_day = stock.history(period="60d", interval="1d")    
        df_ltf = stock.history(period="10d", interval=ltf_period, prepost=True) 
        df_raw_4h = stock.history(period="60d", interval="1h", prepost=True)

        if df_week.empty or df_day.empty or df_ltf.empty or df_raw_4h.empty:
            return None

        # حساب جلسات آسيا ولندن بالخلفية
        asia_high, asia_low, london_high, london_low = calculate_session_high_low(df_raw_4h)

        # 2. بناء وتجميع فريم الـ 4 ساعات (4H) بدقة وحساب المتوسط له
        df_4h = df_raw_4h.resample('4h').agg({
            'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
        }).dropna()
        
        df_4h['EMA50'] = df_4h['Close'].ewm(span=50, adjust=False).mean()
        trend_4h = "صاعد ▲" if df_4h['Close'].iloc[-1] > df_4h['EMA50'].iloc[-1] else "هابط ▼"

        # 3. حساب متوسط الـ EMA 50 للأسبوعي واليومي
        df_week['EMA50'] = df_week['Close'].ewm(span=50, adjust=False).mean()
        week_trend = "صاعد ▲" if df_week['Close'].iloc[-1] > df_week['EMA50'].iloc[-1] else "هابط ▼"
        
        df_day['EMA50'] = df_day['Close'].ewm(span=50, adjust=False).mean()
        day_trend = "صاعد ▲" if df_day['Close'].iloc[-1] > df_day['EMA50'].iloc[-1] else "هابط ▼"

        # 4. حساب شرط السيولة المطور (Liquidity Sweep) ليشمل القيعان السابقة وجلسات آسيا ولندن
        current_low = df_ltf['Low'].iloc[-1]
        current_high = df_ltf['High'].iloc[-1]
        current_close = df_ltf['Close'].iloc[-1]
        
        # تحديد أدنى قاع سابق من الفريم اللحظي لحمايتك
        recent_low_target = df_ltf['Low'].iloc[-7:-2].min()
        recent_high_target = df_ltf['High'].iloc[-7:-2].max()
        
        # دمج الأهداف: السحب يحصل لو نزلنا تحت قاع فني، أو قاع آسيا، أو قاع لندن ثم ارتد السعر فوقهم
        sweep_call = False
        sweep_put = False
        
        # فحص شروط الـ CALL (سحب سيولة قيعان)
        if current_low < recent_low_target and current_close > recent_low_target:
            sweep_call = True
        elif asia_low and current_low < asia_low and current_close > asia_low:
            sweep_call = True
        elif london_low and current_low < london_low and current_close > london_low:
            sweep_call = True
            
        # فحص شروط الـ PUT (سحب سيولة قمم)
        if current_high > recent_high_target and current_close < recent_high_target:
            sweep_put = True
        elif asia_high and current_high > asia_high and current_close < asia_high:
            sweep_put = True
        elif london_high and current_high > london_high and current_close < london_high:
            sweep_put = True

        sweep_status = "لا يوجد سحب سيولة ✗"
        if sweep_call:
            sweep_status = "تم سحب سيولة القيعان ✓"
        elif sweep_put:
            sweep_status = "تم سحب سيولة القمم ✓"

        # 5. اتخاذ القرار التلقائي بناءً على دمج السيولة الذكية المخفية
        if week_trend == "صاعد ▲" and day_trend == "صاعد ▲" and trend_4h == "صاعد ▲" and sweep_call:
            decision = "شراء قوي (CALL) 🔥"
            rr = "1 : 3.0"
        elif day_trend == "صاعد ▲" and trend_4h == "صاعد ▲" and sweep_call:
            decision = "دخول شراء (CALL) 🚀"
            rr = "1 : 2.5"
        elif day_trend == "هابط ▼" and trend_4h == "هابط ▼" and sweep_put:
            decision = "دخول بيع (PUT) 📉"
            rr = "1 : 3.0"
        else:
            decision = "انتظار الشروط ⏳"
            rr = "غير محدد"

        return {
            "الرمز/السهم": ticker, 
            "الأسبوعي (Weekly)": week_trend,
            "اليومي (Daily)": day_trend,
            "الأربع ساعات (4H)": trend_4h,
            "سحب السيولة": sweep_status, 
            "نسبة العائد (RR)": rr,
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
            elif val == "تم سحب سيولة القيعان ✓" or val == "تم سحب سيولة القمم ✓":
                styles.loc[idx, col] = 'background-color: #333333; color: #00ff00; font-weight: bold;'
            elif val == "انتظار الشروط ⏳":
                styles.loc[idx, col] = 'color: #888888;'
    return styles

# --- معالجة البيانات وعرضها المباشر في الواجهة ---
results = []
for t in tickers:
    res = analyze_stock(t)
    if res:
        results.append(res)

if results:
    df_results = pd.DataFrame(results)
    try:
        styled_df = df_results.style.apply(style_table_rows, axis=None).set_properties(**{'text-align': 'center'})
        st.dataframe(styled_df, use_container_width=True)
    except:
        st.dataframe(df_results, use_container_width=True)
else:
    st.warning("الرجاء التأكد من كتابة الرموز بشكل صحيح وجاهزية الاتصال بالإنترنت لفحص السوق.")

st.info("💡 طريقة التشغيل المضمونة: python -m streamlit run app.py")
