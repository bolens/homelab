# Plan

Add an explicit require-existing policy to prepare_stack_ensure_dir_from_env;
retain create as the compatible default for application-local directories.
Update all media callers, document their prerequisite, and run isolated Python
fixtures as part of repository validation. Do not alter Compose mounts or images.
The change enforces documents/PREPARATION-STANDARDS.md without deployment.
