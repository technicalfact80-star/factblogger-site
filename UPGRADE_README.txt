FactBlogger Advanced CMS upgrade bundle

This is an OVERLAY / PATCH bundle. Extract its files directly into the root of your existing factblogger-site project. It does NOT include site_config.json, content/posts/, public/, or your Git repository metadata. Do NOT replace or delete your existing user-specific site_config.json.

Main setup guide: ADVANCED_CMS_SETUP_HINDI.md
Admin entry point: start_admin.bat -> http://127.0.0.1:8787
Daily automation: run_daily_automation.bat (scheduled task via install_daily_task.ps1)

Please make a backup of your project before overwriting build_site.py, generate_post.py, and check_site.py.
