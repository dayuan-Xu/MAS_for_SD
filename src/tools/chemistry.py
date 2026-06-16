from chemicals import MW, Tb, Tm, Tc, Pc, Vc, Hfus, Hfl, Hfg, S0l, S0g, omega, search_chemical
from langchain_core.tools import tool
from thermo import ChemicalConstantsPackage, PRMIX, CEOSLiquid, CEOSGas, FlashPureVLS


@tool
def get_pure_component_properties(chemical_ID: str) -> str:
    """
    纯组分物性查询。
    :param chemical_ID: 以下格式的化学品标识符均可被解析：
        * 化学名称（IUPAC 命名法、常用名称或在 PubChem 中注册的别名），仅支持英文
        * InChI 名称（需添加前缀 'InChI=1S/' 或 'InChI=1/'）
        * InChI 键（需添加前缀 'InChIKey='）
        * PubChem CID（需添加前缀 'PubChem='）
        * SMILES 字符串（需添加前缀 'SMILES=' 以确保正确解析；例如 'C' 会被识别为碳元素，而 'SMILES=C' 才会被解析为甲烷）
        * CAS 号（已废弃的编号可能会指向当前有效编号）
    :return: 格式化后的物性文本
    """
    try:
        # 1. 获取CAS号
        res = search_chemical(chemical_ID)
        cas = res.CASs

        # 2. 获取化合物常用名称
        display_name = res.common_name + f"[IUPAC name: {res.iupac_name}]"

        # 3. 提取常用关键物性(化工高频使用项，带SI单位)
        props = {
            "分子量 MW (g/mol)": f"{MW(cas):.4f}" if MW(cas) else "无数据",
            "正常沸点 Tb (K)": f"{Tb(cas):.2f}" if Tb(cas) else "无数据",
            "熔点 Tm (K)": f"{Tm(cas):.2f}" if Tm(cas) else "无数据",
            "临界温度 Tc (K)": f"{Tc(cas):.2f}" if Tc(cas) else "无数据",
            "临界压力 Pc (Pa)": f"{Pc(cas):.2e}" if Pc(cas) else "无数据",
            "临界体积 Vc (m³/mol)": f"{Vc(cas):.6e}" if Vc(cas) else "无数据",
            "偏心因子 ω": f"{omega(cas):.4f}" if omega(cas) else "无数据",
            "熔化热 Hfus (J/mol)": f"{Hfus(cas):.2f}" if Hfus(cas) else "无数据",
            "液态生成热 Hfl (J/mol)": f"{Hfl(cas):.2f}" if Hfl(cas) else "无数据",
            "气态生成热 Hfg (J/mol)": f"{Hfg(cas):.2f}" if Hfg(cas) else "无数据",
            "液态绝对熵 S0l (J/mol/K)": f"{S0l(cas):.2f}" if S0l(cas) else "无数据",
            "气态绝对熵 S0g (J/mol/K)": f"{S0g(cas):.2f}" if S0g(cas) else "无数据"
        }

        # 4. 拼接成易读文本
        output_lines = [f"===== {display_name} 纯组分物性查询结果 ====="]
        for k, v in props.items():
            output_lines.append(f"{k}：{v}")
        return "\n".join(output_lines)

    except Exception as e:
        return f"get_pure_component_properties 执行异常：{str(e)}"


@tool
def pure_component_flash(chemical_ID: str, T: float, P: float) -> str:
    """
    纯组分闪蒸计算。
    基于 Peng-Robinson 状态方程进行严格的热力学闪蒸计算。
    :param chemical_ID: 以下格式的化学品标识符均可被解析：
        * 化学名称（IUPAC 命名法、常用名称或在 PubChem 中注册的别名），仅支持英文
        * InChI 名称（需添加前缀 'InChI=1S/' 或 'InChI=1/'）
        * InChI 键（需添加前缀 'InChIKey='）
        * PubChem CID（需添加前缀 'PubChem='）
        * SMILES 字符串（需添加前缀 'SMILES=' 以确保正确解析；例如 'C' 会被识别为碳元素，而 'SMILES=C' 才会被解析为甲烷）
        * CAS 号（已废弃的编号可能会指向当前有效编号）
    :param T: 温度，单位：开尔文 (K)
    :param P: 压力，单位：帕斯卡 (Pa)
    :return: 格式化后的闪蒸计算结果文本
    """
    try:
        # 1. 获取CAS号和化合物名称
        res = search_chemical(chemical_ID)
        cas = res.CASs
        if not cas:
            return f"未查询到【{chemical_ID}】对应的化学品,请检查输入的chemical_ID是否正确。"

        display_name = res.common_name + f"[IUPAC name: {res.iupac_name}]"

        # 2. 构建闪蒸对象
        try:
            constants, correlations = ChemicalConstantsPackage.from_IDs([cas])
        except Exception as e:
            return f"无法为【{display_name}】(CAS: {cas})加载热力学常数，该物质可能不在thermo数据库中。错误信息：{str(e)}"

        eos_kwargs = dict(Tcs=constants.Tcs, Pcs=constants.Pcs, omegas=constants.omegas)
        liquid = CEOSLiquid(PRMIX, HeatCapacityGases=correlations.HeatCapacityGases, eos_kwargs=eos_kwargs)
        gas = CEOSGas(PRMIX, HeatCapacityGases=correlations.HeatCapacityGases, eos_kwargs=eos_kwargs)
        flasher = FlashPureVLS(constants, correlations, gas=gas, liquids=[liquid], solids=[])

        # 3. 执行闪蒸计算
        try:
            flash_result = flasher.flash(T=T, P=P)
        except Exception as e:
            return f"闪蒸计算失败（T={T} K, P={P} Pa），可能是温度或压力超出有效范围。错误信息：{str(e)}"

        # 4. 提取关键热力学性质（带SI单位）
        results = {
            "----- 闪蒸计算条件 -----": "",
            "温度 T (K)": f"{T:.2f}",
            "压力 P (Pa)": f"{P:.2e}",
            "----- 相态信息 -----": "",
            "相态": "气液两相" if 0 < flash_result.VF < 1 else ("气相" if flash_result.VF >= 1 else "液相"),
            "气相分率 VF": f"{flash_result.VF:.6f}",
            "----- 摩尔性质 -----": "",
            "摩尔体积 V (m³/mol)": f"{flash_result.V():.6e}",
            "摩尔密度 ρ (mol/m³)": f"{flash_result.rho():.4f}",
            "摩尔焓 H (J/mol)": f"{flash_result.H():.2f}",
            "摩尔熵 S (J/(mol·K))": f"{flash_result.S():.4f}",
            "定压摩尔热容 Cp (J/(mol·K))": f"{flash_result.Cp():.4f}",
            "定容摩尔热容 Cv (J/(mol·K))": f"{flash_result.Cv():.4f}",
            "----- 质量性质 -----": "",
            "质量密度 ρ_mass (kg/m³)": f"{flash_result.rho_mass():.4f}",
            "质量焓 H_mass (J/kg)": f"{flash_result.H_mass():.2f}",
            "质量熵 S_mass (J/(kg·K))": f"{flash_result.S_mass():.4f}",
            "定压质量热容 Cp_mass (J/(kg·K))": f"{flash_result.Cp_mass():.4f}",
            "定容质量热容 Cv_mass (J/(kg·K))": f"{flash_result.Cv_mass():.4f}",
            "----- 其他性质 -----": "",
            "体膨胀系数 α (1/K)": f"{flash_result.isobaric_expansion():.6e}",
            "等温压缩系数 κ (1/Pa)": f"{flash_result.kappa():.6e}",
            "焦耳-汤姆逊系数 μ_JT (K/Pa)": f"{flash_result.Joule_Thomson():.6e}",
            "摩尔声速 c (m·kg^0.5/(s·mol^0.5))": f"{flash_result.speed_of_sound():.4f}",
            "质量声速 c_mass (m/s)": f"{flash_result.speed_of_sound_mass():.4f}"
        }

        # 5. 拼接成易读文本
        output_lines = [f"===== {display_name} 纯组分闪蒸计算结果 ====="]
        for k, v in results.items():
            if v == "":  # 分隔标题行
                output_lines.append(k)
            else:
                output_lines.append(f"{k}：{v}")

        return "\n".join(output_lines)

    except Exception as e:
        return f"pure_component_flash 执行异常：{str(e)}"


def test_get_pure_component_properties():
    # 测试示例：水和乙醇的 6 类标识符
    test_cases = {
        "水": [
            ("化学名称", "Water"),
            ("InChI", "InChI=1S/H2O/h1H2"),
            ("InChIKey", "InChIKey=XLYXNOZMOCQFTK-UHFFFAOYSA-N"),
            ("PubChem CID", "PubChem=962"),
            ("SMILES", "SMILES=O"),
            ("CAS", "7732-18-5")
        ],
        "乙醇": [
            ("化学名称", "Ethanol"),
            ("InChI", "InChI=1S/C2H6O/c1-2-3/h3H,2H,1H3"),
            ("InChIKey", "InChIKey=LFQSCWFLJHTTHZ-UHFFFAOYSA-N"),
            ("PubChem CID", "PubChem=702"),
            ("SMILES", "SMILES=CCO"),
            ("CAS", "64-17-5")
        ]
    }

    for compound_name, identifiers in test_cases.items():
        print(f"\n{'=' * 60}")
        print(f"测试化合物：{compound_name}")
        print(f"{'=' * 60}")

        for id_type, identifier in identifiers:
            print(f"\n(idtype, identifier) = ({id_type}, {identifier})")
            result = get_pure_component_properties.invoke(identifier)
            print(result)
            print("-" * 60)


def test_pure_component_flash():
    """测试纯组分闪蒸计算函数"""
    test_cases = [
        ("乙醇", "Ethanol", 351.44, 101325),  # 乙醇在沸点、常压下
        ("甲醇", "Methanol", 337.8, 101325),  # 甲醇在沸点、常压下
        ("苯", "Benzene", 353.25, 101325),  # 苯在沸点、常压下
    ]

    for compound_name, chemical_id, T, P in test_cases:
        result = pure_component_flash.invoke({"chemical_ID": chemical_id, "T": T, "P": P})
        print(result)
        print("-" * 60)


if __name__ == "__main__":
    # 运行测试
    print("测试1：纯组分物性查询")
    test_get_pure_component_properties()

    print("\n\n测试2：纯组分闪蒸计算")
    test_pure_component_flash()
