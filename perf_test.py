import time
import matplotlib.pyplot as plt
from random import randint, choice, uniform
from engine_heapnodes import Order, OrderBook
import logging

logger = logging.getLogger(__name__)


def time_each_call(func, repeat):
    durations = []
    for _ in range(repeat):
        start = time.perf_counter()
        func()
        end = time.perf_counter()
        durations.append((end - start) * 1000)  # milliseconds
    return durations


def benchmark_all(n=1000):
    book = OrderBook()
    ids = []

    results = {}

    # Benchmark placing orders
    def place_one():
        side = choice(["buy", "sell"])
        price = round(uniform(90, 110), 2)
        qty = randint(1, 100)
        order = Order(side, price, qty)
        book.place_order(order)
        ids.append(order.id)

    logger.info("Benchmarking: place_order()...")
    results["Place Order"] = time_each_call(place_one, n)

    # Benchmark get_order_by_id
    def get_one():
        if ids:
            oid = choice(ids)
            _ = book.get_order_by_id(oid)

    logger.info("Benchmarking: get_order_by_id()...")
    results["Get Order"] = time_each_call(get_one, n)

    # Benchmark cancel_order
    def cancel_one():
        if ids:
            oid = choice(ids)
            try:
                book.cancel_order(oid)
            except KeyError:
                pass

    logger.info("Benchmarking: cancel_order()...")
    results["Cancel Order"] = time_each_call(cancel_one, n)

    # Benchmark update_order
    def update_one():
        if ids:
            oid = choice(ids)
            side = choice(["buy", "sell"])
            price = round(uniform(90, 110), 2)
            qty = randint(1, 100)
            try:
                book.update_order(oid, side, price, qty)
            except KeyError:
                pass

    logger.info("Benchmarking: update_order()...")
    results["Update Order"] = time_each_call(update_one, n)

    # Benchmark get_order_book_depth
    logger.info("Benchmarking: get_order_book_depth()...")
    results["Get Book Depth"] = time_each_call(book.get_order_book_depth, n)

    # Benchmark last_trading_price
    logger.info("Benchmarking: last_trading_price...")
    results["Last Price"] = time_each_call(lambda: book.last_trading_price, n)

    # Benchmark matching throughput (trades per second)
    logger.info("Benchmarking: matching throughput...")
    start = time.perf_counter()
    for _ in range(n * 10):  # Place more orders for throughput test
        side = choice(["buy", "sell"])
        price = round(uniform(90, 110), 2)
        qty = randint(1, 100)
        order = Order(side, price, qty)
        book.place_order(order)
    end = time.perf_counter()
    total_time = end - start
    num_trades = len(book.trades)
    throughput = num_trades / total_time if total_time > 0 else 0
    results["Matching Throughput"] = [throughput]  # Store as list for consistency

    return results


def plot_all_distributions(latency_dict):
    plt.figure(figsize=(12, 10))
    plot_items = [
        (name, times)
        for name, times in latency_dict.items()
        if name != "Matching Throughput"
    ]
    for i, (name, times) in enumerate(plot_items, 1):
        plt.subplot(3, 2, i)
        plt.hist(times, bins=50, color="mediumseagreen", edgecolor="black", alpha=0.75)
        plt.title(name)
        plt.xlabel("Time per call (ms)")
        plt.ylabel("Frequency")
        plt.grid(True, linestyle="--", alpha=0.3)

    plt.tight_layout()
    plt.suptitle("Latency Distribution for Order Book Operations", fontsize=16, y=1.02)
    plt.show()


if __name__ == "__main__":
    logger.info("Running microbenchmarks...")
    latency_data = benchmark_all(n=1000)

    logger.info("\nBenchmark Results Summary:")
    for name, times in latency_data.items():
        if times:
            if name == "Matching Throughput":
                logger.info("%s: %.2f trades/sec", name, times[0])
            else:
                avg = sum(times) / len(times)
                min_t = min(times)
                max_t = max(times)
                logger.info(
                    "%s: Avg=%.3fms, Min=%.3fms, Max=%.3fms", name, avg, min_t, max_t
                )
        else:
            logger.info("%s: No data", name)

    plot_all_distributions(latency_data)
