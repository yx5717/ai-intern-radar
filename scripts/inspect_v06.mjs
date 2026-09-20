import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const workspaceDir = path.resolve(".");
const inputPath = path.join(workspaceDir, "outputs", "ai-intern-radar", "AI实习岗位数据集_v0.6.xlsx");
const previewDir = path.join(workspaceDir, "ai-intern-radar", "tmp", "v07_before_qa");
await fs.mkdir(previewDir, { recursive: true });
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));
const overview = await workbook.inspect({ kind: "sheet", include: "id,name", maxChars: 6000 });
console.log(overview.ndjson);
const names = ["项目说明", "原始JD", "结构化岗位", "首轮标注任务", "人工标注金标准", "规则基线预测", "基线评测报告", "测试集错误清单"];
for (const name of names) {
  const sheet = workbook.worksheets.getItem(name);
  const used = sheet.getUsedRange();
  const preview = await workbook.render({ sheetName: name, range: used.address, scale: 0.7, format: "png" });
  await fs.writeFile(path.join(previewDir, `${name}.png`), new Uint8Array(await preview.arrayBuffer()));
  console.log(`${name}\t${used.address}`);
}
