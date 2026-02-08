WORKFLOW = OpenRouter.alfredworkflow
FILES = info.plist icon.png main.py download_icon.py resources
VERSION := $(shell grep -m 1 'version =' pyproject.toml | cut -d '"' -f 2)

.PHONY: all build install check clean install-dev github-release

all: install

build: $(WORKFLOW)

$(WORKFLOW): $(FILES)
	zip -r $@ $(FILES)

install: $(WORKFLOW)
	open $(WORKFLOW)

check:
	pylint *.py
	mypy *.py
	pycodestyle *.py --max-line-length=120

clean:
	rm -f $(WORKFLOW)
	rm -rf .temp/alfred-openrouter
	rm -rf ~/Library/Caches/com.runningwithcrayons.Alfred/Workflow\ Data/com.alfred.openrouter/*

install-dev:
	pip install -e ".[dev]"

github-release:
	git push -f
	git tag v$(VERSION)
	git push origin v$(VERSION)




