"""
Adaptador DynamoDB para o Motor Analítico Python
Distributed Node Architecture - nodefund

Implementa a mesma interface pública que storage.py (file-based)
mas operando no Amazon DynamoDB via boto3.

Variáveis de ambiente:
  DYNAMODB_TABLE_NAME  (default: nodefund)
  DYNAMODB_ENDPOINT    (default: vazio = AWS produção)
  AWS_REGION           (default: us-east-1)
"""

import os
import re
import json
from datetime import datetime

import boto3
from boto3.dynamodb.conditions import Key

# ─────────────────── Configuração do Cliente ───────────────────

TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME', 'nodefund')
ENDPOINT_URL = os.environ.get('DYNAMODB_ENDPOINT', None)
REGION = os.environ.get('AWS_REGION', 'us-east-1')

_dynamodb_kwargs = {'region_name': REGION}
if ENDPOINT_URL:
    _dynamodb_kwargs['endpoint_url'] = ENDPOINT_URL
    _dynamodb_kwargs['aws_access_key_id'] = os.environ.get('AWS_ACCESS_KEY_ID', 'local')
    _dynamodb_kwargs['aws_secret_access_key'] = os.environ.get('AWS_SECRET_ACCESS_KEY', 'local')

_dynamodb = boto3.resource('dynamodb', **_dynamodb_kwargs)
_table = _dynamodb.Table(TABLE_NAME)


# ─────────────────── Utilidades ───────────────────

def clean_cnpj(cnpj):
    """Remove caracteres não numéricos do CNPJ."""
    if not cnpj:
        return ''
    return re.sub(r'\D', '', str(cnpj))


def format_cnpj(clean):
    """Formata CNPJ limpo para XX.XXX.XXX/XXXX-XX."""
    c = clean_cnpj(clean)
    if len(c) != 14:
        return c
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:14]}"


def clean_ticker(ticker):
    """Limpa ticker B3: remove espaços e sufixo .SA."""
    if not ticker:
        return ''
    return re.sub(r'\.SA$', '', str(ticker).strip(), flags=re.IGNORECASE).upper()


def _convert_decimals(obj):
    """Converte Decimal do DynamoDB para float recursivamente."""
    from decimal import Decimal
    if isinstance(obj, list):
        return [_convert_decimals(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: _convert_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        f = float(obj)
        return int(f) if f == int(f) and not isinstance(obj, float) else f
    return obj


# ─────────────────── Fundos CVM ───────────────────

def load_fund_data(cnpj):
    """Carrega array de cotas do fundo CVM do DynamoDB."""
    cnpj_clean = clean_cnpj(cnpj)
    try:
        response = _table.get_item(Key={'PK': f'FUND#{cnpj_clean}', 'SK': 'DATA'})
        item = response.get('Item')
        if item and 'quotes' in item:
            return _convert_decimals(item['quotes'])
        return []
    except Exception as e:
        print(f"[DynamoDB] Erro ao carregar fundo {cnpj_clean}: {e}")
        return []


def save_fund_data(cnpj, fund_name, new_quotes):
    """Salva/mescla cotas do fundo CVM no DynamoDB."""
    cnpj_clean = clean_cnpj(cnpj)
    existing = load_fund_data(cnpj_clean)

    # Merge incremental por data
    existing_dates = {q['date'] for q in existing}
    merged = list(existing)
    for q in new_quotes:
        if q['date'] in existing_dates:
            # Atualiza registro existente
            for i, eq in enumerate(merged):
                if eq['date'] == q['date']:
                    merged[i] = q
                    break
        else:
            merged.append(q)

    merged.sort(key=lambda q: q['date'])
    now = datetime.utcnow().isoformat()

    _table.put_item(Item={
        'PK': f'FUND#{cnpj_clean}',
        'SK': 'DATA',
        'entity_type': 'fund_quotes',
        'name': fund_name,
        'quotes': merged,
        'record_count': len(merged),
        'start_date': merged[0]['date'] if merged else None,
        'end_date': merged[-1]['date'] if merged else None,
        'last_quota': str(merged[-1].get('quota', 0)) if merged else None,
        'updated_at': now
    })

    return {
        'cnpj': cnpj_clean,
        'name': fund_name,
        'total_quotes': len(merged),
        'new_quotes': len(new_quotes),
        'updated_at': now
    }


# ─────────────────── Ativos B3 ───────────────────

def load_b3_data(ticker):
    """Carrega cotações do ativo B3 do DynamoDB."""
    ticker_clean = clean_ticker(ticker)
    try:
        response = _table.get_item(Key={'PK': f'B3#{ticker_clean}', 'SK': 'DATA'})
        item = response.get('Item')
        if item and 'quotes' in item:
            return _convert_decimals(item['quotes'])
        return []
    except Exception as e:
        print(f"[DynamoDB] Erro ao carregar B3 {ticker_clean}: {e}")
        return []


def save_b3_data(ticker, name, new_quotes):
    """Salva/mescla cotações B3 no DynamoDB."""
    ticker_clean = clean_ticker(ticker)
    existing = load_b3_data(ticker_clean)

    existing_dates = {q['date'] for q in existing}
    merged = list(existing)
    for q in new_quotes:
        if q['date'] in existing_dates:
            for i, eq in enumerate(merged):
                if eq['date'] == q['date']:
                    merged[i] = q
                    break
        else:
            merged.append(q)

    merged.sort(key=lambda q: q['date'])
    now = datetime.utcnow().isoformat()

    last_val = merged[-1].get('quota', merged[-1].get('close', 0)) if merged else 0

    _table.put_item(Item={
        'PK': f'B3#{ticker_clean}',
        'SK': 'DATA',
        'entity_type': 'b3_quotes',
        'name': name,
        'quotes': merged,
        'record_count': len(merged),
        'start_date': merged[0]['date'] if merged else None,
        'end_date': merged[-1]['date'] if merged else None,
        'last_quota': str(last_val),
        'updated_at': now
    })

    return {
        'ticker': ticker_clean,
        'name': name,
        'total_quotes': len(merged),
        'new_quotes': len(new_quotes),
        'updated_at': now
    }


def load_asset_data(asset):
    """Carrega dados polimorficamente: B3 ou Fundo CVM."""
    asset_type = asset.get('type', 'fund')
    if asset_type == 'b3':
        code = asset.get('code', asset.get('ticker', ''))
        return load_b3_data(code)
    else:
        code = asset.get('code', asset.get('cnpj', ''))
        return load_fund_data(code)


# ─────────────────── Benchmarks ───────────────────

def load_benchmark_data(name):
    """Carrega série histórica do benchmark do DynamoDB."""
    try:
        response = _table.get_item(Key={'PK': f'BENCH#{name}', 'SK': 'DATA'})
        item = response.get('Item')
        if item:
            return _convert_decimals(item.get('series', item.get('quotes', [])))
        return []
    except Exception as e:
        print(f"[DynamoDB] Erro ao carregar benchmark {name}: {e}")
        return []


def save_benchmark_data(name, display_name, series_type, new_points):
    """Salva/mescla série de benchmark no DynamoDB."""
    existing = load_benchmark_data(name)

    existing_dates = {p['date'] for p in existing}
    merged = list(existing)
    for p in new_points:
        if p['date'] in existing_dates:
            for i, ep in enumerate(merged):
                if ep['date'] == p['date']:
                    merged[i] = p
                    break
        else:
            merged.append(p)

    merged.sort(key=lambda p: p['date'])
    now = datetime.utcnow().isoformat()

    _table.put_item(Item={
        'PK': f'BENCH#{name}',
        'SK': 'DATA',
        'entity_type': 'benchmark_series',
        'name': display_name,
        'series_type': series_type,
        'series': merged,
        'record_count': len(merged),
        'start_date': merged[0]['date'] if merged else None,
        'end_date': merged[-1]['date'] if merged else None,
        'updated_at': now
    })

    return {
        'benchmark': name,
        'name': display_name,
        'total_points': len(merged),
        'new_points': len(new_points),
        'updated_at': now
    }


# ─────────────────── Carteiras (Portfolios) ───────────────────

def load_manifest(user_id='anonymous'):
    """Carrega manifest de carteiras do usuário."""
    try:
        response = _table.get_item(Key={'PK': f'USER#{user_id}', 'SK': 'MANIFEST'})
        item = response.get('Item')
        if item:
            return _convert_decimals({
                'active_portfolio_id': item.get('active_portfolio_id'),
                'portfolios': item.get('portfolios', [])
            })
        return {'active_portfolio_id': None, 'portfolios': []}
    except Exception as e:
        print(f"[DynamoDB] Erro ao carregar manifest: {e}")
        return {'active_portfolio_id': None, 'portfolios': []}


def save_manifest(manifest_data, user_id='anonymous'):
    """Salva manifest de carteiras do usuário."""
    try:
        _table.put_item(Item={
            'PK': f'USER#{user_id}',
            'SK': 'MANIFEST',
            'entity_type': 'manifest',
            'active_portfolio_id': manifest_data.get('active_portfolio_id'),
            'portfolios': manifest_data.get('portfolios', []),
            'updated_at': datetime.utcnow().isoformat()
        })
        return True
    except Exception as e:
        print(f"[DynamoDB] Erro ao salvar manifest: {e}")
        return False


def get_portfolio_by_id(portfolio_id, user_id='anonymous'):
    """Carrega carteira do usuário por ID."""
    try:
        response = _table.get_item(Key={
            'PK': f'USER#{user_id}',
            'SK': f'PORTFOLIO#{portfolio_id}'
        })
        item = response.get('Item')
        if item:
            data = _convert_decimals(dict(item))
            data.pop('PK', None)
            data.pop('SK', None)
            data.pop('entity_type', None)
            return data
        return None
    except Exception as e:
        print(f"[DynamoDB] Erro ao carregar carteira {portfolio_id}: {e}")
        return None


def get_active_portfolio(user_id='anonymous'):
    """Retorna a carteira ativa do usuário."""
    manifest = load_manifest(user_id)
    active_id = manifest.get('active_portfolio_id')
    if active_id:
        p = get_portfolio_by_id(active_id, user_id)
        if p:
            return p
    # Fallback: primeira carteira
    if manifest.get('portfolios'):
        return get_portfolio_by_id(manifest['portfolios'][0]['id'], user_id)
    return None


def list_portfolios(user_id='anonymous'):
    """Lista carteiras cadastradas do usuário."""
    manifest = load_manifest(user_id)
    active_id = manifest.get('active_portfolio_id')
    result = []
    for p in manifest.get('portfolios', []):
        result.append({
            **p,
            'active': p['id'] == active_id,
            'is_active': p['id'] == active_id
        })
    return result


def set_active_portfolio(portfolio_id, user_id='anonymous'):
    """Altera a carteira ativa do usuário."""
    manifest = load_manifest(user_id)
    found = any(p['id'] == portfolio_id for p in manifest.get('portfolios', []))
    if not found:
        return False
    manifest['active_portfolio_id'] = portfolio_id
    return save_manifest(manifest, user_id)


def save_portfolio(portfolio_data, portfolio_id=None, user_id='anonymous'):
    """Salva carteira do usuário no DynamoDB."""
    p_id = portfolio_id or portfolio_data.get('id')
    if not p_id:
        return False

    now = datetime.utcnow().isoformat()
    portfolio_data['updated_at'] = now
    portfolio_data['id'] = p_id

    _table.put_item(Item={
        'PK': f'USER#{user_id}',
        'SK': f'PORTFOLIO#{p_id}',
        'entity_type': 'portfolio',
        **portfolio_data
    })

    # Atualizar manifest
    manifest = load_manifest(user_id)
    entry = next((p for p in manifest['portfolios'] if p['id'] == p_id), None)
    if entry:
        entry['name'] = portfolio_data.get('name', entry.get('name'))
        entry['asset_count'] = len(portfolio_data.get('funds', []))
    save_manifest(manifest, user_id)

    return True


def create_portfolio(name, base_funds=None, user_id='anonymous'):
    """Cria nova carteira para o usuário."""
    slug = re.sub(r'[^a-z0-9]+', '_', name.lower().strip())
    slug = slug.strip('_')

    manifest = load_manifest(user_id)
    count = len([p for p in manifest.get('portfolios', []) if p['id'].startswith(f'carteira_{slug}')])
    p_id = f'carteira_{slug}_{count + 1}'

    funds = base_funds if base_funds and len(base_funds) > 0 else [{
        'id': 'default_asset',
        'type': 'fund',
        'name': 'Ativo Padrão',
        'cnpj': '',
        'code': '',
        'target_pct': 100,
        'min_investment': 100,
        'color': '#6c5ce7',
        'color_aux': '#f0eeff'
    }]

    now = datetime.utcnow().isoformat()
    portfolio = {
        'id': p_id,
        'name': name,
        'funds': funds,
        'updated_at': now
    }

    _table.put_item(Item={
        'PK': f'USER#{user_id}',
        'SK': f'PORTFOLIO#{p_id}',
        'entity_type': 'portfolio',
        **portfolio
    })

    manifest['portfolios'].append({
        'id': p_id,
        'name': name,
        'file': f'{p_id}.json',
        'asset_count': len(funds)
    })
    manifest['active_portfolio_id'] = p_id
    save_manifest(manifest, user_id)

    return portfolio


def delete_portfolio(portfolio_id, user_id='anonymous'):
    """Exclui carteira do usuário."""
    manifest = load_manifest(user_id)
    if len(manifest.get('portfolios', [])) <= 1:
        return False

    idx = next((i for i, p in enumerate(manifest['portfolios']) if p['id'] == portfolio_id), -1)
    if idx == -1:
        return False

    _table.delete_item(Key={
        'PK': f'USER#{user_id}',
        'SK': f'PORTFOLIO#{portfolio_id}'
    })

    manifest['portfolios'].pop(idx)
    if manifest.get('active_portfolio_id') == portfolio_id:
        manifest['active_portfolio_id'] = manifest['portfolios'][0]['id'] if manifest['portfolios'] else None
    save_manifest(manifest, user_id)

    return True


def get_data_status(portfolio_id=None, user_id='anonymous'):
    """Monta inventário de dados disponíveis no DynamoDB."""
    manifest = load_manifest(user_id)
    all_funds = []

    portfolios_to_check = manifest.get('portfolios', [])
    if portfolio_id and portfolio_id != 'all':
        portfolios_to_check = [p for p in portfolios_to_check if p['id'] == portfolio_id]

    for entry in portfolios_to_check:
        p = get_portfolio_by_id(entry['id'], user_id)
        if p and 'funds' in p:
            for f in p['funds']:
                existing = any(
                    (ef.get('cnpj') and ef['cnpj'] == f.get('cnpj')) or
                    (ef.get('code') and ef['code'] == f.get('code'))
                    for ef in all_funds
                )
                if not existing:
                    all_funds.append(f)

    funds_status = []
    b3_status = []

    for f in all_funds:
        if f.get('type') == 'b3':
            ticker = clean_ticker(f.get('code', f.get('ticker', '')))
            quotes = load_b3_data(ticker)
            b3_status.append({
                'id': f.get('id'),
                'name': f.get('name'),
                'ticker': ticker,
                'type': 'b3',
                'has_data': len(quotes) > 0,
                'record_count': len(quotes),
                'start_date': quotes[0]['date'] if quotes else None,
                'end_date': quotes[-1]['date'] if quotes else None,
                'last_quota': quotes[-1].get('quota', quotes[-1].get('close', 0)) if quotes else None
            })
        else:
            cnpj_clean = clean_cnpj(f.get('cnpj', f.get('code', '')))
            quotes = load_fund_data(cnpj_clean)
            funds_status.append({
                'id': f.get('id'),
                'name': f.get('name'),
                'cnpj': f.get('cnpj'),
                'cnpj_clean': cnpj_clean,
                'type': 'fund',
                'has_data': len(quotes) > 0,
                'record_count': len(quotes),
                'start_date': quotes[0]['date'] if quotes else None,
                'end_date': quotes[-1]['date'] if quotes else None,
                'last_quota': quotes[-1].get('quota', 0) if quotes else None
            })

    # Benchmarks
    benchmarks_status = []
    bench_ids = ['cdi', 'ipca', 'poupanca', 'ibov', 'ifix', 'sp500', 'btc', 'usd']
    for bid in bench_ids:
        series = load_benchmark_data(bid)
        benchmarks_status.append({
            'id': bid,
            'has_data': len(series) > 0,
            'record_count': len(series),
            'start_date': series[0]['date'] if series else None,
            'end_date': series[-1]['date'] if series else None
        })

    return {
        'funds_status': funds_status,
        'b3_status': b3_status,
        'benchmarks_status': benchmarks_status,
        'portfolio_id': portfolio_id or 'all',
        'is_global': not portfolio_id or portfolio_id == 'all',
        'storage': 'dynamodb'
    }

# ─────────────────── Configurações (Fontes e Benchmarks) ───────────────────

def load_data_sources(user_id='anonymous'):
    try:
        response = _table.get_item(Key={'PK': f'USER#{user_id}', 'SK': 'CONFIG#SOURCES'})
        item = response.get('Item')
        if item and 'sources' in item:
            return _convert_decimals(item['sources'])
        return {} # Defaults are handled by config_manager
    except Exception as e:
        print(f"[DynamoDB] Erro ao carregar fontes: {e}")
        return {}

def save_data_sources(sources_config, user_id='anonymous'):
    try:
        _table.put_item(Item={
            'PK': f'USER#{user_id}',
            'SK': 'CONFIG#SOURCES',
            'entity_type': 'config_sources',
            'sources': sources_config,
            'updated_at': datetime.utcnow().isoformat()
        })
        return True
    except Exception as e:
        print(f"[DynamoDB] Erro ao salvar fontes: {e}")
        return False

def load_benchmarks_config(user_id='anonymous'):
    try:
        response = _table.get_item(Key={'PK': f'USER#{user_id}', 'SK': 'CONFIG#BENCHMARKS'})
        item = response.get('Item')
        if item and 'benchmarks' in item:
            return _convert_decimals(item['benchmarks'])
        return []
    except Exception as e:
        print(f"[DynamoDB] Erro ao carregar benchmarks configs: {e}")
        return []

def save_benchmarks_config(benchmarks_list, user_id='anonymous'):
    try:
        _table.put_item(Item={
            'PK': f'USER#{user_id}',
            'SK': 'CONFIG#BENCHMARKS',
            'entity_type': 'config_benchmarks',
            'benchmarks': benchmarks_list,
            'updated_at': datetime.utcnow().isoformat()
        })
        return True
    except Exception as e:
        print(f"[DynamoDB] Erro ao salvar benchmarks configs: {e}")
        return False

