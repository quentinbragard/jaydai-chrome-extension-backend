"""
Prompts utilities module.
"""

from .locales import (
    extract_localized_field,
    create_localized_field,
    update_localized_field,
    get_supported_locales,
    is_locale_supported
)

from .folders import (
    determine_folder_type,
    process_folder_for_response,
    fetch_folders_by_type,
    get_user_pinned_folders,
    update_user_pinned_folders,
    get_all_folder_ids_by_type,
    add_pinned_status_to_folders
)

from .templates import (
    process_template_for_response,
    fetch_templates_for_folders,
    fetch_templates_by_type,
    get_unorganized_templates,
    create_template,
    update_template,
    track_template_usage,
    organize_templates_by_folder,
    add_templates_to_folders
)

__all__ = [
    # Locale utilities
    'extract_localized_field',
    'create_localized_field',
    'update_localized_field',
    'get_supported_locales',
    'is_locale_supported',
    
    # Folder utilities
    'determine_folder_type',
    'process_folder_for_response',
    'fetch_folders_by_type',
    'get_user_pinned_folders',
    'update_user_pinned_folders',
    'get_all_folder_ids_by_type',
    'add_pinned_status_to_folders',
    
    # Template utilities
    'process_template_for_response',
    'fetch_templates_for_folders',
    'fetch_templates_by_type',
    'get_unorganized_templates',
    'create_template',
    'update_template',
    'track_template_usage',
    'organize_templates_by_folder',
    'add_templates_to_folders'
]