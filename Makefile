install-dev::
	pip install -r requirements-dev.txt

black::
	black .

flake::
	flake8 .

isort::
	isort .

pretty::
	black . && isort . && flake8 . --exclude=venv,.venv,env --ignore=E501

test-run::
	python -m test_src.whats_the_date