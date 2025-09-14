
set export

PYTHONPATH := "."
python_dir := if os_family() == "windows" { "./.venv/Scripts" } else { "./.venv/bin" }
python_exe := python_dir + if os_family() == "windows" { "/python.exe" } else { "/python" }

# Set up development environment
bootstrap:
    if test ! -e build/flake; then mkdir -p build/flake; fi
    if test ! -e build/docs; then mkdir -p build/docs; fi
    if test ! -e .venv; then python -m venv .venv; fi
    {{ python_exe }} -m pip install --upgrade pip wheel pip-tools
    {{ python_exe }} -m pip install -r requirements.txt


run CFG="./misc/crypt/dev_config_server.yaml":
    {{ python_exe }} -m tanglenomicon_data_api run --cfg {{CFG}}

adduser CFG="./misc/crypt/dev_config_server.yaml":
    {{ python_exe }} -m tanglenomicon_data_api adduser --cfg {{CFG}}

flake:
    if test ! -e build/flake; then mkdir -p build/flake; fi
    {{ python_exe }} -m flake8 --docstring-convention numpy --format=html --htmldir=build/flake/results

sphinx:
    if test ! -e build/docs; then mkdir -p build/docs; fi
    {{ python_exe }} {{ python_dir }}/sphinx-build -M html docs build/docs

cloc:
    mkdir -p docs/summary
    {{ python_exe }} {{ python_dir}}/pygount --format=summary  --suffix=md,py,yaml

pytest:
    {{ python_exe }} -m pytest

test: flake sphinx pytest cloc
    echo "Done"

live:
    {{ python_dir }}/sphinx-autobuild docs docs/build/html --port 8081

charm:
    sh pycharm ./


check-ruff:
    ruff check
    ruff format --check

do-ruff:
    ruff format

decrypt-sops:
    sops decrypt .sops/mongo.enc.yaml > .sops/mongo.yaml
    sops decrypt .sops/mongo_dev.enc.yaml > .sops/mongo_dev.yaml

encrypt-sops:
    sops encrypt .sops/mongo.yaml > .sops/mongo.enc.yaml
    sops encrypt .sops/mongo_dev.yaml > .sops/mongo_dev.enc.yaml