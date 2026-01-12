I Built a RAG System for 100,000 Documents — Here’s the Architecture
My production system crashed at 2 AM because I underestimated vector databases.
CodeOrbit
CodeOrbit

Follow
8 min read
·
Nov 2, 2025
998


23





Press enter or click to view image in full size

Ai generated Image
I was three months into building a Retrieval-Augmented Generation system for a legal tech startup when everything fell apart. We’d just onboarded our largest client — a law firm with 100,000 case documents — and the entire search infrastructure collapsed under the weight.

The error logs were brutal. Query timeouts. Memory explosions. Embeddings that took 6 hours to generate.

I spent that night rebuilding from scratch. What I learned changed how I think about RAG systems entirely, and I’m going to show you the exact architecture — with real code — that now handles 100K documents with sub-second response times.

The Problem Nobody Talks About: Scale Isn’t Linear
Most RAG tutorials show you how to index 100 PDFs and call it a day. That’s cute. It’s also completely useless for production systems.

Here’s what actually happens when you scale:

At 1,000 documents: Your naive vector search still works. Retrieval takes 200ms. You feel like a genius.

At 10,000 documents: Queries slow to 2 seconds. Your embedding costs explode. You start wondering if you made a mistake.

At 100,000 documents: Everything breaks. Queries timeout. Your vector database consumes 64GB of RAM. Your AWS bill makes you cry.

The issue isn’t just volume — it’s that RAG systems have three interconnected bottlenecks that compound exponentially: ingestion pipeline, retrieval accuracy, and generation quality. Optimize one wrong and you tank the others.

The Architecture That Actually Works
After burning through five different approaches, here’s the stack that handles 100K documents in production:

Layer 1: Intelligent Document Processing
I don’t just chunk documents blindly anymore. That’s amateur hour.

Instead, I built a semantic chunking pipeline that understands document structure. Legal briefs get chunked differently than technical manuals. Contracts preserve clause boundaries. Medical records maintain context across sections.

Here’s the actual chunking logic I use:

from typing import List, Dict
import tiktoken

class SemanticChunker:
    def __init__(self, chunk_size: int = 300, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.encoder = tiktoken.get_encoding("cl100k_base")
    
    def chunk_document(self, text: str, metadata: Dict) -> List[Dict]:
        # Detect document structure
        sections = self._detect_sections(text)
        chunks = []
        
        for section in sections:
            # Respect semantic boundaries
            if self._is_atomic_section(section):
                chunks.append(self._create_chunk(section, metadata))
            else:
                # Split large sections with overlap
                sub_chunks = self._split_with_overlap(
                    section, 
                    self.chunk_size, 
                    self.overlap
                )
                chunks.extend([
                    self._create_chunk(chunk, metadata) 
                    for chunk in sub_chunks
                ])
        
        return chunks
    
    def _split_with_overlap(self, text: str, size: int, overlap: int) -> List[str]:
        tokens = self.encoder.encode(text)
        chunks = []
        
        for i in range(0, len(tokens), size - overlap):
            chunk_tokens = tokens[i:i + size]
            chunks.append(self.encoder.decode(chunk_tokens))
        
        return chunks
    
    def _create_chunk(self, text: str, metadata: Dict) -> Dict:
        return {
            "text": text,
            "metadata": {
                **metadata,
                "chunk_size": len(self.encoder.encode(text)),
                "preview": text[:100] + "..."
            }
        }
This alone improved retrieval accuracy by 34%. Turns out context boundaries matter more than chunk size.

Layer 2: Hybrid Search Architecture
Here’s the controversial part: pure vector search is overrated.

I run a hybrid system combining three retrieval methods. Here’s how I implemented the fusion layer:

from typing import List, Tuple
import numpy as np
from qdrant_client import QdrantClient
from rank_bm25 import BM25Okapi

class HybridRetriever:
    def __init__(self, qdrant_client: QdrantClient, collection_name: str):
        self.qdrant = qdrant_client
        self.collection_name = collection_name
        self.bm25 = None  # Initialized during indexing
        
    def retrieve(self, query: str, top_k: int = 10) -> List[Dict]:
        # Get dense vector results
        query_vector = self._embed(query)
        dense_results = self.qdrant.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=top_k * 2  # Get more candidates
        )
        
        # Get sparse (BM25) results
        sparse_results = self._bm25_search(query, top_k * 2)
        
        # Reciprocal Rank Fusion
        fused_results = self._reciprocal_rank_fusion(
            dense_results, 
            sparse_results, 
            k=60
        )
        
        # Rerank with cross-encoder
        reranked = self._cross_encode_rerank(query, fused_results[:20])
        
        return reranked[:top_k]
    
    def _reciprocal_rank_fusion(
        self, 
        dense: List, 
        sparse: List, 
        k: int = 60
    ) -> List[Tuple[str, float]]:
        scores = {}
        
        # Score dense results
        for rank, result in enumerate(dense, 1):
            doc_id = result.id
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank)
        
        # Score sparse results
        for rank, (doc_id, _) in enumerate(sparse, 1):
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank)
        
        # Sort by combined score
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return ranked
    
    def _cross_encode_rerank(
        self, 
        query: str, 
        candidates: List[Tuple[str, float]]
    ) -> List[Dict]:
        from sentence_transformers import CrossEncoder
        
        model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
        
        # Get candidate texts
        texts = [self._get_document(doc_id) for doc_id, _ in candidates]
        
        # Score query-document pairs
        pairs = [[query, text] for text in texts]
        scores = model.predict(pairs)
        
        # Combine with fusion scores
        final_scores = [
            (doc_id, 0.7 * ce_score + 0.3 * fusion_score)
            for (doc_id, fusion_score), ce_score 
            in zip(candidates, scores)
        ]
        
        return sorted(final_scores, key=lambda x: x[1], reverse=True)
My retrieval metrics after implementing hybrid search:

Recall@10: 87% (up from 62%)
MRR: 0.78 (up from 0.54)
Query latency: 380ms average
Layer 3: The Vector Database Decision
I tested Pinecone, Weaviate, Qdrant, and Milvus. Here’s what I learned:

Pinecone is stupid easy but expensive at scale. At 100K documents with metadata, I was looking at $800/month.

Weaviate gave me more control but struggled with updates. Reindexing took forever.

Qdrant became my choice. Open source, stupid fast, and the quantization support cut my memory usage by 60%. Here’s my production indexing pipeline:

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
import uuid

class DocumentIndexer:
    def __init__(self, qdrant_url: str):
        self.client = QdrantClient(url=qdrant_url)
        
    def create_collection(self, collection_name: str, vector_size: int = 1536):
        self.client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=vector_size,
                distance=Distance.COSINE,
                on_disk=True  # Critical for 100K+ docs
            ),
            optimizers_config={
                "indexing_threshold": 20000,  # Optimize after 20K docs
            },
            quantization_config={
                "scalar": {
                    "type": "int8",  # 4x memory reduction
                    "quantile": 0.99,
                    "always_ram": True
                }
            }
        )
    
    def index_documents(self, documents: List[Dict], batch_size: int = 100):
        points = []
        
        for doc in documents:
            point = PointStruct(
                id=str(uuid.uuid4()),
                vector=doc["embedding"],
                payload={
                    "text": doc["text"],
                    "source": doc["source"],
                    "page": doc["page"],
                    "doc_type": doc["type"],
                    "timestamp": doc["created_at"]
                }
            )
            points.append(point)
            
            # Batch insert
            if len(points) >= batch_size:
                self.client.upsert(
                    collection_name="legal_docs",
                    points=points
                )
                points = []
        
        # Insert remaining
        if points:
            self.client.upsert(
                collection_name="legal_docs",
                points=points
            )
The killer feature? Payload indexing. I can filter by document metadata before running vector search, which is crucial when users want “contracts from 2023 mentioning arbitration.”

Layer 4: Smart Caching Strategy
This is where I clawed back 70% of my API costs.

Here’s my semantic cache implementation:

import redis
import numpy as np
from typing import Optional, Tuple, List, Dict
import time

class SemanticCache:
    def __init__(self, redis_client: redis.Redis, similarity_threshold: float = 0.95):
        self.redis = redis_client
        self.threshold = similarity_threshold
        
    def get(self, query: str, query_embedding: np.ndarray) -> Optional[Dict]:
        # Get all cached queries (in production, use a better data structure)
        cache_keys = self.redis.keys("cache:query:*")
        
        best_match = None
        highest_similarity = 0.0
        
        for key in cache_keys:
            cached_data = self.redis.hgetall(key)
            cached_embedding = np.frombuffer(
                cached_data[b'embedding'], 
                dtype=np.float32
            )
            
            # Compute similarity
            similarity = np.dot(query_embedding, cached_embedding) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(cached_embedding)
            )
            
            # Track the best match above threshold
            if similarity >= self.threshold and similarity > highest_similarity:
                highest_similarity = similarity
                best_match = {
                    "results": cached_data[b'results'].decode(),
                    "cache_hit": True,
                    "similarity": similarity
                }
        
        return best_match
    
    def set(self, query: str, query_embedding: np.ndarray, results: List[Dict], ttl: int = 3600):
        cache_key = f"cache:query:{hash(query)}"
        
        self.redis.hset(cache_key, mapping={
            "query": query,
            "embedding": query_embedding.tobytes(),
            "results": str(results),  # JSON serialize in production
            "timestamp": time.time()
        })
        
        self.redis.expire(cache_key, ttl)
Cache hit rate after two weeks: 64%. That’s thousands of dollars saved monthly.

The Generation Layer: Where Most People Screw Up
Retrieving the right documents is only half the battle. The LLM needs to actually use them correctly.

Here’s my production prompt engineering with context management:

from typing import List
import openai

class RAGGenerator:
    def __init__(self, model: str = "gpt-4-turbo-preview"):
        self.model = model
        self.max_context_tokens = 6000  # Leave room for response
        
    def generate(self, query: str, retrieved_docs: List[Dict]) -> Dict:
        # Pack context intelligently
        context = self._pack_context(retrieved_docs, self.max_context_tokens)
        
        # Build prompt
        prompt = self._build_prompt(query, context)
        
        # Generate with citations
        response = openai.ChatCompletion.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self._get_system_prompt()},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,  # Low for factual accuracy
            max_tokens=1000
        )
        
        return {
            "answer": response.choices[0].message.content,
            "sources": self._extract_citations(response.choices[0].message.content),
            "context_used": context
        }
    
    def _pack_context(self, docs: List[Dict], max_tokens: int) -> List[Dict]:
        sorted_docs = sorted(docs, key=lambda x: x['score'], reverse=True)
        packed = []
        token_count = 0
        
        for doc in sorted_docs:
            doc_tokens = len(doc['text'].split()) * 1.3  # Rough estimate
            
            if token_count + doc_tokens > max_tokens:
                break
                
            packed.append(doc)
            token_count += doc_tokens
        
        return packed
    
    def _build_prompt(self, query: str, context: List[Dict]) -> str:
        context_text = "\n\n".join([
            f"[Document {i+1}] (Source: {doc['source']}, Page: {doc['page']})\n{doc['text']}"
            for i, doc in enumerate(context)
        ])
        
        return f"""Context Documents:
{context_text}

Question: {query}

Provide a comprehensive answer based ONLY on the context above. 
Cite sources using [Document X, Page Y] format after each claim."""
    
    def _get_system_prompt(self) -> str:
        return """You are a legal document analysis assistant.

Rules:
1. Answer ONLY using information from provided context
2. Cite every claim with [Document X, Page Y]
3. If information isn't in context, say "The provided documents don't contain information about [topic]"
4. Never make assumptions or use external knowledge
5. Maintain professional, precise language"""
This cut hallucinations by 89%. Users can verify every claim because the system cites its sources.

The Metrics That Matter
After six months in production, here are the numbers that keep me employed:

Query response time: 1.2 seconds average (including LLM generation)
User satisfaction: 4.6/5 (measured through feedback)
Cost per query: $0.04 (down from $0.28 before optimization)
System uptime: 99.7%
Documents processed: 127,000 and growing
But here’s the metric that actually matters: lawyers use it daily instead of Ctrl+F. That’s the real test.

Three Mistakes I’ll Never Make Again
Mistake 1: Ignoring document preprocessing

I initially just extracted raw text from PDFs. Terrible idea. OCR errors, broken formatting, and lost tables destroyed retrieval quality. Now I use a combination of pypdf, pdfplumber, and AWS Textract for problematic documents.

Mistake 2: Over-engineering the prompt

My first prompts were 800 tokens of instructions. The LLM ignored most of it. Shorter, clearer prompts with examples work infinitely better.

Mistake 3: Not monitoring retrieval quality

I was obsessing over LLM outputs while ignoring whether the right documents were being retrieved. Here’s the monitoring code I wish I’d written from day one:

class RAGMonitor:
    def log_query(self, query: str, retrieved_docs: List[Dict], 
                  user_feedback: Optional[int] = None):
        log_entry = {
            "timestamp": time.time(),
            "query": query,
            "num_results": len(retrieved_docs),
            "top_score": retrieved_docs[0]['score'] if retrieved_docs else 0,
            "user_feedback": user_feedback,
            "latency_ms": self.measure_latency()
        }
        
        # Log to your monitoring system
        self.logger.info(json.dumps(log_entry))
        
        # Track retrieval quality metrics
        if user_feedback:
            self.update_metrics(log_entry)
When retrieval is wrong, generation quality is irrelevant.

The Roadmap: What’s Next
I’m currently testing:

Multi-vector retrieval: Generating multiple embeddings per chunk from different perspectives
Active learning: Using user feedback to fine-tune the retriever
Graph-based context: Connecting related document chunks with knowledge graphs
The goal isn’t perfection. It’s building something lawyers trust more than their own memory.

Start Small, Scale Smart
If you’re building a RAG system, here’s my advice: don’t start with 100K documents.

Start with 1,000. Get the basics right. Monitor everything. Then scale incrementally while measuring each bottleneck.

The architecture I shared handles 100K documents because I spent three months failing with smaller datasets first. Every optimization came from a real production problem, not theoretical best practices.

Your users don’t care about your vector database choice or embedding model. They care whether your system gives them the right answer faster than their alternative.

Build for that.

What’s been your biggest challenge building RAG systems? I’m curious whether these bottlenecks are universal or specific to legal tech. Drop your experience in the comments.

This article is based on a production system serving 400+ daily active users across three law firms. All performance metrics are from our monitoring dashboards, averaged over the past 30 days. Code examples are simplified from production but functionally accurate.

A Message From the Developer
Thanks for reading till the end.

And if this article inspired you, give it a few claps and follow for more RAG System stories that turn weekend ideas into real tools.9 RAG Architectures Every AI Developer Must Know: A Complete Guide with Examples
Architectures beyond Naive Rag to build reliable production AI Systems
Divy Yadav
Divy Yadav

Follow
12 min read
·
Dec 19, 2025
980


19





Your chatbot confidently told a customer your return policy is 90 days. It’s 30.It later described features your product does not even have.

That is the gap between a great demo and a real production system. Language models sound sure even when they are wrong, and in production that gets expensive fast.

This is why serious AI teams use RAG. Not because it is trendy, but because it keeps models grounded in real information.

What most people miss is that there is no single RAG. There are multiple architectures, each solving a different problem. Pick the wrong one, and you waste months.

This guide breaks down the RAG architectures that actually work in production.

Let’s start by Learning about Rag.

What Is RAG and Why Does It Actually Matter?
Press enter or click to view image in full size

Source: https://hyperight.com/7-practical-applications-of-rag-models-and-their-impact-on-society/
Before we dive into architectures, let’s get clear on what we’re talking about.

RAG optimizes language model outputs by having them reference external knowledge bases before generating responses. Instead of relying purely on what the model learned during training, RAG pulls in relevant, current information from your documents, databases, or knowledge graphs.

Here’s the process in practice.

When a user asks a question, your RAG system first retrieves relevant information from external sources based on that query.
Then it combines the original question with this retrieved context and sends everything to the language model.
The model generates a response grounded in actual, verifiable information rather than just its training data.
The Real Problems that RAG Solves
Press enter or click to view image in full size

Photo by Gemini
1. Standard RAG: Start Here
Press enter or click to view image in full size

Source: https://www.bentoml.com/blog/building-rag-with-open-source-and-custom-ai-models
Standard RAG is the “Hello World” of the ecosystem. It treats retrieval as a simple, one-shot lookup. It exists to ground a model in specific data without the overhead of fine-tuning, but it assumes your retrieval engine is perfect.

It is best suited for low-stakes environments where speed is more important than absolute factual density.

How it Works:

Chunking: Documents are split into small, digestible text segments.
Embedding: Each segment is converted into a vector and stored in a database (like Pinecone or Weaviate).
Retrieval: A user query is vectorized, and the “Top-K” most similar segments are pulled using Cosine Similarity.
Generation: These segments are fed to the LLM as “Context” to generate a grounded response.
Realistic Example: A small startup’s internal employee handbook bot. A user asks, “What is our pet policy?” and the bot retrieves the specific paragraph from the HR manual to answer.

Pros:

Sub-second latency.
Extremely low computational cost.
Simple to debug and monitor.
Cons:

Highly susceptible to “noise” (retrieving irrelevant chunks).
No ability to handle complex, multi-part questions.
Lacks self-correction if the retrieved data is wrong.
2. Conversational RAG: Adding Memory
Press enter or click to view image in full size

Source: https://humanloop.com/blog/rag-architectures
Conversational RAG solves the problem of “context blindness.” In a standard setup, if a user asks a follow-up like “How much does it cost?”, the system doesn’t know what “it” refers to. This architecture adds a stateful memory layer that re-contextualizes every turn of the chat.

How it Works:

Context Loading: The system stores the last 5–10 turns of the conversation.
Query Rewriting: An LLM takes the history + the new query to generate a “Stand-alone Query” (e.g., “What is the price of the Enterprise Plan?”).
Retrieval: This expanded query is used for the vector search.
Generation: The answer is generated using the new context.
Realistic Example: A customer support bot for a SaaS company. The user says, “I’m having trouble with my API key,” and then follows up with, “Can you reset it?” The system knows “it” means the API key.

Pros:

Provides a natural, human-like chat experience.
Prevents the user from having to repeat themselves.
Cons:

Memory Drift: Irrelevant context from 10 minutes ago can pollute the current search.
Higher token costs due to the “Query Rewriting” step.
3. Corrective RAG (CRAG): The Self-Checker

Source: https://lancedb.com/blog/implementing-corrective-rag-in-the-easiest-way-2/
CRAG is an architecture designed for high-stakes environments. It introduces a “Decision Gate” that evaluates the quality of retrieved documents before they reach the generator. If the internal search is poor, it triggers a fallback to the live web.

In internal benchmarks reported by teams deploying CRAG-style evaluators, hallucinations have been shown to drop as compared to naive baselines.

How it Works:

Retrieval: Fetch documents from your internal vector store.
Evaluation: A lightweight “Grader” model assigns a score (Correct, Ambiguous, Incorrect) to each document chunk.
Trigger Gate:
Correct: Proceed to the generator.
Incorrect: Discard the data and trigger an external API (like Google Search or Tavily).
4. Synthesis: Generate the answer using the verified internal or fresh external data.

Realistic Example: A financial advisor bot. When asked about a specific stock price that isn’t in its 2024 database, CRAG realizes the data is missing and pulls the live price from a financial news API.

Pros:

Drastically reduces hallucinations.
Bridges the gap between internal data and live, real-world facts.
Cons:

Significant latency increase (adds 2–4 seconds).
Managing external API costs and rate limits.
4. Adaptive RAG: Matching Effort to Complexity
Press enter or click to view image in full size

Source: https://www.analyticsvidhya.com/blog/2025/03/adaptive-rag-systems-with-langgraph/
Adaptive RAG is the “efficiency champion.” It recognizes that not every query requires a bazooka. It uses a router to determine the complexity of a user’s intent and chooses the cheapest, fastest path to the answer.

How it Works:

Complexity Analysis: A small classifier model routes the query.
Path A (No Retrieval): For greetings or general knowledge the LLM already knows.
Path B (Standard RAG): For simple factual lookups.
Path C (Multi-step Agent): For complex analytical questions that require searching multiple sources.
Realistic Example: A university assistant. If a student says “Hello,” it responds directly. If they ask “When is the library open?”, it does a simple search. If they ask “Compare the tuition of the CS program over the last 5 years,” it triggers a complex analysis.

Pros:

Massive cost savings by skipping unnecessary retrieval.
Optimal latency for simple queries.
Cons:

Misclassification risk: If it thinks a hard question is easy, it will fail to search.
Requires a highly reliable routing model.
5. Self-RAG: The AI That Critiques Itself

Source: https://blog.langchain.com/tag/in-the-loop/
Self-RAG is a sophisticated architecture where the model is trained to critique its own reasoning. It doesn’t just retrieve; it generates “Reflection Tokens” that serve as a real-time audit of its own output.

How it Works:

Retrieve: Standard search triggered by the model itself.
Generate with Tokens: The model generates text alongside special tokens like [IsRel] (Is this relevant?), [IsSup] (Is this claim supported?), and [IsUse] (Is this helpful?).
Self-Correction: If the model outputs a [NoSup] token, it pauses, re-retrieves, and rewrites the sentence.
Realistic Example: A legal research tool. The model writes a claim about a court case, realizes the retrieved document doesn’t actually support that claim, and automatically searches for a different precedent.

Pros:

Highest level of factual “groundedness.”
Built-in transparency for the reasoning process.
Cons:

Requires specialized, fine-tuned models (e.g., Self-RAG Llama).
Extremely high computational overhead.
6. Fusion RAG: Multiple Angles, Better Results
Press enter or click to view image in full size

Source: https://bhavishyapandit9.substack.com/p/25-types-of-rag-part-1
Fusion RAG addresses the “Ambiguity Problem.” Most users are bad at searching. Fusion RAG takes a single query and looks at it from multiple angles to ensure high recall.

How it Works:

Query Expansion: Generate 3–5 variations of the user’s question.
Parallel Retrieval: Search for all variations across the vector DB.
Reciprocal Rank Fusion (RRF): Use a mathematical formula to re-rank the results:
Final Ranking: Documents that appear high in multiple searches are boosted to the top.
Realistic Example: A medical researcher searching for “treatments for insomnia.” Fusion RAG also searches for “sleep disorder medications,” “non-pharmacological insomnia therapy,” and “CBT-I protocols” to ensure no relevant study is missed.

Pros:

Exceptional recall (finds documents a single query would miss).
Robust to poor user phrasing.
Cons:

Multiplies search costs (3x-5x).
Higher latency due to re-ranking calculations.
7. HyDE: Generate the Answer, Then Find Similar Docs
Press enter or click to view image in full size

Source: https://mlpills.substack.com/p/issue-85-advanced-retrieval-strategies
HyDE is a counter-intuitive but brilliant pattern. It recognizes that “Questions” and “Answers” are semantically different. It creates a bridge between them by generating a “fake” answer first.

How it Works:

Hypothesize: The LLM writes a fake (hypothetical) answer to the query.
Embedding: The fake answer is vectorized.
Retrieval: Use that vector to find real documents that look like the fake answer.
Generation: Use the real docs to write the final response.
Realistic Example: A user asks a vague question like “That one law about digital privacy in California.” HyDE writes a fake summary of CCPA, uses that to find the actual CCPA legal text, and provides the answer.

Pros:

Dramatically improves retrieval for conceptual or vague queries.
No complex “agent” logic required.
Cons:

Bias Risk: If the “fake answer” is fundamentally wrong, the search will be misled.
Inefficient for simple factual lookups (e.g., “What is 2+2?”).
8. Agentic RAG: Orchestrating Specialists
Press enter or click to view image in full size

Source: https://bhavishyapandit9.substack.com/p/25-types-of-rag-part-1
Instead of blindly fetching documents, it introduces an autonomous agent that plans, reasons, and decides how and where to retrieve information before generating an answer.

It treats information retrieval like research, not a lookup.

How it Works:

Analyze:
The agent first interprets the user query and determines whether it is simple, multi-step, ambiguous, or requires real-time data.
Plan:
It breaks the query into sub-tasks and decides a strategy.
For example, Should it do vector search first? Web search? Call an API? Ask a follow-up question?
Act:
The agent executes those steps by invoking tools such as vector databases, web search, internal APIs, or calculators.
Iterate:
Based on intermediate results, the agent may refine queries, fetch more data, or validate sources.
Generate:
Once sufficient evidence is gathered, the LLM produces a grounded, context-aware final response.
Realistic Example:

A user asks:
“Is it safe for a fintech app to use LLMs for loan approvals under Indian regulations?”

Agentic RAG might:

Detect this is a regulatory + policy + risk question
Search RBI guidelines via web tools
Retrieve internal compliance documents
Cross-check recent regulatory updates
Synthesize a structured answer with citations and caveats
A traditional RAG would likely just retrieve semantically similar documents and answer once.

Pros:

Handles complex, multi-part, and ambiguous queries
Reduces hallucinations through verification and iteration
Can access real-time and external data sources
More adaptable to changing contexts and requirements
Cons:

Higher latency due to multi-step execution
More expensive to run than simple RAG
Requires careful tool and agent orchestration
Overkill for straightforward factual queries
9. GraphRAG: The Relationship Reasoner
Press enter or click to view image in full size

Source: https://rabiloo.com/blog/graph-rag-the-upgrade-that-traditional-rag-needed
While all previous architectures retrieve documents based on semantic similarity, GraphRAG retrieves entities and the explicit relationships between them.

Instead of asking “what text looks similar,” it asks “what is connected, and how?”

How it Works:

Graph Construction:
Knowledge is modeled as a graph where nodes are entities (people, organizations, concepts, events) and edges are relationships (affects, depends_on, funded_by, regulated_by).
Query Parsing:
The user query is analyzed to identify key entities and relationship types, not just keywords.
Graph Traversal:
The system traverses the graph to find meaningful paths that connect the entities across multiple hops.
Optional Hybrid Retrieval:
Vector search is often used alongside the graph to ground entities in unstructured text.
Generation:
The LLM converts the discovered relationship paths into a structured, explainable answer.
Realistic Example:

Query:
“How do Fed interest rate decisions affect tech startup valuations?”

GraphRAG traversal:

Federal Reserve → rate_decision → increased rates
Increased rates → affects → VC capital availability
Reduced VC availability → impacts → early-stage valuations
Tech startups → funded_by → venture capital
The answer emerges from the relationship chain, not document similarity.

Why It’s Different:

Vector RAG:
“What documents are similar to my query?”

GraphRAG:
“What entities matter, and how do they influence each other?”

This makes GraphRAG far stronger for causal, multi-hop, and deterministic reasoning.

Systems combining GraphRAG with structured taxonomies have achieved accuracy close to 99% in deterministic search tasks.

Pros:

Excellent at cause-and-effect reasoning
Highly explainable outputs due to explicit relationships
Strong performance in structured and rule-heavy domains
Reduces false positives caused by semantic similarity
Cons:

High upfront cost to build and maintain knowledge graphs
Graph construction can be computationally expensive
Harder to evolve as domains change
Overkill for open-ended or conversational queries
How to Actually Choose (The Decision Framework)
Press enter or click to view image in full size

Photo by Gemini
Step 1: Start with Standard RAG
Seriously. Unless you have specific proof it won’t work, start here. Standard RAG forces you to nail fundamentals:

Quality document chunking
Good embedding models
Proper evaluation
Monitoring
If Standard RAG doesn’t work well, complexity won’t save you. You’ll just have a complicated system that still sucks.

Step 2: Add Memory Only If Needed
Users asking follow-up questions? Add Conversational RAG. Otherwise, skip it.

Step 3: Match Architecture to Your Actual Problem
Look at real queries, not ideal ones:

Queries are similar and straightforward? Stay with Standard RAG.
Complexity varies wildly? Add Adaptive routing.
Accuracy is life-or-death? Use Corrective RAG despite cost. Healthcare RAG systems show 15% reductions in diagnostic errors.
Open-ended research? Self-RAG or Agentic RAG.
Ambiguous terminology? Fusion RAG.
Rich relational data? GraphRAG if you can afford graph construction.
Step 4: Consider Your Constraints
Tight budget? Standard RAG, optimize retrieval. Avoid Self-RAG and Agentic RAG.

Speed critical? Standard or Adaptive. DoorDash hit 2.5 second response latency for voice, but chat needs under 1 second.

Accuracy critical? Corrective or GraphRAG despite costs.

Step 5: Blend Architectures
Production systems combine approaches:

Standard + Corrective: Fast standard retrieval, corrective fallback for low confidence. 95% fast, 5% verified.
Adaptive + GraphRAG: Simple queries use vectors, complex ones use graphs.
Fusion + Conversational: Query variations with memory.
Hybrid search combining dense embeddings with sparse methods like BM25 is nearly standard for semantic meaning plus exact matches.

Simple Analogy
Think of an LLM as a smart employee with a great brain but a terrible memory.

Standard RAG is like giving them a file cabinet. They pull one folder, read it, and answer.
Conversational RAG is the same employee taking notes during the meeting so they do not ask the same questions again.
Corrective RAG adds a senior reviewer who checks, “Do we actually have proof for this?” before the answer goes out.
Adaptive RAG is a manager deciding effort level. Quick reply for easy questions, full research for hard ones.
Self-RAG is the employee thinking out loud, stopping mid-sentence to look things up when unsure.
Fusion RAG is asking five coworkers the same question in different ways and trusting what they agree on.
HyDE is the employee drafting an ideal answer first, then searching for documents that match that explanation.
Agentic RAG is a team of specialists. Legal, finance, and ops each answer their part, then someone stitches it together.
GraphRAG is using a whiteboard of relationships instead of documents. Who affects whom, and how.How I Built a RAG Chatbot in 45 Minutes (No Coding Required)
Paweł Huryn
Paweł Huryn

Follow
8 min read
·
Dec 19, 2025
10






Press enter or click to view image in full size

No coding required.

Just me, a few free tools, and 45 minutes to understand how RAG actually works by building it.

This isn’t another theoretical explainer. This is the practical guide I wish I’d had when I started learning AI product management. The one that shows you exactly what to do instead of just explaining concepts.

By the end, you’ll have a working RAG chatbot. Something real you can demo. Something that proves you understand the technology. Something worth putting in your AI PM portfolio.

What RAG Actually Means
RAG stands for Retrieval Augmented Generation.

Break that down: You retrieve relevant information from a data source, then augment the LLM’s generation with that information.

Most people think RAG equals vector databases. That’s wrong. “RAG isn’t just about vector stores. It might involve retrieval from any data source like Google Drive, SQL, or text files.”

The point is giving the model access to information it doesn’t have in its training data. Vector databases are one way. But you could retrieve from APIs, databases, file systems, or anything else.

For this tutorial, we’ll use vector databases because they’re the most common pattern. But remember the concept is broader.

Why This Matters for AI PMs
Every AI product manager needs to understand RAG deeply.

Not just conceptually. Actually understand how it works. Where it breaks. What makes it reliable versus unreliable. The tradeoffs between different approaches.

You can’t make good product decisions about RAG systems if you’ve never built one. You can’t evaluate engineering proposals. You can’t debug why quality is bad. You can’t make informed tradeoffs.

Building a simple version yourself creates intuition. You see where latency comes from. You understand why chunk size matters. You experience the difference between good and bad retrieval.

That intuition is what separates PMs who can actually ship AI products from those who just talk about them.

Step 1: Generate Embeddings (The Foundation)
The data isn’t stored in its original format.

Instead, it’s split into chunks. Each chunk becomes a multi-dimensional vector (an embedding). Those vectors get stored in a vector database.

Here’s why: LLMs can’t process your entire knowledge base at once. Context windows have limits. So you need to retrieve only the relevant parts for each query.

Embeddings let you do that. They capture semantic meaning in a way that makes similar content cluster together in vector space. When a user asks a question, you convert it to an embedding and find the closest matches.

Chunk size matters more than you think. Too small and you lose context. Too large and retrieval gets noisy. For most use cases, 500–1000 characters works well.

You’re not just storing text. You’re creating a searchable semantic index. The chunking strategy affects everything downstream. Quality. Relevance. Latency.

This is a product decision, not just a technical one. Different chunk sizes work better for different content types. Documentation needs different chunking than conversational data. Code needs different chunking than prose.

Step 2: Handle Retrieval, Generation, and UI
Users interact with an interface. In this case, I used Lovable for the UI. No coding required. Just describe what you want and iterate.

When someone asks a question, here’s what happens:

First, the question gets converted to an embedding. Same model that created the document embeddings. This ensures they’re in the same vector space.

Second, you search the vector database for similar embeddings. Retrieve the top K most relevant chunks. Usually K is 3–10 depending on your context window and quality needs.

Third, you send both the original question and the retrieved chunks to the LLM. The prompt might look like: “Based on this context: [retrieved chunks], answer this question: [user question].”

Fourth, the LLM generates an answer using the retrieved information as grounding. It can cite sources. It has specific information instead of just its training data.

That’s vanilla RAG. “The simplest possible implementation.”

It works. Most production RAG systems use some version of this pattern. But there are improvements worth knowing about.

Beyond Vanilla: Adaptive and Hybrid RAG
In practice, vanilla RAG isn’t always enough.

Adaptive RAG dynamically selects or modifies the retrieval strategy based on the request. Maybe some queries need semantic search. Others need keyword search. Some need both.

The system decides which approach fits the query. Should we retrieve from the vector database? Or should we call an API? Or should we search multiple sources and combine results?

This adds complexity but improves quality for diverse query types.

Hybrid RAG combines multiple retrieval approaches systematically. Keyword search plus semantic search. Multiple embedding models. Different data sources merged together.

Each approach has strengths and weaknesses. Keyword search is precise but misses semantic matches. Semantic search captures meaning but can return irrelevant results. Combining them balances the tradeoffs.

These aren’t just technical patterns. They’re product decisions. More complex retrieval costs more compute and adds latency. You’re trading quality for speed and cost.

Understanding these tradeoffs lets you make informed decisions. When is vanilla RAG enough? When do you need adaptive? When is hybrid worth the complexity?

Step 3: Evaluate RAG (The Part Everyone Skips)
Building RAG is easy. Building RAG that works reliably is hard.

“RAG systems have two distinct components that require different evaluation approaches: retrieval and generation.”

Most teams skip evaluation entirely. They build a RAG system, try a few queries manually, and call it done. Then they’re surprised when quality is inconsistent in production.

Traditional retrieval metrics like Recall@k, Precision@k, or MRR tell you whether you’re retrieving the right chunks. But they don’t tell you if the final answer is good.

Jason Liu’s framework “There Are Only 6 RAG Evals” makes this clearer. RAG systems have three core components: Question (Q), Context ©, and Answer (A).

You need to evaluate each combination:

Q→C: Does retrieval return relevant context?
C→A: Does generation use context correctly?
Q→A: Is the final answer actually correct?
Q→C→A: Does the full pipeline work end-to-end?
This systematic approach catches failures that spot-checking misses. Context might be relevant but generation ignores it. Or generation uses context well but retrieval returns the wrong chunks.

Error analysis becomes critical. You can’t fix what you can’t measure. You can’t measure what you don’t categorize.

The Tech Stack That Works (And Costs Almost Nothing)
You can build this virtually for free.

UI: Lovable (free version is enough). Describe the interface you want. Iterate until it works. Deploy it.

Orchestration: n8n (trial or free self-hosted edition). Connects all the pieces. Handles the workflow from query to response.

LLM: GPT-4o-mini by OpenAI (less than $2 for hundreds of requests). Fast, cheap, good enough for most use cases.

Embedding model: text-embedding-3-small. OpenAI’s smallest embedding model. Cheap and effective for most use cases.

Vector database: Pinecone (free tier). Stores embeddings. Handles similarity search. Just works.

Document source: Google Drive. Pull documents, chunk them, embed them, store them.

Total cost for learning: essentially free. Maybe a few dollars if you test extensively. But you’re learning by doing, not by spending.

The free tiers are generous enough to build real prototypes. You won’t hit limits unless you’re serving actual users at scale.

What You’ll Learn by Building
Theory is fine. Building is better.

When you actually build a RAG system, you learn things documentation doesn’t teach:

Chunking affects everything. Too small and answers lack context. Too large and retrieval gets noisy. You need to experiment to find the sweet spot for your content.

Retrieval quality determines generation quality. The LLM can only work with what you give it. If retrieval returns irrelevant chunks, generation will struggle no matter how good the model is.

Context window limits force tradeoffs. You can’t just retrieve everything. You need to balance between giving enough context and staying within limits.

Latency comes from multiple sources. Embedding the query. Searching the vector database. LLM generation. Each adds milliseconds or seconds. Product decisions affect user experience.

Evaluation is harder than building. Getting something to work is easy. Getting it to work reliably across diverse queries is hard. You need systematic evaluation.

These lessons come from doing, not reading. Build it. Break it. Fix it. That’s how you develop AI intuition.

Common Mistakes (And How to Avoid Them)
I made all of these mistakes. You don’t have to.

Mistake 1: Ignoring chunk overlap. If you chunk without overlap, relevant information might span chunks. Use 10–20% overlap to avoid this.

Mistake 2: Retrieving too few chunks. Start with 5–10 chunks. Tune based on results. Too few and you miss context. Too many and you add noise.

Mistake 3: Not filtering retrieved results. Sometimes the top matches aren’t actually relevant. Add a similarity threshold. If nothing crosses it, tell the user you don’t have that information.

Mistake 4: Skipping source attribution. Always show users which chunks informed the answer. It builds trust and helps debug when answers are wrong.

Mistake 5: Treating evaluation as optional. If you’re not systematically measuring quality, you don’t know if your system works. Build evaluation in from the start.

Why This Works as Portfolio Material
Every AI PM needs a portfolio. This project checks all the boxes.

It demonstrates technical understanding. You’re not just talking about RAG. You built one.

It shows practical skills. You used real tools. You made tradeoffs. You evaluated quality.

It proves you can ship. This isn’t a half-finished tutorial. It’s a working chatbot you can demo.

When you’re interviewing for AI PM roles, you can walk through your decisions. Why this chunk size? How did you evaluate quality? What would you improve next?

That conversation proves you understand the technology at a product level. Not engineering-level implementation details. But the strategic tradeoffs that affect user experience and business outcomes.

The Next Steps After Building
Don’t stop at vanilla RAG.

Once you have the basic version working, iterate. Try different chunk sizes. Experiment with multiple embedding models. Add hybrid search. Implement adaptive retrieval.

Compare approaches systematically. Measure quality differences. Understand the cost and latency tradeoffs. Document what you learn.

This iterative process is exactly what AI product managers do in real work. You’re not just building features. You’re evaluating approaches and making informed tradeoffs.

Then extend it. Add more data sources. Implement better evaluation. Create a UI that handles edge cases gracefully. Make it production-quality instead of just a demo.

Each improvement teaches you something. Each iteration deepens your intuition. Each decision mirrors what you’d do in a real product role.

How This Fits Into Your Learning Path
RAG is fundamental to most AI products in production.

Customer support bots need RAG to access documentation. Sales assistants need RAG to retrieve CRM data. Research tools need RAG to find relevant papers. Internal tools need RAG to surface the right information.

Understanding RAG deeply unlocks understanding most AI products. The patterns repeat. The challenges are similar. The evaluation approaches transfer.

This project gives you hands-on experience with context engineering, which is critical for AI agents and complex AI systems. You’re learning how to give models the right information at the right time.

That’s a core AI PM skill. One you can only develop through practice.

Start Building Today
The tutorial is ready. The tools are free. The only question is whether you’ll actually do it.

Most people read about RAG and move on. They understand it conceptually. But they never build it.

That’s a mistake. The learning that matters comes from building. From making mistakes. From debugging why quality is bad. From seeing the difference between approaches.

45 minutes. That’s all it takes to go from zero to working RAG chatbot. Then you have something real. Something you can show. Something you can improve.

Learn by doing. Develop better AI intuition. Build something for your portfolio.

The complete step-by-step guide covers everything. Templates included. Demo available. No excuses left.

Stop reading about AI product management. Start building AI products.

That’s how you actually learn. That’s how you develop intuition. That’s how you prove to yourself and others that you can do this work.

The tools are ready. The guide is ready. Now it’s your turn.