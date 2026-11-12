import measured from "@/data/measured.json";
import taskRuns from "@/data/measured-tasks.json";

export { measured, taskRuns };

export const armOrder = ["script_first", "playwright_mcp", "browser_use"] as const;

export type ArmId = (typeof armOrder)[number];

export const armInfo: Record<ArmId, { name: string; role: string; color: string }> = {
  script_first: { name: "script_first", role: "Our approach", color: "var(--color-yours)" },
  playwright_mcp: { name: "Playwright MCP", role: "Baseline", color: "var(--color-arm-mcp)" },
  browser_use: { name: "browser-use", role: "Competitor", color: "var(--color-stop)" },
};

export function seconds(value: number): string {
  return `${value.toFixed(2)}s`;
}

export function dollars(value: number): string {
  return `$${value.toFixed(4)}`;
}

export function oneDecimal(value: number): string {
  return value.toFixed(1);
}

export function share(part: number, whole: number): string {
  return `${((part / whole) * 100).toFixed(1)}%`;
}

export function modelLabel(model: string): string {
  if (model === "gpt-6-luna") return "gpt-6-luna";
  if (model === "gpt-6.1-sol") return "gpt-6.1-sol";
  return model;
}
