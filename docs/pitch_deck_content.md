# RailOpt — Smart India Hackathon Pitch & Project Details

This document contains everything you need to explain, pitch, and defend the RailOpt project to hackathon judges or technical evaluators. It breaks down the problem, your solution, the technology stack, and deep dives into the ML and optimization architectures.

---

## 1. The Problem: Maintenance in Indian Railways
Indian Railways (IR) is the fourth-largest railway network in the world. Maintenance planning currently faces several severe bottlenecks:
* **Siloed Systems**: Engineering uses TMS (Track Management System), S&T uses SMMS (Signal Maintenance Management System), and Traction uses TDMS (Traction Distribution Management System). They do not talk to each other.
* **Wasted Capacity**: Because departments request maintenance "blocks" (track closures) independently, a single track might be closed three times a week for three different departments. 
* **Manual Prioritization**: Maintenance prioritization relies on human judgment rather than data-driven criticality, often leading to missed SLAs on critical safety defects.
* **Traffic Disruption**: Maintenance schedules are rarely optimized against train timetables (COA), causing unnecessary passenger and freight train delays.

## 2. The Solution: RailOpt
**RailOpt** is an AI-powered, multi-layer Automatic Block Planning system. It ingests maintenance requests from all siloed systems, predicts the exact duration and traffic impact of each task using Machine Learning, evaluates them through a rigorous 5-layer risk analysis pipeline, and uses advanced Operations Research (Google OR-Tools) to generate the optimal, conflict-free maintenance schedule.

**The primary goal**: Maximize safety (critical tasks scheduled) while minimizing disruption (train delays) and maximizing "Merge Savings" (combining multiple departments into a single block).

---

## 3. Core Features & Innovations

1. **Unified Data Integration**: Automatically normalizes unstructured and structured data from TMS, SMMS, TDMS, and COA (Control Office Application) into a single schema.
2. **Predictive AI**: Uses tree-based ML models (LightGBM) to predict how long a task will take, its severity, and how many trains will be delayed if a specific time window is chosen.
3. **Multi-Layer Risk Engine**: A 5-layer analysis engine (inspired by advanced Financial Crime detection systems) that blends ML predictions with real-world context (e.g., weather, Rajdhani routes), compliance rules, and behavioral signals (e.g., chronic deferrals).
4. **Multi-Department Merging**: Automatically identifies overlapping tasks from different departments (e.g., Track and Signals) and schedules them in the *same* block window, saving thousands of hours of track closure time.
5. **GenAI Control Room**: Uses Google Gemini to generate human-readable natural language briefings, explain complex ML decisions to engineers, and allow querying the database using plain English.
6. **Adversarial Resilience**: Built-in simulator to test the schedule against unexpected disruptions (e.g., severe weather, asset failures) to ensure the plan doesn't collapse under real-world stress.

---

## 4. Technology Stack

* **Backend Framework**: Python + FastAPI (High-performance, asynchronous REST API).
* **Database**: SQLite with SQLAlchemy ORM (Relational database for storing tasks, corridors, and historical plans).
* **Machine Learning**: 
  * `LightGBM` & `XGBoost` (For tabular data predictions: criticality and duration).
  * `SHAP` (SHapley Additive exPlanations for ML explainability).
* **Operations Research**: `Google OR-Tools (CP-SAT)` (Constraint Programming solver for block scheduling).
* **Generative AI**: `google-genai` (Google Gemini 2.5 Flash for NLP classification, briefings, and NL queries).
* **Frontend UI**: React + Vite, TailwindCSS, Recharts (For live data visualization and dashboarding).

---

## 5. Machine Learning & AI Architecture

RailOpt does not rely on a single black-box AI. It uses specialized models for specialized tasks.

### A. The Three ML Models (Predictive Layer)
1. **Criticality Scorer (Classification & Regression)**: 
   * **What it does**: Predicts the severity (EMERGENCY, HIGH, LOW) and a raw criticality score (0-100) for every incoming task based on asset age, historical failures, and days overdue.
   * **Algorithm**: LightGBM.
2. **Impact Predictor (Regression)**:
   * **What it does**: Looks at block windows and the train timetable (COA). Predicts exactly how many trains will be affected and the cumulative delay minutes if a block is taken.
3. **Duration Estimator (Regression)**:
   * **What it does**: Predicts the exact hours a maintenance task will take, complete with statistical confidence intervals (upper/lower bounds).

### B. The 5-Layer Risk Blending Pipeline
To ensure safety and compliance, the raw ML score is passed through four additional expert-system layers before being fed to the optimizer.
* **Layer 1: ML Score (30%)** — The raw LightGBM criticality prediction.
* **Layer 2: Context Engine (20%)** — Adjusts scores based on environment. (e.g., boosts score if the track is a "Rajdhani Route" or if it's the "Monsoon" season with waterlogging risk).
* **Layer 3: Compliance Engine (15%)** — Hard safety rules. (e.g., if a track defect violates the Indian Railways Permanent Way Manual, it gets heavily escalated).
* **Layer 4: Behavioral Analyzer (20%)** — Detects human patterns. (e.g., penalizes tasks that a department has chronically deferred 5 times in a row).
* **Layer 5: Signal Extractor (15%)** — NLP extraction of urgency from inspector remarks.
**Output**: A single "Blended Risk Score" and a rich evidence summary.

---

## 6. Operations Research (The CP-SAT Solver)

Once tasks are scored, they must be scheduled. RailOpt uses **Constraint Programming (Google OR-Tools CP-SAT)** to solve this NP-Hard scheduling problem.

* **Decision Variables**: Boolean matrix `x[i, j]` (Is Task `i` assigned to Block Window `j`?).
* **Constraints**: 
  * A window's capacity (hours) cannot be exceeded.
  * Only one power block can be granted in a section at a time.
  * Emergency tasks *must* be scheduled (handled as a heavy soft-penalty constraint to prevent solver failure if mathematically impossible).
* **Objective Function (What it optimizes for)**:
  * *Reward* scheduling high-criticality tasks (Beta).
  * *Reward* multi-department merging (Gamma).
  * *Penalize* traffic disruption and train delays (Alpha).
  * *Penalize* leaving tasks unscheduled (Delta).

---

## 7. Generative AI (Google Gemini Integration)

RailOpt uses LLMs responsibly by isolating them from mathematical scheduling and using them strictly for unstructured text and user interaction.

1. **Defect Text Classifier**: When tasks are imported with vague inspector remarks ("wire hanging loose"), Gemini parses the text, extracts the asset type, and categorizes the defect.
2. **Explainability Engine**: Translates complex SHAP values (e.g., "Feature `historical_failures` +14.2") into human-readable explanations ("This task is rated High risk primarily because the asset has failed 4 times previously").
3. **Briefing Generator**: Reads the final JSON Block Plan and generates a military-style morning briefing for the control room.
4. **NL Query Engine**: Allows control room operators to type "Which engineering tasks got deferred this week?" and receives a natural language answer based on the database state.

---

## 8. Human-in-the-Loop & Feedback

RailOpt is an assistive tool, not an autonomous dictator. 
* **Approval Workflow**: The generated plan goes to the dashboard in a `DRAFT` state. Human controllers can `APPROVE`, `REJECT`, or `MODIFY` the plan.
* **Feedback Logger**: If a human modifies a plan (e.g., forces a low-priority task to be scheduled), the `FeedbackLogger` records the override. This data is saved locally to retrain the LightGBM models in the next cycle, allowing the AI to learn from human intuition.
