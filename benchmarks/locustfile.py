import os
import time
from locust import HttpUser, TaskSet, task, between


class UserBehavior(TaskSet):
    def on_start(self):
        # register/login a unique user per simulated user
        username = f"user{int(time.time()*10)}"
        self.client.get(f"/login?username={username}")

    @task(3)
    def game(self):
        self.client.get("/game")

    @task(1)
    def post_random(self):
        self.client.post(
            "/orders/random",
            json={"num_orders": 100, "delay": 0.001},
            headers={"Content-Type": "application/json"},
        )


class WebsiteUser(HttpUser):
    # Base host can be specified via LOCUST_HOST environment variable
    # or via locust CLI `-H`/`--host` flag which overrides this attribute.
    host = os.getenv("LOCUST_HOST", "http://127.0.0.1:8000")
    tasks = [UserBehavior]
    wait_time = between(0.5, 2)
