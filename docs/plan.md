### Trading Simulation Plan

**Overview:**
Create a competitive trading simulation where multiple users (traders) can place market orders (buy/sell) to compete for the highest portfolio value. The system uses one of the existing matching engines (e.g., engine_fifo) for order matching. A bot market maker maintains liquidity and occasionally manipulates the market (rally or pull down prices).

**Key Features:**

- **Traders:** Each trader starts with initial cash (e.g., $10,000). They can place market orders (immediate execution at best available price) and cancel existing orders.
- **Orders:** Only market orders allowed. No limit orders. Orders match immediately against the order book.
- **Short Selling:** Allowed without limits to enable speculation on price declines. Negative holdings represent short positions (owed shares). No borrowing costs or margin calls for simplicity.
- **Competition:** Goal is to maximize portfolio value (cash + holdings \* current price, where negative holdings reduce value). Leaderboard shows rankings.
- **Market Maker Bot:**
  - Maintains liquidity by placing limit orders around the last traded price (LTP) with a spread.
  - Occasionally (e.g., 10% chance) manipulates the market: adds biased orders to rally (more buys) or pull down (more sells) prices.
- **Simulation Loop:** Runs in real-time, updating portfolios, maintaining liquidity, and applying manipulations periodically.

**Components:**

1. **Trader Class:** Manages cash, holdings, portfolio value, and orders. Methods: place_market_order, cancel_order, update_portfolio.
2. **MarketMaker Class:** Maintains liquidity, manipulates market. Methods: maintain_liquidity, manipulate_market.
3. **TradingSimulation Class:** Orchestrates the simulation. Manages book, traders, market maker. Methods: start_simulation, stop_simulation, get_leaderboard.
4. **Integration:** Use existing OrderBook from engine_fifo. Handle market orders by setting price to best available (best_ask for buy, best_bid for sell).

**Technical Details:**

- **Market Orders Handling:** For buy: set price = best_ask. For sell: set price = best_bid. This ensures immediate matching.
- **Liquidity:** Initial orders placed at startup. Market maker refreshes periodically.
- **Manipulation:** Add random orders to bias the market direction.
- **Updates:** Portfolios updated with current LTP. Holdings and cash adjusted on fills.
- **Safety:** Checks for sufficient cash on buys. Sells allowed even with zero/negative holdings (short selling).

**Next Steps:**

- Implement CLI or GUI for user inputs (place orders, cancel, view leaderboard).
- Add more bots or noise traders.
- Integrate with visualization.py for real-time charts.
- Add persistence (save/load state).
- Balance mechanics for fair competition.
