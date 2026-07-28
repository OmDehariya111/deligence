import { ImageResponse } from "next/og";

export const alt = "DeligenX AI due diligence platform";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpenGraphImage() {
  return new ImageResponse(
    <div style={{ height: "100%", width: "100%", display: "flex", flexDirection: "column", justifyContent: "center", padding: "72px", color: "white", background: "linear-gradient(135deg, #020617, #172554 55%, #312e81)" }}>
      <div style={{ fontSize: 28, color: "#a5b4fc", fontWeight: 700 }}>DELIGENX AI</div>
      <div style={{ display: "flex", flexDirection: "column", marginTop: 28, fontSize: 76, letterSpacing: -3, fontWeight: 800 }}><span>Due diligence,</span><span>made decisive.</span></div>
      <div style={{ marginTop: 28, fontSize: 30, color: "#cbd5e1" }}>Institutional-grade financial intelligence.</div>
    </div>,
    size,
  );
}
