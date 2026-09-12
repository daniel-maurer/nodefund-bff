"""
Proxy de Configurações - nodefund
Roteia as chamadas para o DynamoDB ou File System
com base na variável de ambiente STORAGE_BACKEND.
"""

import os
from .config_manager_file import DEFAULT_DATA_SOURCES, DEFAULT_BENCHMARKS
from . import context

STORAGE_BACKEND = os.environ.get('STORAGE_BACKEND', 'dynamodb')

if STORAGE_BACKEND == 'dynamodb':
    from . import dynamo_adapter

    def load_data_sources():
        user_id = context.get_current_user_id()
        data = dynamo_adapter.load_data_sources(user_id)
        # Mesclar default se não houver configurações
        if not data:
            dynamo_adapter.save_data_sources(DEFAULT_DATA_SOURCES, user_id)
            return DEFAULT_DATA_SOURCES
        # Garantir que todas as fontes padrão existam
        for k, v in DEFAULT_DATA_SOURCES.items():
            if k not in data:
                data[k] = v
        return data

    def save_data_sources(sources_config):
        return dynamo_adapter.save_data_sources(sources_config, context.get_current_user_id())

    def load_benchmarks_config():
        user_id = context.get_current_user_id()
        benchmarks = dynamo_adapter.load_benchmarks_config(user_id)
        if not benchmarks:
            dynamo_adapter.save_benchmarks_config(DEFAULT_BENCHMARKS, user_id)
            return DEFAULT_BENCHMARKS
        # Mesclar benchmarks padrão ausentes
        existing_ids = {b["id"] for b in benchmarks}
        for default_bm in DEFAULT_BENCHMARKS:
            if default_bm["id"] not in existing_ids:
                benchmarks.append(default_bm)
        return benchmarks

    def save_benchmarks_config(benchmarks_list):
        return dynamo_adapter.save_benchmarks_config(benchmarks_list, context.get_current_user_id())

else:
    from .config_manager_file import (
        load_data_sources,
        save_data_sources,
        load_benchmarks_config,
        save_benchmarks_config
    )
