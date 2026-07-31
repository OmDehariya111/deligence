import type { Metadata } from "next";
import { Navbar } from "@/components/site/Navbar";
import { Hero } from "@/components/site/Hero";
import { HowItWorks } from "@/components/site/HowItWorks";
import { FeatureGrid } from "@/components/site/FeatureGrid";
import { SampleReport } from "@/components/site/SampleReport";
import { Comparison } from "@/components/site/Comparison";
import { Pricing } from "@/components/site/Pricing";
import { About } from "@/components/site/About";
import { FinalCta } from "@/components/site/FinalCta";
import { Footer } from "@/components/site/Footer";
import { ScrollProgress } from "@/components/site/ScrollProgress";
import { PageTransition } from "@/components/site/PageTransition";

export const metadata: Metadata = {
  title: "DeligenX - An AI Powered Due Deligence Platform",
  description:
    "Turn any US ticker into an institutional-grade investment memorandum in minutes. Autonomous 5-agent AI, SEC-cited, deterministic risk models.",
  openGraph: {
    title: "DeligenX - An AI Powered Due Deligence Platform",
    description:
      "Autonomous due diligence. Institutional grade. Minutes, not weeks.",
  },
};

export default function HomePage() {
  return (
    <div className="relative min-h-screen bg-background text-foreground">
      <ScrollProgress />
      <Navbar />
      <main>
        <PageTransition>
          <Hero />
          <HowItWorks />
          <FeatureGrid />
          <SampleReport />
          <Comparison />
          <Pricing />
          <About />
          <FinalCta />
        </PageTransition>
      </main>
      <Footer />
    </div>
  );
}
