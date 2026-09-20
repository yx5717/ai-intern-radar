import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";
import { predict } from "./baseline_rules_v1.mjs";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const projectDir = path.resolve(scriptDir, "..");
const workspaceDir = path.resolve(projectDir, "..");
const dataDir = path.join(projectDir, "data");
const outputDir = path.join(workspaceDir, "outputs", "ai-intern-radar");
const previewDir = path.join(projectDir, "tmp", "baseline_v1_qa");
const inputWorkbook = path.join(outputDir, "AI实习岗位数据集_v0.5.xlsx");
const outputWorkbook = path.join(outputDir, "AI实习岗位数据集_v0.6.xlsx");

const rows = (await fs.readFile(path.join(dataDir, "gold_labels_v1.jsonl"), "utf8"))
  .trim()
  .split(/\r?\n/)
  .map(JSON.parse);

const predictions = rows.map((row) => ({ source: row, prediction: predict(row) }));

function evaluate(items) {
  const total = items.length;
  const count = (fn) => items.filter(fn).length;
  const score = (fn) => ({ correct: count(fn), total, accuracy: total ? count(fn) / total : 0 });
  return {
    role_family: score(({ source, prediction }) => source.gold.role_family === prediction.role_family),
    weekly_days: score(({ source, prediction }) => source.gold.weekly_days === prediction.weekly_days),
    minimum_months: score(({ source, prediction }) => source.gold.minimum_months === prediction.minimum_months),
    constraint_result: score(({ source, prediction }) => source.gold.constraint_result === prediction.constraint_result),
    bad_case_binary: score(({ source, prediction }) => (source.gold.bad_case_type !== "无") === (prediction.bad_case_type !== "无")),
    bad_case_type: score(({ source, prediction }) => source.gold.bad_case_type === prediction.bad_case_type),
  };
}

const devItems = predictions.filter(({ source }) => source.split === "dev");
const testItems = predictions.filter(({ source }) => source.split === "test");
const report = {
  baseline_version: "rule-baseline-v1",
  split_version: "split-v1",
  evaluation_scope: "internal_holdout_not_blind",
  caveat: "规则开发者参与了全量标注；测试指标仅用于内部回归，不代表严格外部盲测。",
  constraints: { max_weekly_days: 4, min_months: 2, max_months: 4 },
  dev: evaluate(devItems),
  test: evaluate(testItems),
};

await fs.mkdir(dataDir, { recursive: true });
await fs.writeFile(
  path.join(dataDir, "baseline_predictions_v1.jsonl"),
  `${predictions.map(({ prediction }) => JSON.stringify(prediction)).join("\n")}\n`,
  "utf8",
);
await fs.writeFile(path.join(dataDir, "baseline_eval_v1.json"), `${JSON.stringify(report, null, 2)}\n`, "utf8");
console.log(JSON.stringify(report, null, 2));

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputWorkbook));
const predSheet = workbook.worksheets.add("规则基线预测");
const evalSheet = workbook.worksheets.add("基线评测报告");
const blue = "#2878B5";
const navy = "#173F5F";
const paleBlue = "#EAF2F8";
const paleGreen = "#E8F5E9";
const paleRed = "#FDECEC";
const paleYellow = "#FFF4CC";
const paleGray = "#F5F7FA";
const textColor = "#1F2937";
const borderColor = "#D7DEE7";
const bodyFont = "Microsoft YaHei";

const predHeaders = [
  "岗位ID", "划分", "岗位名称", "金标准大类", "基线预测大类", "大类正确", "金标准天数", "预测天数", "天数正确",
  "金标准月数", "预测月数", "月数正确", "金标准硬约束", "预测硬约束", "结论正确", "金标准Bad Case", "预测Bad Case", "时间证据",
];
predSheet.getRange("A1:R1").values = [predHeaders];
predSheet.getRange("A2:R31").values = predictions.map(({ source, prediction }) => [
  source.job_id,
  source.split,
  source.role_title,
  source.gold.role_family,
  prediction.role_family,
  source.gold.role_family === prediction.role_family ? "是" : "否",
  source.gold.weekly_days,
  prediction.weekly_days,
  source.gold.weekly_days === prediction.weekly_days ? "是" : "否",
  source.gold.minimum_months,
  prediction.minimum_months,
  source.gold.minimum_months === prediction.minimum_months ? "是" : "否",
  source.gold.constraint_result,
  prediction.constraint_result,
  source.gold.constraint_result === prediction.constraint_result ? "是" : "否",
  source.gold.bad_case_type,
  prediction.bad_case_type,
  prediction.evidence,
]);
predSheet.getRange("A1:R1").format = {
  fill: blue,
  font: { name: bodyFont, size: 10, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
  borders: { preset: "outside", style: "thin", color: borderColor },
};
predSheet.getRange("A1:R1").format.rowHeight = 38;
predSheet.getRange("A2:R31").format = {
  font: { name: bodyFont, size: 9, color: textColor },
  verticalAlignment: "top",
  wrapText: true,
  borders: { insideHorizontal: { style: "thin", color: borderColor } },
};
predSheet.getRange("A2:R31").format.rowHeight = 40;
predSheet.getRange("A2:A31").format.fill = paleBlue;
for (const column of ["F", "I", "L", "O"]) {
  predSheet.getRange(`${column}2:${column}31`).conditionalFormats.add("containsText", { text: "否", format: { fill: paleRed, font: { bold: true, color: "#9B1C1C" } } });
  predSheet.getRange(`${column}2:${column}31`).conditionalFormats.add("containsText", { text: "是", format: { fill: paleGreen, font: { bold: true, color: "#166534" } } });
}
predSheet.getRange("B2:B31").conditionalFormats.add("containsText", { text: "test", format: { fill: paleYellow, font: { bold: true, color: "#7C5700" } } });
predSheet.getRange("A:A").format.columnWidth = 9;
predSheet.getRange("B:B").format.columnWidth = 10;
predSheet.getRange("C:C").format.columnWidth = 34;
predSheet.getRange("D:E").format.columnWidth = 26;
predSheet.getRange("F:F").format.columnWidth = 12;
predSheet.getRange("G:O").format.columnWidth = 14;
predSheet.getRange("P:Q").format.columnWidth = 22;
predSheet.getRange("R:R").format.columnWidth = 58;
predSheet.freezePanes.freezeRows(1);
predSheet.freezePanes.freezeColumns(3);
predSheet.tables.add("A1:R31", true, "BaselinePredictionsTable").style = "TableStyleMedium2";
predSheet.showGridLines = false;

evalSheet.getRange("A1:F1").merge();
evalSheet.getRange("A1").values = [["AI 实习雷达｜规则基线评测 v1"]];
evalSheet.getRange("A1:F1").format = {
  fill: navy,
  font: { name: bodyFont, size: 18, bold: true, color: "#FFFFFF" },
  verticalAlignment: "center",
};
evalSheet.getRange("A1:F1").format.rowHeight = 34;
evalSheet.getRange("A3:F3").merge();
evalSheet.getRange("A3").values = [["内部留出集结果｜10条固定样本，仅作回归参考；当前并非严格外部盲测"]];
evalSheet.getRange("A3:F3").format = { fill: paleBlue, font: { name: bodyFont, size: 11, bold: true, color: navy } };
evalSheet.getRange("A4:F4").values = [["评测项", "正确数", "样本数", "准确率", "评测对象", "说明"]];
evalSheet.getRange("A4:F4").format = {
  fill: blue,
  font: { name: bodyFont, size: 10, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
};
const metricDefinitions = [
  ["岗位大类准确率", "role_family", "六类岗位的一级分类"],
  ["每周天数准确率", "weekly_days", "抽取后的标准化整数"],
  ["最低月数准确率", "minimum_months", "按保守口径标准化"],
  ["硬约束结论准确率", "constraint_result", "通过 / 需要核实 / 不通过"],
  ["Bad Case识别准确率", "bad_case_binary", "是否存在冲突或边界问题"],
  ["Bad Case类型准确率", "bad_case_type", "无 / 摘要正文冲突 / 边界分类"],
];
evalSheet.getRange("A5:F10").values = metricDefinitions.map(([label, key, explanation]) => [
  label,
  report.test[key].correct,
  report.test[key].total,
  report.test[key].accuracy,
  "internal test / split-v1",
  explanation,
]);
evalSheet.getRange("D5:D10").format.numberFormat = "0.0%";
evalSheet.getRange("A5:F10").format = {
  font: { name: bodyFont, size: 10, color: textColor },
  verticalAlignment: "center",
  wrapText: true,
  borders: { insideHorizontal: { style: "thin", color: borderColor } },
};
evalSheet.getRange("A5:F10").format.rowHeight = 28;

evalSheet.getRange("A12:F12").merge();
evalSheet.getRange("A12").values = [["基线说明"]];
evalSheet.getRange("A12:F12").format = { fill: paleBlue, font: { name: bodyFont, size: 11, bold: true, color: navy } };
evalSheet.getRange("A13:F16").values = [
  ["版本", "rule-baseline-v1", "输入", "岗位标题 + 摘要 + JD正文", "API依赖", "无"],
  ["候选人约束", "每周最多4天", "周期", "2-4个月", "数据切分", "20 dev / 10 test"],
  ["分类原则", "按核心交付物", "时间原则", "冲突时保守记录", "可协商边界", "标记需要核实"],
  ["用途", "可复现下限（非外部盲测）", "下一步", "引入LLM结构化抽取", "最终验证", "新增未见JD建立外部盲测"],
];
evalSheet.getRange("A13:F16").format = {
  font: { name: bodyFont, size: 9, color: textColor },
  verticalAlignment: "center",
  wrapText: true,
  borders: { insideHorizontal: { style: "thin", color: borderColor } },
};
evalSheet.getRange("A13:A16").format.font = { name: bodyFont, size: 9, bold: true, color: textColor };
evalSheet.getRange("C13:C16").format.font = { name: bodyFont, size: 9, bold: true, color: textColor };
evalSheet.getRange("E13:E16").format.font = { name: bodyFont, size: 9, bold: true, color: textColor };

evalSheet.getRange("A18:F18").merge();
evalSheet.getRange("A18").values = [["测试集错误样本"]];
evalSheet.getRange("A18:F18").format = { fill: paleBlue, font: { name: bodyFont, size: 11, bold: true, color: navy } };
evalSheet.getRange("A19:F19").values = [["岗位ID", "字段", "金标准", "基线预测", "岗位名称", "初步原因"]];
evalSheet.getRange("A19:F19").format = {
  fill: blue,
  font: { name: bodyFont, size: 10, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
};
const errors = [];
for (const { source, prediction } of testItems) {
  const comparisons = [
    ["岗位大类", source.gold.role_family, prediction.role_family],
    ["每周天数", source.gold.weekly_days, prediction.weekly_days],
    ["最低月数", source.gold.minimum_months, prediction.minimum_months],
    ["硬约束结论", source.gold.constraint_result, prediction.constraint_result],
    ["Bad Case类型", source.gold.bad_case_type, prediction.bad_case_type],
  ];
  for (const [field, expected, actual] of comparisons) {
    if (expected !== actual) errors.push([source.job_id, field, expected, actual, source.role_title, "规则无法完整表达语义或口径，需要进入Bad Case分析"]);
  }
}
const errorRows = errors.length ? errors : [["-", "无", "-", "-", "测试集无错误", "当前样本量较小，准确率仅代表本批数据"]];
evalSheet.getRange(`A20:F${19 + errorRows.length}`).values = errorRows;
evalSheet.getRange(`A20:F${19 + errorRows.length}`).format = {
  fill: errors.length ? paleRed : paleGreen,
  font: { name: bodyFont, size: 9, color: textColor },
  verticalAlignment: "top",
  wrapText: true,
  borders: { insideHorizontal: { style: "thin", color: borderColor } },
};
evalSheet.getRange("A:A").format.columnWidth = 24;
evalSheet.getRange("B:C").format.columnWidth = 16;
evalSheet.getRange("D:D").format.columnWidth = 14;
evalSheet.getRange("E:E").format.columnWidth = 30;
evalSheet.getRange("F:F").format.columnWidth = 48;
evalSheet.showGridLines = false;

const info = workbook.worksheets.getItem("项目说明");
info.getRange("A1").values = [["AI 实习雷达｜岗位数据集 v0.6"]];
info.getRange("B4").values = [["v0.6"]];

await fs.mkdir(previewDir, { recursive: true });
const previewRanges = [
  ["项目说明", "A1:D31", "项目说明.png"],
  ["原始JD", "A1:J8", "原始JD.png"],
  ["结构化岗位", "A1:X12", "结构化岗位.png"],
  ["首轮标注任务", "A1:O11", "首轮标注任务.png"],
  ["人工标注金标准", "A1:P16", "人工标注金标准_上.png"],
  ["人工标注金标准", "A17:P31", "人工标注金标准_下.png"],
  ["规则基线预测", "A1:R16", "规则基线预测_上.png"],
  ["规则基线预测", "A17:R31", "规则基线预测_下.png"],
  ["基线评测报告", `A1:F${19 + errorRows.length}`, "基线评测报告.png"],
];
for (const [sheetName, range, filename] of previewRanges) {
  const preview = await workbook.render({ sheetName, range, scale: 1, format: "png" });
  await fs.writeFile(path.join(previewDir, filename), new Uint8Array(await preview.arrayBuffer()));
}

const check = await workbook.inspect({
  kind: "table",
  range: `基线评测报告!A1:F${19 + errorRows.length}`,
  include: "values,formulas",
  tableMaxRows: 30,
  tableMaxCols: 6,
  maxChars: 10000,
});
console.log(check.ndjson);
const formulaErrors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 300 },
  summary: "final formula error scan",
});
console.log(formulaErrors.ndjson);

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputWorkbook);
const exported = await SpreadsheetFile.importXlsx(await FileBlob.load(outputWorkbook));
const exportedErrors = await exported.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 300 },
  summary: "post-export formula error scan",
});
console.log(exportedErrors.ndjson);
console.log(`Saved ${outputWorkbook}`);
