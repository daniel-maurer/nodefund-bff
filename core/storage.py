"""
Proxy de Armazenamento - nodefund
Roteia as chamadas de storage para o DynamoDB ou File System
com base na variável de ambiente STORAGE_BACKEND.
"""

import os
from . import context

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORAGE_BACKEND = os.environ.get('STORAGE_BACKEND', 'dynamodb')

if STORAGE_BACKEND == 'dynamodb':
    from . import dynamo_adapter

    def clean_cnpj(cnpj): return dynamo_adapter.clean_cnpj(cnpj)
    def format_cnpj(clean): return dynamo_adapter.format_cnpj(clean)
    def clean_ticker(ticker): return dynamo_adapter.clean_ticker(ticker)
    
    def load_fund_data(cnpj): return dynamo_adapter.load_fund_data(cnpj)
    def save_fund_data(cnpj, fund_name, new_quotes): return dynamo_adapter.save_fund_data(cnpj, fund_name, new_quotes)
    def load_b3_data(ticker): return dynamo_adapter.load_b3_data(ticker)
    def load_b3_dividends(ticker): return dynamo_adapter.load_b3_dividends(ticker)
    def save_b3_data(ticker, name, new_quotes, dividends=None): return dynamo_adapter.save_b3_data(ticker, name, new_quotes, dividends)
    def load_asset_data(asset): return dynamo_adapter.load_asset_data(asset)
    def load_asset_dividends(asset): return dynamo_adapter.load_asset_dividends(asset)
    def load_benchmark_data(name): return dynamo_adapter.load_benchmark_data(name)
    def save_benchmark_data(name, display_name, series_type, new_points): return dynamo_adapter.save_benchmark_data(name, display_name, series_type, new_points)
    
    def load_manifest(): return dynamo_adapter.load_manifest(context.get_current_user_id())
    def save_manifest(manifest_data): return dynamo_adapter.save_manifest(manifest_data, context.get_current_user_id())
    def get_portfolio_by_id(portfolio_id): return dynamo_adapter.get_portfolio_by_id(portfolio_id, context.get_current_user_id())
    def get_active_portfolio(): return dynamo_adapter.get_active_portfolio(context.get_current_user_id())
    def list_portfolios(): return dynamo_adapter.list_portfolios(context.get_current_user_id())
    def set_active_portfolio(portfolio_id): return dynamo_adapter.set_active_portfolio(portfolio_id, context.get_current_user_id())
    def save_portfolio(portfolio_data, portfolio_id=None): return dynamo_adapter.save_portfolio(portfolio_data, portfolio_id, context.get_current_user_id())
    def create_portfolio(name, base_funds=None): return dynamo_adapter.create_portfolio(name, base_funds, context.get_current_user_id())
    def delete_portfolio(portfolio_id): return dynamo_adapter.delete_portfolio(portfolio_id, context.get_current_user_id())
    def get_data_status(portfolio_id=None): return dynamo_adapter.get_data_status(portfolio_id, context.get_current_user_id())

    def load_portfolio(): return get_active_portfolio()
    def get_fund_file_paths(cnpj): return {"quotes_file": f"dynamo_fund_{clean_cnpj(cnpj)}.json", "metadata_file": f"dynamo_meta_{clean_cnpj(cnpj)}.json"}

else:
    from .storage_file import (
        clean_cnpj,
        format_cnpj,
        clean_ticker,
        load_fund_data,
        save_fund_data,
        load_b3_data,
        load_b3_dividends,
        save_b3_data,
        load_asset_data,
        load_asset_dividends,
        load_benchmark_data,
        save_benchmark_data,
        load_manifest,
        save_manifest,
        get_portfolio_by_id,
        get_active_portfolio,
        list_portfolios,
        set_active_portfolio,
        save_portfolio,
        create_portfolio,
        delete_portfolio,
        get_data_status,
        load_portfolio,
        get_fund_file_paths
    )
