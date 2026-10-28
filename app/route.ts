import { readFileSync } from "node:fs";
import { join } from "node:path";

export function GET() {
  const html = readFileSync(join(process.cwd(), "public", "index.html"), "utf8");
  return new Response(html, {
    headers: {
      "Content-Type": "text/html; charset=utf-8",
    },
  });
}
