appname = aa-memberaudit
package = memberaudit
myauth_path = ../myauth/manage.py

help:
	@echo "Makefile for $(appname)"

makemessages:
	cd $(package) && \
	django-admin makemessages \
		-l de \
		-l en \
		-l es \
		-l fr_FR \
		-l it_IT \
		-l ja \
		-l ko_KR \
		-l ru \
		-l uk \
		-l zh_Hans \
		--keep-pot \
		--ignore 'build/*'

tx_push:
	tx push --source

tx_pull:
	tx pull -f

compilemessages:
	cd $(package) && \
	django-admin compilemessages \
		-l de \
		-l en \
		-l es \
		-l fr_FR \
		-l it_IT \
		-l ja \
		-l ko_KR \
		-l ru \
		-l uk \
		-l zh_Hans

coverage:
#	coverage run --concurrency=multiprocessing $(myauth_path) test $(package).tests --keepdb --exclude-tag=breaks_with_aa4 --exclude-tag=breaks_with_py311 --timing --parallel && coverage combine && coverage html && coverage report -m
 	coverage run $(myauth_path) test $(package).tests -v 2 --keepdb --failfast --timing && coverage html && coverage report -m

coverage_single:
	coverage run $(myauth_path) test $(package).tests --keepdb --exclude-tag=breaks_with_aa4 --exclude-tag=breaks_with_py311 --exclude-tag=breaks_with_older_mariadb --timing && coverage html && coverage report -m

test:
	# runs a full test incl. re-creating of the test DB
	python $(myauth_path) test $(package).tests --failfast --timing --parallel -v 2

check_complexity:
	flake8 $(package) --max-complexity=10

flake8:
	flake8 $(package) --count

graph_models:
	python $(myauth_path) graph_models $(package) --arrow-shape normal -o $(appname)_models.png

create_testdata:
	python $(myauth_path) test $(package).tests.testdata.create_eveuniverse --keepdb -v 2
