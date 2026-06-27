# Mid-Sem Report Changelog

## Faculty re-review updates (June 2026)

### Chapter 1
- Added **Contributions** subsection (1.2) with the four explicit dissertation contributions.
- Replaced qualitative objectives with **measurable target** metrics (ROUGE-2, NLI-FCS, fallback rate, human eval).
- Trimmed inline literature survey; added pointer to new Chapter 2.
- Renumbered Chapter 1 subsections (1.3 Literature Context, 1.4 Stated Objectives, 1.5 Objectives Met).

### Chapter 2 (new)
- Standalone **Literature Review** with sections 2.1–2.6:
  - 2.1 Extractive summarisation (TextRank, SummaRuNNer, BertSum)
  - 2.2 Abstractive summarisation (seq2seq, pointer networks, copy mechanisms)
  - 2.3 Pre-trained transformers (BART, PEGASUS, mBART)
  - 2.4 Factuality evaluation (ROUGE, BERTScore, SummaC, ACL 2026)
  - 2.5 Retrieval-augmented generation
  - 2.6 Research gap comparison table

### Chapter renumbering
- Former Chapter 2 (Architecture) → Chapter 3
- Former Chapter 3 (Methodology) → Chapter 4
- Former Chapter 4 (Results) → Chapter 5
- Former Chapter 5 (Future Work) → Chapter 6
- Former Chapter 6 (Bibliography) → Chapter 7

### Source files
- Markdown source: `documentation/chapters/chapter2_literature_review.md`
- Update script: `documentation/update_midsem_report.py`
