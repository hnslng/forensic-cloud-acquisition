"""Real Chromium + HTTP API + disposable PostgreSQL; no production accounts/data."""
import os
from pathlib import Path
import threading
import time
import urllib.request

import pytest
from playwright.sync_api import sync_playwright, expect
from starlette.staticfiles import StaticFiles
import uvicorn

from backend.main import app
from test_phase1 import synthetic_database, migration_connection, PASSWORD

URL = 'http://localhost:8766'


@pytest.fixture(scope='session', autouse=True)
def web_server():
    assert os.environ['FCA_DB_NAME'] == 'fca_test_phase1'
    assert os.environ['FCA_PUBLIC_ORIGIN'] == URL
    # Only this test process serves static files; production continues through nginx/HTTPS.
    app.mount('/', StaticFiles(directory='/app/frontend', html=True), name='test-frontend')
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=8766, log_level='error'))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        try:
            urllib.request.urlopen(URL + '/api/health', timeout=1)
            break
        except OSError:
            time.sleep(.05)
    else:
        pytest.fail('Isolated test web server did not start')
    yield
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture
def page():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(args=['--disable-dev-shm-usage'])
        context = browser.new_context(viewport={'width': 1440, 'height': 1000}, locale='de-AT')
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(URL)
        yield page
        context.close()
        browser.close()
        assert errors == []


def screenshot(page, name):
    directory = Path(os.environ.get('FCA_TEST_ARTIFACT_DIR', '/tmp'))
    directory.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(directory / (name + '.png')), full_page=True)


def sign_in(page, username='alice'):
    page.locator('#case-login-button').click()
    page.locator('#login-form [name=username]').fill(username)
    page.locator('#login-form [name=password]').fill(PASSWORD)
    page.locator('#login-form button[type=submit]').click()
    expect(page.locator('#login-dialog')).not_to_be_visible()


def create_case(page, username='alice'):
    page.locator('#start-open-case').click()
    page.locator('#case-form [name=business_number]').fill('SYNTHETIC-UI-2026')
    page.locator('#case-form [name=name]').fill('Synthetischer Testfall')
    page.locator('#case-form [name=operator_initials]').fill('QA')
    sign_in(page, username)
    expect(page.locator('#case-form [name=business_number]')).to_have_value('SYNTHETIC-UI-2026')
    expect(page.locator('#case-form [name=operator_initials]')).to_have_value('QA')
    page.locator('#case-start').click()
    expect(page.locator('#start-overlay')).not_to_be_visible()
    expect(page.locator('#case-dialog')).not_to_be_visible()
    expect(page.locator('#active-case-number')).to_have_text('SYNTHETIC-UI-2026')


def add_cloud(page, provider, label):
    page.locator('#add-cloud-button').click()
    page.locator(f'#cloud-form [value={provider}]').check()
    page.locator('#cloud-form [name=label]').fill(label)
    screenshot(page, '03a-cloud-modal')
    page.locator('#cloud-submit').click()
    expect(page.locator('#cloud-dialog')).not_to_be_visible()
    expect(page.locator('.cloud-name').filter(has_text=label)).to_be_visible()


def test_start_nested_login_case_and_multi_cloud_persistence(page):
    expect(page.locator('#start-overlay')).to_be_visible()
    assert page.locator('#workspace-frame').evaluate('(el) => el.inert')
    assert '7.5px' in page.locator('#start-overlay').evaluate('(el) => getComputedStyle(el).backdropFilter')
    screenshot(page, '01-start')
    page.locator('#start-open-case').click()
    expect(page.locator('#case-start')).to_be_disabled()
    screenshot(page, '02-case-modal')
    page.locator('[data-close=case-dialog]').click()
    create_case(page)
    for provider, label in [('apple', 'iCloud – Testperson A'), ('apple', 'iCloud – Testperson B'), ('google', 'Google – Testperson A'), ('microsoft', 'OneDrive – Testperson A')]:
        add_cloud(page, provider, label)
    expect(page.locator('.cloud-card')).to_have_count(4)
    for card in page.locator('.cloud-card').all():
        expect(card.get_by_role('button', name='Authentifizieren', exact=True)).to_be_disabled()
        expect(card.get_by_role('button', name='Sicherung starten', exact=True)).to_be_disabled()
    first = page.locator('.cloud-card').first
    first.get_by_role('button', name='Bezeichnung bearbeiten').click()
    expect(page.locator('#provider-choices input').first).to_be_disabled()
    page.locator('#cloud-form [name=label]').fill('iCloud – Umbenannt')
    page.locator('#cloud-submit').click()
    expect(page.locator('.cloud-card').first).to_contain_text('iCloud – Umbenannt')
    screenshot(page, '03-cloud-workspace')
    page.locator('#leave-case-button').click()
    expect(page.locator('#start-overlay')).to_be_visible()
    page.locator('#start-open-case').click()
    page.locator('#open-archive').click()
    page.get_by_role('button', name='Fall öffnen →').click()
    expect(page.locator('.cloud-card')).to_have_count(4)
    expect(page.locator('.cloud-card').first).to_contain_text('iCloud – Umbenannt')
    # A reload retains authentication but deliberately returns to the start screen.
    page.reload()
    expect(page.locator('#start-overlay')).to_be_visible()
    expect(page.locator('.cloud-card')).to_have_count(0)
    page.locator('#start-open-case').click()
    page.locator('#open-archive').click()
    page.get_by_role('button', name='Fall öffnen →').click()
    expect(page.locator('.cloud-card')).to_have_count(4)


def test_separate_admin_settings_and_logout_clears_sensitive_dom(page):
    create_case(page, 'admin')
    add_cloud(page, 'apple', 'SENSITIVE-SYNTHETIC-LABEL')
    expect(page.locator('#settings-dialog')).not_to_be_visible()
    page.locator('#open-settings').click()
    page.locator('#users-tab').click()
    expect(page.locator('#user-rows tr')).to_have_count(3)
    screenshot(page, '04-settings')
    page.locator('#rights-tab').click()
    expect(page.locator('#member-list')).to_contain_text('admin')
    page.locator('[data-pane=session]').click()
    page.locator('#logout-button').click()
    expect(page.locator('#start-overlay')).to_be_visible()
    # Even hidden nodes may not retain previous user's case/account identifiers.
    assert 'SENSITIVE-SYNTHETIC-LABEL' not in page.locator('body').text_content()
    assert 'SYNTHETIC-UI-2026' not in page.locator('body').text_content()
    assert not any(page.locator('input[type=password]').evaluate_all('(els) => els.map(el => el.value)'))
    expect(page.locator('#case-search')).to_have_value('')
    expect(page.locator('#login-form [name=username]')).to_have_value('')
    page.locator('#start-settings').click()
    expect(page.locator('#users-tab')).not_to_be_visible()


def test_viewer_can_open_but_not_modify_clouds(page):
    # Seed through migration role in isolated DB, never through production.
    with migration_connection() as db:
        alice = db.execute("SELECT id FROM users WHERE username='alice'").fetchone()['id']
        bob = db.execute("SELECT id FROM users WHERE username='bob'").fetchone()['id']
        case = db.execute("INSERT INTO cases(business_number,name,operator_initials,created_by) VALUES ('SYNTHETIC-VIEWER','Nur lesen','QA',%s) RETURNING id", (alice,)).fetchone()['id']
        db.execute("INSERT INTO case_members(case_id,user_id,access) VALUES (%s,%s,'viewer')", (case, bob))
        db.execute("INSERT INTO cloud_accounts(case_id,provider,label,created_by) VALUES (%s,'apple','Synthetisches Lesekonto',%s)", (case, alice))
    page.locator('#start-open-case').click()
    sign_in(page, 'bob')
    page.locator('#open-archive').click()
    page.get_by_role('button', name='Fall öffnen →').click()
    expect(page.locator('#add-cloud-button')).to_be_disabled()
    expect(page.locator('.cloud-rename')).to_be_disabled()
    expect(page.locator('.cloud-card')).to_have_count(1)
    page.locator('#open-settings').click()
    expect(page.locator('#users-tab')).not_to_be_visible()
    expect(page.locator('#edit-case-form button[type=submit]')).to_be_disabled()


def test_narrow_viewport_and_modal_keyboard_navigation(page):
    page.set_viewport_size({'width': 390, 'height': 844})
    page.locator('#start-open-case').click()
    expect(page.locator('#case-dialog')).to_be_visible()
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    screenshot(page, '05-mobile-case')
    page.keyboard.press('Escape')
    expect(page.locator('#case-dialog')).not_to_be_visible()
    expect(page.locator('#start-open-case')).to_be_focused()
