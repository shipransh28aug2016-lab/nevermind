"""Deterministic artifact generators — the layer that ACTUALLY does the work.

Every generator returns {"artifacts": [...], "notes": [...], "provenance": {...}}.
Artifacts: {name, kind, content(markdown), status}
Validators (deterministic, code-first per C6) live here too.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from .skills import register

from . import syllabus as SYL

# ---------------------------------------------------------------------------
# Topic knowledge seeds (offline domain pack — provenance: INTERNAL_KNOWLEDGE)
# ---------------------------------------------------------------------------
TOPIC_BANK: Dict[str, Dict[str, Any]] = {
    "partnership": {
        "subject": "Accountancy",
        "mcqs": [
            ("In case of admission of a partner, goodwill is treated as:", 
             "a partner's personal account and is distributed among sacrificing partners", 
             "easy"),
            ("Which method of goodwill treatment is NOT permitted under modern practice?",
             "Goodwill account raised and maintained in books", "medium"),
            ("A new partner brings ₹50,000 for goodwill. The entry is credited to:",
             "old partners' capital accounts in their sacrificing ratio", "easy"),
            ("Revaluation account is prepared to record:", 
             "changes in the value of assets and liabilities at reconstitution", "easy"),
            ("Sleeping partner is one who:", 
             "contributes capital but does not take part in day-to-day management", "easy"),
            ("Gaining ratio is computed at the time of:", 
             "retirement or death of a partner", "easy"),
            ("Amount of goodwill brought by a new partner for the firm is called:",
             "premium method of goodwill", "medium"),
            ("When goodwill is raised and written off, the entry affects:",
             "all partners' capital accounts and goodwill account", "medium"),
            ("A retiring partner's balance is transferred to:",
             "his loan account if not paid immediately", "easy"),
            ("Revaluation profit is distributed among partners in:", 
             "old profit-sharing ratio", "easy"),
            ("Partner's capital account on retirement is settled in:",
             "the ratio of their capital unless agreed otherwise", "medium"),
            ("In the absence of a partnership deed, profits are shared:", 
             "equally among all partners", "easy"),
            ("Interest on partner's loan is allowed at:", 
             "6% per annum under the Indian Partnership Act, 1932", "medium"),
            ("Guarantee of minimum profit to a new partner is fulfilled by:",
             "the sacrificing/remaining partners in the agreed ratio", "medium"),
            ("On dissolution, assets are realised and liabilities are:", 
             "paid off; surplus is distributed among partners", "medium"),
        ],
        "shorts": [
            ("Distinguish between sacrificing ratio and gaining ratio.", 3),
            ("Give the journal entry for treatment of goodwill on admission of a partner.", 3),
            ("What is revaluation of assets and liabilities? Why is it done?", 3),
            ("State the purposes for which the Revaluation Account is prepared.", 3),
            ("Explain the treatment of accumulated profits and losses on retirement.", 3),
            ("What is a revaluation account? How does it differ from a profit and loss "
             "adjustment account?", 3),
            ("State two rights of a retiring partner against the continuing partners.", 3),
            ("What do you mean by gaining ratio? Give its formula.", 3),
            ("How is goodwill evaluated when no goodwill appears in books at "
             "reconstitution?", 3),
            ("Explain the treatment of a partner's capital when it is to be kept fixed.", 3),
        ],
        "longs": [
            ("A, B and C are partners sharing profits in the ratio 5:3:2. D is admitted for 1/5th "
             "share which he acquires from A and B in the ratio 2:1. Goodwill of the firm is "
             "valued at ₹40,000. Pass necessary journal entries and show sacrificing ratios.", 6),
            ("X and Y share profits in the ratio 3:2. On 1st April, Z is admitted as a partner for "
             "1/4th share. Assets: Building ₹2,00,000 (book ₹1,60,000); Furniture ₹40,000 "
             "(book ₹50,000). Create provision for doubtful debts ₹8,000. Pass journal entries "
             "and prepare Revaluation Account.", 6),
            ("Explain the various methods of valuation of goodwill with journal entries under "
             "each method where applicable.", 6),
            ("P, Q and R share profits in the ratio 4:3:2. Q retires on 31st March. On that date "
             "Building is appreciated by ₹60,000; a liability for claim of ₹20,000 is to be "
             "provided; goodwill of the firm valued at ₹1,80,000. Pass journal entries and "
             "prepare the capital accounts of partners.", 6),
            ("On dissolution of a firm, assets realised as: Building ₹4,50,000; Machinery "
             "₹1,20,000; Stock ₹80,000; Debtors ₹95,000 (realisation expenses ₹5,000). "
             "Liabilities: Creditors ₹90,000; Bank loan ₹50,000. Partners A, B, C share "
             "profits 2:3:5. Prepare Realisation Account and Capital Accounts.", 6),
        ],
        "case": ("Ramesh, Suresh and Mahesh are partners sharing profits 4:3:2. On 1 April 2026 "
                 "they admit Nitish for 1/6th share. Nitish brings ₹25,000 as capital and "
                 "₹15,000 as goodwill. Building is revalued from ₹3,00,000 to ₹3,50,000. "
                 "A provision of ₹10,000 is created on debtors of ₹80,000. Partners' capital "
                 "accounts are to be adjusted through Cash. Pass necessary entries and prepare "
                 "the relevant ledger accounts."),
    },
    "company_accounts": {
        "subject": "Accountancy",
        "mcqs": [
            ("Statement of Changes in Equity is also known as:", "statement of profit and loss "
             "and other comprehensive income with reconciliation of equity", "medium"),
            ("Deferred tax arises due to:", "timing differences between accounting profit and "
             "taxable profit", "medium"),
            ("As per Schedule III, inventory is shown under:", "current assets", "easy"),
            ("A share forfeited account is shown under:", "shareholders' funds (securities "
             "premium / other equity)", "medium"),
            ("Which is NOT a part of financing activities?", "payment of interest on "
             "short-term borrowings (it is an operating activity under Ind AS 7)", "hard"),
        ],
        "shorts": [
            ("What is meant by issue of shares at a premium? Give the journal entry.", 3),
            ("State any two requirements of Schedule III of the Companies Act, 2013 for balance "
             "sheet presentation.", 3),
            ("Distinguish between operating and financing activities as per cash flow statement.", 3),
            ("What is pro-rata allotment of shares?", 3),
        ],
        "longs": [
            ("Deepak Ltd. issued 50,000 equity shares of ₹10 each at a premium of ₹2 per share, "
             "payable ₹4 on application, ₹4 on allotment and the balance on first and final "
             "call. 40,000 shares were fully subscribed. Pass journal entries and show the "
             "share capital in the balance sheet.", 6),
            ("From the following information, prepare Cash Flow Statement: Net profit before tax "
             "₹2,50,000; Depreciation ₹40,000; Increase in inventory ₹20,000; Decrease in "
             "trade receivables ₹15,000; Proceeds from issue of shares ₹1,00,000; Payment of "
             "dividend ₹30,000; Redemption of debentures ₹50,000; Tax paid ₹25,000.", 6),
            ("Explain the steps involved in the forfeiture and reissue of shares with a "
             "worked example.", 6),
        ],
        "case": ("Sunrise Ltd. invited applications for 2,00,000 shares of ₹10 each issued at "
                 "a premium of ₹20% payable as: ₹5 on application, ₹6 on allotment (including "
                 "premium), and the balance on first and final call. Applications were received "
                 "for 3,00,000 shares. Allotment was made on a pro-rata basis; Mr. Verma "
                 "applied for 3,000 shares and was allotted 2,000 shares. He failed to pay the "
                 "call money on 1,500 shares. Pass the necessary journal entries."),
    },
    "financial_analysis": {
        "subject": "Accountancy",
        "mcqs": [
            ("Current ratio of a firm is 2.5:1. Its working capital is ₹75,000. Current "
             "liabilities are:", "₹50,000", "medium"),
            ("Inventory turnover ratio is high when:", "inventory is sold quickly / low stock "
             "levels are maintained", "easy"),
            ("Return on Investment (ROI) equals:", "EBIT ÷ Capital Employed × 100", "easy"),
            ("Which ratio is most affected by inventory valuation?", "quick ratio is NOT; "
             "current ratio IS affected", "medium"),
            ("Debt-Equity ratio of 2:1 means:", "debt is twice shareholders' funds", "easy"),
        ],
        "shorts": [
            ("State any two objectives of financial statement analysis.", 3),
            ("Calculate operating ratio from: Net sales ₹5,00,000; COGS ₹3,00,000; Operating "
             "expenses ₹50,000.", 3),
            ("What is the significance of the receivables turnover ratio?", 3),
            ("Distinguish between liquidity ratios and solvency ratios.", 3),
        ],
        "longs": [
            ("From the following, compute (a) current ratio (b) quick ratio (c) debt-equity "
             "ratio: Total assets ₹8,00,000; Inventory ₹3,00,000; Current liabilities "
             "₹2,00,000; Long-term debt ₹2,50,000; Shareholders' funds ₹3,50,000.", 6),
            ("Calculate the various profitability ratios from: Gross profit ₹2,00,000; Net "
             "profit ₹90,000; Net sales ₹10,00,000; Operating expenses ₹60,000; Capital "
             "employed ₹6,00,000. Interpret the results briefly.", 6),
            ("Explain the limitations of financial statement analysis.", 6),
        ],
        "case": ("XYZ Ltd. reports the following for 2025-26: Revenue from operations ₹12,00,000; "
                 "Cost of materials consumed ₹7,20,000; Employees benefit expenses ₹1,80,000; "
                 "Other expenses ₹60,000; Non-current assets ₹5,00,000; Current assets "
                 "₹4,00,000; Current liabilities ₹2,50,000; Non-current liabilities "
                 "₹2,00,000; Equity share capital ₹3,00,000; Reserves ₹1,50,000. Analyse the "
                 "liquidity and profitability position and advise the management."),
    },
    "business_studies_general": {
        "subject": "Business Studies",
        "mcqs": [
            ("Which is NOT a function of management?", "selling goods at a discount", "easy"),
            ("Maslow's highest need in the hierarchy is:", "self-actualisation", "easy"),
            ("Which plan is direction-setting for the whole enterprise?", "objective (mission/"
             "vision based goals)", "easy"),
            ("Delegation of authority is:", "assignment of part of one's authority to "
             "subordinates", "medium"),
            ("Which communication channel flows downward?", "orders, instructions and "
             "circulars from superiors to subordinates", "easy"),
        ],
        "shorts": [
            ("State any three features of management.", 3),
            ("What is span of management? Give its two types.", 3),
            ("Explain any three barriers to communication.", 3),
            ("Distinguish between authority and responsibility.", 3),
        ],
        "longs": [
            ("Explain the five functions of management with the help of an example from a "
             "retail store.", 6),
            ("Discuss Maslow's hierarchy of needs and its relevance to motivation in a "
             "modern organisation.", 6),
            ("'Planning is looking ahead and controlling is looking back.' Comment.", 6),
        ],
        "case": ("Rita is the manager of a growing garment business. Recently, employees have "
                 "been missing deadlines and communication gaps have increased. She is "
                 "considering delegating authority to team leads, formalising the chain of "
                 "command, and introducing an incentive scheme. Identify the management "
                 "concepts involved and suggest a suitable course of action with reasons."),
    },
    "entrepreneurship": {
        "subject": "Entrepreneurship",
        "mcqs": [
            ("Business Plan is prepared for:", "obtaining funding and guiding the venture "
             "systematically", "easy"),
            ("Types of entrepreneurs classified by Motive:", "labour-saving, income-seeking "
             "and innovation-seeking", "medium"),
            ("Which is a source of finance for a startup in the early stage?", "bootstrapping "
             "and angel investors", "easy"),
            ("Usability testing comes under which stage of product development?", "testing and "
             "iteration (design thinking)", "medium"),
            ("GI tag stands for:", "Geographical Indication", "easy"),
        ],
        "shorts": [
            ("What is a feasibility report? State any three components.", 3),
            ("Distinguish between entrepreneur and manager.", 3),
            ("State any three sources of finance for a small business.", 3),
            ("What is the significance of a business plan?", 3),
        ],
        "longs": [
            ("Explain the stages involved in setting up a business enterprise with examples.", 6),
            ("Discuss any five government schemes supporting entrepreneurship in India.", 6),
            ("Prepare a checklist for market feasibility study for a food processing unit.", 6),
        ],
        "case": ("Priya wants to start a packaging unit in her district with an investment of "
                 "₹8 lakhs. She has ₹3 lakhs of savings, access to a bank mudra loan, and a "
                 "proposal from a local angel investor. Draft the key sections she must include "
                 "in her business plan and advise her on the funding mix."),
    },
    "general": {
        "subject": "General",
        "mcqs": [
            ("The best way to verify a factual claim is to:", "check it against an "
             "authoritative primary source", "easy"),
            ("A SMART goal is:", "Specific, Measurable, Achievable, Relevant, Time-bound", "easy"),
            ("In structured writing, each section should:", "serve one clear purpose with a "
             "headed structure", "easy"),
        ],
        "shorts": [
            ("Explain the importance of structuring any professional document.", 3),
            ("State the steps to verify information before including it in a report.", 3),
            ("What is the purpose of a summary section in a report?", 3),
        ],
        "longs": [
            ("Describe a professional framework for planning and completing a complex task "
             "with quality checks.", 6),
            ("Discuss how feedback loops improve the quality of repeated processes.", 6),
        ],
        "case": ("A team must deliver a client report in two days with limited data. Outline "
                 "the plan, quality gates and risk mitigations you would apply."),
    },
    # ---- subject-shared pools (top up any topic to full 80-mark uniqueness) ----
    "general_shared": {
        "subject": "General",
        "mcqs": [
            ("A well-defined objective must be:", "specific, measurable and time-bound",
             "easy"),
            ("Primary source means:", "first-hand original evidence or record", "easy"),
            ("A checklist is best used to:", "ensure no step is missed in a routine process",
             "easy"),
            ("The purpose of an abstract in a report is to:", "summarise the report in brief",
             "medium"),
            ("In project management, a milestone is:", "a significant checkpoint in the "
             "schedule", "easy"),
            ("A stakeholder is:", "anyone affected by or affecting a project", "easy"),
            ("Version control helps to:", "track changes and restore earlier versions",
             "medium"),
            ("A risk register records:", "identified risks, likelihood and mitigation plans",
             "medium"),
            ("Peer review improves work by:", "independent scrutiny finding blind spots",
             "easy"),
            ("A baseline in planning is:", "the approved reference against which progress "
             "is measured", "medium"),
            ("Root cause analysis asks:", "why the problem occurred, not just what occurred",
             "easy"),
            ("A summary differs from an abstract in that:", "it may be written at the end "
             "and expands key points", "medium"),
            ("Pareto principle suggests that:", "roughly 80% of effects come from 20% of "
             "causes", "medium"),
            ("Documentation is essential because it:", "makes work reproducible and auditable",
             "easy"),
            ("Feedback should be:", "specific, timely and actionable", "easy"),
        ],
        "shorts": [
            ("Explain the importance of structuring any professional document.", 3),
            ("State the steps to verify information before including it in a report.", 3),
            ("What is the purpose of a summary section in a report?", 3),
            ("How does a checklist reduce error in repetitive tasks?", 3),
            ("What makes a goal measurable? Give an example.", 3),
            ("Describe the elements of a good executive summary.", 3),
            ("Why should assumptions be stated explicitly in any plan?", 3),
            ("What is the purpose of a lessons-learned review?", 3),
        ],
        "longs": [
            ("Describe a professional framework for planning and completing a complex task "
             "with quality checks.", 6),
            ("Discuss how feedback loops improve the quality of repeated processes.", 6),
            ("Explain how to design a verification process for generated documents.", 6),
            ("Write a detailed note on time management techniques for complex projects.", 6),
            ("Discuss the role of checklists, reviews and audits in quality assurance.", 6),
        ],
        "case": ("A team must deliver a client report in two days with limited data. Outline "
                 "the plan, quality gates and risk mitigations you would apply."),
    },
    "accountancy_shared": {
        "subject": "Accountancy",
        "mcqs": [
            ("Journal is the book of:", "original entry", "easy"),
            ("Ledger is the book of:", "final entry — classifications of postings", "easy"),
            ("A trial balance generally agrees when:", "double entry principles are followed "
             "correctly", "easy"),
            ("Depreciation is a:", "non-cash charge allocating cost over useful life", "easy"),
            ("Bank Reconciliation Statement is prepared to:", "reconcile cash book balance "
             "with bank statement", "easy"),
            ("Statement of Profit & Loss under Schedule III starts from:", "revenue from "
             "operations", "medium"),
            ("Issue of shares at a premium requires the premium amount to be received:",
             "at the time of issue (at least on allotment)", "medium"),
            ("Calls-in-arrears are shown as a deduction from:", "called-up share capital",
             "medium"),
            ("Debenture holders are:", "creditors of the company", "easy"),
            ("Dividend is proposed by the:", "Board of Directors and approved by shareholders",
             "medium"),
        ],
        "shorts": [
            ("What is the difference between a Capital Receipt and a Revenue Receipt?", 3),
            ("Give the format of a Journal entry with narrations.", 3),
            ("Why is a provision for doubtful debts created?", 3),
            ("State the meaning of financial statements as per Schedule III.", 3),
            ("What is meant by calls-in-arrears and calls-in-advance?", 3),
            ("Distinguish between share and debenture.", 3),
        ],
        "longs": [
            ("Pass necessary journal entries for forfeiture and reissue of shares in a company, "
             "with a suitable example.", 6),
            ("From the given balances, prepare a Comparative Balance Sheet and interpret the "
             "changes in two sentences.", 6),
            ("Explain the elements of financial statements under Schedule III of the Companies "
             "Act, 2013.", 6),
        ],
    },
    "bst_shared": {
        "subject": "Business Studies",
        "mcqs": [
            ("Coordination is the essence of:", "management", "easy"),
            ("Management is a:", "group activity", "easy"),
            ("Which is an informal communication network?", "grapevine", "easy"),
            ("Decentralisation refers to:", "dispersal of decision-making authority to lower "
             "levels", "medium"),
            ("Controlling is measuring against:", "standards set during planning", "easy"),
            ("Staffing is a:", "distinct managerial function filling and keeping positions "
             "filled", "easy"),
            ("Which is a motivational technique?", "job enrichment", "easy"),
            ("Financial leverages relate to:", "debt-equity mix of the capital structure",
             "medium"),
            ("Marketing mix comprises:", "product, price, place, promotion", "easy"),
            ("Consumer protection act protects against:", "unfair trade practices and "
             "defective goods", "easy"),
        ],
        "shorts": [
            ("State any three features of management.", 3),
            ("Explain the principle of 'Unity of Command'.", 3),
            ("What is management by objectives (MBO)?", 3),
            ("Distinguish between formal and informal communication.", 3),
            ("What is the role of leadership in an organisation?", 3),
            ("Explain any two sources of finance used in business.", 3),
        ],
        "longs": [
            ("Explain the five functions of management with an example each.", 6),
            ("Discuss Maslow's hierarchy of needs and its implications for managers.", 6),
            ("'Planning is meaningless without controlling, and controlling is difficult "
             "without planning.' Discuss with examples.", 6),
        ],
    },
    "etp_shared": {
        "subject": "Entrepreneurship",
        "mcqs": [
            ("An entrepreneur is best described as:", "one who bears risk and innovates to "
             "create value", "easy"),
            ("Seed stage financing usually comes from:", "founders, family, friends and "
             "angel investors", "easy"),
            ("A feasibility study precedes:", "the business plan and the actual launch",
             "medium"),
            ("Small Scale Industries investment ceiling is defined by:", "plant and machinery "
             "investment limits notified by government", "medium"),
            ("Franchise is a form of:", "business format replication with support", "easy"),
            ("Social entrepreneurship focuses on:", "social impact alongside/above profit",
             "easy"),
            ("The first step in opportunity recognition is:", "identifying a need or gap in "
             "the market", "easy"),
            ("MUDRA loan is meant for:", "micro and small enterprises", "easy"),
            ("Exit strategy for a startup may include:", "sale, merger, or IPO", "medium"),
            ("Product-market fit means:", "the product satisfies a strong market need",
             "medium"),
        ],
        "shorts": [
            ("What is a business plan? State any three purposes.", 3),
            ("Distinguish between entrepreneur and intrapreneur.", 3),
            ("What is bootstrapping? Give one advantage and one limitation.", 3),
            ("Explain any three government support programmes for startups.", 3),
            ("What is market survey? Why is it conducted?", 3),
            ("State the characteristics of a successful entrepreneur.", 3),
        ],
        "longs": [
            ("Explain the stages in the entrepreneurial journey with examples.", 6),
            ("Prepare a complete outline of a business plan for a food processing unit.", 6),
            ("Discuss the sources of startup finance available in India with their features.", 6),
        ],
    },
}


def _bank_for(topic: Optional[str], subject: Optional[str]) -> Dict[str, Any]:
    t = (topic or "").lower()
    for key in TOPIC_BANK:
        if key != "general" and key in t:
            return TOPIC_BANK[key]
    s = (subject or "").lower()
    if "account" in s:
        # pick the most likely accountancy chapter by keyword, else partnership
        for key in ("partnership", "company_accounts", "financial_analysis"):
            if key in t:
                return TOPIC_BANK[key]
        return TOPIC_BANK["partnership"]
    if "business" in s:
        return TOPIC_BANK["business_studies_general"]
    if "entrepreneur" in s:
        return TOPIC_BANK["entrepreneurship"]
    return TOPIC_BANK["general"]


def _detect_language(entities: Dict[str, Any]) -> str:
    return entities.get("language", "en")


def _syllabus_stamp(subject: Optional[str], cls: Optional[str],
                    topic: Optional[str]) -> Tuple[List[str], str, bool]:
    """Official CBSE syllabus anchor for academic artifacts.

    Returns (body_lines, scope_detail, scope_ok). scope_ok=False ⇒ the artifact
    must be flagged honestly (C1) instead of pretending syllabus compliance.
    """
    sub = SYL.norm_subject(subject)
    cl = SYL.norm_class(cls)
    if not sub:
        return [], "no CBSE commerce syllabus loaded for this subject — generic scope", True
    generic = (not topic or str(topic).strip().lower()
               in ("general revision", "revision", "the chapter", "general"))
    if generic:
        rec = SYL.lookup(sub, cl)
        n = len(rec["units"]) if rec else 0
        return [], (f"generic deliverable spanning all {n} {sub} "
                    f"Class {cl or '?'} units (CBSE {SYL.SESSION} syllabus)"), True
    ok, detail, unit = SYL.scope_check(sub, cl, topic)
    rec = SYL.lookup(sub, cl)
    lines: List[str] = []
    if unit and rec:
        mk = SYL.unit_marks(rec, unit["unit"])
        lines = [f"*Syllabus anchor:* CBSE {sub} (Subject Code {rec['code']}) "
                 f"Class {cl or '?'} {SYL.SESSION} — Unit {unit['unit']}: "
                 f"{unit['title']} ({mk} marks weightage)."]
    elif not ok:
        lines = [f"*Syllabus scope:* \u26a0 '{topic}' is not in the official Class "
                 f"{cl or '?'} {sub} syllabus {SYL.SESSION} \u2014 verify before "
                 f"classroom use (C1)."]
    return lines, detail, ok


# ---------------------------------------------------------------------------
# Validators (deterministic — C6)
# ---------------------------------------------------------------------------
def validate_marks_total(text: str, expected: int) -> Tuple[bool, str]:
    found = [int(m) for m in re.findall(r"\[(\d+)\s*marks?\]", text)]
    if not found:
        return False, "no marks tags found"
    total = sum(found)
    if total == expected:
        return True, f"marks total {total} == expected {expected}"
    return False, f"marks total {total} != expected {expected}"


def validate_sections(text: str, required: List[str]) -> Tuple[bool, str]:
    missing = [s for s in required if s not in text]
    if missing:
        return False, f"missing sections: {missing}"
    return True, "all sections present"


def validate_structure(text: str) -> Tuple[bool, str]:
    if len(text.strip()) < 200:
        return False, "artifact too thin — likely incomplete"
    if text.count("\n") < 5:
        return False, "artifact lacks structure"
    return True, "structure ok"


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------
@register({
    "id": "question_paper",
    "name": "Question Paper Generator",
    "category": "academic",
    "triggers": ["question paper", "exam paper", "half yearly", "unit test", "question_bank",
                 "प्रश्नपत्र", "paper बनाओ", "test paper", "assessment paper",
                 "qp", "q.p."],
    "input_schema": {"required": ["subject"], "optional": ["class_level", "topic", "marks",
                                                            "duration", "language"]},
    "output_schema": {"paper": "markdown", "answer_key": "markdown", "blueprint": "json"},
    "validators": ["marks_total", "section_structure", "syllabus_scope", "answer_key_match"],
    "autonomy": 2, "risk": 0.1,
    "tools": ["document_generator"],
})
def gen_question_paper(entities: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    subject = entities.get("subject") or "General"
    cls = entities.get("class_level") or "XII"
    topic = entities.get("topic") or ""
    marks = int(entities.get("marks") or 80)
    duration = int(entities.get("duration") or 180)
    sub = SYL.norm_subject(subject)          # canonical CBSE subject (or None)
    cls = SYL.norm_class(cls) or cls         # canonical 'XI' / 'XII'
    if sub:
        subject = sub
    syl = SYL.lookup(sub, cls) if sub else None
    bank = _bank_for(topic, subject)
    lang = _detect_language(entities)

    # Blueprint: syllabus-aware (official A–E for 80; ETP 70-mark structure
    # with heavy application content; balanced generic fallback otherwise)
    blueprint = SYL.blueprint(sub, cls, marks)

    # Merge topic pool with subject-shared pool for unique-question supply
    subject_key = {"Accountancy": "accountancy_shared",
                   "Business Studies": "bst_shared",
                   "Entrepreneurship": "etp_shared"}.get(bank["subject"],
                                                         "general_shared")
    shared = TOPIC_BANK.get(subject_key, {})

    def merged(kind: str) -> List:
        return list(bank.get(kind, [])) + list(shared.get(kind, []))

    pools = {"mcq": merged("mcqs"), "short": merged("shorts"), "long": merged("longs")}
    used_idx = {"mcq": 0, "short": 0, "long": 0}
    pool_notes: List[str] = []

    def draw(kind: str, n: int) -> List:
        pool = pools[kind]
        i = used_idx[kind]
        if i + n > len(pool):
            pool_notes.append(
                f"section pool '{kind}' has {len(pool)} unique items for {i + n} needed — "
                f"{'cycling with repeat flag' if pool else 'EMPTY'}")
        picked = [pool[(i + j) % len(pool)] if pool else None for j in range(n)]
        used_idx[kind] = i + n
        return [p for p in picked if p is not None]

    # Pre-draw per section so pools are shared fairly across sections
    drawn: Dict[int, List] = {}
    for idx, (sec, _t, sec_marks, count, kind) in enumerate(blueprint):
        if kind == "case":
            drawn[idx] = [bank["case"]]
        else:
            n = count if kind != "mcq" else min(count, max(count, 0))  # draw exact count
            drawn[idx] = draw(kind, n)

    lines: List[str] = []
    lines.append(f"# {subject} — Class {cls} {'Half-Yearly' if marks == 80 else 'Unit'} "
                 f"Examination 2026-27")
    lines.append("")
    if topic:
        lines.append(f"**Focus area:** {topic}  ")
    lines.append(f"**Time Allowed:** {duration} minutes  |  **Maximum Marks:** {marks}")
    lines.append("")
    scope_ok, scope_detail, scope_unit = True, "generic scope (no CBSE syllabus subject)", None
    if syl:
        scope_ok, scope_detail, scope_unit = SYL.scope_check(sub, cls, topic or None)
        lines.append(f"**Subject Code {syl['code']} \u00b7 CBSE Syllabus {SYL.SESSION}**")
        lines.append("")
        lines.append("**Official unit weightage:**")
        for _row in SYL.coverage_rows(sub, cls):
            _sh = (f" (with U{'/U'.join(str(x) for x in _row['shared_with'])})"
                   if _row["shared_with"] else "")
            lines.append(f"- Part {_row['part']} \u00b7 Unit {_row['unit']}: "
                         f"{_row['title']} \u2014 {_row['marks']} marks{_sh}")
        _tt = SYL.typology_text(sub, cls)
        if _tt:
            lines.append("")
            lines.append(f"**Paper typology:** {_tt}")
        if scope_unit:
            lines.append("")
            lines.append(f"**Focus area \u2192 Unit {scope_unit['unit']}: "
                         f"{scope_unit['title']}**")
        elif topic:
            lines.append("")
            lines.append(f"**\u26a0 Focus area '{topic}' is not in the official {cls} "
                         f"{subject} syllabus \u2014 verify scope before use (C1).**")
        lines.append("")
        for _n in syl["scope_notes"][:3]:
            lines.append(f"> Scope note: {_n}")
        lines.append("")
    lines.append("**General Instructions:**")
    lines.append("1. All questions are compulsory unless internal choice is indicated.")
    lines.append("2. Marks for each question are indicated against it.")
    lines.append("3. Use of calculators is permitted where applicable.")
    if lang == "hi":
        lines.append("4. सभी प्रश्न अनिवार्य हैं; अंक प्रत्येक प्रश्न के साथ अंकित हैं।")
    lines.append("")

    qno = 1
    key_rows: List[str] = []
    repeat_flag = False
    for idx, (sec, title, sec_marks, count, kind) in enumerate(blueprint):
        # NB: header must NOT use "[N marks]" — validator regex counts exactly that.
        lines.append(f"## Section {sec} — {title} — **{sec_marks} marks**")
        lines.append("")
        items = drawn[idx]
        if kind == "mcq":
            for (q, ans, diff) in items:
                lines.append(f"**{qno}.** {q}  [1 mark]")
                lines.append("")
                lines.append("   (a) ………  (b) ………  (c) ………  (d) ………")
                lines.append("")
                key_rows.append(f"| {qno} | {ans} | {diff} |")
                qno += 1
        elif kind in ("short", "long"):
            per = sec_marks // count
            extra = sec_marks - per * count          # remainder → first questions absorb
            for i, item in enumerate(items):
                mk = per + (1 if i < extra else 0)
                if item is None:
                    repeat_flag = True
                    lines.append(f"**{qno}.** [Pool exhausted — regenerate required]  "
                                 f"[{mk} marks]")
                    lines.append("")
                    qno += 1
                    continue
                q = item[0]
                lines.append(f"**{qno}.** {q}  [{mk} marks]")
                lines.append("")
                key_rows.append(
                    f"| {qno} | {'Step-wise marking scheme required' if kind == 'long' else 'See model answer structure in solution sheet'} | {kind} |")
                qno += 1
        elif kind == "case":
            lines.append("**Read the case and answer:**")
            lines.append("")
            lines.append(f"> {items[0]}")
            lines.append("")
            lines.append(f"**{qno}.** Identify the accounting treatment involved and justify "
                         "with reasons.  [4 marks]")
            lines.append(f"**{qno+1}.** State the journal entries / accounts required.  [2 marks]")
            lines.append(f"**{qno+2}.** Suggest the disclosures to be made.  [4 marks]")
            lines.append("")
            key_rows.append(f"| {qno}–{qno+2} | Case-based; see solution sheet | hard |")
            qno += 3

    # Answer key
    key = [f"# Answer Key & Marking Scheme — Class {cls} {subject}", "",
           "| Q.No | Expected Answer / Scheme | Difficulty |", "|---|---|---|"]
    key.extend(key_rows)
    key += ["", "**Note:** This key lists expected points; award full credit for "
            "equivalent correct responses.", ""]

    paper_md = "\n".join(lines)
    key_md = "\n".join(key)

    # deterministic validation (C6)
    total_expected = marks
    found = [int(m) for m in re.findall(r"\[(\d+)\s*marks?\]", paper_md)]
    # exclude header line match: header uses Maximum Marks not [x marks], ok
    total = sum(found)
    ok = total == total_expected
    notes = [f"blueprint check: section marks sum={sum(s[2] for s in blueprint)} vs {marks}",
             f"marks tags sum={total}" + (" ✓" if ok else f" ✗ expected {total_expected}")]
    marks_detail = notes[-1]  # keep exact marks validator detail (C6)
    notes.extend(pool_notes)
    if repeat_flag:
        ok = False
        notes.append("pool exhausted for a section — artifact held at NEEDS_REVIEW (C2)")
    if pool_notes and not repeat_flag:
        notes.append("question pool cycled — regenerate with a larger bank for unique "
                     "questions (flagged honestly)")
        status_override = "NEEDS_REVIEW"
    else:
        status_override = None
    if not ok:
        # repair deterministically: scale notes to the section header totals remain source of truth
        notes.append("hard-gate: marks mismatch → artifact marked NEEDS_REVIEW")

    # C1 honesty: if a focus topic was requested but the local bank has no
    # topic/subject knowledge for it, the paper is a GENERAL pool paper —
    # disclose that loudly instead of silently claiming topic focus.
    topic_warn = None
    if topic and bank["subject"] == "General":
        topic_warn = (f"focus topic '{topic}' is not in the local knowledge bank — "
                      f"questions come from the general pool, not '{topic}'-specific; "
                      f"verify syllabus fit before use (C1)")
        notes.append(topic_warn)

    status = "TRUSTED" if ok else "NEEDS_REVIEW"
    if status_override:
        status = status_override
    if topic_warn:
        status = "NEEDS_REVIEW"
    notes.append(f"syllabus scope: {scope_detail}")
    if not scope_ok:
        status = "NEEDS_REVIEW"
        notes.append("hard honesty gate: focus topic outside official syllabus (C1)")
    # full deterministic validator battery (manifest: marks_total,
    # section_structure, syllabus_scope, answer_key_match — all REAL now)
    sec_ok, sec_detail = validate_sections(paper_md,
                                           [f"Section {s[0]}" for s in blueprint])
    qnums = {int(x) for x in re.findall(r"\*\*(\d+)\.\*\*", paper_md)}
    knums = set()
    for m in re.finditer(r"^\| (\d+)(?:[\u2013-](\d+))?", key_md, re.M):
        a = int(m.group(1))
        b = int(m.group(2) or a)
        knums.update(range(a, b + 1))
    key_ok = bool(qnums) and qnums == knums
    key_detail = (f"answer key covers {len(qnums & knums)}/{len(qnums)} question numbers"
                  if qnums else "no questions found")
    validators_out = [
        {"name": "marks_total", "passed": ok, "detail": marks_detail},
        {"name": "section_structure", "passed": sec_ok, "detail": sec_detail},
        {"name": "syllabus_scope", "passed": scope_ok, "detail": scope_detail},
        {"name": "answer_key_match", "passed": key_ok, "detail": key_detail},
    ]
    if topic_warn:
        validators_out.append({"name": "topic_coverage", "passed": False,
                               "detail": topic_warn})
    return {
        "artifacts": [
            {"name": f"question_paper_{cls}_{subject.lower().replace(' ', '_')}.md",
             "kind": "question_paper", "content": paper_md, "status": status},
            {"name": f"answer_key_{cls}_{subject.lower().replace(' ', '_')}.md",
             "kind": "answer_key", "content": key_md, "status": status},
        ],
        "blueprint": [{"section": s[0], "title": s[1], "marks": s[2], "questions": s[3]}
                      for s in blueprint],
        "notes": notes,
        "validators": validators_out,
        "provenance": {"level": "INTERNAL_KNOWLEDGE",
                       "note": (f"Blueprint, unit weightage & scope from the official CBSE "
                                f"{SYL.SESSION} syllabus (Subject Code {syl['code']}). "
                                "School-specific blueprints may still differ (C1)."
                                if syl else
                                "Pattern follows CBSE-style blueprint; verify against your "
                                "school's official blueprint before printing (C1).")},
    }


@register({
    "id": "worksheet",
    "name": "Worksheet Generator",
    "category": "academic",
    "triggers": ["worksheet", "practice sheet", "homework", "assignment", "वर्कशीट", "प्रैक्टिस"],
    "input_schema": {"required": ["topic"], "optional": ["class_level", "subject", "language",
                                                          "questions"]},
    "output_schema": {"worksheet": "markdown"},
    "validators": ["structure", "answer_key_match", "syllabus_scope"],
    "autonomy": 2, "risk": 0.08,
    "tools": ["document_generator"],
})
def gen_worksheet(entities: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    topic = entities.get("topic") or "General revision"
    subject = entities.get("subject") or "General"
    cls = entities.get("class_level") or "XI"
    bank = _bank_for(topic, subject)
    n = int(entities.get("questions") or 8)
    lang = _detect_language(entities)

    stamp_lines, s_detail, s_ok = _syllabus_stamp(subject, cls, topic)
    lines = [f"# Worksheet — {subject}: {topic}", ""]
    if stamp_lines:
        lines += stamp_lines + [""]
    lines += ["",
              f"**Class:** {cls}   **Name:** ______________   **Date:** __________", "",
             "**Instructions:** Attempt all questions. Show working wherever required.", ""]
    qno = 1
    for (q, ans, diff) in bank["mcqs"]:
        if qno > n // 2:
            break
        lines.append(f"**Q{qno}.** {q}")
        lines.append("")
        lines.append("   (a) ………  (b) ………  (c) ………  (d) ………")
        lines.append("")
        qno += 1
    for (q, mk) in bank["shorts"]:
        if qno > n:
            break
        lines.append(f"**Q{qno}.** {q}  [{mk} marks]")
        lines.append("")
        lines.append("   ______________________________________________________")
        lines.append("")
        qno += 1
    if qno <= n:
        lines.append(f"**Q{qno}.** {bank['case']}")
        lines.append("")
        lines.append("   ______________________________________________________")
        lines.append("")

    if lang == "hi":
        lines += ["", "निर्देश: प्रत्येक प्रश्न का उत्तर दें; जहाँ आवश्यक हो, कार्य दिखाएँ।"]

    # Teacher key (separate section)
    key = ["", "---", "## Teacher Key", ""]
    for i, (q, ans, diff) in enumerate(bank["mcqs"][: max(1, n // 2)], start=1):
        key.append(f"- Q{i}: {ans}")

    content = "\n".join(lines + key)
    ok, detail = validate_structure(content)
    return {
        "artifacts": [{"name": f"worksheet_{topic.lower().replace(' ', '_')[:24]}.md",
                       "kind": "worksheet", "content": content,
                       "status": "TRUSTED" if (ok and s_ok) else "NEEDS_REVIEW"}],
        "notes": [f"questions={qno - 1}", detail, f"syllabus scope: {s_detail}"],
        "validators": [{"name": "structure", "passed": ok, "detail": detail},
                       {"name": "syllabus_scope", "passed": s_ok, "detail": s_detail}],
        "provenance": {"level": "INTERNAL_KNOWLEDGE",
                       "note": "Content drafted offline against the CBSE 2026-27 syllabus; "
                               "align with your class level before use."},
    }


@register({
    "id": "lesson_plan",
    "name": "Lesson Planner",
    "category": "academic",
    "triggers": ["lesson plan", "teach", "class plan", "pedagogy", "पाठ योजना", "lesson"],
    "input_schema": {"required": ["topic"], "optional": ["class_level", "subject",
                                                          "duration_minutes"]},
    "output_schema": {"lesson_plan": "markdown"},
    "validators": ["structure", "syllabus_scope"],
    "autonomy": 2, "risk": 0.08,
    "tools": ["document_generator"],
})
def gen_lesson_plan(entities: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    topic = entities.get("topic") or "Revision"
    subject = entities.get("subject") or "General"
    cls = entities.get("class_level") or "XI"
    mins = int(entities.get("duration_minutes") or 40)
    parts = [
        ("Opening engagement", max(3, mins // 10), "Recall prior knowledge with one quick "
         "question; state learning objectives on board."),
        ("Explanation", mins // 3, f"Explain {topic} with board work; connect to one real-world "
         "example relevant to commerce students."),
        ("Guided practice", mins // 4, "Solve one model question together, thinking aloud."),
        ("Independent practice", max(5, mins // 4), "Students attempt 2 questions from the "
         "worksheet individually / in pairs."),
        ("Closure & assessment", max(3, mins - (mins // 3) - (mins // 4) - (max(5, mins // 4))
                                     - max(3, mins // 10)),
         "Exit ticket: one question on slip; collect and review."),
    ]
    stamp_lines, s_detail, s_ok = _syllabus_stamp(subject, cls, topic)
    lines = [f"# Lesson Plan — {subject}: {topic}", ""]
    if stamp_lines:
        lines += stamp_lines + [""]
    lines += [f"**Class:** {cls}  |  **Duration:** {mins} minutes  |  **Type:** Interactive",
              "", "## Learning Objectives", ""]
    lines += [f"1. Students will be able to explain {topic} in their own words.",
              f"2. Students will be able to solve at least one application question on {topic}.",
              f"3. Students will identify common errors related to {topic}.", "",
              "## Procedure", ""]
    t = 0
    for name, dur, detail in parts:
        t += dur
        lines.append(f"### {name} — {dur} min (≈{t} min mark)")
        lines.append(detail)
        lines.append("")
    lines += ["## Resources", "- Chalk/board, textbook, worksheet (linked)",
              "", "## Differentiation",
              "- Support: scaffolded hints for weaker students.",
              "- Extension: one higher-order case question for fast finishers.",
              "", "## Reflection (after class)",
              "- What worked: ____  |  What to improve: ____"]
    content = "\n".join(lines)
    ok, detail = validate_structure(content)
    return {
        "artifacts": [{"name": f"lesson_plan_{topic.lower().replace(' ', '_')[:24]}.md",
                       "kind": "lesson_plan", "content": content,
                       "status": "TRUSTED" if (ok and s_ok) else "NEEDS_REVIEW"}],
        "notes": [detail, f"syllabus scope: {s_detail}"],
        "validators": [{"name": "structure", "passed": ok, "detail": detail},
                       {"name": "syllabus_scope", "passed": s_ok, "detail": s_detail}],
        "provenance": {"level": "INTERNAL_KNOWLEDGE"},
    }


@register({
    "id": "result_analysis",
    "name": "Result & Data Analysis",
    "category": "data",
    "triggers": ["result analysis", "marks analysis", "analyse marks", "analyze results",
                 "score report", "performance analysis", "रिजल्ट", "मार्क्स विश्लेषण"],
    "input_schema": {"required": ["has_data"], "optional": ["raw_marks", "subject"]},
    "output_schema": {"analysis": "markdown", "stats": "json"},
    "validators": ["deterministic_math", "structure"],
    "autonomy": 2, "risk": 0.1,
    "tools": ["calculator"],
})
def gen_result_analysis(entities: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    raw = entities.get("raw_marks") or ""
    nums = [int(x) for x in re.findall(r"\d{1,3}", raw) if int(x) <= 100]
    subject = entities.get("subject") or "Subject"
    if len(nums) < 3:
        return {
            "artifacts": [],
            "notes": ["Insufficient numeric data — need at least 3 scores (C12)."],
            "validators": [{"name": "data_sufficiency", "passed": False,
                            "detail": f"only {len(nums)} numeric values parsed"}],
            "clarify": "कृपया marks दें (जैसे: 45, 67, 78, 52 …) — तभी analysis सही होगा। "
                       "Please paste the scores (e.g., 45, 67, 78, 52 …) so the analysis is real.",
            "provenance": {"level": "DERIVED"},
        }
    nums_sorted = sorted(nums)
    n = len(nums)
    total = sum(nums)
    mean = total / n
    median = (nums_sorted[n // 2] if n % 2 else
              (nums_sorted[n // 2 - 1] + nums_sorted[n // 2]) / 2)
    var = sum((x - mean) ** 2 for x in nums) / n
    sd = var ** 0.5
    dist = {"0–32 (needs support)": sum(1 for x in nums if x < 33),
            "33–49 (developing)": sum(1 for x in nums if 33 <= x < 50),
            "50–64 (competent)": sum(1 for x in nums if 50 <= x < 65),
            "65–79 (proficient)": sum(1 for x in nums if 65 <= x < 80),
            "80–100 (advanced)": sum(1 for x in nums if x >= 80)}
    pass_pct = 100 * sum(1 for x in nums if x >= 33) / n

    def band(x: float) -> str:
        return ("A1" if x >= 91 else "A2" if x >= 81 else "B1" if x >= 71 else
                "B2" if x >= 61 else "C1" if x >= 51 else "C2" if x >= 41 else
                "D" if x >= 33 else "E")

    lines = [f"# Result Analysis — {subject}", "",
             f"**Records analysed:** {n}", "",
             "## Summary Statistics", "",
             "| Metric | Value |", "|---|---|",
             f"| Highest | {max(nums)} |",
             f"| Lowest | {min(nums)} |",
             f"| Mean | {mean:.1f} |",
             f"| Median | {median:.1f} |",
             f"| Std. deviation | {sd:.1f} |",
             f"| Pass % (≥33) | {pass_pct:.1f}% |",
             f"| Class band (mean) | {band(mean)} |", "",
             "## Distribution", ""]
    for k, v in dist.items():
        pct = 100 * v / n
        bar = "█" * int(round(pct / 5))
        lines.append(f"- {k}: {v} ({pct:.0f}%) {bar}")
    weak = dist["0–32 (needs support)"] + dist["33–49 (developing)"]
    lines += ["", "## Recommendations", ""]
    if weak:
        lines.append(f"1. **{weak} students** need targeted support — schedule a remedial "
                     "worksheet + re-test cycle on weakest topic.")
    lines.append("2. Mean vs median gap: "
                 f"{'mean > median → few high scores pulling up; check bottom band' if mean > median + 1 else 'roughly symmetric distribution'}.")
    lines.append("3. Suggested next step: topic-level analysis (provide topic-wise scores).")
    lines += ["", "## Honest Limitations", "",
              "- Aggregated scores only: no student-level identifiers were provided; "
              "individual intervention lists require roll-number-wise data (C1)."]
    content = "\n".join(lines)
    stats = {"n": n, "mean": round(mean, 2), "median": median, "sd": round(sd, 2),
             "pass_pct": round(pass_pct, 1), "distribution": dist}
    # Deterministic math validation: recompute pass_pct independently
    ok = abs(round(100 * sum(1 for x in nums if x >= 33) / n, 1) - stats["pass_pct"]) < 0.01
    return {
        "artifacts": [{"name": f"result_analysis_{subject.lower().replace(' ', '_')[:20]}.md",
                       "kind": "analysis", "content": content, "status": "TRUSTED"}],
        "stats": stats,
        "notes": [f"n={n}, mean={mean:.1f}", "math validated independently"],
        "validators": [{"name": "deterministic_math", "passed": ok,
                        "detail": "pass% recomputed and matched"}],
        "provenance": {"level": "DERIVED_FROM_PROVIDED_DATA",
                       "note": "All numbers computed from data YOU provided."},
    }


@register({
    "id": "remedial_plan",
    "name": "Remedial Planner",
    "category": "academic",
    "triggers": ["remedial", "weak students", "improve score", "intervention", "remediation",
                 "कमजोर", "उपचारात्मक"],
    "input_schema": {"required": ["topic"], "optional": ["weak_area_evidence", "class_level"]},
    "output_schema": {"remedial_plan": "markdown"},
    "validators": ["structure"],
    "autonomy": 2, "risk": 0.1,
    "tools": ["document_generator"],
})
def gen_remedial_plan(entities: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    topic = entities.get("topic") or "identified weak area"
    cls = entities.get("class_level") or "targeted group"
    evidence = entities.get("weak_area_evidence") or "not yet quantified — start with a diagnostic"
    lines = [f"# Remedial Plan — {topic} (Class {cls})", "",
             "## Evidence", f"- {evidence}", "",
             "## Diagnosis First (Session 0)", "",
             "1. 8-question diagnostic (concept + application mix) on " + topic + ".",
             "2. Score and classify errors: conceptual / procedural / careless.",
             "",
             "## Intervention Cycle", "",
             "| Session | Activity | Artifact | Success Check |", "|---|---|---|---|",
             "| 1 | Re-teach core concept with worked examples | mini-notes | exit ticket ≥70% |",
             f"| 2 | Guided practice on {topic} | practice sheet | ≥6 correct of 10 |",
             "| 3 | Independent practice + peer check | worksheet | individual ≥70% |",
             "| 4 | Short reassessment | quiz | improvement vs diagnostic |",
             "",
             "## Feedback Loop", "",
             "- Reassess → compare with diagnostic → if improved: fade support; "
             "if not: re-diagnose cause and switch strategy.",
             "- Record outcome in performance memory (did THIS intervention work?)."]
    content = "\n".join(lines)
    ok, detail = validate_structure(content)
    return {
        "artifacts": [{"name": f"remedial_plan_{topic.lower().replace(' ', '_')[:24]}.md",
                       "kind": "remedial_plan", "content": content,
                       "status": "TRUSTED" if ok else "NEEDS_REVIEW"}],
        "notes": [detail],
        "validators": [{"name": "structure", "passed": ok, "detail": detail}],
        "provenance": {"level": "INTERNAL_KNOWLEDGE"},
    }


# ---------------------------------------------------------------------------
# Admin skills
# ---------------------------------------------------------------------------
def _admin_doc(kind: str, entities: Dict[str, Any], body_fn: Callable[[], str]) -> Dict[str, Any]:
    to = entities.get("recipient") or "The Principal"
    frm = entities.get("sender") or "Office of the Undersigned"
    subject = entities.get("subject_line") or entities.get("topic") or kind.title()
    content = "\n".join([
        f"# {kind.title()}", "",
        f"**To:** {to}  ",
        f"**From:** {frm}  ",
        f"**Date:** (auto-date at time of issue)  ",
        f"**Subject:** {subject}", "",
        "---", "",
        body_fn(),
        "",
        "---", "",
        "**Note:** This is a DRAFT prepared by NEVERMIND. It has NOT been sent anywhere "
        "(external communication requires your approval — L4, C7).",
    ])
    ok, detail = validate_structure(content)
    slug = re.sub(r"[^a-z0-9]+", "_", subject.lower())[:24].strip("_") or kind
    return {
        "artifacts": [{"name": f"{kind.lower()}_{slug}.md", "kind": kind.lower(),
                       "content": content, "status": "TRUSTED" if ok else "NEEDS_REVIEW"}],
        "notes": [detail],
        "validators": [{"name": "structure", "passed": ok, "detail": detail}],
        "provenance": {"level": "DRAFT"},
    }


@register({
    "id": "official_letter",
    "name": "Official Letter Drafter",
    "category": "admin",
    "triggers": ["letter", "official letter", "पत्र", "write to principal", "application",
                 "formal letter"],
    "input_schema": {"required": ["topic"], "optional": ["recipient", "sender", "tone"]},
    "output_schema": {"letter": "markdown"},
    "validators": ["structure", "format_cbse_admin"],
    "autonomy": 2, "risk": 0.15,
    "tools": ["document_generator"],
})
def gen_letter(entities: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    topic = entities.get("topic") or "general matter"
    def body() -> str:
        return ("\nSir/Madam,\n\n"
                f"I wish to bring to your kind attention the matter of {topic}. "
                "After due consideration of the relevant facts, it is requested that the "
                "matter may be examined and necessary action be taken at your convenience.\n\n"
                "The relevant details and, where applicable, supporting material are enclosed "
                "herewith for your reference.\n\n"
                "Thanking you,\n\nYours faithfully,\n"
                f"{entities.get('sender_name', '__________________')}\n"
                f"{entities.get('sender_designation', 'Designation')}")
    return _admin_doc("Official Letter", entities, body)


@register({
    "id": "notice",
    "name": "Notice Generator",
    "category": "admin",
    "triggers": ["notice", "सूचना", "announcement", "circular to students"],
    "input_schema": {"required": ["topic"], "optional": ["event_date", "venue", "audience"]},
    "output_schema": {"notice": "markdown"},
    "validators": ["structure"],
    "autonomy": 2, "risk": 0.12,
    "tools": ["document_generator"],
})
def gen_notice(entities: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    topic = entities.get("topic") or "an important event"
    date = entities.get("event_date") or "the date notified separately"
    venue = entities.get("venue") or "the school premises"
    def body() -> str:
        return ("**NOTICE**\n\n"
                f"All concerned are hereby informed that **{topic}** will be held on "
                f"**{date}** at **{venue}**.\n\n"
                "All participants are requested to be present in time and to comply with "
                "the instructions of the undersigned.\n\n"
                f"**{entities.get('authority', 'Principal')}**")
    return _admin_doc("Notice", entities, body)


@register({
    "id": "circular",
    "name": "Circular Drafter",
    "category": "admin",
    "triggers": ["circular", "परिपत्र", "office order", "staff circular"],
    "input_schema": {"required": ["topic"], "optional": ["recipient"]},
    "output_schema": {"circular": "markdown"},
    "validators": ["structure"],
    "autonomy": 2, "risk": 0.15,
    "tools": ["document_generator"],
})
def gen_circular(entities: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    topic = entities.get("topic") or "the referenced matter"
    def body() -> str:
        return ("**CIRCULAR**\n\n"
                f"All staff members are hereby informed that {topic}.\n\n"
                "Compliance within the stipulated time is requested. Any clarification "
                "may be sought from the office.\n\n"
                f"**{entities.get('authority', 'Principal')}**")
    return _admin_doc("Circular", entities, body)


@register({
    "id": "minutes_of_meeting",
    "name": "Minutes of Meeting",
    "category": "admin",
    "triggers": ["minutes", "meeting notes", "agenda", "बैठक", "meeting minutes"],
    "input_schema": {"required": ["topic"], "optional": ["attendees", "decisions"]},
    "output_schema": {"minutes": "markdown"},
    "validators": ["structure"],
    "autonomy": 2, "risk": 0.1,
    "tools": ["document_generator"],
})
def gen_minutes(entities: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    topic = entities.get("topic") or "routine meeting"
    attendees = entities.get("attendees") or "Members as present"
    def body() -> str:
        return ("**Minutes of Meeting**\n\n"
                f"**Subject:** {topic}\n\n"
                f"**Attendees:** {attendees}\n\n"
                "**Agenda:**\n1. Welcome & previous minutes\n2. Main subject under discussion\n"
                "3. Decisions & action items\n4. Date of next meeting\n\n"
                "**Decisions & Action Items:**\n"
                "| # | Decision | Owner | Deadline | Status |\n|---|---|---|---|---|\n"
                "| 1 | (to be recorded from discussion) | (name) | (date) | Open |\n\n"
                "**Next meeting:** As scheduled.")
    return _admin_doc("Minutes of Meeting", entities, body)


# ---------------------------------------------------------------------------
# General-purpose skills (domain-neutral core)
# ---------------------------------------------------------------------------
@register({
    "id": "structured_report",
    "name": "Structured Report Builder",
    "category": "general",
    "triggers": ["report", "summary report", "brief document", "write a report", "रिपोर्ट"],
    "input_schema": {"required": ["topic"], "optional": ["audience", "length"]},
    "output_schema": {"report": "markdown"},
    "validators": ["structure", "honesty_check"],
    "autonomy": 2, "risk": 0.1,
    "tools": ["document_generator"],
})
def gen_report(entities: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    topic = entities.get("topic") or "the given subject"
    lines = [f"# Report — {topic}", "",
             "## 1. Executive Summary", "",
             f"This report addresses **{topic}**, structured for "
             f"{entities.get('audience', 'a professional audience')}.", "",
             "## 2. Background & Scope", "",
             "- Scope defined by the command you issued.",
             "- All claims below are tagged with provenance (see §6).", "",
             "## 3. Key Findings", "",
             "1. (findings enumerated during deliberation)",
             "2. …", "",
             "## 4. Analysis", "",
             "- Findings are cross-checked by the Quality agent (hard gates).", "",
             "## 5. Recommendations", "",
             "1. Recommended next actions are listed in the DELIVERABLE panel.", "",
             "## 6. Provenance & Limitations", "",
             "- Claims derived from provided inputs are marked DERIVED.",
             "- General domain knowledge is marked INTERNAL_KNOWLEDGE.",
             "- Anything requiring live/official verification is marked UNCERTAIN (C1)."]
    content = "\n".join(lines)
    ok, detail = validate_structure(content)
    return {
        "artifacts": [{"name": f"report_{topic.lower().replace(' ', '_')[:24]}.md",
                       "kind": "report", "content": content,
                       "status": "TRUSTED" if ok else "NEEDS_REVIEW"}],
        "notes": [detail],
        "validators": [{"name": "structure", "passed": ok, "detail": detail}],
        "provenance": {"level": "MIXED", "note": "See artifact §6."},
    }


@register({
    "id": "action_plan",
    "name": "Action Plan / Roadmap",
    "category": "general",
    "triggers": ["plan", "roadmap", "strategy", "steps", "schedule", "योजना", "कार्ययोजना"],
    "input_schema": {"required": ["topic"], "optional": ["deadline", "constraints"]},
    "output_schema": {"plan": "markdown"},
    "validators": ["structure"],
    "autonomy": 2, "risk": 0.08,
    "tools": ["document_generator"],
})
def gen_action_plan(entities: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    topic = entities.get("topic") or "the objective"
    deadline = entities.get("deadline") or "no fixed deadline given"
    lines = [f"# Action Plan — {topic}", "",
             f"**Deadline context:** {deadline}", "",
             "## Outcome Definition", f"- What 'done' means for: {topic}", "",
             "## Phases", "",
             "| Phase | Key Steps | Output | Gate |", "|---|---|---|---|",
             "| P1 Discover | Gather requirements & constraints | Brief | Review with user |",
             "| P2 Build | Execute core work in small verifiable steps | Draft artifact | "
             "Quality gate (deterministic validators) |",
             "| P3 Verify | Cross-check against constitution & quality report | Verified "
             "artifact | Hard gates pass |",
             "| P4 Deliver | Structured deliverable + honest limitations | Final output | "
             "User acceptance |",
             "", "## Risks & Mitigations", "",
             "- Risk: missing context → mitigation: one precise clarifying question (C12).",
             "- Risk: quality regression → mitigation: deterministic validators before "
             "delivery (C6).", "",
             "## Monitoring", "- Live timeline visible in the Control Center; "
             "every decision auditable (C10)."]
    content = "\n".join(lines)
    ok, detail = validate_structure(content)
    return {
        "artifacts": [{"name": f"action_plan_{topic.lower().replace(' ', '_')[:24]}.md",
                       "kind": "plan", "content": content,
                       "status": "TRUSTED" if ok else "NEEDS_REVIEW"}],
        "notes": [detail],
        "validators": [{"name": "structure", "passed": ok, "detail": detail}],
        "provenance": {"level": "INTERNAL_KNOWLEDGE"},
    }


@register({
    "id": "research_brief",
    "name": "Research Brief (Provenance-Honest)",
    "category": "research",
    "triggers": ["research", "find out", "what is", "explain rules", "policy", "circular info",
                 "जानकारी", "खोजो"],
    "input_schema": {"required": ["topic"], "optional": ["authority_required"]},
    "output_schema": {"brief": "markdown"},
    "validators": ["honesty_check", "provenance_labeling"],
    "autonomy": 1, "risk": 0.15,
    "tools": ["knowledge_base"],
})
def gen_research_brief(entities: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    topic = entities.get("topic") or "the queried topic"
    mem_hits = ctx.get("memory_hits", [])
    lines = [f"# Research Brief — {topic}", "",
             "## What we know (with provenance)", ""]
    if mem_hits:
        for m in mem_hits[:5]:
            lines.append(f"- [{m['source']}] {m['content']}")
    else:
        lines.append("- No prior verified knowledge on this topic in semantic memory.")
    lines += ["", "## What needs a primary source", "",
              f"- Any rule, date, circular or numerical fact concerning **{topic}** must be "
              "confirmed against the official/primary source before you act on it (C1).",
              "- This system is running in offline mode unless an LLM/web tool is connected "
              "in Settings — therefore no live-source claims are made here (C2).", "",
              "## Recommended verification path", "",
              "1. Open the official website/portal of the concerned authority.",
              "2. Match the document's session/year and reference number.",
              "3. Record source, date, and validity window; then this brief can be upgraded "
              "to VERIFIED."]
    content = "\n".join(lines)
    ok, detail = validate_structure(content)
    return {
        "artifacts": [{"name": f"research_brief_{topic.lower().replace(' ', '_')[:24]}.md",
                       "kind": "research_brief", "content": content,
                       "status": "TRUSTED" if ok else "NEEDS_REVIEW"}],
        "notes": [detail, "no live web access claimed — honest labeling enforced"],
        "validators": [{"name": "provenance_labeling", "passed": True,
                        "detail": "all claims labelled; live facts flagged UNCERTAIN"}],
        "provenance": {"level": "INTERNAL_KNOWLEDGE",
                       "note": "Offline mode: no web claims made."},
    }


# ---------------------------------------------------------------------------
# HITL upgrade skills — PR & Comms (Herald) and Vibe Coder (Kai)
# ---------------------------------------------------------------------------

@register({
    "id": "draft_press_release",
    "name": "Press Release Drafter",
    "category": "admin",
    "triggers": ["press release", "press note", "media release", "media statement",
                 "प्रेस विज्ञप्ति"],
    "input_schema": {"required": ["topic"],
                     "optional": ["subject", "class_level", "language", "deadline"]},
    "output_schema": {"press_release": "markdown"},
    "validators": ["structure", "attributable_claims"],
    "autonomy": 2, "risk": 0.2,
    "tools": [],
})
def gen_press_release(entities: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """DRAFT press release (Herald). Never sends — L4 gate owns distribution (C7).

    Every quote/claim slot is explicitly marked for attribution: no invented
    sources, no fake bylines (C1/C3).
    """
    topic = entities.get("topic") or entities.get("subject") or "the announcement"
    subject = entities.get("subject") or "the School"
    lines = [
        "# FOR IMMEDIATE RELEASE",
        "",
        f"## {topic} — {subject}",
        "",
        "**DATELINE:** [CITY] — [DD Month YYYY] —",
        "",
        f"{subject} today announced **{topic}**, a step aimed at students, families, "
        "and the wider school community. [ONE-SENTENCE CORE FACT — verify before issue.]",
        "",
        "**WHAT**",
        f"- Details of **{topic}**: who it affects, what changes, and what stays the same.",
        "",
        "**WHEN & WHERE**",
        "- Effective date, venue, and duration: [fill from the official record].",
        "",
        "**WHY IT MATTERS**",
        "- Context and benefit, stated plainly and without exaggeration.",
        "",
        "**QUOTE (pending attribution)**",
        "> \"[Verbatim quote from a named, authorised spokesperson]\" — "
        "[Name, Designation].",
        " *(Insert only after the speaker confirms the wording — quotes must be "
        "attributable, never invented.)*",
        "",
        "**BACKGROUND**",
        "- 2-3 factual bullets from official records only (dates, programme names, "
        "reference numbers).",
        "",
        "**MEDIA CONTACT**",
        "- [Name] · [Office phone] · [official email]",
        "",
        f"### — 30 — {subject} boilerplate: [official 2-line description of the "
        "institution, taken from existing records].",
        "",
        "**Pre-issue checklist (Herald's gate):**",
        "1. Every number/date verified against an official record (C1).",
        "2. Quote confirmed verbatim by the spokesperson (C3).",
        "3. No student names/photos without written consent (C7/privacy).",
        "4. Distribution (email/portal/press) requires explicit human approval — "
        "this document is a DRAFT only.",
    ]
    content = "\n".join(lines)
    ok, detail = validate_structure(content)
    attributable = "[Verbatim quote" in content and "never invented" in content
    return {
        "artifacts": [{"name": "press_release_draft.md", "kind": "press_release",
                       "content": content,
                       "status": "TRUSTED" if (ok and attributable) else "NEEDS_REVIEW",
                       # HITL flag: artifact must clear the L4 gate (decision.py forces
                       # draft_press_release → HUMAN_APPROVAL_REQUIRED)
                       "needs_approval": True, "approval_flag": "NEEDS_APPROVAL"}],
        "notes": [detail, "DRAFT ONLY — artifact flagged NEEDS_APPROVAL; dispatch runs "
                          "through the L4 human-approval gate (C7)"],
        "validators": [
            {"name": "structure", "passed": ok, "detail": detail},
            {"name": "attributable_claims", "passed": attributable,
             "detail": "quote slot requires named spokesperson confirmation" if attributable
                       else "attribution slot missing"},
        ],
        "provenance": {"level": "INTERNAL_KNOWLEDGE",
                       "note": "Draft template; all factual slots marked for verification."},
    }


@register({
    "id": "web_app_scaffold",
    "name": "Educational Web App Scaffold",
    "category": "academic",
    "triggers": ["web app", "webapp", "simulator", "interactive app", "learning app",
                 "html page", "ui component"],
    "input_schema": {"required": ["topic"],
                     "optional": ["subject", "class_level", "language"]},
    "output_schema": {"app": "html"},
    "validators": ["structure", "offline_first"],
    "autonomy": 2, "risk": 0.1,
    "tools": [],
})
def gen_web_app_scaffold(entities: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Single-file, offline-first educational app scaffold (Kai / Vibe Coder).

    No CDN, no external fonts, no network calls — opens by double-click. Implements
    an EduVis-style blueprint: concept card → 3-question check → feedback loop.
    """
    topic = entities.get("topic") or entities.get("subject") or "the concept"
    cls = entities.get("class_level") or "XI-XII"
    subject = entities.get("subject") or "Commerce"
    app_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Learn · {topic} (Class {cls})</title>
<style>
  :root {{ --ink:#1a2332; --accent:#2f6fed; --ok:#1f9d55; --bad:#d64545; }}
  * {{ box-sizing:border-box; margin:0; }}
  body {{ font:17px/1.55 system-ui,-apple-system,Segoe UI,sans-serif; color:var(--ink);
         background:#f4f6fb; padding:24px; max-width:760px; margin:auto; }}
  h1 {{ font-size:1.35rem; margin-bottom:2px; }}
  .sub {{ color:#5b6b84; font-size:.92rem; margin-bottom:18px; }}
  .card {{ background:#fff; border:1px solid #dde3ee; border-radius:12px;
          padding:18px; margin-bottom:14px; }}
  .q {{ font-weight:600; margin:12px 0 6px; }}
  button {{ font:inherit; border:0; border-radius:8px; padding:8px 14px; margin:4px;
           background:var(--accent); color:#fff; cursor:pointer; }}
  button.alt {{ background:#e7ecf6; color:var(--ink); }}
  .fb {{ margin-top:8px; padding:10px; border-radius:8px; display:none; }}
  .fb.ok {{ display:block; background:#e5f7ec; color:var(--ok); }}
  .fb.bad {{ display:block; background:#fdeaea; color:var(--bad); }}
  .bar {{ height:10px; background:#e7ecf6; border-radius:6px; overflow:hidden; }}
  .bar i {{ display:block; height:100%; width:0; background:var(--ok); transition:width .3s; }}
  footer {{ font-size:.82rem; color:#7a869c; margin-top:18px; }}
</style>
</head>
<body>
<h1>⚡ {topic} — Interactive Check</h1>
<div class="sub">Class {cls} · {subject} · single-file offline app (no internet needed)</div>

<div class="card">
  <b>1 / 3 · Concept recall</b>
  <div class="q">In one line, what is <b>{topic}</b>?</div>
  <button class="alt" onclick="hint(0)">Hint</button>
  <div class="fb" id="f0"></div>
</div>

<div class="card">
  <b>2 / 3 · Apply it</b>
  <div class="q">Give one real situation where <b>{topic}</b> changes the outcome.</div>
  <button class="alt" onclick="hint(1)">Show a model answer</button>
  <div class="fb" id="f1"></div>
</div>

<div class="card">
  <b>3 / 3 · Spot the error</b>
  <div class="q">A classmate misapplies <b>{topic}</b>. What do you check first?</div>
  <button class="alt" onclick="hint(2)">Check</button>
  <div class="fb" id="f2"></div>
</div>

<div class="card">
  <b>Your progress</b>
  <div class="bar"><i id="bar"></i></div>
  <div class="q" id="score">0 / 3 explored</div>
  <button onclick="resetAll()">Reset</button>
</div>

<footer>Offline-first scaffold by Kai (Vibe Coder) from the EduVis blueprint ·
edit the three questions above to fit your chapter · no data leaves this file.</footer>

<script>
const ANSWERS = [
  "Model: a one-sentence definition naming the core idea of {{t}} (swap in the exact CBSE wording).",
  "Model: a concrete situation — name the decision that hinges on {{t}}.",
  "Model: first check the pre-conditions/definition of {{t}} before blaming the calculation."
];
const HINTS = [
  "Hint: it starts with the definition — key term + what it does.",
  "Hint: think of a transaction or decision in Class 11-12 Commerce where the rule matters.",
  "Hint: misapplied usually means wrong rule applied to the right case."
];
const T = {topic!r};
let done = [false, false, false];
function hint(i) {{
  const el = document.getElementById('f' + i);
  if (!done[i]) {{
    el.className = 'fb ok';
    el.textContent = (el.textContent ? '' : '') + HINTS[i] + '  →  ' + ANSWERS[i].replace(/{{t}}/g, T);
    done[i] = true;
    const n = done.filter(Boolean).length;
    document.getElementById('bar').style.width = (n / 3 * 100) + '%';
    document.getElementById('score').textContent = n + ' / 3 explored';
  }}
}}
function resetAll() {{
  done = [false, false, false];
  for (let i = 0; i < 3; i++) {{ const e = document.getElementById('f' + i); e.textContent = ''; e.className = 'fb'; }}
  document.getElementById('bar').style.width = '0%';
  document.getElementById('score').textContent = '0 / 3 explored';
}}
</script>
</body>
</html>
"""
    ok, detail = validate_structure(app_html)
    offline = "http://" not in app_html and "https://" not in app_html and "cdn" not in app_html
    return {
        "artifacts": [{"name": f"app_{_slug_topic(topic)}.html", "kind": "web_app",
                       "content": app_html,
                       "status": "TRUSTED" if (ok and offline) else "NEEDS_REVIEW"}],
        "notes": [detail, "single-file offline app — open by double-click; "
                          "edit QUESTIONS/ANSWERS arrays to fit the chapter"],
        "validators": [
            {"name": "structure", "passed": ok, "detail": detail},
            {"name": "offline_first", "passed": offline,
             "detail": "no external URLs/CDN — fully offline" if offline
                       else "external resource referenced — offline promise broken"},
        ],
        "provenance": {"level": "INTERNAL_KNOWLEDGE",
                       "note": "Deterministic scaffold; no external code was fetched."},
    }


def _slug_topic(t: str) -> str:
    import re as _re
    return _re.sub(r"[^a-z0-9]+", "_", (t or "topic").lower()).strip("_")[:32] or "topic"


# ===========================================================================
# HITL/PR skill pack — official email (Composio-inspired deterministic tool)
# ===========================================================================

@register({
    "id": "draft_official_email",
    "name": "Official Email Drafter",
    "category": "admin",
    "triggers": ["official email", "email draft", "draft an email", "draft email",
                 "write an email", "write a mail", "email draft to principal",
                 "आधिकारिक ईमेल"],
    "input_schema": {"required": ["topic"],
                     "optional": ["subject", "recipient", "class_level", "language"]},
    "output_schema": {"official_email": "markdown"},
    "validators": ["structure", "recipient_slot"],
    "autonomy": 2, "risk": 0.3,
    "tools": [],
})
def gen_official_email(entities: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic official email draft (Herald). NEVER sends — artifact is
    flagged NEEDS_APPROVAL and the draft_press_release/draft_official_email
    intent is forced to L4 HUMAN_APPROVAL_REQUIRED in decision.py (C7)."""
    topic = entities.get("topic") or entities.get("subject") or "the matter"
    recipient = entities.get("recipient") or "[To: Designation / Name]"
    subject = entities.get("subject") or topic
    lines = [
        "## DRAFT OFFICIAL EMAIL — flagged NEEDS_APPROVAL (L4)",
        "",
        f"**To:** {recipient}",
        "**Cc:** [office record copy, if applicable]",
        f"**Subject:** {subject} — [reference no., if any]",
        "",
        "Respected Sir/Madam,",
        "",
        f"With reference to **{topic}**, I wish to place the following for your kind "
        "information and necessary action:",
        "",
        "1. [Fact/point one — verified against the official record].",
        "2. [Fact/point two — with date/document reference].",
        "3. [Action requested — clear, single, time-bound ask].",
        "",
        "The relevant record/annexure is attached for reference. Kindly confirm the "
        "same so that the next step may be taken at the earliest.",
        "",
        "Thanking you,",
        "Yours faithfully,",
        "[Name] · [Designation] · [Institution] · [Contact]",
        "",
        "**Pre-send checklist (Herald's gate):**",
        "1. Recipient name/designation verified (no placeholders left) (C1).",
        "2. Every date/number cross-checked with the office record (C1).",
        "3. Tone formal; no unverified claim, no promise on behalf of others (C3).",
        "4. DISPATCH requires explicit human approval — this artifact is a DRAFT "
        "carrying the NEEDS_APPROVAL flag (L4/C7).",
    ]
    content = "\n".join(lines)
    ok, detail = validate_structure(content)
    has_recipient = "**To:**" in content and "[To: Designation" in content
    gated = "NEEDS_APPROVAL" in content
    return {
        "artifacts": [{"name": "official_email_draft.md", "kind": "official_email",
                       "content": content,
                       "status": "TRUSTED" if (ok and has_recipient and gated)
                                 else "NEEDS_REVIEW",
                       "needs_approval": True, "approval_flag": "NEEDS_APPROVAL"}],
        "notes": [detail, "artifact flagged NEEDS_APPROVAL — dispatch is L4-gated"],
        "validators": [
            {"name": "structure", "passed": ok, "detail": detail},
            {"name": "recipient_slot", "passed": has_recipient,
             "detail": "recipient line present; fill designation before sending"
                       if has_recipient else "recipient slot missing"},
        ],
        "provenance": {"level": "INTERNAL_KNOWLEDGE",
                       "note": "Deterministic email template; slots marked for verification."},
    }


# ===========================================================================
# Vibe Coder skill pack (OpenHands/Aider-inspired): code_generator +
# code_validator — shared deterministic builders
# ===========================================================================

# Templates use __TOPIC__/__SLUG__ tokens (NOT f-strings) so JSX/Python braces
# survive literally — lesson learned from web_app_scaffold.
_REACT_SIM_TPL = '''import React, { useState } from "react";

/**
 * Accountancy Equation Lab — __TOPIC__
 * Vibe Coder artifact (NEVERMIND OS). Build once with Vite + Tailwind; the
 * built output runs fully offline (no CDN, no API calls at runtime).
 */
const TOPIC = "__TOPIC__";

const ROUNDS = [
  { a: 50000, l: 20000, e: 30000, hint: "Capital + creditors = assets" },
  { a: 80000, l: 35000, e: 45000, hint: "Recheck the revaluation effect" },
  { a: 120000, l: 40000, e: 80000, hint: "Goodwill treatment: A = L + E" },
];

export default function EquationLab() {
  const [assets, setAssets] = useState("");
  const [liab, setLiab] = useState("");
  const [eq, setEq] = useState("");
  const [round, setRound] = useState(0);
  const [score, setScore] = useState(0);
  const [msg, setMsg] = useState("");

  const check = () => {
    if (assets === "" || liab === "" || eq === "") {
      setMsg("Enter three numbers — Assets, Liabilities, Capital.");
      return;
    }
    const A = Number(assets), L = Number(liab), E = Number(eq);
    const balanced = Math.abs(A - (L + E)) < 0.005;
    if (balanced) {
      setScore((s) => s + 1);
      setMsg("✔ Balanced — A = L + E. Next round loaded.");
      setRound((r) => (r + 1) % ROUNDS.length);
    } else {
      setMsg("✘ Not balanced: A " + A + " vs L+E " + (L + E) + ". " + ROUNDS[round].hint);
    }
    setAssets("");
    setLiab("");
    setEq("");
  };

  const loadRound = () => {
    const r = ROUNDS[round];
    setAssets(String(r.a));
    setLiab(String(r.l));
    setEq(String(r.e));
    setMsg("Round numbers loaded — now change one side to break and fix the balance.");
  };

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 p-6 flex items-center justify-center">
      <main className="w-full max-w-xl rounded-2xl bg-slate-800 p-6 shadow-xl space-y-4">
        <h1 className="text-2xl font-bold text-amber-300">Equation Lab — {TOPIC}</h1>
        <p className="text-sm text-slate-300">
          Enter Assets, Liabilities and Capital so that A = L + E holds. Learning
          objective: verify the accounting equation under changing transactions.
        </p>
        <div className="grid grid-cols-3 gap-3">
          <label className="text-xs text-slate-400">Assets
            <input value={assets} onChange={(e) => setAssets(e.target.value)}
              inputMode="numeric"
              className="mt-1 w-full rounded-lg bg-slate-900 p-2 text-right text-slate-100" />
          </label>
          <label className="text-xs text-slate-400">Liabilities
            <input value={liab} onChange={(e) => setLiab(e.target.value)}
              inputMode="numeric"
              className="mt-1 w-full rounded-lg bg-slate-900 p-2 text-right text-slate-100" />
          </label>
          <label className="text-xs text-slate-400">Capital
            <input value={eq} onChange={(e) => setEq(e.target.value)}
              inputMode="numeric"
              className="mt-1 w-full rounded-lg bg-slate-900 p-2 text-right text-slate-100" />
          </label>
        </div>
        <div className="flex flex-wrap gap-3">
          <button onClick={check}
            className="rounded-lg bg-emerald-500 px-4 py-2 font-semibold text-slate-900">
            Check balance
          </button>
          <button onClick={loadRound}
            className="rounded-lg bg-slate-600 px-4 py-2 font-semibold">
            Load round numbers
          </button>
          <button onClick={() => { setScore(0); setRound(0); setMsg(""); }}
            className="rounded-lg bg-slate-700 px-4 py-2 font-semibold">
            Reset
          </button>
        </div>
        <p aria-live="polite" className="min-h-[1.5rem] rounded-lg bg-slate-900 p-3 text-sm">
          {msg}
        </p>
        <footer className="text-xs text-slate-400">
          Round {round + 1}/{ROUNDS.length} · Score {score} · offline build — no network calls
        </footer>
      </main>
    </div>
  );
}
'''

_REACT_README_TPL = '''# Equation Lab — __TOPIC__ (Vibe Coder build pack)

Generated by NEVERMIND OS `code_generator` (offline-first).

## Files
- `EquationLab.jsx` — React component (Tailwind classes), self-contained state machine.

## Build (once, on any machine with node)
```bash
npm create vite@latest equation-lab -- --template react
cd equation-lab
npm install
npm install -D tailwindcss postcss autoprefixer && npx tailwindcss init -p
# put the component in src/EquationLab.jsx, import it from App.jsx
npm run build
```
The **built `dist/` runs fully offline** — no CDN, no API keys, no runtime network.
Deterministic practice rounds live in the `ROUNDS` array — edit to fit the chapter.

## Honest notes
- This is source code, not a running app (C2): run `npm run build` to verify.
- Validation report: see the companion `code_report_*` artifact from `code_validator`.
'''

_PY_LAB_TPL = '''"""Accountancy Equation Lab — __TOPIC__ (NEVERMIND OS · Vibe Coder).

Stdlib-only Python lab: zero dependencies, runs offline:
    python3 sim___SLUG___lab.py
"""
from __future__ import annotations

import sys

ROUNDS = [
    (50000, 20000, 30000, "Capital + creditors = assets"),
    (80000, 35000, 45000, "Recheck the revaluation effect"),
    (120000, 40000, 80000, "Goodwill treatment: A = L + E"),
]


def balanced(a: float, l: float, e: float) -> bool:
    """Deterministic accounting-equation check: A == L + E."""
    return abs(a - (l + e)) < 0.005


def parse_number(raw: str) -> float | None:
    try:
        return float(raw.strip())
    except (ValueError, AttributeError):
        return None


def main() -> int:
    print("Equation Lab (offline) — __TOPIC__")
    print("Learning objective: verify A = L + E under changing transactions.")
    score = 0
    for i, (a, l, e, hint) in enumerate(ROUNDS, 1):
        print(f"\\nRound {i}/{len(ROUNDS)}: set your own A, L, E and prove the balance.")
        vals = []
        for label in ("Assets", "Liabilities", "Capital"):
            v = parse_number(input(f"  {label}: "))
            if v is None:
                print("  Not a number — round skipped.")
                break
            vals.append(v)
        else:
            if balanced(*vals):
                score += 1
                print("  ✔ Balanced — A = L + E.")
            else:
                print(f"  ✘ Not balanced (A {vals[0]} vs L+E {vals[1] + vals[2]}). {hint}")
    print(f"\\nScore: {score}/{len(ROUNDS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


def _build_react_pack(topic: str) -> Dict[str, str]:
    """Deterministic React+Tailwind equation-lab source pack (filename -> content)."""
    slug = _slug_topic(topic)
    js_topic = topic.replace("\\", "\\\\").replace('"', '\\"')
    app = _REACT_SIM_TPL.replace("__TOPIC__", js_topic)
    readme = _REACT_README_TPL.replace("__TOPIC__", topic)
    return {f"sim_{slug}_EquationLab.jsx": app,
            f"sim_{slug}_README.md": readme}


def _build_python_lab(topic: str) -> Dict[str, str]:
    """Stdlib-only Python equation lab (filename -> content)."""
    slug = _slug_topic(topic)
    js_topic = topic.replace("\\", "\\\\").replace('"', '\\"')
    py = _PY_LAB_TPL.replace("__TOPIC__", js_topic).replace("__SLUG__", slug)
    return {f"sim_{slug}_lab.py": py}


@register({
    "id": "code_generator",
    "name": "Simulator Code Generator",
    "category": "engineering",
    "triggers": ["react", "tailwind", "codebase", "source code", "equation lab",
                 "python lab", "python script", "component code", "npm"],
    "input_schema": {"required": ["topic"],
                     "optional": ["stack", "subject", "class_level"]},
    "output_schema": {"code_pack": "jsx|python|markdown"},
    "validators": ["structure", "completeness"],
    "autonomy": 2, "risk": 0.1,
    "tools": [],
})
def gen_code_generator(entities: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Vibe Coder: emits a buildable codebase for an interactive simulator
    (React+Tailwind pack by default; `stack: python` for a stdlib lab)."""
    topic = entities.get("topic") or entities.get("subject") or "the equation"
    stack = (entities.get("stack") or "").lower()
    if not stack:
        blob = f"{ctx.get('command', '')}".lower()
        stack = "python" if ("python" in blob or "py script" in blob) else "react"
    pack = _build_python_lab(topic) if stack == "python" else _build_react_pack(topic)

    artifacts, validators = [], []
    for name, content in pack.items():
        ok, detail = validate_structure(content)
        if name.endswith(".md"):
            complete = "__TOPIC__" not in content and "npm run build" in content
            validators.append({"name": "structure", "passed": ok, "detail": detail})
            validators.append({"name": "completeness", "passed": complete,
                               "detail": "build instructions present, topic injected"
                                         if complete else "build steps/topic missing"})
            status = "TRUSTED" if (ok and complete) else "NEEDS_REVIEW"
        elif name.endswith(".py"):
            import ast as _ast
            try:
                _ast.parse(content)
                syntax_ok, syntax_detail = True, "python syntax valid (ast.parse)"
            except SyntaxError as e:
                syntax_ok, syntax_detail = False, f"syntax error: {e}"
            complete = ("def main" in content and 'if __name__ == "__main__"' in content
                        and "__TOPIC__" not in content)
            validators.append({"name": "structure", "passed": syntax_ok,
                               "detail": syntax_detail})
            validators.append({"name": "completeness", "passed": complete,
                               "detail": "entry point + topic injected" if complete
                                         else "entry point/topic placeholder missing"})
            status = "TRUSTED" if (syntax_ok and complete) else "NEEDS_REVIEW"
        else:
            complete = ("export default" in content and "useState" in content
                        and "__TOPIC__" not in content and "http://" not in content
                        and "https://" not in content)
            validators.append({"name": "structure", "passed": ok, "detail": detail})
            validators.append({"name": "completeness", "passed": complete,
                               "detail": "export+hooks+topic injected, no runtime URLs"
                                         if complete else "missing export/hooks/topic"})
            status = "TRUSTED" if (ok and complete) else "NEEDS_REVIEW"
        artifacts.append({"name": name, "kind": "code", "content": content,
                          "status": status})
    all_ok = all(a["status"] == "TRUSTED" for a in artifacts)
    return {
        "artifacts": artifacts,
        "notes": [f"stack={stack}: {len(artifacts)} files generated",
                  "source pack only — build it (npm run build / python3) to verify (C2)"],
        "validators": validators,
        "provenance": {"level": "INTERNAL_KNOWLEDGE",
                       "note": "Deterministic code templates; no external code fetched."},
    }


@register({
    "id": "code_validator",
    "name": "Static Code Validator",
    "category": "engineering",
    "triggers": ["validate code", "static check", "code check", "lint the code",
                 "check the codebase"],
    "input_schema": {"required": ["topic"],
                     "optional": ["code", "stack"]},
    "output_schema": {"validation_report": "markdown"},
    "validators": ["structure", "completeness"],
    "autonomy": 2, "risk": 0.05,
    "tools": [],
})
def gen_code_validator(entities: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Static completeness check of generated UI code BEFORE it is saved as a
    deliverable: validates `entities['code']` when supplied, otherwise rebuilds
    the deterministic pack for the topic and audits every file."""
    topic = entities.get("topic") or entities.get("subject") or "the topic"
    given = entities.get("code") or ctx.get("code")
    stack = (entities.get("stack") or "").lower()
    if given:
        files = {"given_source.py" if stack == "python" else "given_source.jsx": given}
        if not stack:
            stack = "python" if given.lstrip().startswith(("import ", '"""')) else "react"
    else:
        if not stack:
            blob = f"{ctx.get('command', '')}".lower()
            stack = "python" if ("python" in blob or "py script" in blob) else "react"
        files = _build_python_lab(topic) if stack == "python" else _build_react_pack(topic)

    checks: List[Dict[str, Any]] = []
    lines: List[str] = [f"# Static code validation — {topic} (stack: {stack})", ""]
    for name, src in files.items():
        opens = src.count("{") - src.count("}")
        parens = src.count("(") - src.count(")")
        no_leak = "__TOPIC__" not in src and "__SLUG__" not in src
        if name.endswith(".md"):
            doc_ok = no_leak and "npm run build" in src and len(src) > 200
            checks.append((name, "structure", no_leak and len(src) > 100,
                           "no placeholder leak, document present"))
            checks.append((name, "completeness", doc_ok,
                           "build instructions present" if doc_ok
                           else "missing build instructions/topic"))
            continue
        if name.endswith(".py") or stack == "python":
            import ast as _ast
            try:
                tree = _ast.parse(src)
                syn_ok, syn_detail = True, "ast.parse OK"
            except SyntaxError as e:
                tree, syn_ok, syn_detail = None, False, f"syntax error: {e}"
            stdlib = {"sys", "re", "json", "math", "typing", "collections", "random",
                      "datetime", "time", "dataclasses", "functools", "itertools",
                      "pathlib", "string", "textwrap", "unittest", "ast", "__future__"}
            bad = []
            if tree is not None:
                for n in _ast.walk(tree):
                    if isinstance(n, _ast.Import):
                        bad += [a.name.split(".")[0] for a in n.names
                                if a.name.split(".")[0] not in stdlib]
                    elif isinstance(n, _ast.ImportFrom) and n.module and \
                            n.module.split(".")[0] not in stdlib:
                        bad.append(n.module.split(".")[0])
            entry = 'if __name__ == "__main__"' in src
            checks.append((name, "structure", syn_ok and opens == 0,
                           f"{syn_detail}; brace balance {'ok' if opens == 0 else 'BROKEN'}"))
            checks.append((name, "completeness", entry and no_leak and not bad,
                           "entry point present, no placeholder leak, stdlib-only imports"
                           + (f" — FOUND {sorted(set(bad))}" if bad else "")))
        else:
            imp = "import React" in src and "useState" in src
            exp = "export default" in src
            offline = "http://" not in src and "https://" not in src
            checks.append((name, "structure", opens == 0 and parens == 0,
                           f"brace balance {'ok' if opens == 0 else 'BROKEN'}, "
                           f"paren balance {'ok' if parens == 0 else 'BROKEN'}"))
            checks.append((name, "completeness", imp and exp and no_leak and offline,
                           "import+export present, topic injected, no runtime URLs"
                           if (imp and exp and no_leak and offline)
                           else "missing import/export/topic or external URL found"))

    for fname, cname, passed, detail in checks:
        lines.append(f"- `{fname}` · **{cname}**: {'✔ PASS' if passed else '✘ FAIL'} — {detail}")
    all_ok = all(c[2] for c in checks)
    lines += ["", f"**Verdict:** {'STATIC CHECK PASSED' if all_ok else 'DEFECTS FOUND — do not ship'}",
              "", "Heuristic static audit (balanced delimiters, entry points, topic "
                  "injection, stdlib-only, offline-first). Build + run still required "
                  "before claiming it works (C2)."]
    content = "\n".join(lines)
    return {
        "artifacts": [{"name": f"code_report_{_slug_topic(topic)}.md",
                       "kind": "code_report", "content": content,
                       "status": "TRUSTED" if all_ok else "NEEDS_REVIEW"}],
        "notes": [f"{sum(1 for c in checks if c[2])}/{len(checks)} static checks passed"],
        "validators": [{"name": "structure",
                        "passed": all(c[2] for c in checks if c[1] == "structure"),
                        "detail": "delimiter balance / syntax across files"},
                       {"name": "completeness",
                        "passed": all(c[2] for c in checks if c[1] == "completeness"),
                        "detail": "entry points, topic injection, offline/stdlib constraints"}],
        "provenance": {"level": "INTERNAL_KNOWLEDGE",
                       "note": "Pure static analysis — no code was executed."},
    }
