.PHONY: setup test test-consumer lint check studio-smoke bradbury-deploy
VENV = .venv/bin

setup:
	python3 -m venv .venv && $(VENV)/pip install -r requirements-dev.txt
	# gltest direct mode needs a genvm release that ships genvm-universal.tar.xz;
	# the repo's "latest" (v0.3.0-rc7) does not, so pre-seed the pinned one:
	$(VENV)/python -c "from gltest.direct.sdk_loader import download_artifacts as d; d('v0.2.16')"

test:
	$(VENV)/python -m pytest -q

test-consumer:
	node --test consumer/decide.test.mjs consumer/read-verdict.test.mjs consumer/alert.test.mjs

# The contract pins the executor v0.3 runner shipped by Bradbury nodes (GenVM v0.6.0-rc10); genvm-lint has no
# SDK tarball for it, so the SDK semantic check runs on a copy with the v0.2.16 (`latest`) header, like the tests.
lint:
	$(VENV)/genvm-lint lint contracts/changelog_guard.py
	mkdir -p artifacts && sed '1s|py-genlayer:[a-z0-9]*|py-genlayer:latest|' contracts/changelog_guard.py > artifacts/changelog_guard.sdk-v02.py
	$(VENV)/genvm-lint validate artifacts/changelog_guard.sdk-v02.py

check: lint test test-consumer

studio-smoke:
	$(VENV)/python scripts/studio_smoke.py

bradbury-deploy:
	node scripts/bradbury.mjs deploy
