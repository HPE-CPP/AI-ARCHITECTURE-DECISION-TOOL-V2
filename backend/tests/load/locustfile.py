"""
LOAD TESTS — Locust
Run with: locust -f tests/load/locustfile.py --host=http://localhost:8000
         locust -f tests/load/locustfile.py --host=http://localhost:8000 --headless -u 50 -r 5 -t 60s

Scenarios:
  - AnalysisReader: read-heavy traffic (GET analysis, GET architectures)
  - QuestionnaireUser: submit questionnaire flow
  - DocumentUploader: upload small document, poll result
  - MixedUser: realistic weighted combination
"""
from locust import HttpUser, task, between, events
import json
import time
import random
import io

# ─────────────────────────────────────────────────────────────────────────────
# Reusable payloads
# ─────────────────────────────────────────────────────────────────────────────

SAMPLE_QUESTIONNAIRE = {
    "dataset_size": "large",
    "data_volatility": "high",
    "query_volume": "high",
    "latency_requirement": "strict",
    "accuracy_requirement": "high",
    "domain_specificity": "specialized",
    "security_level": "high",
    "cost_sensitivity": "moderate",
    "deployment_preference": "cloud",
    "user_scale": "large",
}

SAMPLE_TXT_CONTENT = (
    "Architecture Requirements Document\n\n"
    "This financial services platform processes over 10 million customer records daily. "
    "The system must handle real-time fraud detection with latency requirements under 100ms. "
    "The knowledge base is updated daily with new regulatory data. "
    "We require critical accuracy levels with zero tolerance for false negatives. "
    "The domain is highly specialized in financial services and regulatory compliance. "
    "Security level is critical — SOC2 and HIPAA compliance required. "
    "Deployment must be on AWS cloud infrastructure. "
    "Expected user scale is 1 million+ concurrent enterprise users.\n"
).encode("utf-8")

# Track analysis IDs created during load test for use in read tests
_created_analysis_ids: list[str] = []


# ─────────────────────────────────────────────────────────────────────────────
# 1. Read-heavy user (no LLM calls triggered)
# ─────────────────────────────────────────────────────────────────────────────
class AnalysisReader(HttpUser):
    """
    Simulates users browsing existing analyses and static endpoints.
    Weight 3 = most common user type.
    """
    weight = 3
    wait_time = between(0.5, 2.0)

    @task(5)
    def get_architectures(self):
        self.client.get("/api/v1/architectures", name="/api/v1/architectures")

    @task(5)
    def get_questionnaire_options(self):
        self.client.get("/api/v1/questionnaire/options", name="/api/v1/questionnaire/options")

    @task(3)
    def get_health(self):
        self.client.get("/health", name="/health")

    @task(2)
    def get_existing_analysis(self):
        if _created_analysis_ids:
            aid = random.choice(_created_analysis_ids)
            self.client.get(f"/api/v1/analysis/{aid}", name="/api/v1/analysis/[id]")

    @task(1)
    def get_nonexistent_analysis(self):
        import uuid
        self.client.get(
            f"/api/v1/analysis/{uuid.uuid4()}",
            name="/api/v1/analysis/[not_found]",
        )


# ─────────────────────────────────────────────────────────────────────────────
# 2. Questionnaire user (lightweight — no file IO)
# ─────────────────────────────────────────────────────────────────────────────
class QuestionnaireUser(HttpUser):
    """
    Simulates users submitting questionnaire answers.
    Tests the CPU-bound scoring path.
    Weight 2.
    """
    weight = 2
    wait_time = between(1.0, 4.0)

    @task
    def submit_full_questionnaire(self):
        payload = {
            "answers": SAMPLE_QUESTIONNAIRE,
            "provider": "ollama",
        }
        with self.client.post(
            "/api/v1/questionnaire",
            json=payload,
            name="/api/v1/questionnaire",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                analysis_id = data.get("analysis_id")
                if analysis_id and analysis_id not in _created_analysis_ids:
                    _created_analysis_ids.append(analysis_id)
                resp.success()
            elif resp.status_code in (422, 503):
                resp.success()  # Expected when LLM not available
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")

    @task(2)
    def get_options_then_submit(self):
        opts_resp = self.client.get(
            "/api/v1/questionnaire/options", name="/api/v1/questionnaire/options"
        )
        if opts_resp.status_code == 200:
            # Simulate user filling in answers over time
            time.sleep(random.uniform(0.5, 2.0))
            payload = {
                "answers": {k: random.choice(v["options"])["value"]
                            for k, v in opts_resp.json().get("signals", {}).items()
                            if v.get("options")},
                "provider": "ollama",
            }
            self.client.post("/api/v1/questionnaire", json=payload,
                             name="/api/v1/questionnaire (random)")


# ─────────────────────────────────────────────────────────────────────────────
# 3. Document Uploader (IO-heavy)
# ─────────────────────────────────────────────────────────────────────────────
class DocumentUploader(HttpUser):
    """
    Simulates file uploads with polling.
    Lowest weight — resource intensive.
    """
    weight = 1
    wait_time = between(5.0, 15.0)

    @task
    def upload_and_poll(self):
        # Upload
        with self.client.post(
            "/api/v1/upload?provider=ollama",
            files={"file": ("requirements.txt", io.BytesIO(SAMPLE_TXT_CONTENT), "text/plain")},
            name="/api/v1/upload",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                analysis_id = resp.json().get("analysis_id")
                resp.success()
            elif resp.status_code in (422, 503):
                resp.success()
                return
            else:
                resp.failure(f"Upload failed: {resp.status_code}")
                return

        if not analysis_id:
            return

        _created_analysis_ids.append(analysis_id)

        # Poll with exponential backoff
        backoff = 1.0
        for _ in range(6):
            time.sleep(backoff)
            poll_resp = self.client.get(
                f"/api/v1/analysis/{analysis_id}",
                name="/api/v1/analysis/[poll]",
            )
            if poll_resp.status_code == 200:
                status = poll_resp.json().get("status", "")
                if status in ("complete", "error"):
                    break
            backoff = min(backoff * 2, 8.0)

    @task(2)
    def upload_invalid_file_type(self):
        """Load test must not expose server instability for bad inputs."""
        with self.client.post(
            "/api/v1/upload",
            files={"file": ("data.csv", io.BytesIO(b"col1,col2\nval1,val2"), "text/csv")},
            name="/api/v1/upload (invalid)",
            catch_response=True,
        ) as resp:
            if resp.status_code == 400:
                resp.success()
            else:
                resp.failure(f"Expected 400, got {resp.status_code}")


# ─────────────────────────────────────────────────────────────────────────────
# 4. Follow-up submitter
# ─────────────────────────────────────────────────────────────────────────────
class FollowupUser(HttpUser):
    """Simulates users who submit follow-up answers after receiving results."""
    weight = 1
    wait_time = between(2.0, 8.0)

    @task
    def submit_followup(self):
        if not _created_analysis_ids:
            return
        aid = random.choice(_created_analysis_ids)
        payload = {
            "analysis_id": aid,
            "answers": {
                "dataset_size": "large",
                "latency_requirement": "strict",
            },
        }
        with self.client.post(
            "/api/v1/followup",
            json=payload,
            name="/api/v1/followup",
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 404):
                resp.success()
            else:
                resp.failure(f"Unexpected: {resp.status_code}")


# ─────────────────────────────────────────────────────────────────────────────
# 5. Custom event hooks for reporting
# ─────────────────────────────────────────────────────────────────────────────
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print("\n[LOAD TEST] Starting AI Architecture Decision Platform load test")
    print(f"[LOAD TEST] Target: {environment.host}")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    stats = environment.stats
    print(f"\n[LOAD TEST COMPLETE]")
    print(f"  Total requests:  {stats.total.num_requests}")
    print(f"  Failures:        {stats.total.num_failures}")
    print(f"  Failure rate:    {stats.total.fail_ratio:.1%}")
    print(f"  Avg response:    {stats.total.avg_response_time:.0f}ms")
    print(f"  95th percentile: {stats.total.get_response_time_percentile(0.95):.0f}ms")
    print(f"  99th percentile: {stats.total.get_response_time_percentile(0.99):.0f}ms")
    print(f"  Peak RPS:        {stats.total.current_rps:.1f}")

    # Fail the load test if error rate > 5%
    if stats.total.fail_ratio > 0.05:
        print(f"\n[LOAD TEST FAILED] Error rate {stats.total.fail_ratio:.1%} exceeds 5% threshold")
        environment.process_exit_code = 1
