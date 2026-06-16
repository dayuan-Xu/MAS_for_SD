from langchain_core.tools import tool

"""
计算二元混合物气液平衡组成的工具:
- resolve_molecule: name/CAS → SMILES
- calculate_vapor_pressure: SMILES + T → Psat
- calculate_unifac_activity_coefficients: SMILES list + x + T → γ
- calculate_bubble_point: components + conditions → VLE result"
"""


@tool
def resolve_molecule(name: str):
    """
    输入分子名称，返回对应的SMILES表示
    """
    molecule_dict = {
        "乙醇": "CCO",
        "水": "O"
    }
    if name in molecule_dict:
        return molecule_dict[name]
    else:
        return f"未能找到{name}的SMILES表示"


@tool
def calculate_vapor_pressure(smiles: str, temperature_K: float):
    """
    输入SMILES表示和温度（K），返回对应的(纯组分)饱和蒸气压（Past_kPa）
    """
    if smiles == "CCO" and temperature_K == 351.52:
        return {
            "Past_kPa": 101.009
        }
    elif smiles == "O" and temperature_K == 351.52:
        return {
            "Past_kPa": 44.564
        }
    else:
        return f"未实现{smiles}在{temperature_K}K的饱和蒸气压计算"


@tool
def calculate_unifac_activity_coefficients(smiles_list: list[str], mole_fractions: list[float], temperature_K: float,
                                           model: str = "Dortmund"):
    """
    输入SMILES列表、（液相）摩尔分数列表和温度（K），返回对应的活度系数（γ）
    """
    if model != "Dortmund":
        return f"未实现{model}模型的活度系数计算"

    if smiles_list == ["CCO", "O"] and mole_fractions == [0.5, 0.5] and temperature_K == 351.52:
        return {
            "activity_coefficients": [1.371, 1.458]
        }
    else:
        return f"未实现{smiles_list}在{temperature_K}K的活度系数计算"


@tool
def calculate_bubble_point(smiles_list: list[str], liquid_mole_fractions: list[float], temperature_K: float,
                           pressure_kPa: float, thermo_model="UNIFAC_Dortmund",
                           calculation_type: str = "bubble_P_at_fixed_T"):
    """
    输入SMILES列表、（液相）摩尔分数列表、温度（K）、压力（kPa）、热力学模型（默认UNIFAC_Dortmund）和计算类型（默认bubble_P_at_fixed_T），返回对应的气泡平衡点（bubble point）
    """
    if thermo_model != "UNIFAC_Dortmund":
        return f"未实现{thermo_model}模型的气泡平衡点计算"
    if calculation_type != "bubble_P_at_fixed_T":
        return f"未实现{calculation_type}计算类型的气泡平衡点计算"

    if smiles_list == ["CCO", "O"] and liquid_mole_fractions == [0.5, 0.5] and temperature_K == 351.52:
        return {
            "converged": True,
            "vapor_mole_fractions": [0.681, 0.319],
            "bubble_pressure_kpa": 101.73,
            "activity_coefficients": [1.371, 1.458],
            "relative_volatility": 1.543
        }
    else:
        return f"未实现{smiles_list}在{liquid_mole_fractions}、{temperature_K}K下的气泡平衡点计算"
