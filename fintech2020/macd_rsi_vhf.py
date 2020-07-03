# part of the copyright is owned by Crypto Arsenal
# https://github.com/Crypto-Arsenal/public-docs
class Strategy():
	# option setting needed
	def __setitem__(self, key, value):
		self.options[key] = value

	# option setting needed
	def __getitem__(self, key):
		return self.options.get(key, '')

	def __init__(self):
		# strategy property
		self.subscribedBooks = {
			'Binance': {
				'pairs': ['BTC-USDT'],
			},
		}
		self.period = 60 * 5
		self.options = {}

		# user defined class attribute
		self.last_type = 'sell'
		self.last_cross = None
		self.close_price_trace = np.array([])
		self.ma_long = 26
		self.ma_short = 12
		self.UP = 1
		self.DOWN = 2
		self.trading_times = 1
		self.remain_trading_times = self.trading_times
		self.last_buying_price = 0
		self.stop_profit_rate = 1.2
		self.stop_loss_rate = 0.95

		#switch
		self.ma_switch = 0
		self.macd_switch = 1

		self.rsi_switch = 1
		self.vhf_switch = 1
		self.price_switch = 0

	# short ma is upper or lower than long ma
	def get_ma_status(self):
		s_ma = talib.EMA(self.close_price_trace, self.ma_short)[-1]
		l_ma = talib.EMA(self.close_price_trace, self.ma_long)[-1]
		if np.isnan(s_ma) or np.isnan(l_ma):
			return None
		if s_ma > l_ma:
			return self.UP
		return self.DOWN

	# dif is upper or lower than dea
	def get_macd_status(self):
		dif, dea, macd = talib.MACD(self.close_price_trace, fastperiod = 12, slowperiod = 26, signalperiod = 9)
		return_value = self.UP if (dif[-1] - dea[-1] > 0) else self.DOWN
		return return_value

	# check if there's a golden cross or death cross
	def get_cross_status(self, last_type, current_status, last_status):
		if last_type == 'sell' and current_status == self.UP and last_status == self.DOWN:
			return self.UP
		elif last_type == 'buy' and current_status == self.DOWN and last_status == self.UP:
			return self.DOWN
		else:
			return 0

	# check recent trend
	def get_rsi_status(self, ma):
		rsi =  talib.RSI(self.close_price_trace, ma)[-1]
		if rsi >= 0 and rsi <= 20:
			return self.UP
		elif rsi >= 50 and rsi <= 80:
			return self.UP
		else:
			return self.DOWN

	# check recent volatility
	def get_vhf_status(self):
		last_high_close_price = np.amax(self.close_price_trace)
		last_low_close_price = np.amin(self.close_price_trace)
		numerator = last_high_close_price - last_low_close_price
		denominator = 0
		for i in range(len(self.close_price_trace) - 1):
			temp = self.close_price_trace[i] - self.close_price_trace[i + 1]
			if temp < 0:
				temp = -temp
			denominator += temp
		vhf = 1 if (denominator == 0) else (numerator / denominator)
		return_value = 1 if (vhf > 0.3) else 0
		return return_value

	# check if the price exceeds the stop profit point or stop loss point
	def get_price_status(self):
		return_value = 1 if (self.close_price_trace[-1] > self.stop_profit_rate * self.last_buying_price or self.close_price_trace[-1] < self.stop_loss_rate * self.last_buying_price) else 0
		return return_value

	# called every self.period
	def trade(self, information):

		exchange = list(information['candles'])[0]
		pair = list(information['candles'][exchange])[0]
		close_price = information['candles'][exchange][pair][0]['close']
		# add latest price into trace
		self.close_price_trace = np.append(self.close_price_trace, [float(close_price)])
		# only keep max length of ma_long count elements
		if self.ma_switch == 1:
			self.close_price_trace = self.close_price_trace[-(self.ma_long + 10):]
			cur_cross = self.get_ma_status()
		elif self.macd_switch == 1:
			self.close_price_trace = self.close_price_trace[-40:]
			cur_cross = self.get_macd_status()

		if cur_cross is None:
			return []
		if self.last_cross is None:
			self.last_cross = cur_cross
			return []

		cross_status = self.get_cross_status(self.last_type, cur_cross, self.last_cross)
		rsi_status = self.get_rsi_status(self.ma_short)
		vhf_status = self.get_vhf_status()

		# cross up
		# if there's a golden cross, then buy
		if (vhf_status == 1 or self.vhf_switch == 0) and (rsi_status == self.UP or self.rsi_switch == 0) and (cross_status == self.UP):
			self.last_buying_price = float(close_price)
			# if the signal turns to buy when selling, change the remain trading times
			if (self.remain_trading_times != self.trading_times and self.last_type == 'buy'):
				self.remain_trading_times = self.trading_times - self.remain_trading_times
			# divide assets into several parts 
			amount = information['assets'][exchange]['USDT'] / float(close_price) / self.remain_trading_times
			self.remain_trading_times -= 1
			if self.remain_trading_times == 0:
				self.last_type = 'buy'
				self.last_cross = cur_cross
				self.remain_trading_times = self.trading_times

			return [
				{
					'exchange': exchange,
					'amount': amount,
					'price': -1,
					'type': 'MARKET',
					'pair': pair,
				}
			]

		# cross down
		# if the price exceeds the stop profit point or stop loss point, then sell
		# if there's a death cross, then sell
		elif ((self.get_price_status() == 1 and self.last_type == 'buy') and self.price_switch == 1) or ((vhf_status == 1 or self.vhf_switch == 0) and (rsi_status == self.DOWN or self.rsi_switch == 0) and (cross_status == self.DOWN)):
			# if the signal turns to sell when buying, change the remain trading times
			if (self.remain_trading_times != self.trading_times and self.last_type == 'sell'):
				self.remain_trading_times = self.trading_times - self.remain_trading_times
			# divide assets into several parts 
			amount = information['assets'][exchange]['BTC']	/ self.remain_trading_times
			self.remain_trading_times -= 1
			if self.remain_trading_times == 0:
				self.last_type = 'sell'
				self.last_cross = cur_cross
				self.remain_trading_times = self.trading_times

			return [
				{
					'exchange': exchange,
					'amount': -amount,
					'price': -1,
					'type': 'MARKET',
					'pair': pair,
				}
			]
		self.last_cross = cur_cross
		return []
