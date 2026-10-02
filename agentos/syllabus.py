"""Official CBSE syllabus knowledge — Session 2026-27 (SecP2 documents).

Deep, structured awareness for the agent: per subject (Accountancy 055,
Business Studies 054, Entrepreneurship 066) and per class (XI / XII):

  * unit-by-unit weightage (official marks distribution)
  * unit-by-unit topic lists (verbatim-faithful from the CBSE documents)
  * question-paper typology split (Remembering/Understanding vs Applying
    vs Analysing-Evaluating-Creating) with marks AND percentages
  * project-work marks + structure
  * scope notes / official exclusions (e.g. GST is Class-XI only,
    dissolution excludes piecemeal distribution, Cash Flow = Ind AS 3
    indirect method only …)

Source files (extracted text kept for audit):
  /home/user/syllabus/Accountancy_SecP2_2026-27.txt
  /home/user/syllabus/BusinessStudies_SecP2_2026-27.txt
  /home/user/syllabus/Enterprenuership_SecP2_2026-27.txt

Everything here is deterministic and offline (C1). Use it to:
  * anchor question papers / worksheets / lesson plans to real units
  * validate that a requested topic is INSIDE the official syllabus
  * tell the user exactly which unit & marks a deliverable covers
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

SESSION = "2026-27"

# ---------------------------------------------------------------------------
# The knowledge base
# ---------------------------------------------------------------------------

SUBJECTS: Dict[str, Dict[str, Any]] = {
    "Accountancy": {
        "code": "055",
        "typology": {
            "total": 80,
            "rows": [
                {"name": "Remembering and Understanding", "marks": 32, "pct": 40},
                {"name": "Applying", "marks": 24, "pct": 30},
                {"name": "Analysing, Evaluating and Creating", "marks": 24, "pct": 30},
            ],
        },
        "classes": {
            "XII": {
                "theory": 80, "project": 20,
                "weightage": [
                    {"units": [1], "marks": 36, "part": "A",
                     "part_title": "Accounting for Partnership Firms and Companies"},
                    {"units": [2], "marks": 24, "part": "A",
                     "part_title": "Accounting for Partnership Firms and Companies"},
                    {"units": [3], "marks": 12, "part": "B",
                     "part_title": "Financial Statement Analysis"},
                    {"units": [4], "marks": 8, "part": "B",
                     "part_title": "Financial Statement Analysis"},
                ],
                "units": [
                    {"unit": 1, "title": "Accounting for Partnership Firms", "topics": [
                        "Partnership: features, Partnership Deed",
                        "Provisions of the Indian Partnership Act 1932 in the absence of deed",
                        "Fixed vs fluctuating capital accounts",
                        "Profit and Loss Appropriation account — division of profit, guarantee of profits",
                        "Past adjustments (interest on capital/drawings, salary, profit ratio)",
                        "Goodwill: meaning, nature, factors, valuation — average profit, super profit, capitalisation",
                        "Change in profit sharing ratio: sacrificing ratio, gaining ratio",
                        "Revaluation of assets and reassessment of liabilities; treatment of reserves & accumulated profits",
                        "Admission of a partner: goodwill as per AS-26, revaluation, capital/current accounts, balance sheet",
                        "Retirement and death: effect on ratio, goodwill, revaluation, capital adjustment, loan account of retiring partner",
                        "Deceased partner's share of profit till date of death; deceased partner & executor accounts",
                        "Dissolution: settlement of accounts — realization account, partners' capital, cash/bank",
                    ]},
                    {"unit": 2, "title": "Accounting for Companies", "topics": [
                        "Features and types of companies",
                        "Share and share capital: nature and types; equity vs preference shares",
                        "Issue and allotment of equity and preference shares",
                        "Public subscription: over/under subscription; issue at par and at premium",
                        "Calls in advance and arrears (excluding interest)",
                        "Issue of shares for consideration other than cash",
                        "Private Placement, Employee Stock Option Plan (ESOP), Sweat Equity",
                        "Forfeiture and re-issue of shares",
                        "Disclosure of share capital in the Balance Sheet (Schedule III, Companies Act 2013)",
                        "Debentures: meaning, types; issue at par/premium/discount",
                        "Debentures for consideration other than cash; with terms of redemption",
                        "Debentures as collateral security; interest on debentures (TDS excluded)",
                        "Writing off discount/loss on issue of debentures (SPR first, then P&L as financial cost, AS-16)",
                    ]},
                    {"unit": 3, "title": "Analysis of Financial Statements", "topics": [
                        "Financial statements of a company: meaning, nature, uses (Schedule III form)",
                        "Statement of Profit and Loss and Balance Sheet — major headings/sub-headings",
                        "Financial statement analysis: meaning, significance, objectives, importance, limitations",
                        "Tools: comparative statements, common size statements, ratio analysis, cash flow analysis",
                        "Accounting ratios: meaning, objectives, classification, computation",
                        "Liquidity: Current ratio, Quick ratio",
                        "Solvency: Debt to Equity, Total Asset to Debt, Proprietary, Interest Coverage, Debt to Capital Employed",
                        "Activity: Inventory Turnover, Trade Receivables Turnover, Trade Payables Turnover, "
                        "Fixed Asset Turnover, Net Asset Turnover, Working Capital Turnover",
                        "Profitability: Gross Profit Ratio, Operating Ratio, Operating Profit Ratio, "
                        "Net Profit Ratio (on profit before and after tax), Return on Investment",
                    ]},
                    {"unit": 4, "title": "Cash Flow Statement", "topics": [
                        "Meaning, objectives, benefits; cash and cash equivalents",
                        "Classification of activities; preparation as per AS-3 (Revised) — Indirect Method only",
                        "Adjustments: depreciation & amortisation, profit/loss on sale of assets incl. investments, "
                        "dividend (final and interim), tax",
                        "Bank overdraft and cash credit as short-term borrowings",
                        "Current investments treated as marketable securities unless specified",
                        "Proposed dividend as per AS-4 (current year's proposed dividend accounted next year)",
                    ]},
                ],
                "project": "Part C Project Work 20 marks (Project File 12 + Viva Voce 8) OR "
                           "Part B Computerized Accounting 20 + Part C Practical Work 20 "
                           "(Practical File 12 + Viva 8)",
                "scope_notes": [
                    "Dissolution excludes piecemeal distribution, sale to a company and insolvency of partner(s).",
                    "Realised value of tangible assets not given → treat as book value; intangibles not given → nil.",
                    "Interest on partner's loan is a charge against profits.",
                    "Goodwill adjusted through partners' capital/current accounts; AS-26 applies.",
                    "Cash Flow Statement: Indirect Method only; exceptional/extraordinary/discontinued items excluded "
                    "from Financial Statement Analysis.",
                    "Discount/loss on issue of debentures written off from Security Premium Reserve first, then P&L.",
                ],
                "books": ["Accountancy - I Class XII NCERT", "Accountancy - II Class XII NCERT",
                          "Accountancy — Computerised Accounting System Class XII NCERT"],
            },
            "XI": {
                "theory": 80, "project": 20,
                "weightage": [
                    {"units": [1], "marks": 12, "part": "A", "part_title": "Financial Accounting-1"},
                    {"units": [2], "marks": 44, "part": "A", "part_title": "Financial Accounting-1"},
                    {"units": [3], "marks": 24, "part": "B", "part_title": "Financial Accounting-II"},
                ],
                "units": [
                    {"unit": 1, "title": "Theoretical Framework", "topics": [
                        "Introduction to Accounting: concept, objectives, advantages, limitations, types of information",
                        "Users of accounting information and their needs; qualitative characteristics",
                        "Basic Accounting Terms: entity, transaction, capital, drawings, liabilities, assets, "
                        "expenditure, expense, revenue, income, profit, gain, loss, purchase, sales, stock, "
                        "debtor, creditor, voucher, discount (trade & cash)",
                        "Fundamental accounting assumptions; GAAP concept",
                        "Basic accounting concepts: business entity, money measurement, going concern, accounting period, "
                        "cost, dual aspect, revenue recognition, matching, full disclosure, consistency, conservatism, "
                        "materiality, objectivity",
                        "System of accounting; cash basis vs accrual basis",
                        "Accounting Standards: AS and IndAS applicability",
                        "Goods and Services Tax (GST): characteristics and advantages",
                    ]},
                    {"unit": 2, "title": "Accounting Process", "topics": [
                        "Vouchers and transactions; source documents; preparation of vouchers",
                        "Accounting equation approach; rules of debit and credit",
                        "Journal — books of original entry",
                        "Special purpose books: simple cash book, cash book with bank column, petty cash book, "
                        "purchases book, sales book, purchases return book, sales return book, journal proper",
                        "Simple GST calculation (incl. trade discount, freight, cartage)",
                        "Ledger: format, posting, balancing",
                        "Bank Reconciliation Statement: need and preparation",
                        "Depreciation: meaning, need, causes, factors; depletion and amortisation",
                        "Methods of depreciation: Straight Line Method (SLM) and Written Down Value (WDV); "
                        "comparison; change of method excluded",
                        "Recording depreciation: charging to asset account vs provision/accumulated depreciation account",
                        "Disposal of asset; provisions and reserves; types of reserves (revenue, capital, general, "
                        "specific, secret); capital vs revenue reserve",
                        "Trial balance (balance method only); errors: omission, commission, principle, compensating",
                        "Detection and rectification of errors; suspense account",
                    ]},
                    {"unit": 3, "title": "Financial Statements of Sole Proprietorship", "topics": [
                        "Financial statements: meaning, objectives, importance; revenue vs capital receipts/expenditure; "
                        "deferred revenue expenditure; opening journal entry",
                        "Trading and Profit & Loss Account: gross profit, operating profit, net profit",
                        "Balance Sheet: need, grouping and marshalling",
                        "Adjustments: closing stock, outstanding expenses, prepaid expenses, accrued income, "
                        "income received in advance, depreciation, bad debts, provision for doubtful debts, "
                        "provision for discount on debtors, abnormal loss, goods taken for personal use/staff welfare, "
                        "interest on capital, managers' commission",
                        "Incomplete records: features, reasons, limitations; profit/loss by Statement of Affairs method "
                        "(conversion method excluded)",
                    ]},
                ],
                "project": "Part C Project Work 20 marks — any one: (1) source documents & vouchers; "
                           "(2) BRS with cash book/pass book (20–25 transactions); "
                           "(3) comprehensive sole-proprietorship project with charts.",
                "scope_notes": [
                    "GST treatment is confined to Class XI (Class XII has no GST in Accountancy).",
                    "Depreciation: change of method excluded; trial balance with balance method only.",
                    "Incomplete records: conversion method excluded.",
                ],
                "books": ["Financial Accounting - I Class XI NCERT", "Accountancy - II Class XI NCERT"],
            },
        },
    },

    "Business Studies": {
        "code": "054",
        "typology": {
            "total": 80,
            "rows": [
                {"name": "Remembering and Understanding", "marks": 32, "pct": 40},
                {"name": "Applying", "marks": 24, "pct": 30},
                {"name": "Analysing, Evaluating and Creating", "marks": 24, "pct": 30},
            ],
        },
        "classes": {
            "XII": {
                "theory": 80, "project": 20,
                "weightage": [
                    {"units": [1, 2, 3], "marks": 16, "part": "A",
                     "part_title": "Principles and Functions of Management"},
                    {"units": [4, 5], "marks": 14, "part": "A",
                     "part_title": "Principles and Functions of Management"},
                    {"units": [6, 7, 8], "marks": 20, "part": "A",
                     "part_title": "Principles and Functions of Management"},
                    {"units": [9, 10], "marks": 15, "part": "B",
                     "part_title": "Business Finance and Marketing"},
                    {"units": [11, 12], "marks": 15, "part": "B",
                     "part_title": "Business Finance and Marketing"},
                ],
                "units": [
                    {"unit": 1, "title": "Nature and Significance of Management", "topics": [
                        "Management: concept, objectives, importance",
                        "Effectiveness and efficiency",
                        "Management as science, art and profession",
                        "Levels of management: top, middle, lower",
                        "Management functions: planning, organising, staffing, directing, controlling",
                        "Coordination: concept, characteristics, importance",
                    ]},
                    {"unit": 2, "title": "Principles of Management", "topics": [
                        "Principles of management: concept and significance",
                        "Fayol's principles of management (14 principles)",
                        "Taylor's Scientific Management: principles and techniques",
                        "Comparison of Fayol's and Taylor's contributions",
                    ]},
                    {"unit": 3, "title": "Business Environment", "topics": [
                        "Business environment: concept and importance",
                        "Dimensions: economic, social, technological, political, legal",
                        "Demonetisation: concept and features",
                    ]},
                    {"unit": 4, "title": "Planning", "topics": [
                        "Planning: concept, importance, limitations",
                        "Planning process",
                        "Single-use and standing plans: objectives, strategy, policy, procedure, method, rule, budget, programme",
                    ]},
                    {"unit": 5, "title": "Organising", "topics": [
                        "Organising: concept (structure & process) and importance; organising process",
                        "Structure: functional and divisional",
                        "Formal and informal organisation",
                        "Delegation: concept, elements, importance",
                        "Decentralisation: concept, importance; delegation vs decentralisation",
                    ]},
                    {"unit": 6, "title": "Staffing", "topics": [
                        "Staffing: concept and importance; staffing as part of HRM",
                        "Staffing process",
                        "Recruitment: process, sources, internal vs external merits/demerits",
                        "Selection process",
                        "Training and development: on-job (vestibule, apprenticeship, internship) and off-job methods",
                    ]},
                    {"unit": 7, "title": "Directing", "topics": [
                        "Directing: concept and importance",
                        "Elements of directing",
                        "Motivation: concept, Maslow's hierarchy of needs, financial & non-financial incentives",
                        "Leadership: concept and styles — authoritative, democratic, laissez faire",
                        "Communication: formal/informal, barriers and overcoming them",
                    ]},
                    {"unit": 8, "title": "Controlling", "topics": [
                        "Controlling: concept and importance",
                        "Relationship between planning and controlling",
                        "Steps in the process of control",
                    ]},
                    {"unit": 9, "title": "Financial Management", "topics": [
                        "Financial management: concept, role, objectives",
                        "Financial decisions: investment, financing, dividend — meaning and factors",
                        "Financial planning: concept and importance",
                        "Capital structure: concept and factors",
                        "Fixed and working capital: concept and factors affecting requirements",
                    ]},
                    {"unit": 10, "title": "Financial Markets", "topics": [
                        "Financial markets: concept",
                        "Money market: concept",
                        "Capital market: primary and secondary",
                        "Stock exchange: functions and trading procedure",
                        "Depository services and demat account",
                        "SEBI: objectives and functions",
                    ]},
                    {"unit": 11, "title": "Marketing Management", "topics": [
                        "Marketing: concept, functions, philosophies",
                        "Marketing mix — concept and elements",
                        "Product: branding, labelling, packaging",
                        "Price: concept and factors determining price",
                        "Physical distribution: concept, components, channels of distribution",
                        "Promotion: advertising, personal selling, sales promotion, public relations",
                    ]},
                    {"unit": 12, "title": "Consumer Protection", "topics": [
                        "Consumer protection: concept and importance; scope of Consumer Protection Act, 2019",
                        "Consumer Protection Act 2019: meaning of consumer, rights & responsibilities, "
                        "who can file a complaint, redressal machinery, remedies available",
                        "Consumer awareness: role of consumer organisations and NGOs",
                    ]},
                ],
                "project": "Part C Project Work 20 marks — any ONE of: (1) Elements of Business Environment; "
                           "(2) Principles of Management (field visit — Fayol/Taylor application); "
                           "(3) Stock Exchange (imaginary ₹50,000 portfolio over 20 working days); "
                           "(4) Marketing product plan. Assessment: initiative 2 + creativity 2 + "
                           "content/research 4 + analysis 4 + viva 8.",
                "scope_notes": [
                    "Consumer Protection as per Consumer Protection Act, 2019 (not the old 1986 Act).",
                    "Demonetisation is part of Business Environment (Unit 3).",
                ],
            },
            "XI": {
                "theory": 80, "project": 20,
                "weightage": [
                    {"units": [1, 2], "marks": 16, "part": "A", "part_title": "Foundations of Business"},
                    {"units": [3, 4], "marks": 14, "part": "A", "part_title": "Foundations of Business"},
                    {"units": [5, 6], "marks": 10, "part": "A", "part_title": "Foundations of Business"},
                    {"units": [7, 8], "marks": 20, "part": "B", "part_title": "Finance and Trade"},
                    {"units": [9, 10], "marks": 20, "part": "B", "part_title": "Finance and Trade"},
                ],
                "units": [
                    {"unit": 1, "title": "Evolution and Fundamentals of Business", "topics": [
                        "History of trade and commerce in India: indigenous banking, intermediaries, transport, "
                        "trading communities, trade centres, imports/exports, Indian sub-continent's position",
                        "Business: meaning and characteristics",
                        "Business, profession and employment — concept and differences",
                        "Objectives of business; role of profit",
                        "Classification: industry (primary/secondary/tertiary) and commerce "
                        "(trade: internal/external, wholesale/retail; auxiliaries: banking, insurance, "
                        "transport, warehousing, communication, advertising)",
                        "Business risk: concept, nature, causes",
                    ]},
                    {"unit": 2, "title": "Forms of Business Organisations", "topics": [
                        "Sole proprietorship: concept, merits, limitations",
                        "Partnership: concept, types, merits, limitations, registration, deed, types of partners",
                        "Hindu Undivided Family business",
                        "Cooperative societies: consumers, producers, marketing, farmers, credit, housing",
                        "Company: concept, merits, limitations; private, public, one person company",
                        "Formation of company: stages and important documents",
                        "Choice of form of business organisation — factors",
                    ]},
                    {"unit": 3, "title": "Public, Private and Global Enterprises", "topics": [
                        "Public and private sector enterprises — concept",
                        "Forms: departmental undertakings, statutory corporations, government companies",
                        "Global enterprises: features; joint venture; public private partnership",
                    ]},
                    {"unit": 4, "title": "Business Services", "topics": [
                        "Business services: meaning and types",
                        "Banking: account types — savings, current, recurring, fixed deposit, multiple option deposit",
                        "Bank draft, bank overdraft, cash credit; e-banking and digital payments",
                        "Insurance: principles (utmost good faith, insurable interest, indemnity, contribution, "
                        "subrogation, causa proxima); life, health, fire, marine",
                        "Postal services: mail, registered post, parcel, speed post, courier",
                    ]},
                    {"unit": 5, "title": "Emerging Modes of Business", "topics": [
                        "E-business: concept, scope, benefits; e-business vs traditional business",
                    ]},
                    {"unit": 6, "title": "Social Responsibility of Business and Business Ethics", "topics": [
                        "Social responsibility: concept and case for it",
                        "Responsibility towards owners, investors, consumers, employees, government, community",
                        "Business in environment protection",
                        "Business ethics: concept and elements",
                    ]},
                    {"unit": 7, "title": "Sources of Business Finance", "topics": [
                        "Business finance: concept, nature, importance",
                        "Owners' funds: equity shares, preference shares, retained earnings",
                        "Borrowed funds: debentures & bonds, loans from FIs and banks, public deposits, "
                        "trade credit, inter corporate deposits (ICD)",
                        "Owners' funds vs borrowed funds",
                    ]},
                    {"unit": 8, "title": "Small Business and Enterprises", "topics": [
                        "Entrepreneurship development: concept, characteristics, need, process",
                        "Start-up India Scheme; ways to fund a start-up; Intellectual Property Rights",
                        "Small scale enterprise as per MSMED Act 2006",
                        "Role of small business in India (special reference to rural areas)",
                        "Government schemes and agencies: NSIC and DIC (rural/backward areas)",
                    ]},
                    {"unit": 9, "title": "Internal Trade", "topics": [
                        "Internal trade: meaning, types; wholesaler and retailer services",
                        "Retail trade: itinerant and small scale fixed shop retailers",
                        "Large scale retailers: departmental stores, chain stores, mail order business",
                        "GST: concept and key features",
                    ]},
                    {"unit": 10, "title": "International Trade", "topics": [
                        "International trade: concept and benefits",
                        "Export trade: meaning and procedure",
                        "Import trade: meaning and procedure",
                        "Documents: indent, letter of credit, shipping order, shipping bills, mate's receipt (DA/DP)",
                        "World Trade Organization (WTO): meaning and objectives",
                    ]},
                ],
                "project": "Part C Project Work 20 marks — any ONE of: (1) Field Visit; (2) Case Study on a Product; "
                           "(3) Aids to Trade; (4) Import/Export Procedure; (5) Visit to a State Emporium. "
                           "Assessment: initiative 2 + creativity 2 + content/research 4 + analysis 4 + viva 8.",
                "scope_notes": [
                    "Entrepreneurship Development (Unit 8) is inside Class XI Business Studies "
                    "(Start-up India, IPR, MSMED 2006).",
                    "GST appears in Class XI Internal Trade (concept & key features).",
                ],
            },
        },
    },

    "Entrepreneurship": {
        "code": "066",
        "typology": {
            "total": 70,
            "rows": [
                {"name": "Remembering and Understanding", "marks": 20, "pct": 28.5},
                {"name": "Applying", "marks": 30, "pct": 43},
                {"name": "Analysing and Evaluating", "marks": 20, "pct": 28.5},
                {"name": "Creating", "marks": 0, "pct": 0, "note": "clubbed with Analysing/Evaluating "
                                                                  "in the official table (20+20 = 28.5% row includes Creating)"},
            ],
            "rows_note": "Official QP design: Remembering+Understanding 20 (28.5%), Applying 30 (43%), "
                         "Analysing & Evaluating + Creating 20 (28.5%); total 70.",
        },
        "classes": {
            "XII": {
                "theory": 70, "project": 30,
                "weightage": [
                    {"units": [1, 2], "marks": 30, "part": "A", "part_title": "Core Entrepreneurship"},
                    {"units": [3, 4], "marks": 20, "part": "B", "part_title": "Marketing & Growth"},
                    {"units": [5, 6], "marks": 20, "part": "C", "part_title": "Arithmetic & Finance"},
                ],
                "units": [
                    {"unit": 1, "title": "Entrepreneurial Opportunity", "topics": [
                        "Sensing entrepreneurial opportunities",
                        "Environment scanning: forces affecting business environment",
                        "Problem identification",
                        "Idea fields",
                        "Spotting trends",
                        "Creativity and innovation",
                        "Selecting the right opportunity; opportunity and market assessment",
                    ]},
                    {"unit": 2, "title": "Entrepreneurial Planning", "topics": [
                        "Forms of business organisation: sole proprietorship, partnership, company",
                        "Business plan: concept, format, importance",
                        "Components: organisational plan, operational plan, production plan, "
                        "financial plan, marketing plan, human resource plan",
                        "Public vs private company; why a private company is more desirable",
                    ]},
                    {"unit": 3, "title": "Enterprise Marketing", "topics": [
                        "Marketing and sales strategy",
                        "Branding, logo, tagline",
                        "Promotion strategy; advertising; personal selling; sales promotion; public relations",
                        "Pricing methods; channels of distribution",
                        "Marketing mix (4Ps)",
                    ]},
                    {"unit": 4, "title": "Enterprise Growth Strategies", "topics": [
                        "Franchising: concept, types, advantages & limitations for franchisor and franchisee",
                        "Mergers and acquisitions: concept, reasons, types",
                    ]},
                    {"unit": 5, "title": "Business Arithmetic", "topics": [
                        "Unit of sale, unit cost for multiple products/services",
                        "Break-even analysis for multiple products/services",
                        "Computation of working capital",
                        "Inventory control and Economic Order Quantity (EOQ)",
                        "Return on Investment (ROI) and Return on Equity (ROE)",
                    ]},
                    {"unit": 6, "title": "Resource Mobilization", "topics": [
                        "Capital market: concept",
                        "Primary market: concept, methods of issue",
                        "Angel investor: features",
                        "Venture capital: features, funding",
                    ]},
                ],
                "project": "Project Work 30 marks — TWO projects (Business Plan, Market Survey) at 10 marks each "
                           "+ 5 marks Numerical Assessment + 5 marks Viva Voce.",
                "scope_notes": [
                    "Theory paper is 70 marks (NOT 80) — typology split 20/30/20 with heavy Applying weightage (43%).",
                    "Two projects are compulsory in the session (10+10) plus numerical assessment (5) and viva (5).",
                ],
            },
            "XI": {
                "theory": 70, "project": 30,
                "weightage": [
                    {"units": [1], "marks": 15, "part": "A", "part_title": "Foundations"},
                    {"units": [2, 3, 4], "marks": 20, "part": "B", "part_title": "The Entrepreneur & Journey"},
                    {"units": [5], "marks": 15, "part": "C", "part_title": "Market"},
                    {"units": [6, 7], "marks": 20, "part": "D", "part_title": "Finance & Resources"},
                ],
                "units": [
                    {"unit": 1, "title": "Entrepreneurship: Concept and Functions", "topics": [
                        "Competencies: vision, decision making, logical/critical/analytical thinking, managing skills",
                        "Entrepreneurship: concept, functions, need",
                        "Why entrepreneurship for you; myths about entrepreneurship",
                        "Advantages and limitations of entrepreneurship",
                        "Process of entrepreneurship; entrepreneurship — the Indian scenario",
                    ]},
                    {"unit": 2, "title": "An Entrepreneur", "topics": [
                        "Why be an entrepreneur",
                        "Types of entrepreneurs",
                        "Competencies and characteristics",
                        "Entrepreneurial values, attitudes and motivation",
                        "Intrapreneur: meaning and importance",
                    ]},
                    {"unit": 3, "title": "Entrepreneurial Journey", "topics": [
                        "Idea generation",
                        "Feasibility study and opportunity assessment",
                        "Business plan: meaning, purpose, elements; execution of business plan",
                    ]},
                    {"unit": 4, "title": "Entrepreneurship as Innovation and Problem Solving", "topics": [
                        "Entrepreneurs as problem solvers",
                        "Innovations and entrepreneurial ventures — global and Indian",
                        "Role of technology: e-commerce and social media",
                        "Social entrepreneurship: concept",
                    ]},
                    {"unit": 5, "title": "Understanding the Market", "topics": [
                        "Market: concept, types",
                        "Micro and macro market environment",
                        "Market research: concept, importance, process",
                        "Marketing mix",
                    ]},
                    {"unit": 6, "title": "Business Finance and Arithmetic", "topics": [
                        "Unit of sale, unit price, unit cost — single product/service",
                        "Types of costs: start-up, variable, fixed",
                        "Break-even analysis for a single product/service",
                    ]},
                    {"unit": 7, "title": "Resource Mobilization", "topics": [
                        "Types of resources: physical, human, financial, intangible",
                        "Selection and utilization of professionals — accountants, lawyers, auditors, board members",
                    ]},
                ],
                "project": "Project Work 30 marks — TWO projects of 10 marks each + 5 marks Numerical Assessment "
                           "+ 5 marks Viva Voce. XI topics: District Industries Centre report; entrepreneurial "
                           "venture case study; field visit; Learn to Earn; state handicraft/handloom & IPR.",
                "scope_notes": [
                    "Theory paper is 70 marks (NOT 80) — typology split 20/30/20, Applying = 43%.",
                    "Project work = 30 marks total (two 10-mark projects + 5 numerical + 5 viva).",
                ],
            },
        },
    },
}

# words that carry no syllabus signal when matching a topic to a unit
_STOP = {
    "the", "and", "for", "with", "from", "that", "this", "these", "those", "into",
    "their", "paper", "question", "questions", "class", "marks", "part", "unit",
    "units", "make", "made", "generate", "create", "prepare", "practice", "sheet",
    "exam", "test", "half", "yearly", "annual", "revision", "chapter", "topic",
    "please", "banao", "banana", "assignment", "homework", "assessment", "based",
    "using", "given", "well", "only", "also", "than", "then", "when", "what",
    "which", "about", "subject", "students", "student", "paper's", "important",
    "are", "was", "has", "had", "its", "but", "can", "may", "one", "two", "not",
    "all", "any", "who", "how", "why", "out", "due", "via", "see", "way", "use",
    "new", "per", "get", "yes", "the", "and", "for", "with", "that",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def norm_subject(text: Optional[str]) -> Optional[str]:
    """Canonical subject name for free text, or None when not a known subject."""
    if not text:
        return None
    low = str(text).lower()
    if "account" in low:
        return "Accountancy"
    if "business stud" in low or low.strip() in ("bst", "बिज़नेस स्टडीज़", "बिज़नेस स्टडीज"):
        return "Business Studies"
    if "entrepreneur" in low or low.strip() == "etp" or "उद्यम" in low:
        return "Entrepreneurship"
    return None


def norm_class(text: Optional[str]) -> Optional[str]:
    """Canonical class level ('XI'/'XII') for free text, or None."""
    if not text:
        return None
    low = str(text).strip().upper().replace("CLASS", "").strip()
    low = low.replace("XII", "XII").replace("XII", "XII")
    if low in ("XII", "12", "XII "):
        return "XII"
    if low in ("XI", "11"):
        return "XI"
    m = re.search(r"\b(XII|XI|12|11)\b", low)
    if m:
        return {"12": "XII", "11": "XI"}.get(m.group(1), m.group(1))
    return None


def lookup(subject: Optional[str], cls: Optional[str]) -> Optional[Dict[str, Any]]:
    """Full syllabus record {code, theory, project, units, weightage, typology, ...}."""
    sub = norm_subject(subject)
    cl = norm_class(cls)
    if not sub or not cl:
        return None
    s = SUBJECTS.get(sub)
    if not s or cl not in s["classes"]:
        return None
    data = s["classes"][cl]
    return {
        "subject": sub,
        "code": s["code"],
        "session": SESSION,
        "class_level": cl,
        "theory": data["theory"],
        "project": data["project"],
        "units": data["units"],
        "weightage": data["weightage"],
        "typology": s["typology"],
        "scope_notes": data.get("scope_notes", []),
        "books": data.get("books", []),
    }


def unit_marks(rec: Dict[str, Any], unit_no: int) -> Optional[int]:
    """Official marks for a unit (resolves grouped weightage e.g. ETP 1+2 = 30)."""
    for w in rec["weightage"]:
        if unit_no in w["units"]:
            return w["marks"]
    return None


def _tokens(text: str) -> List[str]:
    out = []
    for t in re.findall(r"[a-z]{3,}", (text or "").lower()):
        if t not in _STOP:
            out.append(t)
    return out


def unit_for_topic(subject: Optional[str], cls: Optional[str],
                   topic: Optional[str]) -> Optional[Dict[str, Any]]:
    """Best-matching official unit for a focus topic (None = no confident match)."""
    rec = lookup(subject, cls)
    if not rec or not topic:
        return None
    toks = set(_tokens(topic))
    if not toks:
        return None
    # per-unit token sets + token document-frequency for distinctiveness
    unit_sets = []
    for u in rec["units"]:
        s = set(_tokens(u["title"]))
        for t in u["topics"]:
            s |= set(_tokens(t))
        unit_sets.append(s)
    best, best_score, best_hits = None, 0, set()
    for u, uts in zip(rec["units"], unit_sets):
        title_hits = toks & set(_tokens(u["title"]))
        hits = toks & uts
        score = 3 * len(title_hits) + min(len(hits), 6)
        if len(toks) > 1 and hits == toks:
            score += 2   # unit covers EVERY requested word (e.g. 'business plan')
        if score > best_score:
            best, best_score, best_hits = u, score, hits
    if not best or best_score == 0:
        return None
    if toks & set(_tokens(best["title"])) or len(best_hits) >= 2:
        return best
    # single body hit: accept only when that token is distinctive (≤2 units)
    tok = next(iter(best_hits))
    if sum(1 for uts in unit_sets if tok in uts) <= 2:
        return best
    return None


def scope_check(subject: Optional[str], cls: Optional[str],
                topic: Optional[str]) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """Is this topic inside the official syllabus?

    Returns (ok, detail, unit). `ok=False` means the focus topic could NOT be
    placed in the requested subject+class syllabus — the deliverable must be
    flagged honestly (C1) instead of silently pretending scope compliance.
    """
    sub = norm_subject(subject)
    if not sub:
        return True, ("subject not one of the CBSE commerce subjects with a loaded "
                      "syllabus — generic scope (declared)"), None
    if not topic:
        rec = lookup(sub, cls)
        n = len(rec["units"]) if rec else 0
        return True, (f"full-syllabus deliverable across {n} units of {sub} "
                      f"Class {norm_class(cls) or '?'} (no single focus topic)"), None
    unit = unit_for_topic(sub, cls, topic)
    if unit:
        mk = unit_marks(lookup(sub, cls), unit["unit"])
        detail = (f"topic '{topic}' maps to Unit {unit['unit']} — {unit['title']} "
                  f"({mk} marks weightage, CBSE {SESSION})")
        return True, detail, unit
    # awareness: maybe it belongs to the OTHER class of the same subject
    other = "XI" if norm_class(cls) == "XII" else "XII"
    other_unit = unit_for_topic(sub, other, topic)
    if other_unit:
        detail = (f"topic '{topic}' is NOT in Class {norm_class(cls)} {sub} syllabus — "
                  f"it belongs to Class {other} Unit {other_unit['unit']} — "
                  f"{other_unit['title']} (cross-class request, flag to user)")
        return False, detail, None
    units = lookup(sub, cls)
    titles = ", ".join(f"U{u['unit']} {u['title']}" for u in (units["units"] if units else []))
    detail = (f"topic '{topic}' could not be placed in Class {norm_class(cls)} "
              f"{sub} syllabus [{titles}] — questions may fall outside official scope (C1)")
    return False, detail, None


def blueprint(subject: Optional[str], cls: Optional[str],
              marks: int) -> List[Tuple[str, str, int, int, str]]:
    """Section blueprint (section, title, marks, count, kind) for a paper.

    80-mark papers follow the standard CBSE-style A–E structure; 70-mark
    Entrepreneurship papers get their own structure with heavier application
    content; everything else falls back to a balanced generic split.
    """
    sub = norm_subject(subject)
    if marks == 80:
        return [("A", "Multiple Choice Questions (1×15)", 15, 15, "mcq"),
                ("B", "Very Short Answer (2×5)", 10, 5, "short"),
                ("C", "Short Answer (3×5)", 15, 5, "short"),
                ("D", "Long Answer (6×5)", 30, 5, "long"),
                ("E", "Case-Based (4 + 2 + 4)", 10, 1, "case")]
    if marks == 70 and sub == "Entrepreneurship":
        # 43% Applying weightage → generous short/long application blocks
        return [("A", "Objective Type (1×10)", 10, 10, "mcq"),
                ("B", "Short Answer I (3×5)", 15, 5, "short"),
                ("C", "Short Answer II (5×3)", 15, 5, "short"),
                ("D", "Long/Application Answer (6×5)", 30, 5, "long")]
    if marks == 40:
        return [("A", "Multiple Choice Questions (1×10)", 10, 10, "mcq"),
                ("B", "Short Answer (2×5)", 10, 5, "short"),
                ("C", "Long Answer (4×5)", 20, 5, "long")]
    n_mcq = max(5, marks // 10)
    rest = marks - n_mcq
    return [("A", f"Multiple Choice Questions (1×{n_mcq})", n_mcq, n_mcq, "mcq"),
            ("B", "Short Answer", rest // 2, 5, "short"),
            ("C", "Long Answer", rest - rest // 2, 5, "long")]


def coverage_rows(subject: Optional[str], cls: Optional[str]) -> List[Dict[str, Any]]:
    """Rows for the official unit-weightage table shown in deliverables."""
    rec = lookup(subject, cls)
    if not rec:
        return []
    rows = []
    for u in rec["units"]:
        w = next((w for w in rec["weightage"] if u["unit"] in w["units"]), {})
        rows.append({"part": w.get("part", ""), "unit": u["unit"],
                     "title": u["title"], "marks": w.get("marks"),
                     "shared_with": [x for x in w.get("units", []) if x != u["unit"]]})
    return rows


def typology_text(subject: Optional[str], cls: Optional[str]) -> Optional[str]:
    """One-line official typology split, e.g. '32 (40%) · 24 (30%) · 24 (30%) / 80'."""
    rec = lookup(subject, cls)
    if not rec:
        return None
    rows = [r for r in rec["typology"]["rows"] if r["marks"] or r["pct"]]
    parts = [f"{r['name']} {r['marks']} ({r['pct']}%)" for r in rows]
    return " · ".join(parts) + f"  → total {rec['typology']['total']}"


def summary(subject: Optional[str], cls: Optional[str]) -> str:
    """Keyword-rich one-paragraph summary (memory seeding / chat display)."""
    rec = lookup(subject, cls)
    if not rec:
        return ""
    units = "; ".join(f"U{u['unit']} {u['title']} ({unit_marks(rec, u['unit'])} marks)"
                      for u in rec["units"])
    # topic keywords make the seed recall-able via content LIKE %needle%
    tops = " | ".join(f"U{u['unit']} " + ", ".join(u["topics"])
                      for u in rec["units"])
    notes = " ".join(rec["scope_notes"])
    return (f"CBSE {rec['subject']} (code {rec['code']}) Class {rec['class_level']} "
            f"syllabus {SESSION}: theory {rec['theory']} + project {rec['project']}. "
            f"Units — {units}. Paper typology: {typology_text(subject, cls)}. "
            f"Scope notes: {notes} "
            f"Topic keywords per unit: {tops}.")


def compact(subject: Optional[str], cls: Optional[str]) -> Optional[Dict[str, Any]]:
    """JSON-safe slim record for API/ctx (drops long topic lists)."""
    rec = lookup(subject, cls)
    if not rec:
        return None
    return {
        "subject": rec["subject"], "code": rec["code"], "session": rec["session"],
        "class_level": rec["class_level"], "theory": rec["theory"],
        "project": rec["project"],
        "units": [{"unit": u["unit"], "title": u["title"],
                   "marks": unit_marks(rec, u["unit"]),
                   "grouped": [x for w in rec["weightage"]
                               if u["unit"] in w["units"] and len(w["units"]) > 1
                               for x in w["units"] if x != u["unit"]],
                   "n_topics": len(u["topics"])} for u in rec["units"]],
        "typology": rec["typology"],
        "scope_notes": rec["scope_notes"],
    }


def payload() -> Dict[str, Any]:
    """Full syllabus for GET /api/syllabus (unit topics included)."""
    out: Dict[str, Any] = {"session": SESSION, "subjects": {}}
    for name, s in SUBJECTS.items():
        subj: Dict[str, Any] = {"code": s["code"], "typology": s["typology"],
                                "classes": {}}
        for cl, data in s["classes"].items():
            rec = lookup(name, cl)
            subj["classes"][cl] = {
                "theory": data["theory"], "project": data["project"],
                "weightage": data["weightage"],
                "units": data["units"],
                "typology": typology_text(name, cl),
                "scope_notes": data.get("scope_notes", []),
                "project_detail": data.get("project", ""),
                "books": data.get("books", []),
                "summary": summary(name, cl),
            }
        out["subjects"][name] = subj
    return out
