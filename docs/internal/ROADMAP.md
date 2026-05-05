# Session Notes (May 5, 2026 — iPhone session, recovered to roadmap)

## Pending technical work to close the paper

- **C1** — Formal Big-O complexity analysis as a dedicated subsection
  in §4 (currently only a paragraph). DP cost is O(|V| · H · B · deg)
  with H = ⌈α_budget · sp_hops⌉, deg = mean degree, B = mass buckets.
- **C2** — Complete bibliography with DOIs (currently the bibliography
  has 13 entries but several lack DOI fields). Needed for arXiv and
  for any subsequent revista submission.
- **C3** — Final Codex audit round (round 6) over the complete
  16-page paper.
- **C4** — arXiv upload. After upload create tag `v1.0-preprint` and
  update README + CITATION.cff with the arXiv ID and DOI.

## Order of operations after C1-C4

1. arXiv submit — wait 24-48h for indexing and canonical URL
2. Once arXiv ID is assigned, in the same afternoon:
   - LinkedIn post with the arXiv URL
   - Update README.md to include arXiv ID
   - Update CITATION.cff with version `v1.0-preprint` and DOI
   - Tag `v1.0-preprint` on HEAD
3. Watch the response for 2-3 weeks before deciding next moves

## Strategic decisions taken in this session

### Publication path

- Target revista: **Computer Networks (Elsevier)**, Tier 2 solid,
  realistic timeline, peer-reviewed legitimacy.
- Backup if rejected: IEEE TNSM (controller-level routing angle from
  §7.2 fits well there).
- **No conferences.** Bobby Fischer mode: arXiv + revista + silence.
- Sole author always.

### What "no conferences" buys us

- Protects sole-author status (conferences breed multi-author papers
  with diluted attribution)
- Avoids the academic-political overhead
- arXiv + GitHub + LinkedIn are sufficient for the audience that
  matters (TR/Pinecone-tier research engineers)

### Career movements (not decided yet, sequenced for later)

- **Movement A** — recolocación TR/Pinecone via direct LinkedIn
  outreach to research engineers (not recruiters). Trigger:
  immediately after LinkedIn post lands.
- **Movement B** — second paper, EMMET as a generalized framework
  for trajectory-aware planning. Trigger: only if first paper gets
  meaningful traction.
- **Movement C** — consultancy / advisory. Trigger: only if
  someone reaches out with a specific need.

### Second paper scope

- **Recommended domain: logistics** (last-mile delivery, supply
  chain). Public datasets abundant (NYC Taxi, Amazon last-mile
  benchmark). Industrial connectability strong.
- Second choice: swarm robotics. More academically prestigious but
  more experimental cost.
- **Discarded**: epidemiology (no medical credentials → reviewer
  hostility), finance (real alpha is hidden behind proprietary code).
- Structure: three case studies in a single paper, framing EMMET as
  a "trajectory-aware planning under medium-induced cost dynamics"
  framework.
- Not started yet. First paper's reception is the trigger.

### Why this is the right shape of move

Carlos doesn't want to maintain EMMET as a product or live off open
source. The paper is portfolio, not product. Once submitted to arXiv:
- The idea belongs to the world
- The timestamp protects priority
- The Sunday-afternoon physical intuition (§3.1) is the human
  signature that makes the work hard to imitate by LLM iteration
- Carlos's commitment to EMMET ends when the paper is published

## Background context (so this file is self-contained)

- Carlos works on EVA under NDA, cannot publish that work
- No formal academic credential
- Terrassa, ADHD
- EMMET is the demonstrable portfolio piece for a research engineer
  role at TR/Pinecone tier
- EVA pays the bills; EMMET is positioning
- Do not mix the two in any public communication

---

# EMMET — Pre-Submission Roadmap

Plan consolidado tras auditoría de 7 modelos externos (Codex GPT, Kimi,
Jarvis, DeepSeek, Perplexity, Gemini 1, Gemini 2, Qwen). Ataque por
tiers de prioridad. Marcado `[x]` cuando se completa.

**Objetivo:** publicación en revista de nivel medio-alto (Computer
Networks Elsevier, IEEE TNSM, Journal of Complex Networks, IFIP
Networking) tras preprint en arXiv. NO apuntamos a top-tier (SIGCOMM,
NSDI) — eso requiere escalar a N≥1000 y baseline RL implementado, fuera
de scope para esta iteración.

**Filosofía:** sin prisa. Esto es I+D no facturable, hay máquina y hay
tiempo. Mejor un paper sólido que un paper rápido.

---

## TIER 1 — Bloqueantes (sin esto no se publica)

### T1.1 — Reformular phase transition vs conectividad ER
- [ ] Citar Bollobás, Newman, Albert & Barabási
- [ ] Reescribir §6.1 explicando que ρc coincide con umbral de
  percolación ln(n)/n y que EMMET caracteriza el comportamiento del
  algoritmo POR ENCIMA y POR DEBAJO de ese umbral, no la transición
  topológica en sí
- [ ] Renombrar "phase transition" → "behavioral regime change at
  connectivity threshold" donde aplique
- [ ] Mantener la observación científica honesta: el dual-superiority
  regime ES intrínseco al algoritmo, no a la topología

**Coste estimado:** 1-2h. **Auditores:** 6/7 (Kimi, Jarvis, DeepSeek,
Perplexity, Gemini 2, Qwen).

### T1.2 — Verificar sesgo de selección en lat_delivered ✅ DONE
- [ ] Recalcular latencia condicionada al subconjunto (src,dst) que
  TODAS las estrategias entregan en cada seed
- [ ] Si Finding 2 (dual-superiority) cambia, reescribir
- [ ] Si Finding 2 se sostiene, añadir esta verificación al paper como
  defensa anticipada

**Coste:** 1-2h compute. **Auditores:** 1/7 (DeepSeek). Crítico técnico.

### T1.3 — Bajar tono físico en Abstract+Intro
- [ ] Quitar "thermal dissipation" → "TTL expiry"
- [ ] Quitar "field collapse" como afirmación fuerte → "loss of
  routable gradient"
- [ ] Suavizar abstract a 200-250 palabras, sin metáforas grandilocuentes
- [ ] Mantener metáforas en §3 (modelo) y §6 (discusión) — ahí aportan
  intuición

**Coste:** 30m-1h. **Auditores:** 5/7 (Kimi, Jarvis, DeepSeek,
Perplexity, Qwen parcial).

### T1.4 — Algorithm 1 con pseudocódigo formal
- [ ] Escribir Algorithm 1: EMMET full routing decision
- [ ] Notación matemática elegante (no markdown) para la potencial
- [ ] Subrutina separada para warm-up

**Coste:** 30m. **Auditores:** 4-5/7 (Kimi, Jarvis, Perplexity,
Gemini 2, Qwen parcial).

### T1.5 — Related work ampliado
- [ ] Añadir Ant Colony Optimization (Di Caro & Dorigo 1998)
- [ ] Añadir RL routing (Boyan & Littman 1994; trabajos modernos
  GNN-based)
- [ ] Añadir backpressure mejorado (algún paper post-Tassiulas que
  corrige latencia)
- [ ] Añadir TE moderno (MATE, B4) como contexto, no como baseline
  directo
- [ ] Diferenciar EMMET claramente vs ACO (descentralizado, sin
  feromonas globales)

**Coste:** 1-2h. **Auditores:** 6/7 (Kimi, Jarvis, DeepSeek, Perplexity,
Gemini 1, Qwen).

### T1.6 — Modelo de pérdidas explícito ✅ DONE
- [ ] Añadir subsección "Traffic and Loss Model" en §4 con regla
  exacta: drop si `load > capacity`, dinámica de `load`, decay
- [ ] Especificar: 1 paquete por step, sin colas, sin retransmisión

**Coste:** 15m. **Auditores:** 1/7 (DeepSeek).

### T1.7 — Cuantificar "near-zero" exacto ✅ DONE
- [ ] Reemplazar todas las apariciones de "near-zero" con cifra
  específica: "mean below 0.2 packets per 200-step run"
- [ ] Verificar consistencia entre abstract, secciones y conclusión

**Coste:** 5-10m. **Auditores:** 2/7 (Kimi, DeepSeek parcial).

---

## TIER 2 — Importantes (sin esto se publica peor)

### T2.1 — Análisis de complejidad Big-O
- [ ] Calcular complejidad por decisión de hop: O(deg(u) · D) donde D
  es coste de Dijkstra desde vecino a destino
- [ ] Optimización: precomputar dist(v,dst) una vez por destino
- [ ] Complejidad warm-up: O(warmup_steps · max_hops · deg)
- [ ] Memoria del snapshot: O(|E|)
- [ ] Tabla comparativa de complejidad vs SP, LASP

**Coste:** 30-45m. **Auditores:** 4/7 (Kimi, Gemini 1, Gemini 2, Qwen).

### T2.2 — Visited set ✅ DONE (Bloom-32 era artefacto, Bloom-128 honesto)
- [ ] Añadir párrafo en §6 (Discussion → Practical considerations)
- [ ] Discutir Bloom Filter en cabecera como alternativa práctica
- [ ] Mencionar que TTL bound limita el peor caso
- [ ] Honesto sobre limitación: en N=10000, lista pura no es viable

**Coste:** 30m. **Auditores:** 1/7 (Gemini 1) — pero crítico para
revisor de redes.

### T2.3 — Análisis de latencia: p95, jitter, latencia bajo congestión
- [ ] Recalcular desde raw_results: p95 y p99 de latencia por estrategia
- [ ] Calcular jitter (std de latencia inter-paquete) por estrategia
- [ ] Tabla nueva en §5 con latencia p50/p95/p99
- [ ] Mostrar latencia tabla density (no solo pérdidas)

**Coste:** 1-2h. **Auditores:** 3-4/7 (Jarvis, DeepSeek, Qwen,
parcialmente Kimi).

### T2.4 — Tests de significancia estadística
- [ ] Mann-Whitney U entre EMMET full y LASP por escenario
- [ ] Reportar p-values en tabla principal o apéndice
- [ ] Si hay escenarios donde la diferencia no es significativa (p>0.05),
  decirlo

**Coste:** 1h. **Auditores:** 1/7 (Perplexity).

### T2.5 — Análisis de sensibilidad de parámetros ✅ DONE
- [ ] Sweep de TTL_FACTOR ∈ {1, 2, 3, 5} en G(20, 0.20)
- [ ] Sweep de θ ∈ {0, 0.5, 1, 2, 5} (sensibilidad del termostato)
- [ ] Sweep de ε ∈ {0, 0.05, 0.10, 0.20, 0.30}
- [ ] Sweep de HALF_LIFE ∈ {25, 50, 100, 200, 500}
- [ ] Tabla resumen en apéndice o §5

**Coste:** 1-2h compute + 1h escritura. **Auditores:** 3/7 (DeepSeek,
Perplexity, Gemini 2).

### T2.6 — Warm-up dinámico (EWMA) en limitaciones ✅ DONE
- [ ] Discutir en §6.4 que el snapshot estático puede degradarse en
  redes no estacionarias
- [ ] Proponer EWMA como solución teórica para producción
- [ ] Mencionar como future work, no implementar

**Coste:** 15-20m. **Auditores:** 2/7 (Gemini 1, Qwen).

### T2.7 — Justificar parámetros por defecto
- [ ] Explicar en §4.6 cómo se eligieron β, γ, ε, θ
- [ ] Referenciar §5.2 (β sweep) y §T2.5 (sensibilidad) como sustento

**Coste:** 15m. **Auditores:** 2-3/7 (DeepSeek, Perplexity, Gemini 2).

### T2.8 — Cambiar terminología "adversarial audits"
- [ ] Reemplazar "adversarial code audits" por "rigorous independent
  code reviews" en todo el paper
- [ ] Mantener narrativa pero terminología estándar

**Coste:** 5m. **Auditores:** 1/7 (Gemini 1).

### T2.9 — Frase de Jarvis "not a paradigm"
- [ ] Añadir al final de la introducción:
  "EMMET is not a new routing paradigm but a robust heuristic that
  trades optimality for stability under dynamic conditions."

**Coste:** 5m. **Auditores:** 1/7 (Jarvis). Posicionamiento defensivo
contra revisor que busque hype.

### T2.10 — Referencias completas con DOIs
- [ ] Ampliar bibliografía a 15-20 entradas
- [ ] DOIs, volúmenes, páginas, año en formato consistente (IEEE)
- [ ] Verificar que cada cita en texto tenga entrada en bibliografía

**Coste:** 30-45m. **Auditores:** 1/7 (Qwen).

### T2.11 — Métricas adicionales (throughput)
- [ ] Calcular delivery ratio (delivered / attempted) por estrategia
- [ ] Throughput efectivo en función del tiempo
- [ ] Tabla complementaria en §5

**Coste:** 30-45m. **Auditores:** 1/7 (Qwen).

### T2.12 — Subsección "Implications for protocol design"
- [ ] Añadir §7 corta: cómo encajaría EMMET en SDN, IPv6, sensor
  networks
- [ ] Honesta sobre lo que falta para implementación real

**Coste:** 1h. **Auditores:** 1/7 (Kimi).

---

## TIER 3 — Solo si vamos a top-tier (DESCARTADO por consenso)

- Escalar a N=500-1000 (4-8h compute, posible)
- Implementar baseline RL real (varios días, descartado)
- Cota teórica formal de convergencia (varios días, descartado)
- Docker/artifact evaluation package (2-3h, opcional para Tier 2.5)
- Cover letter (al momento del envío)

---

## ORDEN DE EJECUCIÓN PROPUESTO

**Sesión 1: Verificaciones críticas técnicas**
1. T1.2 (sesgo selección — verifica si Finding 2 sobrevive)
2. T1.7 (cuantificar near-zero)
3. T1.6 (modelo de pérdidas explícito)

**Sesión 2: Pseudocódigo y notación matemática**
4. T1.4 (Algorithm 1)
5. T2.7 (justificar parámetros)
6. T2.8 (terminología adversarial)
7. T2.9 (frase Jarvis)

**Sesión 3: Reformular phase transition y tono**
8. T1.1 (phase transition vs conectividad)
9. T1.3 (bajar tono físico)
10. T2.6 (warm-up dinámico)

**Sesión 4: Related work y referencias**
11. T1.5 (related work ampliado)
12. T2.10 (referencias completas)

**Sesión 5: Análisis adicionales**
13. T2.1 (Big-O)
14. T2.2 (visited set overhead)
15. T2.3 (latencia p95, jitter)

**Sesión 6: Estadística y sensibilidad**
16. T2.4 (tests significancia)
17. T2.5 (sensibilidad parámetros)
18. T2.11 (throughput)

**Sesión 7: Polish final**
19. T2.12 (implications for protocol design)
20. Recompilar LaTeX, regenerar PDF
21. Pasada final de Codex/Jarvis/etc para QA

**Sesión 8: Submission**
22. arXiv submission (cs.NI primary, physics.soc-ph secondary)
23. Esperar feedback ~días/semanas
24. Revisar y submit a Computer Networks o IEEE TNSM

---

## REGISTRO DE AUDITORÍAS HASTA AHORA

| Auditor | Veredicto | Hallazgos únicos |
|---------|-----------|------------------|
| Codex GPT | aprobó tras 4 rondas de fixes | tablas inconsistentes con JSONs |
| Kimi | "1 iteración seria de subir nivel" | percolación ln(n)/n exacta |
| Jarvis | "trabajo serio publicable" | frase posicionamiento "not a paradigm" |
| DeepSeek | "publicable con refuerzos" | sesgo selección lat_delivered |
| Perplexity | "preprint técnico, journal tras pulir" | tests significancia estadística |
| Gemini 1 | "Computer Networks, IEEE Networking Letters" | visited set overhead cabecera |
| Gemini 2 | (sin venue específico) | citar Albert & Barabási percolación |
| Qwen | "Computer Networks o IEEE TNSM" | artifact evaluation, throughput |

---

## ESTADO ACTUAL DEL PAPER

- 9 páginas, LaTeX compilado a PDF
- 11 findings documentados
- 28800 simulaciones reproducibles
- 5 tablas, 7 figuras
- Repo público en GitHub con MIT license
- Sincronizado en clon Windows
- 33 commits

---

*Roadmap creado tras consenso de 7 auditores externos.
Mantener este documento actualizado: marcar `[x]` cuando se complete
cada tarea y commitear el cambio.*
