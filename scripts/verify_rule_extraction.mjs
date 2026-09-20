import fs from "node:fs";
import { predict } from "./baseline_rules_v1.mjs";

const parse = (file) => fs.readFileSync(file, "utf8").replace(/^\uFEFF/, "").trim().split(/\r?\n/).map(JSON.parse);
const current = parse("./ai-intern-radar/data/gold_labels_v1.jsonl").map(predict);
const previous = parse("./ai-intern-radar/data/baseline_predictions_v1.jsonl");
console.log(JSON.stringify({ count: current.length, identical: JSON.stringify(current) === JSON.stringify(previous) }));
