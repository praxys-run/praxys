import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import { useLocale } from "@/contexts/LocaleContext";
import { TERMS_VERSION, EFFECTIVE_DATE } from "@/lib/legal";

/**
 * Blocking re-consent modal shown when the signed-in user's accepted Terms/EULA
 * version is stale (or null). Mirrors the registration agree UI: a checkbox plus
 * links to the full Terms and Privacy. The app stays gated until the user
 * acknowledges, which stamps the live TERMS_VERSION via POST /api/me/accept-terms.
 * Bilingual via the locale ternary, matching LegalPage.
 */
export default function TermsGate() {
  const { acceptTerms } = useAuth();
  const { locale, setLocale } = useLocale();
  const zh = locale === "zh";
  const [agreed, setAgreed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAccept = async () => {
    if (!agreed) return;
    setSubmitting(true);
    setError(null);
    const ok = await acceptTerms();
    if (!ok) {
      setError(zh ? "\u63d0\u4ea4\u5931\u8d25\uff0c\u8bf7\u91cd\u8bd5\u3002" : "Could not save \u2014 please try again.");
      setSubmitting(false);
    }
    // On success the gate unmounts as termsCurrent flips true.
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-background/80 backdrop-blur-sm p-4">
      <div className="w-full max-w-md rounded-lg border border-border bg-card p-6 shadow-lg">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">
            {zh ? "\u6761\u6b3e\u5df2\u66f4\u65b0" : "Updated Terms"}
          </h2>
          <button
            type="button"
            onClick={() => setLocale(zh ? "en" : "zh")}
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            {zh ? "EN" : "\u4e2d\u6587"}
          </button>
        </div>
        <p className="mt-1 text-sm text-muted-foreground font-data">
          v{TERMS_VERSION} \u00b7 {zh ? "\u751f\u6548\u65e5\u671f " : "Effective "}{EFFECTIVE_DATE}
        </p>
        <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
          {zh
            ? "\u6211\u4eec\u66f4\u65b0\u4e86\u670d\u52a1\u6761\u6b3e\u4e0e\u9690\u79c1\u653f\u7b56\u3002\u8bf7\u9605\u8bfb\u5e76\u540c\u610f\u540e\u7ee7\u7eed\u4f7f\u7528\u3002"
            : "We've updated our Terms and Privacy Policy. Please review and accept to continue."}
        </p>

        <label className="mt-5 flex items-start gap-2 text-sm text-muted-foreground">
          <input
            type="checkbox"
            checked={agreed}
            onChange={(e) => setAgreed(e.target.checked)}
            disabled={submitting}
            className="mt-0.5 flex-none"
          />
          <span>
            {zh ? "\u6211\u540c\u610f" : "I agree to the"}{" "}
            <Link to="/terms" target="_blank" className="text-primary hover:underline">
              {zh ? "\u670d\u52a1\u6761\u6b3e" : "Terms of Service"}
            </Link>{" "}
            {zh ? "\u4e0e" : "and"}{" "}
            <Link to="/privacy" target="_blank" className="text-primary hover:underline">
              {zh ? "\u9690\u79c1\u653f\u7b56" : "Privacy Policy"}
            </Link>
            {zh ? "\u3002" : "."}
          </span>
        </label>

        {error && <p className="mt-3 text-sm text-destructive">{error}</p>}

        <button
          type="button"
          onClick={handleAccept}
          disabled={!agreed || submitting}
          className="mt-6 w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
        >
          {submitting
            ? (zh ? "\u4fdd\u5b58\u4e2d\u2026" : "Saving\u2026")
            : (zh ? "\u540c\u610f\u5e76\u7ee7\u7eed" : "Accept and continue")}
        </button>
      </div>
    </div>
  );
}
