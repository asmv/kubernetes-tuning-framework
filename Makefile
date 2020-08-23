help:
	@printf "\
	See the README file for usage information.\n \
	\tbuild:\t\t builds all images used for experiments.\n \
	\tclean:\t\t removes still-active namespaces.\n \
	\tcreate_venv:\t makes a python environment for script execution if required. \
	\n"

build:
	./makefile_scripts/buildall.sh
	@echo "Built docker images for targets and clients."

clean:
	@for namespace in $$(./makefile_scripts/get_experiment_namespaces.sh); do \
		kubectl delete namespace --grace-period=0 --force $$namespace & \
	done

create_venv:
	python3.7 -m venv .env || python3 -m venv .env
	. .env/bin/activate
	.env/bin/python3 -m pip install -r services/coordinator/requirements.txt
	.env/bin/python3 -m pip install pylint rope