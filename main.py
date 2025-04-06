from AlgorithmImports import *
# endregion
from datetime import timedelta
import numpy as np
class FifteenDeltaRRSPY(QCAlgorithm):
    def initialize(self) -> None:
        self.set_start_date(2010, 1, 5)
        self.set_end_date(2016, 1, 5)
        self.set_account_currency("USD")
        self.set_cash(100000)
        # Ensure USSecurities is properly imported or defined
        self.spy = self.add_equity("SPY", Resolution.DAILY).symbol
        self.spy_price = 0
        option = self.add_option("SPY")
        option.set_filter(-30, 30, timedelta(20), timedelta(30))
        self.option_symbol = option.symbol
        self.schedule.on(
            self.date_rules.every_day("SPY"),
            self.time_rules.after_market_open("SPY", 5),
            self.daily_trade_logic
        )
        self.delta_target = 0.15
        self.delta_band = (0.20, 0.40)
        self.days_to_expiry = 25
        self.days_to_close = 5
        self.days_held = 0
        self.current_contracts: dict[str, Symbol] = {}
        self.performance = {
            "daily_returns": [],
            "portfolio_values": [],
            "last_value": self.portfolio.total_portfolio_value,
        }
    def on_data(self, data: Slice) -> None:
        if data.contains_key(self.spy):
            bar = data[self.spy]
            self.spy_price = bar.close if isinstance(bar, TradeBar) else bar.last_price
    def daily_trade_logic(self):
        self.track_daily_performance()
        if not self.portfolio.invested:
            self.enter_risk_reversal()
        elif self.days_held >= (self.days_to_expiry - self.days_to_close):
            self.liquidate()
            self.enter_risk_reversal()
        else:
            self.rebalance_if_needed()
        self.days_held += 1
    def enter_risk_reversal(self):
        chain = self.current_slice.option_chains.get(self.option_symbol)
        if not chain:
            return
        contracts = sorted(chain, key=lambda x: x.expiry)
        expiry = min(set([c.expiry for c in contracts if (20 <= (c.expiry - self.time).days <= 30)]), default=None)
        if not expiry:
            return
        puts = [c for c in contracts if c.right == OptionRight.PUT and c.expiry == expiry]
        calls = [c for c in contracts if c.right == OptionRight.CALL and c.expiry == expiry]
        if not puts or not calls:
            return
        put = min(puts, key=lambda c: abs(c.greeks.delta + self.delta_target))
        call = min(calls, key=lambda c: abs(c.greeks.delta - self.delta_target))
        quantity = 1
        self.market_order(put.symbol, -quantity)
        self.market_order(call.symbol, quantity)
        self.market_order(self.spy, -30)
        self.current_contracts = {"put": put.symbol, "call": call.symbol}
        self.days_held = 0
    def rebalance_if_needed(self):
        if not self.current_contracts:
            return
        put_delta = self.securities[self.current_contracts["put"]].greeks.delta
        call_delta = self.securities[self.current_contracts["call"]].greeks.delta
        net_delta = put_delta + call_delta
        if net_delta < self.delta_band[0] or net_delta > self.delta_band[1]:
            self.liquidate()
            self.enter_risk_reversal()
    def track_daily_performance(self):
        current_value = self.portfolio.total_portfolio_value
        last_value = self.performance["last_value"]
        daily_return = (current_value - last_value) / last_value
        self.performance["daily_returns"].append(daily_return)
        self.performance["portfolio_values"].append(current_value)
        self.performance["last_value"] = current_value
        cumulative_return = (current_value / self.performance["portfolio_values"][0]) - 1
        if len(self.performance["daily_returns"]) > 2:
            mean_return = np.mean(self.performance["daily_returns"])
            std_dev = np.std(self.performance["daily_returns"])
            sharpe = (mean_return / std_dev) * np.sqrt(252) if std_dev != 0 else 0
        else:
            sharpe = 0





