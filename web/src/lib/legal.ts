// EULA / Terms + Privacy content and version metadata for Praxys.
//
// EDIT THESE PLACEHOLDERS before public launch:
//   OPERATOR_NAME  – your legal name (individual operator) or company
//   JURISDICTION   – your country/state of residence (governing law)
// Keep TERMS_VERSION in sync with api/legal.py::TERMS_VERSION. Bump both and
// EFFECTIVE_DATE whenever the agreement materially changes.
// Azure AI privacy source for the disclosures below:
// https://learn.microsoft.com/en-us/azure/foundry/responsible-ai/openai/data-privacy

export const TERMS_VERSION = "2026.08.1";
export const EFFECTIVE_DATE = "2026-08-09";
export const SUPPORT_EMAIL = "support@praxys.run";
export const OPERATOR_NAME = "Fei Tao";
export const JURISDICTION = "the People’s Republic of China";

export interface LegalText { en: string; zh: string; }
export interface LegalSection { id: string; title: LegalText; body: LegalText[]; }

export const TERMS_SECTIONS: LegalSection[] = [
  { id: "acceptance", title: { en: "1. Acceptance", zh: "1. 接受条款" }, body: [
    { en: "By creating an account or using Praxys (the \"Service\"), you agree to this End User License Agreement and Terms of Service (\"Agreement\"). If you do not agree, do not register or use the Service.",
      zh: "注册账户或使用 Praxys（\"本服务\"）即表示您同意本《最终用户许可与服务协议》（\"本协议\"）。若不同意，请勿注册或使用本服务。" } ] },
  { id: "eligibility", title: { en: "2. Eligibility", zh: "2. 资格" }, body: [
    { en: "You must be at least 16 years old (or the age of digital consent in your country) and able to form a binding contract. You are responsible for keeping your credentials secure and for all activity under your account.",
      zh: "您须年满 16 周岁（或您所在国家的数字同意年龄）且具备订立合同的能力。您须妥善保管账户凭据，并对账户下的所有活动负责。" } ] },
  { id: "license", title: { en: "3. License", zh: "3. 许可" }, body: [
    { en: "We grant you a limited, non-exclusive, non-transferable, revocable license to use the Service for your personal, non-commercial training. You may not copy, resell, reverse engineer, or use the Service to build a competing product.",
      zh: "我们授予您有限、非独占、不可转让、可撤销的许可，仅供您个人非商业训练使用。您不得复制、转售、逆向工程，或利用本服务构建竞品。" } ] },
  { id: "health", title: { en: "4. Health Disclaimer", zh: "4. 健康免责声明" }, body: [
    { en: "Praxys is a training-analytics tool, NOT a medical device or medical advice. Outputs (signals, plans, forecasts) are informational estimates grounded in published sports science. Consult a physician before changing training, especially with any medical condition. Train at your own risk.",
      zh: "Praxys 是训练分析工具，并非医疗器械或医疗建议。其输出（信号、计划、预测）为基于已发表运动科学的参考性估计。在调整训练前请咨询医生，尤其有任何疾病时。训练风险自负。" } ] },
  { id: "data", title: { en: "5. Third-Party Data", zh: "5. 第三方数据" }, body: [
    { en: "Connecting Garmin, Stryd, Oura, Strava or similar means you authorize us to fetch your data via your credentials. You confirm you may share it; their terms still apply. We are not affiliated with or endorsed by these providers.",
      zh: "连接 Garmin、Stryd、Oura、Strava 等即表示您授权我们使用您的凭据获取数据。您确认有权共享该数据；其各自条款仍适用。我们与上述提供方无隶属或背书关系。" },
    { en: "Some connections require your account credentials, which are stored encrypted and used only to retrieve your data; unofficial access may be limited or disrupted at any time. Health and fitness data is sensitive personal information — by connecting, you explicitly consent to its collection and processing for training analytics, and may withdraw consent by disconnecting or deleting your account.",
      zh: "部分连接需要您的账户凭据，凭据加密存储且仅用于获取您的数据；非官方接入可能随时受限或中断。健康与健身数据属于敏感个人信息——连接即表示您明确同意我们为训练分析收集和处理该数据，您可随时断开连接或删除账户以撤回同意。" },
    { en: "Optional information you provide to personalize a plan is processed by Praxys rules by default. It is sent to Microsoft's Azure-hosted AI service only when you separately opt in for that exact context version and disclosed fields. Microsoft states that these inputs and outputs are not available to OpenAI or used to train generative AI foundation models without permission; Praxys does not grant that permission. AI output may be wrong and is not medical advice; you remain in control of plan changes.",
      zh: "可选的计划个性化信息默认仅由 Praxys 规则处理。只有在您针对该版本及明确披露的字段另行同意后，相关最小化副本才会发送至 Microsoft Azure AI 服务。微软说明，这些输入和输出不会提供给 OpenAI，也不会在未经许可的情况下用于训练生成式 AI 基础模型；Praxys 不会授予该许可。AI 输出可能有误且不构成医疗建议；计划变更仍由您决定。" } ] },
  { id: "conduct", title: { en: "6. Acceptable Use", zh: "6. 可接受使用" }, body: [
    { en: "Do not misuse the Service: no unlawful use, unauthorized access, scraping, abuse, or uploading others' data without consent.",
      zh: "请勿滥用本服务：不得用于违法目的、未授权访问、抓取、滥用，或未经同意上传他人数据。" } ] },
  { id: "alpha", title: { en: "7. Alpha & Availability", zh: "7. 内测与可用性" }, body: [
    { en: "Praxys is in private alpha, provided \"as is\" without warranty. Features may change or break; data may be lost. We do not guarantee uptime or accuracy.",
      zh: "Praxys 处于私密内测，按\"现状\"提供，不作任何担保。功能可能变更或失效，数据可能丢失。我们不保证可用性或准确性。" } ] },
  { id: "liability", title: { en: "8. Limitation of Liability", zh: "8. 责任限制" }, body: [
    { en: "To the maximum extent permitted by law, the operator is not liable for indirect, incidental, or consequential damages, including injury or data loss, arising from use of the Service.",
      zh: "在法律允许的最大范围内，运营者不对因使用本服务导致的间接、附带或后果性损害（含伤害或数据丢失）承担责任。" } ] },
  { id: "termination", title: { en: "9. Termination", zh: "9. 终止" }, body: [
    { en: "You may delete your account anytime. We may suspend or terminate accounts that violate this Agreement.",
      zh: "您可随时删除账户。对违反本协议的账户，我们可暂停或终止。" } ] },
  { id: "changes", title: { en: "10. Changes & Contact", zh: "10. 变更与联系" }, body: [
    { en: "We may update this Agreement; material changes are versioned and shown at next sign-in. Governed by the laws of " + JURISDICTION + ", operated by " + OPERATOR_NAME + ". Questions: " + SUPPORT_EMAIL + ".",
      zh: "我们可更新本协议；重大变更将进行版本管理并在下次登录时提示。受 " + JURISDICTION + " 法律管辖，由 " + OPERATOR_NAME + " 运营。如有疑问：" + SUPPORT_EMAIL + "。" } ] },
];

export const PRIVACY_SECTIONS: LegalSection[] = [
  { id: "collect", title: { en: "1. What We Collect", zh: "1. 收集的信息" }, body: [
    { en: "Account email and a hashed password; training data you sync (activities, power, HR, sleep, HRV, recovery); and the platform credentials needed to fetch it.",
      zh: "账户邮箱与哈希后的密码；您同步的训练数据（活动、功率、心率、睡眠、HRV、恢复）；以及获取数据所需的平台凭据。" },
    { en: "If you choose to add private plan context, we collect the selected category, bounded planning fields, dates, and an optional note of up to 280 characters. Praxys does not infer a reason from workout behavior and does not require a note.",
      zh: "若选择添加计划个性化信息，我们会收集所选类别、限定的计划字段、日期，以及最多 280 字符的可选备注。Praxys 不会根据训练行为推断原因，也不要求填写备注。" } ] },
  { id: "use", title: { en: "2. How We Use It", zh: "2. 使用方式" }, body: [
    { en: "To compute and show your training analytics and, when you provide private plan context, to avoid guessing and produce purpose-bounded plan interpretations or suggestions. We do not sell your data, use it for advertising, or place private context in analytics, public trackers, evaluation corpora, or cross-user model training.",
      zh: "用于计算并展示训练分析；在您提供计划个性化信息时，用于避免猜测，并生成限定用途的计划解读或建议。我们不出售您的数据，不将其用于广告，也不会把计划个性化信息放入分析统计、公开问题追踪、评估语料或跨用户模型训练。" } ] },
  { id: "private-context", title: { en: "3. Private Plan Context & AI", zh: "3. 计划个性化信息与 AI" }, body: [
    { en: "Private plan context is encrypted, belongs to your account, and is used only for the purpose and active period you confirm. Optional notes are deleted after 30 days; temporary structured context expires on the date shown and is purged under the disclosed retention schedule.",
      zh: "计划个性化信息经加密保存，仅归属于您的账号，并只在您确认的用途和有效期内使用。可选备注会在 30 天后删除；临时结构化信息会在界面显示的日期失效，并按披露的保留期限清除。" },
    { en: "AI processing is off for each item by default. If you separately enable it, Praxys sends only the disclosed category and fields — and the optional note only if separately selected — to Microsoft's Azure-hosted AI service. Microsoft states that these inputs and outputs are not available to OpenAI or used to train generative AI foundation models without permission; Praxys does not grant that permission. Flagged content may be processed for abuse monitoring under Microsoft's Azure terms. Praxys does not log raw requests or responses. Withdrawing consent blocks new requests but cannot recall a request already processed.",
      zh: "每条信息默认关闭 AI 处理。若另行启用，Praxys 只会把已披露的类别和字段发送至 Microsoft Azure AI 服务；可选备注仅在单独勾选后发送。微软说明，这些输入和输出不会提供给 OpenAI，也不会在未经许可的情况下用于训练生成式 AI 基础模型；Praxys 不会授予该许可。被标记的内容可能会根据 Microsoft Azure 条款接受滥用监测。Praxys 不记录原始请求或响应。撤回同意会阻止后续请求，但无法撤回已经处理的请求。" } ] },
  { id: "security", title: { en: "4. Security", zh: "4. 安全" }, body: [
    { en: "Platform credentials and private plan context are encrypted at rest; passwords are hashed. Access is owner- and purpose-scoped. No system is perfectly secure; you share data at your own risk.",
      zh: "平台凭据和计划个性化信息均静态加密，密码经哈希存储。访问受到账号归属和用途限制。没有系统绝对安全，您共享数据需自担风险。" } ] },
  { id: "rights", title: { en: "5. Your Rights", zh: "5. 您的权利" }, body: [
    { en: "You can inspect, correct, stop using, withdraw AI permission, delete, and export private plan context in the Plan interface. Request export or deletion of your full account and data anytime at " + SUPPORT_EMAIL + ". Deleting your account removes your synced data and private context.",
      zh: "您可在计划界面查看、更正、停止使用、撤回 AI 权限、删除和导出计划个性化信息。您也可随时通过 " + SUPPORT_EMAIL + " 申请导出或删除完整账号与数据。删除账号将移除已同步数据和计划个性化信息。" } ] },
];
