FROM rclone/rclone@sha256:2687085f718d3c628f7fdfb77c52a1d344332aed543110bb88088f2c70d43eb5 AS icloud-runtime

FROM python@sha256:73aa5faee130c60da030e105ec971ccf57473fbd22ce73bd6fc9ba99a40b838d AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY backend/requirements.lock /app/backend/requirements.lock
RUN pip install --no-cache-dir --root-user-action=ignore -r /app/backend/requirements.lock
COPY backend /app/backend
COPY providers /app/providers
COPY --from=icloud-runtime /usr/local/bin/rclone /usr/local/bin/rclone
USER 10001:10001
CMD ["uvicorn","backend.main:app","--host","0.0.0.0","--port","8000","--no-access-log","--proxy-headers","--forwarded-allow-ips=*","--limit-concurrency","24"]

FROM runtime AS test
USER root
COPY backend/requirements-test.lock /app/backend/requirements-test.lock
RUN pip install --no-cache-dir --root-user-action=ignore -r /app/backend/requirements-test.lock
COPY tests /app/tests
USER 10001:10001
CMD ["python","-m","pytest","-q","-p","no:cacheprovider","tests/test_phase1.py","tests/test_cloud_auth.py","tests/test_acquisitions.py"]

# Isolated browser validation only; never used by the application service.
FROM runtime AS browser-dependencies
USER root
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
COPY backend/requirements-browser.lock /app/backend/requirements-browser.lock
RUN pip install --no-cache-dir --root-user-action=ignore -r /app/backend/requirements-browser.lock && python -m playwright install --with-deps --only-shell chromium

FROM browser-dependencies AS browser-test
COPY backend/requirements-test.lock /app/backend/requirements-test.lock
RUN pip install --no-cache-dir --root-user-action=ignore -r /app/backend/requirements-test.lock
COPY tests /app/tests
COPY frontend /app/frontend
USER 10001:10001
CMD ["python","-m","pytest","-q","-p","no:cacheprovider","tests/test_browser.py"]

# Phase-2 development/test tooling only. Not part of the production API target.

FROM runtime AS icloud-adapter
COPY --from=icloud-runtime /usr/local/bin/rclone /usr/local/bin/rclone
COPY providers /app/providers
CMD ["python","-m","providers.apple.cli"]

FROM test AS icloud-adapter-test
COPY --from=icloud-runtime /usr/local/bin/rclone /usr/local/bin/rclone
COPY providers /app/providers
CMD ["python","-m","pytest","-q","-p","no:cacheprovider","tests/test_icloud_adapter.py"]
