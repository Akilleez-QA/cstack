import { randomBytes } from "node:crypto";
export const nowIso = () => new Date().toISOString();
export const decisionId = () => `shd-${new Date().toISOString().replace(/[-:T]/g, "").slice(0, 14)}-${randomBytes(3).toString("hex")}`;
