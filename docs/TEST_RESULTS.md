# Test results (actually executed)

Environment: Python 3.12, SQLite, Chromium (Playwright). PostgreSQL, Docker and gunicorn were NOT available offline - see docs/DEPLOYMENT.md.

## Unit / integration tests: `python -m unittest discover -s tests -t . -v`
```
test_audit_log_and_login_history ... ok
test_backup_failure_is_recorded_and_notified ... ok
test_backup_retention_and_due_logic ... ok
test_backup_run_verified_and_restorable ... ok
test_block_unblock_delete_user_and_session_kill ... ok
test_create_edit_toggle_delete_test_with_settings ... ok
test_delete_attempt_returns_attempt_to_student ... ok
test_exports_xlsx_and_pdf ... ok
test_notifications_and_announcements ... ok
test_pages_render_for_each_role ... ok
test_separate_backup_database ... ok
test_settings_change_is_audited_and_used ... ok
test_subject_and_grade_management ... ok
test_subject_with_tests_cannot_be_deleted ... ok
test_teacher_analytics_frequently_missed ... ok
test_user_search_and_filters ... ok
test_admin_bootstrap_from_env_only ... ok
test_admin_reset_link_flow ... ok
test_blocked_user_cannot_login ... ok
test_csrf_required ... ok
test_duplicate_username_and_phone ... ok
test_login_logout_and_session_revocation ... ok
test_open_redirect_blocked ... ok
test_password_change_requires_current_password ... ok
test_rate_limiting_of_login ... ok
test_registration_cannot_choose_role ... ok
test_registration_creates_student_and_logs_in ... ok
test_session_expiration ... ok
test_unauthorized_access_redirects_or_401 (tests.test_auth.AuthTests.test_unauthorized_access_redirects_or_401) ... ok
test_validation ... ok
test_audit_log_is_append_only_in_database (tests.test_i18n_audit.UzbekAndAuditTests.test_audit_log_is_append_only_in_database) ... ok
test_bell_menu_lists_notifications (tests.test_i18n_audit.UzbekAndAuditTests.test_bell_menu_lists_notifications) ... ok
test_deleting_user_keeps_their_audit_trail (tests.test_i18n_audit.UzbekAndAuditTests.test_deleting_user_keeps_their_audit_trail) ... ok
test_every_js_key_exists_and_patterns_are_safe (tests.test_i18n_audit.UzbekAndAuditTests.test_every_js_key_exists_and_patterns_are_safe) ... ok
test_language_switch_route_and_site_default (tests.test_i18n_audit.UzbekAndAuditTests.test_language_switch_route_and_site_default) ... ok
test_navbar_dashboard_flash_and_errors_in_uzbek (tests.test_i18n_audit.UzbekAndAuditTests.test_navbar_dashboard_flash_and_errors_in_uzbek) ... ok
test_pages_translate_to_uzbek_and_english_unchanged (tests.test_i18n_audit.UzbekAndAuditTests.test_pages_translate_to_uzbek_and_english_unchanged) ... ok
test_user_content_is_not_executed_after_translation (tests.test_i18n_audit.UzbekAndAuditTests.test_user_content_is_not_executed_after_translation) ... ok
test_duplicate_questions_not_imported_twice_into_same_test ... ok
test_edit_delete_reorder_and_add_questions ... ok
test_oversized_upload_rejected ... ok
test_rejects_non_pdf_and_invalid_pdf ... ok
test_upload_review_approve_publish ... ok
test_answer_key_section ... ok
test_cyrillic_uzbek ... ok
test_inline_options_multiline_and_multipage ... ok
test_invalid_pdf_rejected ... ok
test_latin_letter_options_and_answer_line ... ok
test_missing_answer_flagged_for_review ... ok
test_numeric_options_with_key ... ok
test_scanned_pdf_uses_ocr ... ok
test_admin_can_appoint_and_remove_teacher ... ok
test_admin_cannot_demote_self_or_last_admin ... ok
test_leaderboard_hides_private_data ... ok
test_student_cannot_access_admin_or_teacher ... ok
test_student_cannot_appoint_teacher_or_self_promote ... ok
test_students_cannot_view_other_students_results ... ok
test_teacher_limits ... ok
test_teacher_with_export_permission_can_export ... ok
test_any_student_can_take_any_grade_test ... ok
test_attempt_limit ... ok
test_concurrent_answers_same_question_only_one_saved ... ok
test_concurrent_starts_create_one_attempt ... ok
test_correct_answer_stays_associated_with_option ... ok
test_exposure_history_no_repeat_until_pool_exhausted ... ok
test_hidden_correct_answers_when_show_correct_disabled ... ok
test_leaderboard_is_reliability_weighted ... ok
test_new_questions_are_preferred ... ok
test_no_duplicates_and_stable_order_during_attempt ... ok
test_partial_pool_then_new_cycle_fills_without_duplicates ... ok
test_questions_and_options_are_randomised_between_students ... ok
test_refresh_restores_unfinished_attempt_and_results_persist ... ok
test_state_never_leaks_correct_answers ... ok
test_time_limit_expires_attempt ... ok
test_unavailable_tests_cannot_be_started ... ok
test_wrong_answer_feedback_and_scoring_and_no_changing_answers ... ok
test_backup_and_restore_scripts_roundtrip ... ok
test_create_admin_script ... ok
test_production_requires_secret_key ... ok
test_both_themes_defined_with_required_primary_colours ... ok
test_js_files_parse ... ok
test_navbar_shows_username_and_dropdown ... ok
test_no_alert_calls ... ok
test_no_hardcoded_colours_outside_theme_file ... ok
test_no_inline_css_or_js_in_templates ... ok
test_security_headers ... ok
test_sql_injection_attempts_are_harmless ... ok
test_static_structure ... ok
test_theme_init_runs_before_stylesheets_and_viewport_present ... ok
test_xss_is_escaped ... ok
Ran 90 tests in 32.678s
OK
```

## Browser tests (Chromium): `python -m tests.e2e_browser`
```
PASS system light preference applied on first visit
PASS toggle switches to dark
PASS dark background differs
PASS theme persisted after reload
PASS system dark preference respected on first visit
PASS password visibility toggle
PASS weak password shows inline error
PASS registered and landed on dashboard
PASS welcome toast shown
PASS navbar shows username
PASS dropdown hidden initially
PASS dropdown opens
PASS dropdown closes on outside click
PASS sign out returns to home as guest
PASS no horizontal overflow @ 320px (public + student pages)
PASS no horizontal overflow @ 360px (public + student pages)
PASS no horizontal overflow @ 375px (public + student pages)
PASS no horizontal overflow @ 390px (public + student pages)
PASS no horizontal overflow @ 414px (public + student pages)
PASS no horizontal overflow @ 768px (public + student pages)
PASS no horizontal overflow @ 1024px (public + student pages)
PASS no horizontal overflow @ 1440px (public + student pages)
PASS no horizontal overflow @ 320px (admin pages)
PASS quiz renders 5 question buttons
PASS timer visible
PASS correct answer not present in page source
PASS wrong pick highlighted red and correct highlighted green
PASS explanation shown
PASS refresh restores progress (1 answered)
PASS result page shows score
PASS custom confirm modal appears for delete
PASS modal closes on cancel and nothing deleted
PASS review editor lists questions
PASS incomplete question blocked with toast
PASS quiz UI strings are Uzbek
PASS feedback text Uzbek
PASS bell dropdown lists notifications
PASS no JavaScript console errors
38/38 browser checks passed
```

Not covered: PostgreSQL engine (incl. its audit trigger), Docker build, gunicorn start, Uzbek-language OCR packs, real iOS/Android browsers, load testing.
