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
    expect(page.locator('#start-open-case')).to_contain_text('Fall anlegen / öffnen')
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
    for provider,brand in [('apple','Apple iCloud'),('google','Google'),('microsoft','Microsoft')]:
        card=page.locator('.cloud-card[data-provider='+provider+']').first
        expect(card.get_by_role('img',name=brand,exact=True)).to_be_visible()
        assert card.locator('.provider-mark img').evaluate('(el) => el.complete && el.naturalWidth > 0')
        assert card.evaluate('(el) => getComputedStyle(el).boxShadow') != 'none'
    for card in page.locator('.cloud-card').all():
        expect(card.get_by_role('button', name='Anmelden', exact=True)).to_be_disabled()
        expect(card.get_by_role('button', name='Sicherung starten', exact=True)).to_be_disabled()
    first = page.locator('.cloud-card').first
    first.get_by_role('button', name='Bezeichnung bearbeiten').click()
    expect(page.locator('#provider-choices input').first).to_be_disabled()
    page.locator('#cloud-form [name=label]').fill('iCloud – Umbenannt')
    page.locator('#cloud-submit').click()
    expect(page.locator('.cloud-card').first).to_contain_text('iCloud – Umbenannt')
    # Approved design: exactly one full-width account per row, honest unavailable progress.
    expect(page.locator('#jobs-panel')).to_have_count(0)
    expect(page.locator('.status-disconnected')).to_have_count(4)
    expect(page.locator('.progress-track')).to_have_count(4)
    expect(page.locator('.progress-fill')).to_have_count(0)
    assert '%' not in page.locator('#cloud-list').inner_text()
    for width, height in [(1920, 1080), (1440, 900), (1280, 900)]:
        page.set_viewport_size({'width': width, 'height': height})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        container = page.locator('#cloud-list').bounding_box()
        previous_bottom = 0
        for card in page.locator('.cloud-card').all():
            bounds = card.bounding_box()
            assert abs(bounds['width'] - container['width']) <= 2
            assert abs(bounds['x'] - container['x']) <= 2
            assert bounds['y'] >= previous_bottom
            previous_bottom = bounds['y'] + bounds['height']
            expect(card.locator('.progress-track')).not_to_have_attribute('aria-valuenow')
        assert first.evaluate('(el) => getComputedStyle(el).backgroundColor') == 'rgb(25, 40, 60)'
        assert page.locator('body').evaluate('(el) => getComputedStyle(el).backgroundColor') == 'rgb(16, 26, 42)'
        assert float(first.locator('.cloud-name').evaluate('(el) => parseFloat(getComputedStyle(el).fontSize)')) >= 20
        screenshot(page, '08-final-desktop-' + str(width))
    page.set_viewport_size({'width': 390, 'height': 844})
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    screenshot(page, '09-final-mobile')
    page.set_viewport_size({'width': 1440, 'height': 900})
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
    page.locator('#add-user-button').click()
    page.locator('#user-form [name=username]').fill('synthetic-ui-user')
    page.locator('#user-form [name=initials]').fill('QA')
    page.locator('#user-form [name=password]').fill(PASSWORD)
    page.locator('#user-form button[type=submit]').click()
    expect(page.locator('#user-rows tr')).to_have_count(4)
    screenshot(page, '04-settings')
    page.locator('#rights-tab').click()
    expect(page.locator('#member-list')).to_contain_text('admin')
    with migration_connection() as db:
        bob = str(db.execute("SELECT id FROM users WHERE username='bob'").fetchone()['id'])
    page.locator('#member-user').select_option(bob)
    page.locator('#member-form [name=access]').select_option('viewer')
    page.locator('#member-form button[type=submit]').click()
    expect(page.locator('#member-list')).to_contain_text('bob / Lesen')
    page.locator('#member-list p').filter(has_text='bob / Lesen').get_by_role('button', name='Zugriff entziehen').click()
    expect(page.locator('#member-list')).not_to_contain_text('bob / Lesen')
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


def test_icloud_login_2fa_and_explicit_browsing_in_approved_ui(page, monkeypatch):
    """Synthetic provider responses only. Tests real browser/API/rights; no Apple claim."""
    from backend import cloud_auth
    connected = False
    calls = []
    monkeypatch.setattr(cloud_auth, 'available', lambda: True)
    def public_status(*args):
        return {'connection_status': 'connected' if connected else 'disconnected',
                'can_authenticate': True, 'can_browse': connected}
    def synthetic_perform(case_id, account_id, user_id, action, **data):
        nonlocal connected
        calls.append(action)
        if action == 'begin':
            assert data['apple_id'] == 'synthetic@example.invalid'
            assert data['password'] == 'Synthetic-Apple-Password'
            return {'status': 'challenge', 'challenge_id': 'Synthetic-Challenge-ID-Only', 'field': 'config_2fa', 'choices': []}
        if action == 'answer':
            assert data['answer'] == '123456'
            connected = True
            return {'status': 'connected'}
        if action == 'browse':
            return {'service': data['service'], 'path': data['path'], 'downloads_available': False,
                    'entries': [{'name': 'SYNTHETIC-Testordner', 'path': 'SYNTHETIC-Testordner', 'is_dir': True, 'size': -1}] if not data['path'] else []}
        if action == 'forget':
            connected = False
            return {'status': 'disconnected'}
        raise AssertionError(action)
    monkeypatch.setattr(cloud_auth, 'status', public_status)
    monkeypatch.setattr(cloud_auth, 'perform', synthetic_perform)
    create_case(page)
    add_cloud(page, 'apple', 'SYNTHETIC iCloud-Anmeldung')
    card = page.locator('.cloud-card').first
    card.get_by_role('button', name='Anmelden', exact=True).click()
    page.locator('#icloud-login-form [name=apple_id]').fill('synthetic@example.invalid')
    page.locator('#icloud-login-form [name=password]').fill('Synthetic-Apple-Password')
    screenshot(page, '10-icloud-login-synthetic')
    page.locator('#icloud-login-form button[type=submit]').click()
    expect(page.locator('#icloud-confirm-form')).to_be_visible()
    expect(page.locator('#icloud-login-form [name=password]')).to_have_value('')
    page.locator('#icloud-confirm-form [name=answer]').fill('123456')
    page.locator('#icloud-confirm-form button[type=submit]').click()
    expect(page.locator('#icloud-browser')).to_be_visible()
    expect(card.locator('.status-success')).to_have_text('Verbunden')
    assert 'browse' not in calls
    expect(card.get_by_role('button', name='Sicherung starten')).to_be_enabled()
    page.locator('#icloud-drive').click()
    expect(page.locator('#icloud-entries')).to_contain_text('SYNTHETIC-Testordner')
    screenshot(page, '11-icloud-browse-synthetic')
    page.locator('#icloud-entries').get_by_role('button', name='Öffnen').click()
    expect(page.locator('#icloud-path')).to_contain_text('SYNTHETIC-Testordner')
    page.locator('#icloud-forget').click()
    expect(page.locator('#icloud-dialog')).not_to_be_visible()
    expect(card.locator('.status-disconnected')).to_have_text('Nicht verbunden')
    assert calls == ['begin', 'answer', 'browse', 'browse', 'forget']
    expect(page.locator('#icloud-confirm-form [name=answer]')).to_have_value('')


def test_start_synthetic_acquisition_and_integrated_progress(page,monkeypatch):
    from backend import cloud_auth,acquisitions,evidence
    monkeypatch.setattr(evidence,"space",lambda *_:None)
    from test_acquisitions import Synthetic, adapter
    from uuid import UUID
    monkeypatch.setattr(cloud_auth,'status',lambda *_:{'connection_status':'connected','can_authenticate':True,'can_browse':True})
    first=threading.Event();second=threading.Event();download_release=threading.Event()
    class GrowingInventory(Synthetic):
        def inventory(self,*args):
            for i,entry in enumerate(super().inventory(*args)):
                if i==1: entry={**entry,'size':1024*1024}
                yield entry
                if i==0: assert first.wait(20), 'First inventory gate timed out'
                if i==1: assert second.wait(20), 'Second inventory gate timed out'
        def download(self,record,target,reserve,progress):
            if record['source_id']=='1':
                deadline=time.monotonic()+20;count=32768
                while not download_release.wait(.2):
                    count+=1024;target.write_bytes(b'x'*count);progress(count)
                    assert time.monotonic()<deadline, 'Download gate timed out'
            return super().download(record,target,reserve,progress)
    source=GrowingInventory();adapter(monkeypatch,source)
    create_case(page);add_cloud(page,'apple','SYNTHETIC Sicherung')
    card=page.locator('.cloud-card').first
    card.get_by_role('button',name='Sicherung starten',exact=True).click()
    expect(page.locator('#acquisition-dialog')).to_be_visible()
    page.locator('#acquisition-form [name=service]').select_option('drive')
    page.locator('#acquisition-form [name=path]').fill('SYNTHETIC-Testordner')
    page.locator('#acquisition-form button[type=submit]').click()
    expect(page.locator('#acquisition-dialog')).not_to_be_visible()
    expect(card.locator('.status-badge')).to_have_text('Wartet')
    with migration_connection() as db:job=db.execute('SELECT id,case_id FROM acquisitions').fetchone()
    # Background work continues while the browser navigates away from the application.
    worker=threading.Thread(target=acquisitions.run_job,args=(job['id'],));worker.start()
    try:
        expect(card.locator('.progress-summary')).to_contain_text('1 Dateien erfasst',timeout=15000)
        expect(card.locator('.transfer-metrics')).to_contain_text('1 Dateien geprüft',timeout=15000)
        expect(card.locator('.status-badge')).to_have_text('Erfassen und herunterladen')
        expect(card.locator('.acquisition-info')).to_contain_text('Dateierfassung läuft noch')
        page.set_viewport_size({'width':390,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.set_viewport_size({'width':1440,'height':900})
        first.set()
        expect(card.locator('.progress-summary')).to_contain_text('2 Dateien erfasst',timeout=15000)
        expect(card.locator('.transfer-metrics')).to_contain_text('1 von 4 Downloads aktiv',timeout=15000)
        expect(card.locator('.transfer-metrics')).to_contain_text(__import__('re').compile(r'Gesamtgeschwindigkeit: [1-9]'),timeout=15000)
        screenshot(page,'13-live-download-synthetic')
        download_release.set()
        expect(card.locator('.transfer-metrics')).to_contain_text('2 Dateien geprüft',timeout=15000)
        expect(card.locator('.transfer-metrics')).to_contain_text('Restzeit: —')
        page.goto('about:blank')
    finally:
        download_release.set();first.set();second.set();worker.join(timeout=20)
    assert not worker.is_alive()
    page.goto(URL)
    page.locator('#start-open-case').click()
    page.locator('#open-archive').click()
    page.get_by_role('button',name='Fall öffnen →').click()
    expect(page.locator('.cloud-card .status-badge')).to_have_text('Abgeschlossen')
    expect(page.locator('.transfer-metrics')).to_contain_text('8 Dateien geprüft')
    page.get_by_role('button',name='Sicherungsläufe',exact=True).click()
    expect(page.locator('#acquisition-history-dialog')).to_be_visible()
    expect(page.locator('#acquisition-history-list')).to_contain_text('Abgeschlossen')
    expect(page.get_by_role('link',name='Sicherungsbericht',exact=True)).to_have_attribute('href',f'/api/cases/{job["case_id"]}/acquisitions/{job["id"]}/report/bericht')
    page.locator('[data-close=acquisition-history-dialog]').click()
    for width,height in [(1920,1080),(1440,900),(390,844)]:
        page.set_viewport_size({'width':width,'height':height})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        screenshot(page,'12-acquisition-synthetic-'+str(width))

    # Successful OAuth returns directly to the authorized case, once only.
    page.evaluate("id => sessionStorage.setItem('fca-return-case', id)",str(job['case_id']))
    page.reload()
    expect(page.locator('#start-overlay')).not_to_be_visible()
    expect(page.locator('#active-case-number')).to_have_text('SYNTHETIC-UI-2026')
    assert page.evaluate("sessionStorage.getItem('fca-return-case')") is None


def test_combined_icloud_and_compact_md5_card(page,monkeypatch):
    from backend import cloud_auth,acquisitions,evidence
    from test_acquisitions import Synthetic,adapter
    monkeypatch.setattr(evidence,'space',lambda *_:None)
    monkeypatch.setattr(cloud_auth,'status',lambda *_:{'connection_status':'connected','can_authenticate':True,'can_browse':True})
    adapter(monkeypatch,Synthetic())
    create_case(page);add_cloud(page,'apple','SYNTHETIC Drive und Fotos')
    card=page.locator('.cloud-card').first
    card.get_by_role('button',name='Sicherung starten',exact=True).click()
    expect(page.locator('#acquisition-form [name=service]')).to_have_value('both')
    expect(page.locator('#scope-field')).not_to_be_visible()
    expect(page.locator('#acquisition-scope-note')).to_contain_text('getrennten Unterordnern')
    page.locator('#acquisition-form button[type=submit]').click()
    with migration_connection() as db:job=db.execute('SELECT id,category FROM acquisitions').fetchone()
    assert job['category']=='both'
    acquisitions.run_job(job['id'])
    expect(card.locator('.status-badge')).to_have_text('Abgeschlossen',timeout=15000)
    expect(card.locator('.transfer-metrics')).to_contain_text('MD5: 16 Dateien geprüft')
    assert card.inner_text().count('Dateien geprüft')==1
    assert 'Datenmenge:' not in card.inner_text()
    assert 'SHA-256:' not in card.inner_text()
    for width,height in [(1920,1080),(1440,900),(390,844)]:
        page.set_viewport_size({'width':width,'height':height})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        screenshot(page,'14-compact-cloud-'+str(width))


def test_pause_resume_controls_finish_a_real_background_job(page,monkeypatch):
    from backend import cloud_auth,acquisitions,evidence
    from test_acquisitions import Synthetic,adapter
    monkeypatch.setattr(evidence,'space',lambda *_:None)
    monkeypatch.setattr(cloud_auth,'status',lambda *_:{'connection_status':'connected','can_authenticate':True,'can_browse':True})
    started=threading.Event();release=threading.Event()
    class Waiting(Synthetic):
        def download(self,record,target,reserve,progress):
            started.set()
            while not release.wait(.1):progress(0)
            progress(0)
            super().download(record,target,reserve,progress)
    adapter(monkeypatch,Waiting())
    create_case(page);add_cloud(page,'apple','SYNTHETIC Pause und Fortsetzen')
    card=page.locator('.cloud-card').first
    card.get_by_role('button',name='Sicherung starten',exact=True).click()
    page.locator('#acquisition-form [name=service]').select_option('drive')
    page.locator('#acquisition-form button[type=submit]').click()
    with migration_connection() as db:job=db.execute('SELECT id FROM acquisitions').fetchone()
    worker=threading.Thread(target=acquisitions.run_job,args=(job['id'],));worker.start()
    try:
        assert started.wait(10)
        card.get_by_role('button',name='Pausieren',exact=True).click()
        expect(card.get_by_role('button',name='Fortsetzen',exact=True)).to_be_enabled(timeout=15000)
    finally:
        release.set();worker.join(15)
    assert not worker.is_alive()
    card.get_by_role('button',name='Fortsetzen',exact=True).click()
    expect(card.locator('.status-badge')).to_have_text('Wartet')
    adapter(monkeypatch,Synthetic());acquisitions.run_job(job['id'])
    expect(card.locator('.status-badge')).to_have_text('Abgeschlossen',timeout=15000)
