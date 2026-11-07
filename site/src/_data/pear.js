// The pipeline's output: python -m pear site (writes ../build/site/site.json).
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const file = process.env.PEAR_SITE_JSON || path.join(here, "../../../build/site/site.json");

export default function () {
  return JSON.parse(readFileSync(file, "utf-8"));
}
