from datetime import datetime, timedelta
import requests
import pygal
from flask import Flask, render_template, request, url_for, flash, redirect, abort
import pandas as pd

# make a Flask application object called app
app = Flask(__name__)

# set up app to reload upon changes - used in development only
app.config["DEBUG"] = True
app.config['SECRET_KEY'] = 'your secret key' # move to .config or .env file in production

api_key = "SI1O16E6XH389GHD"

# convert string to datetime object
def str_to_datetime(str_date):
    return datetime.strptime(str_date, "%Y-%m-%d")

# get the start month for intraday time series
def get_start_year_month(start_date):
    # convert string to datetime
    dt_start_date = str_to_datetime(start_date)

    # isolate year and month
    year = dt_start_date.strftime("%Y")
    month = dt_start_date.strftime("%m")
    return (year + "-" + month)

# create URL endpoints for API requests (returns URL)
def create_url_endpoint(timeseries, symbol, start_date, api_key):
    if timeseries == "intradaily":
        function = "TIME_SERIES_INTRADAY"
        interval = "5min"
        month = get_start_year_month(start_date)
        return f'https://www.alphavantage.co/query?function={function}&symbol={symbol}&outputsize=full&interval={interval}&month={month}&apikey={api_key}'
    elif timeseries == "daily":
        function = "TIME_SERIES_DAILY"
        return f'https://www.alphavantage.co/query?function={function}&symbol={symbol}&outputsize=full&apikey={api_key}'
    elif timeseries == "weekly":
        function = "TIME_SERIES_WEEKLY"
        return f'https://www.alphavantage.co/query?function={function}&symbol={symbol}&apikey={api_key}'
    elif timeseries == "monthly":
        function = "TIME_SERIES_MONTHLY"
        return f'https://www.alphavantage.co/query?function={function}&symbol={symbol}&apikey={api_key}'

# fetch API data from URL (returns None upon error)
def get_api_data(url):

    print("Requesting URL:", url)
    r = requests.get(url)
    try:
        data = r.json()
    except Exception as e:
        print("Error parsing JSON response:", e)
        print("Response text (truncated):", r.text[:1000])
        return None

    # err check: network/api failure
    if r.status_code != 200:
        print("\nError: Failed to retrieve data from API")
        return None
    
    if not isinstance(data,dict):
        print("\nError: Unexpected API response")
        return None

    # err checks: api error / rate-limit notice
    if "Error Message" in data:
        print("\nError: Invalid symbol or API request")
        return None

    if "Note" in data:
        print("\nAPI rate limit reached, please try again later")
        return None
    
    return data

# format data and generate chart (returns chart file name)
def create_chart(data, symbol, chart_type, timeseries, start_date, end_date):

    # check for valid data
    time_series_key = None
    for key in data:
        if "Time Series" in key:
            time_series_key = key
            break

    if not time_series_key:
        print("Error: Time series data not found in the response.")
        return None

    # format data for chart
    raw_series = data[time_series_key]

    dates = []
    open_prices = []
    high_prices = []
    low_prices = []
    close_prices = []

    for date_str in sorted(raw_series.keys(), reverse=False):
        if timeseries == "intradaily":
            dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        else:
            dt = datetime.strptime(date_str, "%Y-%m-%d")

        if start_date <= str(dt.date()) <= end_date:
            dates.append(date_str)
            open_prices.append(float(raw_series[date_str]['1. open']))
            high_prices.append(float(raw_series[date_str]['2. high']))
            low_prices.append(float(raw_series[date_str]['3. low']))
            close_prices.append(float(raw_series[date_str]['4. close']))

    # error check: no data in selected range
    if not dates:
        print("\nError: No stock data found for the selected date range")
        return None

    # convert start and end dates to datetime
    dt_start_date = str_to_datetime(start_date)
    dt_end_date = str_to_datetime(end_date)

    # calculate distance between start and end dates
    distance = (dt_end_date - dt_start_date).days
    print(f"distance between start and end date: {distance} day(s)")

    # create chart
    if chart_type == "bar":
        # check timeseries and distance to determine x-tick settings
        if timeseries == "intradaily":
            chart = pygal.Bar(x_label_rotation=20, x_labels_major_every=75, show_minor_x_labels=False)
        # elif distance > 5:
        #     chart = pygal.Bar(x_label_rotation=20, x_labels_major_every=5, show_minor_x_labels=False)
        else: 
            chart = pygal.Bar(x_label_rotation=20)
    else:
        # check timeseries and distance to determine x-tick settings
        if timeseries == "intradaily":
            chart = pygal.Line(x_label_rotation=20, x_labels_major_every=45, show_minor_x_labels=False)
        # elif distance > 5:
        #     chart = pygal.Line(x_label_rotation=20, x_labels_major_every=5, show_minor_x_labels=False)
        else:
            chart = pygal.Line(x_label_rotation=20)

    chart.title = f"{timeseries.capitalize()} Stock Data for {symbol.upper()}: {start_date} to {end_date}"
    chart.x_labels = dates
    chart.add('Open', open_prices)
    chart.add('High', high_prices)
    chart.add('Low', low_prices)
    chart.add('Close', close_prices)

    # Render to file in static folder
    chart_file = 'stock_chart.svg'
    chart.render_to_file('static/' + chart_file)
    return chart_file

# add stock info (Symbol, Name, Sector)
stocks = pd.read_csv('./static/stocks.csv')
stocks = stocks.drop('Sector', axis=1) # drop sector column
stock_info = stocks.to_dict(orient='records') # convert to a list of dictionaries

@app.route('/', methods=('GET', 'POST'))
def index():
    if request.method == 'POST':
        # get the stock symbol, chart type, time series, and dates from user input
        symbol = request.form['symbol']
        chart_type = request.form['chart_type']
        timeseries = request.form['timeseries']
        start_date = request.form['start_date']
        end_date = request.form['end_date']

        # error check the user input
        if not symbol:
            flash("Symbol is required.")
        elif not chart_type:
            flash("Chart type is required.")
        elif not timeseries:
            flash("Time series is required.")
        elif end_date < start_date:
            flash(f"End date cannot be earlier than the start date. Please enter a date earlier or equal to the start date ({start_date}).")
        else:
            # make API request
            url = create_url_endpoint(timeseries, symbol, start_date, api_key)
            data = get_api_data(url)
            
            if data is None:
                flash("Unable to retrieve data. Please try again.")
                return render_template('index.html', stock_info=stock_info)
            
            # generate chart
            chart_file = create_chart(data, symbol, chart_type, timeseries, start_date, end_date)

            if chart_file is None:
                flash("Unable to generate chart. Please try again.")
                return render_template('index.html', stock_info=stock_info)

            # send url to be displayed via chart template        
            chart_file_url = url_for('static', filename=chart_file)
            return render_template('chart.html', stock_info=stock_info, chart=chart_file_url)

    return render_template('index.html', stock_info=stock_info)

# tells the application in the container to listen on all ports
app.run(host="0.0.0.0")