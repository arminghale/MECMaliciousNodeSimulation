# Understanding Severity Score and Severity Impact

## Severity Score Formula:
```
severity = (throughput_degradation × 0.25 + 
           latency_increase × 0.20 + 
           success_drop × 0.20 + 
           deadline_drop × 0.20 + 
           failure_increase × 0.15)
```

## Component Definitions:

1. **Throughput Degradation (%)**: 
   - How much fewer requests were processed vs. expected
   - Example: `selective_service_rejection` = 85% (processed only 1819 out of 9300)

2. **Latency Increase (%)**: 
   - How much slower average processing time vs. baseline (10ms)
   - Example: `processing_delay_attack` = 144% (24.4ms vs 10ms = 144% increase)

3. **Success Rate Drop (%)**: 
   - How much success rate dropped from 100% baseline
   - Example: `mixed` = 67.7% (100% - 32.2% = 67.7% drop)

4. **Deadline Met Drop (%)**: 
   - How much deadline met rate dropped from 100% baseline
   - Example: `processing_delay_attack` = 36.1% (100% - 63.8% = 36.1% drop)

5. **Failure Rate Increase (%)**: 
   - How much failure rate increased from 0% baseline
   - Example: `request_dropping` = 34.1% (41 failed out of 120 = 34.1% rate)

## Severity Scores (from 100_10_2_2 dataset):
```
processing_delay_attack:        36.1  (high latency, deadline violations)
mixed:                          69.8  (worst - multiple attack vectors)
false_resource_reporting:        0.0  (no direct performance impact)
selective_service_rejection:    51.0  (high failure rate, low throughput)
request_dropping:               20.5  (moderate packet loss)
```

## Interpretation:
- **High severity (>50)**: Significant performance degradation
- **Medium severity (20-50)**: Noticeable impact
- **Low severity (<20)**: Minimal impact
- **Zero severity**: No measurable performance impact (but may have indirect effects)

## What Severity Score Measures:
**The DIRECT, MEASURABLE performance impact of Byzantine faults on:**
- Request processing throughput
- Response time latency
- Success/failure rates
- SLA compliance (deadline violations)

**What it DOES NOT capture:**
- Indirect effects (e.g., false reporting causing load imbalance elsewhere)
- Long-term cumulative damage
- Resource wastage
- Detection difficulty
- System trust degradation
