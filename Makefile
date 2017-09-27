build:
	rm -rf dist/*
	python setup.py sdist

distribute: build
	twine upload dist/*
