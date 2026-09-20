import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const workspaceDir = path.resolve(".");
const projectDir = path.join(workspaceDir, "ai-intern-radar");
const dataDir = path.join(projectDir, "data");
const outputDir = path.join(workspaceDir, "outputs", "ai-intern-radar");
const previewDir = path.join(projectDir, "tmp", "external_eval_v1_qa");
const inputPath = path.join(outputDir, "AI实习岗位数据集_v0.7.xlsx");
const outputPath = path.join(outputDir, "AI实习岗位数据集_v0.8.xlsx");

const parseJsonl = async (file) => (await fs.readFile(file, "utf8")).replace(/^\uFEFF/, "").trim().split(/\r?\n/).map(JSON.parse);
const records = await parseJsonl(path.join(dataDir, "external_jd_v1.jsonl"));
const predictions = await parseJsonl(path.join(dataDir, "external_predictions_frozen_v1.jsonl"));
const recordById = new Map(records.map((row) => [row.job_id, row]));
const predictionById = new Map(predictions.map((row) => [row.job_id, row]));

const labels = [
  ["EXT001", "数据分析与商业/经营分析", "数据开发与治理", 3, 3, "通过", "无", "核心交付是数仓、数据资产和AI-ready数据基础设施。", "摘要3天/周、3个月。", "时间符合。"],
  ["EXT002", "数据分析与商业/经营分析", "数据平台与数仓", 5, 3, "不通过", "无", "建设数据专题体系、数据资产和数据服务能力。", "摘要5天/周、3个月；全勤仅写为优先。", "每周5天超过上限。"],
  ["EXT003", "数据分析与商业/经营分析", "用户行为与数据科学", 5, 3, "不通过", "无", "围绕用户行为、因果推断和模型效果输出分析结论。", "摘要5天/周、3个月。", "每周5天超过上限。"],
  ["EXT004", "数据分析与商业/经营分析", "体验与经营分析", 5, 5, "不通过", "无", "通过指标体系和专项分析形成体验诊断报告。", "摘要5天/周、5个月。", "天数和周期均超过上限。"],
  ["EXT005", "数据分析与商业/经营分析", "销售策略分析", 5, 3, "需要核实", "摘要正文冲突", "交付增长机会分析、指标监控和策略落地洞察。", "摘要5天/周、3个月；正文每周4天以上，6个月仅为优先。", "需确认是否接受固定每周4天。"],
  ["EXT006", "职能支持/边界岗位", "项目运营与产品支持", 5, 5, "不通过", "边界分类", "核心是需求项目管理、PRD流转和基础数据支持，AI不是核心产出。", "摘要5天/周、5个月。", "天数和周期均超过上限。"],
  ["EXT007", "职能支持/边界岗位", "AI算法研发", 3, 3, "通过", "边界分类", "核心交付是算法模型训练、性能评估和硬件加速支持，不属于六类目标业务岗。", "摘要3天/周、3个月；正文3-6个月，6个月优先。", "硬要求可按3个月满足。"],
  ["EXT008", "职能支持/边界岗位", "AI应用开发", 5, 6, "不通过", "边界分类", "核心是生成式AI应用的编码、云端部署和技术实现。", "摘要5天/周、6个月。", "天数和周期均超过上限。"],
  ["EXT009", "大模型评测、训练与数据质量", "AI训练数据与知识图谱", 4, 3, "通过", "无", "负责知识图谱、Prompt测试、智能体调试、数据标注和反馈优化。", "摘要4天/周、3个月。", "时间符合，内容高度匹配。"],
  ["EXT010", "大模型评测、训练与数据质量", "多模态与大模型评测", 5, 3, "需要核实", "摘要正文冲突", "制作视觉测试集并执行大模型人工评测、问题总结。", "摘要5天/周、3个月；正文每周4-5天。", "需确认是否接受固定每周4天。"],
  ["EXT011", "数据分析与商业/经营分析", "数据治理与分析", 5, 2, "不通过", "无", "参与数据清洗治理、数据挖掘和市场趋势分析报告。", "周实习天数5天，总实习2个月。", "每周5天超过上限。"],
  ["EXT012", "数据分析与商业/经营分析", "大数据开发与运维", 5, 3, "不通过", "无", "交付大数据任务开发、调度监控、故障排查和运维工具。", "周实习天数5天，总实习3个月。", "每周5天超过上限。"],
  ["EXT013", "数据分析与商业/经营分析", "业务数据分析", 3, 3, "通过", "无", "完成数据收集、清理、分析和报告制作。", "周实习天数3天，总实习3个月。", "时间符合。"],
  ["EXT014", "AI产品与Agent产品", "AI招聘产品", 6, 6, "不通过", "摘要正文冲突", "交付AI招聘产品需求、原型、迭代和效果验证。", "摘要6天/周、6个月；正文每周3天以上。", "周期明确超过上限，且天数信息冲突。"],
  ["EXT015", "AI产品与Agent产品", "C端AI招聘产品", 5, 4, "不通过", "无", "围绕搜索、推荐和对话式Agent推进需求到上线复盘。", "周实习天数5天，总实习4个月。", "每周5天超过上限。"],
  ["EXT016", "AI产品与Agent产品", "风控AI产品", 5, 6, "不通过", "摘要正文冲突", "交付风控产品需求、AI探索和领域知识库。", "摘要5天/周、6个月；正文加分项写实习2个月以上。", "每周5天超过上限；周期口径冲突。"],
  ["EXT017", "AI产品与Agent产品", "AI应用与Agent交付", 3, 3, "通过", "无", "面向真实业务设计、搭建和优化AI工具、智能体、知识库与工作流。", "周实习天数3天、总实习3个月；正文每周3天以上。", "时间符合，内容高度匹配。"],
  ["EXT018", "职能支持/边界岗位", "AI应用开发", 4, 6, "需要核实", "摘要正文冲突；边界分类", "核心是AI原型开发、接口集成、数据处理和模型工程。", "摘要4天/周、6个月；正文3-6个月、每周至少4天。", "需确认是否接受恰好4个月；岗位偏技术开发。"],
  ["EXT019", "数据分析与商业/经营分析", "业务数据分析", 5, 3, "不通过", "摘要正文冲突", "完成数据提取清洗、报表、看板和专项分析。", "摘要3天/周、3个月；正文每周至少5天。", "按正文硬要求记5天，不通过。"],
  ["EXT020", "数据分析与商业/经营分析", "业务数据分析", 4, 3, "通过", "无", "交付数据报表、指标监控和数据问题排查。", "4天/周，最少3个月。", "时间符合。"],
  ["EXT021", "数据分析与商业/经营分析", "数据科学", 5, 6, "不通过", "无", "使用SQL和Python完成数据科学全流程分析。", "5天/周，最少6个月。", "天数和周期均超过上限。"],
  ["EXT022", "数据分析与商业/经营分析", "销售运营分析", 4, 3, "通过", "无", "交付销售指标报表、报告及行业信息整理。", "摘要4天/周、3个月；正文4-5天、3-6个月。", "摘要处于正文允许范围内，时间可满足。"],
  ["EXT023", "AI运营、知识库与增长运营", "AI工具与自动化运营", 4, 3, "通过", "边界分类", "沉淀AI工具指南、Prompt模板、自动化工作流和内部知识库。", "4天/周，最少3个月。", "时间符合；按核心交付归入AI运营而非技术开发。"],
  ["EXT024", "大模型评测、训练与数据质量", "模型效果与Bad Case分析", 5, 3, "需要核实", "摘要正文冲突；边界分类", "核心交付是模型指标监控、数据标注、错误归因和优化建议。", "摘要5天/周、3个月；正文每周至少4天。", "需确认是否接受固定每周4天；标题是产品助理但核心是评测。"],
  ["EXT025", "大模型评测、训练与数据质量", "AI数据质量与产品测试", 3, 3, "通过", "边界分类", "维护测试数据集、核对解析结果、分析错误并输出测试报告。", "3天/周，最少3个月；正文3个月以上为优先。", "时间符合；工作横跨产品运营与数据质量。"],
  ["EXT026", "大模型评测、训练与数据质量", "Agent与RAG效果评测", 4, 3, "通过", "边界分类", "搭建评测体系、构建测试集、分析Bad Case并跟踪优化闭环。", "4天/周，最少3个月。", "时间符合，岗位与目标作品方向高度匹配。"],
].map(([job_id, role_family, sub_direction, weekly_days, minimum_months, constraint_result, bad_case_type, role_basis, schedule_evidence, review_notes]) => ({
  job_id, role_family, sub_direction, weekly_days, minimum_months, constraint_result, bad_case_type, role_basis, schedule_evidence, review_notes,
}));
if (labels.length !== 26 || new Set(labels.map((row) => row.job_id)).size !== 26) throw new Error("Gold labels must contain 26 unique IDs.");

const goldRows = labels.map((label) => ({
  ...recordById.get(label.job_id),
  split: "external_blind_v1",
  gold: { ...label, job_id: undefined },
  review_status: "已人工复核",
  label_version: "external-gold-v1",
}));
const toJsonl = (rows) => `${rows.map((row) => JSON.stringify(row)).join("\n")}\n`;
await fs.writeFile(path.join(dataDir, "external_gold_v1.jsonl"), toJsonl(goldRows), "utf8");

const fields = [
  ["role_family", "岗位大类"], ["weekly_days", "每周天数"], ["minimum_months", "最低月数"],
  ["constraint_result", "硬约束结论"], ["bad_case_type", "Bad Case类型"],
];
const comparisons = labels.map((gold) => ({ gold, prediction: predictionById.get(gold.job_id), source: recordById.get(gold.job_id) }));
const metric = (key) => {
  const correct = comparisons.filter(({ gold, prediction }) => gold[key] === prediction[key]).length;
  return { correct, total: comparisons.length, accuracy: correct / comparisons.length };
};
const report = {
  evaluation_scope: "cross_platform_external_blind_test",
  prediction_version: "rule-baseline-v1-frozen",
  gold_version: "external-gold-v1",
  sample_count: 26,
  platforms: { 实习僧: 10, 智联招聘: 8, 牛客网: 8 },
  metrics: Object.fromEntries(fields.map(([key]) => [key, metric(key)])),
};
report.metrics.bad_case_binary = (() => {
  const correct = comparisons.filter(({ gold, prediction }) => (gold.bad_case_type !== "无") === (prediction.bad_case_type !== "无")).length;
  return { correct, total: comparisons.length, accuracy: correct / comparisons.length };
})();
const errors = [];
for (const { gold, prediction, source } of comparisons) {
  for (const [key, label] of fields) {
    if (gold[key] !== prediction[key]) errors.push({ job_id: gold.job_id, field: label, expected: gold[key], actual: prediction[key], role_title: source.role_title });
  }
}
report.error_count = errors.length;
await fs.writeFile(path.join(dataDir, "external_eval_v1.json"), `${JSON.stringify(report, null, 2)}\n`, "utf8");

await fs.mkdir(previewDir, { recursive: true });
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));
const blue = "#2878B5", navy = "#173F5F", paleBlue = "#EAF2F8", paleGreen = "#E8F5E9";
const paleRed = "#FDECEC", paleYellow = "#FFF4CC", paleGray = "#F5F7FA", textColor = "#1F2937", borderColor = "#D7DEE7";
const bodyFont = "Microsoft YaHei";
const formatTable = (sheet, header, body) => {
  sheet.getRange(header).format = { fill: blue, font: { name: bodyFont, size: 10, bold: true, color: "#FFFFFF" }, horizontalAlignment: "center", verticalAlignment: "center", wrapText: true, borders: { preset: "outside", style: "thin", color: borderColor } };
  sheet.getRange(header).format.rowHeight = 38;
  sheet.getRange(body).format = { font: { name: bodyFont, size: 9, color: textColor }, verticalAlignment: "top", wrapText: true, borders: { insideHorizontal: { style: "thin", color: borderColor } } };
  sheet.getRange(body).format.rowHeight = 52;
  sheet.freezePanes.freezeRows(1); sheet.freezePanes.freezeColumns(3); sheet.showGridLines = false;
};

const goldSheet = workbook.worksheets.add("外部盲测金标准");
goldSheet.getRange("A1:O1").values = [["岗位ID", "公司", "岗位名称", "来源平台", "人工岗位大类", "人工细分方向", "人工每周天数", "人工最低月数", "硬约束结论", "Bad Case类型", "分类依据", "时间证据原文", "复核备注", "复核状态", "标注版本"]];
goldSheet.getRange("A2:O27").values = labels.map((label) => { const source = recordById.get(label.job_id); return [label.job_id, source.company, source.role_title, source.source_platform, label.role_family, label.sub_direction, label.weekly_days, label.minimum_months, label.constraint_result, label.bad_case_type, label.role_basis, label.schedule_evidence, label.review_notes, "已人工复核", "external-gold-v1"]; });
formatTable(goldSheet, "A1:O1", "A2:O27");
goldSheet.getRange("A2:A27").format.fill = paleBlue; goldSheet.getRange("N2:O27").format.fill = paleGreen;
goldSheet.getRange("A:A").format.columnWidth = 11; goldSheet.getRange("B:B").format.columnWidth = 20; goldSheet.getRange("C:C").format.columnWidth = 36; goldSheet.getRange("D:D").format.columnWidth = 13;
goldSheet.getRange("E:F").format.columnWidth = 30; goldSheet.getRange("G:H").format.columnWidth = 15; goldSheet.getRange("I:I").format.columnWidth = 16; goldSheet.getRange("J:J").format.columnWidth = 24;
goldSheet.getRange("K:M").format.columnWidth = 46; goldSheet.getRange("N:O").format.columnWidth = 18;
for (let index = 0; index < labels.length; index += 1) { const value = labels[index].constraint_result; goldSheet.getRange(`I${index + 2}`).format = value === "通过" ? { fill: paleGreen, font: { name: bodyFont, size: 9, bold: true, color: "#166534" } } : value === "不通过" ? { fill: paleRed, font: { name: bodyFont, size: 9, bold: true, color: "#9B1C1C" } } : { fill: paleYellow, font: { name: bodyFont, size: 9, bold: true, color: "#7C5700" } }; }
goldSheet.tables.add("A1:O27", true, "ExternalGoldTable").style = "TableStyleMedium2";

const evalSheet = workbook.worksheets.add("外部盲测评测报告");
evalSheet.getRange("A1:F1").merge(); evalSheet.getRange("A1").values = [["跨平台外部盲测结果｜rule-baseline-v1"]];
evalSheet.getRange("A1:F1").format = { fill: navy, font: { name: bodyFont, size: 15, bold: true, color: "#FFFFFF" }, verticalAlignment: "center" }; evalSheet.getRange("A1:F1").format.rowHeight = 34;
evalSheet.getRange("A3:F3").values = [["指标", "正确数", "样本数", "准确率", "评测口径", "结论"]];
const metricRows = [
  ["岗位大类", report.metrics.role_family, "六类岗位，按核心交付物"], ["每周天数", report.metrics.weekly_days, "保守口径标准化整数"],
  ["最低月数", report.metrics.minimum_months, "摘要优先，冲突保留"], ["硬约束结论", report.metrics.constraint_result, "通过 / 需要核实 / 不通过"],
  ["Bad Case识别", report.metrics.bad_case_binary, "是否存在冲突或边界问题"], ["Bad Case类型", report.metrics.bad_case_type, "完整类型精确匹配"],
];
evalSheet.getRange("A4:F9").values = metricRows.map(([name, value, scope]) => [name, value.correct, value.total, value.accuracy, scope, value.accuracy >= 0.8 ? "较稳定" : value.accuracy >= 0.6 ? "可用但需改进" : "泛化不足"]);
formatTable(evalSheet, "A3:F3", "A4:F9"); evalSheet.getRange("D4:D9").setNumberFormat("0.0%"); evalSheet.getRange("A:A").format.columnWidth = 21; evalSheet.getRange("B:C").format.columnWidth = 12; evalSheet.getRange("D:D").format.columnWidth = 14; evalSheet.getRange("E:E").format.columnWidth = 36; evalSheet.getRange("F:F").format.columnWidth = 18;
evalSheet.getRange("A4:F9").format.rowHeight = 30;
evalSheet.getRange("A11:F11").merge(); evalSheet.getRange("A11").values = [["结论：跨平台外部盲测揭示了真实泛化缺口，尤其是智联时间字段、技术边界岗和标题与核心交付不一致的岗位。"]];
evalSheet.getRange("A11:F11").format = { fill: paleYellow, font: { name: bodyFont, size: 10, bold: true, color: "#7C5700" }, wrapText: true, verticalAlignment: "center" }; evalSheet.getRange("A11:F11").format.rowHeight = 34;
evalSheet.getRange("A13:F13").values = [["样本数", "实习僧", "智联招聘", "牛客网", "错误字段数", "预测状态"]];
evalSheet.getRange("A14:F14").values = [[26, 10, 8, 8, errors.length, "冻结未回写"]];
evalSheet.getRange("A13:F13").format = { fill: blue, font: { name: bodyFont, size: 10, bold: true, color: "#FFFFFF" }, horizontalAlignment: "center" };
evalSheet.getRange("A14:F14").format = { fill: paleGray, font: { name: bodyFont, size: 10, color: textColor }, horizontalAlignment: "center" }; evalSheet.showGridLines = false;

const errorSheet = workbook.worksheets.add("外部盲测错误清单");
errorSheet.getRange("A1:F1").values = [["岗位ID", "错误字段", "人工金标准", "冻结预测", "岗位名称", "诊断"]];
errorSheet.getRange(`A2:F${errors.length + 1}`).values = errors.map((row) => [row.job_id, row.field, row.expected, row.actual ?? "未抽取", row.role_title, row.field === "每周天数" && row.actual == null ? "旧规则不识别智联的独立字段格式" : row.field === "岗位大类" ? "标题关键词不能代表核心交付物" : "规则无法完整表达语义或冲突口径"]);
formatTable(errorSheet, "A1:F1", `A2:F${errors.length + 1}`); errorSheet.getRange("A:A").format.columnWidth = 11; errorSheet.getRange("B:B").format.columnWidth = 18; errorSheet.getRange("C:D").format.columnWidth = 30; errorSheet.getRange("E:E").format.columnWidth = 38; errorSheet.getRange("F:F").format.columnWidth = 48;
errorSheet.tables.add(`A1:F${errors.length + 1}`, true, "ExternalErrorsTable").style = "TableStyleMedium2";

const info = workbook.worksheets.getItem("项目说明"); info.getRange("A1").values = [["AI 实习雷达｜岗位数据集 v0.8"]]; info.getRange("B4").values = [["v0.8"]];
info.getRange("A33").values = [["跨平台外部盲测｜预测已冻结，人工金标准已完成"]];
info.getRange("A38:D38").merge(); info.getRange("A38").values = [[`外部评测：岗位大类 ${(report.metrics.role_family.accuracy * 100).toFixed(1)}%｜天数 ${(report.metrics.weekly_days.accuracy * 100).toFixed(1)}%｜月数 ${(report.metrics.minimum_months.accuracy * 100).toFixed(1)}%｜硬约束 ${(report.metrics.constraint_result.accuracy * 100).toFixed(1)}%｜Bad Case类型 ${(report.metrics.bad_case_type.accuracy * 100).toFixed(1)}%`]];
info.getRange("A38:D38").format = { fill: paleGreen, font: { name: bodyFont, size: 10, bold: true, color: "#166534" }, wrapText: true, verticalAlignment: "center" }; info.getRange("A38:D38").format.rowHeight = 30;

const checks = [["外部盲测金标准", "A1:O27"], ["外部盲测评测报告", "A1:F14"], ["外部盲测错误清单", `A1:F${errors.length + 1}`], ["项目说明", "A28:D38"]];
for (const [sheetName, range] of checks) { const check = await workbook.inspect({ kind: "table", range: `${sheetName}!${range}`, include: "values,formulas", tableMaxRows: 28, tableMaxCols: 15, tableMaxCellChars: 90, maxChars: 12000 }); console.log(check.ndjson); const preview = await workbook.render({ sheetName, range, scale: 0.8, format: "png" }); await fs.writeFile(path.join(previewDir, `${sheetName}.png`), new Uint8Array(await preview.arrayBuffer())); }
const scan = await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 300 }, summary: "v0.8 formula error scan" }); console.log(scan.ndjson);
const output = await SpreadsheetFile.exportXlsx(workbook); await output.save(outputPath);
const exported = await SpreadsheetFile.importXlsx(await FileBlob.load(outputPath)); const exportedScan = await exported.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 300 }, summary: "post-export formula error scan" }); console.log(exportedScan.ndjson);
console.log(JSON.stringify(report, null, 2)); console.log(`Saved ${outputPath}`);
