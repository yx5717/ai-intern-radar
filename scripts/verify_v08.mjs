import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const workspaceDir = path.resolve(".");
const inputPath = path.join(workspaceDir, "outputs", "ai-intern-radar", "AI实习岗位数据集_v0.8.xlsx");
const previewDir = path.join(workspaceDir, "ai-intern-radar", "tmp", "v08_all_sheets_qa");
await fs.mkdir(previewDir, { recursive: true });
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));
const rendered = [];
for (const sheet of workbook.worksheets) {
  const used = sheet.getUsedRange();
  const preview = await workbook.render({ sheetName: sheet.name, range: used.address, scale: 0.55, format: "png" });
  const filename = `${String(rendered.length + 1).padStart(2, "0")}_${sheet.name}.png`;
  await fs.writeFile(path.join(previewDir, filename), new Uint8Array(await preview.arrayBuffer()));
  rendered.push({ sheet: sheet.name, range: used.address, file: filename });
}
const errors = await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A", options: { useRegex: true, maxResults: 300 }, summary: "v0.8 all-sheet formula error scan" });
console.log(JSON.stringify({ rendered, formula_scan: errors.ndjson }, null, 2));
