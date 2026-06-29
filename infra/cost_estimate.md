# AEGIS Azure cost estimate (AEGIS-63)

Rough **monthly** estimate for the resources in `infra/main.bicep`, West Europe,
in EUR. Figures are list-price approximations — actual cost depends on usage
(Container Apps and Log Analytics are consumption-based).

| Resource | SKU / size | Est. €/month |
|----------|-----------|-------------:|
| Container Registry | Basic | ~€4 |
| PostgreSQL Flexible Server | Standard_B1ms (1 vCore, Burstable) + 32 GiB | ~€14 |
| Service Bus | Standard namespace | ~€9 |
| Storage account | Standard_LRS (low usage) | ~€1 |
| Container Apps | backend 0.5 vCPU/1 GiB + frontend 0.25 vCPU/0.5 GiB, min-replicas 1 (after the monthly free grant) | ~€15 |
| Log Analytics workspace | PerGB2018, low ingest | ~€3 |
| **Total** | | **~€46 / month** |

✅ Within the ticket's **≤ €50/month** target.

## ⚠️ Note vs the AEGIS-21 budget alert
The AEGIS-21 budget alert is set at **€30/month**, so this stack (~€46) will
**cross that alert**. Either bump the budget to ~€60 or accept the alert as
an early-warning. (Student credits cover this comfortably short-term.)

## Biggest cost levers (if you need to trim toward €30)
- **Container Apps min-replicas 0** (scale-to-zero) — removes the always-on cost; first request after idle has a cold start.
- **Service Bus Basic** instead of Standard (~€0.05/M ops) — but Basic has no topics/sessions; fine if only the `aegis-events` queue is needed.
- **Stop/deallocate Postgres** when not demoing.

## Assumptions
- Light, demo-level traffic (a class-sized exam, not production scale).
- 32 GiB Postgres storage, 7-day backup retention, no geo-redundancy / HA.
- Prices are indicative (Azure list prices change); use `az deployment group what-if`
  + the Azure Pricing Calculator for an exact quote.
