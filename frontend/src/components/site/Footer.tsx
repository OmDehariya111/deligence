import { Github, Twitter, Linkedin } from "lucide-react";
import { Logo } from "./Logo";

const cols = [
  {
    title: "Product",
    links: ["Overview", "Live Demo", "Pipeline", "Changelog", "Roadmap"],
  },
  {
    title: "Company",
    links: ["About", "Team", "Careers", "Press", "Contact"],
  },
  {
    title: "Resources",
    links: ["Docs", "API Reference", "Methodology", "Security", "Status"],
  },
];

export function Footer() {
  return (
    <footer className="relative border-t border-[rgba(255,255,255,0.06)]">
      <div className="mx-auto max-w-7xl px-5 py-16 md:px-8">
        <div className="grid grid-cols-2 gap-10 md:grid-cols-5">
          <div className="col-span-2 md:col-span-2">
            <Logo />
            <p className="mt-4 max-w-xs text-sm text-muted-foreground">
              Autonomous due diligence. Institutional grade. Minutes, not weeks.
            </p>
            <div className="mt-6 flex gap-2">
              {[Github, Twitter, Linkedin].map((Icon, i) => (
                <a
                  key={i}
                  href="#"
                  className="grid h-9 w-9 place-items-center rounded-md border border-[rgba(255,255,255,0.08)] text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
                >
                  <Icon className="h-4 w-4" />
                </a>
              ))}
            </div>
          </div>

          {cols.map((col) => (
            <div key={col.title}>
              <div className="font-mono text-[11px] uppercase tracking-wider text-primary/80">
                {col.title}
              </div>
              <ul className="mt-4 space-y-3">
                {col.links.map((l) => (
                  <li key={l}>
                    <a
                      href="#"
                      className="text-sm text-muted-foreground transition-colors hover:text-foreground"
                    >
                      {l}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-14 flex flex-col items-start justify-between gap-3 border-t border-[rgba(255,255,255,0.06)] pt-6 text-xs text-muted-foreground md:flex-row md:items-center">
          <p>© 2026 DeligenX · Built for IITISoC 2026</p>
          <p className="font-mono text-[11px] uppercase tracking-wider">
            v0.1.0 · <span className="text-primary/80">status: operational</span>
          </p>
        </div>
      </div>
    </footer>
  );
}