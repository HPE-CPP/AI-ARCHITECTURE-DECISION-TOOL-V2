"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[GlobalError]", error);
  }, [error]);

  const router = useRouter();

  return (
    <div className="w-full min-h-screen flex items-center justify-center px-6">
      <div className="flex flex-col items-center text-center max-w-sm">
        <div className="w-16 h-16 rounded-2xl bg-[color:var(--surface)] border border-[color:var(--border)] flex items-center justify-center mb-6 text-2xl">
          ⚠️
        </div>
        <h1 className="text-2xl font-black tracking-tight text-[color:var(--text-primary)] mb-2">
          Something went wrong
        </h1>
        <p className="text-sm text-[color:var(--text-secondary)] font-medium mb-8 leading-relaxed">
          An unexpected error occurred on this page.
        </p>
        <div className="flex items-center gap-3">
          <button
            onClick={() => reset()}
            className="px-6 py-3 rounded-full bg-[color:var(--text-primary)] text-[color:var(--background)] font-bold text-sm hover:opacity-80 transition-opacity active:scale-95"
          >
            Try again
          </button>
          <button
            onClick={() => router.push("/")}
            className="px-6 py-3 rounded-full border border-[color:var(--border)] bg-[color:var(--surface)] text-[color:var(--text-primary)] font-bold text-sm hover:opacity-80 transition-opacity active:scale-95"
          >
            Go home
          </button>
        </div>
      </div>
    </div>
  );
}
