# Chapter 2: Literature Review

## 2.1 Extractive Summarisation

Extractive summarisation selects salient sentences or phrases directly from the source document without generating new text. Early graph-based methods such as TextRank (Mihalcea & Tarau, 2004) model sentences as nodes in a graph, with edges weighted by lexical similarity; sentences are ranked by eigenvector centrality and the top-ranked sentences form the summary. TextRank is unsupervised, requires no labelled data, and remains a strong baseline on news corpora because journalistic writing front-loads key information.

Neural extractive approaches treat sentence selection as a sequence labelling or classification problem. SummaRuNNer (Nallapati et al., 2017) uses a recurrent encoder to score each sentence in context, jointly modelling salience, novelty, and position. BertSum (Liu & Lapata, 2019) extends this paradigm with pretrained transformer encoders, achieving state-of-the-art extractive ROUGE on CNN/DailyMail while still copying source sentences verbatim.

Extractive methods guarantee that every token in the summary appears in the source, which bounds factual inconsistency. However, they produce disjointed prose, cannot paraphrase or compress information across sentences, and often miss abstractive compressions that human editors perform. In this dissertation, TextRank is retained as an ablation comparator for the evidence retrieval stage rather than as the final output format.

## 2.2 Abstractive Summarisation

Abstractive summarisation generates novel text that may paraphrase, fuse, or compress source content. Early seq2seq models with attention (Rush et al., 2015; Hermann et al., 2015) demonstrated that encoder–decoder architectures could produce fluent summaries on news datasets, but suffered from repetition, omission of key facts, and hallucination of unsupported details.

The pointer-generator network (See et al., 2017) addressed copying and out-of-vocabulary issues by allowing the decoder to copy words directly from the source via a pointer mechanism, combined with a coverage loss to reduce repetition. Copy mechanisms and coverage remain foundational ideas, but modern systems largely supersede them with large pretrained transformers fine-tuned end-to-end.

Single-stage abstractive models encode a truncated prefix of the article and decode a summary in one pass. On CNN/DailyMail, this design is simple and fast, but the encoder input budget (typically 512–1024 tokens) forces truncation of long articles, and there is no explicit mechanism to verify that generated claims are supported by the source. These limitations motivate the two-stage, evidence-grounded pipeline proposed in this dissertation.

## 2.3 Pre-trained Transformer Models for Summarisation

Pre-trained sequence-to-sequence transformers have become the dominant paradigm for abstractive news summarisation. Three models are compared in this work:

**BART** (Lewis et al., 2020) is trained as a denoising autoencoder: text is corrupted with span masking and the model learns to reconstruct it. Fine-tuned on CNN/DailyMail, BART-large-cnn achieves approximately 21 ROUGE-2 on the test set with a 1024-token encoder limit. In this project, BART is used in two roles: a zero-shot baseline (`facebook/bart-large`) and a configurable pretrained or self-trained generator path (`facebook/bart-large-cnn` or `facebook/bart-large` as selected in configuration).

**PEGASUS** (Zhang et al., 2020) uses gap-sentence generation as a pretraining objective: sentences are removed from documents and the model learns to generate them from the remaining context. PEGASUS-cnn_dailymail is pretrained on the target domain and reports comparable ROUGE-2 (~21) with a shorter 512-token input limit. It is included as a domain-pretrained comparison baseline.

**mBART** (Liu et al., 2020) extends BART to multilingual corpora via denoising pretraining across 25 languages. While not CNN/DailyMail-specific, mBART supports the dissertation's multilingual feasibility study on Hindi XL-Sum. Its English summarisation quality is typically below domain-specific BART/PEGASUS on CNN/DailyMail but provides a pathway to low-resource languages. The implementation defaults to pretrained `facebook/mbart-large-cc25`, with optional project checkpoint usage enabled through configuration.

| Model | Pretraining objective | Max input | CNN/DM ROUGE-2 (approx.) |
| BART-large / BART-large-cnn (config-dependent in implementation) | Denoising (span corruption) | 1024 | ~21 (for BART-large-cnn fine-tuned on CNN/DM) |
| PEGASUS-cnn_dailymail | Gap-sentence generation | 512 | ~21 |
| mBART-large-cc25 | Multilingual denoising | 1024 | lower (cross-lingual) |

None of these models includes built-in factual verification or a fallback when generation confidence is low; they output a single hypothesis per forward pass.

## 2.4 Factuality Evaluation

Automatic summarisation evaluation historically relied on ROUGE (Lin, 2004), which measures n-gram overlap between system and reference summaries. ROUGE correlates with fluency and content selection but cannot detect hallucinations: a summary may score highly while stating facts absent from the source.

BERTScore (Zhang et al., 2020) measures semantic similarity using contextual embeddings and correlates better with human judgment than ROUGE, yet remains reference-based and does not verify source grounding.

Reference-free factuality metrics increasingly use Natural Language Inference (NLI). SummaC (Laban et al., 2022) frames inconsistency detection as entailment between summary sentences and source chunks, aggregating scores across multiple NLI models. NLI-based Factual Consistency Scores (FCS) provide a tractable approximation to atomic-claim verification without expensive human annotation.

Recent stress-testing work (Mujahid, Wright, & Augenstein, 2026, ACL 2026) evaluated six reference-free metrics on long-document summarisation and found that metric reliability degrades as document length increases. For short-document settings such as CNN/DailyMail—where articles typically fit within a few thousand tokens—NLI-based metrics remain among the most reliable automatic indicators of factual consistency. This finding directly supports the sentence-level NLI verifier used in Stage 3 of the proposed pipeline.

## 2.5 Retrieval-Augmented Generation for Summarisation

Retrieval-Augmented Generation (RAG) (Lewis et al., 2020) conditions a generator on retrieved evidence rather than the full document, improving grounding and reducing hallucination in knowledge-intensive tasks. For summarisation, retrieval typically selects salient sentences or passages within the encoder's token budget, effectively compressing the input while preserving information density.

Lexical retrievers such as BM25 (Robertson & Zaragoza, 2009) capture keyword overlap efficiently; dense retrievers using sentence embeddings capture semantic similarity. Hybrid scoring combines both signals and is robust to vocabulary mismatch between query and document. In single-document summarisation without an external query, self-retrieval—scoring each sentence against the article's overall information density—is a standard approach for evidence selection.

The proposed pipeline applies hybrid BM25 + sentence-embedding retrieval to select top-K sentences within BART's 1024-token budget, providing both the generator input and the evidence pool for downstream NLI verification.

## 2.6 Research Gap and Contribution

Prior work addresses individual aspects of summarisation quality—extractive faithfulness, abstractive fluency, or post-hoc factuality scoring—but no single system combines hybrid evidence retrieval, multi-candidate generation, NLI verification, and a guaranteed extractive fallback within a unified CNN/DailyMail pipeline.

The following table summarises the gap addressed by this dissertation:

| Prior work | Retrieval | Multi-candidate | NLI verification | Fallback guarantee | Ablation study |
| Lead-3 / TextRank | Extractive only | No | No | N/A | — |
| BART / PEGASUS | Truncation | Single beam | No | No | Partial |
| SummaC-style eval | — | — | Metric only | No | — |
| This dissertation | Hybrid BM25+embed | Best-of-N | Sentence NLI FCS | Yes | Systematic A/B/C |

This dissertation fills the gap by chaining four modular stages—hybrid retrieval, Best-of-N abstractive generation, sentence-level NLI verification, and preference reranking with extractive fallback—into a single pipeline evaluated against Lead-3, TextRank, and single-stage BART baselines with systematic ablations. The methodology and implementation of this pipeline are described in Chapter 4; preliminary results are reported in Chapter 5.
