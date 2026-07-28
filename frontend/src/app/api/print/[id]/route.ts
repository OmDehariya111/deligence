import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const pdfUrl = new URL(`/api/v1/jobs/${encodeURIComponent(id)}/pdf`, request.url);
  return NextResponse.redirect(pdfUrl);
}
