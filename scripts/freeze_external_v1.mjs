import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { predict } from "./baseline_rules_v1.mjs";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const projectDir = path.resolve(scriptDir, "..");
const dataDir = path.join(projectDir, "data");
const inputPath = path.join(dataDir, "external_jd_v1.jsonl");
const outputPath = path.join(dataDir, "external_predictions_frozen_v1.jsonl");
const metadataPath = path.join(dataDir, "external_predictions_frozen_v1.meta.json");
const rulesPath = path.join(scriptDir, "baseline_rules_v1.mjs");

const hash = (buffer) => crypto.createHash("sha256").update(buffer).digest("hex");
const inputBuffer = await fs.readFile(inputPath);
const rulesBuffer = await fs.readFile(rulesPath);
const rows = inputBuffer.toString("utf8").trim().split(/\r?\n/).map(JSON.parse);
if (rows.length !== 26) throw new Error(`Expected 26 external records, found ${rows.length}`);

const predictions = rows.map((row) => ({
  ...predict({ ...row, split: "external_blind_v1" }),
  prediction_version: "rule-baseline-v1",
  frozen: true,
}));
const outputText = `${predictions.map((row) => JSON.stringify(row)).join("\n")}\n`;
const frozenAt = new Date().toISOString();
const metadata = {
  dataset: "external_jd_v1",
  evaluation_scope: "cross_platform_external_blind_test",
  answer_status_at_freeze: "not_labeled",
  prediction_version: "rule-baseline-v1",
  prediction_count: predictions.length,
  frozen_at: frozenAt,
  constraints: { max_weekly_days: 4, min_months: 2, max_months: 4 },
  source_platforms: ["实习僧", "智联招聘", "牛客网"],
  hashes: {
    input_sha256: hash(inputBuffer),
    rules_sha256: hash(rulesBuffer),
    predictions_sha256: hash(Buffer.from(outputText, "utf8")),
  },
  immutable_note: "该文件是人工查看或标注外部样本答案前生成的冻结预测。后续评测不得回写或覆盖。",
};

for (const target of [outputPath, metadataPath]) {
  try {
    await fs.access(target);
    throw new Error(`Refusing to overwrite frozen artifact: ${target}`);
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }
}
await fs.writeFile(outputPath, outputText, "utf8");
await fs.writeFile(metadataPath, `${JSON.stringify(metadata, null, 2)}\n`, "utf8");
console.log(JSON.stringify(metadata, null, 2));
