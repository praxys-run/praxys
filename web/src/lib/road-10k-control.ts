import type { Road10KTaperGuardrailProjection } from '@/types/api';

export const ROAD_10K_COPY = {
  "action.add_screenshot": { en: "Add optional screenshot", 'zh-CN': "添加可选截图" },
  "action.adopt": { en: "Adopt exact proposal", 'zh-CN': "采纳此确切提案" },
  "action.back": { en: "Back", 'zh-CN': "返回" },
  "action.baseline": { en: "Review baseline", 'zh-CN': "检查基准" },
  "action.cancel": { en: "Cancel", 'zh-CN': "取消" },
  "action.check": { en: "Check proposal readiness", 'zh-CN': "检查提案准备状态" },
  "action.confirm_baseline": { en: "Confirm this baseline", 'zh-CN': "确认此基准" },
  "action.confirm_inputs": { en: "Confirm plan inputs", 'zh-CN': "确认计划输入" },
  "action.continue": { en: "Continue", 'zh-CN': "继续" },
  "action.delete": { en: "Delete my account", 'zh-CN': "删除我的账户" },
  "action.end_plan": { en: "End plan", 'zh-CN': "结束计划" },
  "action.export": { en: "Export my data", 'zh-CN': "导出我的数据" },
  "action.generate": { en: "Generate proposal", 'zh-CN': "生成提案" },
  "action.generate_revision": { en: "Generate revised proposal", 'zh-CN': "生成修订后的提案" },
  "action.goal": { en: "Review Goal", 'zh-CN': "检查目标" },
  "action.inputs": { en: "Review plan inputs", 'zh-CN': "检查计划输入" },
  "action.join": { en: "Join rollout", 'zh-CN': "加入试点" },
  "action.latest": { en: "Review latest status", 'zh-CN': "查看最新状态" },
  "action.leave": { en: "Leave rollout", 'zh-CN': "退出试点" },
  "action.manage": { en: "Manage plan", 'zh-CN': "管理计划" },
  "action.manage_training": { en: "Manage Training", 'zh-CN': "管理训练" },
  "action.not_now": { en: "Not now", 'zh-CN': "暂不" },
  "action.notice": { en: "Review current notice", 'zh-CN': "查看当前说明" },
  "action.pause_plan": { en: "Pause plan", 'zh-CN': "暂停计划" },
  "action.refresh": { en: "Refresh", 'zh-CN': "刷新" },
  "action.regenerate": { en: "Regenerate proposal", 'zh-CN': "重新生成提案" },
  "action.reject": { en: "Reject proposal", 'zh-CN': "拒绝提案" },
  "action.retry": { en: "Try again", 'zh-CN': "重试" },
  "action.retry_authorized": { en: "Try again", 'zh-CN': "重试" },
  "action.return_training": { en: "Return to Training", 'zh-CN': "返回训练" },
  "action.review_invitation": { en: "Review invitation", 'zh-CN': "查看邀请" },
  "action.review_later": { en: "Review later", 'zh-CN': "稍后查看" },
  "action.review_plan": { en: "Review plan", 'zh-CN': "查看计划" },
  "action.review_proposal": { en: "Review proposal", 'zh-CN': "查看提案" },
  "action.safety_feedback": { en: "Report a safety concern privately", 'zh-CN': "私下报告安全问题" },
  "action.send_private": { en: "Send privately", 'zh-CN': "私下发送" },
  "action.sign_in": { en: "Continue to sign in", 'zh-CN': "继续登录" },
  "action.stop_guidance": { en: "Stop Road 10K guidance", 'zh-CN': "停止公路 10K 指导" },
  "action.training": { en: "View in Training", 'zh-CN': "在训练中查看" },
  "action.trust_feedback": { en: "Report a privacy or trust concern privately", 'zh-CN': "私下报告隐私或信任问题" },
  "baseline.body": { en: "Choose a direct 10K result that Praxys marks as current under the accepted Road 10K rules. Converted or predicted results are not accepted.", 'zh-CN': "请选择 Praxys 按已接受的公路 10K 规则判定为当前有效的直接 10K 成绩。不接受换算或预测成绩。" },
  "baseline.empty_body": { en: "Return when your account has a current qualifying direct 10K result. This pilot has no optional baseline test.", 'zh-CN': "当你的账户中有当前有效且符合条件的直接 10K 成绩后再返回。此试点不提供可选基准测试。" },
  "baseline.empty_title": { en: "No current direct 10K baseline", 'zh-CN': "没有当前有效的直接 10K 基准" },
  "baseline.stale_body": { en: "That result is no longer current under the Road 10K rules. Choose another qualifying direct 10K result.", 'zh-CN': "按公路 10K 规则，该成绩已不再有效。请选择其他符合条件的直接 10K 成绩。" },
  "baseline.stale_title": { en: "Baseline no longer current", 'zh-CN': "基准已不再有效" },
  "baseline.title": { en: "Confirm your direct 10K baseline", 'zh-CN': "确认你的直接 10K 基准" },
  "delete.body": { en: "Deleting your account permanently removes your account, synced data, Road 10K rollout data, proposals and plans, settings, platform connections, and encrypted credentials under the current deletion and backup rules. This cannot be undone.", 'zh-CN': "删除账户将按当前删除与备份规则永久移除你的账户、同步数据、公路 10K 试点数据、提案与计划、设置、平台连接和加密凭据。此操作无法撤销。" },
  "delete.confirm": { en: "Type DELETE to confirm", 'zh-CN': "输入 DELETE 以确认" },
  "delete.title": { en: "Delete my account?", 'zh-CN': "删除我的账户？" },
  "disabled.ack": { en: "Review the current notice and check the acknowledgement before joining.", 'zh-CN': "请查看当前说明并勾选确认后再加入。" },
  "disabled.authority": { en: "This action is not available for the current server-authorized state.", 'zh-CN': "当前服务器授权状态不允许此操作。" },
  "disabled.changes": { en: "Change at least one supported plan input before regenerating.", 'zh-CN': "重新生成前，请至少更改一项受支持的计划输入。" },
  "disabled.ended": { en: "This rollout state does not allow new proposal actions.", 'zh-CN': "当前试点状态不允许新的提案操作。" },
  "disabled.expired": { en: "This proposal has expired and cannot be adopted.", 'zh-CN': "此提案已过期，无法采纳。" },
  "disabled.notice": { en: "Joining is unavailable until the current data notice is ready.", 'zh-CN': "当前数据说明准备就绪前无法加入。" },
  "disabled.offline": { en: "Reconnect before taking this action.", 'zh-CN': "请重新连接后再执行此操作。" },
  "disabled.paused": { en: "Proposal actions are unavailable while the rollout is under review or paused.", 'zh-CN': "试点审核中或暂停时，提案操作不可用。" },
  "disabled.plan": { en: "Your current managed Training state does not allow this proposal action.", 'zh-CN': "你当前的托管训练状态不允许执行此提案操作。" },
  "disabled.progress": { en: "Wait for the current request to finish.", 'zh-CN': "请等待当前请求完成。" },
  "disabled.refresh": { en: "Review the latest server status before taking this action.", 'zh-CN': "请先查看最新服务器状态，再执行此操作。" },
  "disabled.successor": { en: "A revised successor is not available for this proposal.", 'zh-CN': "此提案当前无法生成修订后的后续版本。" },
  "eligibility.baseline_body": { en: "Praxys needs a current qualifying direct 10K result before it can create this proposal. Your Goal and Training are unchanged.", 'zh-CN': "Praxys 需要当前有效且符合条件的直接 10K 成绩，才能创建此提案。你的目标和训练保持不变。" },
  "eligibility.baseline_title": { en: "Direct 10K baseline required", 'zh-CN': "需要直接 10K 基准" },
  "eligibility.checking": { en: "Checking your Road 10K information", 'zh-CN': "正在检查你的公路 10K 信息" },
  "eligibility.confirm_body": { en: "Confirm the requested scope or plan inputs before Praxys checks again. No proposal or plan has been created.", 'zh-CN': "请确认所需范围或计划输入，Praxys 才会再次检查。尚未创建任何提案或计划。" },
  "eligibility.confirm_title": { en: "We need your confirmation", 'zh-CN': "需要你的确认" },
  "eligibility.conflict_body": { en: "Review the conflicting details before Praxys checks again. No proposal or plan has been created.", 'zh-CN': "请先检查相互冲突的信息，Praxys 才会再次检查。尚未创建任何提案或计划。" },
  "eligibility.conflict_title": { en: "Some confirmed details conflict", 'zh-CN': "部分已确认信息相互冲突" },
  "eligibility.event_body": { en: "Your confirmed event context does not allow a supported proposal. Praxys will not create a fallback plan. Your Goal and Training are unchanged.", 'zh-CN': "你已确认的赛事情况不允许生成受支持的提案。Praxys 不会创建替代计划。你的目标和训练保持不变。" },
  "eligibility.history_body": { en: "The accepted Road 10K rules cannot create this proposal from the current recent history. Praxys will not create a fallback plan. Your Goal and Training are unchanged.", 'zh-CN': "按已接受的公路 10K 规则，当前近期历史无法生成此提案。Praxys 不会创建替代计划。你的目标和训练保持不变。" },
  "eligibility.history_title": { en: "Not enough recent running history", 'zh-CN': "近期跑步历史不足" },
  "eligibility.limited_title": { en: "Limited guidance only", 'zh-CN': "仅提供有限指导" },
  "eligibility.near_body": { en: "Your confirmed target is too near for a supported taper proposal. Praxys will not create a fallback plan. Your Goal and Training are unchanged.", 'zh-CN': "你已确认的目标时间过近，无法生成受支持的减量提案。Praxys 不会创建替代计划。你的目标和训练保持不变。" },
  "eligibility.ready_body": { en: "Praxys can continue to baseline and supported plan-input confirmation. Nothing changes until you adopt an exact proposal.", 'zh-CN': "Praxys 可以继续进行基准和受支持计划输入的确认。在你采纳某个确切提案前，不会发生任何更改。" },
  "eligibility.ready_title": { en: "Ready to confirm proposal inputs", 'zh-CN': "可以确认提案输入" },
  "eligibility.safety_body": { en: "Praxys has stopped this Road 10K proposal flow under the accepted Road 10K rules. No proposal or plan was created or changed. This is not a diagnosis, treatment, or medical clearance.", 'zh-CN': "Praxys 已按已接受的公路 10K 规则停止此提案流程。没有创建或更改任何提案或计划。这不是诊断、治疗或医疗许可。" },
  "eligibility.safety_title": { en: "Road 10K proposal stopped", 'zh-CN': "公路 10K 提案已停止" },
  "eligibility.schedule_body": { en: "The confirmed schedule cannot produce a proposal within the accepted Road 10K limits. Review the inputs or return to Training; no fallback plan will be created.", 'zh-CN': "已确认的日程无法在已接受的公路 10K 限制内生成提案。请检查输入或返回训练；不会创建替代计划。" },
  "eligibility.schedule_title": { en: "No schedule fits the confirmed inputs", 'zh-CN': "没有符合已确认输入的日程" },
  "eligibility.unavailable_body": { en: "Praxys could not produce a valid Road 10K result from the confirmed inputs. No proposal or plan was created or changed.", 'zh-CN': "Praxys 无法根据已确认的输入生成有效的公路 10K 结果。没有创建或更改任何提案或计划。" },
  "eligibility.unavailable_title": { en: "Road 10K proposal unavailable", 'zh-CN': "公路 10K 提案不可用" },
  "eligibility.unsupported_body": { en: "This limited pilot does not cover the confirmed goal, surface, intent, or population. Praxys will not infer a different goal or create a fallback plan. Your Goal and Training are unchanged.", 'zh-CN': "此有限试点不涵盖已确认的目标、路面、意图或人群。Praxys 不会推断其他目标或创建替代计划。你的目标和训练保持不变。" },
  "eligibility.unsupported_title": { en: "This pilot does not cover this goal", 'zh-CN': "此试点不涵盖该目标" },
  "empty.no_proposal": { en: "No Road 10K proposal has been created. Check the current status to continue.", 'zh-CN': "尚未创建公路 10K 提案。请检查当前状态后继续。" },
  "error.delete": { en: "Your account was not deleted. Review the current status and try again.", 'zh-CN': "你的账户未被删除。请检查当前状态后重试。" },
  "error.export": { en: "Your data export could not be prepared. Nothing changed.", 'zh-CN': "无法准备你的数据导出。没有任何内容发生更改。" },
  "error.feedback": { en: "Your private report was not sent. Review it and try again when the action is available.", 'zh-CN': "你的私密报告未发送。请检查内容，并在操作可用时重试。" },
  "error.generic": { en: "Praxys could not complete this action. Nothing changed.", 'zh-CN': "Praxys 无法完成此操作。没有任何内容发生更改。" },
  "export.body": { en: "Your export includes the Road 10K records available to you under the current data contract. Export does not change Rollout status or Plan status.", 'zh-CN': "你的导出文件包含当前数据约定下你可获取的公路 10K 记录。导出不会更改试点状态或计划状态。" },
  "export.title": { en: "Export my data", 'zh-CN': "导出我的数据" },
  "feedback.comment": { en: "Optional details", 'zh-CN': "可选详情" },
  "feedback.safety_body": { en: "Send this privately for human review. It is not medical care, diagnosis, or emergency support, and it will not be published or sent to AI. Do not include information about another person.", 'zh-CN': "此信息将私下发送并由人工审核。它不属于医疗服务、诊断或紧急支持，也不会公开或发送给 AI。请勿包含他人的信息。" },
  "feedback.safety_title": { en: "Report a safety concern", 'zh-CN': "报告安全问题" },
  "feedback.screenshot_blocked": { en: "Screenshots are unavailable until private deletion and restore handling are verified.", 'zh-CN': "在私密删除和恢复处理完成验证前，截图不可用。" },
  "feedback.screenshot_notice": { en: "A screenshot may contain sensitive information. Review it and remove details about other people before sending.", 'zh-CN': "截图可能包含敏感信息。发送前请检查并移除与他人有关的详情。" },
  "feedback.sent": { en: "Your private report was sent for human review.", 'zh-CN': "你的私密报告已发送，将由人工审核。" },
  "feedback.trust_body": { en: "Send this privately for human Trust review. It will not be published or sent to AI. Do not include information about another person.", 'zh-CN': "此信息将私下发送，由人工信任审核处理；不会公开，也不会发送给 AI。请勿包含他人的信息。" },
  "feedback.trust_title": { en: "Report a privacy or trust concern", 'zh-CN': "报告隐私或信任问题" },
  "generation.body": { en: "Praxys will use the confirmed versioned inputs and accepted Road 10K rules to create one immutable proposal for the returned date horizon. This does not adopt a plan.", 'zh-CN': "Praxys 将使用已确认且带版本的输入和已接受的公路 10K 规则，创建一个覆盖返回日期范围的不可变提案。此操作不会采纳计划。" },
  "generation.fail_end": { en: "No proposal was created. The current Road 10K state does not allow another generation attempt.", 'zh-CN': "未创建提案。当前公路 10K 状态不允许再次生成。" },
  "generation.fail_retry": { en: "No proposal was created. Review the current status and try again only if the action remains available.", 'zh-CN': "未创建提案。请检查当前状态；仅在操作仍可用时重试。" },
  "generation.fail_title": { en: "Proposal generation failed", 'zh-CN': "提案生成失败" },
  "generation.title": { en: "Generate your Road 10K proposal", 'zh-CN': "生成你的公路 10K 提案" },
  "inputs.available_days": { en: "Available running days", 'zh-CN': "可跑步日期" },
  "inputs.body": { en: "Confirm the supported schedule and event details Praxys will use for this proposal. Changing these inputs never edits an existing proposal in place.", 'zh-CN': "确认 Praxys 将用于此提案的受支持日程和赛事信息。更改这些输入绝不会直接修改现有提案。" },
  "inputs.event_status": { en: "Target event status", 'zh-CN': "目标赛事状态" },
  "inputs.invalid": { en: "Review the highlighted plan inputs before continuing.", 'zh-CN': "请先检查标出的计划输入，再继续。" },
  "inputs.longest_day": { en: "Longest-run day", 'zh-CN': "最长跑日期" },
  "inputs.time_available": { en: "Time available", 'zh-CN': "可用时间" },
  "inputs.title": { en: "Confirm your plan inputs", 'zh-CN': "确认你的计划输入" },
  "invitation.body": { en: "You’re invited to a limited process pilot. Joining lets Praxys check whether it can create one deterministic bounded outdoor road 10K proposal for you. Joining does not create or adopt a plan.", 'zh-CN': "你受邀参加一项有限流程试点。加入后，Praxys 可检查是否能为你创建一个确定且有界的户外公路 10K 提案。加入不会创建或采纳计划。" },
  "invitation.title": { en: "Try a Road 10K plan proposal", 'zh-CN': "试用公路 10K 计划提案" },
  "life.close_in": { en: "Enrollment has closed. Your existing proposal or plan follows the current rollout controls shown here; nothing changes automatically.", 'zh-CN': "报名已结束。你的现有提案或计划遵循此处显示的当前试点控制；不会自动发生任何更改。" },
  "life.close_out": { en: "You did not join before enrollment closed. No proposal or plan was created or changed.", 'zh-CN': "你未在报名关闭前加入。没有创建或更改任何提案或计划。" },
  "life.close_title": { en: "Road 10K rollout enrollment is closed", 'zh-CN': "公路 10K 试点报名已关闭" },
  "life.expiry_body": { en: "This exact proposal is read-only and cannot be adopted or regenerated. It was not rejected, and no successor was created automatically. Any adopted plan is unaffected.", 'zh-CN': "此确切提案为只读，无法采纳或重新生成。它未被拒绝，也未自动创建后续版本。任何已采纳计划都不受影响。" },
  "life.expiry_title": { en: "Proposal expired", 'zh-CN': "提案已过期" },
  "life.hold_body": { en: "New enrollment, generation, regeneration, and adoption are unavailable while the rollout is reviewed. Existing proposals are read-only. Adopted plans are unchanged and remain manageable.", 'zh-CN': "试点审核期间，无法新报名、生成、重新生成或采纳。现有提案为只读。已采纳计划保持不变，仍可管理。" },
  "life.hold_title": { en: "Road 10K rollout under review", 'zh-CN': "公路 10K 试点正在审核" },
  "life.kill_body": { en: "Existing proposals are permanent read-only receipts and cannot be adopted. An adopted plan is unchanged and remains manageable; no new Road 10K guidance or successor will be created. This does not say that you stopped training.", 'zh-CN': "现有提案将永久作为只读记录，无法采纳。已采纳计划保持不变，仍可管理；不会创建新的公路 10K 指导或后续版本。这并不表示你已停止训练。" },
  "life.kill_title": { en: "Road 10K rollout access stopped", 'zh-CN': "公路 10K 试点访问已停止" },
  "life.pause_body": { en: "Proposal actions are unavailable. Existing proposals are read-only. An adopted plan is unchanged and remains manageable; leaving, export, deletion, and private reports remain separate controls.", 'zh-CN': "提案操作不可用。现有提案为只读。已采纳计划保持不变，仍可管理；退出、导出、删除和私密报告仍是独立控制。" },
  "life.pause_title": { en: "Road 10K rollout paused", 'zh-CN': "公路 10K 试点已暂停" },
  "life.removed_body": { en: "Your proposal, if any, is now a read-only receipt and cannot be adopted or regenerated. An adopted plan is unchanged and remains manageable in Training.", 'zh-CN': "如有提案，它现在仅作为只读记录，无法采纳或重新生成。已采纳的计划保持不变，仍可在训练中管理。" },
  "life.removed_title": { en: "Your rollout access ended", 'zh-CN': "你的试点访问权限已结束" },
  "life.resume_body": { en: "Praxys will recheck current authorization and eligibility. If the notice changed, you must review it and opt in again. No proposal or plan changes automatically.", 'zh-CN': "Praxys 将重新检查当前授权和适用条件。如果说明已更改，你必须重新查看并再次选择加入。任何提案或计划都不会自动更改。" },
  "life.resume_title": { en: "Road 10K rollout available again", 'zh-CN': "公路 10K 试点再次可用" },
  "life.revision_body": { en: "The current-stage proposal is read-only and cannot be converted or adopted. An adopted plan is unchanged. Any future version needs a new authorized notice, review, and exact adoption.", 'zh-CN': "当前阶段的提案为只读，无法转换或采纳。已采纳计划保持不变。任何未来版本都需要新的已授权说明、审核和确切采纳。" },
  "life.revision_title": { en: "Road 10K rollout revision required", 'zh-CN': "公路 10K 试点需要修订" },
  "life.rollback_body": { en: "The affected proposal remains a read-only receipt and cannot be adopted. An adopted plan is unchanged and remains manageable. No new Road 10K guidance or successor will be created.", 'zh-CN': "受影响的提案仍为只读记录，无法采纳。已采纳计划保持不变，仍可管理。不会创建新的公路 10K 指导或后续版本。" },
  "life.rollback_title": { en: "Road 10K rollout version withdrawn", 'zh-CN': "公路 10K 试点版本已撤回" },
  "life.stop_body": { en: "Existing proposals cannot be adopted or regenerated. An adopted plan is unchanged and remains manageable; no new Road 10K guidance or successor will be created.", 'zh-CN': "现有提案无法采纳或重新生成。已采纳计划保持不变，仍可管理；不会创建新的公路 10K 指导或后续版本。" },
  "life.stop_title": { en: "Road 10K rollout ended", 'zh-CN': "公路 10K 试点已结束" },
  "life.withdraw_body": { en: "Your proposal will become read-only and cannot be adopted or regenerated. Any adopted plan stays in Training and is not paused or ended. Export and account deletion remain available. Rollout data follows the current notice.", 'zh-CN': "你的提案将变为只读，无法采纳或重新生成。任何已采纳计划都会保留在训练中，不会暂停或结束。你仍可导出数据或删除账户。试点数据按当前说明处理。" },
  "life.withdraw_title": { en: "Leave the Road 10K rollout?", 'zh-CN': "退出公路 10K 试点？" },
  "network.conflict_body": { en: "This changed in another session. Your action was not applied. Review the latest server status before acting again.", 'zh-CN': "此内容已在其他会话中更改。你的操作未应用。再次操作前，请查看最新服务器状态。" },
  "network.conflict_title": { en: "Road 10K status changed", 'zh-CN': "公路 10K 状态已更改" },
  "network.last_confirmed": { en: "Last confirmed {saved_time}", 'zh-CN': "上次确认时间：{saved_time}" },
  "network.offline_body": { en: "Road 10K status and actions need a server check. Reconnect before joining, confirming, generating, rejecting, regenerating, adopting, leaving, or sending feedback.", 'zh-CN': "公路 10K 状态和操作需要服务器检查。请重新连接后再加入、确认、生成、拒绝、重新生成、采纳、退出或发送反馈。" },
  "network.offline_title": { en: "You’re offline", 'zh-CN': "你已离线" },
  "network.slow": { en: "Still checking. Don’t repeat the action.", 'zh-CN': "仍在检查。请勿重复操作。" },
  "network.stale_body": { en: "Refresh before taking any Road 10K action. Nothing has been applied from this stale view.", 'zh-CN': "执行任何公路 10K 操作前请先刷新。此过期视图中的任何操作都未应用。" },
  "network.stale_title": { en: "This view is out of date", 'zh-CN': "此视图已过期" },
  "network.unavailable_body": { en: "Praxys cannot verify the current rollout controls. Road 10K proposal actions are unavailable; existing plan controls remain separate.", 'zh-CN': "Praxys 无法验证当前试点控制。公路 10K 提案操作不可用；现有计划控制保持独立。" },
  "network.unavailable_title": { en: "Road 10K controls unavailable", 'zh-CN': "公路 10K 控制不可用" },
  "notice.ack": { en: "I understand and want to join this Road 10K rollout.", 'zh-CN': "我已了解，并希望加入此公路 10K 试点。" },
  "notice.blocked_body": { en: "The accepted data notice or current rollout authorization is not available. You cannot join or take Road 10K proposal actions.", 'zh-CN': "已接受的数据说明或当前试点授权不可用。你无法加入或执行公路 10K 提案操作。" },
  "notice.blocked_title": { en: "Road 10K rollout not available", 'zh-CN': "公路 10K 试点不可用" },
  "notice.claims": { en: "This does not promise faster performance, injury prevention, medical safety, diagnosis, treatment, clearance, or a personal result.", 'zh-CN': "此试点不承诺更快成绩、预防损伤、医疗安全、诊断、治疗、许可或个人结果。" },
  "notice.control": { en: "No AI chooses or adopts the plan. Nothing is sent to a training provider. Nothing changes until you explicitly adopt the exact proposal.", 'zh-CN': "AI 不会选择或采纳计划。任何内容都不会发送给训练服务提供商。在你明确采纳确切提案前，不会发生任何更改。" },
  "notice.data": { en: "The exact data used, access roles, retention, private feedback handling, export, and deletion terms appear in the current data notice below.", 'zh-CN': "下方当前数据说明列出了确切的数据使用、访问角色、保留期限、私密反馈处理、导出和删除条款。" },
  "notice.intro": { en: "This is a limited, default-off process pilot for one deterministic bounded outdoor road 10K proposal. Joining the rollout does not create or adopt a plan.", 'zh-CN': "这是一项默认关闭的有限流程试点，用于生成一个确定且有界的户外公路 10K 提案。加入试点不会创建或采纳计划。" },
  "notice.leave": { en: "You can leave the rollout, export your data, or delete your account. Leaving the rollout does not pause or end an adopted plan.", 'zh-CN': "你可以退出试点、导出数据或删除账户。退出试点不会暂停或结束已采纳计划。" },
  "notice.scope": { en: "Praxys checks your existing Goal, direct 10K baseline, recent running history, and confirmed scheduling constraints under the accepted Road 10K rules.", 'zh-CN': "Praxys 会按已接受的公路 10K 规则，检查你现有的目标、直接 10K 基准、近期跑步历史和已确认的日程限制。" },
  "notice.title": { en: "Join the Road 10K rollout?", 'zh-CN': "加入公路 10K 试点？" },
  "plan.active_body": { en: "This is the exact proposal you adopted. Use existing managed Training controls to review, adjust, pause, end, or delete it. Rollout controls do not replace plan controls, and this rollout does not send the plan to a provider.", 'zh-CN': "这是你采纳的确切提案。请使用现有托管训练控制来查看、调整、暂停、结束或删除计划。试点控制不能替代计划控制，而且此试点不会将计划发送给服务提供商。" },
  "plan.active_title": { en: "Road 10K plan active", 'zh-CN': "公路 10K 计划进行中" },
  "plan.complete_body": { en: "The returned plan window is complete. No extension or successor was created automatically. Rollout status is shown separately.", 'zh-CN': "返回的计划周期已完成。系统未自动创建延长计划或后续版本。试点状态会单独显示。" },
  "plan.complete_title": { en: "Road 10K plan completed", 'zh-CN': "公路 10K 计划已完成" },
  "plan.ended_body": { en: "You ended this plan through managed Training. This did not leave or end the rollout.", 'zh-CN': "你已通过托管训练结束此计划。此操作没有退出或结束试点。" },
  "plan.ended_title": { en: "Road 10K plan ended by you", 'zh-CN': "你已结束公路 10K 计划" },
  "plan.paused_body": { en: "You paused this plan through managed Training. This did not leave or pause the rollout.", 'zh-CN': "你已通过托管训练暂停此计划。此操作没有退出或暂停试点。" },
  "plan.paused_title": { en: "Road 10K plan paused by you", 'zh-CN': "你已暂停公路 10K 计划" },
  "plan.stop_body": { en: "This stops Road 10K recommendations and records the accepted safety-stop state. It does not diagnose a condition, delete, pause, or end the plan, or claim that you stopped training.", 'zh-CN': "此操作会停止公路 10K 建议，并记录已接受的安全停止状态。它不会诊断状况，不会删除、暂停或结束计划，也不表示你已停止训练。" },
  "plan.stop_title": { en: "Stop Road 10K guidance?", 'zh-CN': "停止公路 10K 指导？" },
  "progress.adopting": { en: "Adopting exact proposal…", 'zh-CN': "正在采纳确切提案…" },
  "progress.baseline": { en: "Loading baseline options.", 'zh-CN': "正在加载基准选项。" },
  "progress.checking": { en: "Checking proposal eligibility.", 'zh-CN': "正在检查提案适用条件。" },
  "progress.confirm_baseline": { en: "Confirming baseline…", 'zh-CN': "正在确认基准…" },
  "progress.delete": { en: "Deleting account…", 'zh-CN': "正在删除账户…" },
  "progress.export": { en: "Preparing your data export…", 'zh-CN': "正在准备你的数据导出…" },
  "progress.feedback": { en: "Sending privately…", 'zh-CN': "正在私下发送…" },
  "progress.generating": { en: "Generating the exact proposal…", 'zh-CN': "正在生成确切提案…" },
  "progress.joining": { en: "Joining the Road 10K rollout…", 'zh-CN': "正在加入公路 10K 试点…" },
  "progress.leaving": { en: "Leaving the Road 10K rollout…", 'zh-CN': "正在退出公路 10K 试点…" },
  "progress.loading_access": { en: "Checking Road 10K access.", 'zh-CN': "正在检查公路 10K 访问权限。" },
  "progress.loading_plan": { en: "Loading the managed plan.", 'zh-CN': "正在加载托管计划。" },
  "progress.loading_proposal": { en: "Loading the exact proposal.", 'zh-CN': "正在加载确切提案。" },
  "progress.regenerating": { en: "Generating a revised proposal…", 'zh-CN': "正在生成修订后的提案…" },
  "progress.rejecting": { en: "Rejecting proposal…", 'zh-CN': "正在拒绝提案…" },
  "proposal.adopt_body": { en: "This makes proposal version {version} your managed Road 10K plan in Training. Praxys will not send it to a provider. Rollout status and Plan status remain separate.", 'zh-CN': "此操作会将提案版本 {version} 设为训练中的托管公路 10K 计划。Praxys 不会将其发送给服务提供商。试点状态和计划状态仍会分开显示。" },
  "proposal.adopt_title": { en: "Adopt this exact proposal?", 'zh-CN': "采纳此确切提案？" },
  "proposal.badge": { en: "Proposal — not adopted", 'zh-CN': "提案——尚未采纳" },
  "proposal.body": { en: "This exact proposal is read-only. Reviewing it does not change Training. Nothing changes until you choose Adopt exact proposal and the server confirms that version.", 'zh-CN': "此确切提案为只读。查看它不会更改训练。只有当你选择“采纳此确切提案”且服务器确认该版本后，才会发生更改。" },
  "proposal.created": { en: "Created", 'zh-CN': "创建时间" },
  "proposal.expires": { en: "Expires", 'zh-CN': "到期时间" },
  "proposal.horizon": { en: "Proposal horizon", 'zh-CN': "提案日期范围" },
  "proposal.generator": { en: "Generator", 'zh-CN': "生成器" },
  "proposal.later_body": { en: "This keeps the proposal open until {expiry}. It does not reject it and does not adopt it.", 'zh-CN': "此操作会让提案保持开放至 {expiry}。它不会拒绝提案，也不会采纳提案。" },
  "proposal.later_title": { en: "Review this proposal later?", 'zh-CN': "稍后查看此提案？" },
  "proposal.policy": { en: "Policy", 'zh-CN': "策略" },
  "proposal.regen_body": { en: "Change an allowed plan input first. Praxys will create one new immutable successor and preserve this version as read-only. It will not change an adopted plan.", 'zh-CN': "请先更改一项允许的计划输入。Praxys 将创建一个新的不可变后续版本，并将此版本保留为只读。它不会更改已采纳的计划。" },
  "proposal.regen_title": { en: "Create a revised proposal?", 'zh-CN': "创建修订后的提案？" },
  "proposal.reject_body": { en: "This closes this proposal without changing your Goal, existing Training, or any adopted plan. Rejection is different from Review later.", 'zh-CN': "此操作会关闭该提案，但不会更改你的目标、现有训练或任何已采纳计划。拒绝与“稍后查看”不同。" },
  "proposal.reject_title": { en: "Reject this proposal?", 'zh-CN': "拒绝此提案？" },
  "proposal.science": { en: "Science decision", 'zh-CN': "科学决策" },
  "proposal.title": { en: "Your Road 10K proposal", 'zh-CN': "你的公路 10K 提案" },
  "proposal.version": { en: "Version", 'zh-CN': "版本" },
  "reauth.body": { en: "For your privacy, confirm your first-party Praxys session before reviewing the rollout notice or joining. This does not enroll you.", 'zh-CN': "为保护你的隐私，请先确认你的 Praxys 第一方会话，再查看试点说明或加入。此操作不会让你报名。" },
  "reauth.expired": { en: "Your session expired. Sign in again, then review the latest Road 10K status before taking any action.", 'zh-CN': "你的会话已过期。请重新登录，并在执行任何操作前查看最新的公路 10K 状态。" },
  "reauth.title": { en: "Confirm it’s you", 'zh-CN': "确认是你本人" },
  "status.plan_active": { en: "Plan status: Active", 'zh-CN': "计划状态：进行中" },
  "status.plan_baseline": { en: "Plan status: Baseline required", 'zh-CN': "计划状态：需要基准" },
  "status.plan_checking": { en: "Plan status: Checking", 'zh-CN': "计划状态：检查中" },
  "status.plan_completed": { en: "Plan status: Completed", 'zh-CN': "计划状态：已完成" },
  "status.plan_deleted": { en: "Plan status: Deleted", 'zh-CN': "计划状态：已删除" },
  "status.plan_ended": { en: "Plan status: Ended by you", 'zh-CN': "计划状态：已由你结束" },
  "status.plan_expired": { en: "Plan status: Proposal expired", 'zh-CN': "计划状态：提案已过期" },
  "status.plan_failed": { en: "Plan status: Proposal generation failed", 'zh-CN': "计划状态：提案生成失败" },
  "status.plan_generating": { en: "Plan status: Generating proposal", 'zh-CN': "计划状态：正在生成提案" },
  "status.plan_limited": { en: "Plan status: Limited guidance", 'zh-CN': "计划状态：有限指导" },
  "status.plan_none": { en: "Plan status: No Road 10K plan", 'zh-CN': "计划状态：没有公路 10K 计划" },
  "status.plan_paused": { en: "Plan status: Paused by you", 'zh-CN': "计划状态：已由你暂停" },
  "status.plan_proposal": { en: "Plan status: Proposal ready — not adopted", 'zh-CN': "计划状态：提案已就绪——尚未采纳" },
  "status.plan_rejected": { en: "Plan status: Proposal rejected", 'zh-CN': "计划状态：提案已拒绝" },
  "status.plan_review_later": { en: "Plan status: Proposal saved for later review", 'zh-CN': "计划状态：提案已保留供稍后查看" },
  "status.plan_safety": { en: "Plan status: Safety stop", 'zh-CN': "计划状态：安全停止" },
  "status.plan_successor": { en: "Plan status: Revised proposal ready", 'zh-CN': "计划状态：修订后的提案已就绪" },
  "status.rollout_enrolled": { en: "Rollout status: Enrolled", 'zh-CN': "试点状态：已加入" },
  "status.rollout_hold": { en: "Rollout status: On hold", 'zh-CN': "试点状态：审核中" },
  "status.rollout_invited": { en: "Rollout status: Invited", 'zh-CN': "试点状态：已邀请" },
  "status.rollout_killed": { en: "Rollout status: Access stopped", 'zh-CN': "试点状态：访问已停止" },
  "status.rollout_paused": { en: "Rollout status: Paused", 'zh-CN': "试点状态：已暂停" },
  "status.rollout_removed": { en: "Rollout status: Access ended", 'zh-CN': "试点状态：访问已结束" },
  "status.rollout_revision": { en: "Rollout status: Revision required", 'zh-CN': "试点状态：需要修订" },
  "status.rollout_rollback": { en: "Rollout status: Rolled back", 'zh-CN': "试点状态：已回滚" },
  "status.rollout_stopped": { en: "Rollout status: Ended", 'zh-CN': "试点状态：已结束" },
  "status.rollout_withdrawn": { en: "Rollout status: Left rollout", 'zh-CN': "试点状态：已退出" },
  "success.adopted": { en: "Proposal {version} adopted. Your managed Road 10K plan is now active.", 'zh-CN': "已采纳提案 {version}。你的托管公路 10K 计划现已启用。" },
  "success.baseline": { en: "Baseline confirmed. No proposal or plan has been created or adopted.", 'zh-CN': "基准已确认。尚未创建或采纳任何提案或计划。" },
  "success.deleted": { en: "Your account was deleted.", 'zh-CN': "你的账户已删除。" },
  "success.export": { en: "Your data export is ready.", 'zh-CN': "你的数据导出已准备好。" },
  "success.guidance_stopped": { en: "Road 10K guidance stopped. Your adopted plan and its controls are unchanged.", 'zh-CN': "公路 10K 指导已停止。你已采纳的计划及其控制保持不变。" },
  "success.joined": { en: "You joined the Road 10K rollout. No plan has been created or adopted.", 'zh-CN': "你已加入公路 10K 试点。尚未创建或采纳任何计划。" },
  "success.later": { en: "Saved for later review. The proposal was not rejected or adopted.", 'zh-CN': "已保留供稍后查看。该提案未被拒绝，也未被采纳。" },
  "success.rejected": { en: "Proposal rejected. Your Goal, existing Training, and any adopted plan are unchanged.", 'zh-CN': "提案已拒绝。你的目标、现有训练和任何已采纳计划保持不变。" },
  "success.successor": { en: "Revised proposal created. The earlier version remains read-only and unchanged.", 'zh-CN': "修订后的提案已创建。先前版本仍为只读且保持不变。" },
  "success.withdrawn": { en: "You left the Road 10K rollout. Your adopted plan, if any, is unchanged and was not paused or ended.", 'zh-CN': "你已退出公路 10K 试点。如有已采纳计划，它保持不变，未被暂停或结束。" },
} as const;

export type Road10KCopyKey = keyof typeof ROAD_10K_COPY;

export const ROAD_10K_SCREENSHOT_AVAILABLE = false as const;

export const ROAD_10K_ROLLOUT_STATES = [
  "invited", "enrolled", "hold", "withdrawn", "removed", "paused", "killed", "rollback", "stopped", "revision",
] as const;
export type Road10KExperienceRolloutState =
  (typeof ROAD_10K_ROLLOUT_STATES)[number];

export const ROAD_10K_PLAN_STATES = [
  "none", "checking", "baseline-required", "limited-guidance", "safety-stop", "generating", "generation-failed", "proposal-ready", "review-later", "rejected", "successor-requested", "expired", "active", "paused-by-owner", "ended-by-owner", "completed", "deleted",
] as const;
export type Road10KExperiencePlanState =
  (typeof ROAD_10K_PLAN_STATES)[number];

export const ROAD_10K_ROLLOUT_STATUS_COPY = {
  "invited": "status.rollout_invited",
  "enrolled": "status.rollout_enrolled",
  "hold": "status.rollout_hold",
  "withdrawn": "status.rollout_withdrawn",
  "removed": "status.rollout_removed",
  "paused": "status.rollout_paused",
  "killed": "status.rollout_killed",
  "rollback": "status.rollout_rollback",
  "stopped": "status.rollout_stopped",
  "revision": "status.rollout_revision",
} as const satisfies Record<Road10KExperienceRolloutState, Road10KCopyKey>;

export const ROAD_10K_ACCESS_STATE_COPY = {
  "invited": ["invitation.title", "invitation.body", "status.rollout_invited", "status.plan_none"],
  "enrolled": ["success.joined", "status.rollout_enrolled", "status.plan_none"],
  "hold": ["life.hold_title", "life.hold_body"],
  "withdrawn": ["status.rollout_withdrawn", "success.withdrawn"],
  "removed": ["life.removed_title", "life.removed_body"],
  "paused": ["life.pause_title", "life.pause_body"],
  "killed": ["life.kill_title", "life.kill_body"],
  "rollback": ["life.rollback_title", "life.rollback_body"],
  "stopped": ["life.stop_title", "life.stop_body"],
  "revision": ["life.revision_title", "life.revision_body"],
} as const satisfies Record<
  Road10KExperienceRolloutState,
  readonly Road10KCopyKey[]
>;

export function road10kAccessStateCopy(
  rolloutStatus: Road10KExperienceRolloutState,
  planStatus: Road10KExperiencePlanState,
): readonly Road10KCopyKey[] {
  void planStatus;
  return ROAD_10K_ACCESS_STATE_COPY[rolloutStatus];
}

export function road10kRolloutSummaryCopy(
  rolloutStatus: Road10KExperienceRolloutState,
  planStatus: Road10KExperiencePlanState,
): { title: Road10KCopyKey; body: Road10KCopyKey } {
  const keys = road10kAccessStateCopy(rolloutStatus, planStatus);
  const title = rolloutStatus === 'enrolled'
    ? 'status.rollout_enrolled'
    : keys[0];
  const body = rolloutStatus === 'enrolled'
    ? 'success.joined'
    : rolloutStatus === 'invited'
      ? 'invitation.body'
      : (keys[keys.length - 1] ?? title);
  return { title, body };
}

export const ROAD_10K_PLAN_STATE_COPY = {
  "none": ["status.plan_none", "empty.no_proposal"],
  "checking": ["status.plan_checking", "progress.checking"],
  "baseline-required": ["status.plan_baseline", "eligibility.baseline_title", "eligibility.baseline_body"],
  "limited-guidance": ["status.plan_limited", "eligibility.limited_title"],
  "safety-stop": ["status.plan_safety", "eligibility.safety_title", "eligibility.safety_body"],
  "generating": ["status.plan_generating", "progress.generating"],
  "generation-failed": ["status.plan_failed", "generation.fail_title"],
  "proposal-ready": ["status.plan_proposal", "proposal.title", "proposal.body"],
  "review-later": ["status.plan_review_later", "success.later"],
  "rejected": ["status.plan_rejected", "success.rejected"],
  "successor-requested": ["status.plan_successor", "success.successor"],
  "expired": ["status.plan_expired", "life.expiry_title", "life.expiry_body"],
  "active": ["status.plan_active", "plan.active_title", "plan.active_body"],
  "paused-by-owner": ["status.plan_paused", "plan.paused_title", "plan.paused_body"],
  "ended-by-owner": ["status.plan_ended", "plan.ended_title", "plan.ended_body"],
  "completed": ["status.plan_completed", "plan.complete_title", "plan.complete_body"],
  "deleted": ["status.plan_deleted", "success.deleted"],
} as const satisfies Record<
  Road10KExperiencePlanState,
  readonly Road10KCopyKey[]
>;

export const ROAD_10K_NETWORK_STATE_COPY = {
    "offline": ["network.offline_title", "network.offline_body", "action.retry"],
  "slow": ["network.slow"],
  "stale": ["network.stale_title", "network.stale_body", "action.refresh"],
  "conflict": ["network.conflict_title", "network.conflict_body", "action.latest"],
  "unknown-control": ["network.unavailable_title", "network.unavailable_body"],
  "session-expired": ["reauth.expired", "action.sign_in", "action.cancel"],
} as const satisfies Record<
  'offline' | 'slow' | 'stale' | 'conflict' | 'unknown-control' | 'session-expired',
  readonly Road10KCopyKey[]
>;

export function road10kCopy(
  key: Road10KCopyKey,
  locale: 'en' | 'zh-CN' = 'en',
): string {
  return ROAD_10K_COPY[key][locale] ?? ROAD_10K_COPY[key].en;
}

export interface Road10KTaperScienceCopy {
  title: string;
  horizon: string;
  event_eve: string;
  body: string;
  source_label: string;
  source_path: string;
}

export function road10kTaperScienceCopy(
  taper: Road10KTaperGuardrailProjection,
  locale: 'en' | 'zh-CN' = 'en',
): Road10KTaperScienceCopy {
  const percent = new Intl.NumberFormat(locale, {
    style: 'percent',
    maximumFractionDigits: 0,
  }).format(taper.planned_volume_reduction_fraction);
  const intensity = taper.maintain_intensity_exposure_without_adding_quality
    ? locale === 'zh-CN'
      ? '保持强度接触且不增加质量课'
      : 'maintains intensity exposure without adding quality'
    : locale === 'zh-CN'
      ? '不保证保持强度接触'
      : 'does not promise maintained intensity exposure';
  const evidence = taper.evidence_population === 'mixed_endurance_athletes'
    ? locale === 'zh-CN'
      ? '证据来自混合耐力运动员人群，属于间接证据'
      : 'evidence is indirect from mixed-endurance athletes'
    : locale === 'zh-CN'
      ? '证据人群适用性有限'
      : 'the evidence population has limited applicability';
  const validation = taper.direct_recreational_road_10k_validation
    ? locale === 'zh-CN'
      ? '已有休闲公路 10K 跑者的直接验证'
      : 'has direct validation in recreational road 10K runners'
    : locale === 'zh-CN'
      ? '没有休闲公路 10K 跑者的直接验证'
      : 'has no direct validation in recreational road 10K runners';
  const eventEve = taper.single_target_taper_result
    === 'taper_proposal_truncated_to_event_eve'
    ? locale === 'zh-CN'
      ? '单一目标赛事提案在赛前一日结束'
      : 'the single-target proposal is truncated to event eve'
    : locale === 'zh-CN'
      ? '提案遵循返回的赛事边界'
      : 'the proposal follows its returned event boundary';
  const noPersonalClaims = (
    !taper.personal_performance_gain_claim
    && taper.causal_plan_benefit_claim === 'disabled'
    && taper.personal_injury_probability === 'disabled'
  )
    ? locale === 'zh-CN'
      ? '不声称个人表现提升、计划因果收益或个人伤害概率及安全收益'
      : 'does not claim a personal performance gain, causal plan benefit, or personal injury probability or safety benefit'
    : locale === 'zh-CN'
      ? '个人收益和安全结果仍存在不确定性'
      : 'personal benefit and safety outcomes remain uncertain';

  return {
    title: locale === 'zh-CN' ? '减量依据与限制' : 'Taper evidence and limits',
    horizon: locale === 'zh-CN' ? '提案日期范围' : 'Proposal horizon',
    event_eve: locale === 'zh-CN' ? '赛前一日' : 'event eve',
    body: locale === 'zh-CN'
      ? `已接受的减量规则将计划量相对同日期非减量日程降低 ${percent}，${intensity}；${eventEve}。${evidence}，${validation}。此规则${noPersonalClaims}。`
      : `The accepted taper guardrail reduces planned volume by ${percent} versus the matching non-taper schedule and ${intensity}; ${eventEve}. The ${evidence} and ${validation}. It ${noPersonalClaims}.`,
    source_label: locale === 'zh-CN'
      ? '已接受的公路 10K 计划生成政策'
      : 'Accepted road 10K plan-generation policy',
    source_path: 'data/science/decisions/sdr-road-10k-plan-generation-policy-v2.yaml',
  };
}
