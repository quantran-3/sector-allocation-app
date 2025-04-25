import pandas as pd
import yfinance as yf
from datetime import datetime

def get_price(symbol):
    """Enhanced price fetching for stocks, ETFs, and mutual funds"""
    try:
        ticker = yf.Ticker(symbol)
        
        # Try multiple methods to get the price
        # Method 1: Current Price
        price = ticker.info.get('currentPrice')
        if price:
            return price
            
        # Method 2: Regular Market Price
        price = ticker.info.get('regularMarketPrice')
        if price:
            return price
            
        # Method 3: Latest Historical Close (good for mutual funds)
        hist = ticker.history(period='1d')
        if not hist.empty:
            return hist['Close'].iloc[-1]
            
        # Method 4: Previous Close
        price = ticker.info.get('previousClose')
        if price:
            return price
            
        print(f"No price data found for {symbol}")
        return None
        
    except Exception as e:
        print(f"Error fetching price for {symbol}: {e}")
        return None

def create_portfolio():
    """Create portfolio DataFrame with your holdings"""
    portfolio_data = [
        ['AAPL', 'Apple', 'Information Technology', 7],
        ['ALT', 'Altimmune', 'Health Care', 12],
        ['AMD', 'Advanced Micro Devices', 'Information Technology', .683],
        ['ASML', 'Asml Holding ADR Representing', 'Information Technology', .213],
        ['BA', 'Boeing', 'Industrials', 0.289],
        ['BRK-B', 'Berkshire Hathaway Class B', 'Financials', 6],
        ['CMG', 'Chipotle Mexican Grill', 'Consumer Discretionary', 10],
        ['CRWD', 'Crowdstrike Holdings Class A', 'Information Technology', .16],
        ['CSX', 'Csx', 'Industrials', 36],
        ['ESPR', 'Esperion Therapeutics', 'Health Care', 75],
        ['FBGRX', 'Fidelity Blue Chip Growth Fund', 'ETF', 6.419],
        ['FBTC', 'Fidelity Wise Origin Bitcoin Fund', 'ETF', 1.333],
        ['GH', 'Guardant Health', 'Health Care', 20],
        ['IBRX', 'Immunitybio', 'Health Care', 10],
        ['INTC', 'Intel', 'Information Technology', 1.732],
        ['IOVA', 'Iovance Biotherapeutics', 'Health Care', 25],
        ['JPM', 'Jpmorgan Chase', 'Financials', .084],
        ['LMT', 'Lockheed Martin', 'Industrials', .018],
        ['MDWD', 'Mediwound', 'Health Care', 5],
        ['NNE', 'Nano Nuclear Energy', 'Industrials', 2.855],
        ['NVDA', 'NVIDIA', 'Information Technology', 18],
        ['OKLO', 'Oklo Class A', 'Utilities', 3.16],
        ['ORCL', 'Oracle', 'Information Technology', .187],
        ['OXY', 'Occidental Petroleum', 'Energy', 5],
        ['PLTR', 'Palantir Technologies Class A', 'Information Technology', .094],
        ['QCOM', 'QUALCOMM', 'Information Technology', .5],
        ['SBUX', 'Starbucks', 'Consumer Discretionary', 4],
        ['SCHD', 'Schwab US Dividen Equity ETF', 'ETF', 1.747],
        ['SCHW', 'Charles Schwab', 'Financials', 16],
        ['SONY', 'Sony Group ADR Representing', 'Consumer Discretionary', 30],
        ['TSLA', 'Tesla', 'Consumer Discretionary', .47],
        ['TSM', 'Taiwan Semiconductor Manufacturing ADR Representing 5', 'Information Technology', 2],
        ['VFH', 'Vanguard Financials Index Fund ETF', 'ETF', .357],
        ['VOO', 'Vanguard 500 Index Fund ETF', 'ETF', 2.118],
        ['VRNA', 'Verona Pharma ADR', 'Health Care', 15],
        ['VTI', 'Vanguard Total Stock Market Index Fund ETF', 'ETF', 13]
    ]
    
    # Create DataFrame
    df = pd.DataFrame(portfolio_data, 
                     columns=['Symbol', 'Company', 'Sector', 'Shares'])
    return df

def update_portfolio_prices(df):
    """Update portfolio with current prices and calculate values"""
    # Add or ensure required columns exist
    if 'Current Price' not in df.columns:
        df['Current Price'] = 0.0
    if 'Total Value' not in df.columns:
        df['Total Value'] = 0.0
    if 'Last Updated' not in df.columns:
        df['Last Updated'] = None
    
    # Update prices and calculate values
    for index, row in df.iterrows():
        price = get_price(row['Symbol'])
        if price:
            df.at[index, 'Current Price'] = price
            df.at[index, 'Total Value'] = price * float(row['Shares'])
            df.at[index, 'Last Updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"Updated {row['Symbol']}: ${price:.2f}")
        else:
            print(f"Could not update price for {row['Symbol']}")
    
    return df

def calculate_sector_allocation(df):
    """Calculate sector allocations and summary"""
    sector_summary = df.groupby('Sector').agg({
        'Total Value': 'sum'
    }).reset_index()
    
    total_portfolio = df['Total Value'].sum()
    sector_summary['Percentage'] = (sector_summary['Total Value'] / total_portfolio * 100).round(2)
    sector_summary = sector_summary.sort_values('Percentage', ascending=False)
    
    return sector_summary

if __name__ == "__main__":
    print("Portfolio Tracker Starting...")
    print("-" * 50)
    
    # Create and update portfolio
    portfolio = create_portfolio()
    print("\nInitial Portfolio Structure:")
    print(portfolio[['Symbol', 'Company', 'Sector', 'Shares']].to_string())
    
    # Update prices
    portfolio = update_portfolio_prices(portfolio)
    
    # Calculate sector allocation
    sector_summary = calculate_sector_allocation(portfolio)
    
    # Print results
    print("\nUpdated Portfolio:")
    print(portfolio.to_string())
    
    print("\nSector Allocation:")
    print(sector_summary.to_string())
    
    # Print summary statistics
    total_value = portfolio['Total Value'].sum()
    print(f"\nTotal Portfolio Value: ${total_value:,.2f}")
    
    # Count securities by type
    stock_count = len(portfolio[~portfolio['Sector'].isin(['ETF'])])
    etf_count = len(portfolio[portfolio['Sector'] == 'ETF'])
    print(f"\nPortfolio Composition:")
    print(f"Stocks: {stock_count}")
    print(f"ETFs: {etf_count}")