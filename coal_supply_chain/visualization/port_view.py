"""港口内部Z层级视图 - 模拟TSimOP港区运作流程
展示：列车排队→翻车机卸车→堆场堆存→装船机→泊位装船→船舶离港
实现逐帧动画，体现物料从铁路侧到海运侧的全流程
"""
import numpy as np
import plotly.graph_objects as go


# 港口布局参数（从左到右：铁路侧 → 海运侧）
LAYOUT = {
    "rail_yard": {"x_range": (0.02, 0.15), "y_center": 0.5, "label": "到达场"},
    "dumpers": {"x_range": (0.18, 0.30), "y_center": 0.5, "label": "翻车机房"},
    "conveyors": {"x_range": (0.32, 0.42), "y_center": 0.5, "label": "皮带运输"},
    "stockyard": {"x_range": (0.44, 0.65), "y_center": 0.5, "label": "堆场"},
    "reclaimers": {"x_range": (0.67, 0.75), "y_center": 0.5, "label": "取料机"},
    "berths": {"x_range": (0.78, 0.98), "y_center": 0.5, "label": "泊位/装船"},
}

# 翻车机参数
DUMPER_POSITIONS = [
    {"id": f"CD{i+1}", "y": 0.15 + i * 0.058, "type": "large" if i >= 9 else "normal"}
    for i in range(13)
]

# 泊位参数
BERTH_POSITIONS = [
    {"id": f"B{i+1}", "y": 0.08 + i * 0.052}
    for i in range(17)
]


def create_port_cross_section(metrics_llm, frame_hour=0):
    """创建港口截面静态图（某一时刻快照）"""
    fig = go.Figure()

    # 背景区域划分
    zones = [
        (0.02, 0.15, "rgba(200,200,255,0.15)", "到达场\n(铁路入港)"),
        (0.18, 0.30, "rgba(255,200,200,0.15)", "翻车机房\n(13台)"),
        (0.32, 0.42, "rgba(200,255,200,0.1)", "皮带机\n(输送)"),
        (0.44, 0.65, "rgba(139,90,43,0.1)", "堆场\n(464万吨)"),
        (0.67, 0.75, "rgba(200,255,200,0.1)", "取料机\n(堆→船)"),
        (0.78, 0.98, "rgba(100,149,237,0.12)", "泊位区\n(17个)"),
    ]
    for x0, x1, color, label in zones:
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=0.02, y1=0.98,
                      fillcolor=color, line=dict(width=1, color="rgba(100,100,100,0.3)"))
        fig.add_annotation(x=(x0+x1)/2, y=0.99, text=label,
                          showarrow=False, font=dict(size=10, color="#555"),
                          xanchor="center", yanchor="bottom")

    # 翻车机
    for d in DUMPER_POSITIONS:
        x = 0.24
        y = d["y"]
        color = "#c0392b" if d["type"] == "large" else "#e74c3c"
        size = 12 if d["type"] == "large" else 9
        fig.add_trace(go.Scatter(
            x=[x], y=[y], mode="markers+text",
            marker=dict(size=size, color=color, symbol="square",
                        line=dict(width=1, color="darkred")),
            text=[d["id"]], textposition="middle left", textfont=dict(size=7),
            showlegend=False, hovertemplate=f"{d['id']}: {'大型' if d['type']=='large' else '标准'}翻车机<extra></extra>"
        ))

    # 泊位
    for b in BERTH_POSITIONS:
        x = 0.88
        y = b["y"]
        fig.add_trace(go.Scatter(
            x=[x], y=[y], mode="markers+text",
            marker=dict(size=8, color="#3498db", symbol="diamond",
                        line=dict(width=1, color="#2980b9")),
            text=[b["id"]], textposition="middle right", textfont=dict(size=7),
            showlegend=False, hovertemplate=f"泊位 {b['id']}<extra></extra>"
        ))

    # 堆场（煤堆形态）
    storage_ratio = metrics_llm.hourly_port_storage[min(frame_hour, len(metrics_llm.hourly_port_storage)-1)] / 464.0
    _draw_stockpiles(fig, storage_ratio)

    # 流程箭头
    arrow_y = 0.96
    arrows = [(0.15, 0.18), (0.30, 0.32), (0.42, 0.44), (0.65, 0.67), (0.75, 0.78)]
    for x0, x1 in arrows:
        fig.add_annotation(x=x1, y=arrow_y, ax=x0, ay=arrow_y,
                          arrowhead=2, arrowsize=1.2, arrowwidth=2,
                          arrowcolor="#888", showarrow=True)

    fig.update_layout(
        height=500,
        title=dict(text=f"港口内部作业流程截面图（第{frame_hour}小时）", x=0.5, font=dict(size=14)),
        xaxis=dict(visible=False, range=[0, 1]),
        yaxis=dict(visible=False, range=[0, 1.05]),
        plot_bgcolor="white",
        margin=dict(l=10, r=10, t=50, b=10),
    )

    return fig


def _draw_stockpiles(fig, ratio):
    """绘制煤堆（梯形/三角形堆积效果）"""
    num_piles = 6
    x_start, x_end = 0.46, 0.63
    pile_width = (x_end - x_start) / num_piles

    for i in range(num_piles):
        cx = x_start + (i + 0.5) * pile_width
        height = ratio * 0.35 * (0.7 + 0.3 * np.sin(i * 1.5))
        half_base = pile_width * 0.4
        half_top = half_base * 0.3

        # 梯形煤堆
        xs = [cx - half_base, cx - half_top, cx + half_top, cx + half_base, cx - half_base]
        ys_base = 0.35
        ys = [ys_base, ys_base + height, ys_base + height, ys_base, ys_base]

        fig.add_trace(go.Scatter(
            x=xs, y=ys, fill="toself",
            fillcolor=f"rgba(60,40,20,{0.5 + ratio*0.4})",
            line=dict(color="rgba(40,20,10,0.7)", width=1),
            showlegend=False, hoverinfo="skip"
        ))


def create_port_animation(metrics_llm, closure_start=48, closure_end=120):
    """创建港口动态运作动画
    展示列车→翻车→堆场→装船全流程动态
    动画数据来源于仿真metrics的实际inflow/outflow/storage
    """
    num_frames = 42  # 168h / 4h = 42 frames
    np.random.seed(42)

    fig = go.Figure()

    # 静态底图：区域划分
    zones = [
        (0.02, 0.15, "rgba(200,200,255,0.12)", "到达场"),
        (0.18, 0.30, "rgba(255,200,200,0.12)", "翻车机房"),
        (0.32, 0.42, "rgba(200,255,200,0.08)", "皮带输送"),
        (0.44, 0.65, "rgba(139,90,43,0.08)", "堆场(464万吨)"),
        (0.67, 0.75, "rgba(200,255,200,0.08)", "取料"),
        (0.78, 0.98, "rgba(100,149,237,0.10)", "泊位(17个)"),
    ]
    for x0, x1, color, label in zones:
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=0.02, y1=0.95,
                      fillcolor=color, line=dict(width=0.5, color="rgba(150,150,150,0.4)"))
        fig.add_annotation(x=(x0+x1)/2, y=0.97, text=label,
                          showarrow=False, font=dict(size=9, color="#666"))

    # 翻车机固定位置标记
    for d in DUMPER_POSITIONS:
        fig.add_trace(go.Scatter(
            x=[0.24], y=[d["y"]], mode="markers",
            marker=dict(size=7, color="#bbb", symbol="square",
                        line=dict(width=0.5, color="#999")),
            showlegend=False, hoverinfo="skip"
        ))

    # 泊位固定位置标记
    for b in BERTH_POSITIONS:
        fig.add_trace(go.Scatter(
            x=[0.88], y=[b["y"]], mode="markers",
            marker=dict(size=6, color="#bbb", symbol="diamond",
                        line=dict(width=0.5, color="#999")),
            showlegend=False, hoverinfo="skip"
        ))

    # 动态元素初始trace placeholders
    # trace idx for dynamic elements: trains_arriving, trains_unloading, coal_flow, ships
    base_trace_count = len(fig.data)

    # 列车（到达场排队）
    fig.add_trace(go.Scatter(
        x=[], y=[], mode="markers", name="排队列车",
        marker=dict(size=10, color="#8B4513", symbol="square",
                    line=dict(width=1, color="#5D2E0C")),
    ))
    trains_trace_idx = base_trace_count

    # 正在翻车的列车
    fig.add_trace(go.Scatter(
        x=[], y=[], mode="markers", name="翻车作业",
        marker=dict(size=9, color="#e74c3c", symbol="square",
                    line=dict(width=1.5, color="#c0392b")),
    ))
    unloading_trace_idx = base_trace_count + 1

    # 煤流（皮带上的物料）
    fig.add_trace(go.Scatter(
        x=[], y=[], mode="markers", name="煤流(皮带)",
        marker=dict(size=5, color="#4a3000", symbol="circle"),
    ))
    coal_flow_trace_idx = base_trace_count + 2

    # 船舶（泊位停靠）
    fig.add_trace(go.Scatter(
        x=[], y=[], mode="markers", name="在泊船舶",
        marker=dict(size=14, color="#2980b9", symbol="triangle-right",
                    line=dict(width=1, color="#1a5276")),
    ))
    ships_trace_idx = base_trace_count + 3

    # 堆场库存指示条
    fig.add_trace(go.Scatter(
        x=[], y=[], mode="lines", name="库存水位",
        line=dict(color="rgba(139,69,19,0.7)", width=3),
        fill="tozeroy", fillcolor="rgba(139,90,43,0.3)",
    ))
    stock_trace_idx = base_trace_count + 4

    # KPI文字
    fig.add_trace(go.Scatter(
        x=[0.54], y=[0.06], mode="text", name="KPI",
        text=[""], textfont=dict(size=11, color="#333"),
        showlegend=False
    ))
    kpi_trace_idx = base_trace_count + 5

    # 生成动画帧 - 基于实际仿真数据
    frames = []
    for frame_idx in range(num_frames):
        hour = frame_idx * 4
        storage = metrics_llm.hourly_port_storage[min(hour, len(metrics_llm.hourly_port_storage)-1)]
        storage_ratio = storage / 464.0

        # 封航判断：基于传入的实际封航参数
        is_closed = (closure_start <= hour < closure_end)

        # 到达场列车数：基于实际入港流量
        hourly_inflow = metrics_llm.hourly_inflow[min(hour, len(metrics_llm.hourly_inflow)-1)]
        # 入港流量映射到列车数（22万吨/天≈45列/天≈1.9列/小时→~8列在场）
        base_trains = max(1, int(hourly_inflow * 24 / 22 * 8 + np.random.normal(0, 1)))
        num_arriving = min(12, max(1, base_trains))
        train_x = [0.05 + np.random.uniform(0, 0.08) for _ in range(num_arriving)]
        train_y = [0.15 + i * 0.065 for i in range(num_arriving)]

        # 翻车作业：活跃数与入港流量正相关
        active_dumpers = min(13, max(2, int(num_arriving * 1.1 + np.random.randint(-1, 2))))
        active_idx = np.random.choice(13, active_dumpers, replace=False)
        unload_x = [0.24] * active_dumpers
        unload_y = [DUMPER_POSITIONS[i]["y"] for i in active_idx]

        # 皮带上的煤流粒子
        num_particles = int(active_dumpers * 2.5)
        coal_x = [np.random.uniform(0.32, 0.42) for _ in range(num_particles)]
        coal_y = [np.random.uniform(0.35, 0.65) for _ in range(num_particles)]

        # 在泊船舶：基于实际出港流量
        hourly_outflow = metrics_llm.hourly_outflow[min(hour, len(metrics_llm.hourly_outflow)-1)]
        if is_closed:
            num_ships = 0
        else:
            # 出港流量映射到在泊船数（18万吨/天正常≈5-6艘在泊）
            num_ships = min(12, max(0, int(hourly_outflow * 24 / 18 * 5 + np.random.normal(0, 1))))
        ship_berths = np.random.choice(17, min(num_ships, 17), replace=False) if num_ships > 0 else []
        ship_x = [0.92] * len(ship_berths)
        ship_y = [BERTH_POSITIONS[i]["y"] for i in ship_berths]

        # 堆场库存水位线：直接来自仿真数据
        stock_x = [0.44, 0.46, 0.50, 0.54, 0.58, 0.62, 0.65]
        stock_y = [0.3 + storage_ratio * 0.35 * (0.8 + 0.2 * np.sin(x * 20))
                   for x in stock_x]

        # KPI文本
        status_text = "🔴 封航中" if is_closed else "🟢 正常运营"
        kpi = f"第{hour}h | 库存:{storage:.0f}万吨({storage_ratio*100:.0f}%) | {status_text}"

        frame = go.Frame(
            data=[
                go.Scatter(x=train_x, y=train_y, mode="markers",
                           marker=dict(size=10, color="#8B4513", symbol="square",
                                       line=dict(width=1, color="#5D2E0C"))),
                go.Scatter(x=unload_x, y=unload_y, mode="markers",
                           marker=dict(size=9, color="#e74c3c", symbol="square",
                                       line=dict(width=1.5, color="#c0392b"))),
                go.Scatter(x=coal_x, y=coal_y, mode="markers",
                           marker=dict(size=5, color="#4a3000", symbol="circle")),
                go.Scatter(x=ship_x, y=ship_y, mode="markers",
                           marker=dict(size=14, color="#2980b9", symbol="triangle-right",
                                       line=dict(width=1, color="#1a5276"))),
                go.Scatter(x=stock_x, y=stock_y, mode="lines",
                           line=dict(color="rgba(139,69,19,0.7)", width=3),
                           fill="tozeroy", fillcolor="rgba(139,90,43,0.3)"),
                go.Scatter(x=[0.54], y=[0.06], mode="text",
                           text=[kpi], textfont=dict(size=11, color="#333")),
            ],
            traces=[trains_trace_idx, unloading_trace_idx, coal_flow_trace_idx,
                    ships_trace_idx, stock_trace_idx, kpi_trace_idx],
            name=f"h{hour}",
        )
        frames.append(frame)

    fig.frames = frames

    # 播放控制
    fig.update_layout(
        updatemenus=[dict(
            type="buttons", showactive=False,
            x=0.5, y=-0.02, xanchor="center",
            buttons=[
                dict(label="  ▶ 播放  ",
                     method="animate",
                     args=[None, {"frame": {"duration": 400, "redraw": True},
                                  "fromcurrent": True,
                                  "transition": {"duration": 150}}]),
                dict(label="  ⏸ 暂停  ",
                     method="animate",
                     args=[[None], {"frame": {"duration": 0, "redraw": False},
                                    "mode": "immediate"}]),
            ]
        )],
        sliders=[dict(
            active=0,
            steps=[dict(
                args=[[f"h{i*4}"], {"frame": {"duration": 400, "redraw": True},
                                     "mode": "immediate"}],
                label=f"{i*4}h" if i % 4 == 0 else "",
                method="animate")
                for i in range(num_frames)],
            x=0.08, len=0.84, xanchor="left", y=-0.06,
            currentvalue=dict(prefix="仿真时间: ", visible=True,
                              xanchor="center", font=dict(size=12)),
            transition=dict(duration=150),
        )],
    )

    fig.update_layout(
        height=550,
        title=dict(text="港口内部作业动态仿真（Z层级视图）", x=0.5, font=dict(size=14)),
        xaxis=dict(visible=False, range=[-0.01, 1.01]),
        yaxis=dict(visible=False, range=[-0.02, 1.05]),
        plot_bgcolor="#fafbfc",
        paper_bgcolor="white",
        legend=dict(x=0.01, y=0.12, bgcolor="rgba(255,255,255,0.85)",
                    bordercolor="#ddd", borderwidth=1, font=dict(size=9)),
        margin=dict(l=10, r=10, t=50, b=70),
    )

    return fig


def create_port_sankey(metrics_llm, hour=72):
    """创建港口物流桑基图 - 展示煤炭流向"""
    storage = metrics_llm.hourly_port_storage[min(hour, len(metrics_llm.hourly_port_storage)-1)]

    # 节点
    labels = [
        "铁路入港(22万吨/天)",  # 0
        "翻车机卸车",            # 1
        "皮带输送",              # 2
        "动力煤堆场",            # 3
        "特种煤堆场",            # 4
        "取料机取煤",            # 5
        "装船机装船",            # 6
        "大型船(≥7万吨)",       # 7
        "中型船(3-7万吨)",      # 8
        "小型船(<3万吨)",       # 9
        "华南电厂群",            # 10
        "华东电厂群",            # 11
        "华北电厂群",            # 12
    ]

    colors = [
        "#8B4513", "#e74c3c", "#f39c12", "#8B6914", "#2d5016",
        "#f39c12", "#3498db", "#2980b9", "#1abc9c", "#16a085",
        "#27ae60", "#2ecc71", "#52be80"
    ]

    # 流量关系 (source, target, value)
    inflow = 22.0
    links = [
        (0, 1, inflow * 0.85),        # 铁路→翻车机（大部分）
        (0, 1, inflow * 0.15),        # 铁路→翻车机（特种煤）
        (1, 2, inflow * 0.95),        # 翻车→皮带
        (2, 3, inflow * 0.75),        # 皮带→动力煤堆
        (2, 4, inflow * 0.20),        # 皮带→特种煤堆
        (3, 5, 15.0),                 # 动力煤堆→取料
        (4, 5, 3.0),                  # 特种煤堆→取料
        (5, 6, 18.0),                 # 取料→装船
        (6, 7, 8.0),                  # 装船→大船
        (6, 8, 7.0),                  # 装船→中船
        (6, 9, 3.0),                  # 装船→小船
        (7, 10, 8.0),                 # 大船→华南
        (8, 11, 7.0),                 # 中船→华东
        (9, 12, 3.0),                 # 小船→华北
    ]

    fig = go.Figure(go.Sankey(
        node=dict(
            pad=15, thickness=20,
            line=dict(color="rgba(0,0,0,0.3)", width=0.5),
            label=labels, color=colors
        ),
        link=dict(
            source=[l[0] for l in links],
            target=[l[1] for l in links],
            value=[l[2] for l in links],
            color=[f"rgba({int(c[1:3],16)},{int(c[3:5],16)},{int(c[5:7],16)},0.3)"
                   for c in [colors[l[0]] for l in links]]
        )
    ))

    fig.update_layout(
        title=dict(text=f"港口煤炭物流桑基图（日均流量，万吨/天）", x=0.5, font=dict(size=14)),
        height=450,
        margin=dict(l=20, r=20, t=50, b=20),
    )

    return fig
