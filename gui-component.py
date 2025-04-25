import os
import sys
from io import StringIO

# Import PyQt6 components
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QVBoxLayout, QHBoxLayout, 
    QWidget, QLabel, QPushButton, QTableWidget, QTableWidgetItem, 
    QLineEdit, QComboBox, QDoubleSpinBox, QMessageBox, QFileDialog,
    QDialog, QFormLayout, QDialogButtonBox, QGroupBox, QSplitter
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QActionGroup

# Set up matplotlib to use PyQt6
import matplotlib
matplotlib.use('QtAgg')

# Now import the canvas
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

import pandas as pd
try:
    import openpyxl  # For xlsx files
    import xlrd      # For xls files
    EXCEL_SUPPORT = True
except ImportError:
    EXCEL_SUPPORT = False
import yfinance as yf

import matplotlib.pyplot as plt
from datetime import datetime
import json

# Set up Qt environment
os.environ['QT_API'] = 'pyqt6'


class StockSearchDialog(QDialog):
    """Dialog for searching and adding stocks to portfolio"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add New Position")
        self.setMinimumWidth(500)
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Search form
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Symbol:"))
        self.symbol_input = QLineEdit()
        search_layout.addWidget(self.symbol_input)
        
        self.search_btn = QPushButton("Search")
        self.search_btn.clicked.connect(self.search_stock)
        search_layout.addWidget(self.search_btn)
        layout.addLayout(search_layout)
        
        # Stock info group
        self.stock_info_group = QGroupBox("Stock Information")
        self.stock_info_group.setVisible(False)
        stock_info_layout = QFormLayout()
        
        self.name_label = QLabel("")
        stock_info_layout.addRow("Name:", self.name_label)
        
        self.sector_label = QLabel("")
        stock_info_layout.addRow("Sector:", self.sector_label)
        
        self.current_price_label = QLabel("")
        stock_info_layout.addRow("Current Price:", self.current_price_label)
        
        self.stock_info_group.setLayout(stock_info_layout)
        layout.addWidget(self.stock_info_group)
        
        # Position details
        position_group = QGroupBox("Position Details")
        position_layout = QFormLayout()
        
        self.shares_input = QDoubleSpinBox()
        self.shares_input.setDecimals(3)
        self.shares_input.setRange(0.001, 100000)
        self.shares_input.setValue(1)
        position_layout.addRow("Shares:", self.shares_input)
        
        position_group.setLayout(position_layout)
        layout.addWidget(position_group)
        
        # Dialog buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | 
                                          QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.button_ok = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        self.button_ok.setEnabled(False)
        
        layout.addWidget(self.button_box)
        self.setLayout(layout)
        
        # Store stock data
        self.stock_data = None
        
    def search_stock(self):
        """Search for stock information by symbol"""
        symbol = self.symbol_input.text().strip().upper()
        if not symbol:
            QMessageBox.warning(self, "Input Error", "Please enter a stock symbol")
            return
            
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            # Check if we got valid data
            if not info or 'shortName' not in info:
                QMessageBox.warning(self, "Stock Not Found", 
                                   f"Could not find information for {symbol}")
                return
                
            # Store stock data
            self.stock_data = {
                'symbol': symbol,
                'name': info.get('shortName', 'Unknown'),
                'sector': info.get('sector', 'Unknown'),
                'price': info.get('currentPrice', 
                                 info.get('regularMarketPrice', 
                                         info.get('previousClose', 0)))
            }
            
            # Update UI
            self.name_label.setText(self.stock_data['name'])
            self.sector_label.setText(self.stock_data['sector'])
            self.current_price_label.setText(f"${self.stock_data['price']:.2f}")
            self.stock_info_group.setVisible(True)
            self.button_ok.setEnabled(True)
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error fetching stock data: {str(e)}")
    
    def get_position_data(self):
        """Return the position data entered by user"""
        if not self.stock_data:
            return None
            
        return {
            'Symbol': self.stock_data['symbol'],
            'Company': self.stock_data['name'],
            'Sector': self.stock_data['sector'],
            'Shares': self.shares_input.value(),
            'Current Price': self.stock_data['price'],
            'Total Value': self.stock_data['price'] * self.shares_input.value(),
            'Last Updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }


class PieChartWidget(FigureCanvas):
    """Widget for displaying a pie chart"""
    
    def __init__(self, parent=None, width=5, height=5, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        super().__init__(fig)
        self.setParent(parent)
        fig.tight_layout()
    
    def plot_sector_allocation(self, sector_data):
        """Plot sector allocation pie chart"""
        self.axes.clear()
        
        if sector_data.empty:
            self.axes.text(0.5, 0.5, "No data available", 
                          ha='center', va='center', fontsize=12)
            self.draw()
            return
        
        # Extract data
        labels = sector_data['Sector'].tolist()
        sizes = sector_data['Percentage'].tolist()
        
        # Generate colors
        colors = plt.cm.tab10(range(len(labels)))
        
        # Create pie chart
        self.axes.pie(sizes, labels=labels, autopct='%1.1f%%', 
                     startangle=90, colors=colors)
        self.axes.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle
        self.axes.set_title('Portfolio Sector Allocation')
        
        self.draw()


class PortfolioService:
    """Service class for handling portfolio operations"""
    
    def __init__(self):
        self.data_file = "portfolio_data.json"
        
    def get_security_type(self, symbol):
        """Determine the type of security (Stock, ETF, Mutual Fund, etc.)"""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            # Check if it's an ETF
            if 'etf' in info.get('quoteType', '').lower() or symbol.endswith('F'):
                return "ETF"
            
            # Check if it's a mutual fund
            if 'mutualFund' in info.get('quoteType', '').lower() or symbol.endswith('X'):
                return "Mutual Fund"
                
            # Check if it's an index
            if 'index' in info.get('quoteType', '').lower():
                return "Index"
                
            # Otherwise assume it's a stock
            return "Stock"
            
        except Exception:
            # If we can't determine, default to stock
            return "Stock"
            
    def get_etf_sector_classification(self, symbol):
        """Classify ETFs by type/sector based on name and info"""
        try:
            ticker = yf.Ticker(symbol)
            name = ticker.info.get('shortName', '').lower()
            
            # Check for common ETF types in the name
            if any(term in name for term in ['bond', 'treasury', 'income']):
                return "Bond ETF"
            elif any(term in name for term in ['nasdaq', 'tech', 'technology']):
                return "Technology ETF"
            elif any(term in name for term in ['s&p', 'sp500', '500', 'total market']):
                return "Index ETF"
            elif any(term in name for term in ['health', 'healthcare']):
                return "Healthcare ETF"
            elif any(term in name for term in ['energy', 'oil', 'gas']):
                return "Energy ETF"
            elif any(term in name for term in ['financial', 'bank']):
                return "Financial ETF"
            elif any(term in name for term in ['dividend', 'yield']):
                return "Dividend ETF"
            elif any(term in name for term in ['growth']):
                return "Growth ETF"
            elif any(term in name for term in ['value']):
                return "Value ETF"
            elif any(term in name for term in ['bitcoin', 'crypto']):
                return "Crypto ETF"
            else:
                return "ETF"
                
        except Exception:
            return "ETF"
        
    def get_price(self, symbol):
        """Enhanced price fetching for stocks, ETFs, and mutual funds"""
        try:
            ticker = yf.Ticker(symbol)
            
            # Try multiple methods to get the price
            price = ticker.info.get('currentPrice')
            if price:
                return price
                
            price = ticker.info.get('regularMarketPrice')
            if price:
                return price
                
            hist = ticker.history(period='1d')
            if not hist.empty:
                return hist['Close'].iloc[-1]
                
            price = ticker.info.get('previousClose')
            if price:
                return price
                
            return None
            
        except Exception as e:
            print(f"Error fetching price for {symbol}: {e}")
            return None
    
    def save_portfolio(self, df):
        """Save portfolio to JSON file"""
        try:
            # Convert DataFrame to JSON
            json_data = df.to_json(orient='records')
            with open(self.data_file, 'w') as f:
                f.write(json_data)
            return True
        except Exception as e:
            print(f"Error saving portfolio: {e}")
            return False
    
    def load_portfolio(self):
        """Load portfolio from JSON file"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r') as f:
                    json_data = f.read()
                # Use StringIO to avoid the FutureWarning
                df = pd.read_json(StringIO(json_data), orient='records')
                return df
            else:
                # Return empty DataFrame with correct columns
                return pd.DataFrame(columns=[
                'Symbol', 'Company', 'Sector', 'Shares', 
                'Current Price', 'Total Value', 'Last Updated'
            ])
        except Exception as e:
            print(f"Error loading portfolio: {e}")
            return pd.DataFrame(columns=[
            'Symbol', 'Company', 'Sector', 'Shares', 
            'Current Price', 'Total Value', 'Last Updated'
        ])
    
    def update_portfolio_prices(self, df):
        """Update portfolio with current prices and calculate values"""
        if df.empty:
            return df
            
        # Add required columns if they don't exist
        if 'Current Price' not in df.columns:
            df['Current Price'] = 0.0
        if 'Total Value' not in df.columns:
            df['Total Value'] = 0.0
        if 'Last Updated' not in df.columns:
            df['Last Updated'] = None
            
        # Update prices and calculate values
        for index, row in df.iterrows():
            price = self.get_price(row['Symbol'])
            if price:
                df.at[index, 'Current Price'] = price
                df.at[index, 'Total Value'] = price * float(row['Shares'])
                df.at[index, 'Last Updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
        return df
    
    def calculate_sector_allocation(self, df):
        """Calculate sector allocations"""
        if df.empty or 'Total Value' not in df.columns:
            return pd.DataFrame(columns=['Sector', 'Total Value', 'Percentage'])
            
        sector_summary = df.groupby('Sector').agg({
            'Total Value': 'sum'
        }).reset_index()
        
        total_portfolio = df['Total Value'].sum()
        if total_portfolio > 0:
            sector_summary['Percentage'] = (sector_summary['Total Value'] / total_portfolio * 100).round(2)
        else:
            sector_summary['Percentage'] = 0
            
        sector_summary = sector_summary.sort_values('Percentage', ascending=False)
        
        return sector_summary


class PortfolioTableWidget(QTableWidget):
    """Custom table widget for displaying portfolio data"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        
    def init_ui(self):
        # Set up table headers
        headers = ["Symbol", "Company", "Sector", "Shares", 
                  "Current Price", "Total Value", "Last Updated"]
        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setAlternatingRowColors(True)
        
        # Set column widths
        self.setColumnWidth(0, 80)  # Symbol
        self.setColumnWidth(1, 200)  # Company
        self.setColumnWidth(2, 150)  # Sector
        self.setColumnWidth(3, 80)   # Shares
        self.setColumnWidth(4, 100)  # Current Price
        self.setColumnWidth(5, 120)  # Total Value
        self.setColumnWidth(6, 150)  # Last Updated
    
    def update_from_dataframe(self, df):
        """Update table data from pandas DataFrame"""
        self.setRowCount(0)  # Clear existing rows
        
        if df.empty:
            return
            
        # Add rows from DataFrame
        for idx, row in df.iterrows():
            self.insertRow(self.rowCount())
            self.setItem(self.rowCount()-1, 0, QTableWidgetItem(str(row['Symbol'])))
            self.setItem(self.rowCount()-1, 1, QTableWidgetItem(str(row['Company'])))
            self.setItem(self.rowCount()-1, 2, QTableWidgetItem(str(row['Sector'])))
            self.setItem(self.rowCount()-1, 3, QTableWidgetItem(f"{float(row['Shares']):.3f}"))
            
            # Format price with color based on value
            price_item = QTableWidgetItem(f"${float(row['Current Price']):.2f}")
            self.setItem(self.rowCount()-1, 4, price_item)
            
            # Format total value
            value_item = QTableWidgetItem(f"${float(row['Total Value']):.2f}")
            self.setItem(self.rowCount()-1, 5, value_item)
            
            # Last updated
            if 'Last Updated' in row and row['Last Updated']:
                self.setItem(self.rowCount()-1, 6, QTableWidgetItem(str(row['Last Updated'])))
            else:
                self.setItem(self.rowCount()-1, 6, QTableWidgetItem("Never"))


class PortfolioOverviewTab(QWidget):
    """Tab showing overview of portfolio"""
    
    portfolio_updated = pyqtSignal(pd.DataFrame)
    
    def __init__(self, portfolio_service):
        super().__init__()
        self.portfolio_service = portfolio_service
        self.portfolio_df = None
        self.init_ui()
        
    def init_ui(self):
        main_layout = QVBoxLayout()
    
        # Top controls
        controls_layout = QHBoxLayout()
        
        add_btn = QPushButton("Add Position")
        add_btn.clicked.connect(self.add_position)
        controls_layout.addWidget(add_btn)
        
        # Add import button here
        import_btn = QPushButton("Import Spreadsheet")
        import_btn.clicked.connect(self.import_spreadsheet)
        controls_layout.addWidget(import_btn)
        
        refresh_btn = QPushButton("Refresh Prices")
        refresh_btn.clicked.connect(self.refresh_portfolio)
        controls_layout.addWidget(refresh_btn)
            
        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self.remove_selected)
        controls_layout.addWidget(remove_btn)
        
        controls_layout.addStretch()
        
        self.summary_label = QLabel("Portfolio Summary")
        self.summary_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        controls_layout.addWidget(self.summary_label)
        
        main_layout.addLayout(controls_layout)
        
        # Portfolio table
        self.portfolio_table = PortfolioTableWidget()
        main_layout.addWidget(self.portfolio_table)
        
        self.setLayout(main_layout)
        
        # Load initial data
        self.load_portfolio()
        
    def load_portfolio(self):
        """Load portfolio data"""
        self.portfolio_df = self.portfolio_service.load_portfolio()
        self.update_display()
        
    def update_display(self):
        """Update UI with current portfolio data"""
        if self.portfolio_df is not None:
            self.portfolio_table.update_from_dataframe(self.portfolio_df)
            
            # Update summary
            total_value = self.portfolio_df['Total Value'].sum() if 'Total Value' in self.portfolio_df.columns and not self.portfolio_df.empty else 0
            item_count = len(self.portfolio_df) if not self.portfolio_df.empty else 0
            self.summary_label.setText(f"Total Value: ${total_value:.2f} | Securities: {item_count}")
            
            # Emit signal that portfolio was updated
            self.portfolio_updated.emit(self.portfolio_df)
    
    def add_position(self):
        """Open dialog to add new position"""
        dialog = StockSearchDialog(self)
        if dialog.exec():
            position_data = dialog.get_position_data()
            if position_data:
                # Add to DataFrame
                if self.portfolio_df is None:
                    self.portfolio_df = pd.DataFrame([position_data])
                else:
                    # Check if symbol already exists
                    existing = self.portfolio_df[self.portfolio_df['Symbol'] == position_data['Symbol']]
                    if not existing.empty:
                        # Ask user if they want to update or add
                        msg_box = QMessageBox()
                        msg_box.setIcon(QMessageBox.Icon.Question)
                        msg_box.setText(f"{position_data['Symbol']} is already in your portfolio.")
                        msg_box.setInformativeText("Do you want to update the existing position or add as a new position?")
                        update_button = msg_box.addButton("Update", QMessageBox.ButtonRole.AcceptRole)
                        add_button = msg_box.addButton("Add New", QMessageBox.ButtonRole.RejectRole)
                        cancel_button = msg_box.addButton("Cancel", QMessageBox.ButtonRole.DestructiveRole)
                        msg_box.exec()
                        
                        if msg_box.clickedButton() == update_button:
                            # Update existing position
                            idx = self.portfolio_df[self.portfolio_df['Symbol'] == position_data['Symbol']].index[0]
                            self.portfolio_df.at[idx, 'Shares'] = position_data['Shares']
                            self.portfolio_df.at[idx, 'Current Price'] = position_data['Current Price']
                            self.portfolio_df.at[idx, 'Total Value'] = position_data['Total Value']
                            self.portfolio_df.at[idx, 'Last Updated'] = position_data['Last Updated']
                        elif msg_box.clickedButton() == add_button:
                            # Add as new position
                            self.portfolio_df = pd.concat([self.portfolio_df, pd.DataFrame([position_data])], 
                                                        ignore_index=True)
                        else:
                            # Cancel - do nothing
                            return
                    else:
                        # Add new position
                        self.portfolio_df = pd.concat([self.portfolio_df, pd.DataFrame([position_data])], 
                                                    ignore_index=True)
                
                # Save and update
                self.portfolio_service.save_portfolio(self.portfolio_df)
                self.update_display()
    
    def refresh_portfolio(self):
        """Refresh portfolio prices"""
        if self.portfolio_df is not None and not self.portfolio_df.empty:
            # Update progress in status bar
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            
            # Update prices
            self.portfolio_df = self.portfolio_service.update_portfolio_prices(self.portfolio_df)
            
            # Save and update
            self.portfolio_service.save_portfolio(self.portfolio_df)
            self.update_display()
            
            QApplication.restoreOverrideCursor()
            
            # Confirmation message
            QMessageBox.information(self, "Update Complete", 
                                  "Portfolio prices have been updated successfully!")
    
    def remove_selected(self):
        """Remove selected positions from portfolio"""
        selected_rows = set(item.row() for item in self.portfolio_table.selectedItems())
        
        if not selected_rows:
            QMessageBox.information(self, "Selection Required", 
                                   "Please select one or more positions to remove.")
            return
            
        # Confirmation dialog
        confirm = QMessageBox.question(self, "Confirm Removal", 
                                     f"Are you sure you want to remove {len(selected_rows)} selected position(s)?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if confirm == QMessageBox.StandardButton.Yes:
            # Convert selected rows to list and sort in descending order
            # (to avoid index shifting during removal)
            rows_to_remove = sorted(list(selected_rows), reverse=True)
            
            # Drop rows from DataFrame
            self.portfolio_df = self.portfolio_df.drop(index=rows_to_remove).reset_index(drop=True)
            
            # Save and update
            self.portfolio_service.save_portfolio(self.portfolio_df)
            self.update_display()
    
    def import_spreadsheet(self):
        """Import portfolio from a spreadsheet file (CSV, XLSX, XLS)"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Spreadsheet", "", "Spreadsheet Files (*.csv *.xlsx *.xls);;All Files (*)"
        )
        
        if not file_path:
            return
            
        try:
            # Determine file type and read accordingly
            if file_path.endswith('.csv'):
                imported_df = pd.read_csv(file_path)
            elif file_path.endswith(('.xlsx', '.xls')):
                if not EXCEL_SUPPORT:
                    QMessageBox.critical(self, "Import Failed", 
                                    "Excel support is not available. Please install openpyxl and xlrd packages.")
                    return
                
                # Handle Excel files
                try:
                    imported_df = pd.read_excel(file_path)
                except Exception as excel_error:
                    QMessageBox.critical(self, "Excel Import Failed", 
                                    f"Could not read Excel file: {str(excel_error)}")
                    return
            else:
                QMessageBox.critical(self, "Import Failed", 
                                "Unsupported file format. Please use CSV or Excel files.")
                return
            
            # Validate that we have the required columns
            required_columns = ['Symbol', 'Shares']
            missing_columns = [col for col in required_columns if col not in imported_df.columns]
            
            if missing_columns:
                QMessageBox.critical(self, "Import Failed", 
                                   f"File missing required columns: {', '.join(missing_columns)}")
                return
            
            # Process the imported data
            self.process_imported_data(imported_df)
            
        except Exception as e:
            QMessageBox.critical(self, "Import Failed", 
                               f"Error importing file: {str(e)}")
    
    def process_imported_data(self, imported_df):
        """Process imported data and add to portfolio"""
        # Check if the DataFrame has Company and Sector columns
        has_full_info = all(col in imported_df.columns for col in ['Company', 'Sector'])
        
        if not has_full_info:
            # Only Symbol and Shares are available - need to fetch other info
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            
            # Access status bar through the main window
            try:
                main_window = QApplication.instance().activeWindow()
                if main_window and hasattr(main_window, 'statusBar'):
                    main_window.statusBar().showMessage("Fetching ticker information...")
            except:
                # If we can't access the status bar, just continue
                pass
            
            # Create a new DataFrame with minimal required columns
            processed_df = pd.DataFrame()
            processed_df['Symbol'] = imported_df['Symbol'].astype(str).str.strip().str.upper()
            processed_df['Shares'] = pd.to_numeric(imported_df['Shares'], errors='coerce')
            processed_df['Company'] = ""
            processed_df['Sector'] = ""
            processed_df['Current Price'] = 0.0
            processed_df['Total Value'] = 0.0
            processed_df['Last Updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Fetch data for each symbol
            successful_imports = 0
            for idx, row in processed_df.iterrows():
                symbol = row['Symbol']
                try:
                    ticker = yf.Ticker(symbol)
                    info = ticker.info
                    
                    # Get company name
                    processed_df.at[idx, 'Company'] = info.get('shortName', 'Unknown')
                    
                    # Determine security type and set appropriate sector
                    security_type = self.portfolio_service.get_security_type(symbol)
                    
                    if security_type == "ETF":
                        # For ETFs, use our specialized function
                        sector = self.portfolio_service.get_etf_sector_classification(symbol)
                        processed_df.at[idx, 'Sector'] = sector
                    elif security_type == "Mutual Fund":
                        # For mutual funds, categorize by fund type if possible
                        fund_name = info.get('shortName', '').lower()
                        if 'bond' in fund_name or 'income' in fund_name:
                            processed_df.at[idx, 'Sector'] = "Bond Fund"
                        elif 'growth' in fund_name:
                            processed_df.at[idx, 'Sector'] = "Growth Fund"
                        elif 'value' in fund_name:
                            processed_df.at[idx, 'Sector'] = "Value Fund"
                        elif 'index' in fund_name:
                            processed_df.at[idx, 'Sector'] = "Index Fund"
                        else:
                            processed_df.at[idx, 'Sector'] = "Mutual Fund"
                    else:
                        # For stocks, use the sector from Yahoo Finance
                        processed_df.at[idx, 'Sector'] = info.get('sector', 'Unknown')
                    
                    # Get current price
                    price = self.portfolio_service.get_price(symbol)
                    if price:
                        processed_df.at[idx, 'Current Price'] = price
                        processed_df.at[idx, 'Total Value'] = price * float(row['Shares'])
                        successful_imports += 1
                except Exception as e:
                    print(f"Error processing {symbol}: {e}")
            
            QApplication.restoreOverrideCursor()
            
            # Update the portfolio with the processed data
            if self.portfolio_df is not None and not self.portfolio_df.empty:
                # Merge with existing portfolio
                self.portfolio_df = pd.concat([self.portfolio_df, processed_df], ignore_index=True)
            else:
                self.portfolio_df = processed_df
            
            # Save and update display
            self.portfolio_service.save_portfolio(self.portfolio_df)
            self.update_display()
            
            QMessageBox.information(self, "Import Complete", 
                                f"Successfully imported {successful_imports} of {len(processed_df)} positions.")
        else:
            # We have all needed columns already
            if self.portfolio_df is not None and not self.portfolio_df.empty:
                # Merge with existing portfolio
                self.portfolio_df = pd.concat([self.portfolio_df, imported_df], ignore_index=True)
            else:
                self.portfolio_df = imported_df
            
            # Update prices if needed
            self.portfolio_df = self
            self.portfolio_service.save_portfolio(self.portfolio_df)
            self.update_display()
            
            QMessageBox.information(self, "Import Complete", 
                                   f"Successfully imported {len(imported_df)} positions.")


class SectorAllocationTab(QWidget):
    """Tab showing sector allocation analysis"""
    
    def __init__(self, portfolio_service):
        super().__init__()
        self.portfolio_service = portfolio_service
        self.sector_data = None
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Controls
        controls_layout = QHBoxLayout()
        
        analyze_btn = QPushButton("Analyze Sectors")
        analyze_btn.clicked.connect(self.analyze_sectors)
        controls_layout.addWidget(analyze_btn)
        
        controls_layout.addStretch()
        
        layout.addLayout(controls_layout)
        
        # Create a splitter for resizable sections
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Sector allocation chart
        chart_container = QWidget()
        chart_layout = QVBoxLayout(chart_container)
        chart_layout.setContentsMargins(0, 0, 0, 0)
        
        self.pie_chart = PieChartWidget(width=5, height=5)
        chart_layout.addWidget(self.pie_chart)
        splitter.addWidget(chart_container)
        
        # Sector details table
        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        
        table_layout.addWidget(QLabel("<b>Sector Details</b>"))
        
        self.sector_table = QTableWidget()
        self.sector_table.setColumnCount(3)
        self.sector_table.setHorizontalHeaderLabels(["Sector", "Value ($)", "Allocation (%)"])
        self.sector_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.sector_table.setAlternatingRowColors(True)
        self.sector_table.setColumnWidth(0, 150)  # Sector
        self.sector_table.setColumnWidth(1, 120)  # Value
        self.sector_table.setColumnWidth(2, 120)  # Percentage
        table_layout.addWidget(self.sector_table)
        
        splitter.addWidget(table_container)
        
        # Set initial sizes
        splitter.setSizes([500, 300])
        
        layout.addWidget(splitter)
        
        self.setLayout(layout)
        
    def update_from_portfolio(self, portfolio_df):
        """Update sector allocation from portfolio data"""
        if portfolio_df is not None and not portfolio_df.empty:
            self.analyze_sectors(portfolio_df)
    
    def analyze_sectors(self, portfolio_df=None):
        """Analyze sector allocation"""
        if portfolio_df is None:
            # Load from file if not provided
            portfolio_df = self.portfolio_service.load_portfolio()
            
        # Check if portfolio_df is a DataFrame and not empty
        if not isinstance(portfolio_df, pd.DataFrame) or portfolio_df.empty:
            QMessageBox.information(self, "No Data", 
                                "No portfolio data available to analyze.")
            return
            
        # Calculate sector allocation
        self.sector_data = self.portfolio_service.calculate_sector_allocation(portfolio_df)
        
        # Update pie chart
        self.pie_chart.plot_sector_allocation(self.sector_data)
        
        # Update table
        self.sector_table.setRowCount(0)
        for idx, row in self.sector_data.iterrows():
            self.sector_table.insertRow(self.sector_table.rowCount())
            self.sector_table.setItem(self.sector_table.rowCount()-1, 0, 
                                    QTableWidgetItem(str(row['Sector'])))
            
            # Format value
            value_item = QTableWidgetItem(f"${float(row['Total Value']):.2f}")
            self.sector_table.setItem(self.sector_table.rowCount()-1, 1, value_item)
            
            # Format percentage
            pct_item = QTableWidgetItem(f"{float(row['Percentage']):.2f}%")
            self.sector_table.setItem(self.sector_table.rowCount()-1, 2, pct_item)


class PortfolioTrackerApp(QMainWindow):
    """Main application window for the portfolio tracker"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Portfolio Tracker")
        self.setMinimumSize(800, 600)
        self.portfolio_service = PortfolioService()
        self.init_ui()
        
    def init_ui(self):
        # Central widget and tab container
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        # Create tabs
        self.overview_tab = PortfolioOverviewTab(self.portfolio_service)
        self.sector_tab = SectorAllocationTab(self.portfolio_service)
        
        # Connect signals
        self.overview_tab.portfolio_updated.connect(self.sector_tab.update_from_portfolio)
        
        # Add tabs to container
        self.tabs.addTab(self.overview_tab, "Portfolio Overview")
        self.tabs.addTab(self.sector_tab, "Sector Allocation")
        
        # Status bar
        self.statusBar().showMessage("Ready")
        
        # Set up timers
        self.auto_refresh_timer = QTimer()
        self.auto_refresh_timer.timeout.connect(self.check_auto_refresh)
        
        # Menu bar
        self.create_menus()
        
    def create_menus(self):
        """Create application menus"""
        # File menu
        file_menu = self.menuBar().addMenu("&File")
        
        # Save portfolio action
        save_action = file_menu.addAction("&Save Portfolio")
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_portfolio)
        
        # Export portfolio action
        export_action = file_menu.addAction("&Export to CSV")
        export_action.triggered.connect(self.export_portfolio)
        
        # Exit action
        exit_action = file_menu.addAction("E&xit")
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        
        # Tools menu
        tools_menu = self.menuBar().addMenu("&Tools")
        
        # Refresh prices action
        refresh_action = tools_menu.addAction("&Refresh Prices")
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self.refresh_prices)
        
        # Auto-refresh submenu
        auto_refresh_menu = tools_menu.addMenu("Auto-Refresh")
        
        # Auto-refresh options
        self.auto_refresh_disabled = auto_refresh_menu.addAction("Disabled")
        self.auto_refresh_disabled.setCheckable(True)
        self.auto_refresh_disabled.setChecked(True)
        
        self.auto_refresh_5min = auto_refresh_menu.addAction("Every 5 minutes")
        self.auto_refresh_5min.setCheckable(True)
        
        self.auto_refresh_15min = auto_refresh_menu.addAction("Every 15 minutes")
        self.auto_refresh_15min.setCheckable(True)
        
        self.auto_refresh_30min = auto_refresh_menu.addAction("Every 30 minutes")
        self.auto_refresh_30min.setCheckable(True)
        
        # Create action group for auto-refresh options
        auto_refresh_group = QActionGroup(self)
        auto_refresh_group.addAction(self.auto_refresh_disabled)
        auto_refresh_group.addAction(self.auto_refresh_5min)
        auto_refresh_group.addAction(self.auto_refresh_15min)
        auto_refresh_group.addAction(self.auto_refresh_30min)
        auto_refresh_group.triggered.connect(self.set_auto_refresh)
        
        # Help menu
        help_menu = self.menuBar().addMenu("&Help")
        
        # About action
        about_action = help_menu.addAction("&About")
        about_action.triggered.connect(self.show_about)
    
    def save_portfolio(self):
        """Save portfolio to file"""
        df = self.overview_tab.portfolio_df
        if df is not None and not df.empty:
            success = self.portfolio_service.save_portfolio(df)
            if success:
                self.statusBar().showMessage("Portfolio saved successfully", 3000)
            else:
                self.statusBar().showMessage("Error saving portfolio", 3000)
    
    def export_portfolio(self):
        """Export portfolio to CSV file"""
        df = self.overview_tab.portfolio_df
        if df is None or df.empty:
            QMessageBox.information(self, "No Data", 
                                   "No portfolio data available to export.")
            return
            
        # Ask for save location
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Portfolio", "", "CSV Files (*.csv);;All Files (*)"
        )
        
        if not file_path:
            return
            
        try:
            # Add .csv extension if not provided
            if not file_path.lower().endswith('.csv'):
                file_path += '.csv'
                
            # Export to CSV
            df.to_csv(file_path, index=False)
            
            self.statusBar().showMessage(f"Portfolio exported to {file_path}", 3000)
            
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", 
                               f"Error exporting portfolio: {str(e)}")
    
    def refresh_prices(self):
        """Trigger price refresh"""
        self.overview_tab.refresh_portfolio()
    
    def set_auto_refresh(self, action):
        """Set auto-refresh timer"""
        # Stop existing timer
        self.auto_refresh_timer.stop()
        
        # Set new timer interval
        if action == self.auto_refresh_5min:
            self.auto_refresh_timer.start(5 * 60 * 1000)  # 5 minutes
            self.statusBar().showMessage("Auto-refresh set to 5 minutes", 3000)
        elif action == self.auto_refresh_15min:
            self.auto_refresh_timer.start(15 * 60 * 1000)  # 15 minutes
            self.statusBar().showMessage("Auto-refresh set to 15 minutes", 3000)
        elif action == self.auto_refresh_30min:
            self.auto_refresh_timer.start(30 * 60 * 1000)  # 30 minutes
            self.statusBar().showMessage("Auto-refresh set to 30 minutes", 3000)
        else:  # Disabled
            self.statusBar().showMessage("Auto-refresh disabled", 3000)
    
    def check_auto_refresh(self):
        """Perform auto-refresh if needed"""
        # Only refresh during market hours (9:30 AM to 4:00 PM ET)
        # Simplified check - doesn't account for holidays or weekends
        now = datetime.now()
        if 0 <= now.weekday() <= 4:  # Monday to Friday
            hour = now.hour
            minute = now.minute
            
            # Convert to ET (assuming system is in ET for simplicity)
            if (9 <= hour < 16) or (hour == 9 and minute >= 30):
                self.refresh_prices()
                self.statusBar().showMessage("Auto-refreshed prices", 3000)
    
    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(self, "About Portfolio Tracker",
                         """<h2>Portfolio Tracker</h2>
                         <p>A simple application to track and analyze your stock portfolio.</p>
                         <p>Built with Python, PyQt6, and yfinance.</p>
                         <p>© 2025 Your Name</p>""")


def main():
    """Application entry point"""
    app = QApplication(sys.argv)
    window = PortfolioTrackerApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()