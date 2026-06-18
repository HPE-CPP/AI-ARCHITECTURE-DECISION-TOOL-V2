import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description: "Privacy Policy for ArchGuide.",
};

const sections = [
  {
    title: "Information We Collect",
    body:
      "ArchGuide may collect account details, project inputs, uploaded requirement documents, analysis history, and basic usage information needed to provide and improve the service.",
  },
  {
    title: "How We Use Information",
    body:
      "We use your information to run architecture analyses, save your projects, authenticate your account, improve product reliability, and communicate important service updates.",
  },
  {
    title: "Data Sharing",
    body:
      "We do not sell your personal information. We may share limited data with service providers that help operate ArchGuide, such as authentication, hosting, analytics, and AI processing providers.",
  },
  {
    title: "Your Choices",
    body:
      "You can choose what project information you provide, delete projects where supported, and contact us to request access, correction, or deletion of personal information.",
  },
  {
    title: "Security",
    body:
      "We use reasonable technical and organizational safeguards to protect your information, but no internet service can guarantee absolute security.",
  },
  {
    title: "Contact",
    body:
      "For privacy questions or requests, contact the ArchGuide team at 9555974189.",
  },
];

export default function PrivacyPolicyPage() {
  return (
    <div className="min-h-screen px-6 py-28 md:px-16 md:py-36">
      <div className="mx-auto max-w-4xl">
        <p className="mb-4 text-xs font-bold uppercase tracking-[0.2em] text-[color:var(--text-secondary)]">
          Legal
        </p>
        <h1 className="mb-6 text-5xl font-bold tracking-tight md:text-7xl">Privacy Policy</h1>
        <p className="mb-16 max-w-2xl text-base leading-7 text-[color:var(--text-secondary)] md:text-lg">
          Last updated: June 18, 2026. This policy explains how ArchGuide handles information when you use the application.
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
