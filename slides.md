Here’s a **fully clean Markdown slide deck** (no extra IDs, ready for Marp / Reveal.js / HackMD):

---

```markdown
# Building a Stock Exchange in Python

### How modern markets match buyers and sellers

Animesh Chouhan

---

# What happens when you press BUY?

- your order reaches an exchange
- it enters an order book
- a matching engine decides if a trade happens
- the trade executes in microseconds

**At its core, this entire system is just an algorithm.**

---

# What is a Stock Exchange?

A stock exchange:

- receives buy and sell orders
- stores them in an order book
- matches compatible orders
- executes trades

**Goal: match buyers and sellers efficiently**

---

# The Core Problem

Trader A  
Buy 100 shares at ₹101

Trader B  
Sell 100 shares at ₹99

**Should a trade happen?**

Yes.

**Rule: Buy Price ≥ Sell Price → Trade**

---

# The Order Book

Two sides:

**Bids (Buy Orders)**  
Highest price first

**Asks (Sell Orders)**  
Lowest price first

Example:
```

BIDS ASKS
101 × 5 102 × 4
100 × 10 103 × 8

```

---

# Top of Book

- Best Bid → highest buy price
- Best Ask → lowest sell price

If:

**Best Bid ≥ Best Ask**

→ Trade occurs

---

# Orders

Each order has:

- id
- side (buy / sell)
- price
- quantity

Example:

```

Order(id=1, side="buy", price=101, quantity=5)

````

---

# Choosing the Right Data Structure

We need fast access to:

- highest buy price
- lowest sell price

Use:

**Priority Queue (Heap)**

- Buy → Max heap
- Sell → Min heap

---

# Python Trick

Python only has a min heap.

Simulate max heap:

```python
heapq.heappush(buys, (-price, order))
````

---

# The Matching Engine

Core loop:

```python
while best_bid >= best_ask:
    execute_trade()
```

Trade quantity:

```python
min(buy.quantity, sell.quantity)
```

---

# Example Matching

Initial:

```
Buy              Sell
101 × 5          100 × 3
```

Trade happens:

```
TRADE: 3 @ 100
```

Remaining:

```
Buy
101 × 2
```

---

# Partial Fills

Example:

```
Buy  100 × 10
Sell 100 × 3
```

Trade:

```
3 shares
```

Remaining:

```
Buy 100 × 7
```

**This is called a partial fill.**

---

# Putting It Together

Core components:

- Order object
- Buy heap
- Sell heap
- Matching function

**~100 lines of Python = working exchange**

---

# Live Demo

Input:

```
BUY 100 5
BUY 101 2
SELL 99 3
```

Output:

```
TRADE 99 x 2
TRADE 100 x 1
```

---

# Real Exchanges Are Harder

- millions of orders per second
- microsecond latency
- order cancellation
- market orders
- fairness rules
- distributed systems

---

# Key Insight

A stock exchange is:

- an order book
- a priority queue
- a matching algorithm

**Markets run on data structures.**

---

# Closing

With simple algorithms, we can simulate a financial market.

**Behind the global stock market is just a very fast matching engine.**

```

---

If you want next step, I can give you a **super clean dark theme (black + subtle gold, very trading desk vibe)** or a **demo script that syncs perfectly slide-by-slide**.
```
