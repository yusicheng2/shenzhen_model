import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# ================= 页面配置 =================
st.set_page_config(page_title="深圳园区光储综合能源与现货交易模型", layout="wide")

# 修改点：在此处添加了隐藏 header, MainMenu 和 stDeployButton 的 CSS
st.markdown('''
<style>
/* 隐藏右上角的主菜单、部署按钮和整个头部容器 */
#MainMenu {visibility: hidden;}
header {visibility: hidden;}
.stDeployButton {display:none;}
footer {visibility: hidden;} /* 可选：隐藏底部的 "Made with Streamlit" */

/* 原有自定义样式 */
.custom-main-title { font-size: 1.8rem !important; font-weight: bold; margin-bottom: 0.5rem; }
.custom-sub-title { font-size: 1.3rem !important; font-weight: bold; margin-top: 1.5rem; margin-bottom: 0.5rem; }
div[data-testid="stMetricValue"] { font-size: 22px !important; white-space: normal !important; word-break: break-word !important; }
</style>
''', unsafe_allow_html=True)

st.markdown('<div class="custom-main-title">⚡ 深圳市园区综合能源现货交易与收益量化模型 (深圳专属 v1.0)</div>', unsafe_allow_html=True)
st.caption("v1.0 核心逻辑：引入表后EMC自发自用结算 ｜ 储能需量削峰与峰谷套利 ｜ 独立现货交易与VPP响应")
st.markdown("---")

# ================= 侧边栏：参数输入 =================
st.sidebar.header("📊 园区资产与交易参数设定")

st.sidebar.subheader("1. 物理资产参数 (基于初始设定)")
pv_cap = st.sidebar.slider("光伏装机 (MW)", 0.0, 20.0, 6.0, 0.5)
pv_hours = st.sidebar.number_input("光伏年等效利用小时 (h)", value=1100, step=50)
ess_cap = st.sidebar.slider("储能装机 (MWh)", 0.0, 50.0, 15.0, 1.0)
ess_power = st.sidebar.slider("储能功率 (MW)", 0.0, 20.0, 5.0, 0.5)
park_load = st.sidebar.slider("园区日均基础负荷 (MWh)", 10, 100, 45, 5)

st.sidebar.subheader("2. 运营模式与余电上网 (二选一)")
sz_mode = st.sidebar.radio(
    "深圳市园区运营模式",
    ["模式一：业主自发自用、余电上网的表后EMC模式", "模式二：作为独立主体直接参与电网现货交易与VPP响应模式"]
)

if "表后EMC" in sz_mode:
    self_use_ratio = st.sidebar.slider("光伏自发自用比例 (%)", 0.0, 100.0, 80.0, 1.0) / 100.0
    retail_price = st.sidebar.number_input("综合度电均价/EMC电价 (元/kWh)", 0.5, 1.5, 0.85, 0.05)
    demand_price = st.sidebar.number_input("深圳需量电价节省 (元/kW·月)", 0.0, 60.0, 42.0, 1.0)
else:
    vpp_freq = st.sidebar.slider("每月VPP响应次数", 0, 10, 2, 1)
    vpp_price = st.sidebar.number_input("VPP响应补偿期望 (元/kWh)", 1.0, 10.0, 2.5, 0.5)

feed_mode = st.sidebar.radio(
    "余电/上网结算方案",
    ["竞价成功：增量光伏项目上网电量的80%享受机制电价", "未参与竞价：全额现货市场价"]
)
mech_price = st.sidebar.number_input("机制电价/标杆价 (元/kWh)", value=0.453, step=0.005)
spot_mean = st.sidebar.slider("现货日前市场均价期望 (元/kWh)", 0.15, 0.55, 0.25, 0.01)
spot_sigma = st.sidebar.slider("现货价格波动率 (Sigma)", 0.05, 0.30, 0.15, 0.01)

st.sidebar.subheader("3. 偏差考核与风险参数")
deviation_sigma = st.sidebar.slider("光伏预测误差标准差 (%)", 2.0, 20.0, 8.0, 1.0) / 100.0
penalty_multiplier = st.sidebar.slider("偏差惩罚倍数 (实时电价)", 1.0, 3.0, 1.5, 0.1)
deviation_threshold = st.sidebar.slider("免考核死区 (%)", 0.0, 10.0, 5.0, 0.5) / 100.0

st.sidebar.subheader("4. 年化校准与压力情景")
annual_factor = st.sidebar.slider("年化折算系数 (仅限台风季光伏折减)", 0.60, 1.00, 0.80, 0.05)
typhoon_pv_drop = st.sidebar.slider("台风周光伏出力骤降 (%)", 0, 90, 60, 5) / 100.0
typhoon_price_drop = st.sidebar.slider("台风周现货电价骤降 (%)", 0, 90, 70, 5) / 100.0

st.sidebar.subheader("5. 园区收益分成刚性成本")
share_mode = st.sidebar.radio("收益分成计算模式", ["模式一：按年总用电量分成", "模式二：按定额折扣优惠"])
if share_mode == "模式一：按年总用电量分成":
    share_vol = st.sidebar.number_input("年用电量 (万kWh, 封顶4000)", 0, 4000, 2500, 100)
    share_price = st.sidebar.number_input("度电单价 (元/kWh, 封顶0.10)", 0.00, 0.10, 0.06, 0.01)
    annual_share_cost = share_vol * share_price
else:
    share_fixed = st.sidebar.number_input("年折扣总金额 (万元, 封顶500)", 0, 500, 150, 10)
    annual_share_cost = share_fixed

st.sidebar.subheader("6. 衰减因子与刚性运营成本")
pv_deg = st.sidebar.number_input("光伏组件年均衰减率 (%)", value=0.5, step=0.1)
ess_deg = st.sidebar.number_input("储能电池年衰减率 (%)", value=2.0, step=0.1)
dev_fee = st.sidebar.number_input("园区路条/前期开发费 (万元)", value=200, step=10)
cont_fee = st.sidebar.number_input("不可预见费用 (万元)", value=50, step=10)
land_rent = st.sidebar.number_input("场地租金 (万元/年)", value=10, step=1)
pv_om = st.sidebar.number_input("光伏运维费 (万元/MW/年)", value=5, step=1)
ess_om = st.sidebar.number_input("储能运维费 (万元/年)", value=20, step=1)

# ================= 核心计算引擎 =================
def simulate_market_and_risk(days=30, steps=24):
    np.random.seed(42)
    hours = days * steps
    t = np.arange(hours)

    daily_cycle = 0.15 * np.sin((t % 24 - 6) * np.pi / 12)
    spot_prices = spot_mean + daily_cycle + np.random.normal(0, spot_sigma, hours)
    spot_prices = np.clip(spot_prices, 0.0, 1.5)

    base_pv_curve = np.maximum(0, np.sin((t % 24 - 6) * np.pi / 12))
    daily_base_sum = base_pv_curve[:24].sum()
    
    if pv_cap > 0 and daily_base_sum > 0:
        norm_factor = (pv_hours / 365.0) / daily_base_sum
        pv_generation = pv_cap * 1000 * base_pv_curve * norm_factor
        prediction_error = np.random.normal(0, deviation_sigma, hours)
        pv_actual = pv_generation * np.maximum(0, (1 + prediction_error))
        pv_forecast = pv_generation
        
        deviation = np.abs(pv_actual - pv_forecast)
        threshold_kwh = pv_forecast * deviation_threshold
        penalized_deviation = np.maximum(0, deviation - threshold_kwh)
        penalty_cost = penalized_deviation * spot_prices * penalty_multiplier

        if "表后EMC" in sz_mode:
            self_use_rev = pv_actual * self_use_ratio * retail_price
            if "机制电价" in feed_mode:
                excess_rev = pv_actual * (1 - self_use_ratio) * 0.8 * mech_price + pv_actual * (1 - self_use_ratio) * 0.2 * spot_prices
            else:
                excess_rev = pv_actual * (1 - self_use_ratio) * spot_prices
            mech_revenue = self_use_rev + excess_rev
            spot_revenue = np.zeros(hours)
        else:
            if "机制电价" in feed_mode:
                mech_revenue = pv_actual * 0.8 * mech_price
                spot_revenue = pv_actual * 0.2 * spot_prices
            else:
                mech_revenue = np.zeros(hours)
                spot_revenue = pv_actual * spot_prices
    else:
        pv_forecast = np.zeros(hours)
        pv_actual = np.zeros(hours)
        mech_revenue = np.zeros(hours)
        spot_revenue = np.zeros(hours)
        penalty_cost = np.zeros(hours)

    ess_revenue = np.zeros(hours)
    if ess_cap > 0 and ess_power > 0:
        if "表后EMC" in sz_mode:
            daily_arb_profit = ess_cap * 0.85 * 0.7 * 1000  
            demand_savings_total = ess_power * 1000 * demand_price * (days / 30.0) 
            for h in range(hours):
                ess_revenue[h] = (daily_arb_profit / 24.0) + (demand_savings_total / hours)
        else:
            soc = ess_cap * 0.5  
            for h in range(hours):
                price = spot_prices[h]  
                if price < (spot_mean - 0.5 * spot_sigma) and soc < ess_cap * 0.9:
                    charge_mwh = min(ess_power, (ess_cap * 0.9 - soc) / 0.85)
                    soc += charge_mwh * 0.85
                    ess_revenue[h] -= charge_mwh * 1000 * price
                elif price > (spot_mean + 0.5 * spot_sigma) and soc > ess_cap * 0.1:
                    discharge_mwh = min(ess_power, (soc - ess_cap * 0.1))
                    soc -= discharge_mwh / 0.85
                    ess_revenue[h] += discharge_mwh * 1000 * price
            vpp_total = vpp_freq * (days/30.0) * ess_power * 1000 * vpp_price
            for h in range(hours):
                ess_revenue[h] += vpp_total / hours

    return pd.DataFrame({
        'Hour': t, 'Spot_Price': spot_prices,
        'PV_Forecast': pv_forecast, 'PV_Actual': pv_actual,
        'Mech_Rev': mech_revenue, 'Spot_Rev': spot_revenue,
        'ESS_Rev': ess_revenue, 'Penalty': penalty_cost
    })

df = simulate_market_and_risk()

# ================= 财务与风险指标 =================
total_rev = df['Mech_Rev'].sum() + df['Spot_Rev'].sum() + df['ESS_Rev'].sum()
total_penalty = df['Penalty'].sum()

fixed_opex_annual = (pv_cap * pv_om) + ess_om + land_rent  
monthly_share_cost_rmb = (annual_share_cost * 10000.0) / 12.0
monthly_fixed_opex_rmb = (fixed_opex_annual * 10000.0) / 12.0
weekly_share_cost_rmb = (annual_share_cost * 10000.0) * (7.0 / 365.0)
weekly_fixed_opex_rmb = (fixed_opex_annual * 10000.0) * (7.0 / 365.0)

sim_gross_rev = total_rev - total_penalty
sim_net_rev = sim_gross_rev - monthly_share_cost_rmb - monthly_fixed_opex_rmb

capex = (pv_cap * 280.0 + ess_cap * 70.0) + dev_fee + cont_fee

pv_rev_1 = (df['Mech_Rev'].sum() + df['Spot_Rev'].sum()) * (365/30) * annual_factor / 10000.0
ess_rev_1 = df['ESS_Rev'].sum() * (365/30) / 10000.0
penalty_1 = df['Penalty'].sum() * (365/30) * annual_factor / 10000.0

cumulative_cash = 0.0
payback_years = 0.0
total_net_20y = 0.0

for y in range(1, 21):
    p_factor = (1 - pv_deg / 100.0)**(y - 1)
    e_factor = (1 - ess_deg / 100.0)**(y - 1)
    y_rev = (pv_rev_1 * p_factor) + (ess_rev_1 * e_factor) - (penalty_1 * p_factor)
    y_net = y_rev - annual_share_cost - fixed_opex_annual
    total_net_20y += y_net
    if payback_years == 0:
        cumulative_cash += y_net
        if cumulative_cash >= capex and y_net > 0:
            payback_years = (y - 1) + (capex - (cumulative_cash - y_net)) / y_net

avg_net_20y = total_net_20y / 20.0
year1_net_rev_10k = (pv_rev_1 + ess_rev_1 - penalty_1) - annual_share_cost - fixed_opex_annual

payback_display = "无新增资产" if capex == 0 else (f"{payback_years:.1f} 年" if payback_years > 0 else ">20年 (无法回本)")

np.random.seed(7)
mc_results = []
for _ in range(2000):
    price_f = np.random.normal(1.0, 0.2)
    dev_f = np.abs(np.random.normal(1.0, 0.4))
    sim_gross = (total_rev * price_f) - (total_penalty * dev_f * penalty_multiplier)
    sim_net = sim_gross - monthly_share_cost_rmb - monthly_fixed_opex_rmb
    mc_results.append(sim_net / 10000.0)
mc_arr = np.array(mc_results)
p5_value = np.percentile(mc_arr, 5)
var95 = (sim_net_rev / 10000.0) - p5_value

# 台风周极端压力测试 (简化版)
np.random.seed(99)
t_s = np.arange(7 * 24)
base_pv_curve = np.maximum(0, np.sin((t_s % 24 - 6) * np.pi / 12))
daily_base_sum = base_pv_curve[:24].sum()

if pv_cap > 0 and daily_base_sum > 0:
    norm_factor = (pv_hours / 365.0) / daily_base_sum
    pv_forecast_week = pv_cap * 1000 * base_pv_curve * norm_factor
    pv_actual_week = pv_forecast_week * (1 - typhoon_pv_drop)
    crash_price = np.clip(spot_mean * (1 - typhoon_price_drop), 0.0, 1.5)

    if "表后EMC" in sz_mode:
        stress_revenue = (pv_actual_week * self_use_ratio * retail_price).sum() + (pv_actual_week * (1-self_use_ratio) * crash_price).sum()
    else:
        if "机制电价" in feed_mode:
            stress_revenue = (pv_actual_week * 0.8 * mech_price).sum() + (pv_actual_week * 0.2 * crash_price).sum()
        else:
            stress_revenue = (pv_actual_week * crash_price).sum()
            
    stress_deviation = np.maximum(0, (pv_forecast_week - pv_actual_week) - deviation_threshold * pv_forecast_week)
    stress_penalty = (stress_deviation * crash_price * penalty_multiplier).sum()
else:
    stress_revenue, stress_penalty = 0.0, 0.0

stress_ess_rev = df['ESS_Rev'].sum() / (30.0 / 7.0)
stress_net = (stress_revenue + stress_ess_rev) - stress_penalty - weekly_share_cost_rmb - weekly_fixed_opex_rmb
normal_week_net = sim_net_rev / (30.0 / 7.0)
stress_shrink_pct = ((normal_week_net - stress_net) / normal_week_net * 100.0) if normal_week_net > 0 else 0.0

# ================= 前端可视化 =================
col1, col2, col3, col4 = st.columns(4)
col1.metric("模拟期(单月)净收益", f"{sim_net_rev/10000:.2f} 万元", f"20年均净收益: {avg_net_20y:.1f} 万")
col2.metric("动态回本期(含衰减)", payback_display, f"首年净利润: {year1_net_rev_10k:.1f} 万")
col3.metric("偏差考核总罚款", f"{total_penalty/10000:.2f} 万元", "⚠️ 现货偏差风险", delta_color="inverse")
col4.metric("P5风险价值 (VaR95)", f"{var95:.2f} 万元", f"P5净收益 {p5_value:.1f} 万", delta_color="inverse")

st.markdown('<div class="custom-sub-title">📈 深圳资产收益构成瀑布图</div>', unsafe_allow_html=True)
rev_components = {
    '光伏EMC/机制收益': df['Mech_Rev'].sum(),
    '光伏现货敞口收益': df['Spot_Rev'].sum(),
    '储能/VPP/套利收益': df['ESS_Rev'].sum(),
    '偏差考核罚款(扣除)': -df['Penalty'].sum(),
    '园区收益分成(扣除)': -monthly_share_cost_rmb,
    '固定运维与租金(扣除)': -monthly_fixed_opex_rmb
}
rev_components = {k: v for k, v in rev_components.items() if v != 0}

fig2 = go.Figure(go.Waterfall(
    name="收益瀑布", orientation="v",
    x=list(rev_components.keys()), y=list(rev_components.values()),
    connector={"line": {"color": "rgb(63, 63, 63)"}},
))
fig2.update_layout(title="模拟期(单月)现金流净构成 (单位：元)", yaxis_title="金额", template="plotly_white")
st.plotly_chart(fig2, use_container_width=True)

st.markdown("---")
st.markdown('<div class="custom-main-title" style="margin-top: 1rem;">📜 深圳专属专家策略与法律边界分析</div>', unsafe_allow_html=True)

st.subheader("1. 深圳特有电价与商业模式适配")
if "表后EMC" in sz_mode:
    st.success("**✅ 稳健型：表后EMC自用为主**。深圳高额的零售电价是光伏的最佳消纳场景，配合储能削峰填谷（减少每月需量电费），能获取极为确定的收益。注意监控净外购电量的月利用小时，避免跌破250h/400h触发输配电价升档。")
else:
    st.warning("**⚠️ 激进型：直接参与现货与VPP**。独立主体身份脱离了深圳园区高昂零售电价的保护伞，收益完全由电力现货价差及VPP（虚拟电厂）调峰补偿决定。必须依靠高频套利算法与辅助服务对冲敞口风险。")

st.subheader("2. 法律边界与 EMC / 现货合规要点")
st.markdown('''
1. **需量电费核算争议**：在表后EMC模式下，储能削峰填谷产生的“需量/容量电费节省”往往成为园区与投资方扯皮的重灾区。合同中必须明确基准需量以及节约额的分配比例。
2. **利用小时跌档风险（深圳特有）**：由于光伏大量自发自用，可能导致园区从电网净购电量大幅下降，触发《深圳电网输配电价表》中“250小时/400小时”以下的惩罚性高档输配电价。EMC合同必须包含此类政策性风险的豁免或补偿条款。
3. **VPP 聚合调度责任边界**：在独立主体模式下，直接参与现货与VPP响应时，需事前取得业主排他性的调度授权，并厘清因设备故障导致响应未达标的违约金分担机制。
''')
st.caption("© 2026 yusicheng lawyer | 慎独 · 专注 · 专业\n\n⚖️ 免责声明：本模型已引入增量光伏项目上网电量的80%享受机制电价设定，测算结果供投资论证及风险对冲参考，不构成法定收益承诺。")
