# Подготовка к звонку: Speechmatics Integration - DoValue CCA

**Дата:** 14 мая 2026  
**Тип звонка:** Уточнения по документу Speechmatics Production DevOps Guide  
**Основной топик:** Clarifications for Speechmatics part  
**Дополнительно:** На среду — звонок про Basic Environment

---

## 📋 КЛЮЧЕВЫЕ МОМЕНТЫ ДОКУМЕНТА

### Что рекомендуется:
- **Инфраструктура:** AKS (Kubernetes) для Speechmatics, НЕ Azure Container Apps
- **Вычислительный ресурс:** GPU Enhanced на NC8as_T4_v3 (8 vCPU + 1× NVIDIA T4)
  - На пике: 2 узла достаточно (min 3 для HA)
  - RTF: 0.127 = ~34 сек на 4.5 минут аудио
  - Cost: $3.18/hr на пике (4 узла)

- **Архитектура:** Webhook pattern (не polling)
  - Избегает timeouts на длинные файлы
  - Self-hosted в VNet = безопасность (нет публичных IP)

### Главные компоненты интеграции:
1. **Azure Function (Transcription)** — отправляет audio в Speechmatics, exit immediately
2. **AKS + Speechmatics** — 2 Kubernetes Deployments
   - `sm-gpu-inference-server` (Triton) — GPU inference
   - `batch-asr-transcriber` — ASR worker, REST API на port 8082
3. **Webhook callback** — Function App на Private Endpoint получает результаты
4. **Key Vault + Secrets CSI Driver** — безопасное управление лицензией
5. **KEDA Autoscaling** — scale по Triton queue depth, не по CPU

### Что выводится из production:
- Azure AI Speech (старая система)
- Возможно Azure Translator (если принять Speechmatics translation)

---

## ❓ ВЕРОЯТНЫЕ ВОПРОСЫ НА ЗВОНКЕ

### ГРУППА 1: ВЫБОР ИНФРАСТРУКТУРЫ

**Q1: Почему именно AKS, а не Azure Container Apps?**
- ✅ AKS: Зрелая GPU поддержка (nvidia device plugin), full HPA + cluster autoscaler, Speechmatics officially supported Kubernetes
- ❌ ACA: GPU доступна только в select regions, Speechmatics не certified, меньше контроля над scaling
- Recommendation: AKS для production (Container Apps если нет K8s expertise, но меньше гибкости)

**Q2: GPU quota — где взять?**
- Нужно подтвердить в Azure: `az vm list-skus --location swedencentral | grep NC8as_T4_v3`
- Fallback: NC4as_T4_v3 (дешевле, но half throughput, нужно 4+ узлов) или D16ds_v5 CPU (дешево, но медленнее)
- Action: DevOps должен проверить quota перед началом

**Q3: Лицензирование — онлайн или оффлайн?**
- Online: требует NAT Gateway + fixed IP для allowlisting на Speechmatics
- Offline: файл license.json в контейнере, никакого outbound трафика
- Pros/cons: Online гибче (автоматические обновления), offline безопаснее (no external calls)
- Decision: DoValue Security должен выбрать

---

### ГРУППА 2: АРХИТЕКТУРА И NETWORKING

**Q4: Webhook vs Polling — почему вебхуки обязательны?**
- Polling в Azure Function = timeout risk на long audio + waste of resources (holding connection)
- Webhooks = Speechmatics calls back когда готово = Function App free to handle other recordings
- Self-hosted in VNet = callback is internal (no public internet exposure) = security win
- Callback на Private Endpoint Function App + VNet Integration

**Q5: Как Function App достучится до Speechmatics на AKS?**
- Speechmatics Service = Internal LoadBalancer (не ClusterIP!)
- Private IP в VNet, reachable from Function App subnet
- NSG rules открыты между Function App subnet ↔ AKS speechmatics subnet
- SPEECHMATICS_BASE_URL = `http://<internal-lb-ip>:8082/v2`

**Q6: Как передается лицензия в контейнеры?**
- CSI Driver + Key Vault secret: LICENSE_TOKEN env var
- Или mount /license.json file
- Оба способа поддержаны, оба secure

---

### ГРУППА 3: CAPACITY & PERFORMANCE

**Q7: На 6,000 calls/day достаточно 2-3 узлов?**
- Load analysis:
  - 600 calls/hour average (10 в минуту)
  - 900 calls/hour peak (15 в минуту, 09:00-13:00)
  - 4,050 audio-minutes/hour на пике
- NC8as_T4_v3: 2,400 audio-min/hour per node = 2 узла достаточно на пике
- Min 3 узла for HA (spread across availability zones)
- Max 4 узла (matches autoscale max)
- ✅ Recommendations: 3-4 узла в production

**Q8: Как быстро обрабатывается аудио?**
- RTF (Real-Time Factor) 0.127 = 4.5 min audio обрабатывается ~34 сек
- Но это benchmark на длинных файлах (>20 min). На 4-5 min есть batching overhead
- Load test обязателен перед production!

**Q9: Что если peak load больше чем ожидается?**
- KEDA autoscaling: target maxReplicaCount=4 для batch-asr-transcriber
- Если max replicas hit регулярно → нужно increase GPU quota или add nodes

---

### ГРУППА 4: MONITORING & ALERTING

**Q10: Какие метрики мониторить?**
- Custom metrics (backend dev должен instrument):
  - speechmatics_job_failed
  - speechmatics_job_duration_seconds (P95 > 120s = alert)
  - speechmatics_status == 'rejected'
- Built-in metrics:
  - Dead-letter queue depth
  - Webhook callback HTTP 5xx
  - Pod CrashLoopBackOff
  - GPU utilization (если DCGM Exporter развернут)

**Q11: SLA для transcription latency?**
- Документ предлагает alert на P95 > 120s (Sev 3)
- Но фактический SLA зависит от бизнес-требований (не указано в doc)
- Recommendation: clarify with ops team

---

### ГРУППА 5: МИГРАЦИЯ & DECOMMISSIONING

**Q12: Как безопасно переключиться с Azure Speech на Speechmatics?**
- Step 1: Deploy с SPEECHMATICS_ENABLED=false (Speechmatics уже в prod, но не используется)
- Step 2: Run 10 test recordings, verify webhook fires, transcripts land in results
- Step 3: Set SPEECHMATICS_ENABLED=true
- Step 4: Full end-to-end test (Preprocess → Analysis → Transmission → SQL → Qualco)
- Step 5: Load test (200 concurrent)
- Step 6: Monitor 1 week at production traffic
- Step 7: Decommission Azure AI Speech (remove Private Link, DNS, resource, KV secret)
- Action items: все в Section 7.3 (Production Deployment Sequence)

**Q13: Что с Azure Translator?**
- Может быть replaced Speechmatics native translation
- Требует evaluation: quality compare, cost analysis, latency impact
- Decision: backend dev + architect (не на DevOps)
- Если adopt → просто remove Azure Translator resource после

---

### ГРУППА 6: OPEN QUESTIONS (всё еще не решено)

| # | Question | Owner | Status |
|----|----------|-------|--------|
| 1 | AKS или Container Apps? | Lead DevOps / Architect | 🟡 OPEN |
| 2 | GPU quota NC8as_T4_v3 available? | DevOps | 🟡 OPEN |
| 3 | Online или offline лицензирование? | DoValue Security | 🟡 OPEN |
| 4 | AQM delivers stereo .wav files? | DoValue IT / AQM Vendor | 🟡 OPEN |
| 5 | Speechmatics translation replace Azure Translator? | Architect / Backend Dev | 🟡 OPEN |
| 6 | Function App hosting plan (Premium или Dedicated)? | DevOps | 🟡 OPEN |
| 7 | Custom Greek financial vocabulary before go-live? | Backend Dev / BA | 🟡 OPEN |

---

## 🎯 РЕКОМЕНДУЕМЫЙ ПОДХОД К ЗВОНКУ

### Фаза 1: Уточнение требований (первые 10 минут)
- Подтвердить что они хотят уточнить именно про Speechmatics (а не Infrastructure/Backend)
- Узнать какие части документа вызывают вопросы

### Фаза 2: Обсуждение ключевых design decisions (15 минут)
- AKS vs Container Apps → **strongly recommend AKS**
- Webhook architecture → **explain why mandatory**
- GPU sizing → **2 nodes peak, 3 min for HA**

### Фаза 3: Discuss Open Questions (15 минут)
- Какие из 7 questions они хотят решить сегодня?
- Какие нужна escalation на другие team?

### Фаза 4: Next steps & timeline (5 минут)
- Когда начинается implementation?
- Кто будет owner каждого раздела (DevOps, Backend, Infra)?

---

## 💡 TALKING POINTS

### Если спросят про стоимость:
- GPU solution: $3.18/hr на пике = можно scale to zero ночью
- CPU fallback: $2.45/hr (дешевле, но медленнее RTF 0.085 vs 0.127)
- Total: ~$73/день на пике × 20 рабочих дней = ~$1,460/month (примерно)

### Если спросят про риски:
- ✅ Risk mitigation: webhook pattern (no timeouts), internal VNet (no public exposure), KEDA (smart scaling), CSI Driver (secret security)
- ⚠️ Remaining risks: GPU quota availability, Speechmatics license terms TBD, load test validation needed

### Если спросят про timeline:
- Pre-work (confirm decisions): 1-2 недели
- Infrastructure provisioning (AKS, ACR, Key Vault): 2-3 дня
- Backend development (client + webhook handler): 2-3 недели
- Testing + load test: 1 неделя
- Production monitoring: 1 неделя
- Decommissioning Azure Speech: 1 день
- **Total: ~6-8 недель** (если параллельная разработка backend)

---

## 📝 NOTES ДЛЯ СЕБЯ

- **Документ версия:** 1.0 Draft, April 2026
- **Статус:** Production ready (but depends on 7 open questions)
- **Главное limitation:** Backend developer ДОЛЖЕН instrument код для custom metrics (otherwise alerts won't work)
- **Action after call:** Create detailed timeline + assign owners + schedule follow-up на Open Questions

