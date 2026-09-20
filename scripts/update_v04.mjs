import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const projectDir = path.resolve(scriptDir, "..");
const workspaceDir = path.resolve(projectDir, "..");
const outputDir = path.join(workspaceDir, "outputs", "ai-intern-radar");
const inputPath = path.join(outputDir, "AI实习岗位数据集_v0.3.xlsx");
const outputPath = path.join(outputDir, "AI实习岗位数据集_v0.4.xlsx");
const previewDir = path.join(projectDir, "tmp", "v04_qa");
const inspectOnly = process.argv.includes("--inspect-only");

await fs.mkdir(previewDir, { recursive: true });
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));

const sheetNames = ["项目说明", "原始JD", "结构化岗位", "首轮标注任务"];
const previewRanges = {
  项目说明: "A1:D26",
  原始JD: "A1:J8",
  结构化岗位: "A1:X12",
  首轮标注任务: "A1:O11",
};

async function renderSheets(prefix) {
  for (const sheetName of sheetNames) {
    const preview = await workbook.render({
      sheetName,
      range: previewRanges[sheetName],
      scale: 1,
      format: "png",
    });
    const filename = `${prefix}_${sheetName}.png`;
    await fs.writeFile(path.join(previewDir, filename), new Uint8Array(await preview.arrayBuffer()));
  }
}

if (inspectOnly) {
  await renderSheets("before");
  const overview = await workbook.inspect({
    kind: "sheet,table",
    maxChars: 7000,
    tableMaxRows: 4,
    tableMaxCols: 16,
    tableMaxCellChars: 100,
  });
  console.log(overview.ndjson);
  const annotation = await workbook.inspect({
    kind: "table",
    range: "首轮标注任务!A1:O11",
    include: "values,formulas",
    tableMaxRows: 12,
    tableMaxCols: 15,
    maxChars: 18000,
  });
  console.log(annotation.ndjson);
  const styles = await workbook.inspect({
    kind: "computedStyle",
    sheetId: "首轮标注任务",
    range: "A1:O3",
    maxChars: 6000,
  });
  console.log(styles.ndjson);
  console.log(`Rendered v0.3 previews to ${previewDir}`);
  process.exit(0);
}

const info = workbook.worksheets.getItem("项目说明");
const raw = workbook.worksheets.getItem("原始JD");
const processed = workbook.worksheets.getItem("结构化岗位");
const annotation = workbook.worksheets.getItem("首轮标注任务");

const rawRows = raw.getRange("A2:J31").values;
const processedRows = processed.getRange("A2:X31").values;
const rawById = new Map(rawRows.map((row) => [row[0], row]));
const processedById = new Map(processedRows.map((row) => [row[0], row]));

const reviews = [
  {
    id: "J001",
    family: "大模型评测、训练与数据质量",
    direction: "模型评测",
    days: 5,
    months: 4,
    result: "不通过",
    badCase: "摘要正文冲突",
    evidence: "北京5天/周4个月；为期3个月及以上的项目实践机会。",
    note: "周期冲突，按保守口径记4个月；每周5天超过候选人上限。",
  },
  {
    id: "J003",
    family: "AI行业研究与战略分析",
    direction: "AI产业研究",
    days: 3,
    months: 3,
    result: "通过",
    badCase: "无",
    evidence: "实习期不少于3个月，每周不少于3天。",
    note: "时间符合；核心交付是AI行业信息整理与研究报告。",
  },
  {
    id: "J004",
    family: "AI产品与Agent产品",
    direction: "AI产品助理",
    days: 3,
    months: 6,
    result: "需要核实",
    badCase: "摘要正文冲突",
    evidence: "北京3天/周6个月；每周实习3天及以上、持续3个月以上。",
    note: "周期冲突，按保守口径记6个月；需向招聘方核实。",
  },
  {
    id: "J005",
    family: "AI产品与Agent产品",
    direction: "AI Agent产品与交付",
    days: 5,
    months: 3,
    result: "需要核实",
    badCase: "摘要正文冲突",
    evidence: "北京4天/周3个月；每周需出勤4~5天。",
    note: "天数冲突；候选人只能每周4天，需确认能否固定4天。",
  },
  {
    id: "J007",
    family: "AI产品与Agent产品",
    direction: "Agent产品策略",
    days: 5,
    months: 3,
    result: "不通过",
    badCase: "无",
    evidence: "北京5天/周3个月；参与AI Agent产品机制与编排设计。",
    note: "产品策略是核心交付，但每周5天超过候选人上限。",
  },
  {
    id: "J015",
    family: "大模型评测、训练与数据质量",
    direction: "大模型数据与Benchmark",
    days: 4,
    months: 4,
    result: "通过",
    badCase: "摘要正文冲突",
    evidence: "北京4天/周4个月；每周到岗4天以上，实习期不少于3个月。",
    note: "周期摘要与正文不同，按4个月记录；每周4天可满足最低要求。",
  },
  {
    id: "J016",
    family: "数据分析与商业/经营分析",
    direction: "数据治理",
    days: 5,
    months: 3,
    result: "不通过",
    badCase: "摘要正文冲突",
    evidence: "北京5天/周3个月；150-200元/天；底薪3500+绩效500。",
    note: "每周5天超过候选人上限；日薪与月薪口径冲突。",
  },
  {
    id: "J024",
    family: "AI运营、知识库与增长运营",
    direction: "垂直场景AI运营",
    days: 5,
    months: 5,
    result: "不通过",
    badCase: "无",
    evidence: "北京5天/周5个月；参与知识库建设、评测集构建、Prompt优化与效果验证。",
    note: "工作内容高度匹配，但每周天数和实习周期均超过候选人上限。",
  },
  {
    id: "J027",
    family: "数据分析与商业/经营分析",
    direction: "业务数据分析",
    days: 5,
    months: 3,
    result: "不通过",
    badCase: "摘要正文冲突",
    evidence: "北京4天/周3个月；每周工作5天，总实习期不低于3个月。",
    note: "天数冲突，按正文硬要求记每周5天，因此不通过。",
  },
  {
    id: "J029",
    family: "大模型评测、训练与数据质量",
    direction: "Agent质量与知识管理",
    days: 3,
    months: 3,
    result: "通过",
    badCase: "无",
    evidence: "每周可实习至少3天，连续实习3个月以上，能够实习6个月者优先。",
    note: "每周3天、连续3个月是硬要求；6个月仅为优先条件，不应误判为硬门槛。",
  },
];

const staticContextRows = reviews.map((review) => {
  const rawRow = rawById.get(review.id);
  const processedRow = processedById.get(review.id);
  if (!rawRow || !processedRow) throw new Error(`Missing source row for ${review.id}`);
  return [
    review.id,
    processedRow[1],
    processedRow[2],
    rawRow[2],
    processedRow[10],
    processedRow[11],
  ];
});
annotation.getRange("A2:F11").values = staticContextRows;
annotation.getRange("G2:O11").values = reviews.map((review) => [
  review.family,
  review.direction,
  review.days,
  review.months,
  review.result,
  review.badCase,
  review.evidence,
  review.note,
  "已复核",
]);
annotation.getRange("A2:O11").format.rowHeight = 48;

const sampledIds = new Set(reviews.map((review) => review.id));
const scheduleValues = processedRows.map((row) => {
  const days = row[7];
  const months = row[8];
  if (days === null || days === "" || months === null || months === "") return ["待补全"];
  return [Number(days) <= 4 && Number(months) <= 4 ? "摘要初筛通过" : "摘要初筛不通过"];
});
processed.getRange("N2:N31").values = scheduleValues;
processed.getRange("M2:M31").values = processedRows.map((row) => [
  sampledIds.has(row[0]) ? "已人工复核" : row[12],
]);

const missingLinks = rawRows.filter((row) => row[5] === null || row[5] === "").length;
const missingPublishedDates = rawRows.filter((row) => row[6] === null || row[6] === "").length;
const conflictCount = processedRows.filter((row) => row[14] === "是").length;
const initialPassCount = scheduleValues.filter(([value]) => value === "摘要初筛通过").length;
const familyCounts = new Map();
for (const row of processedRows) {
  familyCounts.set(row[10], (familyCounts.get(row[10]) ?? 0) + 1);
}

info.getRange("A1").values = [["AI 实习雷达｜岗位数据集 v0.4"]];
info.getRange("B4").values = [["v0.4"]];
info.getRange("D4").values = [[rawRows.length]];
info.getRange("B14:B17").values = [[missingLinks], [missingPublishedDates], [conflictCount], [initialPassCount]];
info.getRange("D16").values = [["首轮10条已复核"]];
info.getRange("B21:B26").values = info.getRange("A21:A26").values.map(([family]) => [familyCounts.get(family) ?? 0]);

await renderSheets("after");

const annotationCheck = await workbook.inspect({
  kind: "table",
  range: "首轮标注任务!A1:O11",
  include: "values,formulas",
  tableMaxRows: 12,
  tableMaxCols: 15,
  maxChars: 22000,
});
console.log(annotationCheck.ndjson);

const infoCheck = await workbook.inspect({
  kind: "table",
  range: "项目说明!A1:D26",
  include: "values,formulas",
  tableMaxRows: 26,
  tableMaxCols: 4,
  maxChars: 12000,
});
console.log(infoCheck.ndjson);

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
const exportedReview = await exportedWorkbook.inspect({
  kind: "table",
  range: "首轮标注任务!A1:O11",
  include: "values,formulas",
  tableMaxRows: 12,
  tableMaxCols: 15,
  maxChars: 5000,
});
console.log(exportedReview.ndjson);
console.log(`Saved ${outputPath}`);
