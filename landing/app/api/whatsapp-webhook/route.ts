import { NextRequest, NextResponse } from "next/server";

const RENDER_WEBHOOK_URL = "https://dona-agent.onrender.com/webhook";

export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams.toString();
  const res = await fetch(`${RENDER_WEBHOOK_URL}?${params}`, {
    headers: Object.fromEntries(request.headers),
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}

export async function POST(request: NextRequest) {
  const body = await request.text();
  const res = await fetch(RENDER_WEBHOOK_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
