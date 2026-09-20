import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const workspaceDir = path.resolve(".");
const projectDir = path.join(workspaceDir, "ai-intern-radar");
const dataDir = path.join(projectDir, "data");
const outputDir = path.join(workspaceDir, "outputs", "ai-intern-radar");
const previewDir = path.join(projectDir, "tmp", "v07_qa");
const inputPath = path.join(outputDir, "AI实习岗位数据集_v0.6.xlsx");
const outputPath = path.join(outputDir, "AI实习岗位数据集_v0.7.xlsx");

const parseJsonl = async (file) => (await fs.readFile(file, "utf8"))
  .replace(/^\uFEFF/, "").trim().split(/\r?\n/).map(JSON.parse);
const records = await parseJsonl(path.join(dataDir, "external_jd_v1.jsonl"));
const predictions = await parseJsonl(path.join(dataDir, "external_predictions_frozen_v1.jsonl"));
const metadata = JSON.parse(await fs.readFile(path.join(dataDir, "external_predictions_frozen_v1.meta.json"), "utf8"));
if (records.length !== 26 || predictions.length !== 26) throw new Error("External records and predictions must each contain 26 rows.");

await fs.mkdir(previewDir, { recursive: true });
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));
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

const styleSheet = (sheet, headerRange, bodyRange) => {
  sheet.getRange(headerRange).format = {
    fill: blue,
    font: { name: bodyFont, size: 10, bold: true, color: "#FFFFFF" },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
    borders: { preset: "outside", style: "thin", color: borderColor },
  };
  sheet.getRange(headerRange).format.rowHeight = 38;
  sheet.getRange(bodyRange).format = {
    font: { name: bodyFont, size: 9, color: textColor },
    verticalAlignment: "top",
    wrapText: true,
    borders: { insideHorizontal: { style: "thin", color: borderColor } },
  };
  sheet.getRange(bodyRange).format.rowHeight = 54;
  sheet.freezePanes.freezeRows(1);
  sheet.freezePanes.freezeColumns(3);
  sheet.showGridLines = false;
};

const raw = workbook.worksheets.add("外部盲测原始JD");
raw.getRange("A1:J1").values = [[
  "岗位ID", "公司", "岗位名称", "来源平台", "发布日期", "采集日期", "原岗位链接", "摘要原文", "JD原文", "数据状态",
]];
raw.getRange("A2:J27").values = records.map((row) => [
  row.job_id, row.company, row.role_title, row.source_platform, row.published_at ?? "", row.collected_at,
  row.source_url ?? "", row.raw_meta, row.jd_raw, row.parsing_status,
]);
styleSheet(raw, "A1:J1", "A2:J27");
raw.getRange("A2:A27").format.fill = paleBlue;
raw.getRange("D2:D27").format.fill = paleGray;
raw.getRange("J2:J27").format.fill = paleYellow;
raw.getRange("A:A").format.columnWidth = 11;
raw.getRange("B:B").format.columnWidth = 20;
raw.getRange("C:C").format.columnWidth = 36;
raw.getRange("D:D").format.columnWidth = 13;
raw.getRange("E:F").format.columnWidth = 14;
raw.getRange("G:G").format.columnWidth = 18;
raw.getRange("H:H").format.columnWidth = 48;
raw.getRange("I:I").format.columnWidth = 90;
raw.getRange("J:J").format.columnWidth = 22;
raw.getRange("E2:F27").setNumberFormat("yyyy-mm-dd");
raw.tables.add("A1:J27", true, "ExternalRawTable").style = "TableStyleMedium2";

const frozen = workbook.worksheets.add("外部盲测冻结预测");
frozen.getRange("A1:L1").values = [[
  "岗位ID", "公司", "岗位名称", "来源平台", "预测岗位大类", "预测细分方向", "预测每周天数", "预测最低月数",
  "预测硬约束", "预测Bad Case", "时间证据", "冻结状态",
]];
const recordById = new Map(records.map((row) => [row.job_id, row]));
frozen.getRange("A2:L27").values = predictions.map((prediction) => {
  const source = recordById.get(prediction.job_id);
  return [prediction.job_id, source.company, source.role_title, source.source_platform, prediction.role_family,
    prediction.sub_direction, prediction.weekly_days, prediction.minimum_months, prediction.constraint_result,
    prediction.bad_case_type, prediction.evidence, "已冻结｜答案未标注"];
});
styleSheet(frozen, "A1:L1", "A2:L27");
frozen.getRange("A2:A27").format.fill = paleBlue;
frozen.getRange("L2:L27").format = { fill: paleYellow, font: { name: bodyFont, size: 9, bold: true, color: "#7C5700" } };
for (let index = 0; index < predictions.length; index += 1) {
  const result = predictions[index].constraint_result;
  frozen.getRange(`I${index + 2}`).format = result === "通过"
    ? { fill: paleGreen, font: { name: bodyFont, size: 9, color: "#166534", bold: true } }
    : result === "不通过"
      ? { fill: paleRed, font: { name: bodyFont, size: 9, color: "#9B1C1C", bold: true } }
      : { fill: paleYellow, font: { name: bodyFont, size: 9, color: "#7C5700", bold: true } };
}
frozen.getRange("A:A").format.columnWidth = 11;
frozen.getRange("B:B").format.columnWidth = 20;
frozen.getRange("C:C").format.columnWidth = 36;
frozen.getRange("D:D").format.columnWidth = 13;
frozen.getRange("E:F").format.columnWidth = 30;
frozen.getRange("G:H").format.columnWidth = 15;
frozen.getRange("I:I").format.columnWidth = 16;
frozen.getRange("J:J").format.columnWidth = 20;
frozen.getRange("K:K").format.columnWidth = 60;
frozen.getRange("L:L").format.columnWidth = 23;
frozen.tables.add("A1:L27", true, "ExternalFrozenPredictionsTable").style = "TableStyleMedium2";

const info = workbook.worksheets.getItem("项目说明");
info.getRange("A1").values = [["AI 实习雷达｜岗位数据集 v0.7"]];
info.getRange("B4").values = [["v0.7"]];
info.getRange("A33:D33").merge();
info.getRange("A33").values = [["跨平台外部盲测｜预测已冻结，答案尚未标注"]];
info.getRange("A33:D33").format = { fill: paleBlue, font: { name: bodyFont, size: 11, bold: true, color: navy }, verticalAlignment: "center" };
info.getRange("A33:D33").format.rowHeight = 26;
info.getRange("A34:D34").values = [["外部样本", "来源平台", "冻结版本", "冻结时间（UTC）"]];
info.getRange("A34:D34").format = { fill: blue, font: { name: bodyFont, size: 10, bold: true, color: "#FFFFFF" }, horizontalAlignment: "center", verticalAlignment: "center" };
info.getRange("A35:D35").values = [[26, "实习僧 / 智联招聘 / 牛客网", metadata.prediction_version, `UTC ${metadata.frozen_at.replace("T", " ").replace("Z", "")}`]];
info.getRange("A35:D35").format = { font: { name: bodyFont, size: 9, color: textColor }, horizontalAlignment: "center", wrapText: true };
info.getRange("A36:D36").merge();
info.getRange("A36").values = [[`规则 SHA-256：${metadata.hashes.rules_sha256}`]];
info.getRange("A37:D37").merge();
info.getRange("A37").values = [["盲测纪律：人工金标准建立后，不得修改或覆盖本批冻结预测；规则改进另开版本评估。"]];
info.getRange("A36:D37").format = { fill: paleGray, font: { name: bodyFont, size: 9, color: textColor }, wrapText: true, verticalAlignment: "center" };
info.getRange("A36:D37").format.rowHeight = 28;

const checks = [
  ["外部盲测原始JD", "A1:J27"],
  ["外部盲测冻结预测", "A1:L27"],
  ["项目说明", "A28:D37"],
];
for (const [sheetName, range] of checks) {
  const result = await workbook.inspect({ kind: "table", range: `${sheetName}!${range}`, include: "values,formulas", tableMaxRows: 27, tableMaxCols: 12, tableMaxCellChars: 100, maxChars: 10000 });
  console.log(result.ndjson);
  const preview = await workbook.render({ sheetName, range, scale: 0.8, format: "png" });
  await fs.writeFile(path.join(previewDir, `${sheetName}.png`), new Uint8Array(await preview.arrayBuffer()));
}
const errors = await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 300 }, summary: "v0.7 formula error scan" });
console.log(errors.ndjson);

await fs.mkdir(outputDir, { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
const exported = await SpreadsheetFile.importXlsx(await FileBlob.load(outputPath));
const exportedErrors = await exported.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 300 }, summary: "post-export formula error scan" });
console.log(exportedErrors.ndjson);
console.log(`Saved ${outputPath}`);
