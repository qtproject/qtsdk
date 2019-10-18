print-%  : ; @echo $*=$($*)

PYTHON_VERSION := 3
PYTHON := python$(PYTHON_VERSION)
PIPENV := pipenv

first: pipenv

# common
test: pythontest

qtsdktest: first test

clean:
	rm -rf Pipfile.lock.sha1

# python

pythontest: pipenv
	env $(PIPENV) run stestr run

pipenv:
	hash $(PIPENV) 2>&1 || $(PYTHON) -m pip install --user $(PIPENV)
	sha1sum -c Pipfile.lock.sha1 || $(PIPENV) --python 3 sync --dev && sha1sum Pipfile.lock > Pipfile.lock.sha1

pipenv_sync:
	$(PIPENV) sync --dev
