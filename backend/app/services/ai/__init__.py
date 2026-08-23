"""AI services package for AEGIS.

Three features, all feature-flagged and locally runnable:

  narrative.py   — 1A: AI Integrity Brief (metadata-only evidence summary)
  grading.py     — 1B: AI-Assisted Short-Answer Grading suggestions
  similarity.py  — 1C: Answer-Similarity / Collusion Detection via embeddings

Backend resolution order (see client.py):
  Azure OpenAI (gpt-4.1 / text-embedding-3-large)
    -> Ollama (qwen3:8b / nomic-embed-text)  [local twin]
    -> Dev stub                               [always boots, CI-safe]

Kill switch: set AI_FEATURES_ENABLED=false (or unset all Azure/Ollama vars)
to disable AI features entirely and fall back to the dev stub.
"""
