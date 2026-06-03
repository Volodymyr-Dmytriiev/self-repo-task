# QUICK REFERENCE — Во время звонка

## 🔢 CRITICAL NUMBERS

| Параметр | Значение |
|----------|----------|
| **Volume** | 6,000 recordings/day, 4.5 min average |
| **Peak throughput** | 900 calls/hour (15/min), 09:00-13:00 |
| **Recommended VM** | NC8as_T4_v3: 8 vCPU + 1× NVIDIA T4 |
| **Nodes at peak** | 2 (cost: $3.18/hr) |
| **Min nodes (HA)** | 3 (1 per AZ) |
| **Max nodes** | 4 (autoscale limit) |
| **RTF** | 0.127 = ~34 sec per 4.5 min audio |
| **Processing time** | ~34 sec (test & confirm with load test!) |
| **Cost/hr (node)** | $0.796/hr (Sweden Central, Linux) |

---

## ✅ MAIN RECOMMENDATIONS

1. **Use AKS** (not Container Apps)
   - GPU support mature + Kubernetes officially supported by Speechmatics
   - Fall back to Container Apps only if no K8s expertise

2. **Use Webhooks** (not polling)
   - Avoids timeouts on long audio
   - Self-hosted in VNet = no public IP exposure

3. **Use GPU** (not CPU unless quota unavailable)
   - GPU: RTF 0.127, 2 nodes needed
   - CPU: RTF 0.200, 3 nodes needed (slower, higher latency)

4. **Use KEDA** (not HPA)
   - Speechmatics officially recommends for GPU workloads
   - Scales on Triton queue depth (more accurate than CPU)

5. **Use CSI Driver + Key Vault**
   - More secure than raw K8s secrets
   - License stays out of etcd

---

## ⚠️ 7 OPEN QUESTIONS (need answers!)

| # | Q | Answer | Owner |
|----|---|--------|-------|
| 1 | AKS or Container Apps? | **→ AKS recommended** | Architect |
| 2 | GPU quota available? | **→ DevOps to verify** | DevOps |
| 3 | Online or offline license? | **→ TBD by Security** | Security |
| 4 | Stereo .wav files from AQM? | **→ TBD by IT** | IT / Vendor |
| 5 | Speechmatics translation? | **→ TBD by Backend** | Backend / Architect |
| 6 | Function App plan type? | **→ TBD by DevOps** | DevOps |
| 7 | Custom Greek vocabulary? | **→ TBD by Backend** | Backend / BA |

**Action:** Ask which ones they want to resolve in this call vs. defer

---

## 🏗️ ARCHITECTURE AT A GLANCE

```
Audio File (Blob)
    ↓
[Azure Function - transcribe_blob]
    ↓ (submit async)
[AKS Namespace: speechmatics]
  ├─ sm-gpu-inference-server (Triton)
  └─ batch-asr-transcriber (ASR worker)
    ↓ (processing on GPU)
[Speechmatics webhook callback]
    ↓ (POST to)
[Azure Function - transcription_callback] ← Private Endpoint
    ↓ (writes JSON)
[Blob storage: results]
    ↓
[Queue: preprocessing]
    ↓
[Rest of pipeline: Preprocess → Analysis → Transmission → SQL → Qualco]
```

---

## 📊 DEPLOYMENT SEQUENCE (Section 7.3)

| Step | Action | Owner | Duration |
|------|--------|-------|----------|
| 1 | Pre-provision: KV secrets, Function App settings, NSG | DevOps | 1 day |
| 2 | Provision AKS node pool, mirror images, deploy K8s manifests | DevOps | 1-2 days |
| 3 | Verify connectivity Function App → Speechmatics LB | DevOps | 2-4 hrs |
| 4 | Backend merges Speechmatics code + webhook handler | Backend | varies |
| 5 | Deploy with ENABLED=false, verify Function App healthy | DevOps | 2-4 hrs |
| 6 | Set ENABLED=true, run 10 test recordings, verify end-to-end | DevOps+Backend | 4-8 hrs |
| 7 | Run full pipeline test (Preprocess → Analysis → ... → Qualco) | Backend | 4-8 hrs |
| 8 | Load test: 200 concurrent recordings, monitor scaling | DevOps | 4-8 hrs |
| 9 | Monitor production traffic for 1 week | DevOps | 7 days |
| 10 | Decommission Azure AI Speech | DevOps | 1 day |

**Estimated timeline:** 6-8 weeks (if backend dev is parallel)

---

## 🛑 KEY DECISION POINTS

**If they ask about CPU fallback:**
- D16ds_v5 option exists but NOT recommended for financial calls
- Accuracy lower, downstream LLM analysis quality suffers
- Only if GPU quota absolutely unavailable

**If they ask about Node Pool HA:**
- Min 3 nodes for HA across availability zones
- ⚠️ GPU SKU may not support all 3 AZs in some regions
- Must verify: `az vm list-skus --location <region> | grep NC8as`
- If only 2 AZs support it: 2+1 distribution across zones

**If they ask about license file size:**
- license.json = full JSON from Speechmatics
- Store ENTIRE contents as Key Vault secret value
- Don't store as plain string

---

## 📋 MONITORING CHECKLIST (Section 8)

### Custom Metrics (Backend MUST instrument):
- [ ] speechmatics_job_failed
- [ ] speechmatics_job_duration_seconds
- [ ] speechmatics_status

### Built-in Metrics (automatic):
- [ ] Dead-letter queue depth
- [ ] Webhook callback HTTP 5xx
- [ ] Pod health, node status

### Alerts:
- [ ] Job failure rate > 5 in 15 min (Sev 2)
- [ ] Transcription P95 > 120s (Sev 3)
- [ ] Webhook 5xx > 3 in 5 min (Sev 1 → PagerDuty)
- [ ] Pod CrashLoopBackOff (Sev 1 → PagerDuty)

---

## 💬 IF THEY SAY...

| They say | You respond |
|----------|-------------|
| "Azure Container Apps is simpler" | Yes, but GPU support less mature. AKS is production-grade. Recommend AKS unless team has no K8s expertise. |
| "Why not just poll Speechmatics?" | Polling risks timeouts on long files + wastes resources. Webhook is async, lets Function App handle other calls. |
| "Can we use existing networking?" | Need dedicated subnet for speechmatics node pool + NSG rules Function App ↔ AKS. Callback on Private Endpoint (no public IP). |
| "What if GPU quota unavailable?" | Fall back to D16ds_v5 CPU, but requires 3 nodes (instead of 2) + higher latency. NOT recommended for financial calls. |
| "When is this production-ready?" | After: design decisions confirmed (7 open questions), implementation, load test validation, 1 week production monitoring. Timeline: 6-8 weeks. |
| "What about cost?" | ~$3.18/hr peak (scales to zero overnight). ~$1,460/month for 20 business days. Can optimize with RI if volume stable. |

---

## 🎯 YOUR ROLE IN THIS CALL

- **You are:** DevOps/Infra person who helped create this doc
- **You know:** The technical details, the open questions, the recommendations
- **You explain:** Why certain choices (AKS, GPU, webhooks, KEDA, CSI Driver)
- **You defer:** Questions outside DevOps scope (backend code, business decisions)
- **You note:** Which open questions need resolution and by whom

---

## 📞 CALL FLOW

1. **Intro (2 min):** "Document is comprehensive production guide, my role today is clarify Speechmatics DevOps specifics"
2. **Overview (3 min):** "Recommendation: AKS + GPU, 2-3 nodes, webhook pattern, 6-8 week timeline"
3. **Deep dives (30 min):** Let them ask questions, use Quick Reference above
4. **Open questions (10 min):** "Here are 7 decisions still open, which ones do we resolve today?"
5. **Next steps (5 min):** "Assign owners, schedule follow-ups, confirm timeline"

---

## 🔗 KEY SECTIONS TO REFERENCE

- **Capacity Planning:** Section 1 (load analysis + sizing)
- **Why AKS:** Section 3 (comparison table)
- **Why Webhooks:** Section 4 (architecture diagram)
- **How to deploy:** Section 7.3 (step-by-step sequence)
- **Monitoring:** Section 8 (alert rules + dashboard)
- **Decommissioning:** Section 10 (checklist)
