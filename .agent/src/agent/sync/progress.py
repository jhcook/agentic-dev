import time

class ProgressTracker:
    def __init__(self, total):
        self.total = total
        self.completed = 0
        self.start_time = time.time()

    def update(self, count):
        self.completed += count
        elapsed = time.time() - self.start_time
        eta = (elapsed / self.completed) * (self.total - self.completed) if self.completed > 0 else 0
        print(f"Progress: {self.completed}/{self.total} ({int(eta)}s remaining)")