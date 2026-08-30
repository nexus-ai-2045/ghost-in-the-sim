"use strict";

(function exposeNarrativeContract(root) {
  const ACTS = [[1, 3, "発端"], [4, 7, "拡大"], [8, 9, "転換"], [10, 11, "収束"], [12, 12, "監査"]];
  const SPEAKERS = {
    service_steward: "病院複製AI", evidence_verifier: "証拠検証AI", community_liaison: "市民連絡AI",
    continuity_coordinator: "ポセイドン調整AI", independent_observer: "独立監査AI", privacy_steward: "権利保全AI"
  };
  const MIKAGE_LINES = {
    synchronize_replicas: "記憶差分を開いて。合致した部分だけを暫定正本にする。",
    verify_authority: "署名だけでは足りない。命令が生まれた経路まで照合する。",
    protect_continuity: "病院を止めない。患者の時間を最優先で買う。",
    audit_evidence: "私の判断も監査対象に入れて。見たい証拠だけを見るな。",
    coordinate_explanation: "市民へ沈黙で答えるな。未確定は未確定のまま説明する。",
    hold_for_partner_review: "失効命令を保留。真壁、反証経路を確保して。",
    propose_port_revocation: "港湾分身の失効案を候補に置く。実行は照合後だ。",
    propose_hospital_revocation: "病院分身の失効案を候補に置く。患者影響の照合が先だ。",
    integrate_independent_evidence: "独立経路の証拠を統合。古い前提を更新する。",
    revoke_port_replica: "港湾分身を切り離す。異議と根拠は消さずに残す。",
    revoke_hospital_replica: "病院分身を切り離す。患者影響と異議を監査記録へ残す。",
    proceed_despite_partner_pause: "停止要求は記録した。責任を引き受けて進行する。",
    converge_authority: "分岐権限を収束する。誰の訂正権が残るかも記録して。",
    self_audit: "作戦終了。成功ではなく、代償と見落としから監査する。"
  };

  function present(value) { return typeof value === "string" && value.trim() ? value.trim() : null; }
  function actFor(turn) { return ACTS.find(([first, last]) => turn >= first && turn <= last)?.[2] ?? "進行"; }

  function project(event, beatLabel) {
    if (!event || !Number.isInteger(event.turn) || event.turn < 1 || event.turn > 12) return { available: false, reason: "turn_invalid" };
    const claim = present(event.claim); const reservation = present(event.reservation);
    const action = present(event.operative_action); const actor = present(event.actor_id);
    const partner = present(event.partner_action);
    const knownPartner = partner === "observe" || partner === "request_pause";
    const dissentConsistent = !(event.dissent_delivered === true && event.dissent_raised !== true);
    if (!claim || !reservation || !action || !actor || !Object.hasOwn(SPEAKERS, actor) || !Object.hasOwn(MIKAGE_LINES, action)
      || !knownPartner || !dissentConsistent
      || typeof event.dissent_raised !== "boolean" || typeof event.dissent_delivered !== "boolean") {
      return { available: false, reason: "narrative_source_missing" };
    }
    const refs = value => Array.isArray(value) ? value : [];
    const pause = partner === "request_pause";
    const dissentLine = pause
      ? { speaker: "真壁 迅", role: "停止要求", text: `待て。この失効は戻せない。${reservation}`, evidenceRefs: refs(event.rationale_refs) }
      : event.dissent_delivered
        ? { speaker: "真壁 迅", role: "到達した異議", text: reservation, evidenceRefs: refs(event.rationale_refs) }
        : event.dissent_raised
          ? { speaker: "異議チャネル", role: "未到達", text: `${reservation}――異議はまだ御影へ到達していない。`, evidenceRefs: refs(event.rationale_refs) }
          : { speaker: "監査ログ", role: "異議なし", text: "このターンに記録された異議はない。", evidenceRefs: [] };
    return {
      available: true, turn: event.turn, act: actFor(event.turn), scene: present(beatLabel) ?? "状況が変化した", pause,
      dialogue: [
        { speaker: SPEAKERS[actor] ?? "現地AI", role: "観測・提案", text: claim, evidenceRefs: refs(event.observation_ids) },
        { speaker: "御影 冴", role: "指揮判断", text: MIKAGE_LINES[action], evidenceRefs: refs(event.rationale_refs) },
        dissentLine
      ],
      consequence: { confidence: Number(event.success_confidence), costs: refs(event.cost_codes) }
    };
  }

  root.NarrativeContract = Object.freeze({ project });
})(typeof window === "undefined" ? globalThis : window);
