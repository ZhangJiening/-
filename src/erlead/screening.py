from __future__ import annotations
from dataclasses import asdict, dataclass
import math
from .optimization import validate_weights

ADMET_FIELDS = ("logS", "F_percent", "PPB_percent", "hepatotoxic", "CYP3A4_inhibitor")


@dataclass(frozen=True)
class Rules:
    activity_threshold: float = 6.0
    stage_weights: tuple = (0.40, 0.35, 0.25)
    reward: float = 0.0
    penalty: float = 0.0
    logs_min: float = -4.0
    logs_max: float = 0.0
    f_min: float = 30.0
    ppb_max: float = 95.0

    def validate(self):
        values = (self.activity_threshold, self.reward, self.penalty, self.logs_min, self.logs_max, self.f_min, self.ppb_max)
        if not all(math.isfinite(x) for x in values):
            raise ValueError("规则参数必须为有限数值")
        if not 6 <= self.activity_threshold <= 12:
            raise ValueError("活性门槛只能在6.0至12.0调整，保留6.0硬底线")
        validate_weights(self.stage_weights, 3)
        if not 0 <= self.reward <= 1 or not 0 <= self.penalty <= 1:
            raise ValueError("奖惩系数必须在0至1之间")
        if self.logs_min > self.logs_max or not 0 <= self.f_min <= 100 or not 0 <= self.ppb_max <= 100:
            raise ValueError("ADMET阈值范围无效")


def screen(pic50, rules=None, admet=None, structure=None, demo=False, evidence=None):
    rules = rules or Rules()
    rules.validate()
    if not math.isfinite(pic50):
        raise ValueError("活性预测值必须有限")
    if (admet is not None or structure is not None) and not demo and not str(evidence or "").strip():
        raise ValueError("真实阶段2/3输入必须提供可追溯证据说明；流程样例应选择演示模式")
    active = pic50 >= rules.activity_threshold
    stages = [{"stage": 1, "name": "活性", "input": {"pIC50": pic50},
               "criterion": f"pIC50 ≥ {rules.activity_threshold:g}（硬底线6.0）",
               "status": "通过" if active else "淘汰", "score": min(pic50 / 8, 1) if active else 0,
               "source": "真实活性回归模型"}]
    stage2 = {"stage": 2, "name": "ADMET", "input": admet, "criterion": "5项门槛；肝毒性/CYP3A4高风险为硬拦截",
              "status": "未评估", "score": None, "passed_count": None, "checks": None,
              "source": "演示数据" if demo and admet is not None else evidence if admet is not None else "缺少测量/模型数据"}
    if admet is not None:
        if set(admet) != set(ADMET_FIELDS):
            raise ValueError("ADMET输入必须完整包含5项指标，缺测请保留未评估")
        if not all(type(admet[k]) is bool for k in ("hepatotoxic", "CYP3A4_inhibitor")):
            raise ValueError("毒性/抑制标志必须为布尔值")
        if not all(isinstance(admet[k], (int, float)) and math.isfinite(admet[k]) for k in ADMET_FIELDS[:3]):
            raise ValueError("ADMET数值无效")
        if not all(0 <= admet[k] <= 100 for k in ("F_percent", "PPB_percent")):
            raise ValueError("F和PPB必须使用0至100的百分数")
        checks = {"logS": rules.logs_min <= admet["logS"] <= rules.logs_max,
                  "F_percent": admet["F_percent"] >= rules.f_min, "PPB_percent": admet["PPB_percent"] <= rules.ppb_max,
                  "hepatotoxic": not admet["hepatotoxic"], "CYP3A4_inhibitor": not admet["CYP3A4_inhibitor"]}
        fatal = not checks["hepatotoxic"] or not checks["CYP3A4_inhibitor"]
        stage2.update(status="淘汰" if fatal else "通过" if all(checks.values()) else "需复核",
                      score=0 if fatal else sum(checks.values()) / 5, passed_count=sum(checks.values()), checks=checks)
    stage3 = {"stage": 3, "name": "结构/理化", "input": structure, "criterion": "完整67项外部判定；本期不训练67输出模型",
              "status": "未评估", "score": None, "passed_count": None,
              "source": "演示数据" if demo and structure is not None else evidence if structure is not None else "缺少完整约束清单与数据"}
    if structure is not None:
        if len(structure) != 67 or not all(type(x) is bool for x in structure):
            raise ValueError("结构流程输入须为完整67项布尔判定，不能用部分项目冒充XX/67")
        count = sum(structure)
        stage3.update(status="通过" if count == 67 else "需复核", score=count / 67, passed_count=count)
    stages.extend([stage2, stage3])
    complete = all(s["score"] is not None for s in stages)
    hard_fail = not active or stage2["status"] == "淘汰"
    base, adjusted = None, None
    if complete:
        base = sum(w * s["score"] for w, s in zip(rules.stage_weights, stages))
        adjustment = rules.reward * base - rules.penalty * (1 - base)
        adjusted = min(1.0, max(0.0, base + adjustment))
    if hard_fail:
        conclusion = "淘汰：活性不达标" if not active else "淘汰：ADMET关键风险"
    elif not complete:
        conclusion = "活性达标；后续阶段未评估"
    elif any(s["status"] == "需复核" for s in stages):
        conclusion = "需复核：存在未达标约束"
    else:
        conclusion = "优先推荐候选（待实验验证）" if adjusted >= 0.8 else "可进一步评估" if adjusted >= 0.6 else "存在短板" if adjusted >= 0.4 else "不推荐"
    if demo and (admet is not None or structure is not None):
        conclusion = "【流程演示】" + conclusion
    for i, stage in enumerate(stages):
        stage["flow"] = "未放行" if any(s["status"] in ("淘汰", "未评估", "需复核") for s in stages[:i]) else "已到达"
    return {"stages": stages, "conclusion": conclusion, "complete": complete, "demo": demo,
            "base_score": base, "adjusted_score": adjusted, "rules": asdict(rules), "evidence": evidence,
            "score_label": "演示综合分（非科研结论）" if demo else "综合分",
            "reward_formula": "clip(base + reward*base - penalty*(1-base), 0, 1); hard elimination takes priority"}
