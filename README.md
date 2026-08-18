# EdgeSimPy Malicious Fault Simulation

A comprehensive simulation framework for analyzing Malicious faults in edge computing systems using EdgeSimPy.

## 📋 Overview

This project simulates and analyzes the impact of Malicious faults on edge computing infrastructures. It implements multiple fault injection strategies to evaluate how malicious or faulty edge servers degrade system performance under various attack scenarios.

### Fault Types

The simulation supports five Malicious fault scenarios:

1. **Processing Delay Attack** - Misbehaving servers artificially increase processing latency
2. **Request Dropping** - Servers silently drop incoming requests
3. **False Resource Reporting** - Servers report inflated/false resource availability
4. **Selective Service Rejection** - Servers reject requests for specific services
5. **Mixed Faults** - Combination of all four attack types simultaneously

## 🏗️ Project Structure

```
EdgeSimPy/
├── Core Simulations
│   ├── edge.py                          # FaultyEdgeServer implementation
│   ├── mini_simulation.py               # Minimal simulation with all fault types
│   ├── scaled_simulation.py             # Large-scale simulation framework
│   ├── scaled_simulation_run_batch.py   # Batch execution utility
│   └── comprehensive_analysis.py        # Full-scale analysis pipeline
│
├── Dataset Generators
│   ├── dataset_baseline.py              # Baseline (healthy) scenarios
│   ├── dataset_delay_attack.py          # Processing delay attack datasets
│   ├── dataset_false_reporting.py       # False reporting attack datasets
│   ├── dataset_request_dropping.py      # Request dropping attack datasets
│   ├── dataset_selective_rejection.py   # Selective rejection attack datasets
│   ├── dataset_mixed_faults.py          # Mixed fault scenarios
│   ├── v2_dataset.py                    # V2 dataset generation
│   └── v2_test_all_scenarios.py         # V2 comprehensive testing
│
├── Analysis & Utilities
│   ├── analysis_tools.py                # Common analysis functions
│   ├── compare_simulations.py           # Cross-scenario comparison
│   ├── test_all_scenarios.py            # Comprehensive test suite
│   └── test_suite_summary.json          # Test execution summary
│
├── Configuration
│   ├── input.json                       # Simulation parameters
│   ├── requirements.txt                 # Python dependencies
│   └── Severity.md                      # Severity score documentation
│
├── Output & Results
│   ├── Analysis/                        # Analyzed results by configuration
│   │   ├── 100_10_2-3_2-3/
│   │   ├── 100_50_2-4_2-4/
│   │   ├── 150_30_2-3_2-3/
│   │   ├── 200_20_2-3_2-3/
│   │   ├── 200_40_2-4_2-4/
│   │   ├── 250_30_2-3_2-3/
│   │   ├── 300_10_2-3_2-3/
│   │   ├── 300_50_2-4_2-4/
│   │   ├── 400_30_2-3_2-3/
│   │   └── 500_20_3-5_3-5/
│   │       └── table1_fault_summary.csv
│   │       └── table2_overall_summary.csv
│   │       └── table3_impact_severity.csv
│   ├── Compare_Analysis/                # Cross-scenario analysis
│   │   ├── comparison_summary_table.csv
│   │   └── parameter_trends.csv
│   ├── ComprehensiveAnalysis/           # Detailed metrics
│   │   ├── impact_metrics.csv
│   │   ├── server_metrics.csv
│   │   └── service_metrics.csv
│   ├── logs/                            # Simulation msgpack logs
│   │   ├── ContainerRegistry.msgpack
│   │   ├── EdgeServer.msgpack
│   │   ├── FaultyEdgeServer.msgpack
│   │   ├── NetworkSwitch.msgpack
│   │   ├── Service.msgpack
│   │   └── User.msgpack
│   └── metrics_delay_attack.json        # Sample metrics output
│
└── README.md                            # This file
```

## 🚀 Getting Started

### Installation

1. **Clone or navigate to the project directory:**
   ```bash
   cd ../MECMaliciousNodeSimulation
   ```

2. **Install dependencies:**
   ```bash
   pip install -q git+https://github.com/EdgeSimPy/EdgeSimPy.git
   ```

3. **Verify EdgeSimPy installation:**
   ```bash
   python -c "import edge_sim_py; print(edge_sim_py.__version__)"
   ```

### Quick Start

Run a minimal simulation with all fault types:
```bash
python mini_simulation.py
```

Run a scaled simulation:
```bash
python scaled_simulation.py
```

Run comprehensive analysis on all datasets:
```bash
python comprehensive_analysis.py
```

## 📊 Configuration

Edit `input.json` to customize simulation parameters:

```json
{
  "num_edge_servers": 100,
  "num_base_stations": 10,
  "misbehaving_ratio": 0.1,
  "simulation_duration": 100,
  "fault_config": {
    "processing_delay_attack": {
      "slowdown_factor": 2.0
    },
    "request_dropping": {
      "drop_probability": 0.3
    },
    "false_resource_reporting": {
      "lie_probability": 0.25,
      "inflation_factor": 1.5
    }
  }
}
```

## 📈 Analysis & Metrics

### Severity Score

Each fault scenario is evaluated using a comprehensive severity score (0-100):

**Formula:**
```
severity = (throughput_degradation × 0.25 + 
           latency_increase × 0.20 + 
           success_drop × 0.20 + 
           deadline_drop × 0.20 + 
           failure_increase × 0.15)
```

**Components:**
- **Throughput Degradation**: Percentage reduction in processed requests
- **Latency Increase**: Percentage increase in average processing time
- **Success Rate Drop**: Percentage reduction from 100% baseline success
- **Deadline Met Drop**: Percentage reduction in deadline compliance
- **Failure Rate Increase**: Percentage increase from 0% baseline failures

**Interpretation:**
- High severity (>50): Significant performance degradation
- Medium severity (20-50): Noticeable impact
- Low severity (<20): Minimal impact
- Zero severity: No direct performance impact

See [Severity.md](Severity.md) for detailed severity documentation.

### Output Tables

Each analysis generates three CSV tables:

1. **table1_fault_summary.csv** - Fault injection statistics
   - Misbehaving vs. benign server counts
   - Dropped, rejected, delayed requests
   - False reports count

2. **table2_overall_summary.csv** - System-wide performance metrics
   - Execution time
   - Speedup factor
   - Request processing statistics

3. **table3_impact_severity.csv** - Fault impact analysis
   - Throughput degradation
   - Latency increase
   - Success/deadline drop rates
   - Failure increase percentage
   - **Severity score**

## 🔧 Key Components

### FaultyEdgeServer (`edge.py`)

Extends EdgeSimPy's `EdgeServer` with Byzantine fault injection:

```python
server = FaultyEdgeServer(
    fault_type="processing_delay_attack",
    fault_config={"slowdown_factor": 2.0}
)
```

**Supported Fault Types:**
- `PROCESSING_DELAY_ATTACK`
- `REQUEST_DROPPING`
- `FALSE_RESOURCE_REPORTING`
- `SELECTIVE_SERVICE_REJECTION`

### Dataset Generators

Each dataset generator creates simulation configurations for a specific fault type:

| File | Purpose |
|------|---------|
| `dataset_baseline.py` | Healthy baseline for comparison |
| `dataset_delay_attack.py` | Processing delay attack scenarios |
| `dataset_request_dropping.py` | Request dropping attack scenarios |
| `dataset_false_reporting.py` | False resource reporting scenarios |
| `dataset_selective_rejection.py` | Selective service rejection scenarios |
| `dataset_mixed_faults.py` | Mixed/combined fault scenarios |

### Analysis Tools

- **analysis_tools.py**: Utility functions for metrics calculation and analysis
- **compare_simulations.py**: Compare across multiple scenarios
- **comprehensive_analysis.py**: Full pipeline from simulation to analysis
- **test_all_scenarios.py**: Automated testing of all fault scenarios

## 📝 Example Workflow

### 1. Generate a Dataset
```bash
python dataset_delay_attack.py --servers 100 --ratio 0.1
```

### 2. Run Simulation
```bash
python scaled_simulation.py
```

### 3. Analyze Results
```bash
python analysis_tools.py --input metrics.json
```

### 4. Compare Scenarios
```bash
python compare_simulations.py --baseline baseline_metrics.json \
                               --scenario delay_attack_metrics.json
```

## 📋 Test Suite

Run comprehensive test suite:
```bash
python test_all_scenarios.py
```

Results are saved to `test_suite_summary.json` including:
- Execution status for each scenario
- Performance metrics
- Error logs
- Coverage statistics

## 🔍 Simulation Scales

The project includes pre-configured simulations at multiple scales:

| Config | Servers | Stations | Faults | Duration |
|--------|---------|----------|--------|----------|
| 100_10_2-3_2-3 | 100 | 10 | 2-3% | 2-3s |
| 100_50_2-4_2-4 | 100 | 50 | 2-4% | 2-4s |
| 150_30_2-3_2-3 | 150 | 30 | 2-3% | 2-3s |
| 200_20_2-3_2-3 | 200 | 20 | 2-3% | 2-3s |
| 200_40_2-4_2-4 | 200 | 40 | 2-4% | 2-4s |
| 250_30_2-3_2-3 | 250 | 30 | 2-3% | 2-3s |
| 300_10_2-3_2-3 | 300 | 10 | 2-3% | 2-3s |
| 300_50_2-4_2-4 | 300 | 50 | 2-4% | 2-4s |
| 400_30_2-3_2-3 | 400 | 30 | 2-3% | 2-3s |
| 500_20_3-5_3-5 | 500 | 20 | 3-5% | 3-5s |

## 📊 Output Data

### Simulation Logs
Binary msgpack format logs stored in `logs/`:
- Component-level metrics for all edge servers, users, services, etc.
- Detailed event traces for debugging and analysis

### Analysis Results
CSV tables and JSON metrics in `Analysis/` and `ComprehensiveAnalysis/`:
- Comparative fault impact analysis
- Severity scoring across scenarios
- Performance trend analysis

## 🛠️ Requirements

- Python 3.8+
- EdgeSimPy (installed via git)
- pandas
- numpy
- matplotlib
- msgpack

See `requirements.txt` for full dependency list.

## 📚 Documentation

- [Severity.md](Severity.md) - Severity score calculation and interpretation
- [analysis_report.txt](analysis_report.txt) - Sample analysis output
- Inline code documentation in Python files

## 🔬 Research Applications

This framework is suitable for:

- **Malicious Fault Tolerance Research** - Evaluate detection and recovery mechanisms
- **Edge Computing Security** - Assess vulnerability to various attack types
- **Resource Management** - Study impact on task scheduling and placement
- **System Resilience** - Measure degradation under fault conditions
- **Defense Mechanism Evaluation** - Test detection and mitigation strategies

## 📌 Notes

- Simulations use msgpack for efficient log storage
- Analysis pipeline automatically aggregates results across simulation runs
- Severity scores are normalized (0-100) for cross-scenario comparison
- All timestamps are relative to simulation start (step 0)

