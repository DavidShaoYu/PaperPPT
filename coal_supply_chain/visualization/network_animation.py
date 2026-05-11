"""2D铁路网络动态仿真动画 - 模拟TSimOP效果
展示列车在铁路网络上的动态运行，港口/电厂库存实时变化
"""
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# 简化铁路网络拓扑（基于论文实际线路）
STATIONS = {
    # 装车站（煤源）- 左侧
    "白音华东站": (0.05, 0.15),
    "霍林郭勒站": (0.08, 0.28),
    "伊图里河站": (0.06, 0.38),
    "扎兰淖尔站": (0.07, 0.33),
    "哈日努拉站": (0.04, 0.22),
    # 集运站
    "白音胡硕站": (0.18, 0.72),
    "新立屯站": (0.15, 0.58),
    "扎鲁特站": (0.20, 0.62),
    "车家窝棚站": (0.13, 0.50),
    "燕舞站": (0.08, 0.55),
    "西哲里木站": (0.08, 0.45),
    # 干线中间站
    "大林站": (0.35, 0.75),
    "五道木站": (0.35, 0.60),
    "钱家店站": (0.38, 0.68),
    "门达站": (0.38, 0.80),
    "白市站": (0.42, 0.85),
    "欧里站": (0.40, 0.90),
    "双辽站": (0.48, 0.90),
    # 主干线
    "通辽站": (0.30, 0.55),
    "甘旗卡站": (0.42, 0.55),
    "彰武站": (0.48, 0.65),
    "新立电站": (0.52, 0.58),
    "黑山站": (0.55, 0.65),
    "大虎山站": (0.52, 0.50),
    # 主干线下方
    "花吐古拉站": (0.28, 0.45),
    "双泡子站": (0.32, 0.45),
    "金宝图站": (0.36, 0.45),
    "水泉站": (0.40, 0.45),
    "遂辽站": (0.44, 0.45),
    # 港口入口
    "锦州港入口": (0.62, 0.40),
    "芳山堡站": (0.58, 0.38),
    # 港口
    "秦皇岛港": (0.75, 0.35),
    # 电厂
    "电厂群": (0.92, 0.35),
}

# 铁路连接（边）
RAIL_LINKS = [
    ("白音华东站", "哈日努拉站"), ("哈日努拉站", "霍林郭勒站"),
    ("霍林郭勒站", "扎兰淖尔站"), ("扎兰淖尔站", "伊图里河站"),
    ("霍林郭勒站", "白音胡硕站"), ("白音胡硕站", "大林站"),
    ("燕舞站", "车家窝棚站"), ("车家窝棚站", "新立屯站"),
    ("新立屯站", "扎鲁特站"), ("扎鲁特站", "白音胡硕站"),
    ("西哲里木站", "车家窝棚站"),
    ("新立屯站", "通辽站"), ("通辽站", "五道木站"),
    ("五道木站", "钱家店站"), ("钱家店站", "大林站"),
    ("大林站", "门达站"), ("门达站", "白市站"),
    ("白市站", "欧里站"), ("欧里站", "双辽站"),
    ("通辽站", "花吐古拉站"), ("花吐古拉站", "双泡子站"),
    ("双泡子站", "金宝图站"), ("金宝图站", "水泉站"),
    ("水泉站", "遂辽站"), ("遂辽站", "甘旗卡站"),
    ("甘旗卡站", "彰武站"), ("彰武站", "新立电站"),
    ("新立电站", "黑山站"), ("黑山站", "大虎山站"),
    ("大虎山站", "芳山堡站"), ("芳山堡站", "锦州港入口"),
    ("锦州港入口", "秦皇岛港"),
    ("双辽站", "彰武站"),
    # 港口到电厂（海运）
    ("秦皇岛港", "电厂群"),
]

# 主要运输路径（列车经过的站点序列）
MAIN_ROUTES = [
    ["白音华东站", "哈日努拉站", "霍林郭勒站", "白音胡硕站", "大林站",
     "钱家店站", "五道木站", "通辽站", "花吐古拉站", "双泡子站",
     "金宝图站", "水泉站", "遂辽站", "甘旗卡站", "彰武站",
     "新立电站", "黑山站", "大虎山站", "芳山堡站", "锦州港入口", "秦皇岛港"],
    ["燕舞站", "车家窝棚站", "新立屯站", "通辽站", "花吐古拉站",
     "双泡子站", "金宝图站", "水泉站", "遂辽站", "甘旗卡站",
     "彰武站", "新立电站", "黑山站", "大虎山站", "芳山堡站",
     "锦州港入口", "秦皇岛港"],
    ["伊图里河站", "扎兰淖尔站", "霍林郭勒站", "白音胡硕站",
     "大林站", "钱家店站", "五道木站", "通辽站", "花吐古拉站",
     "双泡子站", "金宝图站", "水泉站", "遂辽站", "甘旗卡站",
     "彰武站", "新立电站", "黑山站", "大虎山站", "芳山堡站",
     "锦州港入口", "秦皇岛港"],
]


def interpolate_position(route, progress):
    """在路径上根据进度(0-1)插值计算位置"""
    if progress <= 0:
        station = route[0]
        return STATIONS[station]
    if progress >= 1:
        station = route[-1]
        return STATIONS[station]

    total_segments = len(route) - 1
    segment_progress = progress * total_segments
    segment_idx = int(segment_progress)
    segment_idx = min(segment_idx, total_segments - 1)
    local_progress = segment_progress - segment_idx

    start = STATIONS[route[segment_idx]]
    end = STATIONS[route[segment_idx + 1]]

    x = start[0] + (end[0] - start[0]) * local_progress
    y = start[1] + (end[1] - start[1]) * local_progress
    return (x, y)


def generate_train_positions(num_trains, num_frames, hour_start, hour_end):
    """生成列车在每帧的位置
    列车沿路线往返运动：去程为重车(载煤)，回程为空车(返回装车)
    """
    np.random.seed(42)
    trains = []

    for i in range(num_trains):
        route_idx = i % len(MAIN_ROUTES)
        route = MAIN_ROUTES[route_idx]
        start_progress = np.random.uniform(0, 1.6)
        speed = np.random.uniform(0.006, 0.012)
        trains.append({
            "route": route,
            "start_progress": start_progress,
            "speed": speed,
        })

    frames_data = []
    for frame in range(num_frames):
        frame_trains = []
        for t in trains:
            raw_progress = t["start_progress"] + frame * t["speed"]
            cycle = raw_progress % 2.0
            if cycle <= 1.0:
                progress = cycle
                is_loaded = True
            else:
                progress = 2.0 - cycle
                is_loaded = False
            progress = max(0.0, min(1.0, progress))
            pos = interpolate_position(t["route"], progress)
            frame_trains.append({
                "x": pos[0], "y": pos[1],
                "loaded": is_loaded,
            })
        frames_data.append(frame_trains)

    return frames_data


def create_network_animation(metrics_b0, metrics_llm, strategy_name="大模型调度"):
    """创建完整的2D铁路网络动画"""
    num_frames = 42  # 168小时 / 4小时间隔
    num_trains = 25

    train_frames = generate_train_positions(num_trains, num_frames, 0, 168)

    # 创建基础图层
    fig = make_subplots(
        rows=2, cols=4,
        row_heights=[0.2, 0.8],
        column_widths=[0.25, 0.25, 0.25, 0.25],
        specs=[
            [{"type": "bar"}, {"type": "bar"}, {"type": "scatter"}, {"type": "scatter"}],
            [{"type": "scatter", "colspan": 4}, None, None, None],
        ],
        subplot_titles=["装车完成量（列）", "铁路运输量（万吨）",
                        "电厂实时库存（万吨）", "港口库存（万吨）",
                        ""],
    )

    # ---- 底图：铁路网络 ----
    # 绘制铁路连线
    for link in RAIL_LINKS:
        if link[0] in STATIONS and link[1] in STATIONS:
            x0, y0 = STATIONS[link[0]]
            x1, y1 = STATIONS[link[1]]
            is_sea = "电厂" in link[1]
            fig.add_trace(go.Scatter(
                x=[x0, x1], y=[y0, y1],
                mode="lines",
                line=dict(color="rgba(100,149,237,0.5)" if not is_sea else "rgba(0,128,255,0.3)",
                          width=2 if not is_sea else 1.5,
                          dash="solid" if not is_sea else "dash"),
                showlegend=False, hoverinfo="skip",
            ), row=2, col=1)

    # 绘制站点
    station_x = [pos[0] for pos in STATIONS.values()]
    station_y = [pos[1] for pos in STATIONS.values()]
    station_names = list(STATIONS.keys())

    # 分类站点颜色
    station_colors = []
    station_sizes = []
    for name in station_names:
        if "港" in name:
            station_colors.append("#e74c3c")
            station_sizes.append(14)
        elif "电厂" in name:
            station_colors.append("#2ecc71")
            station_sizes.append(14)
        elif name in ["白音华东站", "霍林郭勒站", "伊图里河站", "扎兰淖尔站", "哈日努拉站", "燕舞站", "西哲里木站"]:
            station_colors.append("#f39c12")
            station_sizes.append(8)
        else:
            station_colors.append("#e67e22")
            station_sizes.append(6)

    fig.add_trace(go.Scatter(
        x=station_x, y=station_y,
        mode="markers+text",
        marker=dict(size=station_sizes, color=station_colors,
                    line=dict(width=1, color="white")),
        text=station_names,
        textposition="bottom center",
        textfont=dict(size=7, color="#333"),
        showlegend=False,
        hovertemplate="%{text}<extra></extra>",
    ), row=2, col=1)

    # 初始帧列车位置
    initial_trains = train_frames[0]
    loaded_x = [t["x"] for t in initial_trains if t["loaded"]]
    loaded_y = [t["y"] for t in initial_trains if t["loaded"]]
    empty_x = [t["x"] for t in initial_trains if not t["loaded"]]
    empty_y = [t["y"] for t in initial_trains if not t["loaded"]]

    fig.add_trace(go.Scatter(
        x=loaded_x, y=loaded_y,
        mode="markers", name="重车(载煤)",
        marker=dict(size=9, color="#e74c3c", symbol="circle",
                    line=dict(width=1, color="darkred")),
    ), row=2, col=1)

    fig.add_trace(go.Scatter(
        x=empty_x, y=empty_y,
        mode="markers", name="空车(返回)",
        marker=dict(size=7, color="#2ecc71", symbol="circle",
                    line=dict(width=1, color="darkgreen")),
    ), row=2, col=1)

    # 初始KPI
    fig.add_trace(go.Bar(
        x=["动力煤", "特种煤"], y=[3, 1],
        marker_color=["#8B4513", "#2d5016"],
        showlegend=False,
    ), row=1, col=1)

    fig.add_trace(go.Bar(
        x=["动力煤", "特种煤"], y=[4, 0.8],
        marker_color=["#8B4513", "#2d5016"],
        showlegend=False,
    ), row=1, col=2)

    # 电厂库存折线
    plant_hours = list(range(0, min(4, len(metrics_llm.hourly_port_storage))))
    plant_stock_sample = [metrics_llm.plant_stock_history["PP00"][h] for h in plant_hours] if plant_hours else [0]
    fig.add_trace(go.Scatter(
        x=plant_hours, y=plant_stock_sample,
        mode="lines", line=dict(color="#2ecc71", width=2),
        showlegend=False,
    ), row=1, col=3)

    # 港口库存折线
    port_hours = list(range(0, min(4, len(metrics_llm.hourly_port_storage))))
    port_storage_sample = [metrics_llm.hourly_port_storage[h] for h in port_hours] if port_hours else [210]
    fig.add_trace(go.Scatter(
        x=port_hours, y=port_storage_sample,
        mode="lines+markers", line=dict(color="#3498db", width=2),
        fill="tozeroy", fillcolor="rgba(52,152,219,0.2)",
        showlegend=False,
    ), row=1, col=4)

    # ---- 创建动画帧 ----
    frames = []
    for frame_idx in range(num_frames):
        hour = frame_idx * 4
        frame_trains_data = train_frames[frame_idx]

        loaded_x = [t["x"] for t in frame_trains_data if t["loaded"]]
        loaded_y = [t["y"] for t in frame_trains_data if t["loaded"]]
        empty_x = [t["x"] for t in frame_trains_data if not t["loaded"]]
        empty_y = [t["y"] for t in frame_trains_data if not t["loaded"]]

        # KPI更新
        daily_loading = max(2, 5 - frame_idx * 0.05 + np.random.normal(0, 0.3))
        daily_special = max(0.5, 1.2 + np.random.normal(0, 0.1))

        # 电厂库存（到当前时刻）
        end_hour = min(hour + 4, len(metrics_llm.hourly_port_storage))
        plant_hours_f = list(range(0, end_hour))
        plant_stock_f = [metrics_llm.plant_stock_history["PP00"][h] for h in plant_hours_f] if plant_hours_f else [0]

        # 港口库存
        port_hours_f = list(range(0, end_hour))
        port_storage_f = [metrics_llm.hourly_port_storage[h] for h in port_hours_f] if port_hours_f else [210]

        frame = go.Frame(
            data=[
                # traces 0-N: rail links (skip, static)
                # 列车位置更新 - 需要知道trace index
                go.Scatter(x=loaded_x, y=loaded_y,
                           mode="markers",
                           marker=dict(size=9, color="#e74c3c", symbol="circle",
                                       line=dict(width=1, color="darkred"))),
                go.Scatter(x=empty_x, y=empty_y,
                           mode="markers",
                           marker=dict(size=7, color="#2ecc71", symbol="circle",
                                       line=dict(width=1, color="darkgreen"))),
                go.Bar(x=["动力煤", "特种煤"], y=[daily_loading, daily_special],
                       marker_color=["#8B4513", "#2d5016"]),
                go.Bar(x=["动力煤", "特种煤"], y=[daily_loading * 1.1, daily_special * 0.9],
                       marker_color=["#8B4513", "#2d5016"]),
                go.Scatter(x=plant_hours_f, y=plant_stock_f,
                           mode="lines", line=dict(color="#2ecc71", width=2)),
                go.Scatter(x=port_hours_f, y=port_storage_f,
                           mode="lines+markers", line=dict(color="#3498db", width=2),
                           fill="tozeroy", fillcolor="rgba(52,152,219,0.2)"),
            ],
            traces=[len(RAIL_LINKS) + 1, len(RAIL_LINKS) + 2,
                    len(RAIL_LINKS) + 3, len(RAIL_LINKS) + 4,
                    len(RAIL_LINKS) + 5, len(RAIL_LINKS) + 6],
            name=f"h{hour}",
        )
        frames.append(frame)

    fig.frames = frames

    # 播放控制按钮（多倍速）
    fig.update_layout(
        updatemenus=[
            dict(
                type="buttons",
                showactive=False,
                x=0.52, y=0.42,
                xanchor="center",
                direction="left",
                buttons=[
                    dict(label=" 0.5x ",
                         method="animate",
                         args=[None, {"frame": {"duration": 2000, "redraw": True},
                                      "fromcurrent": True,
                                      "transition": {"duration": 800}}]),
                    dict(label=" ▶ 1x ",
                         method="animate",
                         args=[None, {"frame": {"duration": 1000, "redraw": True},
                                      "fromcurrent": True,
                                      "transition": {"duration": 400}}]),
                    dict(label=" 2x ",
                         method="animate",
                         args=[None, {"frame": {"duration": 500, "redraw": True},
                                      "fromcurrent": True,
                                      "transition": {"duration": 200}}]),
                    dict(label=" ⏸ ",
                         method="animate",
                         args=[[None], {"frame": {"duration": 0, "redraw": False},
                                        "mode": "immediate",
                                        "transition": {"duration": 0}}]),
                ]
            )
        ],
        sliders=[dict(
            active=0,
            steps=[dict(args=[[f"h{i*4}"],
                               {"frame": {"duration": 1000, "redraw": True},
                                "mode": "immediate",
                                "transition": {"duration": 400}}],
                        label=f"第{i*4}h", method="animate")
                   for i in range(num_frames)],
            x=0.15, len=0.7,
            xanchor="left",
            y=0.38,
            currentvalue=dict(prefix="仿真时间: ", visible=True, xanchor="center"),
            transition=dict(duration=400),
        )],
    )

    # 布局美化
    fig.update_layout(
        height=800,
        title_text=f"煤炭供应链2D动态仿真 — {strategy_name}",
        title_x=0.5,
        margin=dict(l=30, r=30, t=60, b=30),
        plot_bgcolor="white",
    )

    # 网络图区域设置
    fig.update_xaxes(visible=False, range=[-0.02, 1.02], row=2, col=1)
    fig.update_yaxes(visible=False, range=[0.05, 0.98], row=2, col=1)

    # KPI子图设置
    fig.update_yaxes(range=[0, 6], row=1, col=1)
    fig.update_yaxes(range=[0, 7], row=1, col=2)
    fig.update_yaxes(range=[0, 0.35], row=1, col=3)
    fig.update_yaxes(range=[0, 350], row=1, col=4)

    return fig


def create_simple_network_animation(metrics_llm, closure_start=48, closure_end=120):
    """创建简化版网络动画（无subplot，更流畅）
    列车沿铁路线平滑运动，使用单一trace保证Plotly逐点插值
    """
    num_frames = 84
    num_trains = 30

    train_frames = generate_train_positions(num_trains, num_frames, 0, 168)

    fig = go.Figure()

    # 铁路连线
    for link in RAIL_LINKS:
        if link[0] in STATIONS and link[1] in STATIONS:
            x0, y0 = STATIONS[link[0]]
            x1, y1 = STATIONS[link[1]]
            is_sea = "电厂" in link[1]
            fig.add_trace(go.Scatter(
                x=[x0, x1], y=[y0, y1],
                mode="lines",
                line=dict(
                    color="rgba(65,105,225,0.6)" if not is_sea else "rgba(0,100,200,0.3)",
                    width=2.5 if not is_sea else 2,
                    dash="solid" if not is_sea else "dot"),
                showlegend=False, hoverinfo="skip",
            ))

    # 站点
    for name, (x, y) in STATIONS.items():
        if "港" in name:
            color, size, symbol = "#e74c3c", 18, "diamond"
        elif "电厂" in name:
            color, size, symbol = "#27ae60", 18, "star"
        elif name in ["白音华东站", "霍林郭勒站", "伊图里河站", "扎兰淖尔站",
                      "哈日努拉站", "燕舞站", "西哲里木站"]:
            color, size, symbol = "#f39c12", 10, "circle"
        else:
            color, size, symbol = "#e67e22", 7, "circle"

        fig.add_trace(go.Scatter(
            x=[x], y=[y], mode="markers+text",
            marker=dict(size=size, color=color, symbol=symbol,
                        line=dict(width=1.5, color="white")),
            text=[name.replace("站", "")], textposition="bottom center",
            textfont=dict(size=8, color="#444"),
            showlegend=False,
            hovertemplate=f"{name}<extra></extra>",
        ))

    # 列车使用单一trace（固定30个点），通过颜色数组区分重/空车
    # 这样Plotly按索引对每个点做位置插值，保证平滑沿线运动
    initial = train_frames[0]
    all_x = [t["x"] for t in initial]
    all_y = [t["y"] for t in initial]
    colors = ["#c0392b" if t["loaded"] else "#27ae60" for t in initial]

    train_trace_idx = len(fig.data)
    fig.add_trace(go.Scatter(
        x=all_x, y=all_y,
        mode="markers", name="运行列车",
        marker=dict(size=9, color=colors, symbol="circle",
                    line=dict(width=1.5, color="rgba(0,0,0,0.4)")),
    ))

    # 图例辅助trace（不参与动画，仅显示图例）
    fig.add_trace(go.Scatter(
        x=[None], y=[None], mode="markers", name="重车(载煤)",
        marker=dict(size=9, color="#c0392b", symbol="circle"),
    ))
    fig.add_trace(go.Scatter(
        x=[None], y=[None], mode="markers", name="空车(返回)",
        marker=dict(size=9, color="#27ae60", symbol="circle"),
    ))

    # 动画帧：每帧更新同一个trace的x/y/color
    frames = []
    for frame_idx in range(num_frames):
        hour = frame_idx * 2
        ft = train_frames[frame_idx]
        frame_x = [t["x"] for t in ft]
        frame_y = [t["y"] for t in ft]
        frame_colors = ["#c0392b" if t["loaded"] else "#27ae60" for t in ft]

        frames.append(go.Frame(
            data=[
                go.Scatter(x=frame_x, y=frame_y, mode="markers",
                           marker=dict(size=9, color=frame_colors, symbol="circle",
                                       line=dict(width=1.5, color="rgba(0,0,0,0.4)"))),
            ],
            traces=[train_trace_idx],
            name=f"h{hour}",
        ))

    fig.frames = frames

    # 播放按钮（多倍速）- transition设为0避免切角偏离轨道
    fig.update_layout(
        updatemenus=[dict(
            type="buttons", showactive=False,
            x=0.5, y=-0.03, xanchor="center",
            direction="left",
            buttons=[
                dict(label=" 0.5x ",
                     method="animate",
                     args=[None, {"frame": {"duration": 1000, "redraw": True},
                                  "fromcurrent": True,
                                  "transition": {"duration": 0}}]),
                dict(label=" ▶ 1x ",
                     method="animate",
                     args=[None, {"frame": {"duration": 500, "redraw": True},
                                  "fromcurrent": True,
                                  "transition": {"duration": 0}}]),
                dict(label=" 2x ",
                     method="animate",
                     args=[None, {"frame": {"duration": 250, "redraw": True},
                                  "fromcurrent": True,
                                  "transition": {"duration": 0}}]),
                dict(label=" ⏸ ",
                     method="animate",
                     args=[[None], {"frame": {"duration": 0, "redraw": False},
                                    "mode": "immediate"}]),
            ]
        )],
        sliders=[dict(
            active=0,
            steps=[dict(
                args=[[f"h{i*2}"], {"frame": {"duration": 500, "redraw": True},
                                     "mode": "immediate",
                                     "transition": {"duration": 0}}],
                label=f"{i*2}h" if i % 6 == 0 else "",
                method="animate")
                for i in range(num_frames)],
            x=0.1, len=0.8, xanchor="left", y=-0.08,
            currentvalue=dict(prefix="仿真时间: ", visible=True,
                              xanchor="center", font=dict(size=13)),
            transition=dict(duration=0),
        )],
    )

    # 阶段标注
    fig.add_annotation(x=0.75, y=0.92, text="🌀 台风预警 → 封航 → 恢复",
                       showarrow=False, font=dict(size=11, color="#555"),
                       xref="paper", yref="paper")

    # 图例
    fig.add_annotation(x=0.88, y=0.15, text="◆ 港口  ★ 电厂  ● 装车站",
                       showarrow=False, font=dict(size=9, color="#666"),
                       xref="paper", yref="paper")

    fig.update_layout(
        height=650,
        title=dict(text="煤炭供应链铁路网络动态仿真", x=0.5, font=dict(size=16)),
        xaxis=dict(visible=False, range=[-0.03, 1.05]),
        yaxis=dict(visible=False, range=[0.05, 0.98]),
        plot_bgcolor="#fafbfc",
        paper_bgcolor="white",
        legend=dict(x=0.82, y=0.08, bgcolor="rgba(255,255,255,0.8)",
                    bordercolor="#ddd", borderwidth=1),
        margin=dict(l=20, r=20, t=50, b=80),
    )

    return fig
