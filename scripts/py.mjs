import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");
const backend = path.join(root, "backend");
const win = process.platform === "win32";
const python = path.join(backend, win ? ".venv\\Scripts\\python.exe" : ".venv/bin/python");

if (!existsSync(python)) {
  console.error(`Backend virtualenv not found: ${python}`);
  console.error("Run `npm run backend:install` first.");
  process.exit(1);
}

const result = spawnSync(python, process.argv.slice(2), { stdio: "inherit", cwd: backend });
process.exit(result.status ?? 1);
