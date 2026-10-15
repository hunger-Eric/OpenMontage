import { runMediaCli } from "./media.js";
try {
  await runMediaCli(process.argv.slice(2), { write: text => process.stdout.write(text) });
} catch (error) {
  process.stderr.write(String(error instanceof Error ? error.message : error));
  process.exitCode = 1;
}
