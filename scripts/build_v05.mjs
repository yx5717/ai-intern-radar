import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const projectDir = path.resolve(scriptDir, "..");
const workspaceDir = path.resolve(projectDir, "..");
const outputDir = path.join(workspaceDir, "outputs", "ai-intern-radar");
const inputPath = path.join(outputDir, "AI实习岗位数据集_v0.4.xlsx");
const outputPath = path.join(outputDir, "AI实习岗位数据集_v0.5.xlsx");
const previewDir = path.join(projectDir, "tmp", "v05_qa");

await fs.mkdir(previewDir, { recursive: true });
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));

const raw = workbook.worksheets.getItem("原始JD");
const processed = workbook.worksheets.getItem("结构化岗位");
const firstReview = workbook.worksheets.getItem("首轮标注任务");

const reviewedIds = new Set(firstReview.getRange("A2:A11").values.flat());
const rawRows = raw.getRange("A2:J31").values;
const processedRows = processed.getRange("A2:X31").values;
const rawById = new Map(rawRows.map((row) => [row[0], row]));
const processedById = new Map(processedRows.map((row) => [row[0], row]));

if (process.argv.includes("--inspect-only")) {
  const preview = await workbook.render({
    sheetName: "首轮标注任务",
    range: "A1:O11",
    scale: 1,
    format: "png",
  });
  await fs.writeFile(path.join(previewDir, "before_首轮标注任务.png"), new Uint8Array(await preview.arrayBuffer()));

  const remaining = rawRows.filter((row) => !reviewedIds.has(row[0]));
  const batchArg = process.argv.find((arg) => arg.startsWith("--batch="));
  const batch = Number(batchArg?.split("=")[1] ?? 1);
  const selected = remaining.slice((batch - 1) * 10, batch * 10);
  for (const row of selected) {
    const p = processedById.get(row[0]);
    console.log(`\n===== ${row[0]} | ${p[1]} | ${p[2]} =====`);
    console.log(`摘要：${row[2]}`);
    console.log(`建议分类：${p[10]} | ${p[11]}`);
    console.log(`冲突：${p[14]} | ${p[15]}`);
    console.log(row[3]);
  }
  process.exit(0);
}

const labels = [
  ["J001", "大模型评测、训练与数据质量", "模型评测", 5, 4, "不通过", "摘要正文冲突", "核心工作是通用大模型的人工评估、自动评估与众测。", "北京5天/周4个月；正文写为期3个月及以上。", "周期冲突，按保守口径记4个月；每周5天超过上限。"],
  ["J002", "AI产品与Agent产品", "对话策略产品", 5, 3, "不通过", "边界分类", "交付对话风格、人设、对话策略及可量化体验方案，核心是产品策略。", "北京5天/周3个月。", "工作横跨评测与训练数据，但核心交付物是对话产品策略；每周5天超过上限。"],
  ["J003", "AI行业研究与战略分析", "AI产业研究", 3, 3, "通过", "无", "收集AI、芯片等行业信息并形成研究报告、榜单和深度文章。", "实习期不少于3个月，每周不少于3天。", "时间符合，核心交付是AI行业研究材料与报告。"],
  ["J004", "AI产品与Agent产品", "AI产品助理", 3, 6, "需要核实", "摘要正文冲突", "协助需求梳理、产品文档、数据分析与版本迭代。", "北京3天/周6个月；正文写每周3天以上、持续3个月以上。", "周期冲突，按保守口径记6个月；需向招聘方核实能否接受4个月。"],
  ["J005", "AI产品与Agent产品", "AI Agent产品与交付", 5, 3, "需要核实", "摘要正文冲突", "推进AI Agent设计、搭建、落地，并执行AI工具UAT。", "北京4天/周3个月；正文要求每周4~5天。", "候选人只能每周4天，需确认能否固定4天。"],
  ["J006", "职能支持/边界岗位", "招聘运营", 3, 6, "不通过", "无", "核心工作包含招聘数据、培训推广及相关职能支持。", "每周至少实习3天，不少于6个月。", "实习周期6个月超过候选人上限；岗位也不属于求职主线。"],
  ["J007", "AI产品与Agent产品", "Agent产品策略", 5, 3, "不通过", "无", "参与Agent角色、关系、剧情、记忆、目标等产品机制与编排设计。", "北京5天/周3个月。", "产品策略是核心交付，但每周5天超过上限。"],
  ["J008", "数据分析与商业/经营分析", "薪酬数据分析", 3, 3, "通过", "无", "完成薪酬调查数据收集、清理、汇总、分析和报告制作。", "北京3天/周3个月。", "时间符合，职责是标准的数据分析交付。"],
  ["J009", "数据分析与商业/经营分析", "战略数据与自动化", 4, 4, "通过", "摘要正文冲突", "用爬虫、自动化代码和大模型API抓取、清洗并维护战略数据。", "摘要为4天/周、3个月；正文要求至少4天/周、持续4个月以上。", "周期冲突，按正文硬要求记4个月；仍在候选人上限内。"],
  ["J010", "数据分析与商业/经营分析", "产品数据分析", 4, 4, "通过", "无", "建设看板、分析核心指标异动并对用户行为建模。", "每周至少实习4天，实习4个月以上。", "时间刚好达到候选人上限，可以投递。"],
  ["J011", "数据分析与商业/经营分析", "商业分析", 5, 3, "需要核实", "摘要正文冲突", "交付经营指标体系、商业分析报告和可执行建议。", "摘要为5天/周；正文写每周4天及以上、连续3个月及以上优先。", "若能固定每周4天则可满足，需先向招聘方确认。"],
  ["J012", "AI行业研究与战略分析", "AI研究与项目支持", 4, 3, "通过", "边界分类", "研究跟踪AI发展并撰写技术文档和项目报告，同时参与项目支持。", "北京4天/周3个月。", "职责包含技术项目，但核心交付偏研究跟踪与报告。"],
  ["J013", "AI产品与Agent产品", "Agent产品运营", 4, 3, "通过", "边界分类", "跟踪用户任务和反馈、分析产品数据，并推进Agent需求到上线。", "每周可实习4天及以上，可实习3个月及以上。", "横跨产品与运营，因核心目标是推动Agent迭代而归入产品类。"],
  ["J014", "数据分析与商业/经营分析", "增长数据分析", 4, 5, "需要核实", "摘要正文冲突；边界分类", "搭建增长、收入和转化指标，输出日报、周报及专题分析。", "摘要为4天/周、5个月；正文写4天以上、连续3个月以上者优先。", "核心交付是指标与分析，不是增长运营执行；周期需确认能否接受4个月。"],
  ["J015", "大模型评测、训练与数据质量", "大模型数据与Benchmark", 4, 4, "通过", "摘要正文冲突", "覆盖大模型数据、对照测试和Benchmark评测工作。", "摘要为4天/周、4个月；正文写每周4天以上、实习不少于3个月。", "按摘要记4个月，时间仍符合。"],
  ["J016", "数据分析与商业/经营分析", "数据治理", 5, 3, "不通过", "摘要正文冲突", "核心交付为数据治理、数据质量和数据规范。", "北京5天/周3个月；摘要为150-200元/天，正文为底薪3500+绩效500/月。", "每周5天超过上限；薪资口径也存在冲突。"],
  ["J017", "AI产品与Agent产品", "ToB AI产品", 4, 5, "需要核实", "摘要正文冲突", "设计工业智能体产品、分析客户需求并推进产品上线迭代。", "摘要为4天/周、5个月；正文希望至少保证4个月以上。", "候选人最多4个月，需确认是否接受恰好4个月。"],
  ["J018", "数据分析与商业/经营分析", "经营分析", 5, 6, "不通过", "摘要正文冲突", "围绕经营目标完成指标拆解、专题分析和商业分析报告。", "摘要为5天/周、6个月；正文写每周出勤不少于4天、连续实习半年以上。", "无论天数取4或5天，半年周期都超过候选人上限。"],
  ["J019", "数据分析与商业/经营分析", "商业数据分析", 4, 3, "通过", "无", "提取、清洗营销数据并完成数据解读和报告输出。", "北京4天/周3个月。", "时间符合；另有2027年以后毕业要求，投递前需保持毕业年份匹配。"],
  ["J020", "AI产品与Agent产品", "多模态AI产品", 4, 6, "不通过", "无", "负责多模态Agent需求分析、产品设计和模型能力产品化。", "北京4天/周6个月。", "每周天数符合，但6个月周期超过候选人上限。"],
  ["J021", "数据分析与商业/经营分析", "用户行为分析", 4, 4, "通过", "无", "完成埋点、用户行为分析、数据看板和竞品数据研究。", "北京4天/周4个月。", "时间刚好达到候选人上限，可以投递。"],
  ["J022", "数据分析与商业/经营分析", "业务数据分析", 5, 3, "需要核实", "摘要正文冲突", "用SQL保障看板数据可信，并分析指标异动、支撑业务复盘。", "摘要为5天/周；正文要求连续3个月以上、每周4~5天。", "若可固定每周4天则符合，需向招聘方确认。"],
  ["J023", "数据分析与商业/经营分析", "用户研究与数据分析", 3, 3, "通过", "无", "负责问卷、数据报告审核、分析报告和用户研究项目执行。", "尽快入职，至少3个月，每周3天及以上。", "时间符合，且可立即到岗。"],
  ["J024", "AI运营、知识库与增长运营", "垂直场景AI运营", 5, 5, "不通过", "无", "参与知识库建设、评测集构建、Prompt优化和效果验证。", "北京5天/周5个月。", "工作内容高度匹配，但每周天数和周期均超过上限。"],
  ["J025", "数据分析与商业/经营分析", "价格分析", 5, 3, "需要核实", "摘要正文冲突", "维护价格数据并分析趋势和异常，输出针对性报告。", "摘要为5天/周；正文要求北京职场每周出勤4天以上。", "若招聘方接受固定每周4天则可满足，需要核实。"],
  ["J026", "AI运营、知识库与增长运营", "用户增长运营", 4, 6, "不通过", "无", "利用AI筛选流量、挖掘用户并持续优化增长转化。", "每周4天，需稳定连续实习6个月及以上。", "每周天数符合，但6个月周期超过候选人上限。"],
  ["J027", "数据分析与商业/经营分析", "业务数据分析", 5, 3, "不通过", "摘要正文冲突", "核心交付是业务数据处理、分析与报告。", "摘要为4天/周、3个月；正文明确每周工作5天、总实习期不低于3个月。", "按正文硬要求记每周5天，因此不通过。"],
  ["J028", "职能支持/边界岗位", "AI招聘", 5, 3, "需要核实", "摘要正文冲突", "核心交付是技术人才寻访、面试推进和招聘流程优化。", "摘要为4天/周、3个月；正文要求连续3个月以上、每周4~5天。", "AI是行业背景和提效工具；需确认能否固定每周4天。"],
  ["J029", "大模型评测、训练与数据质量", "Agent质量与知识管理", 3, 3, "通过", "边界分类", "分析Agent真实表现，建设评测标准、监控机制并治理知识。", "每周至少3天、连续3个月以上；6个月仅为优先。", "硬要求是3天和3个月；岗位虽含原型探索，核心仍是Agent质量。"],
  ["J030", "AI产品与Agent产品", "AI产品与自动化", 5, 3, "不通过", "无", "梳理需求、搭建Demo并持续迭代AI产品和自动化流程。", "北京5天/周3个月。", "内容匹配，但每周5天超过候选人上限。"],
].map(([id, family, direction, days, months, result, badCase, roleBasis, scheduleEvidence, note]) => ({
  id, family, direction, days, months, result, badCase, roleBasis, scheduleEvidence, note,
}));

if (labels.length !== 30 || new Set(labels.map((item) => item.id)).size !== 30) {
  throw new Error("Gold labels must contain 30 unique job IDs.");
}

// Fixed stratified holdout v1: every role family is represented, and test outcomes are 4 pass / 3 verify / 3 fail.
const testIds = new Set(["J002", "J003", "J004", "J010", "J011", "J015", "J016", "J024", "J028", "J029"]);
const splitVersion = "split-v1";

const goldRows = labels.map((label) => {
  const rawRow = rawById.get(label.id);
  const processedRow = processedById.get(label.id);
  if (!rawRow || !processedRow) throw new Error(`Missing source row for ${label.id}`);
  return [
    label.id,
    testIds.has(label.id) ? "test" : "dev",
    processedRow[1],
    processedRow[2],
    rawRow[2],
    label.family,
    label.direction,
    label.days,
    label.months,
    label.result,
    label.badCase,
    label.roleBasis,
    label.scheduleEvidence,
    label.note,
    "已复核",
    splitVersion,
  ];
});

const gold = workbook.worksheets.add("人工标注金标准");
const headers = [
  "岗位ID", "数据集划分", "公司", "岗位名称", "摘要原文", "人工岗位大类", "人工细分方向", "人工每周天数",
  "人工最低月数", "硬约束结果", "Bad Case类型", "分类依据", "时间证据原文", "复核备注", "复核状态", "切分版本",
];
gold.getRange("A1:P1").values = [headers];
gold.getRange("A2:P31").values = goldRows;

const blue = "#2878B5";
const paleBlue = "#EAF2F8";
const paleYellow = "#FFF4CC";
const paleRed = "#FDECEC";
const paleGreen = "#E8F5E9";
const textColor = "#1F2937";
const borderColor = "#D7DEE7";
const bodyFont = "Microsoft YaHei";

gold.getRange("A1:P1").format = {
  fill: blue,
  font: { name: bodyFont, size: 10, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
  borders: { preset: "outside", style: "thin", color: borderColor },
};
gold.getRange("A1:P1").format.rowHeight = 38;
gold.getRange("A2:P31").format = {
  font: { name: bodyFont, size: 9, color: textColor },
  verticalAlignment: "top",
  wrapText: true,
  borders: { insideHorizontal: { style: "thin", color: borderColor } },
};
gold.getRange("A2:P31").format.rowHeight = 46;
gold.getRange("A2:A31").format.fill = paleBlue;
gold.getRange("B2:B31").conditionalFormats.add("containsText", { text: "test", format: { fill: paleYellow, font: { bold: true, color: "#7C5700" } } });
gold.getRange("K2:K31").conditionalFormats.add("notContainsText", { text: "无", format: { fill: paleRed } });
gold.getRange("A:A").format.columnWidth = 9;
gold.getRange("B:B").format.columnWidth = 11;
gold.getRange("C:C").format.columnWidth = 18;
gold.getRange("D:D").format.columnWidth = 34;
gold.getRange("E:E").format.columnWidth = 25;
gold.getRange("F:G").format.columnWidth = 25;
gold.getRange("H:I").format.columnWidth = 15;
gold.getRange("J:J").format.columnWidth = 16;
gold.getRange("K:K").format.columnWidth = 22;
gold.getRange("L:M").format.columnWidth = 44;
gold.getRange("N:N").format.columnWidth = 48;
gold.getRange("O:P").format.columnWidth = 14;
gold.freezePanes.freezeRows(1);
gold.freezePanes.freezeColumns(4);
gold.tables.add("A1:P31", true, "GoldLabelsTable").style = "TableStyleMedium2";
for (let index = 0; index < labels.length; index += 1) {
  const result = labels[index].result;
  const resultStyle = result === "通过"
    ? { fill: paleGreen, font: { name: bodyFont, size: 9, bold: true, color: "#166534" } }
    : result === "不通过"
      ? { fill: paleRed, font: { name: bodyFont, size: 9, bold: true, color: "#9B1C1C" } }
      : { fill: paleYellow, font: { name: bodyFont, size: 9, bold: true, color: "#7C5700" } };
  gold.getRange(`J${index + 2}`).format = resultStyle;
}
gold.showGridLines = false;

const info = workbook.worksheets.getItem("项目说明");
info.getRange("A1").values = [["AI 实习雷达｜岗位数据集 v0.5"]];
info.getRange("B4").values = [["v0.5"]];
info.getRange("A16:D16").values = [[
  "摘要/正文冲突",
  labels.filter((label) => label.badCase.includes("摘要正文冲突")).length,
  "冲突字段按更严格口径记录，并保留核实状态",
  "30条已复核",
]];
info.getRange("A28:D28").merge();
info.getRange("A28").values = [["金标准与数据集切分"]];
info.getRange("A28:D28").format = {
  fill: paleBlue,
  font: { name: bodyFont, size: 11, bold: true, color: "#173F5F" },
  verticalAlignment: "center",
};
info.getRange("A28:D28").format.rowHeight = 26;
info.getRange("A29:D29").values = [["金标准样本", "开发集", "测试集", "切分版本"]];
info.getRange("A29:D29").format = {
  fill: blue,
  font: { name: bodyFont, size: 10, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
  borders: { preset: "outside", style: "thin", color: borderColor },
};
info.getRange("A30:D30").values = [[30, 20, 10, splitVersion]];
info.getRange("A30:D30").format = {
  font: { name: bodyFont, size: 9, color: textColor },
  horizontalAlignment: "center",
  borders: { insideHorizontal: { style: "thin", color: borderColor } },
};
info.getRange("A31:D31").merge();
info.getRange("A31").values = [["固定分层留出：测试集覆盖六类岗位，并包含通过、需要核实、不通过三种结论；后续调优不得查看测试集答案。"]];
info.getRange("A31:D31").format = {
  fill: "#F5F7FA",
  font: { name: bodyFont, size: 9, color: textColor },
  wrapText: true,
  verticalAlignment: "center",
};
info.getRange("A31:D31").format.rowHeight = 34;

processed.getRange("M2:M31").values = labels.map(() => ["已人工复核"]);
processed.getRange("O2:O31").values = labels.map((label) => [label.badCase.includes("摘要正文冲突") ? "是" : "否"]);
processed.getRange("P2:P31").values = labels.map((label) => [label.badCase.includes("摘要正文冲突") ? label.note : ""]);

const dataDir = path.join(projectDir, "data");
await fs.mkdir(dataDir, { recursive: true });
const jsonRecords = labels.map((label) => {
  const rawRow = rawById.get(label.id);
  const processedRow = processedById.get(label.id);
  return {
    job_id: label.id,
    split: testIds.has(label.id) ? "test" : "dev",
    split_version: splitVersion,
    company: processedRow[1],
    role_title: processedRow[2],
    raw_meta: rawRow[2],
    jd_raw: rawRow[3],
    gold: {
      role_family: label.family,
      sub_direction: label.direction,
      weekly_days: label.days,
      minimum_months: label.months,
      constraint_result: label.result,
      bad_case_type: label.badCase,
      role_basis: label.roleBasis,
      schedule_evidence: label.scheduleEvidence,
      review_notes: label.note,
    },
  };
});
const toJsonl = (rows) => `${rows.map((row) => JSON.stringify(row)).join("\n")}\n`;
await fs.writeFile(path.join(dataDir, "gold_labels_v1.jsonl"), toJsonl(jsonRecords), "utf8");
await fs.writeFile(path.join(dataDir, "dev_v1.jsonl"), toJsonl(jsonRecords.filter((row) => row.split === "dev")), "utf8");
await fs.writeFile(path.join(dataDir, "test_v1.jsonl"), toJsonl(jsonRecords.filter((row) => row.split === "test")), "utf8");

const previewRanges = [
  ["项目说明", "A1:D31", "after_项目说明.png"],
  ["原始JD", "A1:J8", "after_原始JD.png"],
  ["结构化岗位", "A1:X12", "after_结构化岗位.png"],
  ["首轮标注任务", "A1:O11", "after_首轮标注任务.png"],
  ["人工标注金标准", "A1:P16", "after_人工标注金标准_上.png"],
  ["人工标注金标准", "A17:P31", "after_人工标注金标准_下.png"],
];
for (const [sheetName, range, filename] of previewRanges) {
  const preview = await workbook.render({ sheetName, range, scale: 1, format: "png" });
  await fs.writeFile(path.join(previewDir, filename), new Uint8Array(await preview.arrayBuffer()));
}

const check = await workbook.inspect({
  kind: "table",
  range: "人工标注金标准!A1:P31",
  include: "values,formulas",
  tableMaxRows: 31,
  tableMaxCols: 16,
  tableMaxCellChars: 100,
  maxChars: 16000,
});
console.log(check.ndjson);
const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 300 },
  summary: "final formula error scan",
});
console.log(errors.ndjson);

await fs.mkdir(outputDir, { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

const exportedWorkbook = await SpreadsheetFile.importXlsx(await FileBlob.load(outputPath));
const exportedErrors = await exportedWorkbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 300 },
  summary: "post-export formula error scan",
});
console.log(exportedErrors.ndjson);
const exportedCheck = await exportedWorkbook.inspect({
  kind: "table",
  range: "人工标注金标准!A1:P31",
  include: "values,formulas",
  tableMaxRows: 5,
  tableMaxCols: 16,
  maxChars: 5000,
});
console.log(exportedCheck.ndjson);
console.log(`Saved ${outputPath}`);
