"""
Contexto Thread-Local para o Worker Python
Distributed Node Architecture
"""
import threading

_local = threading.local()

def set_current_user_id(user_id):
    _local.user_id = user_id

def get_current_user_id():
    return getattr(_local, 'user_id', 'anonymous')
