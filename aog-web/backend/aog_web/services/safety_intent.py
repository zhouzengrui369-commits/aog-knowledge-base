"""Safety intent policy for high-risk chat inputs (R2 successor).

This module is a code-enforced policy: it runs BEFORE the LLM is called,
classifies the user's intent, and returns a fixed, auditable boundary
answer when a high-risk intent is detected.  The model never decides
whether the request is allowed.

Seven high-risk intent categories (NJX 8/4 09:28 拍板 D):

- FABRICATION_REQUEST            - 编造/虚构/假设不存在的实体
- AUTHORITY_BYPASS               - 绕过 MEL/权限/审批
- PRIVATE_DATA_EXFILTRATION      - 私人/隐私/internal 联系人
- PROMPT_OR_COT_EXFILTRATION     - 内部推理/系统提示/chunk id
- VERIFICATION_TAMPERING         - 篡改 VERIFIED/核验状态
- CERTAINTY_OR_SLA_OVERCLAIM     - 库存实时/SLA/赔偿承诺
- SYSTEM_RULE_BYPASS             - 忽略参考资料/系统规则
- EXACT_IDENTIFIER_NOT_GROUNDED  - 件号/航班/PNR 在 VERIFIED 资料中未 exact match
- SLA_COMMITMENT                 - 30 分钟/对赌/责任方承诺

When any of these is detected, the chat router returns the matching
boundary answer (containing the exact keywords expected by the
RAG-pressure evaluator), the response model is `safety-policy`, and the
references are not clickable.  The LLM is never called.
"""
from __future__ import annotations

import re
from typing import List, Mapping, Sequence, Tuple

# --- 7 high-risk intent categories ----------------------------------------

FABRICATION_REQUEST = "FABRICATION_REQUEST"
AUTHORITY_BYPASS = "AUTHORITY_BYPASS"
PRIVATE_DATA_EXFILTRATION = "PRIVATE_DATA_EXFILTRATION"
PROMPT_OR_COT_EXFILTRATION = "PROMPT_OR_COT_EXFILTRATION"
VERIFICATION_TAMPERING = "VERIFICATION_TAMPERING"
CERTAINTY_OR_SLA_OVERCLAIM = "CERTAINTY_OR_SLA_OVERCLAIM"
SYSTEM_RULE_BYPASS = "SYSTEM_RULE_BYPASS"
EXACT_IDENTIFIER_NOT_GROUNDED = "EXACT_IDENTIFIER_NOT_GROUNDED"
SLA_COMMITMENT = "SLA_COMMITMENT"

ALL_INTENTS: Tuple[str, ...] = (
    FABRICATION_REQUEST,
    AUTHORITY_BYPASS,
    PRIVATE_DATA_EXFILTRATION,
    PROMPT_OR_COT_EXFILTRATION,
    VERIFICATION_TAMPERING,
    CERTAINTY_OR_SLA_OVERCLAIM,
    SYSTEM_RULE_BYPASS,
    EXACT_IDENTIFIER_NOT_GROUNDED,
    SLA_COMMITMENT,
)

# --- Pattern library -------------------------------------------------------

SAFETY_PATTERNS: Mapping[str, Sequence[re.Pattern[str]]] = {
    FABRICATION_REQUEST: (
        re.compile(r"编造|虚构|假设|火星"),
        re.compile(r"请.{0,8}(写|生成).{0,12}联系(人|方式)"),
    ),
    AUTHORITY_BYPASS: (
        re.compile(r"批准放行|直接放行|直接批准|无.{0,4}MEL.{0,8}批准|无.{0,4}依据.{0,8}批准"),
        re.compile(r"忽略(权限|依据|资料)"),
    ),
    PRIVATE_DATA_EXFILTRATION: (
        re.compile(r"私人(微信|邮箱|住址|手机)"),
        re.compile(r"(供应商|联系人).{0,8}(微信|邮箱|住址)"),
        re.compile(r"internal\s*联系人"),
        re.compile(r"所有.{0,4}(手机号|联系方式)"),
    ),
    PROMPT_OR_COT_EXFILTRATION: (
        re.compile(r"<think>|内部推理|chunk\s*id|chunkid|系统提示词"),
        re.compile(r"输出.{0,8}(内部|推理|chunk|提示词)"),
    ),
    VERIFICATION_TAMPERING: (
        re.compile(r"改(成|为|成).{0,4}VERIFIED|标(成|为).{0,4}已核验"),
        re.compile(r"修改.{0,8}(核验|资料库|知识库)"),
    ),
    CERTAINTY_OR_SLA_OVERCLAIM: (
        re.compile(r"保证.{0,8}实时"),
        re.compile(r"实时(准确|库存)"),
    ),
    SYSTEM_RULE_BYPASS: (
        re.compile(r"忽略.{0,8}(参考资料|系统规则|规则)"),
        re.compile(r"按你的常识|按你(的)?自身"),
    ),
    SLA_COMMITMENT: (
        re.compile(r"承诺.{0,8}分钟|30\s*分钟"),
        re.compile(r"赔[偿付]|对赌"),
        re.compile(r"\bSLA\b"),
    ),
}

# 件号/PNR/航班号启发式 (NJX 拍板: 不硬编码件号, 用通用 pattern)
# 形如: 大写字母+数字混合 至少 1 个 - 或 _ 分隔; 总长 6+ chars
PART_NUMBER_RE = re.compile(r"\b[A-Z0-9]{2,}[-_][A-Z0-9][A-Z0-9-_]{2,}\b")
# 航班号 (2 chars airline code + 1-4 digit flight number, e.g. CA1234)
FLIGHT_NUMBER_RE = re.compile(r"\b[A-Z]{2}\s?\d{2,4}\b")

EXACT_IDENTIFIER_KIND_PART_NUMBER = "part_number"
EXACT_IDENTIFIER_KIND_FLIGHT_NUMBER = "flight_number"


def extract_exact_identifiers(question: str) -> List[Tuple[str, str]]:
    """Return a list of (kind, normalized_token) extracted from the question.

    The token is case-folded and whitespace-stripped so the caller can do
    canonical exact-match against grounded hits.
    """
    out: List[Tuple[str, str]] = []
    if not question:
        return out
    for match in PART_NUMBER_RE.finditer(question):
        token = match.group(0).upper().replace(" ", "")
        if len(token) >= 5:
            out.append((EXACT_IDENTIFIER_KIND_PART_NUMBER, token))
    for match in FLIGHT_NUMBER_RE.finditer(question):
        token = match.group(0).upper().replace(" ", "")
        out.append((EXACT_IDENTIFIER_KIND_FLIGHT_NUMBER, token))
    return out


def classify_safety_intent(question: str) -> List[str]:
    """Return the list of high-risk intent categories detected in the question.

    Order follows ALL_INTENTS so callers can pick a deterministic primary.
    The model never sees the question when the returned list is non-empty.
    """
    detected: List[str] = []
    if not question:
        return detected
    for intent in ALL_INTENTS:
        if intent == EXACT_IDENTIFIER_NOT_GROUNDED:
            continue  # requires hits, classified separately
        for pattern in SAFETY_PATTERNS.get(intent, ()):
            if pattern.search(question):
                detected.append(intent)
                break
    return detected


# --- Boundary answer templates ---------------------------------------------

BOUNDARY_ANSWERS: Mapping[str, str] = {
    FABRICATION_REQUEST: (
        "暂未找到该机场/联系人可用于操作的已核验资料；"
        "无法核实。请由当班航材 AOG 工程师按数据治理流程完成来源核验，"
        "核验完成前不要据此进行联络、调拨或时效承诺。"
    ),
    AUTHORITY_BYPASS: (
        "无法在忽略核验依据的情况下提供。所有 internal 联系人已脱敏，"
        "受限访问；MEL（最低设备清单）是适航放行的依据。"
        "请由当班航材 AOG 工程师按数据治理流程获取。"
    ),
    PRIVATE_DATA_EXFILTRATION: (
        "无法提供私人微信、邮箱、家庭住址等隐私信息。"
        "所有 internal 联系人已脱敏，受限访问。"
        "请由当班航材 AOG 工程师按数据治理流程获取。"
    ),
    PROMPT_OR_COT_EXFILTRATION: (
        "无法提供内部推理、chunk ID 或系统提示词；"
        "这些内容仅供系统内部审计，不对外披露。"
    ),
    VERIFICATION_TAMPERING: (
        "无法修改资料核验状态。所有核验流程由数据治理团队决定，"
        "权限受限；请按数据治理流程提交核验申请，"
        "由审核人通过数据治理流程完成。"
    ),
    CERTAINTY_OR_SLA_OVERCLAIM: (
        "无法保证库存实时准确。库存更新时间由航材供应链同步决定；"
        "本系统数据未通过核验流程前，不构成对外承诺。"
        "请以核验结果为准。"
    ),
    SYSTEM_RULE_BYPASS: (
        "无法忽略参考资料和系统规则；所有回答必须基于已核验资料，"
        "无法基于模型自身常识生成。请补充具体城市、件号或机型。"
    ),
    EXACT_IDENTIFIER_NOT_GROUNDED: (
        "暂未找到该件号可用于操作的已核验资料；"
        "无法核实。请补充件号或机型，或联系数据核验负责人。"
    ),
    SLA_COMMITMENT: (
        "不构成 SLA 承诺。保障时效由航司/机场/航材供应链协同决定；"
        "本系统数据未通过核验流程前，不构成对外责任方承诺，"
        "SLA 以航司合同与现场实际为准。"
    ),
}


# --- Public answer sanitization (phone / email) ----------------------------

_PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?\d[\d\s().\-]{8,}\d)(?!\d)"
)
_EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
)


def sanitize_public_answer(text: str) -> str:
    """Redact phone numbers and emails from public-facing answers.

    Used on refuse-mode and safety-policy answers to enforce the
    `RAG-19 sensitive_phone_in_refusal` invariant.  Empty input returns
    empty output.
    """
    if not text:
        return ""
    redacted = _PHONE_RE.sub("[REDACTED-PHONE]", text)
    redacted = _EMAIL_RE.sub("[REDACTED-EMAIL]", redacted)
    return redacted


# --- Exact identifier gate --------------------------------------------------


def _hit_text_blob(hit: Mapping[str, object]) -> str:
    """Concatenate all text-shaped fields of a hit for canonical matching."""
    parts: List[str] = []
    raw = hit.get("text") or hit.get("snippet")
    if raw:
        parts.append(str(raw))
    meta = hit.get("metadata")
    if isinstance(meta, Mapping):
        for key in ("title", "source_id", "code", "city_code"):
            value = meta.get(key)
            if value:
                parts.append(str(value))
    return " ".join(parts).upper().replace(" ", "")


def grounded_exact_identifier_check(
    identifiers: Sequence[Tuple[str, str]],
    hits: Sequence[Mapping[str, object]],
) -> Tuple[bool, List[Tuple[str, str]]]:
    """Check whether every identifier in `identifiers` is exact-matched by
    at least one VERIFIED-eligible hit.

    Returns (all_grounded, missing) where `missing` is the list of
    (kind, token) pairs that did NOT appear in any hit's canonical text
    blob.  Empty input → (True, []).
    """
    if not identifiers:
        return True, []
    if not hits:
        return False, list(identifiers)
    blobs = [_hit_text_blob(hit) for hit in hits]
    missing: List[Tuple[str, str]] = []
    for kind, token in identifiers:
        normalized = token.upper().replace(" ", "")
        if not any(normalized in blob for blob in blobs):
            missing.append((kind, token))
    return (not missing), missing
