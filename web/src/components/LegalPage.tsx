import { Link } from "react-router-dom";
import { useLocale } from "@/contexts/LocaleContext";
import {
  TERMS_VERSION, EFFECTIVE_DATE, SUPPORT_EMAIL,
  type LegalSection,
} from "@/lib/legal";

interface Props {
  kind: "terms" | "privacy";
  sections: LegalSection[];
}

export default function LegalPage({ kind, sections }: Props) {
  const { locale, setLocale } = useLocale();
  const zh = locale === "zh";
  const title = kind === "terms"
    ? (zh ? "服务条款与最终用户许可" : "Terms of Service & EULA")
    : (zh ? "隐私政策" : "Privacy Policy");

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="mx-auto max-w-3xl px-6 py-12">
        <div className="flex items-center justify-between mb-8">
          <Link to="/login" className="text-sm text-primary hover:underline">
            {zh ? "返回登录" : "Back to sign in"}
          </Link>
          <button
            type="button"
            onClick={() => setLocale(zh ? "en" : "zh")}
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            {zh ? "EN" : "中文"}
          </button>
        </div>

        <h1 className="text-3xl font-semibold tracking-tight">Praxys</h1>
        <h2 className="mt-1 text-xl font-medium">{title}</h2>
        <p className="mt-2 text-sm text-muted-foreground font-data">
          v{TERMS_VERSION} · {zh ? "生效日期 " : "Effective "}{EFFECTIVE_DATE}
        </p>

        <div className="mt-8 space-y-6">
          {sections.map((s) => (
            <section key={s.id}>
              <h3 className="text-base font-semibold">{zh ? s.title.zh : s.title.en}</h3>
              {s.body.map((p, i) => (
                <p key={i} className="mt-1 text-sm leading-relaxed text-muted-foreground">
                  {zh ? p.zh : p.en}
                </p>
              ))}
            </section>
          ))}
        </div>

        <div className="mt-10 pt-6 border-t border-border text-sm text-muted-foreground">
          {kind === "terms"
            ? <Link to="/privacy" className="text-primary hover:underline">{zh ? "隐私政策" : "Privacy Policy"}</Link>
            : <Link to="/terms" className="text-primary hover:underline">{zh ? "服务条款" : "Terms of Service"}</Link>}
          <span className="mx-2">·</span>
          <a href={`mailto:${SUPPORT_EMAIL}`} className="hover:underline">{SUPPORT_EMAIL}</a>
        </div>
      </div>
    </div>
  );
}
