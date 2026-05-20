import os
import time
from locust import HttpUser, TaskSet, task, between


ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "ignite123")


class UserBehavior(TaskSet):
    def on_start(self):
        username = f"user{int(time.time()*10)}"
        self.client.get(f"/login?username={username}", name="/login")

    @task
    def state(self):
        self.client.get("/state")


class AdminBehavior(TaskSet):
    def on_start(self):
        self.client.post("/admin/login", json={"password": ADMIN_PASSWORD})

    @task
    def trigger_orders(self):
        self.client.post(
            "/orders/random",
            json={"num_orders": 100, "delay": 0.001},
        )


class WebsiteUser(HttpUser):
    host = os.getenv("LOCUST_HOST", "http://127.0.0.1:8000")
    tasks = [UserBehavior]
    wait_time = between(0.5, 2)
    weight = 20


class AdminUser(HttpUser):
    host = os.getenv("LOCUST_HOST", "http://127.0.0.1:8000")
    tasks = [AdminBehavior]
    wait_time = between(5, 10)
    weight = 1
