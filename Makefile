all: jupyter

setup:
	pip3 install -r ./requirements.txt

install:
	pip3 install .

install_editable:
	pip3 install --editable . --config-settings editable_mode=strict

jupyter:
	jupyter notebook ./example/two_node_eg.ipynb

test:
	pip3 install .
	pytest ./tests

test_combined:
	pip3 install .
	pytest ./tests/test_combined_functionality.py

vercel_setup:
	npm install -g vercel
	vercel login

supabase_setup:
	npm install -g supabase
	supabase login

datastack_setup:
	pip install datastack

minddb_setup:
	pip install minddb

superagi_setup:
	pip install superagi
