import time
import matplotlib.pyplot as plt
from random import randint, choice, uniform
from engine_heapnodes import Order, OrderBook


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

    print("Benchmarking: place_order()...")
    results["Place Order"] = time_each_call(place_one, n)

    # Benchmark get_order_by_id
    def get_one():
        if ids:
            oid = choice(ids)
            _ = book.get_order_by_id(oid)

    print("Benchmarking: get_order_by_id()...")
    results["Get Order"] = time_each_call(get_one, n)

    # Benchmark cancel_order
    def cancel_one():
        if ids:
            oid = choice(ids)
            try:
                book.cancel_order(oid)
            except KeyError:
                pass

    print("Benchmarking: cancel_order()...")
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

    print("Benchmarking: update_order()...")
    results["Update Order"] = time_each_call(update_one, n)

    # Benchmark get_order_book_depth
    print("Benchmarking: get_order_book_depth()...")
    results["Get Book Depth"] = time_each_call(book.get_order_book_depth, n)

    # Benchmark last_trading_price
    print("Benchmarking: last_trading_price...")
    results["Last Price"] = time_each_call(lambda: book.last_trading_price, n)

    # Benchmark matching throughput (trades per second)
    print("Benchmarking: matching throughput...")
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
    print("Running microbenchmarks...")
    latency_data = benchmark_all(n=1000)

    print("\nBenchmark Results Summary:")
    for name, times in latency_data.items():
        if times:
            if name == "Matching Throughput":
                print(f"{name}: {times[0]:.2f} trades/sec")
            else:
                avg = sum(times) / len(times)
                min_t = min(times)
                max_t = max(times)
                print(f"{name}: Avg={avg:.3f}ms, Min={min_t:.3f}ms, Max={max_t:.3f}ms")
        else:
            print(f"{name}: No data")

    plot_all_distributions(latency_data)
