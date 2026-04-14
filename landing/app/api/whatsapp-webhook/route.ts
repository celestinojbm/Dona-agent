import { NextRequest, NextResponse } from "next/server";

const RENDER_WEBHOOK_URL = "https://dona-agent.onrender.com/webhook";

// ── Rate limiting simple por IP (en memoria del edge worker) ──────────────
// Límite: 30 requests por minuto por IP (Meta envía ráfagas pero no tanto)
const RATE_LIMIT_WINDOW_MS = 60_000;
const RATE_LIMIT_MAX = 30;
const ipRequests = new Map<string, { count: number; resetAt: number }>();

function checkRateLimit(ip: string): boolean {
  const now = Date.now();
  const entry = ipRequests.get(ip);

  if (!entry || now > entry.resetAt) {
    ipRequests.set(ip, { count: 1, resetAt: now + RATE_LIMIT_WINDOW_MS });
    return true;
  }

  entry.count++;
  return entry.count <= RATE_LIMIT_MAX;
}

// Limpiar entradas expiradas cada 5 minutos (evitar memory leak)
setInterval(() => {
  const now = Date.now();
  for (const [ip, entry] of ipRequests) {
    if (now > entry.resetAt) ipRequests.delete(ip);
  }
}, 5 * 60_000);

export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams.toString();
  const res = await fetch(`${RENDER_WEBHOOK_URL}?${params}`, {
    headers: Object.fromEntries(request.headers),
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}

export async function POST(request: NextRequest) {
  // Rate limiting por IP
  const ip = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || "unknown";
  if (!checkRateLimit(ip)) {
    return NextResponse.json(
      { error: "Too many requests" },
      { status: 429 }
    );
  }

  const body = await request.text();

  // Validación básica: rechazar payloads vacíos o muy grandes (>1MB)
  if (!body || body.length < 2) {
    return NextResponse.json({ error: "Empty payload" }, { status: 400 });
  }
  if (body.length > 1_048_576) {
    return NextResponse.json({ error: "Payload too large" }, { status: 413 });
  }

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  // Forward Meta's HMAC signature so Render can verify authenticity
  const signature = request.headers.get("X-Hub-Signature-256");
  if (signature) {
    headers["X-Hub-Signature-256"] = signature;
  }
  const res = await fetch(RENDER_WEBHOOK_URL, {
    method: "POST",
    headers,
    body,
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
