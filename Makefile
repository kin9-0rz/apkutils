twine: dist
	twine upload dist/*
dist:
	python3 setup.py sdist
	python3 setup.py bdist_wheel
	ls -l dist
install:
	python3 setup.py install