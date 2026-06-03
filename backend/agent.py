import json
import asyncio
import uuid
from typing import AsyncGenerator, List, Dict, Any, Optional
import httpx

SYSTEM_PROMPT = """You are TASH, an expert AI research agent specialized in Single-Cell Aging Atlas Analysis. You assist bioinformaticians and researchers with:

- Single-cell RNA sequencing (scRNA-seq) data analysis workflows
- Computational tools: Scanpy, Seurat, scVI, Geneformer, scGPT
- Cell type annotation, clustering, trajectory inference, and differential expression
- Aging biology at single-cell resolution — cellular senescence, clonal hematopoiesis, tissue remodeling
- Designing pipelines and interpreting results from single-cell datasets
- Finding relevant papers from the aging and single-cell genomics literature

You are agentic: you break tasks into steps, use tools when needed, and reason step-by-step before answering. When writing code, use proper Scanpy/Python conventions with concise, runnable examples."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search for recent papers, tools, and information about single-cell analysis and aging biology",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_scanpy_analysis",
            "description": "Generate and explain a Scanpy analysis pipeline for single-cell data",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "What analysis to perform"},
                    "data_type": {"type": "string", "description": "Type of data (e.g., PBMC, brain, liver)"}
                },
                "required": ["task"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_aging_atlas",
            "description": "Query the Single-Cell Aging Atlas for gene expression across tissues and age groups",
            "parameters": {
                "type": "object",
                "properties": {
                    "gene": {"type": "string"},
                    "tissue": {"type": "string"},
                    "age_group": {"type": "string", "enum": ["young", "middle", "old", "all"]}
                },
                "required": ["gene"]
            }
        }
    }
]

MOCK_TOOL_RESULTS = {
    "web_search": lambda args: f"""Found 4 relevant results for "{args.get('query', '')}":

1. **Single-cell transcriptomic atlas of aging mouse brain** (Nature, 2024)
   Key finding: Microglia show progressive inflammatory gene upregulation with age.

2. **scGPT: Toward building a foundation model for single-cell multi-omics** (Nature Methods, 2024)
   Unified model pre-trained on 33M cells; outperforms task-specific baselines.

3. **Aging Cell Atlas v2.0** - tabula-muris-senis.czbiohub.org
   23 mouse tissues, 350k cells, young/old comparisons.

4. **Geneformer: Transfer learning enables predictions in network biology** (Nature, 2023)
   Transformer model for gene network inference using rank-value encoding.""",

    "run_scanpy_analysis": lambda args: f"""Scanpy pipeline for: {args.get('task', 'analysis')}

```python
import scanpy as sc
import pandas as pd
import matplotlib.pyplot as plt

# Load data
adata = sc.read_h5ad("data.h5ad")

# QC metrics
sc.pp.calculate_qc_metrics(adata, percent_top=None, log1p=False, inplace=True)
adata = adata[adata.obs.n_genes_by_counts > 200]
adata = adata[adata.obs.pct_counts_mt < 5]

# Normalization
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)

# Feature selection
sc.pp.highly_variable_genes(adata, min_mean=0.0125, max_mean=3, min_disp=0.5)
adata = adata[:, adata.var.highly_variable]

# Dimensionality reduction
sc.pp.pca(adata, svd_solver="arpack")
sc.pp.neighbors(adata, n_neighbors=10, n_pcs=40)
sc.tl.umap(adata)
sc.tl.leiden(adata, resolution=0.5)

# Visualize
sc.pl.umap(adata, color=["leiden", "age"], frameon=False)
```

Pipeline ready. Found {12 if 'aging' in args.get('task','').lower() else 8} highly variable genes associated with aging signatures.""",

    "query_aging_atlas": lambda args: f"""Aging Atlas query for gene: **{args.get('gene', 'N/A')}** | Tissue: {args.get('tissue', 'all')} | Age: {args.get('age_group', 'all')}

| Age Group | Mean Expression | % Cells Expressing | p-value |
|-----------|----------------|-------------------|---------|
| Young (3m) | 1.23 ± 0.41 | 34.2% | - |
| Middle (12m) | 1.89 ± 0.52 | 48.7% | 0.003 |
| Old (24m) | 2.71 ± 0.68 | 61.3% | 0.0001 |

Cell types with highest expression: Monocytes, NK cells, B cells
Trajectory: Progressive upregulation with age (r=0.87, p<0.001)"""
}

MOCK_BIOLOGY_RESPONSE = """Based on my analysis, here's what the single-cell aging literature tells us:

**Key aging signatures at single-cell resolution:**

1. **Inflammaging** - Pro-inflammatory gene modules (IL6, TNF, CXCL10) are consistently upregulated in aged immune cells across tissues.

2. **Stem cell exhaustion** - Hematopoietic stem cells show reduced quiescence markers (EPCAM, CD34) and increased senescence signals (p21, p16).

3. **Clonal hematopoiesis** - Somatic mutations in DNMT3A, TET2, and ASXL1 expand with age and correlate with myeloid bias.

4. **Cellular senescence** - Senescence-associated secretory phenotype (SASP) cells accumulate in multiple tissues, characterized by high CDKN1A, MMP3, and SERPINE1.

**Recommended analysis pipeline:**
- Use Scanpy for preprocessing + Leiden clustering
- Apply scVI for batch correction across datasets
- Use Geneformer for cell type annotation
- Run CellChat or LIANA for cell-cell communication analysis

Would you like me to generate specific code for any of these steps?"""


async def mock_stream(user_message: str) -> AsyncGenerator[str, None]:
    """Generate a realistic mock agent response with tool steps."""

    msg_lower = user_message.lower()

    tool_calls = []
    if any(w in msg_lower for w in ["search", "paper", "recent", "latest", "find", "look"]):
        tool_calls.append(("web_search", {"query": user_message[:60]}))
    if any(w in msg_lower for w in ["code", "scanpy", "pipeline", "how to", "analyze", "analysis"]):
        tool_calls.append(("run_scanpy_analysis", {"task": user_message[:60]}))
    if any(w in msg_lower for w in ["gene", "expression", "atlas", "tissue", "age"]):
        gene = next((w for w in user_message.split() if w[0].isupper() and len(w) > 2), "TP53")
        tool_calls.append(("query_aging_atlas", {"gene": gene, "tissue": "all", "age_group": "all"}))

    yield f"data: {json.dumps({'type': 'thinking', 'content': 'Analyzing your question...'})}\n\n"
    await asyncio.sleep(0.6)

    accumulated_steps = []
    for tool_name, tool_args in tool_calls:
        step_id = str(uuid.uuid4())[:8]
        yield f"data: {json.dumps({'type': 'tool_start', 'step_id': step_id, 'tool': tool_name, 'input': tool_args})}\n\n"
        await asyncio.sleep(0.8)

        result = MOCK_TOOL_RESULTS[tool_name](tool_args)
        yield f"data: {json.dumps({'type': 'tool_result', 'step_id': step_id, 'content': result})}\n\n"
        accumulated_steps.append({"id": step_id, "tool": tool_name, "input": tool_args, "output": result, "status": "done"})
        await asyncio.sleep(0.4)

    yield f"data: {json.dumps({'type': 'thinking', 'content': 'Composing response...'})}\n\n"
    await asyncio.sleep(0.5)

    final_response = MOCK_BIOLOGY_RESPONSE if not tool_calls else (
        f"Based on my {len(tool_calls)} tool search(es), here's a comprehensive answer:\n\n" + MOCK_BIOLOGY_RESPONSE
    )

    words = final_response.split(" ")
    chunk = ""
    for i, word in enumerate(words):
        chunk += word + " "
        if len(chunk) > 30 or i == len(words) - 1:
            yield f"data: {json.dumps({'type': 'text', 'content': chunk})}\n\n"
            chunk = ""
            await asyncio.sleep(0.03)

    yield f"data: {json.dumps({'type': 'done', 'tool_steps': accumulated_steps})}\n\n"


async def llm_stream(
    messages: List[Dict],
    model: str,
    base_url: str,
    api_key: str,
    tool_steps_collector: list
) -> AsyncGenerator[str, None]:
    """Stream from a real OpenAI-compatible LLM endpoint."""

    headers = {"Authorization": f"Bearer {api_key or 'ollama'}", "Content-Type": "application/json"}

    system_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages

    payload = {
        "model": model,
        "messages": system_messages,
        "tools": TOOLS,
        "stream": False,
        "temperature": 0.7,
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

            choice = data["choices"][0]
            msg = choice["message"]

            tool_calls = msg.get("tool_calls", [])

            for tc in tool_calls:
                step_id = str(uuid.uuid4())[:8]
                fn = tc["function"]
                tool_name = fn["name"]
                try:
                    args = json.loads(fn.get("arguments", "{}"))
                except Exception:
                    args = {}

                yield f"data: {json.dumps({'type': 'tool_start', 'step_id': step_id, 'tool': tool_name, 'input': args})}\n\n"
                await asyncio.sleep(0.5)

                if tool_name in MOCK_TOOL_RESULTS:
                    result = MOCK_TOOL_RESULTS[tool_name](args)
                else:
                    result = "Tool executed successfully."

                yield f"data: {json.dumps({'type': 'tool_result', 'step_id': step_id, 'content': result})}\n\n"
                tool_steps_collector.append({"id": step_id, "tool": tool_name, "input": args, "output": result, "status": "done"})
                await asyncio.sleep(0.3)

            final_content = msg.get("content") or ""

            if tool_calls and not final_content:
                tool_results_text = "\n\n".join([s["output"] for s in tool_steps_collector])
                followup_payload = {
                    "model": model,
                    "messages": system_messages + [
                        {"role": "assistant", "content": None, "tool_calls": tool_calls},
                        {"role": "tool", "tool_call_id": tool_calls[0]["id"], "content": tool_results_text}
                    ],
                    "stream": False,
                    "temperature": 0.7,
                }
                resp2 = await client.post(f"{base_url}/chat/completions", headers=headers, json=followup_payload)
                resp2.raise_for_status()
                final_content = resp2.json()["choices"][0]["message"].get("content", "")

            words = (final_content or "").split(" ")
            chunk = ""
            for i, word in enumerate(words):
                chunk += word + " "
                if len(chunk) > 40 or i == len(words) - 1:
                    yield f"data: {json.dumps({'type': 'text', 'content': chunk})}\n\n"
                    chunk = ""
                    await asyncio.sleep(0.02)

    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"


async def agent_stream(
    conversation_id: str,
    user_message: str,
    history: List[Dict],
    model: str,
    base_url: Optional[str],
    api_key: Optional[str],
) -> AsyncGenerator[str, None]:
    """Main agent streaming entry point."""

    tool_steps: list = []

    if model == "mock" or not base_url:
        async for event in mock_stream(user_message):
            yield event
        return

    messages = [{"role": m["role"], "content": m["content"]} for m in history]
    messages.append({"role": "user", "content": user_message})

    yield f"data: {json.dumps({'type': 'thinking', 'content': 'Planning approach...'})}\n\n"
    await asyncio.sleep(0.4)

    async for event in llm_stream(messages, model, base_url, api_key or "", tool_steps):
        yield event

    yield f"data: {json.dumps({'type': 'done', 'tool_steps': tool_steps})}\n\n"
