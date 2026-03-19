---
name: answer-question
description: Answer user questions using RAG knowledge base and contract registry
version: "1.0"
trigger: manual
agent: groot-chat
input: { query: string, max_sources: int }
output: { answer: string, sources: list, confidence: string }
---

# Answer Question

Search the knowledge base and contract registry for relevant context,
then generate a grounded response.

## Steps
1. Search knowledge base for documents matching `{query}`
2. Search contract registry for relevant SDKs
3. Synthesize a response using retrieved context
4. Cite sources naturally in the response
5. Indicate confidence level (grounded vs general knowledge)
