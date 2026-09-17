# A股技术面 AI 诊断师 (云端部署安全版)
import streamlit as st
import pandas as pd
import requests
import urllib3
import datetime
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="A股技术面AI诊断师", page_icon="📈", layout="centered")

# ================= 固定的本地模型列表 =================
PRESET_MODELS = {
    "DeepSeek": {"base": "https://api.deepseek.com/v1", "model": "deepseek-chat"},
    "阿里云 Qwen": {"base": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus"},
    "智谱 GLM-4": {"base": "https://open.bigmodel.cn/api/paas/v4", "model": "glm-4"},
    "月之暗面 Kimi": {"base": "https://api.moonshot.cn/v1", "model": "moonshot-v1-8k"},
    "自定义": {"base": "", "model": ""}
}

# 初始化云端会话状态 (隔离每个用户的访问)
if "config" not in st.session_state:
    st.session_state.config = {"api_key": "", "api_base": PRESET_MODELS["DeepSeek"]["base"], "model_name": PRESET_MODELS["DeepSeek"]["model"]}
if "history" not in st.session_state:
    st.session_state.history = []
if "active_record" not in st.session_state:
    st.session_state.active_record = None
if "input_symbol" not in st.session_state:
    st.session_state.input_symbol = "600519"
if "trigger_analysis" not in st.session_state:
    st.session_state.trigger_analysis = None

# ================= 侧边栏 =================
with st.sidebar:
    st.header("⚙️ API 配置 (离开网页自动清除)")
    default_key = st.session_state.config.get("api_key", "")
    default_base = st.session_state.config.get("api_base", PRESET_MODELS["DeepSeek"]["base"])
    default_model = st.session_state.config.get("model_name", PRESET_MODELS["DeepSeek"]["model"])
    
    provider_options = list(PRESET_MODELS.keys())
    default_provider_index = 0
    for i, provider in enumerate(provider_options):
        if provider != "自定义" and PRESET_MODELS[provider]["base"] == default_base:
            default_provider_index = i
            break
        elif provider == "自定义" and default_base not in [v["base"] for v in PRESET_MODELS.values() if v["base"]]:
            default_provider_index = i

    selected_provider = st.selectbox("选择大模型", provider_options, index=default_provider_index)
    
    if selected_provider == "自定义":
        api_base = st.text_input("API Base URL", value=default_base)
        model_name = st.text_input("模型名称", value=default_model)
    else:
        api_base = PRESET_MODELS[selected_provider]["base"]
        model_name = st.text_input("模型名称", value=default_model if default_model and default_provider_index != len(provider_options)-1 else PRESET_MODELS[selected_provider]["model"])

    api_key = st.text_input("API Key", type="password", value=default_key)
    
    if st.button("💾 保存当前配置", use_container_width=True):
        st.session_state.config = {"api_key": api_key, "api_base": api_base, "model_name": model_name}
        st.success("配置已保存在当前浏览器页面！")

    st.markdown("---")
    
    st.header("🕰️ 本次访问查询记录")
    if not st.session_state.history:
        st.info("暂无查询记录")
    else:
        for i, record in enumerate(reversed(st.session_state.history[-10:])):
            stock_name_disp = record.get('name', '未知')
            with st.expander(f"{record['time']} | {stock_name_disp} ({record['symbol']})"):
                st.caption(f"模型: {record.get('model', '未知')}")
                if st.button(f"🔄 在主界面查看", key=f"hist_btn_{record['time']}_{i}"):
                    st.session_state.active_record = record
                    st.session_state.input_symbol = record['symbol']
                    st.rerun()
        if st.button("🗑️ 清空记录", use_container_width=True):
            st.session_state.history = []
            st.session_state.active_record = None
            st.rerun()

# ================= 核心功能与数据获取 =================
@st.cache_data(ttl=60) 
def fetch_market_indices():
    indices = {"上证指数": "1.000001", "深证成指": "0.399001", "创业板指": "0.399006"}
    results = {}
    headers = {"User-Agent": "Mozilla/5.0"}
    proxies = {"http": None, "https": None}
    
    for name, secid in indices.items():
        url = f"http://push2his.eastmoney.com/api/qt/stock/kline/get?secid={secid}&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116&klt=101&fqt=1&end=20500101&lmt=1"
        try:
            response = requests.get(url, headers=headers, proxies=proxies, verify=False, timeout=5)
            data = response.json()
            klines = data.get("data", {}).get("klines", [])
            if klines:
                latest = klines[0].split(',')
                results[name] = {"close": float(latest[2]), "pct_chg": float(latest[8])}
        except Exception:
            results[name] = {"close": 0.0, "pct_chg": 0.0}
    return results

@st.cache_data(ttl=3600)  
def fetch_stock_data(symbol):
    try:
        if symbol in ["上证指数", "sh000001", "999999"]: secid = "1.000001"
        elif symbol in ["深证成指", "sz399001", "399001"]: secid = "0.399001"
        elif symbol in ["创业板指", "sz399006", "399006"]: secid = "0.399006"
        else: secid = f"1.{symbol}" if symbol.startswith(('6', '5')) else f"0.{symbol}"
            
        url = f"http://push2his.eastmoney.com/api/qt/stock/kline/get?secid={secid}&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116&klt=101&fqt=1&end=20500101&lmt=100"
        headers = {"User-Agent": "Mozilla/5.0"}
        proxies = {"http": None, "https": None}
        
        response = requests.get(url, headers=headers, proxies=proxies, verify=False, timeout=15)
        if response.status_code != 200: return None
            
        data = response.json()
        stock_name = data.get("data", {}).get("name", "未知名称")
        klines = data.get("data", {}).get("klines", [])
        
        if not klines: return None
            
        parsed_data = []
        for row in klines:
            fields = row.split(',')
            if len(fields) >= 11:
                parsed_data.append({"date": fields[0], "close": float(fields[2]), "high": float(fields[3]), "low": float(fields[4]), "pct_chg": float(fields[8]), "turnover": float(fields[10])})
                
        df = pd.DataFrame(parsed_data)
        df['MA5'] = df['close'].rolling(window=5).mean()
        df['MA20'] = df['close'].rolling(window=20).mean()
        df['MA60'] = df['close'].rolling(window=60).mean()
        df['High_20'] = df['high'].rolling(window=20).max()
        df['Low_20'] = df['low'].rolling(window=20).min()
        latest = df.iloc[-1]
        
        return {
            "名称": stock_name,
            "收盘": float(latest['close']),
            "涨跌幅": float(round(latest['pct_chg'], 2)) if not pd.isna(latest['pct_chg']) else 0.0,
            "换手率": float(round(latest['turnover'], 2)) if not pd.isna(latest['turnover']) else "未知",
            "MA5": float(round(latest['MA5'], 2)), "MA20": float(round(latest['MA20'], 2)), "MA60": float(round(latest['MA60'], 2)),
            "High_20": float(round(latest['High_20'], 2)), "Low_20": float(round(latest['Low_20'], 2))
        }
    except Exception as e:
        st.error(f"接口请求失败: {e}")
        return None

def generate_ai_diagnosis(data, symbol, api_key, api_base, model_name):
    ma_status = "多头排列(强势)" if (data['MA5'] > data['MA20'] > data['MA60']) else "空头排列(弱势)" if (data['MA5'] < data['MA20'] < data['MA60']) else "震荡整理"
    is_index = data['名称'] in ["上证指数", "深证成指", "创业板指"]
    title_prefix, strategy_target = ("大盘", "大盘策略") if is_index else ("个股", "个股操作")
    
    prompt = f"""
    【输入数据】标的：{data['名称']}({symbol})，最新价：{data['收盘']}，涨幅：{data['涨跌幅']}%，换手率：{data['换手率']}%
    【均线】MA5={data['MA5']:.2f}, MA20={data['MA20']:.2f}, MA60={data['MA60']:.2f} ({ma_status})
    【近20日】最高 {data['High_20']:.2f}，最低 {data['Low_20']:.2f}
    
    请以此数据输出微信群诊断快报。要求：
    1. 标题：【AI {title_prefix}技术面快评：{data['名称']}】
    2. 一句话定调多空。
    3. 分析量价配合与支撑。
    4. 给出近期支撑位与压力位。
    5. {strategy_target}建议。
    结尾附加免责声明，不用Markdown加粗，可适度用Emoji。
    """
    
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model_name, "messages": [{"role": "system", "content": "你是专业金融AI助手。"}, {"role": "user", "content": prompt}], "temperature": 0.2}
    
    try:
        response = requests.post(f"{api_base}/chat/completions", headers=headers, json=payload, timeout=30)
        if response.status_code == 200: return response.json()['choices'][0]['message']['content']
        else: return f"API请求失败: {response.status_code} - {response.text}"
    except Exception as e:
        return f"请求异常: {str(e)}"

# ================= 主界面渲染 =================
st.title("🤖 A股技术面 AI 诊断师")

with st.container():
    market_data = fetch_market_indices()
    if market_data:
        m_cols = st.columns(3)
        for col, (name, data) in zip(m_cols, market_data.items()):
            col.metric(name, f"{data['close']:.2f}", f"{data['pct_chg']}%", delta_color="inverse")
            if col.button(f"🤖 诊断{name}", key=f"btn_{name}", use_container_width=True):
                st.session_state.trigger_analysis = name
    st.markdown("---")

st.markdown("输入股票代码，或点击上方按钮一键诊断大盘。")
col1, col2 = st.columns([2, 1])
with col1:
    symbol_input = st.text_input("🔍 输入 6 位 A股代码 (或输入 '上证指数')", value=st.session_state.input_symbol, max_chars=10)
with col2:
    st.write("")
    st.write("")
    analyze_btn = st.button("🚀 生成诊断卡片", use_container_width=True)

if analyze_btn:
    st.session_state.trigger_analysis = symbol_input

if st.session_state.trigger_analysis:
    target_symbol = st.session_state.trigger_analysis
    st.session_state.trigger_analysis = None
    st.session_state.input_symbol = target_symbol
    
    if not api_key:
        st.warning("👈 请先在左侧配置 API Key！")
    elif len(target_symbol) < 4:
        st.error("请输入正确的股票或大盘代码！")
    else:
        with st.spinner(f"极速获取 {target_symbol} 行情数据..."):
            latest_data = fetch_stock_data(target_symbol)
            
        if latest_data is not None:
            with st.spinner(f"AI 正在深度推演 {latest_data['名称']} 的走势..."):
                report = generate_ai_diagnosis(latest_data, target_symbol, api_key, api_base, model_name)
            
            new_record = {"time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "symbol": target_symbol, "name": latest_data["名称"], "model": model_name, "data": latest_data, "report": report}
            st.session_state.history.append(new_record)
            st.session_state.active_record = new_record
            st.rerun()

if st.session_state.active_record:
    record = st.session_state.active_record
    r_data = record.get("data", {})
    r_name = record.get("name", r_data.get("名称", "未知股票"))
    r_symbol = record.get("symbol", "")
    r_report = record.get("report", "")
    
    st.markdown("---")
    st.subheader(f"📊 {r_name} 盘面核心数据速览")
    
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    m_col1.metric("最新价", f"{r_data.get('收盘', 0):.2f}", f"{r_data.get('涨跌幅', 0)}%", delta_color="inverse")
    turnover_val = r_data.get('换手率', '未知')
    m_col2.metric("换手率", f"{turnover_val}%" if isinstance(turnover_val, (int, float)) else turnover_val)
    m_col3.metric("MA20", f"{r_data.get('MA20', 0):.2f}")
    m_col4.metric("近20日最高", f"{r_data.get('High_20', 0):.2f}")
    
    st.info(r_report)
    st.text_area("👇 复制区域", value=r_report, height=280)