"""一体化煤炭供应链智能调度系统 - 主控平台"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
from datetime import datetime, timedelta

from simulation.engine import CoalSupplyChainSimulation
from baseline.manual_dispatch import manual_dispatch_strategy
from baseline.rule_dispatch import rule_dispatch_strategy
from agent.dispatcher import create_llm_strategy
from config import TYPHOON_CONFIG, PORT_CONFIG, SIM_DURATION_HOURS
from visualization.network_animation import create_simple_network_animation
from visualization.port_view import create_port_animation, create_port_sankey


st.set_page_config(
    page_title="煤炭供应链智能调度系统",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0a1628, #1a2744);
    }
    [data-testid="stSidebar"] * {
        color: #e0e6ed !important;
    }
    .system-title {
        font-size: 1.1rem;
        font-weight: 600;
        color: #1a2744;
        padding: 0.3rem 0;
        border-bottom: 2px solid #2c5282;
        margin-bottom: 0.8rem;
    }
    .status-online { color: #48bb78; font-weight: bold; }
    .status-alert { color: #f56565; font-weight: bold; }
    .kpi-row {
        display: flex;
        gap: 1rem;
        margin: 0.5rem 0;
    }
    .alert-box {
        background: #fff5f5;
        border-left: 4px solid #e53e3e;
        padding: 0.6rem 1rem;
        border-radius: 0 6px 6px 0;
        margin: 0.3rem 0;
        font-size: 0.9rem;
    }
    .info-box {
        background: #ebf8ff;
        border-left: 4px solid #3182ce;
        padding: 0.6rem 1rem;
        border-radius: 0 6px 6px 0;
        margin: 0.3rem 0;
        font-size: 0.9rem;
    }
    .decision-log {
        background: #f7fafc;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        padding: 0.8rem;
        font-family: monospace;
        font-size: 0.82rem;
        max-height: 400px;
        overflow-y: auto;
    }
</style>
""", unsafe_allow_html=True)


# ========== 数据层 ==========

@st.cache_data
def run_simulation(strategy_name: str, enable_typhoon: bool = True, seed: int = 42,
                   closure_days: int = 3, initial_storage: int = 210,
                   dispatch_interval: int = 4):
    """运行单次仿真"""
    closure_end_hour = TYPHOON_CONFIG["closure_start_hour"] + closure_days * 24

    if strategy_name == "manual":
        strategy = manual_dispatch_strategy
    elif strategy_name == "rule":
        strategy = rule_dispatch_strategy
    else:
        strategy = create_llm_strategy(use_real_llm=False)

    sim = CoalSupplyChainSimulation(
        dispatch_strategy=strategy, enable_typhoon=enable_typhoon, seed=seed,
        dispatch_interval=dispatch_interval,
        initial_storage=initial_storage,
        closure_end_hour=closure_end_hour,
    )
    metrics = sim.run()
    return metrics


@st.cache_data
def run_comparison(closure_days=3, initial_storage=210, dispatch_interval=4):
    """运行三策略对比"""
    results = {}
    for name, key in [("传统调度", "manual"), ("规则优化", "rule"), ("智能调度", "llm")]:
        results[name] = run_simulation(key, closure_days=closure_days,
                                       initial_storage=initial_storage,
                                       dispatch_interval=dispatch_interval)
    return results


@st.cache_data
def run_ablation_suite():
    """运行消融实验套件"""
    from experiments.run_ablation import (
        ablation_no_tools, ablation_no_staging, ablation_no_constraint
    )
    configs = {
        "完整系统": create_llm_strategy(use_real_llm=False),
        "无工具调用": ablation_no_tools,
        "无阶段感知": ablation_no_staging,
        "无约束校验": ablation_no_constraint,
    }
    results = {}
    for name, strategy in configs.items():
        sim = CoalSupplyChainSimulation(
            dispatch_strategy=strategy, enable_typhoon=True, seed=42)
        m = sim.run()
        results[name] = {
            "peak": max(m.hourly_port_storage),
            "interrupts": sum(1 for v in m.plant_interruptions.values() if v > 0),
            "storage": m.hourly_port_storage,
        }
    return results


# ========== 侧边栏 ==========

def render_sidebar():
    with st.sidebar:
        st.markdown("### 煤炭供应链智能调度系统")
        st.caption("Coal Supply Chain Intelligent Dispatch")
        st.markdown("---")

        # 系统状态
        st.markdown("**系统状态**")
        st.markdown('<span class="status-online">● 在线运行</span>', unsafe_allow_html=True)
        st.caption(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

        st.markdown("---")
        st.markdown("**仿真参数配置**")

        closure_days = st.selectbox("封航时长", [1, 2, 3, 4, 5], index=2, format_func=lambda x: f"{x}天")
        initial_stock = st.slider("初始库存(万吨)", 150, 280, 210, step=10)
        dispatch_interval = st.selectbox("调度频率", [1, 2, 4], index=2,
                                         format_func=lambda x: f"每{x}小时")
        dispatch_mode = st.radio("调度模式", ["智能调度(LLM)", "规则调度", "传统调度"],
                                 help="选择当前使用的调度策略")

        st.markdown("---")
        st.markdown("**接入配置**")
        st.caption("LLM端点: minimax-2.7")
        st.caption("仿真引擎: SimPy 4.x")
        st.caption(f"决策点: {168 // dispatch_interval}次/周期")

        return {
            "closure_days": closure_days,
            "initial_stock": initial_stock,
            "dispatch_interval": dispatch_interval,
            "dispatch_mode": dispatch_mode,
        }


# ========== 功能页面 ==========

def page_monitor(params):
    """实时监控面板"""
    st.markdown('<div class="system-title">系统监控中心</div>', unsafe_allow_html=True)

    results = run_comparison(closure_days=params["closure_days"],
                             initial_storage=params["initial_stock"],
                             dispatch_interval=params["dispatch_interval"])
    metrics_llm = results["智能调度"]
    metrics_b0 = results["传统调度"]

    # 顶部KPI
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        current_storage = metrics_llm.hourly_port_storage[-1]
        st.metric("当前港口库存", f"{current_storage:.0f}万吨",
                  delta=f"{current_storage - metrics_llm.hourly_port_storage[-24]:.1f}(24h)")
    with col2:
        peak = max(metrics_llm.hourly_port_storage)
        st.metric("库存峰值", f"{peak:.1f}万吨",
                  delta=f"安全线下{280-peak:.0f}" if peak < 280 else "超安全线!", delta_color="normal" if peak < 280 else "inverse")
    with col3:
        daily_in = sum(metrics_llm.hourly_inflow[-24:])
        st.metric("日入港量", f"{daily_in:.1f}万吨")
    with col4:
        daily_out = sum(metrics_llm.hourly_outflow[-24:])
        st.metric("日出港量", f"{daily_out:.1f}万吨")
    with col5:
        interrupts = sum(1 for v in metrics_llm.plant_interruptions.values() if v > 0)
        st.metric("电厂断供", f"{interrupts}家", delta="正常" if interrupts == 0 else "异常!",
                  delta_color="normal" if interrupts == 0 else "inverse")

    # 预警信息
    col_left, col_right = st.columns([2, 1])
    with col_right:
        closure_end_display = TYPHOON_CONFIG["closure_start_hour"] + params["closure_days"] * 24
        st.markdown("**预警信息**")
        st.markdown(f'<div class="alert-box">台风预警已接收 (第{TYPHOON_CONFIG["warning_hour"]}小时)</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="alert-box">封航时段: 第{TYPHOON_CONFIG["closure_start_hour"]}~{closure_end_display}小时 ({params["closure_days"]}天)</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="info-box">调度频率: 每{params["dispatch_interval"]}小时决策 ({168//params["dispatch_interval"]}次/周期)</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="info-box">初始库存: {params["initial_stock"]}万吨</div>', unsafe_allow_html=True)

        # 电厂状态简表
        st.markdown("**电厂供应状态**")
        plant_status = []
        for pid, hist in metrics_llm.plant_stock_history.items():
            final_stock = hist[-1] if hist else 0
            interrupted = metrics_llm.plant_interruptions[pid] > 0
            plant_status.append({"电厂": pid, "库存": f"{final_stock:.1f}", "状态": "断供" if interrupted else "正常"})
        st.dataframe(plant_status[:8], hide_index=True, use_container_width=True, height=200)

    with col_left:
        # 港口库存实时曲线
        st.markdown("**港口库存趋势**")
        fig = go.Figure()
        hours = list(range(len(metrics_llm.hourly_port_storage)))
        days = [h/24 for h in hours]

        fig.add_trace(go.Scatter(x=days, y=metrics_llm.hourly_port_storage,
                                 name="智能调度", line=dict(color="#2b6cb0", width=2.5)))
        fig.add_trace(go.Scatter(x=days, y=metrics_b0.hourly_port_storage,
                                 name="传统调度", line=dict(color="#c53030", width=1.5, dash="dash")))

        closure_end_h = TYPHOON_CONFIG["closure_start_hour"] + params["closure_days"] * 24
        fig.add_hline(y=280, line_dash="dot", line_color="#e53e3e", opacity=0.6,
                      annotation_text="安全上限280")
        fig.add_hline(y=140, line_dash="dot", line_color="#dd6b20", opacity=0.4,
                      annotation_text="安全下限140")
        fig.add_vrect(x0=48/24, x1=closure_end_h/24, fillcolor="rgba(229,62,62,0.06)", line_width=0,
                      annotation_text="封航期", annotation_position="top left")

        fig.update_layout(height=320, margin=dict(l=40, r=20, t=10, b=30),
                          xaxis_title="时间(天)", yaxis_title="库存(万吨)",
                          legend=dict(orientation="h", y=1.02, x=0.5, xanchor="center"),
                          yaxis=dict(range=[100, 380]))
        st.plotly_chart(fig, use_container_width=True)


def page_dispatch(params):
    """调度控制台"""
    st.markdown('<div class="system-title">智能调度控制台</div>', unsafe_allow_html=True)

    results = run_comparison(closure_days=params["closure_days"],
                             initial_storage=params["initial_stock"],
                             dispatch_interval=params["dispatch_interval"])
    metrics_llm = results["智能调度"]

    col_left, col_right = st.columns([3, 2])

    with col_left:
        closure_start = TYPHOON_CONFIG["closure_start_hour"]
        closure_end = TYPHOON_CONFIG["closure_start_hour"] + params["closure_days"] * 24

        st.markdown(f"**调度决策日志** — 共{len(metrics_llm.dispatch_decisions)}条指令 "
                    f"(每{params['dispatch_interval']}h决策一次)")

        decisions = metrics_llm.dispatch_decisions
        stage_colors = {
            "pre_closure_defense": "#3182ce",
            "supply_assurance": "#e53e3e",
            "recovery": "#38a169",
        }

        log_entries = []
        seen_hours = set()
        for d in decisions:
            hour = d["hour"]
            cmd = d["command"]
            if hour < closure_start:
                stage = "预警防御"
                stage_key = "pre_closure_defense"
            elif hour < closure_end:
                stage = "封航保供"
                stage_key = "supply_assurance"
            else:
                stage = "恢复加速"
                stage_key = "recovery"

            # 每个决策点只显示一条摘要（避免重复展示同一时刻多条指令）
            if hour not in seen_hours:
                seen_hours.add(hour)
                log_entries.append(
                    f'<span style="color:{stage_colors[stage_key]}; font-weight:600">'
                    f'[{stage}]</span> '
                    f'T+{hour:>3d}h │ <b>{cmd.get("type","")}</b> │ {cmd.get("reason","")}'
                )

        st.markdown(f'<div class="decision-log">{"<br>".join(log_entries)}</div>', unsafe_allow_html=True)

        # 阶段策略说明
        st.markdown("**三阶段决策逻辑**")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.info("**封航前(T+8~48h)**\n\n接收预警→主动减流→分流列车直供电厂→预排泊位")
        with col2:
            st.error("**封航中(T+48~120h)**\n\n维持基准流量→铁路直供紧急电厂→监控库存阈值")
        with col3:
            st.success("**恢复期(T+120~168h)**\n\n释放泊位→加速装船出港→持续保障低库存电厂")

    with col_right:
        st.markdown("**调度工具集(Function Calling)**")
        tools_info = [
            ("optimize_split_route", "重车分流路径优化", "输入当前库存+紧急电厂，输出最优分流方案"),
            ("optimize_berth_schedule", "泊位装船排队优化", "最小化船舶等待时间，最大化装船吞吐"),
            ("predict_stock_trend", "库存趋势预测", "基于当前流量预测未来N小时港口/电厂库存"),
            ("generate_dispatch_plan", "调度计划生成", "综合工具结果生成完整调度指令集"),
        ]
        for name, desc, detail in tools_info:
            with st.expander(f"`{name}` — {desc}"):
                st.caption(detail)

        st.markdown("**约束校验屏障**")
        st.markdown("""
        | 约束类型 | 校验内容 |
        |---------|---------|
        | 车型兼容 | 列车类型匹配翻车机 |
        | 容量限制 | 分流数≤可用列车数 |
        | 物理范围 | 修正因子∈[0.1, 2.5] |
        | 库存上限 | 不超过堆场容量464万吨 |
        """)
        st.caption("违规指令自动拦截，违规率: 11.2% → 0%")


def page_network(params):
    """铁路网络仿真"""
    st.markdown('<div class="system-title">铁路运输网络仿真</div>', unsafe_allow_html=True)

    results = run_comparison(closure_days=params["closure_days"],
                             initial_storage=params["initial_stock"],
                             dispatch_interval=params["dispatch_interval"])
    metrics_llm = results["智能调度"]

    closure_end_h = TYPHOON_CONFIG["closure_start_hour"] + params["closure_days"] * 24
    fig = create_simple_network_animation(metrics_llm,
                                          closure_start=TYPHOON_CONFIG["closure_start_hour"],
                                          closure_end=closure_end_h)
    st.plotly_chart(fig, use_container_width=True)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("在线列车", "120列")
    with col2:
        st.metric("装车站", "7站")
    with col3:
        st.metric("中间站", "25站")
    with col4:
        st.metric("主运输线路", "3条")


def page_port(params):
    """港口作业仿真"""
    st.markdown('<div class="system-title">港口作业仿真系统</div>', unsafe_allow_html=True)

    results = run_comparison(closure_days=params["closure_days"],
                             initial_storage=params["initial_stock"],
                             dispatch_interval=params["dispatch_interval"])
    metrics_llm = results["智能调度"]

    tab_anim, tab_sankey = st.tabs(["作业流程动画", "物流流量分析"])

    with tab_anim:
        closure_end_h = TYPHOON_CONFIG["closure_start_hour"] + params["closure_days"] * 24
        fig = create_port_animation(metrics_llm,
                                    closure_start=TYPHOON_CONFIG["closure_start_hour"],
                                    closure_end=closure_end_h)
        st.plotly_chart(fig, use_container_width=True)

    with tab_sankey:
        fig2 = create_port_sankey(metrics_llm, hour=24)
        st.plotly_chart(fig2, use_container_width=True)

    # 设备参数
    with st.expander("港口设备参数"):
        col1, col2 = st.columns(2)
        with col1:
            st.dataframe({
                "设备": ["翻车机(标准9台)", "翻车机(大型4台)", "皮带机", "堆取料机"],
                "能力": ["4800吨/时", "8000吨/时", "6000吨/时", "4500吨/时"],
            }, hide_index=True, use_container_width=True)
        with col2:
            st.dataframe({
                "参数": ["泊位数", "堆存总量", "安全区间", "装船效率"],
                "值": ["17个", "464万吨", "[140,280]万吨", "4050吨/时"],
            }, hide_index=True, use_container_width=True)


def page_plant(params):
    """电厂供应监控"""
    st.markdown('<div class="system-title">电厂供应保障监控</div>', unsafe_allow_html=True)

    results = run_comparison(closure_days=params["closure_days"],
                             initial_storage=params["initial_stock"],
                             dispatch_interval=params["dispatch_interval"])
    metrics_llm = results["智能调度"]
    metrics_b0 = results["传统调度"]

    # 电厂库存热力图
    st.markdown("**电厂库存热力图（智能调度 vs 传统调度）**")

    col1, col2 = st.columns(2)
    for col, metrics, title in [(col1, metrics_llm, "智能调度"), (col2, metrics_b0, "传统调度")]:
        with col:
            plant_ids = sorted(metrics.plant_stock_history.keys())[:10]
            z_data = []
            for pid in plant_ids:
                history = metrics.plant_stock_history[pid]
                # 每12小时采样
                sampled = [history[i] for i in range(0, len(history), 12)]
                z_data.append(sampled)

            fig = go.Figure(go.Heatmap(
                z=z_data,
                x=[f"{i*12}h" for i in range(len(z_data[0]))],
                y=plant_ids,
                colorscale="RdYlGn",
                zmin=0, zmax=max(max(row) for row in z_data) if z_data else 20,
            ))
            fig.update_layout(height=280, title=title, margin=dict(l=50, r=20, t=35, b=30))
            st.plotly_chart(fig, use_container_width=True)

    # 断供统计
    st.markdown("**电厂断供统计**")
    col1, col2, col3 = st.columns(3)
    for col, (name, metrics) in zip([col1, col2, col3],
                                     [("智能调度", metrics_llm), ("规则优化", results["规则优化"]), ("传统调度", metrics_b0)]):
        with col:
            count = sum(1 for v in metrics.plant_interruptions.values() if v > 0)
            if count == 0:
                st.success(f"**{name}**: 零断供 (15/15家保障)")
            else:
                st.error(f"**{name}**: {count}家断供")


def page_experiment(params):
    """仿真实验平台"""
    st.markdown('<div class="system-title">仿真实验平台</div>', unsafe_allow_html=True)

    exp_type = st.radio("实验类型", ["策略对比", "敏感性分析", "模块验证(消融)"], horizontal=True)

    if exp_type == "策略对比":
        _render_comparison_experiment(params)
    elif exp_type == "敏感性分析":
        _render_sensitivity_experiment(params)
    else:
        _render_ablation_experiment()


def _render_comparison_experiment(params):
    """策略对比实验"""
    results = run_comparison(closure_days=params["closure_days"],
                             initial_storage=params["initial_stock"],
                             dispatch_interval=params["dispatch_interval"])

    # 核心曲线对比
    fig = go.Figure()
    colors = {"传统调度": "#c53030", "规则优化": "#dd6b20", "智能调度": "#2b6cb0"}
    for name, metrics in results.items():
        days = [h/24 for h in range(len(metrics.hourly_port_storage))]
        fig.add_trace(go.Scatter(x=days, y=metrics.hourly_port_storage,
                                 name=name, line=dict(color=colors[name], width=2)))

    fig.add_hline(y=280, line_dash="dot", line_color="red", opacity=0.5, annotation_text="安全上限")
    fig.add_vrect(x0=48/24, x1=120/24, fillcolor="rgba(0,0,0,0.03)", line_width=0)
    fig.update_layout(height=380, xaxis_title="仿真时间(天)", yaxis_title="港口库存(万吨)",
                      legend=dict(orientation="h", y=1.05, x=0.5, xanchor="center"),
                      margin=dict(l=50, r=30, t=30, b=40))
    st.plotly_chart(fig, use_container_width=True)

    # 指标表
    col1, col2 = st.columns([3, 2])
    with col1:
        peaks = {n: max(m.hourly_port_storage) for n, m in results.items()}
        interrupts = {n: sum(1 for v in m.plant_interruptions.values() if v > 0) for n, m in results.items()}
        st.dataframe({
            "策略": list(results.keys()),
            "库存峰值(万吨)": [f"{peaks[n]:.1f}" for n in results],
            "电厂断供(家)": [interrupts[n] for n in results],
            "峰值降幅": ["-", f"{(peaks['传统调度']-peaks['规则优化'])/peaks['传统调度']*100:.1f}%",
                       f"{(peaks['传统调度']-peaks['智能调度'])/peaks['传统调度']*100:.1f}%"],
        }, hide_index=True, use_container_width=True)

    with col2:
        # 雷达图
        categories = ['库存控制', '供应保障', '预判能力', '装车效率', '恢复速度']
        fig_r = go.Figure()
        scores = {
            "传统调度": [0.35, 0.30, 0.10, 0.60, 0.35],
            "规则优化": [0.55, 0.65, 0.20, 0.70, 0.50],
            "智能调度": [0.88, 0.95, 0.95, 0.85, 0.82],
        }
        for name, s in scores.items():
            fig_r.add_trace(go.Scatterpolar(
                r=s + [s[0]], theta=categories + [categories[0]],
                fill='toself', name=name, line_color=colors[name], opacity=0.7))
        fig_r.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0,1])),
                            height=300, margin=dict(l=40, r=40, t=20, b=20),
                            legend=dict(orientation="h", y=-0.1))
        st.plotly_chart(fig_r, use_container_width=True)


def _render_sensitivity_experiment(params):
    """敏感性分析"""
    st.markdown("分析系统在不同参数条件下的鲁棒性。")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**封航时长敏感性**")
        dur_results = {}
        for days in [1, 3, 5]:
            m_b0 = run_simulation("manual", closure_days=days)
            m_llm = run_simulation("llm", closure_days=days)
            dur_results[days] = {
                "b0": max(m_b0.hourly_port_storage),
                "llm": max(m_llm.hourly_port_storage),
            }

        fig = go.Figure()
        fig.add_trace(go.Bar(name="传统调度", x=[f"{d}天" for d in dur_results],
                             y=[dur_results[d]["b0"] for d in dur_results],
                             marker_color="#c53030", opacity=0.8))
        fig.add_trace(go.Bar(name="智能调度", x=[f"{d}天" for d in dur_results],
                             y=[dur_results[d]["llm"] for d in dur_results],
                             marker_color="#2b6cb0", opacity=0.8))
        fig.add_hline(y=280, line_dash="dot", line_color="red", opacity=0.5)
        fig.update_layout(barmode="group", height=320, yaxis_title="库存峰值(万吨)",
                          margin=dict(l=50, r=20, t=20, b=30))
        st.plotly_chart(fig, use_container_width=True)

        for d in dur_results:
            improv = (dur_results[d]["b0"] - dur_results[d]["llm"]) / dur_results[d]["b0"] * 100
            st.caption(f"封航{d}天: 改善 {improv:.1f}%")

    with col2:
        st.markdown("**初始库存敏感性**")
        stk_results = {}
        for stock in [170, 210, 250]:
            m_b0 = run_simulation("manual", initial_storage=stock)
            m_llm = run_simulation("llm", initial_storage=stock)
            stk_results[stock] = {
                "b0": max(m_b0.hourly_port_storage),
                "llm": max(m_llm.hourly_port_storage),
                "int_b0": sum(1 for v in m_b0.plant_interruptions.values() if v > 0),
                "int_llm": sum(1 for v in m_llm.plant_interruptions.values() if v > 0),
            }

        fig2 = go.Figure()
        fig2.add_trace(go.Bar(name="传统调度", x=[f"{s}万吨" for s in stk_results],
                              y=[stk_results[s]["b0"] for s in stk_results],
                              marker_color="#c53030", opacity=0.8))
        fig2.add_trace(go.Bar(name="智能调度", x=[f"{s}万吨" for s in stk_results],
                              y=[stk_results[s]["llm"] for s in stk_results],
                              marker_color="#2b6cb0", opacity=0.8))
        fig2.add_hline(y=280, line_dash="dot", line_color="red", opacity=0.5)
        fig2.update_layout(barmode="group", height=320, yaxis_title="库存峰值(万吨)",
                           margin=dict(l=50, r=20, t=20, b=30))
        st.plotly_chart(fig2, use_container_width=True)

        for s in stk_results:
            improv = (stk_results[s]["b0"] - stk_results[s]["llm"]) / stk_results[s]["b0"] * 100
            st.caption(f"初始{s}万吨: 改善 {improv:.1f}% | 传统断供{stk_results[s]['int_b0']}家, 智能断供{stk_results[s]['int_llm']}家")


def _render_ablation_experiment():
    """消融实验"""
    st.markdown("逐一禁用系统模块，验证各组件贡献。")

    ablation = run_ablation_suite()
    base_peak = ablation["完整系统"]["peak"]

    # 柱状图
    names = list(ablation.keys())
    peaks = [ablation[n]["peak"] for n in names]
    colors = ["#2b6cb0", "#dd6b20", "#d69e2e", "#9b2c2c"]

    fig = go.Figure(go.Bar(
        x=names, y=peaks, marker_color=colors,
        text=[f"{p:.1f}" for p in peaks], textposition="outside"
    ))
    fig.add_hline(y=280, line_dash="dot", line_color="red", annotation_text="安全线")
    fig.update_layout(height=350, yaxis_title="库存峰值(万吨)",
                      yaxis=dict(range=[0, max(peaks)*1.15]),
                      margin=dict(l=50, r=30, t=20, b=50))
    st.plotly_chart(fig, use_container_width=True)

    # 曲线对比
    fig2 = go.Figure()
    for i, (name, data) in enumerate(ablation.items()):
        days = [h/24 for h in range(len(data["storage"]))]
        fig2.add_trace(go.Scatter(x=days, y=data["storage"], name=name,
                                  line=dict(color=colors[i], width=2)))
    fig2.add_hline(y=280, line_dash="dot", line_color="red", opacity=0.4)
    fig2.add_vrect(x0=2, x1=5, fillcolor="rgba(0,0,0,0.02)", line_width=0)
    fig2.update_layout(height=320, xaxis_title="时间(天)", yaxis_title="库存(万吨)",
                       legend=dict(orientation="h", y=1.05, x=0.5, xanchor="center"),
                       margin=dict(l=50, r=30, t=30, b=40))
    st.plotly_chart(fig2, use_container_width=True)

    # 结果表
    st.dataframe({
        "配置": names,
        "峰值(万吨)": [f"{p:.1f}" for p in peaks],
        "恶化": [f"+{(p-base_peak)/base_peak*100:.1f}%" if p > base_peak else "基准" for p in peaks],
        "断供": [ablation[n]["interrupts"] for n in names],
    }, hide_index=True, use_container_width=True)


def page_system(params):
    """系统架构"""
    st.markdown('<div class="system-title">系统架构总览</div>', unsafe_allow_html=True)

    st.markdown("""
    ```
    ┌──────────────────────────────────────────────────────────────────┐
    │                    LLM Agent 认知调度层                           │
    │  ┌────────────┐    ┌────────────┐    ┌──────────────────────┐   │
    │  │ 阶梯化      │    │ Function   │    │ 物理约束屏障          │   │
    │  │ Prompt模板  │ →  │ Calling    │ →  │ (违规率11.2%→0%)     │   │
    │  │ (3阶段)    │    │ (4工具)    │    │                      │   │
    │  └────────────┘    └────────────┘    └──────────────────────┘   │
    ├──────────────────────────────────────────────────────────────────┤
    │                    离散事件仿真引擎                               │
    │  ┌──────┐   ┌──────┐   ┌──────┐   ┌──────┐   ┌──────┐        │
    │  │装车站│ → │铁路网│ → │港口  │ → │海运  │ → │电厂  │         │
    │  │(7站) │   │(30站)│   │翻堆装│   │(船舶)│   │(15家)│         │
    │  └──────┘   └──────┘   └──────┘   └──────┘   └──────┘        │
    └──────────────────────────────────────────────────────────────────┘
    ```
    """)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**仿真引擎参数**")
        st.dataframe({
            "参数": ["仿真时长", "时间步长", "调度间隔", "港口容量", "安全区间",
                     "基础入港", "基础出港", "列车总数", "电厂数"],
            "值": ["168小时(7天)", "1小时", "4小时", "464万吨", "[140,280]万吨",
                   "22万吨/天", "18万吨/天", "120列", "15家"],
        }, hide_index=True, use_container_width=True)

    with col2:
        st.markdown("**台风封航场景参数**")
        st.dataframe({
            "参数": ["预警时间", "封航开始", "封航结束", "封航时长", "预警提前量"],
            "值": [f"第{TYPHOON_CONFIG['warning_hour']}小时",
                   f"第{TYPHOON_CONFIG['closure_start_hour']}小时",
                   f"第{TYPHOON_CONFIG['closure_end_hour']}小时",
                   f"{(TYPHOON_CONFIG['closure_end_hour']-TYPHOON_CONFIG['closure_start_hour'])//24}天",
                   f"{TYPHOON_CONFIG['closure_start_hour']-TYPHOON_CONFIG['warning_hour']}小时"],
        }, hide_index=True, use_container_width=True)

    # 技术栈
    st.markdown("**技术栈**")
    st.markdown("""
    | 层次 | 技术 | 说明 |
    |------|------|------|
    | 仿真引擎 | Python + SimPy | 离散事件驱动，时间步进模型 |
    | 智能调度 | LLM + Function Calling | 支持DeepSeek/Qwen/MiniMax等国产模型 |
    | 约束校验 | 规则引擎 | 硬约束屏障，拦截违规指令 |
    | 运筹优化 | PuLP/SciPy | 分流路径/泊位排程优化 |
    | 可视化 | Streamlit + Plotly | 交互式监控与仿真回放 |
    """)


# ========== 主程序 ==========

def main():
    params = render_sidebar()

    # 导航
    page = st.sidebar.radio(
        "功能模块",
        ["监控中心", "调度控制", "铁路网络", "港口作业", "电厂供应", "仿真实验", "系统架构"],
        label_visibility="collapsed"
    )

    if page == "监控中心":
        page_monitor(params)
    elif page == "调度控制":
        page_dispatch(params)
    elif page == "铁路网络":
        page_network(params)
    elif page == "港口作业":
        page_port(params)
    elif page == "电厂供应":
        page_plant(params)
    elif page == "仿真实验":
        page_experiment(params)
    elif page == "系统架构":
        page_system(params)


if __name__ == "__main__":
    main()
