import time
import random
import threading
from datetime import datetime, timedelta
from decimal import ROUND_HALF_EVEN, Decimal

import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.gridspec import GridSpec


from engine_fifo import Order, OrderBook


class Visualization:
    def __init__(self, book=None):
        self.book = book or OrderBook()
        self.setup_figure()

    def setup_figure(self):
        plt.style.use("dark_background")  # Dark theme for better visibility

        # Hide matplotlib default toolbar
        plt.rcParams["toolbar"] = "None"

        plt.rcParams.update(
            {
                "font.size": 14,  # Bigger text
                "font.weight": "bold",  # Bold text
                "axes.labelweight": "bold",  # Bold axis labels
                "axes.titlesize": 16,  # Bigger title
                "axes.titleweight": "bold",  # Bold title
                "legend.fontsize": 12,  # Legend font size
                "legend.title_fontsize": 14,  # If using legend titles
                "xtick.labelsize": 12,  # X-axis tick labels
                "ytick.labelsize": 12,  # Y-axis tick labels
                "axes.facecolor": "#1e1e1e",  # Dark background for axes
                "figure.facecolor": "#1e1e1e",  # Dark figure background
            }
        )

        self.fig = plt.figure(figsize=(14, 6))
        # Make the plot fullscreen where possible
        # try:
        #     manager = plt.get_current_fig_manager()
        #     manager.full_screen_toggle()
        # except Exception:
        #     pass

        # Default tight layout / margins for this plot arrangement
        self.fig.subplots_adjust(
            top=0.933, bottom=0.083, left=0.055, right=0.967, hspace=0.174, wspace=0.216
        )

        gs = self.fig.add_gridspec(
            2, 3, height_ratios=[3, 1]
        )  # share x for right panel

        self.ax_book = self.fig.add_subplot(gs[1, 2])  # Left: Order Book
        self.ax_price = self.fig.add_subplot(gs[0, :2])  # Right Top: Candlestick + SMA
        self.ax_vol = self.fig.add_subplot(
            gs[1, :2], sharex=self.ax_price
        )  # Right Bottom: Volume
        self.ax_price.get_xaxis().set_visible(False)

    @staticmethod
    def get_candlestick_df(trades, interval_secs=5):
        if not trades:
            return pd.DataFrame()

        df = pd.DataFrame(
            [
                {
                    "timestamp": datetime.fromtimestamp(t.timestamp),
                    "price": t.price,
                    "volume": t.volume,
                }
                for t in trades
            ]
        )

        df.set_index("timestamp", inplace=True)

        grouper = pd.Grouper(freq=f"{interval_secs}s")

        ohlc = df.groupby(grouper)["price"].agg(
            open="first", high="max", low="min", close="last"
        )

        volume = df.groupby(grouper)["volume"].sum()

        # Combine both
        ohlcv = pd.concat([ohlc, volume], axis=1)

        # mplfinance expects float
        ohlcv = ohlcv.astype(float)

        return ohlcv.dropna()

    def update(self, frame):
        self.ax_book.clear()
        self.ax_price.clear()
        self.ax_vol.clear()

        order_book_depth = self.book.get_order_book_depth()
        buy_depth, sell_depth = order_book_depth["buy"], order_book_depth["sell"]
        all_prices = sorted(set(buy_depth) | set(sell_depth))
        if not all_prices or not self.book.trades:
            return

        # Order book
        last_trade_price = self.book.last_trading_price
        if last_trade_price is None:
            return

        last_trade_price = float(last_trade_price)
        all_prices = [float(p) for p in all_prices]

        buy_volumes = [buy_depth.get(p, 0) for p in all_prices]
        sell_volumes = [sell_depth.get(p, 0) for p in all_prices]

        self.ax_book.bar(all_prices, buy_volumes, width=0.9, color="green", label="Buy")
        self.ax_book.bar(all_prices, sell_volumes, width=0.9, color="red", label="Sell")
        self.ax_book.axvline(
            last_trade_price,
            color="yellow",
            linestyle="--",
            linewidth=2,
            label=f"Last @ {last_trade_price:.2f}",
            alpha=0.7,
        )

        # Center x-axis around LTP
        spread = 10  # show +/- 5 price units
        self.ax_book.set_xlim(last_trade_price - spread, last_trade_price + spread)

        self.ax_book.set_title("Live Order Book")
        self.ax_book.set_xlabel("Price")
        self.ax_book.set_ylabel("Volume")
        self.ax_book.legend(loc="upper right")
        self.ax_book.grid(True)

        # -- CANDLESTICK (right) --
        if isinstance(self.book.trades, dict):
            trades = list(
                self.book.trades.values()
            )  # Get list of Trade objects from dict
        else:
            trades = self.book.trades  # Assume it's already a list

        ohlc_df = self.get_candlestick_df(trades, interval_secs=3)
        if ohlc_df.empty:
            return

        smas = (3, 5)

        low = ohlc_df["low"].min()
        high = ohlc_df["high"].max()
        padding = (high - low) * 0.2
        # Plot using mplfinance into ax2
        mpf.plot(
            ohlc_df[-60:],  # last 45 candles
            type="candle",
            style="yahoo",
            show_nontrading=True,
            mav=smas,
            mavcolors=[
                "#FF6B35",
                "#00D4FF",
            ],  # Bright orange and cyan for dark theme contrast
            ax=self.ax_price,  # upper right: price + SMA
            volume=self.ax_vol,  # lower right: volume
            tight_layout=True,
            warn_too_much_data=1000,
            ylim=(low - padding, high + padding),
        )

        self.ax_price.yaxis.set_label_position("left")
        self.ax_price.yaxis.tick_left()

        self.ax_price.set_title("LTP Candlestick Chart")
        # Extract SMA lines (they're added *after* candlesticks, in order)
        sma_lines = self.ax_price.lines[-len(smas) :]  # last N lines are the SMAs
        sma_labels = [f"SMA({s})" for s in smas]

        # Add legend using actual line handles and labels
        self.ax_price.legend(sma_lines, sma_labels, loc="upper right")


def generate_random_order(book):
    side = random.choice(["buy", "sell"])
    ltp = book.last_trading_price or 90

    # 10% chance of a market order to generate trades
    if random.random() < 0.1:
        if side == "buy" and book.best_ask:
            price = book.best_ask + Decimal("0.1")
        elif side == "sell" and book.best_bid:
            price = book.best_bid - Decimal("0.1")
        else:
            # Fallback to limit order if no spread
            price = Decimal(random.gauss(float(ltp), 2)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_EVEN
            )
    else:
        # Add price skew: buyers mostly place lower, sellers higher
        if side == "buy":
            price = Decimal(random.gauss(float(ltp) - 5, 10))  # e.g., ~5 below LTP
        else:
            price = Decimal(random.gauss(float(ltp) + 5, 10))  # e.g., ~5 above LTP

    # Clip price within bounds
    # price = max(1, min(price, ltp + 20))

    # Size distribution: more small orders, few big ones
    quantity = int(random.expovariate(1 / 10)) + 1
    quantity = min(quantity, 100)
    return Order(side, price, quantity)


def run_simulation(book):
    while True:
        order = generate_random_order(book)
        print(order)
        book.place_order(order)
        time.sleep(0.05)


if __name__ == "__main__":
    vis = Visualization()
    threading.Thread(target=run_simulation, args=(vis.book,), daemon=True).start()
    ani = FuncAnimation(vis.fig, vis.update, interval=200)
    plt.show()
