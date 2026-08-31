import { useEffect, useRef } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  Database,
  HeartPulse,
  MapPin,
  ShieldCheck,
} from "lucide-react";
import { useLocale } from "@/contexts/LocaleContext";
import { Button } from "@/components/ui/button";
import {
  CHINA_PROCESSING_NOTICE_VERSION,
} from "@/lib/china-processing";
import { EFFECTIVE_DATE } from "@/lib/legal";

interface Props {
  onContinue: () => void;
  onCancel?: () => void;
}

export default function ChinaProcessingNoticeGate({
  onContinue,
  onCancel,
}: Props) {
  const { locale } = useLocale();
  const navigate = useNavigate();
  const headingRef = useRef<HTMLHeadingElement>(null);
  const zh = locale === "zh";

  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  const facts = zh
    ? [
        {
          icon: MapPin,
          label: "境外处理与接收方",
          value:
            "核心服务信息由 Microsoft Corporation 及其 Azure 关联方和公开列明的分包处理方在中国大陆境外处理；当前主要托管区域为 Azure East Asia（中国香港特别行政区）。",
        },
        {
          icon: Database,
          label: "处理目的与信息范围",
          value:
            "用于账号、登录、同步、训练分析、计划、数据导出、删除、安全和必要运维；范围包括账号标识、训练活动、恢复数据、目标与设置、加密连接凭据及必要日志。",
        },
        {
          icon: HeartPulse,
          label: "敏感个人信息",
          value:
            "心率、HRV、睡眠、恢复、活动轨迹及由此形成的健康或运动判断可能属于敏感个人信息。缺少相应数据时，相关训练功能无法提供。",
        },
      ]
    : [
        {
          icon: MapPin,
          label: "Overseas processing and recipient",
          value:
            "Core service information is processed outside mainland China by Microsoft Corporation, its Azure affiliates, and published subprocessors. The current primary hosting region is Azure East Asia (Hong Kong SAR).",
        },
        {
          icon: Database,
          label: "Purposes and data",
          value:
            "Account access, provider sync, training analysis, plans, export, deletion, security, and essential operations use account identifiers, training and recovery data, goals and settings, encrypted connection credentials, and necessary logs.",
        },
        {
          icon: HeartPulse,
          label: "Sensitive personal information",
          value:
            "Heart rate, HRV, sleep, recovery, activity routes, and related health or fitness inferences may be sensitive personal information. Features that depend on those categories cannot operate without them.",
        },
      ];

  return (
    <main className="min-h-dvh bg-background px-5 py-10 text-foreground sm:px-8 sm:py-16">
      <div className="mx-auto w-full max-w-3xl">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary text-primary-foreground">
            <ShieldCheck className="h-5 w-5" aria-hidden="true" />
          </div>
          <span className="text-xl font-semibold tracking-tight">Praxys</span>
        </div>

        <h1
          ref={headingRef}
          tabIndex={-1}
          className="mt-10 max-w-2xl text-balance text-3xl font-semibold tracking-tight outline-none sm:text-4xl"
        >
          {zh
            ? "Praxys 如何处理数据以提供服务"
            : "How Praxys processes data to provide the service"}
        </h1>
        <p className="mt-4 max-w-2xl text-base leading-7 text-muted-foreground">
          {zh
            ? "为创建和管理账号，并提供所请求的训练功能，Praxys 必须通过位于中国大陆境外的系统传输和处理下列信息。该处理是履行 Praxys 服务所必需，不以同意为处理基础。"
            : "To create and manage an account and provide the requested training features, Praxys must transmit and process the information below through systems outside mainland China. This processing is necessary to perform the Praxys service and is not based on consent."}
        </p>
        <p className="mt-3 font-data text-xs text-muted-foreground">
          v{CHINA_PROCESSING_NOTICE_VERSION} ·{" "}
          {zh ? "生效日期 " : "Effective "}
          {EFFECTIVE_DATE}
        </p>

        <dl className="mt-8 divide-y divide-border border-y border-border">
          {facts.map(({ icon: Icon, label, value }) => (
            <div
              key={label}
              className="grid gap-3 py-5 sm:grid-cols-[11rem_1fr] sm:gap-6"
            >
              <dt className="flex items-center gap-2 text-sm font-medium">
                <Icon
                  className="h-4 w-4 text-accent-cobalt"
                  aria-hidden="true"
                />
                {label}
              </dt>
              <dd className="text-sm leading-6 text-muted-foreground">
                {value}
              </dd>
            </div>
          ))}
        </dl>

        <div className="mt-6 rounded-lg border border-accent-cobalt/30 bg-accent-cobalt/5 p-4">
          <p className="text-sm leading-6 text-foreground">
            {zh
              ? "Azure 核心托管与 Azure AI 处理是不同功能。普通服务的已列明 AI 用途由当前条款和服务端运行状态授权，不另设退出选项；输入按账号、用途和字段最小化。中国版网页仅发送经最小化的性能、请求和白名单产品事件；浏览器 Statsig 保持关闭。"
              : "Azure core hosting and Azure AI processing are distinct functions. Current Terms and server runtime state authorize the enumerated AI purposes for ordinary service; there is no separate opt-out, and inputs are minimized by account, purpose, and field. The China web deployment sends only minimized performance, request, and allowlisted product events; browser Statsig remains disabled."}
          </p>
        </div>

        <p className="mt-6 text-sm leading-6 text-muted-foreground">
          {zh ? "继续即确认已经阅读本告知。若不接受当前条款，将无法使用普通服务，但仍可使用现有的权利行使流程。详见" : "Continuing acknowledges that this notice has been read. If you do not accept the current Terms, ordinary service is unavailable, while the existing rights flow remains available. See the"}{" "}
          <Link
            to="/privacy#mainland-china-processing"
            target="_blank"
            className="font-medium text-primary underline-offset-4 hover:underline"
          >
            {zh ? "《隐私政策》与中国大陆处理说明" : "Privacy Policy and Mainland China processing notice"}
          </Link>
          {zh ? "。" : "."}
        </p>

        <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center">
          <Button className="min-h-11 sm:min-w-52" onClick={onContinue}>
            {zh ? "确认已阅读并继续" : "Acknowledge and continue"}
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Button>
          <Button
            variant="ghost"
            className="min-h-11 sm:min-w-28"
            onClick={() => {
              if (onCancel) {
                onCancel();
                return;
              }
              navigate("/", { replace: true });
            }}
          >
            {zh ? "暂不继续" : "Not now"}
          </Button>
        </div>
      </div>
    </main>
  );
}
