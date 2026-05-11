# 架构总览

> 一页讲清楚整个 pipeline 的数据流、组件边界、Hook 触发点。

## 模块职责

```mermaid
flowchart LR
    subgraph In[输入]
        post[posts.jsonl 一条帖子]
    end

    subgraph U[understanding/]
        an[analyzer.analyze_post]
        sc[schema.PostUnderstanding]
        an --> sc
    end

    subgraph R[retrieval/]
        rc[reddit_client]
        pe[pattern_extractor]
        rc --> pe
    end

    subgraph G[generation/]
        st[styles.py]
        gen[generator.generate_candidates]
        st --> gen
    end

    subgraph V[risk/]
        sm[state_machine]
        val[validator.validate]
        bl[blocklists/*.txt]
        bl --> val
        sm --> val
    end

    subgraph H[hooks/]
        h1[pre_generation_injection_guard]
        h2[pre_publish_safety_gate]
        h3[prompt_secret_leak_guard]
    end

    subgraph Out[输出]
        rec[recommended candidate]
        evd[evidence/sessions/*.jsonl]
    end

    post --> an
    sc --> rc
    sc --> gen
    pe --> gen
    pe -.no raw text.-> gen
    gen --> val
    val --> rec

    sc -.before_generation.-> h1
    h1 -.BLOCKED.-> stop1((stop))
    val -.before_publish_decision.-> h2
    val -.before_publish_decision.-> h3
    h2 -.BLOCKED.-> stop2((stop))
    h3 -.BLOCKED.-> stop2

    an --> evd
    pe --> evd
    gen --> evd
    val --> evd

    classDef mod fill:#E6F1FB,stroke:#185FA5,color:#042C53
    classDef hook fill:#FAEEDA,stroke:#854F0B,color:#412402
    classDef io fill:#F1EFE8,stroke:#444441,color:#2C2C2A
    classDef stop fill:#FCEBEB,stroke:#A32D2D,color:#501313

    class an,sc,rc,pe,gen,val,bl,sm,st mod
    class h1,h2,h3 hook
    class post,rec,evd io
    class stop1,stop2 stop
```

## 端到端时序

```mermaid
sequenceDiagram
    participant U as User / CLI
    participant P as pipeline.py
    participant An as understanding.analyzer
    participant Rc as retrieval.reddit_client
    participant Pe as retrieval.pattern_extractor
    participant H as hooks.registry
    participant G as generation.generator
    participant V as risk.validator
    participant L as evidence.logger

    U->>P: run --post-id X
    P->>An: analyze_post(raw)
    An->>L: log llm_call (post_understanding)
    An-->>P: PostUnderstanding
    Note over P: 若 risk == do_not_engage<br/>→ 短路，pipeline 结束

    P->>H: run("post_understanding_done")
    P->>Rc: search_high_engagement_comments(theme)
    Rc-->>P: RetrievalResult (or RetrievalUnavailable → 降级)
    P->>Pe: extract_patterns(result)
    Pe-->>P: ReferenceAnalysis (no raw text)

    P->>H: run("before_generation")
    Note over H: pre_generation_injection_guard<br/>可能 BLOCKED → 短路
    H-->>P: ok / HookBlocked

    P->>G: generate_candidates(understanding, references)
    loop each style
        G->>L: log llm_call (comment_generation)
    end
    G-->>P: CommentCandidate[]

    loop each candidate
        P->>V: validate(c, understanding, references, raw_refs)
        V->>L: log risk_validation
        V-->>P: ValidationResult
    end

    P->>H: run("before_publish_decision")
    Note over H: pre_publish_safety_gate +<br/>prompt_secret_leak_guard
    H-->>P: ok / HookBlocked

    P->>P: pick_best(validated)
    P-->>U: recommended (or None + reason)
```

## 数据契约（关键 schema）

```mermaid
classDiagram
    class PostUnderstanding {
        +SCHEMA_VERSION
        +PostFacts facts
        +PostJudgments judgments
        +ImageFacts[] image_facts
        +ImageJudgments[] image_judgments
        +RiskProfile risk
        +CommentDirection direction
    }
    class PostFacts { platform; post_id; raw_title; raw_body; has_image; engagement_metrics }
    class PostJudgments { theme; core_claim; tone; punch_points; confidence }
    class RiskProfile { flagged_buckets; sensitive_entities; overall_level; rationale }
    class CommentDirection { recommended_styles; avoid_styles; interaction_levers }

    class ReferenceAnalysis { query; selection_rationale; CommentPattern[] patterns; sample_count; confidence }
    class CommentPattern { name; description; skeleton; why_it_works; examples_count; confidence }

    class CommentCandidate { text; style; leveraged_pattern; interaction_hypothesis; why_it_could_work; self_risk_estimate; pending_review }
    class ValidationResult { CandidateState state; reasons[]; metrics }

    PostUnderstanding "1" *-- "1" PostFacts
    PostUnderstanding "1" *-- "1" PostJudgments
    PostUnderstanding "1" *-- "1" RiskProfile
    PostUnderstanding "1" *-- "1" CommentDirection
    ReferenceAnalysis "1" *-- "*" CommentPattern
    CommentCandidate "1" -- "1" ValidationResult
```

## 三个常见的"路径分支"

```mermaid
flowchart LR
    start([帖子进入])
    start --> understand[analyze_post]
    understand --> dne{risk == do_not_engage?}
    dne -->|yes| short[短路返回<br/>candidates=[]]
    dne -->|no| inject{含注入 marker<br/>且 risk=high?}
    inject -->|yes| hookblock[Hook BLOCKED<br/>candidates=[]<br/>blocked_by_hook 写明]
    inject -->|no| gen[正常 generation]
    gen --> validate[5 层校验]
    validate --> ok([recommended ✓])

    classDef happy fill:#E1F5EE,stroke:#0F6E56,color:#04342C
    classDef sad fill:#FCEBEB,stroke:#A32D2D,color:#501313
    classDef neutral fill:#F1EFE8,stroke:#444441,color:#2C2C2A

    class ok happy
    class short,hookblock sad
    class start,understand,gen,validate,dne,inject neutral
```
