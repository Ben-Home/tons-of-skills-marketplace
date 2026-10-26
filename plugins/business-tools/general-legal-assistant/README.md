# General Legal Assistant

AI-powered contract review, risk analysis, document generation, and compliance auditing. 12 skills, 5 parallel agents.

## Skills

### Contract Analysis

| Skill | What It Does |
|-------|-------------|
| `contract-review` | **Flagship** — Full review with 5 parallel agents. Contract Safety Score (0-100), clause-by-clause analysis, prioritized recommendations. |
| `risk-analysis` | Evidence-linked review across ten issue categories, with explicit assumptions, unknowns and source-backed scenarios. |
| `contract-compare` | Clause-level version comparison with exact evidence, coverage gaps and qualified possible effects for the identified parties. |
| `plain-english` | Clause-linked explanations that preserve conditions, exceptions and ambiguity; readability metrics only when actually measured. |
| `missing-protections` | Relevant clause-topic gap review with applicability, evidence status and scoped drafting options when requested. |
| `freelancer-review` | Fourteen commercial review lenses, clause evidence and actual-work questions, with scoped worker-classification limits. |
| `negotiate` | Generates counter-proposals with replacement language and a negotiation email template. |

### Document Generation

| Skill | What It Does |
|-------|-------------|
| `nda-generator` | Confidentiality drafts with explicit disclosure direction, relationship context, term decisions and template provenance. |
| `terms-generator` | Service-specific terms drafts from confirmed features and business choices, with scoped applicability review. |
| `privacy-generator` | Privacy-notice drafts from confirmed processing facts, with a separate evidence and unresolved-questions record. |
| `agreement-generator` | Ten relationship-based drafting flows using confirmed commercial facts, proposed choices and source provenance. |

### Compliance

| Skill | What It Does |
|-------|-------------|
| `compliance-audit` | Scoped readiness review across seven lenses, with applicability questions, traceable evidence gaps and remediation actions; no compliance grade or attestation. |

## Agents

The `contract-review` skill spawns 5 specialized agents in parallel:

| Agent | Role | Weight |
|-------|------|--------|
| `legal-clauses` | Clause extraction and categorization | 20% |
| `legal-risks` | Risk scoring and threat identification | 25% |
| `legal-compliance` | Regulatory compliance verification | 20% |
| `legal-obligations` | Obligation mapping and financial exposure | 15% |
| `legal-recommendations` | Recommendations and negotiation strategy | 20% |

## Install

```bash
/plugin marketplace add jeremylongshore/claude-code-plugins
```

Or via CLI:

```bash
ccpi install legal-assistant
```

## Authoritative Sources Referenced

| Source | Authority | License |
|--------|-----------|---------|
| [CommonPaper](https://commonpaper.com/standards/) | 40+ attorneys, standard commercial contracts | CC BY 4.0 |
| [Bonterms](https://github.com/Bonterms/Cloud-Terms) | Enterprise cloud terms by practicing attorneys | CC BY 4.0 |
| [ICO Privacy Generator](https://ico.org.uk/create-your-own-privacy-notice) | UK statutory regulator (GDPR) | Crown copyright |
| [CA Attorney General](https://oag.ca.gov/privacy/ccpa) | CCPA enforcement body | Public domain |
| [FTC Compliance Guides](https://www.ftc.gov/business-guidance) | US federal regulator | Public domain |
| [SCORE / SBA](https://www.score.org) | US government-backed NDA templates | Free |
| [IRS 20-Factor Test](https://www.irs.gov/businesses/small-businesses-self-employed) | Contractor classification | Public domain |
| [W3C WCAG 2.1](https://www.w3.org/WAI/standards-guidelines/wcag/) | Accessibility standards | W3C |
| [PCI Security Standards](https://www.pcisecuritystandards.org/) | Payment security | Free reference |

## Disclaimer

This plugin provides AI-assisted legal analysis and document drafting. It does not constitute legal advice. Generated documents are drafts that should be reviewed by a qualified attorney before use. No attorney-client relationship is created by using this tool.

## License

MIT
