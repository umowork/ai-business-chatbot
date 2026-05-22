"""Locust load tests.
Usage: locust -f tests/locustfile.py --headless -u 10 -r 2 -H http://localhost:8000
"""
from locust import HttpUser, task, between


class ApiUser(HttpUser):
    wait_time = between(0.5, 3)

    @task(1)
    def health(self):
        self.client.get("/health")

    @task(3)
    def query(self):
        self.client.post("/api/query", json={"text": "test"})

