import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ================= 1. 网页大屏 UI 设置 =================
st.set_page_config(page_title="极速刺客 V4.4 终极版", layout="wide")
st.title("🎯 极速刺客 V4.4 - 终极全视界指挥部")
st.markdown("---")
st.sidebar.header("⚙️ 战术控制台")

error_rate = st.sidebar.number_input("允许 EXPMA 误差 (%)", 0.1, 5.0, 2.0, 0.1) / 100
lookback_days = st.sidebar.number_input("近期寻找涨停的天数", 3, 20, 10)
vol_limit = st.sidebar.number_input("缩量要求 (低于涨停量%)", 10, 120, 80) / 100
amp_limit = st.sidebar.number_input("今日振幅上限 (避雷%)", 1.0, 15.0, 8.0, 0.5)
profit_target = st.sidebar.number_input("预设止盈点 (次日%)", 1.0, 10.0, 3.0, 0.5) / 100

def get_market_prefix(code):
    return f"sh{code}" if code.startswith('6') else f"sz{code}"

# ================= 2. 杀戮引擎 =================
def full_analysis(code, error_limit, days, v_ratio, a_limit, p_target):
    headers = {'User-Agent': 'Mozilla/5.0'}
    t_code = get_market_prefix(code)
    
    url_day = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={t_code},day,,,60,qfq"
    url_min = f"https://web.ifzq.gtimg.cn/appstock/app/minute/query?code={t_code}"
    
    try:
        # --- A. 解析日 K 数据 ---
        res_day = requests.get(url_day, headers=headers, timeout=5).json()
        if t_code not in res_day['data'] or res_day['data'][t_code] == "":
            st.error("🚨 目标不存在！请检查代码。")
            return None

        try:
            stock_name = res_day['data'][t_code]['qt'][t_code][1]
        except:
            stock_name = "未知名称"

        raw = res_day['data'][t_code]['qfqday'] if 'qfqday' in res_day['data'][t_code] else res_day['data'][t_code]['day']
        df = pd.DataFrame(raw, columns=['日期', '开盘', '收盘', '最高', '最低', '成交量'])
        df[['开盘', '收盘', '最高', '最低', '成交量']] = df[['开盘', '收盘', '最高', '最低', '成交量']].astype(float)
        
        df['昨收'] = df['收盘'].shift(1)
        df['涨幅'] = (df['收盘'] - df['昨收']) / df['昨收'] * 100
        df['EXPMA_12'] = df['收盘'].ewm(span=12, adjust=False).mean()
        df['振幅'] = (df['最高'] - df['最低']) / df['昨收'] * 100
        
        today = df.iloc[-1]
        close, exp12, vol, amp, prev_close = today['收盘'], today['EXPMA_12'], today['成交量'], today['振幅'], today['昨收']
        diff = (close - exp12) / exp12

        recent = df.iloc[-int(days)-1:-1]
        limit_ups = recent[recent['涨幅'] >= 9.5]
        gene = "❌ 无涨停基因"
        if not limit_ups.empty:
            max_v = limit_ups['成交量'].max()
            gene = "✅ 涨停缩量" if vol <= max_v * v_ratio else "⚠️ 涨停放量(嫌疑)"
            
        amp_status = "🟢 走势平稳" if amp <= a_limit else f"🔴 振幅过大({round(amp,1)}%)"
        line_status = "🎯 完美踩线" if 0 <= diff <= error_limit else ("💀 破位" if diff < 0 else "悬空")

        target_price = close * (1 + p_target)
        stop_price = exp12 * 0.99 
        
        # --- B. 解析分时数据 ---
        intra_df = pd.DataFrame()
        try:
            res_min = requests.get(url_min, headers=headers, timeout=5).json()
            min_data = res_min['data'][t_code]['data']['data']
            parsed_min = []
            for item in min_data:
                parts = item.split(' ')
                parsed_min.append({'时间': parts[0][:2] + ":" + parts[0][2:], '价格': float(parts[1]), '累计量': float(parts[2])})
            intra_df = pd.DataFrame(parsed_min)
            
            # ⚡️ 计算每分钟成交量
            intra_df['成交量'] = intra_df['累计量'].diff().fillna(intra_df['累计量']).clip(lower=0)
            intra_df['昨价'] = intra_df['价格'].shift(1).fillna(prev_close)
            
            # ⚡️ 核心升级：计算分时均线 (VWAP)
            # 均价 = 累计成交金额 / 累计成交量 (这里用 价格*成交量 模拟成交金额)
            intra_df['分钟成交额'] = intra_df['价格'] * intra_df['成交量']
            intra_df['累计成交额'] = intra_df['分钟成交额'].cumsum()
            intra_df['均价'] = intra_df['累计成交额'] / intra_df['累计量']
            
        except Exception as e:
            pass 

        return {
            "name": stock_name, "code": code, "df": df, "intra_df": intra_df, "prev_close": prev_close,
            "close": close, "exp12": exp12, "diff": diff,
            "gene": gene, "amp": amp_status, "line": line_status,
            "target": target_price, "stop": stop_price
        }
    except Exception as e:
        st.error(f"侦察失败: {e}")
        return None

# ================= 3. 指挥台 =================
col1, col2 = st.columns([3, 1])
with col1:
    target_code = st.text_input("🔍 输入6位猎物代码锁定目标", max_chars=6)
with col2:
    st.write(""); st.write("")
    fire = st.button("🔫 瞬间测算与成图", type="primary", use_container_width=True)

if fire and len(target_code) == 6:
    report = full_analysis(target_code, error_rate, lookback_days, vol_limit, amp_limit, profit_target)
    
    if report:
        st.markdown(f"### 📜 【{report['name']} - {report['code']}】 绝密刺杀报告")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("当前现价", f"￥{report['close']}")
        c2.metric("EXPMA 12 防线", round(report['exp12'], 2), f"{round(report['diff']*100, 2)}%")
        c3.metric("涨停判定", report['gene'])
        c4.metric("刺杀指令", report['line'])

        st.markdown("---")
        a1, a2, a3 = st.columns(3)
        a1.info(f"📈 次日绝杀止盈 (+{int(profit_target*100)}%): **￥{round(report['target'], 2)}**")
        a2.warning(f"📉 铁血止损防线 (破线1%): **￥{round(report['stop'], 2)}**")
        a3.error(f"⚡ 波动扫描预警: **{report['amp']}**")
        st.markdown("---")
        
        tab1, tab2 = st.tabs(["📉 战术显微镜 (今日分时走势)", "📊 战略透视镜 (近期日 K 走势)"])
        
        # --- TAB 1: 真实分时图 (含均线) ---
        with tab1:
            if not report['intra_df'].empty:
                intra = report['intra_df']
                prev_c = report['prev_close']
                min_colors = ['red' if p >= y else 'green' for p, y in zip(intra['价格'], intra['昨价'])]
                
                fig_intra = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.02, row_heights=[0.7, 0.3])
                
                # 1. 股价白线 (根据红绿盘变色)
                l_color = '#FF5252' if report['close'] >= prev_c else '#4CAF50'
                fig_intra.add_trace(go.Scatter(
                    x=intra['时间'], y=intra['价格'], mode='lines', 
                    line=dict(color=l_color, width=2), 
                    fill='tozeroy', fillcolor=f"rgba({ '255,82,82' if report['close'] >= prev_c else '76,175,80' }, 0.05)", 
                    name="股价线"
                ), row=1, col=1)
                
                # ⚡️ 核心升级：分时均价黄线 (同花顺标配)
                fig_intra.add_trace(go.Scatter(
                    x=intra['时间'], y=intra['均价'], mode='lines', 
                    line=dict(color='#FFD700', width=1.5), # 纯正黄金色
                    name="均价线"
                ), row=1, col=1)
                
                # 2. 昨收基准线
                fig_intra.add_hline(y=prev_c, line_dash="dash", line_color="gray", row=1, col=1, opacity=0.5)
                
                # 3. 分时成交量柱
                fig_intra.add_trace(go.Bar(
                    x=intra['时间'], y=intra['成交量'], marker_color=min_colors, name="分钟量"
                ), row=2, col=1)
                
                # 坐标轴居中对齐
                max_diff = max(abs(intra['价格'].max() - prev_c), abs(intra['价格'].min() - prev_c))
                y_max = prev_c + max_diff * 1.1
                y_min = prev_c - max_diff * 1.1
                
                fig_intra.update_layout(xaxis_rangeslider_visible=False, height=550, margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
                fig_intra.update_yaxes(range=[y_min, y_max], row=1, col=1)
                fig_intra.update_xaxes(type='category', nticks=12)
                fig_intra.update_xaxes(showticklabels=False, row=1, col=1)
                st.plotly_chart(fig_intra, use_container_width=True)
            else:
                st.info("暂无分时数据...")

        # --- TAB 2: 日 K 线图 ---
        with tab2:
            chart_df = report['df'].tail(40).copy()
            chart_df['日期'] = chart_df['日期'].astype(str)
            v_cols = ['red' if o <= c else 'green' for o, c in zip(chart_df['开盘'], chart_df['收盘'])]
            fig_k = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])
            fig_k.add_trace(go.Candlestick(x=chart_df['日期'], open=chart_df['开盘'], high=chart_df['最高'], low=chart_df['最低'], close=chart_df['收盘'], increasing_line_color='red', decreasing_line_color='green', name="K线"), row=1, col=1)
            fig_k.add_trace(go.Scatter(x=chart_df['日期'], y=chart_df['EXPMA_12'], mode='lines', line=dict(color='orange', width=2), name='EXPMA 12'), row=1, col=1)
            fig_k.add_trace(go.Bar(x=chart_df['日期'], y=chart_df['成交量'], marker_color=v_cols, name="成交量"), row=2, col=1)
            fig_k.update_layout(xaxis_rangeslider_visible=False, height=600, margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
            fig_k.update_xaxes(type='category')
            fig_k.update_xaxes(showticklabels=False, row=1, col=1)
            st.plotly_chart(fig_k, use_container_width=True)

elif fire:
    st.warning("⚠️ 请输对 6 位代码！")