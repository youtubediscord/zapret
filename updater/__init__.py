# updater/__init__.py
from .update_netrogat import update_netrogat_list
from .update_other import update_other_list
from .update import run_update_async, check_and_run_update

__all__ = [
    'update_netrogat_list',
    'update_other_list', 
    'run_update_async',
    'check_and_run_update'
]

# Version info for the updater module
__version__ = "1.0.0"
__author__ = "Zapret GUI Team"
