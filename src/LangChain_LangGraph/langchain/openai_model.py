from langchain_openai import ChatOpenAI
from rich.pretty import pprint
from src.config.llm import LLMs
from src.config.settings import settings

reasoning = {
    "effort": "medium",  # 'low', 'medium', or 'high'
    "summary": "auto",  # 'detailed', 'auto', or None
}

model = ChatOpenAI(
    model=LLMs["gpt-5-nano"], reasoning=reasoning,
    output_version="responses/v1",
    base_url=settings.OPENAI_BASE_URL,
)
response = model.invoke("如何正确使用chatgpt做毕设?")
pprint(response)

# Response text
print(f"Output: {response.text}")

# Reasoning summaries
for block in response.content:
    if block["type"] == "reasoning":
        for summary in block["summary"]:
            print(summary["text"])


"""
AIMessage(
│   content=[
│   │   {
│   │   │   'id': 'rs_02224eeba87b90ea0069b7aef715f88197959bd7d037296c4e',
│   │   │   'summary': [
│   │   │   │   {
│   │   │   │   │   'text': "**Outlining do's and don'ts for AI usage**\n\nI’m considering a list of do's and don'ts for using AI as a resource. For the do's, I think using it for brainstorming, structure, language editing, and generating outlines would be beneficial. On the don't side, I should emphasize not using AI to bypass proper research, relying on it for credible facts, or avoiding citations. I can also suggest setting guardrails for content quality, providing disclaimers, and discussing what to do if an advisor prohibits AI usage, perhaps with example scenarios.",
│   │   │   │   │   'type': 'summary_text'
│   │   │   │   },
│   │   │   │   {
│   │   │   │   │   'text': "**Demonstrating prompts for outlines**\n\nI’m thinking about providing a step-by-step demonstration on creating outlines and sample content, specifically tailored for various disciplines. To meet the user’s request accurately, I’ll include example prompts in Chinese that can easily adapt across fields. I want to ensure we maintain disclaimers and avoid any potentially plagiarized content. I'll incorporate quick guidelines like confirming with an advisor about AI usage policies, present an actionable workflow, and offer checklists, bullet lists, and templates for literature reviews and research methods. It should be useful and engaging!",
│   │   │   │   │   'type': 'summary_text'
│   │   │   │   },
│   │   │   │   {
│   │   │   │   │   'text': "**Emphasizing ethics in AI usage**\n\nI want to ensure that I'm not encouraging any form of cheating and instead emphasizing the importance of ethics. I'll mention features like summarizing, translation, rewriting, and code debugging, but I need to be careful about the risks, like potentially generating text that might pass as original work. I’ll start with a direct answer about maintaining academic integrity and follow up with core principles. I'll emphasize using AI as a tool, verifying facts, and citing sources while providing a phased guide to effectively use AI without compromising ethics.",
│   │   │   │   │   'type': 'summary_text'
│   │   │   │   },
│   │   │   │   {
│   │   │   │   │   'text': "**Creating a structured guide for research**\n\nI’m outlining a structured guide for research that starts with clarifying the institutional policy. Then, Step 1 involves selecting a topic with prompts and guidelines to assess feasibility. For Step 2, I’ll provide prompts for creating an annotated bibliography and tips for summarization. Step 3 will focus on formulating research questions. Steps 4 through 10 will include everything from analyzing data, drafting, language polishing, citation management, self-checking for plagiarism, to preparing for advisor reviews. I'll ensure the content remains ethical and clear throughout!",
│   │   │   │   │   'type': 'summary_text'
│   │   │   │   }
│   │   │   ],
│   │   │   'type': 'reasoning'
│   │   },
│   │   {
│   │   │   'type': 'text',
│   │   │   'text': '可以。以下给出一个实用、负责的使用思路，帮助你在本科毕设中把 ChatGPT 用好、用对，既提升效率，又尽量避免学术不端或内容质量问题。你也可以把其中的要点按你的专业和院校要求做调整。\n\n一、使用前的底线与原则\n- 先了解学校和导师的 AI 使用政策，明确允许范围、需要披露的情况（例如在致谢、方法论部分的 AI 助力说明）。\n- 把 ChatGPT 视为辅助工具，而非“替代作者”。对任何关键结论、数据、代码和图表都要亲自核实、可重复、可溯源。\n- 内容要有你自己的独立分析和原创贡献。用 AI 生成的文字要经你润色、改写并融入自己的观点，避免照抄照搬。\n- 注重来源可验证性。AI 可以帮助梳理文献、提取要点，但引用必须来自真实的、可检索的原始文献，且要严格按学校要求的引文格式处理。\n\n二、一个可执行的工作流程（分阶段要点与实用 prompts）\n阶段1：明确选题和研究问题\n- 目标：确定可行、具有学术价值的研究题目与问题。\n- 如何用 ChatGPT：用来头脑风暴、筛选方向、初步评估可行性，但最终确定仍需要你和导师确认。\n- 可用 prompts（示例，按你专业可改写）：\n  - “我在学习[领域名]，想找一个本科毕设的研究方向。请给出10个可行的研究题目，并简要说明每个题目的研究意义、数据/实验可行性和潜在难点。”\n  - “请结合当前[领域热点，如‘深度学习在医学影像中的应用’]，给出前5个可行的具体题目，并按‘创新性、可行性、数据可得性’排序，给出理由。”\n  - “请帮我把主题从‘描述性分析’扩展为‘因果/对比实验’的研究思路，给出至少3种可执行设计并标注优缺点。”\n阶段2：文献综述初步整理\n- 目标：建立领域脉络、确定研究缺口、形成初步综述结构。\n- 如何用 ChatGPT：用它来整理文献清单、提炼核心观点和对比点，但每条观点都要你手动核对原文、保留引用。\n- 可用 prompts：\n  - “以下是我计划研究方向的关键词，请给出一个文献检索思路和至少8篇核心文献的简要要点摘要（不要直接抄写原文），并列出每篇文献的研究问题、方法、主要结论和缺口。”\n  - “请基于以上文献，给出一份文献综述的段落结构大纲，包含研究领域的演变、主要观点分歧、常用方法、尚存的研究空缺，以及你拟开展研究的定位。”\n  - 将你已有的参考文献清单整理成统一的摘要表格，列出：作者、年份、研究问题、方法、数据来源、主要结论、局限性。你可以让 ChatGPT 先给出大纲，再让你逐条填充与核对。\n阶段3：研究设计与方法\n- 目标：构建清晰、可执行的研究设计（理论或实验/实证）。\n- 如何用 ChatGPT：获取方法学思路、变量定义、数据分析方案的初稿；但你要据实填充具体细节和数据来源。\n- 可用 prompts：\n  - “请给出一个适合[领域/题目]的研究设计草案，包含研究问题、变量定义、假设、数据来源、样本量/样本选择、分析方法、评估指标、潜在偏差与局限。”\n  - “请给出一个对照实验的流程设计，包含实验组/对照组的分配、数据收集时间点、伦理考量、数据分析路径、预期结果與风险控制。”\n阶段4：数据准备与分析（如有数据）\n- 目标：规范数据获取、清洗、分析流程，确保可复现。\n- 如何用 ChatGPT：生成代码草稿、分析步骤、可视化方案的初稿；但实际数据处理要你来执行和验证。\n- 可用 prompts（Python/R 示例）：\n  - “请给出一个Python数据清洗脚本骨架，读取CSV，处理缺失值，规范数据类型，生成描述性统计变量，并输出一个简要报告。”\n  - “请给出一个R语言的线性回归分析流程，包含数据准备、模型拟合、诊断检查、结果解释和可视化代码。”\n- 提醒：ChatGPT 不能直接运行你的数据，生成的代码需要你在本地环境测试、调试、确保正确性和可重复性。\n阶段5：初稿撰写（结构与表达）\n- 目标：搭建论文骨架，初步把研究思路、方法、结果写成文本。\n- 如何用 ChatGPT：用来生成章节大纲、段落初稿或润色；最终文本要你亲自确认、增删、改写为自己的语言风格。\n- 可用 prompts：\n  - “请帮我把以下研究问题与假设，转成论文的‘引言’段落，语言风格保持正式、学术、逻辑清晰。请给出一个4–6段的结构，但不要包含具体数据，仅描述研究动机与研究意义。”\n  - “请给出‘研究方法’章节的草稿，包含研究设计、数据来源、变量、分析方法、伦理/合规说明等要点。”\n  - “请根据下面的结果要点，撰写‘结果’章节的描述性文字，包含1–2处关键发现的解释性句子和一个简短的结论性段落。” \n阶段6：语言润色与格式规范\n- 目标：确保论文语言正式、逻辑清晰、符合学术规范的排版与引用风格。\n- 如何用 ChatGPT：用于润色、改写、统一术语、检查段落衔接；严格按学校的引用风格统一引用格式。\n- 可用 prompts：\n  - “请将以下中文段落改写为学术中文，保持原意但增强逻辑性、用词正式、避免口语化，并保持字数在±15%内。”\n  - “请把以下参考文献列表按 GB/T 7714 风格整理成规范的参考文献条目，并给出对应的 BibTeX/EndNote/Word 引用格式。” \n  - “请检查下列文本的论证结构，并给出改进建议（如段落顺序、论证逻辑、过渡句、重复表述的去除等）。”\n阶段7：引用管理与伦理披露\n- 目标：确保引用准确、避免抄袭、透明披露 AI 使用情况。\n- 如何用 ChatGPT：帮助整理引用格式、生成引文草稿，但不要把 AI 生成的文本直接当作引用来源；对事实性断言要以原始文献为准。\n- 可用 prompts：\n  - “请把下列参考文献列表整理成APA/GB/T 7714 引用风格，并给出每条的 DOI/URL（若有）。” \n  - “请帮我写一段致谢/方法说明，说明在本研究中使用了 AI 辅助写作工具（如 ChatGPT），并阐述使用范围与局限。”\n阶段8：自检与导师评阅准备\n- 目标：自我检查、准备给导师的版本、模拟答辩要点。\n- 如何用 ChatGPT：生成自检清单、常见问题答辩要点、可能的疑问及回答要点。\n- 可用 prompts：\n  - “请给出一份本科毕设的自我检查清单，覆盖创新性、可重复性、数据/方法透明性、语言表达、图表与表格清晰度、引用一致性等方面。”\n  - “请基于以下研究问题，列出导师可能提出的5个核心质疑，以及对应的要点式回答思路。”\n阶段9：防守与提交\n- 目标：顺利完成论文提交与答辩准备。\n- 如何用 ChatGPT：帮助整理答辩提纲、口头报告要点、PPT 结构与图表说明，但不要代替你对研究的理解与阐释。\n- 可用 prompts：\n  - “请给出一个5–7页的答辩PPT提纲，包含研究背景、问题、方法、主要结果、结论、局限与未来工作、以及可展示的关键图表说明。”\n  - “请帮我把以下论文要点转成答辩主持人可能问的问题及简短回答要点。”\n\n三、写作中的要点与注意事项\n- 保有原创性：AI 可以提供结构、表述、语言润色，但核心观点、数据分析的结论、设计思路等要由你独立完成并清晰标注来源。\n- 验证与可追溯性：对每条重要结论尽量给出原始文献或数据来源，避免“AI 提供的结论”成为你论文中的唯一依据。\n- 学术语言与风格：中文学术写作通常更注重逻辑性和简练性，避免口语、重复表达，确保段落之间的连贯过渡。\n- 数据与隐私：如果使用公开数据集、机构内部数据或涉及个人信息，遵循伦理规范与数据保护要求，避免在公开版本中泄露敏感信息。\n- 文献管理：建立一个统一的文献管理流程（如 Zotero/MZ、EndNote、Mendeley），并确保文献引用和参考文献清单的一致性。\n- 审稿式自查：在提交前进行自查（自我检测清单），并请导师在提交前进行评阅，确保排版、图表、引用等符合学校要求。\n\n四、易用的中文示例模板（你可直接修改使用）\n- 引言段落模板（示例）\n  请用正式学术中文撰写以下内容的引言：研究背景、研究动机、研究问题或假设、研究意义、论文结构安排。请保持逻辑清晰、语言正式、字数控制在600–800字。\n\n- 研究方法段落模板（示例）\n  请用正式中文撰写以下研究设计的“研究方法”部分，包含研究问题、变量定义、数据来源、样本与抽样、分析方法、指标体系、伦理与局限。尽量做到条理清晰、可重复。\n\n- 结果描述段落模板（示例）\n  请用正式中文描述以下研究结果，先给出总体结论，再逐条展开关键发现，避免过度解读，最后用简短的解释性语言联系研究问题。\n\n五、常见误区与避免策略\n- 误区1：直接把 ChatGPT 的输出做成论文原文。对策：始终进行改写、核对、再加工；不等同于原著观点的表达。\n- 误区2：依赖 AI 生成的数据分析或实验结果。对策：所有数据分析步骤都需要你亲自执行、验证和记录，可在文档中给出你自己的代码和运行结果。\n- 误区3：忽略引用与来源。对策：用 AI 生成的摘要仅作为理解工具，最终写作要以原始文献的要点和你自己的表述为主，并规范引用格式。\n- 误区4：不披露 AI 使用情况。对策：在致谢、方法论段落或附录中如实披露 AI 辅助写作的情况和范围。\n\n六、如果你愿意，我可以为你定制一份“你专属”的使用方案\n请告诉我以下信息，我可以据此给出更贴合你情况的操作清单和 prompts：\n- 你的专业领域和研究方向（学科、题目方向、是否涉及数据/实验）。\n- 你所在学校的毕设要求（字数、结构、引用格式、是否允许 AI 使用等）。\n- 你已有的初步题目、文献清单或数据来源（若有）。\n- 你偏好的工作流程与时间安排（如按周计划、里程碑等）。\n\n温馨提示\n- 任何时候，优先以可靠原文和数据为依据，ChatGPT 只是辅助工具。\n- 在正式提交前，务必进行自我检查与导师审核，确保论文符合学术规范与伦理要求。\n\n如果你愿意，可以告诉我你的专业、方向和一个初步题目，我可以给你一份“可直接使用”的分阶段 prompts 列表，帮助你快速落地。',
│   │   │   'annotations': [],
│   │   │   'id': 'msg_02224eeba87b90ea0069b7af15bd9481978af9a6fe7d6e03a8'
│   │   }
│   ],
│   additional_kwargs={},
│   response_metadata={
│   │   'id': 'resp_02224eeba87b90ea0069b7aef6a89481979ed43de72f3cdcff',
│   │   'created_at': 1773645558.0,
│   │   'model': 'gpt-5-nano-2025-08-07',
│   │   'object': 'response',
│   │   'status': 'completed',
│   │   'model_provider': 'openai',
│   │   'model_name': 'gpt-5-nano-2025-08-07'
│   },
│   id='resp_02224eeba87b90ea0069b7aef6a89481979ed43de72f3cdcff',
│   tool_calls=[],
│   invalid_tool_calls=[],
│   usage_metadata={
│   │   'input_tokens': 16,
│   │   'output_tokens': 7344,
│   │   'total_tokens': 7360,
│   │   'input_token_details': {'cache_read': 0},
│   │   'output_token_details': {'reasoning': 4416}  # 完整的推理内容输出耗费了4416个Token
│   }
)
"""