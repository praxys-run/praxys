// EULA / Terms + Privacy content and version metadata for Praxys.
//
// EDIT THESE PLACEHOLDERS before public launch:
//   OPERATOR_NAME  – your legal name (individual operator) or company
//   JURISDICTION   – your country/state of residence (governing law)
// Keep TERMS_VERSION in sync with api/legal.py::TERMS_VERSION. Bump both and
// EFFECTIVE_DATE whenever the agreement materially changes.
// Azure AI privacy source for the disclosures below:
// https://learn.microsoft.com/en-us/azure/foundry/responsible-ai/openai/data-privacy

export const TERMS_VERSION = "2026.08.5";
export const TERMS_CONTENT_DIGEST =
  "sha256:57cca8f824f6e803a3df9b1de45d76cfc21fb750483e61281e7c4ff495ae218e";
export const EFFECTIVE_DATE = "2026-08-31";
export const SUPPORT_EMAIL = "support@praxys.run";
export const OPERATOR_NAME = "Fei Tao";
export const JURISDICTION = "the People’s Republic of China";
export const MICROSOFT_PRIVACY_REQUEST_URL =
  "https://aka.ms/privacyresponseother";

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
    { en: "Connecting a third-party training or recovery service means you authorize us to fetch your data using the access method you provide. You confirm you may share it; that provider's terms still apply. We are not affiliated with or endorsed by connected providers.",
      zh: "连接第三方训练或恢复服务，即表示你授权我们通过你提供的访问方式获取数据。你确认有权共享这些数据，且仍需遵守相应服务商的条款。Praxys 与所连接的服务商不存在隶属或背书关系。" },
    { en: "Some connections require your account credentials, which are stored encrypted and used only to retrieve your data; unofficial access may be limited or disrupted at any time. Health and fitness data may be sensitive personal information. When you activate a connection, processing the disclosed categories is necessary to perform that sync and training-analysis feature. Disconnecting stops future retrieval; deleting your account removes the stored copy.",
      zh: "部分连接需要您的账户凭据，凭据加密存储且仅用于获取您的数据；非官方接入可能随时受限或中断。健康与健身数据可能属于敏感个人信息。启用连接后，处理已披露的信息类别是履行相应同步和训练分析功能所必需。断开连接会停止后续获取；删除账号会移除已存储副本。" },
    { en: "Praxys uses Microsoft's Azure-hosted AI service for the ordinary AI features described in this Agreement, including training reviews, forecasts, support-feedback text or screenshot triage, and purpose-bounded plan-context interpretation. Accepting the current Agreement authorizes those enumerated purposes; there is no separate AI opt-out for ordinary service. Inputs are minimized and isolated per account and purpose. Microsoft states that inputs and outputs are not available to OpenAI or used to train generative AI foundation models without permission; Praxys does not grant that permission. AI output may be wrong and is not medical advice; you remain in control of plan changes.",
      zh: "Praxys 使用 Microsoft Azure 托管的 AI 服务提供本协议所述的普通 AI 功能，包括训练回顾、预测、支持反馈文本或截图分类，以及限定用途的计划个性化信息解读。接受当前协议即授权这些已列明用途；普通服务不另设 AI 退出选项。输入会按账号和用途进行最小化与隔离。微软说明，输入和输出不会提供给 OpenAI，也不会在未经许可的情况下用于训练生成式 AI 基础模型；Praxys 不会授予该许可。AI 输出可能有误且不构成医疗建议；计划变更仍由您决定。" } ] },
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
    { en: "Account identifiers and contact information; a hashed password or WeChat identifier; training data you sync (activities, routes, power, heart rate, sleep, HRV, recovery); goals, plans, settings, and feedback you submit; and the encrypted platform credentials needed to fetch connected data.",
      zh: "账号标识与联系信息；哈希后的密码或微信标识；您同步的训练数据（活动、路线、功率、心率、睡眠、HRV、恢复）；目标、计划、设置及您提交的反馈；以及获取已连接数据所需的加密平台凭据。" },
    { en: "If you choose to add private plan context, we collect the selected category, bounded planning fields, dates, and an optional note of up to 280 characters. Praxys does not infer a reason from workout behavior and does not require a note.",
      zh: "若选择添加计划个性化信息，我们会收集所选类别、限定的计划字段、日期，以及最多 280 字符的可选备注。Praxys 不会根据训练行为推断原因，也不要求填写备注。" },
    { en: "Essential security and reliability records may include request time, route, response status, coarse client or network information, and a pseudonymous account identifier. Praxys does not intentionally place raw training content, passwords, access tokens, or provider credentials in telemetry.",
      zh: "必要的安全与可靠性记录可能包括请求时间、接口路径、响应状态、粗粒度客户端或网络信息，以及经假名化处理的账号标识。Praxys 不会有意将原始训练内容、密码、访问令牌或平台凭据写入遥测。" } ] },
  { id: "use", title: { en: "2. How We Use It", zh: "2. 使用方式" }, body: [
    { en: "To create and secure your account; authenticate you; retrieve data from providers you activate; compute and show training analytics, signals, plans, and forecasts; deliver requested account controls; diagnose failures; and meet legal obligations. When you provide private plan context, we use it to avoid guessing and produce purpose-bounded plan interpretations or suggestions.",
      zh: "用于创建和保护账号、验证身份、从您启用的平台获取数据、计算并展示训练分析、信号、计划和预测、提供所请求的账号控制、诊断故障及履行法定义务。在您提供计划个性化信息时，我们用其避免猜测，并生成限定用途的计划解读或建议。" },
    { en: "We do not sell personal information, use it for advertising, or place private context in browser analytics, public trackers, evaluation corpora, or cross-user model training. The praxys.cn deployment uses minimized Application Insights performance and request telemetry plus allowlisted product events. It strips URL queries and fragments, suppresses browser exception capture, and does not intentionally send email, raw account identifiers, training content, private context, or feedback text. Browser Statsig remains disabled.",
      zh: "我们不出售个人信息，不将其用于广告，也不会把计划个性化信息放入浏览器分析、公开问题追踪、评估语料或跨用户模型训练。praxys.cn 使用经最小化的 Application Insights 性能与请求遥测及白名单产品事件；URL 查询参数和片段会被移除，浏览器异常采集会被关闭，且不会有意发送邮箱、原始账号标识、训练内容、计划个性化信息或反馈原文。浏览器 Statsig 仍保持关闭。" },
    { en: "Azure AI may privately classify support feedback text and screenshots under this Agreement. Publishing feedback to an external issue tracker is separate and occurs only when you give the exact per-submission publication permission shown with the feedback form. Accepting these Terms does not grant publication permission, and screenshots remain private.",
      zh: "Azure AI 可依据本协议对支持反馈文本和截图进行私密分类。将反馈发布到外部问题追踪器属于独立处理，只有在您通过反馈表单针对该次提交明确授权时才会发生。接受本条款不构成发布授权，截图始终保持私密。" } ] },
  { id: "mainland-china-processing", title: { en: "3. Mainland China Processing & Overseas Recipients", zh: "3. 中国大陆用户处理与境外接收方" }, body: [
    { en: "Controller/operator: " + OPERATOR_NAME + ", contactable at " + SUPPORT_EMAIL + ". Core overseas recipient and processor: Microsoft Corporation and the Microsoft affiliates and subprocessors that provide the Azure subscription used by Praxys. Microsoft privacy requests may be submitted at " + MICROSOFT_PRIVACY_REQUEST_URL + ". Praxys remains responsible for responding to your request and coordinating with processors.",
      zh: "个人信息处理者/运营者：" + OPERATOR_NAME + "，联系邮箱：" + SUPPORT_EMAIL + "。核心境外接收方和受托处理方：Microsoft Corporation，以及为 Praxys 所用 Azure 订阅提供服务的 Microsoft 关联方和分包处理方。可通过 " + MICROSOFT_PRIVACY_REQUEST_URL + " 向 Microsoft 提交隐私请求；Praxys 仍负责响应您的请求并与受托处理方协调。" },
    { en: "Destination and method: the account, API, database, encrypted credential, storage, and essential monitoring path is processed in Microsoft-managed Azure services outside mainland China. At this policy's effective date, the current primary hosting region is Azure East Asia (Hong Kong SAR). Microsoft may change facilities or published subprocessors while providing the same disclosed purposes and safeguards; Praxys will update this notice before a material change to the recipient, purpose, information categories, or rights process. Tencent Cloud EdgeOne serves the static praxys.cn frontend and does not receive the authenticated training dataset from Praxys.",
      zh: "处理地点与方式：账号、API、数据库、加密凭据、存储和必要监控链路由 Microsoft 管理的 Azure 服务在中国大陆境外处理。本政策生效时，主要托管区域为 Azure East Asia（中国香港特别行政区）。Microsoft 可在保持已披露目的和保护措施不变的情况下调整设施或其公开列明的分包处理方；若接收方、处理目的、信息类别或行权方式发生实质变化，Praxys 将在变更前更新本说明。腾讯云 EdgeOne 仅提供 praxys.cn 静态前端，不从 Praxys 接收已认证训练数据集。" },
    { en: "Purposes and categories: Microsoft processes the account identifiers, contact information, authentication records, synced activities and routes, power, heart rate, sleep, HRV, recovery, goals, plans, settings, encrypted provider credentials, support content, and minimized security or reliability records needed to host and operate the features you request.",
      zh: "目的与信息类别：Microsoft 为托管和运行您所请求的功能，处理所需的账号标识、联系信息、认证记录、已同步活动与路线、功率、心率、睡眠、HRV、恢复、目标、计划、设置、加密平台凭据、支持内容，以及最小化的安全或可靠性记录。" },
    { en: "Server-side feature rollout is evaluated inside Praxys. The Statsig SDK downloads rollout rules without user identity, while user-event logging and SDK diagnostics are disabled. Account identifiers, email addresses, targeting attributes, and training data are not transmitted to Statsig or Amplitude for these checks.",
      zh: "服务端功能发布判断在 Praxys 内部完成。Statsig SDK 仅在不携带用户身份的情况下下载发布规则，并关闭用户事件日志与 SDK 诊断。执行这些检查时，账号标识、邮箱、定向属性及训练数据不会发送至 Statsig 或 Amplitude。" },
    { en: "Connected providers are separate recipients only when you activate them. Depending on the selected connection, Praxys sends the authentication details you provide to Garmin, Strava, Stryd, Oura, or COROS and retrieves the supported activity, route, power, heart-rate, sleep, HRV, recovery, fitness, or plan data. The connection dialog identifies the provider and links its current privacy and contact information before transfer. Provider processing locations vary by account region and policy. Connecting is optional, and disconnecting stops future retrieval.",
      zh: "仅在您主动启用连接时，所连接的平台才成为独立接收方。根据所选连接，Praxys 会把您提供的认证信息发送至 Garmin、Strava、Stryd、Oura 或 COROS，并获取该连接支持的活动、路线、功率、心率、睡眠、HRV、恢复、体能或计划数据。传输前，连接对话框会标明服务商并链接其当前隐私及联系方式。服务商的处理地点依账号区域和其政策而异。连接并非必需；断开连接会停止后续获取。" },
    { en: "Mainland processors: Tencent Cloud EdgeOne serves the static praxys.cn frontend; WeChat processes login codes and identifiers used for mini-program authentication; and Tencent Exmail processes destination addresses and message content for requested verification or service email. These services do not receive the authenticated training dataset from Praxys except for the minimum information needed for their stated function.",
      zh: "境内受托处理方：腾讯云 EdgeOne 提供 praxys.cn 静态前端；微信处理小程序认证所需的登录码和标识；腾讯企业邮箱处理所请求验证或服务邮件的收件地址与邮件内容。除完成各自明确功能所需的最少信息外，这些服务不从 Praxys 接收已认证训练数据集。" },
    { en: "Legal basis and necessity for mainland China users: Praxys determines that this core overseas processing is strictly necessary to enter into and perform the service contract requested by the individual. It relies on Article 13(1)(2) of the Personal Information Protection Law and the contract-necessity exemption in Article 5(1) of the 2024 Provisions on Promoting and Regulating Cross-Border Data Flows, rather than consent, for the core path. You may stop future core processing by disconnecting providers and deleting the account, but Praxys cannot provide the corresponding account, sync, or training features without the necessary data.",
      zh: "中国大陆用户的处理依据与必要性：Praxys 判断，上述核心境外处理属于订立、履行个人作为一方当事人的服务合同所严格必需。核心链路依据《个人信息保护法》第十三条第一款第二项及《促进和规范数据跨境流动规定》第五条第一项的合同履行必要情形处理，而非以同意为基础。您可通过断开平台连接并删除账号停止未来核心处理；但缺少必要数据时，Praxys 无法提供相应账号、同步或训练功能。" },
    { en: "Sensitive information and impact: heart rate, HRV, sleep, recovery, precise activity routes, health or fitness inferences, and encrypted provider credentials may be sensitive personal information. These categories are used only where needed for the signal, analysis, plan, forecast, connection, or security function you request. Overseas processing may increase exposure to network interception, foreign legal access, provider outages, or unauthorized access. Praxys reduces those risks through encryption in transit and at rest, credential encryption, per-user authorization, data minimization, access controls, private screenshot storage, monitored deletion, and a documented personal-information protection impact assessment.",
      zh: "敏感个人信息及影响：心率、HRV、睡眠、恢复、精确活动路线、健康或运动推断以及加密平台凭据可能属于敏感个人信息。这些信息仅在生成您所请求的信号、分析、计划、预测、连接或安全功能所必需时使用。境外处理可能增加网络截获、境外法律访问、服务商中断或未授权访问风险。Praxys 通过传输和静态加密、凭据加密、按用户授权、数据最小化、访问控制、私有截图存储、受监控删除及形成个人信息保护影响评估等措施降低风险。" },
    { en: "Azure core hosting and Azure AI processing are distinct service functions. Core hosting currently uses Azure East Asia as described above. The ordinary Azure AI purposes enumerated in this policy use a configured endpoint in West US 3, United States; Microsoft may use supporting facilities and published subprocessors in other locations under its terms. Current Terms acceptance and server runtime state—not a mutable client preference—govern these AI requests. If you reject or do not renew the current Terms, ordinary service is unavailable and only the displayed rights flow remains. During an Azure AI outage or emergency stop, AI-only features are explicitly unavailable while provider sync and deterministic metrics continue.",
      zh: "Azure 核心托管与 Azure AI 处理是不同的服务功能。核心托管目前使用上述 Azure East Asia 区域。本政策列明的普通 Azure AI 用途使用位于美国 West US 3 的已配置端点；Microsoft 可依据其条款使用其他地点的支持设施和公开列明的分包处理方。当前条款接受记录和服务端运行状态（而非可变的客户端偏好）决定这些 AI 请求。若您拒绝或未重新接受当前条款，普通服务不可用，仅保留界面所示的权利行使流程。Azure AI 中断或紧急停止期间，AI 专属功能会明确显示不可用，但平台同步和确定性指标继续运行。" } ] },
  { id: "private-context", title: { en: "4. Private Plan Context & AI", zh: "4. 计划个性化信息与 AI" }, body: [
    { en: "Private plan context is encrypted, belongs to your account, and is used only for the purpose and active period you confirm. Optional notes are deleted after 30 days; temporary structured context expires on the date shown and is purged under the disclosed retention schedule.",
      zh: "计划个性化信息经加密保存，仅归属于您的账号，并只在您确认的用途和有效期内使用。可选备注会在 30 天后删除；临时结构化信息会在界面显示的日期失效，并按披露的保留期限清除。" },
    { en: "For a confirmed context purpose, Praxys may send only that item's selected category, provided structured fields, and provided optional note to Microsoft's Azure-hosted AI service. Item identity, version, purpose, field minimization, retention, safety exclusions, and payload-free use receipts remain enforced. Microsoft states that inputs and outputs are not available to OpenAI or used to train generative AI foundation models without permission; Praxys does not grant that permission. Flagged content may be processed for abuse monitoring under Microsoft's Azure terms. Praxys does not log raw requests or responses.",
      zh: "对于已确认的个性化信息用途，Praxys 仅可将该条目的所选类别、已提供的结构化字段和已提供的可选备注发送至 Microsoft Azure AI 服务。条目标识、版本、用途、字段最小化、保留期限、安全排除及不含载荷的使用记录仍受严格约束。微软说明，输入和输出不会提供给 OpenAI，也不会在未经许可的情况下用于训练生成式 AI 基础模型；Praxys 不会授予该许可。被标记的内容可能会根据 Microsoft Azure 条款接受滥用监测。Praxys 不记录原始请求或响应。" } ] },
  { id: "security", title: { en: "5. Security", zh: "5. 安全措施" }, body: [
    { en: "Platform credentials and private plan context are encrypted at rest; passwords are hashed; production traffic uses HTTPS; access is owner-, role-, and purpose-scoped; provider credentials are isolated per user; and feedback screenshots are private by construction. No system is perfectly secure, but Praxys reviews access, deletion, incident, and processor risks as part of its operating controls.",
      zh: "平台凭据和计划个性化信息均静态加密，密码经哈希存储，生产流量使用 HTTPS，访问受账号归属、角色和用途限制，平台凭据按用户隔离，反馈截图按设计保持私有。没有系统绝对安全；Praxys 将访问、删除、事件和受托处理方风险纳入运营控制并持续复核。" } ] },
  { id: "retention", title: { en: "6. Retention", zh: "6. 保存期限" }, body: [
    { en: "Core account and training data is kept while the account is active and deleted from active systems when you delete the account. Encrypted PostgreSQL point-in-time recovery backups may retain a recoverable copy for up to 14 days; a restore may require operator reconciliation before traffic reopens. Deletion records, security logs, and legally required records may remain for their bounded purpose. Optional private-context notes follow the shorter periods shown in the product. Browser and backend Application Insights data is retained for 30 days. Praxys keeps the personal-information protection impact assessment and processing record for at least three years.",
      zh: "核心账号和训练数据在账号有效期间保存，并在您删除账号时从活动系统中清除。加密的 PostgreSQL 时间点恢复备份可能在最长 14 天内保留可恢复副本；发生恢复时，运营者可能需要在重新开放流量前执行删除对账。删除记录、安全日志及依法必须保存的记录可在限定用途和期限内保留。可选计划个性化备注遵循产品中显示的更短期限。浏览器与后端 Application Insights 数据保留 30 天。Praxys 对个人信息保护影响评估和处理情况记录至少保存三年。" } ] },
  { id: "rights", title: { en: "7. Your Rights", zh: "7. 您的权利" }, body: [
    { en: "You may ask Praxys to explain the processing rules; inspect, copy, correct, supplement, restrict, or delete personal information; disconnect a provider; export your account data; or delete the account. Use the product controls where available or email " + SUPPORT_EMAIL + ". For information processed by an overseas recipient, contact Praxys through the same channel; Praxys will verify the request and coordinate the response. You may also complain to the competent personal-information protection authority.",
      zh: "您可要求 Praxys 说明处理规则，查阅、复制、更正、补充、限制或删除个人信息，断开平台连接，导出账号数据或删除账号。请优先使用产品内控制；也可发送邮件至 " + SUPPORT_EMAIL + "。对于境外接收方处理的信息，请通过同一渠道联系 Praxys；Praxys 会核验请求并协调响应。您也可向有权个人信息保护主管部门投诉。" },
    { en: "Deleting the account stops future core processing and removes synced data and private context from active systems. Some requests may require identity verification or may be limited where retention is legally required or necessary to protect another person's rights.",
      zh: "删除账号会停止未来核心处理，并从活动系统中移除已同步数据和计划个性化信息。部分请求可能需要验证身份；如法律要求保存或为保护他人权利所必需，相关权利可能依法受到限制。" } ] },
  { id: "changes-contact", title: { en: "8. Changes & Contact", zh: "8. 变更与联系" }, body: [
    { en: "Material changes to recipients, destinations, purposes, categories, retention, rights, or legal basis are versioned and presented before the updated processing starts. Operator: " + OPERATOR_NAME + ". Privacy and rights contact: " + SUPPORT_EMAIL + ".",
      zh: "如境外接收方、处理地点、目的、信息类别、保存期限、权利方式或处理依据发生重大变化，我们会更新版本，并在新处理开始前向您展示。运营者：" + OPERATOR_NAME + "。隐私与权利联系邮箱：" + SUPPORT_EMAIL + "。" } ] },
];
