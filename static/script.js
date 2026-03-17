const state = {
    selectedSide: "buy",
    isSubmitting: false,
    chartDefaultRangeApplied: false,
    game: window.__GAME__ || null,
};

const traders = Array.isArray(window.__TRADERS__) ? window.__TRADERS__ : [];
const pageName = window.__PAGE__ || "user";
const currentUser = window.__CURRENT_USER__ || null;

const chartContainer = document.getElementById("ohlc-chart");
const quantityInput = document.getElementById("quantity-input");
const leaderboardBody = document.getElementById("leaderboard-body");
const bidsBook = document.getElementById("bids-book");
const asksBook = document.getElementById("asks-book");
const orderFeedback = document.getElementById("order-feedback");
const orderStatusChip = document.getElementById("order-status-chip");
const engineStatus = document.getElementById("engine-status");
const lastUpdated = document.getElementById("last-updated");
const selectedTraderCard = document.getElementById("selected-trader-card");
const heroTraderName = document.getElementById("hero-trader-name");
const profilePortfolio = document.getElementById("profile-portfolio");
const profileCash = document.getElementById("profile-cash");
const profileHoldings = document.getElementById("profile-holdings");
const profileRank = document.getElementById("profile-rank");
const topPortfolioValue = document.getElementById("top-portfolio-value");
const topPortfolioSubtext = document.getElementById("top-portfolio-subtext");
const gamePhase = document.getElementById("game-phase");
const gameTimer = document.getElementById("game-timer");
const adminStartButton = document.getElementById("admin-start-btn");
const adminResetButton = document.getElementById("admin-reset-btn");
const adminResetAllButton = document.getElementById("admin-reset-all-btn");
const adminLogoutButton = document.getElementById("admin-logout-btn");
const loadTestButton = document.getElementById("load-test-btn");
const adminToolsFeedback = document.getElementById("admin-tools-feedback");
const isMobileViewport = () => window.matchMedia("(max-width: 480px)").matches;

function formatMobileTickMark(time) {
    const date = new Date(Number(time) * 1000);
    const minutes = String(date.getMinutes()).padStart(2, "0");
    const seconds = String(date.getSeconds()).padStart(2, "0");
    return `${minutes}:${seconds}`;
}

function getChartOptions() {
    const mobile = isMobileViewport();
    return {
        autoSize: true,
        layout: {
            background: { color: "#0b1821" },
            textColor: "#d7e4eb",
            fontFamily: "IBM Plex Sans, sans-serif",
            fontSize: mobile ? 9 : 12,
        },
        grid: {
            vertLines: { color: "rgba(255, 255, 255, 0.05)" },
            horzLines: { color: "rgba(255, 255, 255, 0.05)" },
        },
        rightPriceScale: {
            visible: true,
            borderColor: "rgba(255, 255, 255, 0.08)",
            ticksVisible: true,
            alignLabels: false,
            scaleMargins: {
                top: 0.08,
                bottom: mobile ? 0.12 : 0.1,
            },
            minimumWidth: mobile ? 56 : 64,
        },
        timeScale: {
            visible: true,
            borderColor: "rgba(255, 255, 255, 0.08)",
            timeVisible: true,
            secondsVisible: true,
            ticksVisible: true,
            minimumHeight: mobile ? 28 : 24,
            tickMarkMaxCharacterLength: mobile ? 4 : 8,
            minBarSpacing: mobile ? 2 : 0.5,
            rightOffset: mobile ? 1 : 0,
            fixLeftEdge: false,
            fixRightEdge: false,
            tickMarkFormatter: mobile ? formatMobileTickMark : undefined,
        },
        localization: {
            priceFormatter: (price) => price.toFixed(mobile ? 1 : 2),
        },
        handleScroll: {
            mouseWheel: true,
            pressedMouseMove: true,
            horzTouchDrag: true,
            vertTouchDrag: false,
        },
        handleScale: {
            axisPressedMouseMove: true,
            mouseWheel: true,
            pinch: true,
        },
        crosshair: {
            vertLine: {
                color: "rgba(77, 198, 255, 0.35)",
                labelBackgroundColor: "#1178ff",
            },
            horzLine: {
                color: "rgba(255, 209, 102, 0.35)",
                labelBackgroundColor: "#d29314",
            },
        },
    };
}

const chart = chartContainer ? LightweightCharts.createChart(chartContainer, getChartOptions()) : null;

function addSeries(chartInstance, legacyMethod, seriesType, options) {
    if (typeof chartInstance[legacyMethod] === "function") {
        return chartInstance[legacyMethod](options);
    }
    if (typeof chartInstance.addSeries === "function" && seriesType) {
        return chartInstance.addSeries(seriesType, options);
    }
    throw new Error(`Unable to create ${legacyMethod} on this Lightweight Charts build.`);
}

const candlestickSeries = chart ? addSeries(
    chart,
    "addCandlestickSeries",
    LightweightCharts.CandlestickSeries,
    {
        upColor: "#29c48a",
        downColor: "#ff6b57",
        borderUpColor: "#29c48a",
        borderDownColor: "#ff6b57",
        wickUpColor: "#7ef1c0",
        wickDownColor: "#ff9f93",
    }
) : null;

const areaSeries = chart ? addSeries(
    chart,
    "addAreaSeries",
    LightweightCharts.AreaSeries,
    {
        lineColor: "rgba(77, 198, 255, 0.9)",
        topColor: "rgba(77, 198, 255, 0.18)",
        bottomColor: "rgba(77, 198, 255, 0.01)",
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: false,
    }
) : null;

function resizeChartToContainer() {
    if (!chart || !chartContainer) {
        return;
    }
    chart.applyOptions(getChartOptions());
    const width = chartContainer.clientWidth;
    const minChartHeight = isMobileViewport() ? 300 : 260;
    const height = Math.max(chartContainer.clientHeight, minChartHeight);
    if (width > 0 && height > 0) {
        chart.resize(width, height);
    }
}

function formatCurrency(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) {
        return "--";
    }
    return `Rs ${number.toFixed(2)}`;
}

function formatBookPrice(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) {
        return "--";
    }
    return number.toFixed(2);
}

function formatSigned(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) {
        return "--";
    }
    return `${number >= 0 ? "+" : ""}${number.toFixed(2)}`;
}

function formatDuration(secondsRemaining) {
    const safeSeconds = Math.max(0, Number(secondsRemaining) || 0);
    const minutes = String(Math.floor(safeSeconds / 60)).padStart(2, "0");
    const seconds = String(safeSeconds % 60).padStart(2, "0");
    return `${minutes}:${seconds}`;
}

function setFeedback(message, type = "") {
    if (!orderFeedback) {
        return;
    }
    orderFeedback.textContent = message;
    orderFeedback.className = `feedback-text${type ? ` ${type}` : ""}`;
}

function setAdminToolsFeedback(message, type = "") {
    if (!adminToolsFeedback) {
        return;
    }
    adminToolsFeedback.textContent = message;
    adminToolsFeedback.className = `feedback-text${type ? ` ${type}` : ""}`;
}

function setSubmissionState(isSubmitting) {
    state.isSubmitting = isSubmitting;
    if (orderStatusChip) {
        orderStatusChip.textContent = isSubmitting ? "Sending" : "Ready";
    }
    const placeOrderButton = document.getElementById("place-order-btn");
    if (placeOrderButton) {
        placeOrderButton.disabled = isSubmitting;
    }
}

function updateMetric(id, value) {
    const node = document.getElementById(id);
    if (node) {
        node.textContent = value;
    }
}

function syncCurrentUser() {
    if (heroTraderName) {
        heroTraderName.textContent = currentUser || "Trader";
    }
    if (selectedTraderCard) {
        selectedTraderCard.textContent = "-- / --";
    }
}

function renderBookRows(container, rows, side) {
    if (!container) {
        return;
    }
    if (!rows.length) {
        container.innerHTML = '<div class="empty-state">Waiting for liquidity...</div>';
        return;
    }

    const maxRows = pageName === "user" ? 6 : 6;
    const maxQty = Math.max(...rows.map((row) => row.quantity), 1);
    container.innerHTML = rows
        .slice(0, maxRows)
        .map((row) => {
            const width = `${Math.max((row.quantity / maxQty) * 100, 10)}%`;
            return `
                <div class="book-row ${side}" style="--depth-width: ${width}">
                    <span class="book-price">${formatBookPrice(row.price)}</span>
                    <span class="book-qty">${row.quantity}</span>
                </div>
            `;
        })
        .join("");
}

function renderLeaderboard(rows) {
    if (!leaderboardBody) {
        return;
    }
    if (!rows.length) {
        const colspan = pageName === "admin" ? 5 : 4;
        leaderboardBody.innerHTML = `<tr><td colspan="${colspan}">No active players yet.</td></tr>`;
        return;
    }

    leaderboardBody.innerHTML = rows
        .map((trader, index) => {
            const holdingsClass = trader.holdings >= 0 ? "positive" : "negative";
            const rankCell = pageName === "admin" ? `<td data-label="Rank">#${index + 1}</td>` : "";
            return `
                <tr>
                    ${rankCell}
                    <td data-label="Trader">${trader.name}</td>
                    <td data-label="Holdings" class="${holdingsClass}">${trader.holdings}</td>
                    <td data-label="Cash">${formatCurrency(trader.cash)}</td>
                    <td data-label="Portfolio">${formatCurrency(trader.portfolio_value)}</td>
                </tr>
            `;
        })
        .join("");
}

function renderUserProfile(profile) {
    if (pageName !== "user" || !currentUser) {
        return;
    }
    const rank = profile?.rank || null;
    const totalPlayers = profile?.total_players || null;

    if (selectedTraderCard) {
        selectedTraderCard.textContent = rank && totalPlayers ? `Rank: ${rank}/ ${totalPlayers}` : "Rank: --/--";
    }

    if (profilePortfolio) {
        profilePortfolio.textContent = profile && profile.portfolio_value !== null ? formatCurrency(profile.portfolio_value) : "--";
    }
    if (profileCash) {
        profileCash.textContent = profile && profile.cash !== null ? formatCurrency(profile.cash) : "--";
    }
    if (profileHoldings) {
        profileHoldings.textContent = profile && profile.holdings !== null ? String(profile.holdings) : "--";
    }
    if (profileRank) {
        profileRank.textContent = rank ? `#${rank}` : "--";
    }
    if (topPortfolioValue) {
        topPortfolioValue.textContent = profile && profile.portfolio_value !== null ? formatCurrency(profile.portfolio_value) : "--";
    }
    if (topPortfolioSubtext) {
        topPortfolioSubtext.textContent = profile && profile.cash !== null ? `Cash ${formatCurrency(profile.cash)}` : "Cash --";
    }
}

function renderGameState(game) {
    if (!game) {
        return;
    }
    state.game = game;

    if (gamePhase) {
        gamePhase.textContent = game.status.charAt(0).toUpperCase() + game.status.slice(1);
        const gamePhasePill = gamePhase.closest(".mini-status");
        if (gamePhasePill) {
            gamePhasePill.classList.remove("mini-status-waiting", "mini-status-running", "mini-status-finished");
            gamePhasePill.classList.add(`mini-status-${game.status}`);
        }
    }
    if (gameTimer) {
        gameTimer.textContent = formatDuration(game.seconds_remaining);
    }

    if (pageName === "user" && !state.isSubmitting) {
        if (game.status === "waiting") {
            setFeedback("Waiting for admin to start the round.", "");
        } else if (game.status === "running") {
            setFeedback(`Round live. ${formatDuration(game.seconds_remaining)} remaining.`, "");
        } else if (game.status === "finished") {
            setFeedback("Round finished. Waiting for admin to reset the next game.", "success");
        }
    }
}

function updateSummary(orderBook, leaderboard, candles, game) {
    const bestBid = Number(orderBook.best_bid);
    const bestAsk = Number(orderBook.best_ask);
    const lastPrice = Number(orderBook.last_trading_price);
    const spread = Number.isFinite(bestAsk) && Number.isFinite(bestBid) ? bestAsk - bestBid : null;
    const mid = Number.isFinite(bestAsk) && Number.isFinite(bestBid) ? (bestAsk + bestBid) / 2 : null;
    const recent = candles[candles.length - 1];
    const recentVolume = recent && Number.isFinite(Number(recent.volume)) ? Number(recent.volume) : null;
    const range = recent ? Number(recent.high) - Number(recent.low) : null;
    const leaderText = leaderboard[0] ? `Leader ${leaderboard[0].name}` : "Leader --";

    updateMetric("ltp-value", formatCurrency(lastPrice));
    updateMetric("spread-value", spread === null ? "Spread --" : `Spread ${formatSigned(spread)}`);
    updateMetric("bid-ask-value", `${formatCurrency(bestBid)} / ${formatCurrency(bestAsk)}`);
    updateMetric("mid-value", mid === null ? "Mid --" : `Mid ${formatCurrency(mid)}`);
    updateMetric("range-value", range === null ? "--" : formatSigned(range));
    updateMetric("volume-value", recentVolume === null ? "Volume --" : `Volume ${recentVolume.toFixed(0)}`);
    const totalPlayers = game?.active_players?.length || leaderboard.length || traders.length;
    updateMetric("trader-count", String(totalPlayers));

    if (pageName === "user" && currentUser) {
        updateMetric("leader-value", leaderText);
        return;
    }

    updateMetric("leader-value", leaderText);
}

function updateChart(candles) {
    if (!candlestickSeries || !areaSeries || !chart) {
        return;
    }
    if (!candles.length) {
        candlestickSeries.setData([]);
        areaSeries.setData([]);
        return;
    }

    const formattedCandles = candles.map((candle) => ({
        time: Number(candle.time),
        open: Number(candle.open),
        high: Number(candle.high),
        low: Number(candle.low),
        close: Number(candle.close),
    }));

    const latestTime = formattedCandles[formattedCandles.length - 1].time;
    const defaultRangeStart = latestTime - 60;

    candlestickSeries.setData(formattedCandles);
    areaSeries.setData(
        formattedCandles.map((candle) => ({
            time: candle.time,
            value: candle.close,
        }))
    );

    if (!state.chartDefaultRangeApplied) {
        chart.timeScale().setVisibleRange({
            from: defaultRangeStart,
            to: latestTime,
        });
        state.chartDefaultRangeApplied = true;
    }
}

async function fetchDashboardData() {
    const [ohlcResponse, orderBookResponse, leaderboardResponse, gameResponse] = await Promise.all([
        fetch("/ohlc"),
        fetch("/orderbook"),
        fetch("/leaderboard"),
        fetch("/game"),
    ]);

    if (!ohlcResponse.ok || !orderBookResponse.ok || !leaderboardResponse.ok || !gameResponse.ok) {
        throw new Error("Failed to fetch market data");
    }

    const [candles, orderBook, leaderboard, game] = await Promise.all([
        ohlcResponse.json(),
        orderBookResponse.json(),
        leaderboardResponse.json(),
        gameResponse.json(),
    ]);

    return { candles, orderBook, leaderboard, game };
}

async function refreshDashboard() {
    try {
        const { candles, orderBook, leaderboard, game } = await fetchDashboardData();
        if (engineStatus) {
            engineStatus.textContent = "Live";
        }
        if (lastUpdated) {
            lastUpdated.textContent = new Date().toLocaleTimeString();
        }

        renderGameState(game);
        updateChart(candles);
        renderBookRows(
            bidsBook,
            (orderBook.bids || []).map((row) => ({
                price: Number(row.price),
                quantity: Number(row.quantity),
            })),
            "buy"
        );
        renderBookRows(
            asksBook,
            (orderBook.asks || []).map((row) => ({
                price: Number(row.price),
                quantity: Number(row.quantity),
            })),
            "sell"
        );
        renderLeaderboard(leaderboard || []);
        renderUserProfile(game?.current_user_profile || null);
        updateSummary(orderBook, leaderboard || [], candles || [], game || null);
    } catch (error) {
        if (engineStatus) {
            engineStatus.textContent = "Reconnect";
        }
        if (lastUpdated) {
            lastUpdated.textContent = "Fetch failed";
        }
    }
}

const orderForm = document.getElementById("order-form");
if (orderForm) {
    orderForm.addEventListener("submit", async (event) => {
        event.preventDefault();

        const submitter = event.submitter;
        if (submitter && submitter.dataset.side) {
            state.selectedSide = submitter.dataset.side;
        }

        const quantity = Number(quantityInput.value);
        if (!Number.isInteger(quantity) || quantity <= 0) {
            setFeedback("Enter a whole quantity greater than zero.", "error");
            return;
        }

        if (state.game && state.game.status === "finished") {
            setFeedback("Round finished. Waiting for admin to reset the next game.", "error");
            return;
        }

        if (state.game && state.game.status === "waiting") {
            setFeedback("Waiting for admin to start the round.", "error");
            return;
        }

        setSubmissionState(true);
        setFeedback("Routing order to the game engine...", "");

        try {
            const response = await fetch("/orders", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    side: state.selectedSide,
                    quantity,
                }),
            });

            const payload = await response.json();
            if (!response.ok || payload.error) {
                throw new Error(payload.error || "Order rejected");
            }

            setFeedback("Order accepted.", "success");
            quantityInput.value = "10";
            state.game = payload.game || state.game;
            renderGameState(state.game);
            await refreshDashboard();
        } catch (error) {
            setFeedback(error.message || "Order failed.", "error");
        } finally {
            setSubmissionState(false);
        }
    });
}

if (adminStartButton) {
    adminStartButton.addEventListener("click", async () => {
        const response = await fetch("/admin/round/start", { method: "POST" });
        const payload = await response.json();
        if (!response.ok || payload.error) {
            return;
        }
        state.game = payload.game || state.game;
        renderGameState(state.game);
        await refreshDashboard();
    });
}

if (adminResetButton) {
    adminResetButton.addEventListener("click", async () => {
        const response = await fetch("/admin/round/reset", { method: "POST" });
        const payload = await response.json();
        if (!response.ok || payload.error) {
            return;
        }
        state.game = payload.game || state.game;
        state.chartDefaultRangeApplied = false;
        renderGameState(state.game);
        await refreshDashboard();
    });
}

if (adminResetAllButton) {
    adminResetAllButton.addEventListener("click", async () => {
        const response = await fetch("/admin/reset-all", { method: "POST" });
        const payload = await response.json();
        if (!response.ok || payload.error) {
            return;
        }
        state.game = payload.game || state.game;
        state.chartDefaultRangeApplied = false;
        renderGameState(state.game);
        await refreshDashboard();
    });
}

if (loadTestButton) {
    loadTestButton.addEventListener("click", async () => {
        loadTestButton.disabled = true;

        try {
            const seedResponse = await fetch("/admin/players/seed", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    count: 100,
                    prefix: "noobot",
                }),
            });
            const seedPayload = await seedResponse.json();
            if (!seedResponse.ok || seedPayload.error) {
                throw new Error(seedPayload.error || "Failed to add bots.");
            }

            const burstResponse = await fetch("/orders/random", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    num_orders: 1500,
                    delay: 0.1,
                    prefix: "noobot",
                }),
            });
            const burstPayload = await burstResponse.json();
            if (!burstResponse.ok || burstPayload.error) {
                throw new Error(burstPayload.error || "Failed to start random burst.");
            }

            await refreshDashboard();
        } catch (error) {
            console.error(error);
        } finally {
            loadTestButton.disabled = false;
        }
    });
}

if (adminLogoutButton) {
    adminLogoutButton.addEventListener("click", async () => {
        await fetch("/admin/logout", { method: "POST" });
        window.location.href = "/admin";
    });
}

syncCurrentUser();
resizeChartToContainer();
renderGameState(state.game);
refreshDashboard();
setInterval(refreshDashboard, 1000);

window.addEventListener("load", resizeChartToContainer);
window.addEventListener("resize", resizeChartToContainer);
window.addEventListener("orientationchange", resizeChartToContainer);

if (chartContainer && typeof ResizeObserver !== "undefined") {
    const chartResizeObserver = new ResizeObserver(() => {
        resizeChartToContainer();
    });
    chartResizeObserver.observe(chartContainer);
}
