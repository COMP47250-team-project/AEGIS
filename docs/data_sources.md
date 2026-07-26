# AEGIS Data Sources and References

**Module:** COMP47250 Team Software Project  
**University College Dublin × Microsoft, 2026**

All references are formatted in IEEE style. Browser API references follow the W3C/MDN documentation citation convention.

---

## Academic References

[1] F. Monrose and A. D. Rubin, "Keystroke dynamics as a biometric for authentication," *Future Generation Computer Systems*, vol. 16, no. 4, pp. 351–359, Feb. 2000. doi: 10.1016/S0167-739X(99)00059-X.

> Foundational work establishing that inter-keystroke intervals (IKI) are sufficiently distinctive to serve as a biometric identifier. Used to justify the IKI signal selection and the scoring approach of measuring deviation from a per-student baseline (Phase 2 roadmap).

[2] C. Romero, S. Ventura, P. G. Espejo, and C. Hervas, "Data mining algorithms to classify students," in *Proc. 1st Int. Conf. Educational Data Mining (EDM 2008)*, Montreal, Canada, Jun. 2008, pp. 8–17.

> Provides empirical grounding for browser-based behavioural signals (tab switching, navigation events) as indicators of off-task behaviour during computer-based assessments. Referenced in signal selection justification for tab/window blur detection.

[3] K. Raman and J. D. Santhakumaran, "Detection of academic dishonesty in online examinations using keystroke dynamics," *International Journal of Advanced Computer Science and Applications (IJACSA)*, vol. 13, no. 6, pp. 214–221, 2022. doi: 10.14569/IJACSA.2022.0130625.

> Directly addresses AI-assisted cheating in online exams using keystroke dynamics. Validates the use of IKI mean and variance as discriminating features between honest and assisted exam sessions. Used to justify the answer-timing and IKI components of the AEGIS scorer.

[4] J. Brooke, "SUS: A 'quick and dirty' usability scale," in *Usability Evaluation in Industry*, P. W. Jordan, B. Thomas, B. A. Weerdmeester, and I. L. McClelland, Eds. London, U.K.: Taylor & Francis, 1996, pp. 189–194.

> Original SUS questionnaire reference. The standard 10-item SUS form and the 0–100 scoring formula used in the AEGIS usability study (§4 of the evaluation plan) are taken directly from this source. The ≥ 68 "above average usability" interpretation follows Bangor et al. (2008).

[5] A. Bangor, P. T. Kortum, and J. T. Miller, "An empirical evaluation of the System Usability Scale," *International Journal of Human-Computer Interaction*, vol. 24, no. 6, pp. 574–594, 2008. doi: 10.1080/10447310802205776.

> Provides the interpretive scale for SUS scores (≥ 68 = above average, ≥ 80 = excellent) used to set the AEGIS usability targets. Also validates SUS as reliable for software systems with small participant samples (n ≥ 5).

---

## Browser API Documentation

[6] W3C, "Page Visibility API," W3C Recommendation, Oct. 2013. [Online]. Available: https://www.w3.org/TR/page-visibility/. [Accessed: Jul. 2026].

> Specification for the `document.visibilitychange` event and `document.visibilityState` property used in AEGIS's tab-blur signal detector (`frontend/src/telemetry/signals/tabBlur.ts`). Supported in all target browsers including mobile Safari since iOS 7.

[7] W3C, "Clipboard API and events," W3C Working Draft. [Online]. Available: https://www.w3.org/TR/clipboard-apis/. [Accessed: Jul. 2026].

> Specification for the `paste` event used in AEGIS's paste signal detector (`frontend/src/telemetry/signals/paste.ts`). AEGIS uses only the `paste` event (character count via `event.clipboardData.getData('text').length`) and never accesses clipboard content directly, consistent with the API's privacy model.

[8] MDN Web Docs, "KeyboardEvent," Mozilla Developer Network. [Online]. Available: https://developer.mozilla.org/en-US/docs/Web/API/KeyboardEvent. [Accessed: Jul. 2026].

> Reference for the `keydown` event and `KeyboardEvent.timeStamp` property used in AEGIS's IKI and first-keypress signal detectors. AEGIS captures only `timeStamp` (milliseconds since page load) and never reads `KeyboardEvent.key` or `KeyboardEvent.code`, consistent with GDPR data minimisation.

---

## Azure Service Documentation

[9] Microsoft, "Azure Service Bus documentation," Microsoft Azure Docs, 2024. [Online]. Available: https://learn.microsoft.com/en-us/azure/service-bus-messaging/. [Accessed: Jul. 2026].

> Reference for Azure Service Bus Standard tier used in AEGIS for asynchronous score job dispatch (`app/services/scoring/dispatch.py`) and KEDA-based autoscaling of the scorer worker on Azure Container Apps. SDK version: `azure-servicebus>=7.12` (see `backend/pyproject.toml`).

---

## Typing Speed Baseline Reference

[10] Dhakal, V., Feit, A. M., Kristensson, P. O., and Oulasvirta, A., "Observations on typing from 136 million keystrokes," in *Proc. CHI Conf. on Human Factors in Computing Systems (CHI 2018)*, Montreal, Canada, Apr. 2018. doi: 10.1145/3173574.3174220.

> Large-scale empirical study of typing speed across 168,000 participants. Reports a median inter-keystroke interval of approximately 175ms for proficient typists, with significant individual variation. Used to inform the 400ms global IKI reference baseline used in the AEGIS scorer (`app/services/scoring/components/iki.py`), chosen as an upper boundary of normal typing rhythm rather than a median, to minimise false positives for fast typists. Per-student baseline calibration (Phase 2) will replace this global reference.
