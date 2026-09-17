# A股技术面 AI 诊断师 (云端部署安全版)
import streamlit as st
import pandas as pd
import requests
import datetime

st.set_page_config(page_title="A股技术面AI诊断师", page_icon="📈", layout="centered")

# ================= 模型服务商（模型名称将通过 /models 联网更新） =================
PRESET_MODELS = {
    "DeepSeek": {"base": "https://api.deepseek.com/v1", "model": "deepseek-chat"},
    "阿里云 Qwen": {"base": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus"},
    "智谱 GLM-4": {"base": "https://open.bigmodel.cn/api/paas/v4", "model": "glm-4"},
    "月之暗面 Kimi": {"base": "https://api.moonshot.cn/v1", "model": "moonshot-v1-8k"},
    "自定义": {"base": "", "model": ""}
}

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}


def normalize_api_base(api_base):
    """统一 API Base，避免出现 //models 或 //chat/completions。"""
    return (api_base or "").strip().rstrip("/")


@st.cache_data(ttl=300, show_spinner=False)
def fetch_available_models(api_base, api_key):
    """从 OpenAI 兼容接口获取模型；失败时由界面回退到默认/手动模式。"""
    api_base = normalize_api_base(api_base)
    if not api_base or not api_key:
        return [], "请先填写 API Key"

    try:
        response = requests.get(
            f"{api_base}/models",
            headers={**REQUEST_HEADERS, "Authorization": f"Bearer {api_key}"},
            timeout=12,
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict):
            raw_models = payload.get("data") or []
        elif isinstance(payload, list):
            raw_models = payload
        else:
            raw_models = []
        models = sorted(
            {
                item.get("id") if isinstance(item, dict) else str(item)
                for item in raw_models
                if (isinstance(item, dict) and item.get("id")) or isinstance(item, str)
            },
            key=str.lower,
        )
        if not models:
            return [], "接口已连接，但没有返回可用模型"
        return models, ""
    except requests.RequestException as exc:
        return [], f"模型列表更新失败：{exc}"
    except (TypeError, ValueError) as exc:
        return [], f"模型列表格式无法识别：{exc}"

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

    selected_provider = st.selectbox("选择大模型服务商", provider_options, index=default_provider_index)
    
    if selected_provider == "自定义":
        api_base = st.text_input("API Base URL", value=default_base)
    else:
        api_base = PRESET_MODELS[selected_provider]["base"]
    api_key = st.text_input("API Key", type="password", value=default_key)

    api_base = normalize_api_base(api_base)
    preset_model = PRESET_MODELS[selected_provider]["model"]
    saved_model = default_model if api_base == normalize_api_base(default_base) else ""

    if selected_provider == "自定义":
        live_models, model_error = fetch_available_models(api_base, api_key) if api_key else ([], "")
        if live_models:
            options = live_models + ([saved_model] if saved_model and saved_model not in live_models else [])
            initial_model = saved_model if saved_model in options else options[0]
            model_name = st.selectbox("联网模型列表", options, index=options.index(initial_model))
            st.caption(f"✅ 已联网获取 {len(live_models)} 个模型（每 5 分钟自动更新）")
        else:
            model_name = st.text_input("模型名称", value=saved_model)
            if model_error:
                st.caption(f"⚠️ {model_error}，可手动填写模型名称。")
    else:
        live_models, model_error = fetch_available_models(api_base, api_key) if api_key else ([], "")
        if live_models:
            options = live_models + ([saved_model] if saved_model and saved_model not in live_models else [])
            preferred_model = saved_model if saved_model in options else preset_model
            initial_model = preferred_model if preferred_model in options else options[0]
            model_name = st.selectbox("选择模型（联网更新）", options, index=options.index(initial_model))
            st.caption(f"✅ 已获取 {len(live_models)} 个最新可用模型（缓存 5 分钟）")
        else:
            fallback_model = saved_model or preset_model
            model_name = st.text_input("模型名称（接口不可用时可手动修改）", value=fallback_model)
            if api_key and model_error:
                st.caption(f"⚠️ {model_error}")

    if st.button("🔄 立即刷新模型列表", use_container_width=True):
        fetch_available_models.clear()
        st.rerun()
    
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
@st.cache_data(ttl=15, show_spinner=False)
def fetch_market_indices():
    """获取实时指数快照，盘中为最新价、收盘后为最新收盘价。"""
    secids = "1.000001,0.399001,0.399006"
    url = "https://push2.eastmoney.com/api/qt/ulist.np/get"
    params = {
        "fltt": "2",
        "invt": "2",
        "fields": "f12,f14,f2,f3,f4,f18,f124",
        "secids": secids,
    }
    try:
        response = requests.get(url, params=params, headers=REQUEST_HEADERS, timeout=8)
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data") or {} if isinstance(payload, dict) else {}
        rows = data.get("diff") or []
        if isinstance(rows, dict):
            rows = list(rows.values())
        results = {}
        for row in rows:
            name = row.get("f14")
            price = row.get("f2")
            pct_chg = row.get("f3")
            if name and isinstance(price, (int, float)):
                quote_time = row.get("f124")
                if quote_time:
                    updated_at = datetime.datetime.fromtimestamp(
                        quote_time, tz=datetime.timezone(datetime.timedelta(hours=8))
                    ).strftime("%Y-%m-%d %H:%M:%S")
                else:
                    updated_at = datetime.datetime.now(
                        datetime.timezone(datetime.timedelta(hours=8))
                    ).strftime("%Y-%m-%d %H:%M:%S")
                results[name] = {
                    "close": float(price),
                    "pct_chg": float(pct_chg or 0),
                    "change": float(row.get("f4") or 0),
                    "updated_at": updated_at,
                }
        return results, ""
    except (requests.RequestException, TypeError, ValueError) as exc:
        return {}, f"实时指数获取失败：{exc}"

@st.cache_data(ttl=60, show_spinner=False)
def fetch_stock_data(symbol):
    try:
        if symbol in ["上证指数", "sh000001", "999999"]: secid = "1.000001"
        elif symbol in ["深证成指", "sz399001", "399001"]: secid = "0.399001"
        elif symbol in ["创业板指", "sz399006", "399006"]: secid = "0.399006"
        else: secid = f"1.{symbol}" if symbol.startswith(('6', '5')) else f"0.{symbol}"
            
        url = f"https://push2his.eastmoney.com/api/qt/stock/kline/get?secid={secid}&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116&klt=101&fqt=1&end=20500101&lmt=100"
        
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=15)
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
        response = requests.post(f"{normalize_api_base(api_base)}/chat/completions", headers=headers, json=payload, timeout=30)
        if response.status_code == 200: return response.json()['choices'][0]['message']['content']
        else: return f"API请求失败: {response.status_code} - {response.text}"
    except Exception as e:
        return f"请求异常: {str(e)}"

# ================= 主界面渲染 =================
st.title("🤖 A股技术面 AI 诊断师")

with st.container():
    market_data, market_error = fetch_market_indices()
    if market_data:
        m_cols = st.columns(3)
        for col, (name, data) in zip(m_cols, market_data.items()):
            col.metric(name, f"{data['close']:.2f}", f"{data['pct_chg']:+.2f}%", delta_color="inverse")
            if col.button(f"🤖 诊断{name}", key=f"btn_{name}", use_container_width=True):
                st.session_state.trigger_analysis = name
        latest_quote_time = max(item["updated_at"] for item in market_data.values())
        st.caption(f"行情更新时间（北京时间）：{latest_quote_time} · 页面加载自动获取，数据缓存 15 秒")
    elif market_error:
        st.warning(market_error)

    if st.button("🔄 刷新指数行情", use_container_width=True):
        fetch_market_indices.clear()
        st.rerun()
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
