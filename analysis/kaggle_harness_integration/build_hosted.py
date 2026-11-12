"""Bundle local adapter/controls into the standalone Kaggle task source."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
source = (HERE/'hosted_template.py').read_text()
source = source.replace('# ADAPTER_SOURCE', (HERE/'adapter.py').read_text())
source = source.replace('# CONTROLS_SOURCE', (HERE/'controls.py').read_text().split("if __name__ == '__main__':")[0])
compile(source, 'hosted_probe.py', 'exec')
(HERE/'hosted_probe.py').write_text(source)
print('Built hosted_probe.py')
