"""主入口 - 运行封航场景对比实验并生成可视化结果"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from simulation.engine import CoalSupplyChainSimulation
from baseline.manual_dispatch import manual_dispatch_strategy
from baseline.rule_dispatch import rule_dispatch_strategy
from agent.dispatcher import create_llm_strategy
from visualization.charts import plot_comparison_results


def run_experiment(use_real_llm: bool = False):
    """运行完整对比实验"""
    print("=" * 70)
    print("  一体化煤炭供应链建模仿真系统 - 封航场景对比实验")
    print("  基于大模型的智能调度 vs 传统人工调度")
    print("=" * 70)

    # 实验1：传统人工调度 (B0)
    print("\n[1/3] 运行传统人工调度 (B0 基线)...")
    sim_manual = CoalSupplyChainSimulation(
        dispatch_strategy=manual_dispatch_strategy,
        enable_typhoon=True, seed=42
    )
    metrics_manual = sim_manual.run()
    print(f"  → 港口库存峰值: {max(metrics_manual.hourly_port_storage):.1f} 万吨")
    print(f"  → 电厂断供: {sum(1 for v in metrics_manual.plant_interruptions.values() if v > 0)} 家")

    # 实验2：纯规则优化 (B1)
    print("\n[2/3] 运行纯规则优化调度 (B1)...")
    sim_rule = CoalSupplyChainSimulation(
        dispatch_strategy=rule_dispatch_strategy,
        enable_typhoon=True, seed=42
    )
    metrics_rule = sim_rule.run()
    print(f"  → 港口库存峰值: {max(metrics_rule.hourly_port_storage):.1f} 万吨")
    print(f"  → 电厂断供: {sum(1 for v in metrics_rule.plant_interruptions.values() if v > 0)} 家")

    # 实验3：大模型智能调度
    print("\n[3/3] 运行大模型智能调度...")
    llm_strategy = create_llm_strategy(use_real_llm=use_real_llm)
    sim_llm = CoalSupplyChainSimulation(
        dispatch_strategy=llm_strategy,
        enable_typhoon=True, seed=42
    )
    metrics_llm = sim_llm.run()
    agent = llm_strategy._agent
    print(f"  → 港口库存峰值: {max(metrics_llm.hourly_port_storage):.1f} 万吨")
    print(f"  → 电厂断供: {sum(1 for v in metrics_llm.plant_interruptions.values() if v > 0)} 家")
    print(f"  → 约束违规率: {agent.get_violation_rate():.1%}")

    # 汇总结果
    print("\n" + "=" * 70)
    print("  实验结果汇总")
    print("=" * 70)

    results = {
        "传统人工(B0)": metrics_manual,
        "规则优化(B1)": metrics_rule,
        "大模型调度": metrics_llm,
    }

    print(f"\n{'指标':<20} {'传统人工(B0)':<15} {'规则优化(B1)':<15} {'大模型调度':<15}")
    print("-" * 65)

    for name, m in results.items():
        peak = max(m.hourly_port_storage)
        interrupts = sum(1 for v in m.plant_interruptions.values() if v > 0)
        print(f"{'港口库存峰值(万吨)':<20} " if name == "传统人工(B0)" else "", end="")

    peak_manual = max(metrics_manual.hourly_port_storage)
    peak_rule = max(metrics_rule.hourly_port_storage)
    peak_llm = max(metrics_llm.hourly_port_storage)

    int_manual = sum(1 for v in metrics_manual.plant_interruptions.values() if v > 0)
    int_rule = sum(1 for v in metrics_rule.plant_interruptions.values() if v > 0)
    int_llm = sum(1 for v in metrics_llm.plant_interruptions.values() if v > 0)

    print(f"{'港口库存峰值(万吨)':<18} {peak_manual:<15.1f} {peak_rule:<15.1f} {peak_llm:<15.1f}")
    print(f"{'电厂断供数(家)':<18} {int_manual:<15d} {int_rule:<15d} {int_llm:<15d}")
    print(f"{'超安全线':<18} {'是' if peak_manual > 280 else '否':<15} {'是' if peak_rule > 280 else '否':<15} {'是' if peak_llm > 280 else '否':<15}")

    improvement = (peak_manual - peak_llm) / peak_manual * 100
    print(f"\n  库存峰值降低: {improvement:.1f}%")
    print(f"  电厂断供减少: {int_manual - int_llm} 家")

    # 生成对比图表
    print("\n正在生成对比图表...")
    plot_comparison_results(results)
    print("  → 图表已保存至 output/ 目录")

    return results


if __name__ == "__main__":
    use_real = "--real-llm" in sys.argv
    if use_real:
        print("使用真实大模型API（需要设置DEEPSEEK_API_KEY环境变量）")
    else:
        print("使用模拟大模型（无需API Key，适合演示）")

    run_experiment(use_real_llm=use_real)
