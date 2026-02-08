WORKFLOW = OpenRouter.alfredworkflow
BUNDLE_FILES = info.plist icon.png main.py download_icon.py
BUNDLE_DIRS = resources workflow
# Expand directories into individual files for proper dependency tracking
DEPS = $(BUNDLE_FILES) $(shell find $(BUNDLE_DIRS) -type f ! -path '*/__pycache__/*')
VERSION := $(shell grep -m 1 'version =' pyproject.toml | cut -d '"' -f 2)

.PHONY: all build install check clean install-dev sync-version github-release

all: install

build: $(WORKFLOW)

$(WORKFLOW): $(DEPS)
	zip -r $@ $(BUNDLE_FILES) $(BUNDLE_DIRS) -x '*__pycache__*'

install: $(WORKFLOW)
	open $(WORKFLOW)

check:
	pylint *.py workflow/*.py
	mypy *.py workflow/*.py
	ruff check *.py workflow/*.py
	plutil -lint info.plist

clean:
	rm -f $(WORKFLOW)
	rm -rf .temp/alfred-openrouter
	rm -rf __pycache__
	rm -rf workflow/__pycache__

install-dev:
	pip install -e ".[dev]"

sync-version:
	@sed -i '' 's|<string>[0-9]*\.[0-9]*\.[0-9]*</string><!-- version -->|<string>$(VERSION)</string><!-- version -->|' info.plist
	@echo "Version synced to $(VERSION)"

github-release: sync-version
	git add info.plist && git commit --amend --no-edit
	git push -f
	git tag v$(VERSION) -f
	git push origin v$(VERSION) -f
