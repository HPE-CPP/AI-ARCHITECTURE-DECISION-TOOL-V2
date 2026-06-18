import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Terms of Service",
  description: "Terms of Service for ArchGuide.",
};

const sections = [
  {
    title: "Use of ArchGuide",
    body:
      "You may use ArchGuide to create projects, upload requirements, generate architecture recommendations, and explore related analysis features.",
  },
  {
    title: "Your Content",
    body:
      "You are responsible for the project details, files, and other content you submit. You should only upload content that you have the right to use.",
  },
  {
    title: "Recommendations",
    body:
      "ArchGuide provides architecture guidance and analysis to support decision-making. You remain responsible for reviewing recommendations before relying on them in production or business-critical contexts.",
  },
  {
    title: "Acceptable Use",
    body:
      "You agree not to misuse the service, interfere with its operation, attempt unauthorized access, or upload unlawful, harmful, or infringing content.",
  },
  {
    title: "Service Availability",
    body:
      "We aim to keep ArchGuide reliable, but features may change, pause, or become unavailable as the product evolves.",
  },
  {
    title: "Contact",
    body:
      "For questions about these terms, contact the ArchGuide team at 9555974189.",
  },
];

export default function TermsOfServicePage() {
  return (
    <div className="min-h-screen px-6 py-28 md:px-16 md:py-36">
      <div className="mx-auto max-w-4xl">
        <p className="mb-4 text-xs font-bold uppercase tracking-[0.2em] text-[color:var(--text-secondary)]">
          Legal
        </p>
        <h1 className="mb-6 text-5xl font-bold tracking-tight md:text-7xl">Terms of Service</h1>
        <p className="mb-16 max-w-2xl text-base leading-7 text-[color:var(--text-secondary)] md:text-lg">
          Last updated: June 18, 2026. These terms describe the basic rules for using ArchGuide.
        </p>

        <div className="space-y-10">
          {sections.map((section) => (
            <section key={section.title} className="border-t border-[color:var(--border)] pt-8">
              <h2 className="mb-4 text-2xl font-bold tracking-tight">{section.title}</h2>
              <p className="text-base leading-7 text-[color:var(--text-secondary)]">{section.body}</p>
            </section>
          ))}
        </div>
      </div>
    </div>
  );
}
