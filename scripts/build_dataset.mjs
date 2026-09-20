import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const projectDir = path.resolve(scriptDir, "..");
const workspaceDir = path.resolve(projectDir, "..");
const records = JSON.parse(await fs.readFile(path.join(projectDir, "tmp", "jd_records.json"), "utf8"));
const outputDir = path.join(workspaceDir, "outputs", "ai-intern-radar");
const outputPath = path.join(outputDir, "AI实习岗位数据集_v0.3.xlsx");

const roleFamilies = {
  J001: "大模型评测、训练与数据质量", J002: "AI产品与Agent产品", J003: "AI行业研究与战略分析", J004: "AI产品与Agent产品",
  J005: "AI产品与Agent产品", J006: "职能支持/边界岗位", J007: "AI产品与Agent产品", J008: "数据分析与商业/经营分析",
  J009: "数据分析与商业/经营分析", J010: "数据分析与商业/经营分析", J011: "数据分析与商业/经营分析",
  J012: "AI行业研究与战略分析", J013: "AI产品与Agent产品", J014: "AI运营、知识库与增长运营",
  J015: "大模型评测、训练与数据质量", J016: "数据分析与商业/经营分析", J017: "AI产品与Agent产品",
  J018: "数据分析与商业/经营分析", J019: "数据分析与商业/经营分析", J020: "AI产品与Agent产品",
  J021: "数据分析与商业/经营分析", J022: "数据分析与商业/经营分析", J023: "数据分析与商业/经营分析",
  J024: "AI运营、知识库与增长运营", J025: "数据分析与商业/经营分析", J026: "AI运营、知识库与增长运营",
  J027: "数据分析与商业/经营分析", J028: "职能支持/边界岗位", J029: "大模型评测、训练与数据质量",
  J030: "AI产品与Agent产品",
};

const subDirections = {
  J001: "模型评测", J002: "对话策略产品", J003: "AI产业研究", J004: "AI产品助理",
  J005: "AI Agent产品与交付", J006: "招聘运营", J007: "Agent产品策略", J008: "数据分析",
  J009: "战略数据与自动化", J010: "产品数据分析", J011: "商业分析", J012: "AI研究与项目支持",
  J013: "Agent产品运营", J014: "数据运营", J015: "大模型数据与Benchmark", J016: "数据治理",
  J017: "ToB AI产品", J018: "经营分析", J019: "商业数据分析", J020: "多模态AI产品",
  J021: "用户行为分析", J022: "业务数据分析", J023: "用户研究与数据分析", J024: "垂直场景AI运营",
  J025: "价格分析", J026: "用户增长运营", J027: "业务数据分析", J028: "AI招聘",
  J029: "Agent质量与知识管理", J030: "AI产品与自动化",
};

const conflicts = {
  J001: "标题中的‘2728届’写法疑似缺少分隔符；摘要4个月，正文仅说明3个月以上。",
  J004: "摘要为6个月，正文要求3个月以上。",
  J005: "摘要为每周4天，正文要求每周4-5天。",
  J009: "摘要为3个月，正文要求持续4个月以上。",
  J011: "摘要为每周5天，正文写每周4天及以上。",
  J014: "摘要为5个月，正文写连续3个月以上优先。",
  J015: "摘要为4个月，正文写不少于3个月。",
  J016: "摘要为150-200元/天，正文为底薪3500元+绩效500元/月。",
  J017: "摘要为5个月，正文写至少4个月。",
  J018: "摘要为每周5天，正文写每周4天及以上。",
  J027: "摘要为每周4天，正文明确每周工作5天。",
};

const fit = {
  J001: ["暂缓", "每周5天超出当前上限；可作为评测岗位研究样本。"],
  J002: ["暂缓", "每周5天超出当前上限，岗位竞争也较强。"],
  J003: ["优先", "3天/周、3个月；经济统计、AI研究、英文与报告能力匹配。"],
  J004: ["优先核实", "3天/周且职责匹配，但摘要与正文的周期要求冲突。"],
  J005: ["优先", "AI Agent、UAT与文档工作匹配；4-5天要求需核实。"],
  J006: ["不匹配", "要求2026届且连续6个月。"],
  J007: ["暂缓", "岗位内容高度相关，但每周5天超出当前上限。"],
  J008: ["优先", "3天/周、3个月；统计、BI与Python背景直接匹配。"],
  J009: ["可投", "4天/周；正文周期4个月可满足上限，需补API调用作品证据。"],
  J010: ["可投", "4天/周、4个月；专业匹配，但SQL是明显能力缺口。"],
  J011: ["优先核实", "正文4天可满足，摘要写5天；SQL/Python要求较高。"],
  J012: ["可投", "4天/周、3个月，但岗位描述较泛，需要进一步核实实际工作。"],
  J013: ["优先", "4天/周、3个月；Agent产品、用户反馈和数据体系与目标方向一致。"],
  J014: ["优先核实", "4天/周且统计背景匹配，但周期摘要5个月、正文3个月以上。"],
  J015: ["优先", "4天/周、4个月；接受无实习经历，覆盖对照测试和benchmark。"],
  J016: ["暂缓", "每周5天超出上限，且薪资口径冲突。"],
  J017: ["优先核实", "每周4天，AI产品内容匹配；周期需确认能否接受4个月。"],
  J018: ["暂缓", "周期6个月超出当前上限。"],
  J019: ["可投", "4天/周、3个月且毕业年份匹配；需要补SQL。"],
  J020: ["暂缓", "周期6个月超出当前上限，且更看重成熟Side Project。"],
  J021: ["可投", "4天/周、4个月；统计专业匹配，需要补SQL。"],
  J022: ["暂缓", "每周5天超出当前上限，SQL要求较高。"],
  J023: ["优先", "3天/周、3个月；统计软件、研究与报告能力匹配。"],
  J024: ["暂缓", "岗位内容非常匹配，但5天/周、5个月均超出当前上限。"],
  J025: ["暂缓", "每周5天超出当前上限，且SQL为硬要求。"],
  J026: ["暂缓", "周期6个月超出当前上限。"],
  J027: ["不匹配", "正文明确每周5天，超出当前上限。"],
  J028: ["可投但非主线", "时间条件匹配，但方向是招聘而非AI产品/评测/数据主线。"],
  J029: ["最高优先", "3天/周、3个月；专业不限，职责完整覆盖Agent质量、知识库和评测。"],
  J030: ["暂缓", "每周5天超出当前上限，且API/Git/基础开发要求较高。"],
};

const skillPatterns = [
  ["SQL", /\bSQL\b/i], ["Python", /\bPython\b/i], ["Excel", /\bExcel\b/i],
  ["R", /(?:^|[\s、，,/（(])R(?:[\s、，,/）)]|$)/], ["SPSS", /\bSPSS\b/i],
  ["Stata", /\bStata\b/i], ["BI", /\bBI\b|FineBI|Power BI/i], ["PPT", /\bPPT\b/i],
  ["Prompt", /Prompt/i], ["RAG", /\bRAG\b/i], ["Agent", /Agent|智能体/i],
  ["Coze", /Coze/i], ["Dify", /Dify/i], ["LangChain", /LangChain/i],
  ["LangGraph", /LangGraph/i], ["n8n", /\bn8n\b/i], ["API", /\bAPI\b/i],
  ["Git", /\bGit\b|GitLab/i], ["Codex", /Codex/i], ["Tableau", /Tableau/i],
  ["VBA", /\bVBA\b/i],
];

function mentionedSkills(text) {
  return skillPatterns.filter(([, pattern]) => pattern.test(text)).map(([name]) => name).join("、");
}

const workbook = Workbook.create();
const info = workbook.worksheets.add("项目说明");
const raw = workbook.worksheets.add("原始JD");
const processed = workbook.worksheets.add("结构化岗位");
const annotation = workbook.worksheets.add("首轮标注任务");
workbook.comments.setSelf({ displayName: "王嘉麟" });

const navy = "#173F5F";
const blue = "#2878B5";
const paleBlue = "#EAF2F8";
const paleGray = "#F5F7FA";
const paleYellow = "#FFF4CC";
const paleRed = "#FDECEC";
const paleGreen = "#E8F5E9";
const textColor = "#1F2937";
const borderColor = "#D7DEE7";
const bodyFont = "Microsoft YaHei";

function styleTitle(sheet, range, title) {
  sheet.getRange(range).merge();
  const cell = sheet.getRange(range.split(":")[0]);
  cell.values = [[title]];
  sheet.getRange(range).format = {
    fill: navy,
    font: { name: bodyFont, size: 18, bold: true, color: "#FFFFFF" },
    verticalAlignment: "center",
  };
  sheet.getRange(range).format.rowHeight = 34;
}

function styleHeader(range) {
  range.format = {
    fill: blue,
    font: { name: bodyFont, size: 10, bold: true, color: "#FFFFFF" },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
    borders: { preset: "outside", style: "thin", color: borderColor },
  };
  range.format.rowHeight = 32;
}

function styleBody(range) {
  range.format = {
    font: { name: bodyFont, size: 9, color: textColor },
    verticalAlignment: "top",
    borders: { insideHorizontal: { style: "thin", color: borderColor } },
  };
}

// 项目说明
styleTitle(info, "A1:D1", "AI 实习雷达｜岗位数据集 v0.3");
info.getRange("A3:D3").merge();
info.getRange("A3").values = [["数据集概览"]];
info.getRange("A4:D6").values = [
  ["数据集版本", "v0.3", "岗位数量", null],
  ["来源平台", "BOSS直聘", "采集日期", new Date("2026-09-20T00:00:00")],
  ["原岗位链接", "未保留，字段留空", "发布日期", "来源页面未显示，字段留空"],
];
info.getRange("D4").formulas = [["=COUNTA('原始JD'!$A$2:$A$31)"]];
info.getRange("D5").format.numberFormat = "yyyy-mm-dd";

info.getRange("A8:D8").merge();
info.getRange("A8").values = [["候选人硬约束"]];
info.getRange("A9:D10").values = [
  ["到岗时间", "立即", "每周最多线下天数", 4],
  ["可实习最短月数", 2, "可实习最长月数", 4],
];

info.getRange("A12:D12").merge();
info.getRange("A12").values = [["数据质量与处理原则"]];
info.getRange("A13:D13").values = [["检查项", "数量", "处理原则", "状态"]];
info.getRange("A14:D17").values = [
  ["来源链接缺失", null, "保留空值，不补造链接", "已记录"],
  ["发布日期缺失", null, "不以采集日期替代", "已记录"],
  ["摘要/正文冲突", null, "进入人工复核与Bad Case", "待复核"],
  ["摘要初筛通过", null, "仅按天数与周期判断", "初筛结果"],
];
info.getRange("B14").formulas = [["=COUNTBLANK('原始JD'!$F$2:$F$31)"]];
info.getRange("B15").formulas = [["=COUNTBLANK('原始JD'!$G$2:$G$31)"]];
info.getRange("B16").formulas = [["=COUNTIF('结构化岗位'!$O$2:$O$31,\"是\")"]];
info.getRange("B17").formulas = [["=COUNTIF('结构化岗位'!$N$2:$N$31,\"摘要初筛通过\")"]];

info.getRange("A19:D19").merge();
info.getRange("A19").values = [["岗位分类体系｜按核心交付物归类，不按AI工具关键词归类"]];
info.getRange("A20:D20").values = [["岗位大类", "样本数", "市场常见岗位名称", "本项目分类边界"]];
const families = [
  ["AI产品与Agent产品", null, "AI产品经理、AI产品实习生、Agent产品", "交付需求、策略、原型、版本或产品落地"],
  ["大模型评测、训练与数据质量", null, "大模型评测、AI训练师、模型质量、数据策略", "交付评测集、Benchmark、训练数据或质量改善结果"],
  ["AI运营、知识库与增长运营", null, "AI产品运营、知识库运营、模型运营、增长运营", "交付知识内容、用户反馈闭环、Prompt优化或增长结果"],
  ["数据分析与商业/经营分析", null, "数据分析、商业分析、经营分析、用户研究", "交付指标看板、业务诊断、经营结论或研究报告"],
  ["AI行业研究与战略分析", null, "AI行业研究、科技研究、战略分析、研究助理", "交付产业、政策、公司、产品或技术趋势判断"],
  ["职能支持/边界岗位", null, "AI招聘、泛运营等", "AI只是行业背景或提效工具，不是岗位核心产出"],
];
info.getRange("A21:D26").values = families;
for (let i = 0; i < families.length; i += 1) {
  info.getRange(`B${21 + i}`).formulas = [[`=COUNTIF('结构化岗位'!$K$2:$K$31,A${21 + i})`]];
}
for (const row of [3, 8, 12, 19]) {
  info.getRange(`A${row}:D${row}`).format = {
    fill: paleBlue,
    font: { name: bodyFont, size: 11, bold: true, color: navy },
    verticalAlignment: "center",
  };
  info.getRange(`A${row}:D${row}`).format.rowHeight = 26;
}
styleHeader(info.getRange("A13:D13"));
styleHeader(info.getRange("A20:D20"));
styleBody(info.getRange("A4:D6"));
styleBody(info.getRange("A9:D10"));
styleBody(info.getRange("A14:D17"));
styleBody(info.getRange("A21:D26"));
info.getRange("A4:A6").format.font = { name: bodyFont, size: 9, bold: true, color: textColor };
info.getRange("C4:C6").format.font = { name: bodyFont, size: 9, bold: true, color: textColor };
info.getRange("A9:A10").format.font = { name: bodyFont, size: 9, bold: true, color: textColor };
info.getRange("C9:C10").format.font = { name: bodyFont, size: 9, bold: true, color: textColor };
info.getRange("A1:D26").format.wrapText = true;
info.getRange("A:A").format.columnWidth = 29;
info.getRange("B:B").format.columnWidth = 13;
info.getRange("C:C").format.columnWidth = 42;
info.getRange("D:D").format.columnWidth = 50;
info.getRange("A21:D26").format.rowHeight = 38;
info.showGridLines = false;

// 原始 JD
const rawHeaders = ["job_id", "raw_heading", "raw_meta", "jd_raw", "source_platform", "source_url", "published_at", "collected_at", "source_file", "parsing_status"];
raw.getRange("A1:J1").values = [rawHeaders];
styleHeader(raw.getRange("A1:J1"));
const rawRows = records.map((r) => [
  r.job_id, r.raw_heading, r.raw_meta, r.jd_raw, r.source_platform, r.source_url,
  r.published_at, new Date(`${r.collected_at}T00:00:00`), r.source_file, r.parsing_status,
]);
raw.getRange(`A2:J${rawRows.length + 1}`).values = rawRows;
styleBody(raw.getRange(`A2:J${rawRows.length + 1}`));
raw.getRange(`H2:H${rawRows.length + 1}`).format.numberFormat = "yyyy-mm-dd";
raw.getRange(`B2:D${rawRows.length + 1}`).format.wrapText = true;
raw.getRange(`A2:A${rawRows.length + 1}`).format.fill = paleBlue;
raw.getRange("A:A").format.columnWidth = 10;
raw.getRange("B:B").format.columnWidth = 45;
raw.getRange("C:C").format.columnWidth = 28;
raw.getRange("D:D").format.columnWidth = 80;
raw.getRange("E:E").format.columnWidth = 14;
raw.getRange("F:G").format.columnWidth = 18;
raw.getRange("H:H").format.columnWidth = 14;
raw.getRange("I:I").format.columnWidth = 14;
raw.getRange("J:J").format.columnWidth = 20;
raw.freezePanes.freezeRows(1);
raw.freezePanes.freezeColumns(1);
raw.tables.add(`A1:J${rawRows.length + 1}`, true, "RawJDTable").style = "TableStyleMedium2";
raw.showGridLines = false;

// 结构化岗位
const processedHeaders = [
  "job_id", "company", "role_title", "salary_min", "salary_max", "pay_unit", "city",
  "weekly_days_summary", "duration_months_summary", "education_summary", "proposed_role_family",
  "proposed_sub_direction", "family_review_status", "schedule_screen", "conflict_flag", "conflict_notes", "fit_tier_proposed",
  "fit_reason_proposed", "mentioned_skills", "graduation_requirement", "collected_at", "source_platform",
  "source_url", "published_at",
];
processed.getRange("A1:X1").values = [processedHeaders];
styleHeader(processed.getRange("A1:X1"));
const graduationRequirements = {
  J006: "2026届", J019: "2027年以后毕业", J023: "2026年及之后毕业", J028: "2027年以后毕业",
};
const processedRows = records.map((r) => {
  const [tier, reason] = fit[r.job_id];
  return [
    r.job_id, r.company, r.role_title, r.salary_min, r.salary_max, r.pay_unit, r.city,
    r.weekly_days_summary, r.duration_months_summary, r.education_summary, roleFamilies[r.job_id],
    subDirections[r.job_id], "待人工复核", null, conflicts[r.job_id] ? "是" : "否", conflicts[r.job_id] ?? "",
    tier, reason, mentionedSkills(r.jd_raw), graduationRequirements[r.job_id] ?? "未明确",
    new Date(`${r.collected_at}T00:00:00`), r.source_platform, r.source_url, r.published_at,
  ];
});
processed.getRange(`A2:X${processedRows.length + 1}`).values = processedRows;
for (let row = 2; row <= processedRows.length + 1; row += 1) {
  processed.getRange(`N${row}`).formulas = [[`=IF(OR(H${row}=\"\",I${row}=\"\"),\"待补充\",IF(AND(H${row}<='项目说明'!$D$9,I${row}<='项目说明'!$D$10),\"摘要初筛通过\",\"摘要初筛不通过\"))`]];
}
styleBody(processed.getRange(`A2:X${processedRows.length + 1}`));
processed.getRange(`D2:E${processedRows.length + 1}`).format.numberFormat = "0";
processed.getRange(`H2:I${processedRows.length + 1}`).format.numberFormat = "0";
processed.getRange(`U2:U${processedRows.length + 1}`).format.numberFormat = "yyyy-mm-dd";
processed.getRange(`A2:A${processedRows.length + 1}`).format.fill = paleBlue;
processed.getRange(`M2:M${processedRows.length + 1}`).format.fill = paleYellow;
processed.getRange(`P2:S${processedRows.length + 1}`).format.wrapText = true;
processed.getRange(`O2:O${processedRows.length + 1}`).conditionalFormats.add("containsText", { text: "是", format: { fill: paleRed, font: { color: "#9B1C1C", bold: true } } });
processed.getRange(`N2:N${processedRows.length + 1}`).conditionalFormats.add("containsText", { text: "通过", format: { fill: paleGreen, font: { color: "#166534", bold: true } } });
processed.getRange(`N2:N${processedRows.length + 1}`).conditionalFormats.add("containsText", { text: "不通过", format: { fill: paleRed, font: { color: "#9B1C1C", bold: true } } });
processed.getRange("A:A").format.columnWidth = 9;
processed.getRange("B:B").format.columnWidth = 18;
processed.getRange("C:C").format.columnWidth = 34;
processed.getRange("D:F").format.columnWidth = 12;
processed.getRange("G:J").format.columnWidth = 14;
processed.getRange("K:K").format.columnWidth = 24;
processed.getRange("L:L").format.columnWidth = 25;
processed.getRange("M:O").format.columnWidth = 17;
processed.getRange("P:P").format.columnWidth = 42;
processed.getRange("Q:Q").format.columnWidth = 14;
processed.getRange("R:R").format.columnWidth = 48;
processed.getRange("S:S").format.columnWidth = 36;
processed.getRange("T:X").format.columnWidth = 18;
processed.freezePanes.freezeRows(1);
processed.freezePanes.freezeColumns(3);
processed.tables.add(`A1:X${processedRows.length + 1}`, true, "ProcessedJobsTable").style = "TableStyleMedium2";
processed.showGridLines = false;

// 首轮人工标注任务
const sampleIds = ["J001", "J003", "J004", "J005", "J007", "J015", "J016", "J024", "J027", "J029"];
const annotationHeaders = [
  "岗位ID", "公司", "岗位名称", "摘要原文", "建议大类", "建议细分方向", "人工岗位大类",
  "人工细分方向", "人工每周天数", "人工最低月数", "硬约束结果", "Bad Case类型",
  "证据原文", "复核备注", "复核状态",
];
annotation.getRange("A1:O1").values = [annotationHeaders];
styleHeader(annotation.getRange("A1:O1"));
for (let i = 0; i < sampleIds.length; i += 1) {
  const jobNumber = Number(sampleIds[i].slice(1));
  const sourceRow = jobNumber + 1;
  const row = i + 2;
  annotation.getRange(`A${row}:F${row}`).formulas = [[
    `='结构化岗位'!A${sourceRow}`,
    `='结构化岗位'!B${sourceRow}`,
    `='结构化岗位'!C${sourceRow}`,
    `='原始JD'!C${sourceRow}`,
    `='结构化岗位'!K${sourceRow}`,
    `='结构化岗位'!L${sourceRow}`,
  ]];
  annotation.getRange(`G${row}:O${row}`).values = [[null, null, null, null, null, null, null, null, "待复核"]];
}
styleBody(annotation.getRange("A2:O11"));
annotation.getRange("A2:F11").format.fill = paleGray;
annotation.getRange("G2:O11").format.fill = paleYellow;
annotation.getRange("D2:O11").format.wrapText = true;
annotation.getRange("G2:G11").dataValidation = { rule: { type: "list", values: [
  "AI产品与Agent产品", "大模型评测、训练与数据质量", "AI运营、知识库与增长运营",
  "数据分析与商业/经营分析", "AI行业研究与战略分析", "职能支持/边界岗位",
] } };
annotation.getRange("H2:H11").dataValidation = { rule: { type: "list", values: [
  "模型评测", "Agent质量", "AI训练与数据", "AI产品", "Agent产品", "AI产品运营", "知识库运营",
  "数据分析", "商业分析", "经营分析", "数据运营", "增长运营", "AI行业研究", "其他",
] } };
annotation.getRange("K2:K11").dataValidation = { rule: { type: "list", values: ["通过", "不通过", "需要核实"] } };
annotation.getRange("L2:L11").dataValidation = { rule: { type: "list", values: [
  "无", "字段缺失", "摘要正文冲突", "边界分类", "无依据推断", "文本截断", "其他",
] } };
annotation.getRange("O2:O11").dataValidation = { rule: { type: "list", values: ["待复核", "已复核"] } };
annotation.getRange("A:A").format.columnWidth = 9;
annotation.getRange("B:B").format.columnWidth = 18;
annotation.getRange("C:C").format.columnWidth = 34;
annotation.getRange("D:D").format.columnWidth = 24;
annotation.getRange("E:H").format.columnWidth = 23;
annotation.getRange("I:L").format.columnWidth = 18;
annotation.getRange("M:N").format.columnWidth = 42;
annotation.getRange("O:O").format.columnWidth = 14;
annotation.getRange("A1:O1").format.rowHeight = 38;
annotation.freezePanes.freezeRows(1);
annotation.freezePanes.freezeColumns(3);
annotation.tables.add("A1:O11", true, "AnnotationTaskTable").style = "TableStyleMedium2";
annotation.showGridLines = false;

await fs.mkdir(outputDir, { recursive: true });

const previewRanges = [
  ["项目说明", "A1:D26", "preview_info.png"],
  ["原始JD", "A1:J7", "preview_raw.png"],
  ["结构化岗位", "A1:X12", "preview_processed.png"],
  ["首轮标注任务", "A1:O11", "preview_annotation.png"],
];
for (const [sheetName, range, filename] of previewRanges) {
  const preview = await workbook.render({ sheetName, range, scale: 1, format: "png" });
  await fs.writeFile(path.join(projectDir, "tmp", filename), new Uint8Array(await preview.arrayBuffer()));
}

const check = await workbook.inspect({
  kind: "table",
  range: "项目说明!A1:D26",
  include: "values,formulas",
  tableMaxRows: 25,
  tableMaxCols: 8,
  maxChars: 6000,
});
console.log(check.ndjson);
const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "final formula error scan",
});
console.log(errors.ndjson);

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(`Saved ${outputPath}`);
